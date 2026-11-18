"""Matriz de cierre de GUI en subprocesos, con límite externo de seguridad para las pruebas."""
import json,os,signal,subprocess,sys,time
from pathlib import Path

out=Path('results/audio_lifecycle');out.mkdir(exist_ok=True)
rows=[]
for case,device in [('real',None),('real',0),('error',None),('opening',None),('closing',None),('wav',None),('probe-opening',None)]:
    name=case+('fixed0' if device==0 else '')
    report_path=out/(name+'.json')
    command=[sys.executable,'scripts/comprobar_cierre_audio.py','--case',case,'--output',str(report_path)]
    if device is not None:command+=['--device',str(device)]
    start=time.monotonic()
    p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    forced=False
    try:
        output,_=p.communicate(timeout=32)
    except subprocess.TimeoutExpired:
        forced=True
        os.killpg(p.pid,signal.SIGTERM)
        try:output,_=p.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);output,_=p.communicate(timeout=2)
    (out/(name+'.log')).write_text(output)
    row={'case':name,'exit_code':p.returncode,'elapsed':time.monotonic()-start,'outer_forced':forced}
    if report_path.exists():
        detail=json.loads(report_path.read_text())
        row['close_seconds']=detail['close_seconds']
        row['audio_opened']='device' in detail['observed']
        row['failures']=detail['failures']
    rows.append(row);print(json.dumps(row),flush=True)
    if p.returncode:print(output[-2000:],flush=True)
(out/'summary.json').write_text(json.dumps(rows,indent=2))
if any(row['exit_code'] or row['outer_forced'] for row in rows):raise SystemExit(1)
