# audio_listener_whisper.py
import sounddevice as sd
import numpy as np
import threading
import time
from faster_whisper import WhisperModel
from translator import traducir_a_video

class AudioListenerWhisper:
    def __init__(self, video_player, ventana_seg=2.5, solapamiento_seg=0.5):
        self.video_player = video_player
        self.ventana = ventana_seg
        self.solapamiento = solapamiento_seg
        self.fs = 16000  # Frecuencia que Whisper usa
        self.modelo = WhisperModel("small", device="cpu", compute_type="int8")
        self.is_listening = False

    def _grabar_y_procesar(self):
        while self.is_listening:
            audio = sd.rec(int(self.ventana * self.fs), samplerate=self.fs, channels=1, dtype="float32")
            sd.wait()
            threading.Thread(target=self._procesar_audio, args=(audio.copy(),)).start()
            time.sleep(self.ventana - self.solapamiento)

    def _procesar_audio(self, audio):
        try:
            segments, _ = self.modelo.transcribe(audio, language="es")
            for segment in segments:
                texto = segment.text.strip().lower()
                print(f"Detectado: {texto}")
                for palabra in texto.split():
                    ruta_video = traducir_a_video(palabra)
                    if ruta_video:
                        self.video_player.reproducir_video(ruta_video)
        except Exception as e:
            print(f"Error al transcribir: {e}")

    def iniciar(self):
        self.is_listening = True
        threading.Thread(target=self._grabar_y_procesar).start()

    def detener(self):
        self.is_listening = False
