"""Supervisión acotada de PortAudio; este módulo NO importa sounddevice."""
import json
import os
import queue
import subprocess
import sys
import threading
import time


class AudioProcess:
    def __init__(self, device=None, expected_name=None, mode="capture", command=None):
        self.command = command or [sys.executable, "-m", "vozslides.audio_worker", mode]
        if command is None and device is not None:
            self.command += ["--device", str(device)]
        if command is None and expected_name:
            self.command += ["--expected-name", expected_name]
        self.process = None
        self.messages = queue.Queue(maxsize=128)
        self.cleanup = None

    def start(self):
        environment=os.environ.copy()
        environment.update(OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1")
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=None, text=True, encoding="utf-8", bufsize=1,env=environment)
        threading.Thread(target=self._read, daemon=True, name="audio-ipc").start()

    def _put(self, message):
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            try:
                self.messages.put_nowait(message)
            except queue.Full:
                pass

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self._put(json.loads(line))
                except ValueError:
                    self._put({"kind":"error", "value":"Respuesta inválida del proceso de audio"})
        except (OSError, ValueError):
            pass
        finally:
            self.process.stdout.close()
            self._put({"kind":"exit", "value":None})

    def read(self, timeout=.1):
        return self.messages.get(timeout=timeout)

    def close(self):
        """Solo en un supervisor, nunca dentro de un callback Tk. Esperas limitadas."""
        if self.cleanup is not None:
            return self.cleanup
        process = self.process
        forced = False
        if process is not None:
            try:
                if process.poll() is None:
                    try:
                        process.stdin.write("stop\n")
                        process.stdin.flush()
                    except (OSError, ValueError):
                        pass
                    try:
                        process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        forced = True
                        process.terminate()
                        try:
                            process.wait(timeout=.4)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            try:
                                process.wait(timeout=.4)
                            except subprocess.TimeoutExpired:
                                pass  # Ni siquiera una espera kernel debe retener Tk.
            finally:
                if process.stdin:
                    try:process.stdin.close()
                    except (OSError, ValueError):pass
                # stdout lo cierra su lector al recibir EOF; no contender con readline.
        self.cleanup = {"pid":process.pid if process else None,
                        "returncode":process.poll() if process else None,
                        "forced":forced}
        return self.cleanup


def probe_inputs(stop_event, timeout=5., backend_factory=AudioProcess):
    backend = backend_factory(mode="devices")
    try:
        backend.start()
        deadline = time.monotonic()+timeout
        while not stop_event.is_set():
            if time.monotonic()>deadline:
                raise RuntimeError("La búsqueda de micrófonos excedió 5 s. Actualiza las entradas o revisa el audio del sistema.")
            try:
                message = backend.read(.1)
            except queue.Empty:
                continue
            if message["kind"]=="devices":
                return message["value"]
            if message["kind"] in ("error", "exit"):
                raise RuntimeError(message.get("value") or "El proceso de audio terminó sin enumerar entradas")
        return None
    finally:
        backend.close()
