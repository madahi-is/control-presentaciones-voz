"""Único propietario de sounddevice/PortAudio, ejecutado fuera de Tk y TensorFlow."""
import argparse
import base64
import json
import os
import queue
import sys
import threading


def send(kind, value=None):
    print(json.dumps({"kind":kind,"value":value},ensure_ascii=False),flush=True)


def devices(sd):
    inputs = [{"index":i,"name":d["name"],"hostapi":d["hostapi"],
               "max_input_channels":d["max_input_channels"],
               "default_samplerate":d["default_samplerate"]}
              for i,d in enumerate(sd.query_devices()) if d["max_input_channels"]>0]
    return {"inputs":inputs,"default_input":int(sd.default.device[0]),
            "sounddevice":sd.__version__,"portaudio":sd.get_portaudio_version()[1]}


def settings(sd, device, expected_name=None):
    try:
        info = sd.query_devices(device,"input")
    except Exception:
        if not expected_name:raise
        info=None
    if expected_name and (info is None or info["name"]!=expected_name):
        matches=[(i,d) for i,d in enumerate(sd.query_devices())
                 if d["name"]==expected_name and d["max_input_channels"]>0]
        if len(matches)!=1:
            raise RuntimeError(f"La entrada seleccionada '{expected_name}' ya no está disponible con ese índice. Pulsa Actualizar entradas y selecciona el micrófono físico.")
        device,info=matches[0]  # Mismo nombre, nunca cambiar a otro micrófono silenciosamente.
    rates = list(dict.fromkeys([int(info["default_samplerate"]),48000,44100,16000]))
    channels = [1] + ([2] if info["max_input_channels"]>=2 else [])
    failures = []
    for rate in rates:
        for count in channels:
            parameters = dict(device=device,samplerate=rate,channels=count,dtype="float32")
            send("attempt",{**parameters,"name":info["name"],"blocksize":0,"latency":"high"})
            try:
                sd.check_input_settings(**parameters)
                return {**parameters,"blocksize":0,"latency":"high"}, info
            except Exception as error:
                failures.append(f"{rate} Hz/{count} canal(es): {error}")
    raise RuntimeError("No hay formato de entrada compatible: "+"; ".join(failures))


def capture(sd, device, expected_name, stop):
    import numpy as np
    stream = None
    chunks = queue.Queue(maxsize=32)
    overflow = threading.Event()
    def callback(indata, frames, timing, status):
        if status:
            overflow.set()
        try:
            chunks.put_nowait(indata.copy())
        except queue.Full:
            overflow.set()
    try:
        parameters, info = settings(sd, device, expected_name)
        if stop.is_set():return
        stream = sd.InputStream(callback=callback,**parameters)
        if stop.is_set():return
        stream.start()
        send("opened",{**parameters,"name":info["name"]})
        while not stop.is_set():
            if overflow.is_set():
                overflow.clear();send("overflow")
            try:
                chunk = chunks.get(timeout=.1)
            except queue.Empty:
                continue
            mono = chunk.mean(axis=1).astype("float32",copy=False)
            send("chunk",base64.b64encode(mono.tobytes()).decode("ascii"))
    finally:
        if stream is not None:
            try:
                stream.abort()  # Captura: no esperar a vaciar un stream al cerrar.
            finally:
                stream.close()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["devices","capture"])
    parser.add_argument("--device",type=int)
    parser.add_argument("--expected-name")
    args=parser.parse_args()
    stop=threading.Event()
    def commands():
        os.read(sys.stdin.fileno(), 1024)
        stop.set()
    threading.Thread(target=commands,daemon=True).start()
    try:
        import sounddevice as sd  # Incluye Pa_Initialize y atexit solo en este proceso.
        if args.mode=="devices":
            send("devices",devices(sd))
        elif not stop.is_set():
            capture(sd,args.device,args.expected_name,stop)
    except Exception as error:
        send("error",f"No se pudo abrir/utilizar el micrófono: {error}. Selecciona otra entrada o revisa permisos y disponibilidad del dispositivo.")
    finally:
        send("ended")

if __name__=="__main__":main()
