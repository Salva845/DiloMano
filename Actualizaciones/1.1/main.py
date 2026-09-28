import tkinter as tk
from video_player import VideoPlayer
from translator import Translator, normalizar, obtener_raiz
from streaming_listener import StreamingListener
import threading
from diccionario import diccionario_senas

class App:
    def __init__(self, root, mic_id=None):
        self.root = root
        self.root.title("Dilo Mano")
        self.root.geometry("800x600")
        self.root.minsize(400, 300)

        # 🔹 Frame para el video (ocupa la parte superior y es responsive)
        frame_video = tk.Frame(root, bg="black")
        frame_video.pack(fill="both", expand=True)

        # 🔹 Frame para controles (texto + botón abajo)
        frame_controles = tk.Frame(root)
        frame_controles.pack(fill="x", pady=5)

        # Reproductor de video en el frame superior
        self.player = VideoPlayer(frame_video)
        self.translator = Translator()

        # Texto de detección
        self.label = tk.Label(frame_controles, text="Habla para mostrar señas...", font=("Arial", 14))
        self.label.pack(side="left", padx=10)

        # Botón mute
        self.muted = False
        self.btn_mute = tk.Button(frame_controles, text="🔇 Mutear", command=self.toggle_mute)
        self.btn_mute.pack(side="right", padx=10)

        # 🔹 Modo de reconocimiento (parciales/finales)
        self.modo = tk.StringVar(value="parciales")
        menu_modo = tk.OptionMenu(frame_controles, self.modo, "parciales", "finales")
        menu_modo.pack(side="right", padx=10)

        # Solo última palabra reproducida (para evitar duplicados en parciales)
        self.ultima_palabra = ""

        # Listener en un hilo separado
        self.listener = StreamingListener(self.procesar_frase, modelo_path="vosk-model-es-0.42")
        threading.Thread(target=self.listener.iniciar, daemon=True, args=(mic_id,)).start()

    def toggle_mute(self):
        """Activa/desactiva el micrófono"""
        self.muted = not self.muted
        if self.muted:
            self.btn_mute.config(text="🎤 Activar micrófono")
            self.label.config(text="Micrófono en silencio")
        else:
            self.btn_mute.config(text="🔇 Mutear")
            self.label.config(text="Micrófono activado, habla...")

    def procesar_frase(self, frase, final=False):
        """Procesa la frase detectada por el listener"""
        if self.muted:
            return  # Ignorar audio si está muteado

        modo_actual = self.modo.get()

        # 🔹 MODO PARCIALES
        if modo_actual == "parciales" and not final:
            # ✅ usamos el Translator para que también imprima logs
            videos = self.translator.traducir(frase)

            if videos:
                # Tomamos solo el primero (última palabra traducida)
                ultima_ruta = videos[-1]

                palabra_raiz = obtener_raiz(frase.split()[-1])
                if palabra_raiz != self.ultima_palabra:
                    self.player.reproducir_videos(ultima_ruta)
                    self.ultima_palabra = palabra_raiz

            self.label.config(text=f"Detectado (parcial): {frase}")
            return


        # 🔹 MODO FINALES
        if modo_actual == "finales" and final:
            self.label.config(text=f"Frase final: {frase}")
            videos = self.translator.traducir(frase)
            if videos:
                self.player.reproducir_videos(videos)
            self.ultima_palabra = ""  # resetear

if __name__ == "__main__":
    root = tk.Tk()

    MIC_ID = 1  

    app = App(root, mic_id=MIC_ID)
    root.mainloop()