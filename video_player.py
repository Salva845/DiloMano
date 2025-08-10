# video_player.py
import tkinter as tk
import imageio
from PIL import Image, ImageTk
import threading
import time

class VideoPlayer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dilo Mano - Traducción en Señas")
        self.label = tk.Label(self.root)
        self.label.pack()
        self.current_video_thread = None

    def reproducir_video(self, ruta):
        if self.current_video_thread and self.current_video_thread.is_alive():
            return  # Evita solapar videos
        self.current_video_thread = threading.Thread(target=self._play, args=(ruta,))
        self.current_video_thread.start()

    def _play(self, ruta):
        try:
            reader = imageio.get_reader(ruta)
            for frame in reader:
                image = ImageTk.PhotoImage(Image.fromarray(frame))
                self.label.config(image=image)
                self.label.image = image
                time.sleep(1 / reader.get_meta_data()['fps'])
        except Exception as e:
            print(f"Error al reproducir {ruta}: {e}")

    def iniciar(self):
        self.root.mainloop()
