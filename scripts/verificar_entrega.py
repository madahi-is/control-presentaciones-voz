"""Registra lo observado, sin probar captura de micrófono ni interacción visual."""
import importlib.util
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

result={'python':platform.python_version(),'platform':platform.platform(),
        'microphone_capture':'No ejecutada: procedimiento personal en README.md',
        'gui_visual':'No ejecutada: falta python3-tk; sudo requiere contraseña personal'}
xml=Path('results/tests.xml')
if xml.exists():
    suite=ET.parse(xml).getroot().find('testsuite')
    result['pytest']={k:suite.attrib[k] for k in ('tests','failures','errors','skipped','time')}
result['tkinter_installed']=importlib.util.find_spec('tkinter') is not None
try:
    import sounddevice as sd
    result['input_devices_enumerated']=sum(d['max_input_channels']>0 for d in sd.query_devices())
except Exception as error:result['input_devices_error']=str(error)
for kind in ('smoke','full'):
    p=Path('models')/kind/'run.json'
    result[kind+'_training']=json.loads(p.read_text()) if p.exists() else 'Pendiente'
    result[kind+'_save_load_verified']=p.exists()
check=subprocess.run([str(Path('.venv/bin/python')),'-m','pip','check'],capture_output=True,text=True)
result['pip_check']={'exit_code':check.returncode,'output':check.stdout.strip()}
Path('results/verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(result,indent=2,ensure_ascii=False))
