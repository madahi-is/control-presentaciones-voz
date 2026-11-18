import queue
import sys
import threading
import time
from types import SimpleNamespace
import numpy as np
from vozslides.common import config
from vozslides.live import Microphone
from vozslides.rendering import PageImages


def test_page_cache_reuses_projection_for_preview():
    import pymupdf
    with pymupdf.open('assets/demo.pdf') as doc:
        cache=PageImages(capacity=2)
        full=cache.get(doc[0],1366,768)
        for _ in range(10):
            preview=cache.get(doc[0],700,400)
        assert cache.rasterizations==1
        assert full.width>preview.width
        cache.get(doc[1],700,400);cache.get(doc[2],700,400)
        assert len(cache.images)==2
        cache.clear();assert not cache.images


def test_capture_keeps_delivering_levels_while_cnn_is_busy(monkeypatch):
    # Fuente y CNN de prueba: no accede a hardware ni sustituye el modelo del producto.
    entered=threading.Event();release=threading.Event()
    class Predictor:
        cfg=config()
        info={'threshold':.8}
        def predict(self,audio,rate):
            entered.set();release.wait(2)
            return 'right',.95
    import base64
    class Backend:
        def __init__(self,**kwargs):
            self.messages=queue.Queue();self.done=threading.Event()
        def start(self):
            self.messages.put({'kind':'opened','value':{'samplerate':16000,'name':'entrada de prueba'}})
            def produce():
                for i in range(200):
                    if self.done.is_set():break
                    level=.1 if 3<=i<11 else 0.
                    audio=np.full(640,level,dtype=np.float32)
                    self.messages.put({'kind':'chunk','value':base64.b64encode(audio.tobytes()).decode()})
                    self.done.wait(.01)
            self.producer=threading.Thread(target=produce,daemon=True);self.producer.start()
        def read(self,timeout):return self.messages.get(timeout=timeout)
        def close(self):
            self.done.set();self.producer.join(1)
            return {'forced':False}
    events=queue.Queue();mic=Microphone(Predictor(),events,session=7,backend_factory=Backend)
    mic.start()
    try:
        assert entered.wait(1), 'Debe iniciarse la inferencia'
        while not events.empty():events.get_nowait()
        deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            _,(session,kind,value)=events.get(timeout=.3)
            if kind=='level':
                assert session==7
                assert not release.is_set(), 'El nivel debe actualizarse antes de terminar la CNN'
                break
        else:raise AssertionError('La captura quedó bloqueada por la inferencia')
    finally:
        mic.stop();release.set();mic.thread.join(1)
    assert not mic.thread.is_alive()


def test_unchecked_fullscreen_does_not_create_projection():
    from vozslides.presentation import PresentationWindow
    # No se proporciona un root: crear un Toplevel aquí sería un fallo.
    projection=PresentationWindow(None,lambda:None,lambda:None,lambda:None,
                                  lambda:None,lambda:None,lambda *args:None)
    for _ in range(3):
        projection.show(fullscreen=False)
        assert projection.window is None and projection.photo is None
        assert projection.resize_job is None
