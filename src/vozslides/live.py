"""Segmentación energética, una inferencia por pronunciación; sin acceso a Tk."""
import queue
import threading
import time
from collections import deque
import numpy as np
from .audio import rms, waveform
from .control import Gate

class Microphone:
    def __init__(self,predictor,events,device=None):
        self.predictor,self.events,self.device=predictor,events,device
        self.stop_event=threading.Event()
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            import sounddevice as sd
            cfg=self.predictor.cfg
            device_info=sd.query_devices(self.device,"input")
            rate=int(device_info["default_samplerate"])
            block=int(rate*.04)
            chunks=queue.Queue(maxsize=50)
            overflow=threading.Event()
            def callback(indata,frames,timing,status):
                if status:
                    overflow.set()
                try:
                    chunks.put_nowait(indata[:,0].copy())
                except queue.Full:
                    overflow.set()
            gate=Gate(self.predictor.info["threshold"],cfg["silence_rms"],cfg["cooldown_seconds"])
            pre=deque(maxlen=3); utterance=[]; quiet=0; locked=False
            with sd.InputStream(samplerate=rate,blocksize=block,channels=1,dtype="float32",device=self.device,callback=callback):
                self.events.put(("status","Micrófono activo. Esc: detener escucha"))
                while not self.stop_event.is_set():
                    if overflow.is_set():
                        overflow.clear();utterance=[];quiet=0;locked=False;pre.clear()
                        while not chunks.empty():
                            try:chunks.get_nowait()
                            except queue.Empty:break
                        self.events.put(("status","Audio descartado por desbordamiento; vuelve a pronunciar"))
                    try:chunk=chunks.get(timeout=.1)
                    except queue.Empty:continue
                    silent=rms(chunk)<cfg["silence_rms"]
                    if locked:
                        quiet=quiet+1 if silent else 0
                        if quiet*40>=cfg["release_ms"]:
                            locked=False;quiet=0;pre.clear()
                        continue
                    if not utterance:
                        pre.append(chunk)
                        if silent:continue
                        utterance=list(pre);pre.clear();quiet=0
                    else:
                        utterance.append(chunk);quiet=quiet+1 if silent else 0
                    # Evita repetir una frase larga: bloqueado hasta nuevo silencio.
                    forced=len(utterance)*.04>=1.4
                    if quiet*40>=cfg["release_ms"] or forced:
                        audio=np.concatenate(utterance)
                        # Retira silencio final para centrar la palabra en la ventana de 1 s.
                        if quiet and len(audio)>quiet*block:
                            audio=audio[:-quiet*block]
                        word,confidence=self.predictor.predict(audio,rate)
                        accepted,reason=gate.accept(confidence,rms(waveform(audio,rate,cfg)),time.monotonic())
                        if not self.stop_event.is_set():
                            self.events.put(("prediction",(word,confidence,accepted,reason)))
                        utterance=[];quiet=0;locked=forced
        except Exception as error:
            self.events.put(("error",str(error)))
        finally:
            self.events.put(("stopped",None))
