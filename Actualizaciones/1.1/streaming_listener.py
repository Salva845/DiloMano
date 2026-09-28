import sounddevice as sd
import vosk
import queue
import json
import numpy as np
import functools

class StreamingListener:
    def __init__(self, frase_callback, modelo_path="vosk-model-es-0.42", samplerate=16000):
        self.frase_callback = frase_callback
        self.q = queue.Queue()
        self.samplerate = samplerate
        self.ultima_palabra = ""   # 👈 guardamos última palabra reproducida

        print("Cargando modelo Vosk...")
        self.model = vosk.Model(modelo_path)
        print("Modelo cargado.")

    def _callback_audio(self, indata, frames, time_info, status):
        """Callback que procesa el audio en bruto"""
        if status:
            print(status)
        audio_int16 = np.int16(indata * 32767)
        self.q.put(audio_int16.tobytes())

    def iniciar(self, device_id=None):
        try:
            with sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                # ✅ Pasamos self usando functools.partial
                callback=functools.partial(self._callback_audio),
                device=device_id
            ):
                rec = vosk.KaldiRecognizer(self.model, self.samplerate)
                rec.SetWords(True)
                print("Escuchando en streaming...")

                while True:
                    data = self.q.get()
                    if rec.AcceptWaveform(data):
                        # ✅ Resultado final
                        result = json.loads(rec.Result())
                        frase = result.get("text", "").strip().lower()
                        if frase:
                            print("Frase final:", frase)
                            self.frase_callback(frase, final=True)
                            self.ultima_palabra = ""  # resetear
                    else:
                        # ✅ Parcial en vivo
                        partial = json.loads(rec.PartialResult())
                        frase_parcial = partial.get("partial", "").strip().lower()

                        if frase_parcial:
                            palabras = frase_parcial.split()
                            ultima = palabras[-1]
                            if ultima != self.ultima_palabra:
                                print("Parcial palabra nueva:", ultima)
                                self.frase_callback(ultima, final=False)
                                self.ultima_palabra = ultima

        except Exception as e:
            print("Error al iniciar micrófono:", e)