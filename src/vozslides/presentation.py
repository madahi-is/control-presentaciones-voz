"""Ventana de proyección independiente; comparte navegación con el panel principal."""


class PresentationWindow:
    def __init__(self, root, get_page, finish, stop_listening, previous, next_slide, get_image):
        self.get_image = get_image
        self.signature = None
        self.root = root
        self.get_page = get_page
        self.finish = finish
        self.stop_listening = stop_listening
        self.previous = previous
        self.next_slide = next_slide
        self.window = None
        self.viewer = None
        self.photo = None
        self.resize_job = None

    @staticmethod
    def key(callback):
        def handle(event):
            callback()
            return "break"
        return handle

    def show(self, fullscreen=False):
        # Sin proyección, se utiliza exclusivamente el visor principal.
        if not fullscreen:
            self.hide()
            return
        import tkinter as tk
        if self.window is None:
            self.window = tk.Toplevel(self.root)
            self.window.title("VozSlides · Presentación")
            self.window.configure(background="black")
            self.window.geometry("960x600")
            self.viewer = tk.Label(self.window, background="black", borderwidth=0,
                                   width=1, height=1, anchor="center")
            self.viewer.pack(fill="both", expand=True)
            self.window.protocol("WM_DELETE_WINDOW", self.finish)
            self.window.bind("<F11>", self.key(self.finish))
            self.window.bind("<Escape>", self.key(self.stop_listening))
            self.window.bind("<Right>", self.key(self.next_slide))
            self.window.bind("<space>", self.key(self.next_slide))
            self.window.bind("<Left>", self.key(self.previous))
            self.viewer.bind("<Configure>", self.schedule_render)
        self.window.attributes("-fullscreen", bool(fullscreen))
        self.window.lift()
        self.window.focus_set()
        self.render()

    def schedule_render(self, event=None):
        if self.window is None:
            return
        if self.resize_job is not None:
            self.window.after_cancel(self.resize_job)
        self.resize_job = self.window.after(80, self.render)

    def render(self):
        if self.window is None:
            return
        if self.resize_job is not None:
            self.window.after_cancel(self.resize_job)
        self.resize_job = None
        page = self.get_page()
        if page is None:
            return
        from PIL import ImageTk
        width, height = max(1, self.viewer.winfo_width()), max(1, self.viewer.winfo_height())
        if width < 10 or height < 10:
            return
        signature=(id(page.parent),page.number,width,height)
        if signature==self.signature:
            return
        image=self.get_image(page,width,height)
        self.photo=ImageTk.PhotoImage(image,master=self.window)
        self.signature=signature
        self.viewer.configure(image=self.photo)

    def hide(self):
        if self.window is None:
            return
        if self.resize_job is not None:
            self.window.after_cancel(self.resize_job)
        self.resize_job = None
        self.window.destroy()
        self.window = self.viewer = self.photo = None
        self.signature = None
