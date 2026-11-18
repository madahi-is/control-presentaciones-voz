import queue
import sys
import threading
import time
from pathlib import Path
import pytest
from vozslides.audio_backend import AudioProcess,probe_inputs
from vozslides.audio_worker import settings
from vozslides.common import config
from vozslides.live import Microphone

FIXTURE=Path(__file__).parent/'fixtures/audio_child.py'
class Predictor:
    cfg=config()
    info={'threshold':.8}
    def predict(self,*args):raise AssertionError('No se espera voz en estas pruebas')

def backend(mode):
    return lambda **kwargs:AudioProcess(command=[sys.executable,str(FIXTURE),mode])

@pytest.mark.parametrize('mode',['active','error','opening','closing'])
def test_microphone_stops_even_if_native_audio_would_hang(mode):
    events=queue.Queue();mic=Microphone(Predictor(),events,backend_factory=backend(mode),open_timeout=.4)
    mic.start()
    try:
        # Espera a que el hijo realmente abra o anuncie el intento de apertura.
        deadline=time.monotonic()+2
        observed=[]
        while time.monotonic()<deadline:
            _,(_,kind,value)=events.get(timeout=1)
            observed.append(kind)
            if kind in ('device','attempt','error'):break
        start=time.monotonic();mic.stop();mic.thread.join(2)
        assert not mic.thread.is_alive()
        assert mic.shutdown_complete.is_set()
        assert time.monotonic()-start<2
        assert mic.backend.process.poll() is not None
    finally:
        mic.stop();mic.thread.join(2)
        if mic.backend:mic.backend.close()


def test_open_timeout_emits_error_and_exits():
    events=queue.Queue();mic=Microphone(Predictor(),events,backend_factory=backend('opening'),open_timeout=.25)
    mic.start();mic.thread.join(2)
    try:
        assert not mic.thread.is_alive()
        messages=[]
        while not events.empty():messages.append(events.get_nowait()[1])
        assert any(kind=='error' and 'apertura' in value for _,kind,value in messages)
        assert any(kind=='stopped' for _,kind,value in messages)
        assert mic.backend.process.poll() is not None
    finally:
        mic.stop();mic.backend.close()


def test_device_enumeration_timeout_is_bounded():
    start=time.monotonic()
    with pytest.raises(RuntimeError,match='búsqueda'):
        probe_inputs(threading.Event(),timeout=.2,backend_factory=backend('opening'))
    assert time.monotonic()-start<2


def test_mono_rejection_can_choose_valid_stereo_without_changing_device():
    from types import SimpleNamespace
    attempts=[]
    def check(**kw):
        attempts.append(kw)
        if kw['channels']==1:raise ValueError('Formato mono no soportado')
    sd=SimpleNamespace(query_devices=lambda *a:{'name':'ALC','default_samplerate':48000,'max_input_channels':2},check_input_settings=check)
    result,_=settings(sd,3,'ALC')
    assert result==dict(device=3,samplerate=48000,channels=2,dtype='float32',blocksize=0,latency='high')
    assert [x['channels'] for x in attempts]==[1,2]


def test_stale_index_resolves_same_name_and_does_not_switch_microphone():
    from types import SimpleNamespace
    entry={'name':'ALC','default_samplerate':44100,'max_input_channels':2}
    def query(*args):
        if args:raise ValueError('Índice obsoleto')
        return [entry]
    sd=SimpleNamespace(query_devices=query,check_input_settings=lambda **kw:None)
    result,_=settings(sd,10,'ALC')
    assert result['device']==0
    with pytest.raises(RuntimeError,match='ya no está disponible'):
        settings(sd,10,'otro micrófono')
