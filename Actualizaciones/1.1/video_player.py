import imageio
import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import os

class VideoPlayer:
    def __init__(self, ventana):
        # Frame donde se mostrará el video
        self.frame_video = tk.Frame(ventana, bg="black")
        self.frame_video.pack(fill="both", expand=True)

        # Label fijo para el video
        self.label_video = tk.Label(self.frame_video, bg="black")
        self.label_video.place(relx=0.5, rely=0.5, anchor="center")  
        # 🔹 IMPORTANTE: usamos place() para que no cambie de tamaño ni mueva los demás widgets

        self.reproduciendo = False
        self.cola_videos = queue.Queue()
        self.lock = threading.Lock()

        # Tamaño inicial del área de video
        self.label_ancho = 640
        self.label_alto = 480
        self.label_video.config(width=self.label_ancho, height=self.label_alto)

        # Detectar cambios de tamaño del frame
        self.frame_video.bind("<Configure>", self._on_resize)

        # Hilo que procesa la cola de videos
        threading.Thread(target=self._procesar_cola, daemon=True).start()

    def _on_resize(self, event):
        """Actualizar tamaño cuando el frame cambia"""
        self.label_ancho = event.width
        self.label_alto = event.height
        self.label_video.config(width=self.label_ancho, height=self.label_alto)

    def reproducir_videos(self, lista_videos):
        """Agrega videos a la cola para reproducir"""
        if isinstance(lista_videos, str):
            lista_videos = [lista_videos]

        with self.lock:
            cola_actual = list(self.cola_videos.queue)
            for video in lista_videos:
                if isinstance(video, str) and os.path.isfile(video) and video not in cola_actual:
                    self.cola_videos.put(video)

    def _procesar_cola(self):
        """Procesa los videos en la cola uno por uno"""
        while True:
            video = self.cola_videos.get()
            with self.lock:
                self.reproduciendo = True
            self.reproducir_video(video)
            with self.lock:
                self.reproduciendo = False
            self.cola_videos.task_done()

    def reproducir_video(self, path):
        """Reproduce un video dentro del label sin que el label cambie de tamaño"""
        try:
            reader = imageio.get_reader(path)
        except Exception as e:
            print(f"Error al abrir video {path}: {e}")
            return

        for frame in reader:
            with self.lock:
                if not self.reproduciendo:
                    break

            # Convertir frame a imagen PIL
            img = Image.fromarray(frame)

            # 🔹 Escalar manteniendo proporción al tamaño del label
            img.thumbnail((self.label_ancho, self.label_alto), Image.Resampling.LANCZOS)

            # Convertir a PhotoImage para Tkinter
            image = ImageTk.PhotoImage(img)

            # Mostrar frame centrado (sin redimensionar el label)
            self.label_video.config(image=image)
            self.label_video.image = image

            # Actualizar ventana
            self.frame_video.update_idletasks()
            self.frame_video.after(33)  # ~30 FPS

        reader.close()