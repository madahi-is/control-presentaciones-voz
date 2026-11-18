"""Consolida evidencia existente y comprueba dependencias, sin activar audio."""
import importlib.util
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def read(path):
    p=Path(path)
    return json.loads(p.read_text()) if p.exists() else None

result={'python':platform.python_version(),'platform':platform.platform(),
        'tkinter_installed':importlib.util.find_spec('tkinter') is not None,
        'controlled_human_voice_accuracy':'Pendiente: no medida con frases humanas controladas'}
xml=Path('results/tests.xml')
if xml.exists():
    suite=ET.parse(xml).getroot().find('testsuite')
    result['pytest']={k:suite.attrib[k] for k in ('tests','failures','errors','skipped','time')}
ui=read('results/ui_verification.json')
result['gui_visual']=ui or 'Sin registro de prueba visual'
life=read('results/audio_lifecycle/summary.json')
result['audio_lifecycle']=life or 'Sin registro de secuencia activar/cerrar'
real=[]
for name in ('real','realfixed0'):
    report=read('results/audio_lifecycle/'+name+'.json')
    if report and report['observed'].get('device'):
        real.append({'settings':report['observed']['device'],
                     'levels':report['observed'].get('levels',0),
                     'close_seconds':report['close_seconds'],
                     'audio_processes':report['audio_processes']})
result['microphone_capture']=real or 'Sin registro de entrada real abierta'
devices=read('results/audio_lifecycle/devices.json')
if devices:result['input_devices_in_saved_snapshot']=len(devices['inputs'])
for kind in ('smoke','full'):
    run=read('models/'+kind+'/run.json')
    result[kind+'_training']=run or 'Pendiente'
    result[kind+'_save_load_verified']=bool(run)
check=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True,timeout=30)
result['pip_check']={'exit_code':check.returncode,'output':check.stdout.strip()}
Path('results/verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print('results/verification.json actualizado con evidencia de archivos, GUI y cierre de audio')
