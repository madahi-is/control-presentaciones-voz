"""Proceso de fallo controlado para pruebas; nunca usado por vozslides gui normal."""
import base64,json,os,signal,sys,threading,time

def send(kind,value=None):print(json.dumps({'kind':kind,'value':value}),flush=True)
mode=sys.argv[1]
settings={'device':0,'name':'entrada de prueba','samplerate':16000,'channels':1,'dtype':'float32','blocksize':0,'latency':'high'}
if mode=='devices':
    send('devices',{'inputs':[{'index':0,'name':'entrada de prueba','max_input_channels':1,'default_samplerate':16000,'hostapi':0}],'default_input':0,'sounddevice':'fixture','portaudio':'fixture'})
    raise SystemExit(0)
if mode=='error':
    send('attempt',settings);send('error','ALSA: fallo controlado al abrir el micrófono');raise SystemExit(0)
if mode=='opening':
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    send('attempt',settings)
    while True:time.sleep(.1)
stop=threading.Event()
def commands():os.read(0,1024);stop.set()
threading.Thread(target=commands,daemon=True).start()
if mode=='closing':signal.signal(signal.SIGTERM,signal.SIG_IGN)
send('opened',settings)
if mode=='wav':
    import numpy as np
    from vozslides.audio import read_audio,waveform
    from vozslides.common import config
    x,rate=read_audio(sys.argv[2]);x=waveform(x,rate,config())
    x=np.pad(x,(3200,6400))
    for i in range(0,len(x),640):
        if stop.is_set():break
        send('chunk',base64.b64encode(x[i:i+640].tobytes()).decode())
        stop.wait(.04)
while not stop.is_set():
    send('chunk',base64.b64encode(bytes(640*4)).decode());stop.wait(.04)
if mode=='closing':
    while True:time.sleep(.1)
send('ended')
