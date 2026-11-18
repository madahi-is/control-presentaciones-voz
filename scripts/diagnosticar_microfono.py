"""Diagnóstico aislado y con plazos: no guarda audio ni importa PortAudio en este proceso."""
import argparse,base64,json,queue,threading,time
from vozslides.audio_backend import AudioProcess,probe_inputs

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--device',type=int)
parser.add_argument('--seconds',type=int,default=3,choices=range(1,11))
parser.add_argument('--list',action='store_true')
parser.add_argument('--output')
args=parser.parse_args()
backend=None
report={}
try:
    if args.list:
        report=probe_inputs(threading.Event())
    else:
        import numpy as np
        backend=AudioProcess(device=args.device)
        backend.start();opened=False;levels=[];deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            try:message=backend.read(.1)
            except queue.Empty:continue
            kind,value=message['kind'],message.get('value')
            if kind=='attempt':print('Intento:',json.dumps(value,ensure_ascii=False),flush=True)
            elif kind=='opened':
                opened=True;report['settings']=value
                print(f"Habla durante {args.seconds} segundos. No se guardará audio.",flush=True)
                deadline=time.monotonic()+args.seconds
            elif kind=='chunk':
                x=np.frombuffer(base64.b64decode(value),dtype=np.float32)
                levels.append(float(np.sqrt(np.mean(x.astype(np.float64)**2))))
            elif kind in ('error','exit','ended'):raise RuntimeError(value or 'El proceso de audio terminó')
        if not opened:raise RuntimeError('La apertura del micrófono excedió 8 s')
        if not levels:raise RuntimeError('La entrada abrió pero no entregó muestras')
        report.update(blocks=len(levels),rms_max=max(levels),blocks_over_0_008=sum(v>=.008 for v in levels),
                      audio_saved=False,scope='Nivel de señal; no evalúa reconocimiento de palabras')
except Exception as error:
    report['error']=str(error)
finally:
    if backend is not None:report['cleanup']=backend.close()
if args.output:
    from pathlib import Path
    Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps(report,indent=2,ensure_ascii=False))
if 'error' in report:raise SystemExit(1)
