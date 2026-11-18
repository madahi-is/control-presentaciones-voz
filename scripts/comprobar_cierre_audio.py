"""Reproduce vozslides gui → activar escucha → cerrar. Fallos solo mediante fixtures explícitas."""
import argparse
import json
from pathlib import Path
import runpy
import sys
import threading
import time
import tkinter as tk

from vozslides.audio_backend import AudioProcess
from vozslides import audio_backend,live

parser=argparse.ArgumentParser()
parser.add_argument('--case',choices=['real','error','opening','closing','wav','probe-opening'],default='real')
parser.add_argument('--device',type=int)
parser.add_argument('--output')
args=parser.parse_args()
fixture=Path('tests/fixtures/audio_child.py').resolve()
original_mic=live.Microphone
original_probe=audio_backend.probe_inputs
original_tk=tk.Tk
observed={};backends=[];failures=[]

def factory(**kwargs):
    command=[sys.executable,str(fixture),args.case]
    if args.case=='wav':command.append(str(Path('data/raw/mini_speech_commands/right/037c445a_nohash_0.wav').resolve()))
    result=AudioProcess(command=command);backends.append(result);return result

class ObservedMicrophone(original_mic):
    def __init__(self,*a,**kw):
        if args.case!='real':kw['backend_factory']=factory
        super().__init__(*a,**kw)
        observed['microphone']=self
    def emit(self,kind,value):
        if kind in ('device','attempt','error','cleanup','prediction'):observed[kind]=value
        if kind=='level':observed['levels']=observed.get('levels',0)+1
        super().emit(kind,value)
live.Microphone=ObservedMicrophone

if args.case=='probe-opening':
    def probe(stop):
        def blocked(**kwargs):
            result=AudioProcess(command=[sys.executable,str(fixture),'opening']);backends.append(result);return result
        return original_probe(stop,backend_factory=blocked)
    audio_backend.probe_inputs=probe
elif args.case!='real':
    audio_backend.probe_inputs=lambda stop:{'inputs':[{'index':0,'name':'entrada de prueba'}],
        'default_input':0,'sounddevice':'fixture','portaudio':'fixture'}

class LifecycleTk(original_tk):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.deadline=time.monotonic()+20
        self.close_started=None
        self.ticks=0
        self.after(50,self.heartbeat)
        self.after(100,self.activate)
    def heartbeat(self):
        self.ticks+=1;self.after(50,self.heartbeat)
    def walk(self,w=None):
        for child in (w or self).winfo_children():
            yield child;yield from self.walk(child)
    def report_callback_exception(self,exc,value,tb):
        failures.append(repr(value));self.close_app()
    def activate(self):
        if args.case=='probe-opening':
            if backends and backends[0].process is not None:
                self.after(200,self.close_app);return
        else:
            widgets=list(self.walk())
            button=next((w for w in widgets if w.winfo_class()=='TButton' and w.cget('text')=='Activar escucha'),None)
            if button is not None and not button.instate(['disabled']):
                combo=next(w for w in widgets if w.winfo_class()=='TCombobox')
                if args.device is not None:
                    choices=list(combo.cget('values'))
                    index=next((i for i,v in enumerate(choices) if v.startswith(str(args.device)+':')),None)
                    if index is None:
                        if time.monotonic()>self.deadline:
                            failures.append(f'La entrada {args.device} no estuvo disponible para la prueba')
                            self.close_app();return
                        if time.monotonic()-getattr(self,'last_refresh',0)>1:
                            refresh=next(w for w in widgets if w.winfo_class()=='TButton' and w.cget('text')=='↻')
                            refresh.invoke();self.last_refresh=time.monotonic()
                        self.after(100,self.activate);return
                    combo.current(index)
                observed['selection']=combo.get()
                button.invoke();self.after(50,self.monitor);return
        if time.monotonic()>self.deadline:
            failures.append('No se pudo activar escucha antes del plazo de prueba');self.close_app()
        else:self.after(100,self.activate)
    def monitor(self):
        if args.case=='opening' and 'attempt' in observed:
            self.close_app();return
        if args.case=='error' and 'error' in observed:
            labels=[str(self.getvar(str(w.cget('textvariable')))) for w in self.walk()
                    if w.winfo_class()=='TLabel' and w.cget('textvariable')]
            if any(v.startswith('Error:') for v in labels):
                observed['error_visible']=True
                button=next(w for w in self.walk() if w.winfo_class()=='TButton' and w.cget('text')=='Siguiente →')
                button.invoke()
                current=[str(self.getvar(str(w.cget('textvariable')))) for w in self.walk()
                         if w.winfo_class()=='TLabel' and w.cget('textvariable')]
                observed['manual_navigation_after_error']=any(v.startswith('Diapositiva 2/4') for v in current)
                if not observed['manual_navigation_after_error']:failures.append('La navegación no respondió tras el error de audio')
                self.close_app();return
        if args.case=='wav' and 'prediction' in observed:
            labels=[str(self.getvar(str(w.cget('textvariable')))) for w in self.walk()
                    if w.winfo_class()=='TLabel' and w.cget('textvariable')]
            if any(v.startswith('Diapositiva 2/4') for v in labels):
                observed['navigation']='right → siguiente verificado con CNN real y WAV de validación'
                self.close_app();return
        if args.case in ('real','closing'):
            if 'error' in observed:
                observed['audio_failed_but_gui_responsive']=True;self.after(200,self.close_app);return
            if observed.get('levels',0)>=3:
                self.close_app();return
        if time.monotonic()>self.deadline:
            failures.append('La secuencia no alcanzó el estado esperado');self.close_app()
        else:self.after(50,self.monitor)
    def close_app(self):
        if self.close_started is not None:return
        self.close_started=time.monotonic();observed['ticks_at_close']=self.ticks
        self.tk.call(self.protocol('WM_DELETE_WINDOW'))

instances=[]
def create_root(*a,**kw):
    root=LifecycleTk(*a,**kw);instances.append(root);return root
tk.Tk=create_root
sys.argv=['vozslides','gui']
try:
    runpy.run_path('.venv/bin/vozslides',run_name='__main__')
except SystemExit as error:
    if error.code not in (None,0):raise
root=instances[0]
mic=observed.pop('microphone',None)
if mic is not None and mic.backend is not None and mic.backend not in backends:backends.append(mic.backend)
report={'case':args.case,'device_requested':args.device,'close_seconds':time.monotonic()-root.close_started if root.close_started else None,
    'mainloop_returned':True,'portaudio_imported_in_gui':'sounddevice' in sys.modules,
    'audio_processes':[b.cleanup for b in backends], 'observed':observed,'failures':failures,
    'scope':'real abre entrada física sin frase controlada; wav usa CNN real con WAV de validación; otros casos inyectan fallos de audio'}
if any(b.process is not None and b.process.poll() is None for b in backends):failures.append('Quedó un proceso de audio vivo')
if report['portaudio_imported_in_gui']:failures.append('PortAudio se importó en el proceso principal')
if args.case=='wav' and 'navigation' not in observed:failures.append('No se verificó navegación por CNN')
if args.output:Path(args.output).write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps(report,indent=2,ensure_ascii=False),flush=True)
if failures:raise SystemExit(1)
