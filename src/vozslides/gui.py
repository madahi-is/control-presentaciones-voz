"""Tk se usa exclusivamente desde el hilo principal."""
import queue
import threading
from pathlib import Path
from .control import Navigation,command_action

ACTION_LABELS={"next":"Siguiente diapositiva", "previous":"Diapositiva anterior",
               "start":"Iniciar presentación", "finish":"Finalizar presentación"}


def demo(path="assets/demo.pdf"):
    import pymupdf
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    document=pymupdf.open()
    for title,body in [
        ("Control de presentaciones por voz","Prototipo universitario - CNN local"),
        ("Comandos en ingles","right: siguiente | left: anterior | go: iniciar | stop: finalizar"),
        ("Como funciona","Audio -> espectrograma -> CNN -> filtro -> accion"),
        ("Limites del prototipo","No reconoce todavia comandos en espanol. Esc detiene la escucha.")]:
        page=document.new_page(width=960,height=540)
        page.draw_rect(page.rect,color=None,fill=(.06,.1,.18))
        page.insert_text((55,155),title,fontsize=30,color=(.4,.8,1))
        page.insert_textbox((55,220,900,450),body,fontsize=20,color=(1,1,1))
    document.save(path);document.close()
    return path


def launch():
    try:
        import tkinter as tk
        from tkinter import ttk,filedialog,messagebox
    except ImportError as error:
        raise SystemExit("Falta Tkinter. En Linux Mint: sudo apt install python3-tk") from error
    import pymupdf
    from PIL import Image,ImageTk
    from .audio import read_audio,rms,waveform
    from .inference import Predictor
    from .live import Microphone

    root=tk.Tk();root.title("Presentaciones por voz · Prototipo en inglés");root.geometry("1100x820")
    events=queue.Queue();nav=Navigation()
    state={"document":None,"predictor":None,"mic":None,"photo":None,"busy":False,"closing":False}
    status=tk.StringVar(value="Control manual disponible. Cargando modelo…")
    result=tk.StringVar(value="Palabra: — | Puntuación: — | Acción: —")
    number=tk.StringVar(value="Sin documento")
    top=ttk.Frame(root,padding=8);top.pack(fill="x")
    viewer=ttk.Label(root,anchor="center");viewer.pack(fill="both",expand=True,padx=10)
    ttk.Label(root,textvariable=number).pack()
    controls=ttk.Frame(root,padding=8);controls.pack(fill="x")
    ttk.Label(root,textvariable=status).pack(anchor="w",padx=10)
    ttk.Label(root,textvariable=result).pack(anchor="w",padx=10)
    log=tk.Text(root,height=7,state="disabled");log.pack(fill="x",padx=10,pady=8)

    def record(text):
        from datetime import datetime
        log.configure(state="normal");log.insert("end",f"{datetime.now():%H:%M:%S} {text}\n");log.see("end");log.configure(state="disabled")

    def render():
        document=state["document"]
        if document is None:return
        page=document[nav.index]
        width=max(400,viewer.winfo_width()-20);height=max(200,viewer.winfo_height()-20)
        scale=min(width/page.rect.width,height/page.rect.height,2)
        pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False)
        image=Image.frombytes("RGB",[pix.width,pix.height],pix.samples)
        state["photo"]=ImageTk.PhotoImage(image);viewer.configure(image=state["photo"])
        number.set(f"Diapositiva {nav.index+1}/{nav.pages} · {'Presentación' if nav.presenting else 'Vista previa'}")

    def action(name):
        if nav.apply(name):
            if name=="start":root.attributes("-fullscreen",True)
            elif name=="finish":root.attributes("-fullscreen",False)
            render();record(f"Acción: {ACTION_LABELS[name]}")

    def open_pdf(path=None):
        path=path or filedialog.askopenfilename(filetypes=[("Presentación PDF","*.pdf")])
        if not path:return
        try:
            document=pymupdf.open(path)
            if document.needs_pass or len(document)==0:
                document.close();raise ValueError("PDF vacío o protegido con contraseña")
            previous=state["document"];state["document"]=document
            if previous is not None:previous.close()
            nav.pages=len(document);nav.index=0;nav.presenting=False
            root.attributes("-fullscreen",False);render();record(f"PDF cargado: {path}")
        except Exception as error:messagebox.showerror("No se pudo abrir el PDF",str(error))

    def stop():
        if state["mic"]:state["mic"].stop()
        status.set("Escucha desactivada");record("Detención manual de escucha")

    devices=[]
    selected=tk.StringVar()
    combo=ttk.Combobox(controls,textvariable=selected,state="readonly",width=36)
    def refresh_devices():
        devices.clear()
        try:
            import sounddevice as sd
            devices.extend((i,d["name"]) for i,d in enumerate(sd.query_devices()) if d["max_input_channels"]>0)
            combo["values"]=[f"{i}: {name}" for i,name in devices]
            if devices:combo.current(0)
        except Exception as error:record(f"Dispositivos no disponibles: {error}")

    def listen():
        if state["predictor"] is None:
            messagebox.showinfo("Modelo no disponible","Entrena primero con vozslides train. El control manual sigue disponible.");return
        if state["mic"] is not None or state["busy"]:return
        if not devices:messagebox.showinfo("Micrófono","No hay dispositivos. Pulsa Actualizar entradas.");return
        device=devices[combo.current()][0]
        state["mic"]=Microphone(state["predictor"],events,device);state["mic"].start()

    def audio_file():
        if state["predictor"] is None:
            messagebox.showinfo("Modelo no disponible","Entrena primero el modelo.");return
        if state["busy"] or state["mic"] is not None:
            messagebox.showinfo("Inferencia ocupada","Detén la escucha y espera a que termine antes de probar un archivo.");return
        path=filedialog.askopenfilename(filetypes=[("Audio","*.wav *.flac *.ogg")])
        if not path:return
        state["busy"]=True
        def work():
            try:
                predictor=state["predictor"];x,rate=read_audio(path)
                word,confidence=predictor.predict(x,rate)
                from .control import Gate
                accepted,reason=Gate(predictor.info["threshold"],predictor.cfg["silence_rms"]).accept(confidence,rms(waveform(x,rate,predictor.cfg)),0)
                events.put(("prediction",(word,confidence,accepted,reason)))
            except Exception as error:events.put(("error",str(error)))
            finally:events.put(("idle",None))
        threading.Thread(target=work,daemon=True).start()

    def load_model():
        try:events.put(("model",Predictor()))
        except Exception as error:events.put(("missing",str(error)))

    def poll():
        while True:
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=="model":state["predictor"]=value;status.set("Modelo cargado. Escucha desactivada")
            elif kind=="missing":status.set("Sin modelo utilizable. Control manual disponible; ejecuta vozslides train.");record(value)
            elif kind=="prediction":
                word,confidence,accepted,reason=value
                # Ignora resultados de escucha después de una detención manual.
                if state["mic"] is not None and state["mic"].stop_event.is_set():continue
                command=command_action(word,state["predictor"].cfg["classes"]) if accepted else None
                if command:action(command)
                text=f"Palabra: {word} | Puntuación: {confidence:.3f} | Acción: {ACTION_LABELS.get(command, 'ninguna')} ({reason})"
                result.set(text);record(text)
            elif kind=="status":
                if state["mic"] is not None and not state["mic"].stop_event.is_set():status.set(value)
            elif kind=="stopped":state["mic"]=None;status.set("Escucha desactivada")
            elif kind=="idle":state["busy"]=False
            elif kind=="error":status.set("Error: "+value);record(value)
        root.after(80,poll)

    ttk.Button(top,text="Abrir PDF",command=open_pdf).pack(side="left")
    ttk.Button(top,text="Demostración",command=lambda:open_pdf("assets/demo.pdf")).pack(side="left")
    for label,name in [("Anterior","previous"),("Siguiente","next"),("Iniciar","start"),("Finalizar","finish")]:
        ttk.Button(top,text=label,command=lambda n=name:action(n)).pack(side="left",padx=3)
    ttk.Button(top,text="Probar audio",command=audio_file).pack(side="left")
    combo.pack(side="left")
    ttk.Button(controls,text="Actualizar entradas",command=refresh_devices).pack(side="left")
    ttk.Button(controls,text="Activar escucha",command=listen).pack(side="left")
    ttk.Button(controls,text="DETENER ESCUCHA (Esc)",command=stop).pack(side="left")
    root.bind("<Escape>",lambda e:stop())
    resize_job=[None]
    def resized(event):
        if resize_job[0]:root.after_cancel(resize_job[0])
        resize_job[0]=root.after(150,render)
    viewer.bind("<Configure>",resized)
    def close():
        stop()
        if state["document"] is not None:state["document"].close()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW",close)
    refresh_devices()
    if not Path("assets/demo.pdf").exists():demo()
    open_pdf("assets/demo.pdf")
    threading.Thread(target=load_model,daemon=True).start();poll();root.mainloop()
