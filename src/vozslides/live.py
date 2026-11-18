"""Captura aislada en proceso; segmentación e inferencia supervisadas en segundo plano."""
import base64
import queue
import threading
import time
import numpy as np
from .audio import rms, waveform
from .audio_backend import AudioProcess
from .control import Gate, command_action
from .segmentation import Segmenter, noise_threshold


class Microphone:
    def __init__(self,predictor,events,device=None,calibrate=False,session=None,
                 expected_name=None,backend_factory=AudioProcess,open_timeout=8.):
        self.predictor,self.events,self.device=predictor,events,device
        self.calibrate,self.session=calibrate,session
        self.expected_name=expected_name
        self.backend_factory=backend_factory
        self.open_timeout=open_timeout
        self.stop_event=threading.Event()
        self.shutdown_complete=threading.Event()
        self.thread=None
        self.backend=None

    def emit(self,kind,value):
        self.events.put(("microphone",(self.session,kind,value)))

    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True,name="microphone-supervisor")
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _opened(self):
        deadline=time.monotonic()+self.open_timeout
        while not self.stop_event.is_set():
            if time.monotonic()>deadline:
                raise RuntimeError("La apertura del micrófono excedió 8 s. Prueba otra entrada; el audio se ha cancelado.")
            try:message=self.backend.read(.1)
            except queue.Empty:continue
            kind,value=message["kind"],message.get("value")
            if kind=="opened":return value
            if kind=="attempt":self.emit("attempt",value)
            elif kind in ("error","exit","ended"):
                raise RuntimeError(value or "El proceso de audio terminó antes de abrir el micrófono")
        return None

    def run(self):
        inference=None
        try:
            self.backend=self.backend_factory(device=self.device,expected_name=self.expected_name)
            if self.stop_event.is_set():return
            self.backend.start()
            opened=self._opened()
            if opened is None:return
            rate=int(opened["samplerate"])
            self.emit("device",opened)
            cfg=self.predictor.cfg
            threshold=cfg["silence_rms"]
            segmenter=Segmenter(rate,threshold,cfg["release_ms"])
            gate=Gate(self.predictor.info["threshold"],threshold,cfg["cooldown_seconds"])
            pending=queue.Queue(maxsize=1)
            def infer():
                while not self.stop_event.is_set():
                    try:audio,captured=pending.get(timeout=.1)
                    except queue.Empty:continue
                    if self.stop_event.is_set():return
                    if time.monotonic()-captured>1.5:
                        self.emit("status","Pronunciación atrasada descartada; vuelve a hablar");continue
                    try:
                        word,confidence=self.predictor.predict(audio,rate)
                        if self.stop_event.is_set():return
                        if time.monotonic()-captured>1.5:
                            self.emit("status","Inferencia tardía descartada; vuelve a pronunciar");continue
                        accepted,reason=gate.accept(confidence,rms(waveform(audio,rate,cfg)),time.monotonic(),
                            consume=command_action(word,cfg["classes"]) is not None)
                        self.emit("prediction",(word,confidence,accepted,reason))
                    except Exception as error:
                        self.emit("error",str(error));self.stop_event.set();return
            inference=threading.Thread(target=infer,daemon=True,name="microphone-inference")
            inference.start()
            self.emit("status","Guarda silencio durante 2 segundos…" if self.calibrate else "Escuchando · pronuncia una palabra y haz una pausa")
            calibrating=self.calibrate
            levels=[];buffer=np.empty(0,dtype=np.float32)
            block=int(rate*.04)
            last_chunk=time.monotonic();last_level=0.
            while not self.stop_event.is_set():
                try:message=self.backend.read(.1)
                except queue.Empty:
                    if time.monotonic()-last_chunk>3:
                        raise RuntimeError("El dispositivo no entrega audio. Prueba otra entrada de micrófono.")
                    continue
                kind,value=message["kind"],message.get("value")
                if kind in ("error","exit","ended"):
                    raise RuntimeError(value or "La captura de audio se interrumpió")
                if kind=="overflow":
                    segmenter.reset();levels.clear();buffer=np.empty(0,dtype=np.float32)
                    self.emit("status","Audio descartado por desbordamiento; vuelve a pronunciar")
                    continue
                if kind!="chunk":continue
                chunk=np.frombuffer(base64.b64decode(value),dtype=np.float32)
                last_chunk=time.monotonic()
                buffer=np.concatenate((buffer,chunk))
                while len(buffer)>=block and not self.stop_event.is_set():
                    chunk,buffer=buffer[:block],buffer[block:]
                    energy=rms(chunk);now=time.monotonic()
                    if now-last_level>=.1:
                        self.emit("level",(energy,threshold));last_level=now
                    if calibrating:
                        levels.append(energy)
                        if len(levels)>=50:
                            threshold,noise=noise_threshold(levels,cfg["silence_rms"])
                            segmenter.threshold=threshold;calibrating=False
                            self.emit("calibrated",(threshold,noise))
                            self.emit("status","Escuchando · calibración terminada")
                        continue
                    audio=segmenter.feed(chunk)
                    if audio is None:continue
                    try:pending.put_nowait((audio,time.monotonic()))
                    except queue.Full:
                        self.emit("status","Modelo ocupado: pronunciación descartada; espera un momento")
        except Exception as error:
            if not self.stop_event.is_set():self.emit("error",str(error))
        finally:
            self.stop_event.set()
            try:
                if self.backend is not None:
                    cleanup=self.backend.close()
                    if cleanup and cleanup.get("forced"):
                        self.emit("cleanup",cleanup)
                if inference is not None:inference.join(timeout=.15)
            finally:
                self.shutdown_complete.set()
                self.emit("stopped",None)
