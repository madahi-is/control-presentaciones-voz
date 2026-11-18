"""Abre una ventana real, comprueba navegación y guarda SOLO su captura. Sin micrófono."""
from pathlib import Path
import json
import tkinter as tk
from PIL import ImageGrab
from vozslides.gui import launch

OriginalTk=tk.Tk
checks={"microphone":"No se realiza captura ni se activa la escucha"}
errors=[]

class CheckedTk(OriginalTk):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.ticks=0
        self.heartbeat()
        self.after(8000,self.verify)

    def report_callback_exception(self,exc,value,trace):
        errors.append(f"{exc.__name__}: {value}")
        self.after(0,self.finish)

    def widgets(self,parent=None):
        for widget in (parent or self).winfo_children():
            yield widget
            yield from self.widgets(widget)

    def verify(self):
        self.buttons={str(w.cget('text')):w for w in self.widgets() if w.winfo_class()=='TButton'}
        self.fullscreen_option=next(w for w in self.widgets() if w.winfo_class()=='TCheckbutton' and str(w.cget('text'))=='Pantalla completa al iniciar')
        self.step(0)

    def slide(self):
        for w in self.widgets():
            if w.winfo_class()=='TLabel':
                variable=w.cget('textvariable')
                if variable:
                    value=str(self.getvar(str(variable)))
                    if value.startswith('Diapositiva '):return value
        return ''

    def heartbeat(self):
        self.ticks+=1
        self.after(50,self.heartbeat)

    def projection(self):
        return next((w for w in self.winfo_children() if isinstance(w,tk.Toplevel)),None)

    def step(self, index):
        try:
            if index==0:
                assert self.slide().startswith('Diapositiva 1/4'), self.slide()
                assert self.buttons['← Anterior'].instate(['disabled'])
                self.buttons['Siguiente →'].invoke()
            elif index==1:
                assert self.slide().startswith('Diapositiva 2/4'), self.slide()
                assert not self.buttons['← Anterior'].instate(['disabled'])
                self.buttons['← Anterior'].invoke()
            elif index==2:
                assert self.slide().startswith('Diapositiva 1/4'), self.slide()
                self.before_projection=self.ticks
                self.buttons['Iniciar'].invoke()
            elif index==3:
                assert self.projection() is None, 'Sin pantalla completa no debe existir ventana adicional'
                assert 'Presentación' in self.slide(), self.slide()
                assert self.state()=='normal'
                assert self.ticks>self.before_projection
                self.buttons['Siguiente →'].invoke()
            elif index==4:
                assert self.slide().startswith('Diapositiva 2/4'), self.slide()
                assert self.projection() is None
                self.buttons['← Anterior'].invoke()
            elif index==5:
                assert self.slide().startswith('Diapositiva 1/4'), self.slide()
                self.buttons['Iniciar'].invoke()
                assert self.projection() is None, 'Repetir Iniciar no debe crear ventanas'
                self.buttons['Finalizar'].invoke()
            elif index==6:
                assert self.projection() is None
                assert 'Vista previa' in self.slide()
            elif index==7:
                assert self.projection() is None, 'F11 debe cerrar solo la presentación'
                assert 'Vista previa' in self.slide(), self.slide()
                self.fullscreen_option.invoke()
                self.buttons['Iniciar'].invoke()
            elif index==8:
                projection=self.projection()
                assert projection is not None
                assert bool(projection.attributes('-fullscreen')), 'La opción marcada debe abrir a pantalla completa'
                projection.update_idletasks()
                x,y=projection.winfo_rootx(),projection.winfo_rooty()
                ImageGrab.grab(bbox=(x,y,x+projection.winfo_width(),y+projection.winfo_height())).save('results/presentation_fullscreen.png')
                projection.event_generate('<Right>')
            elif index==9:
                assert self.slide().startswith('Diapositiva 2/4'), self.slide()
                self.projection().event_generate('<Escape>')
            elif index==10:
                assert self.projection() is not None, 'Esc conserva proyección'
                self.projection().event_generate('<F11>')
            elif index==11:
                assert self.projection() is None
                assert 'Vista previa' in self.slide(), self.slide()
                assert self.slide().startswith('Diapositiva 2/4')
                checks['navigation']='Sin pantalla completa: solo visor principal incluso al repetir Iniciar; modo y navegación verificados; con opción marcada: proyección independiente y cierre conservando PDF; ciclo de eventos activo'
                self.fullscreen_option.invoke()
                checks['presentation_screenshot']='results/presentation_fullscreen.png'
                self.geometry(f"{min(1220,self.winfo_screenwidth()-40)}x{min(840,self.winfo_screenheight()-80)}+10+30")
                self.after(700,self.capture)
                return
            self.after(400,lambda:self.step(index+1))
        except Exception as error:
            errors.append(repr(error));self.finish()

    def capture(self):
        try:
            self.update_idletasks();self.lift();self.update()
            x,y=self.winfo_rootx(),self.winfo_rooty()
            path=Path('results/ui_mejorada.png');path.parent.mkdir(exist_ok=True)
            ImageGrab.grab(bbox=(x,y,x+self.winfo_width(),y+self.winfo_height())).save(path)
            checks['screenshot']=str(path)
            checks['size']=[self.winfo_width(),self.winfo_height()]
        except Exception as error:errors.append(str(error))
        finally:self.finish()

    def finish(self):
        callback=self.protocol('WM_DELETE_WINDOW')
        if callback:self.tk.call(callback)
        else:self.destroy()

tk.Tk=CheckedTk
launch()
checks['errors']=errors
Path('results/ui_verification.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False))
print(json.dumps(checks,indent=2,ensure_ascii=False))
if errors:raise SystemExit(1)
