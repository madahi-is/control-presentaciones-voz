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
    from .audio_backend import probe_inputs
    from .presentation import PresentationWindow
    from .rendering import PageImages
    page_images=PageImages()
    preview_signature=None

    root=tk.Tk();root.title("VozSlides · Presentaciones por voz");root.geometry("1220x840")
    root.minsize(980,700)
    root.configure(background="#edf2f7")
    style=ttk.Style(root);style.theme_use("clam")
    style.configure("TFrame",background="#edf2f7")
    style.configure("TLabel",background="#edf2f7",foreground="#243449",font=("DejaVu Sans",10))
    style.configure("Card.TFrame",background="white")
    style.configure("Card.TLabel",background="white")
    style.configure("Title.TLabel",font=("DejaVu Sans",23,"bold"),foreground="#10243a")
    style.configure("Heading.TLabel",background="white",font=("DejaVu Sans",12,"bold"))
    style.configure("TButton",padding=(12,7),font=("DejaVu Sans",10))
    style.configure("Primary.TButton",background="#176b87",foreground="white")
    style.map("Primary.TButton",background=[("active","#12566d"),("disabled","#c6d4de")])
    style.configure("Danger.TButton",background="#a52c3b",foreground="white")
    style.map("Danger.TButton",background=[("active","#812331"),("disabled","#c6d4de")])
    style.configure("Card.TCheckbutton",background="white")
    events=queue.Queue();nav=Navigation()
    state={"document":None,"predictor":None,"mic":None,"photo":None,"busy":False,"closing":False,"session":0,"enumerating":False,"probe_thread":None,"audio_error":None}
    status=tk.StringVar(value="Control manual disponible. Cargando modelo…")
    result=tk.StringVar(value="Todavía no hay una palabra detectada")
    number=tk.StringVar(value="Sin documento")
    filename=tk.StringVar(value="Presentación de demostración")
    model_status=tk.StringVar(value="Modelo: cargando…")
    calibration=tk.BooleanVar(value=False)
    fullscreen=tk.BooleanVar(value=False)
    header=ttk.Frame(root,padding=(20,14));header.pack(fill="x")
    ttk.Label(header,text="VozSlides",style="Title.TLabel").pack(side="left")
    ttk.Label(header,text="Presenta con tu voz",padding=(20,0)).pack(side="left")
    ttk.Label(header,textvariable=model_status).pack(side="right")
    top=ttk.Frame(root,padding=(20,0,20,12));top.pack(fill="x")
    body=ttk.Frame(root,padding=(20,0));body.pack(fill="both",expand=True)
    body.columnconfigure(0,weight=1);body.rowconfigure(0,weight=1)
    stage=ttk.Frame(body,style="Card.TFrame",padding=10);stage.grid(row=0,column=0,sticky="nsew",padx=(0,16))
    ttk.Label(stage,textvariable=filename,style="Heading.TLabel").pack(anchor="w",pady=(0,8))
    viewer=tk.Label(stage,background="#142235",anchor="center",borderwidth=0,width=1,height=1)
    viewer.pack(fill="both",expand=True)
    footer=ttk.Frame(stage,style="Card.TFrame");footer.pack(fill="x",pady=(10,0))
    ttk.Label(footer,textvariable=number,style="Card.TLabel").pack(side="left")
    navigation=ttk.Frame(stage,style="Card.TFrame");navigation.pack(fill="x",pady=(8,0))
    side_shell=ttk.Frame(body,style="Card.TFrame")
    side_shell.grid(row=0,column=1,sticky="ns")
    side_canvas=tk.Canvas(side_shell,width=286,background="white",highlightthickness=0)
    side_scroll=ttk.Scrollbar(side_shell,orient="vertical",command=side_canvas.yview)
    side_scroll.pack(side="right",fill="y");side_canvas.pack(side="left",fill="both",expand=True)
    side_canvas.configure(yscrollcommand=side_scroll.set)
    sidebar=ttk.Frame(side_canvas,style="Card.TFrame",padding=12)
    side_window=side_canvas.create_window((0,0),window=sidebar,anchor="nw")
    sidebar.bind("<Configure>",lambda e:side_canvas.configure(scrollregion=side_canvas.bbox("all")))
    side_canvas.bind("<Configure>",lambda e:side_canvas.itemconfigure(side_window,width=e.width))
    def scroll_panel(event):
        side_canvas.yview_scroll(-1 if event.num==4 else 1,"units")
    side_canvas.bind("<Button-4>",scroll_panel);side_canvas.bind("<Button-5>",scroll_panel)
    ttk.Label(sidebar,text="Control por voz",style="Heading.TLabel").pack(anchor="w")
    ttk.Label(sidebar,text="Entrada de micrófono",style="Card.TLabel").pack(anchor="w",pady=(16,5))
    controls=ttk.Frame(sidebar,style="Card.TFrame");controls.pack(fill="x")
    ttk.Label(sidebar,text="Nivel de entrada",style="Card.TLabel").pack(anchor="w",pady=(14,4))
    level=ttk.Progressbar(sidebar,maximum=100);level.pack(fill="x")
    level_text=tk.StringVar(value="Activa la escucha para ver el nivel")
    ttk.Label(sidebar,textvariable=level_text,style="Card.TLabel",wraplength=265).pack(anchor="w",pady=4)
    ttk.Checkbutton(sidebar,text="Calibrar ruido al iniciar (2 s)",variable=calibration,style="Card.TCheckbutton").pack(anchor="w",pady=8)
    voice_buttons=ttk.Frame(sidebar,style="Card.TFrame");voice_buttons.pack(fill="x")
    ttk.Label(sidebar,textvariable=status,style="Card.TLabel",wraplength=265).pack(anchor="w",pady=(12,8))
    ttk.Separator(sidebar).pack(fill="x",pady=8)
    ttk.Label(sidebar,text="Último reconocimiento",style="Heading.TLabel").pack(anchor="w")
    ttk.Label(sidebar,textvariable=result,style="Card.TLabel",wraplength=265).pack(anchor="w",pady=8)
    confidence_bar=ttk.Progressbar(sidebar,maximum=100);confidence_bar.pack(fill="x")
    history_frame=ttk.Frame(root,padding=(20,12,20,14));history_frame.pack(fill="x",side="bottom",before=body)
    ttk.Label(history_frame,text="Historial de eventos").pack(anchor="w",pady=(0,5))
    log=tk.Text(history_frame,height=3,state="disabled",background="white",foreground="#243449",
                relief="flat",font=("DejaVu Sans Mono",9),wrap="word")
    scroll=ttk.Scrollbar(history_frame,command=log.yview);scroll.pack(side="right",fill="y")
    log.configure(yscrollcommand=scroll.set);log.pack(fill="x")

    def record(text):
        from datetime import datetime
        log.configure(state="normal");log.insert("end",f"{datetime.now():%H:%M:%S} {text}\n");log.see("end");log.configure(state="disabled")

    def render():
        nonlocal preview_signature
        if state["closing"]:return
        document=state["document"]
        if document is None:return
        page=document[nav.index]
        # La proyección genera la imagen grande; la miniatura reutiliza esa imagen.
        presentation.render()
        width=max(1,viewer.winfo_width()-20);height=max(1,viewer.winfo_height()-20)
        signature=(id(document),nav.index,width,height)
        if width>10 and height>10 and signature!=preview_signature:
            image=page_images.get(page,width,height)
            state["photo"]=ImageTk.PhotoImage(image)
            viewer.configure(image=state["photo"])
            preview_signature=signature
        number.set(f"Diapositiva {nav.index+1}/{nav.pages} · {'Presentación' if nav.presenting else 'Vista previa'}")

    def action(name):
        if nav.apply(name):
            if name=="start":presentation.show(fullscreen=fullscreen.get())
            elif name=="finish":
                presentation.hide()
                root.lift();root.focus_set()
            render();record(f"Acción: {ACTION_LABELS[name]}")

    def open_pdf(path=None):
        path=path or filedialog.askopenfilename(filetypes=[("Presentación PDF","*.pdf")])
        if not path:return
        try:
            document=pymupdf.open(path)
            if document.needs_pass or len(document)==0:
                document.close();raise ValueError("PDF vacío o protegido con contraseña")
            presentation.hide()
            page_images.clear()
            previous=state["document"];state["document"]=document
            if previous is not None:previous.close()
            nav.pages=len(document);nav.index=0;nav.presenting=False
            filename.set(Path(path).name)
            render();record(f"PDF cargado: {path}")
        except Exception as error:messagebox.showerror("No se pudo abrir el PDF",str(error))

    def stop():
        if state["mic"]:state["mic"].stop()
        level["value"]=0;level_text.set("Escucha detenida")
        status.set("Deteniendo escucha…" if state["mic"] else "Escucha desactivada");record("Detención manual de escucha")

    def current_page():
        document=state["document"]
        return document[nav.index] if document is not None and nav.pages else None

    presentation=PresentationWindow(root,current_page,lambda:action("finish"),stop,
                                    lambda:action("previous"),lambda:action("next"),page_images.get)

    devices=[]
    selected=tk.StringVar()
    combo=ttk.Combobox(controls,textvariable=selected,state="readonly",width=22)
    probe_stop=threading.Event()
    def refresh_devices():
        if state["mic"] is not None or state["enumerating"] or state["closing"]:return
        state["enumerating"]=True
        probe_stop.clear()
        status.set("Buscando entradas de audio…")
        def work():
            try:
                value=probe_inputs(probe_stop)
                if not probe_stop.is_set():events.put(("devices",value))
            except Exception as error:
                if not probe_stop.is_set():events.put(("devices_error",str(error)))
        thread=threading.Thread(target=work,daemon=True,name="audio-enumeration")
        state["probe_thread"]=thread
        thread.start()

    def listen():
        if state["predictor"] is None:
            messagebox.showinfo("Modelo no disponible","Entrena primero con vozslides train. El control manual sigue disponible.");return
        if state["mic"] is not None or state["busy"]:return
        if not devices:messagebox.showinfo("Micrófono","No hay dispositivos. Pulsa Actualizar entradas.");return
        if combo.current()<0:return
        device=devices[combo.current()][0]
        state["session"]+=1
        state["mic"]=Microphone(state["predictor"],events,device,
                                calibrate=calibration.get(),session=state["session"],expected_name=devices[combo.current()][1])
        status.set("Abriendo micrófono…")
        state["mic"].start()

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
        if state["closing"]:return
        for _ in range(30):
            try:kind,value=events.get_nowait()
            except queue.Empty:break
            if kind=="microphone":
                session,kind,value=value
                if session!=state["session"]:continue
                if state["mic"] is None:continue
                if state["mic"].stop_event.is_set() and kind not in ("stopped","error","cleanup","attempt","device"):continue
            if kind=="devices":
                state["enumerating"]=False
                state["audio_error"]=None
                previous=combo.get()
                devices[:]=[(d["index"],d["name"]) for d in value["inputs"]]
                choices=[f"{i}: {name}" for i,name in devices]
                combo["values"]=choices
                if devices:
                    index=choices.index(previous) if previous in choices else next((n for n,(i,_) in enumerate(devices) if i==value["default_input"]),0)
                    combo.current(index)
                    status.set("Entradas listas. Escucha desactivada")
                else:
                    selected.set("")
                    state["audio_error"]="No se encontraron micrófonos. Control manual disponible"
                    status.set(state["audio_error"])
                record(f"Audio: {len(devices)} entradas · sounddevice {value['sounddevice']} · {value['portaudio']}")
            elif kind=="devices_error":
                state["enumerating"]=False
                state["audio_error"]="Error de audio: "+value
                status.set(state["audio_error"]);record(status.get())
            elif kind=="model":
                state["predictor"]=value
                status.set(state["audio_error"] or ("Buscando entradas de audio…" if state["enumerating"] else "Modelo cargado. Escucha desactivada"))
                model_status.set("CNN lista · umbral "+format(value.info["threshold"],".2f"))
            elif kind=="missing":
                model_status.set("Modelo no disponible")
                status.set("Sin modelo utilizable. Control manual disponible; ejecuta vozslides train.");record(value)
            elif kind=="prediction":
                word,confidence,accepted,reason=value
                # Ignora resultados de escucha después de una detención manual.
                if state["mic"] is not None and state["mic"].stop_event.is_set():continue
                command=command_action(word,state["predictor"].cfg["classes"]) if accepted else None
                if command:action(command)
                text=f"Palabra: {word} | Puntuación: {confidence:.3f} | Acción: {ACTION_LABELS.get(command, 'ninguna')} ({reason})"
                result.set(text);confidence_bar["value"]=confidence*100;record(text)
            elif kind=="status":
                if state["mic"] is not None and not state["mic"].stop_event.is_set():status.set(value)
            elif kind=="stopped":
                state["mic"]=None;level["value"]=0
                if not status.get().startswith("Error:"):status.set("Escucha desactivada")
            elif kind in ("attempt","device"):
                prefix="Intento de audio" if kind=="attempt" else "Micrófono abierto"
                record(f"{prefix}: índice {value['device']} · {value['name']} · {value['samplerate']} Hz · {value['channels']} canal(es) · {value['dtype']} · bloque {value['blocksize']} · latencia {value['latency']}")
            elif kind=="cleanup":
                record("El proceso de audio no respondió al cierre y fue detenido automáticamente")
            elif kind=="level":
                energy,threshold=value
                level["value"]=min(100,energy/max(threshold,1e-6)*25)
                level_text.set(f"Nivel {energy:.4f} · umbral {threshold:.4f}")
            elif kind=="calibrated":
                threshold,noise=value
                record(f"Calibración de sesión: ruido {noise:.4f}, umbral {threshold:.4f}")
                if threshold>.04:record("Ruido elevado: acércate al micrófono o busca un lugar más silencioso")
            elif kind=="idle":state["busy"]=False
            elif kind=="error":status.set("Error: "+value);record(value)
        active=state["mic"] is not None
        can_infer=state["predictor"] is not None and not state["busy"] and not active and not state["enumerating"]
        listen_button.configure(state="normal" if can_infer and devices else "disabled")
        audio_button.configure(state="normal" if can_infer else "disabled")
        stop_button.configure(state="normal" if active else "disabled")
        combo.configure(state="disabled" if active else "readonly")
        refresh_button.configure(state="disabled" if active or state["enumerating"] else "normal")
        previous_button.configure(state="normal" if nav.pages and nav.index>0 else "disabled")
        next_button.configure(state="normal" if nav.pages and nav.index<nav.pages-1 else "disabled")
        if not state["closing"]:root.after(80,poll)

    ttk.Button(top,text="Abrir PDF",style="Primary.TButton",command=open_pdf).pack(side="left")
    ttk.Button(top,text="Demostración",command=lambda:open_pdf("assets/demo.pdf")).pack(side="left",padx=8)
    audio_button=ttk.Button(top,text="Probar archivo de audio",command=audio_file);audio_button.pack(side="left")
    ttk.Button(top,text="Guía de comandos",command=lambda:messagebox.showinfo("Comandos de voz",
        "Esta CNN reconoce palabras inglesas:\n\nright → Siguiente\nleft → Anterior\ngo → Iniciar\nstop → Finalizar\n\nyes, no, up y down no ejecutan acciones.\n\nEsc detiene la escucha. F11 o stop cierran la presentación.\nLas flechas permiten navegar en pantalla completa.\n\nCalibración opcional: permanece en silencio durante 2 segundos al activar la escucha.")).pack(side="right")
    ttk.Checkbutton(top,text="Pantalla completa al iniciar",variable=fullscreen).pack(side="left",padx=8)
    previous_button=ttk.Button(navigation,text="← Anterior",command=lambda:action("previous"));previous_button.pack(side="left")
    next_button=ttk.Button(navigation,text="Siguiente →",command=lambda:action("next"));next_button.pack(side="left",padx=6)
    ttk.Button(navigation,text="Iniciar",command=lambda:action("start")).pack(side="right",padx=6)
    ttk.Button(navigation,text="Finalizar",command=lambda:action("finish")).pack(side="right")
    combo.pack(side="left",fill="x",expand=True)
    refresh_button=ttk.Button(controls,text="↻",width=2,command=refresh_devices);refresh_button.pack(side="right",padx=(4,0))
    listen_button=ttk.Button(voice_buttons,text="Activar escucha",style="Primary.TButton",command=listen);listen_button.pack(fill="x")
    stop_button=ttk.Button(voice_buttons,text="Detener escucha · Esc",style="Danger.TButton",command=stop);stop_button.pack(fill="x",pady=(6,0))
    root.bind("<Escape>",lambda e:stop())
    root.bind("<F11>",lambda e:action("finish") if nav.presenting else action("start"))
    resize_job=[None]
    def resized(event):
        if resize_job[0]:root.after_cancel(resize_job[0])
        resize_job[0]=root.after(150,render)
    viewer.bind("<Configure>",resized)
    def finish_close():
        mic=state["mic"]
        probe=state["probe_thread"]
        if ((mic is not None and mic.thread is not None and mic.thread.is_alive())
                or (probe is not None and probe.is_alive())):
            root.after(30,finish_close)
            return
        if state["document"] is not None:state["document"].close()
        page_images.clear()
        root.destroy()

    def close():
        if state["closing"]:return
        state["closing"]=True
        if state["mic"]:state["mic"].stop()
        probe_stop.set()
        status.set("Cerrando audio y aplicación…")
        presentation.hide()
        if resize_job[0]:root.after_cancel(resize_job[0])
        # No ejecutar join, abort ni close de PortAudio en un callback de Tk.
        root.after(20,finish_close)
    root.protocol("WM_DELETE_WINDOW",close)
    refresh_devices()
    if not Path("assets/demo.pdf").exists():demo()
    open_pdf("assets/demo.pdf")
    threading.Thread(target=load_model,daemon=True).start();poll()
    try:
        root.mainloop()
    finally:
        probe_stop.set()
        if state["mic"]:
            state["mic"].stop()
            state["mic"].thread.join(timeout=2.)
        if state["probe_thread"]:state["probe_thread"].join(timeout=2.)
