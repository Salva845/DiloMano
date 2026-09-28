import sounddevice as sd
import vosk
import queue
import json
import numpy as np
import functools
import threading
from collections import deque
import time

class StreamingListener:
    def __init__(self, frase_callback, modelo_path="vosk-model-es-0.42", samplerate=16000):
        self.frase_callback = frase_callback
        # Usar deque para mejor performance en operaciones frecuentes
        self.q = queue.Queue(maxsize=50)  # Limitar tamaño para evitar acumulación
        self.samplerate = samplerate
        self.ultima_palabra = ""
        self.running = False
        self.model = None
        self.stream = None
        
        # Cache de palabras recientes para evitar repeticiones
        self.cache_palabras = deque(maxlen=10)
        self.ultimo_tiempo = time.time()
        
        # CORREGIDO: Inicializar el diccionario para tiempos de palabras
        self.ultimo_tiempo_palabra = {}  # <-- ESTA LÍNEA FALTABA
        
        # Configuración optimizada
        self.blocksize = 4096  # Tamaño de bloque optimizado
        self.dtype = np.float32  # Usar float32 para mejor performance
        
        print("Inicializando modelo Vosk...")
        self._init_model(modelo_path)

    def _init_model(self, modelo_path):
        """Inicializa el modelo con manejo de errores"""
        try:
            self.model = vosk.Model(modelo_path)
            print("Modelo Vosk cargado exitosamente.")
        except Exception as e:
            print(f"Error cargando modelo Vosk: {e}")
            raise

    def _callback_audio(self, indata, frames, time_info, status):
        """Callback optimizado que procesa el audio en bruto"""
        if status:
            print(f"Audio callback status: {status}")
        
        if not self.running:
            return
            
        try:
            # Conversión más eficiente
            audio_int16 = (indata * 32767).astype(np.int16)
            data = audio_int16.tobytes()
            
            # Usar put_nowait para evitar bloqueos
            try:
                self.q.put_nowait(data)
            except queue.Full:
                # Descartar datos antiguos si la cola está llena
                try:
                    self.q.get_nowait()
                    self.q.put_nowait(data)
                except queue.Empty:
                    pass
                    
        except Exception as e:
            print(f"Error en callback de audio: {e}")

    def _procesar_audio(self, rec):
        """Procesa el audio en un hilo separado para mejor performance"""
        while self.running:
            try:
                # Timeout para evitar bloqueos indefinidos
                data = self.q.get(timeout=1.0)
                
                if rec.AcceptWaveform(data):
                    # ✅ Resultado final
                    result = json.loads(rec.Result())
                    frase = result.get("text", "").strip().lower()
                    if frase and len(frase.split()) > 0:
                        print(f"Frase final: {frase}")
                        self.frase_callback(frase, final=True)
                        self.ultima_palabra = ""
                        self.cache_palabras.clear()
                        # Limpiar el diccionario de tiempos cuando se completa una frase
                        self.ultimo_tiempo_palabra.clear()
                else:
                    # ✅ Resultado parcial optimizado
                    tiempo_actual = time.time()
                    # Limitar frecuencia de procesamiento de parciales
                    if tiempo_actual - self.ultimo_tiempo < 0.2:  # Reducido a 5 Hz
                        continue
                    
                    partial = json.loads(rec.PartialResult())
                    frase_parcial = partial.get("partial", "").strip().lower()

                    if frase_parcial:
                        palabras = frase_parcial.split()
                        if palabras:
                            ultima = palabras[-1]
                            
                            # Permitir palabras repetidas después de cierto tiempo
                            tiempo_ultima_palabra = self.ultimo_tiempo_palabra.get(ultima, 0)
                            tiempo_desde_ultima_palabra = tiempo_actual - tiempo_ultima_palabra
                            
                            # Condiciones más flexibles para permitir repetición
                            if (len(ultima) > 2 and  # Mínimo 3 caracteres
                                (ultima != self.ultima_palabra or tiempo_desde_ultima_palabra > 3.0) and  # Diferente o pasaron 3 segundos
                                tiempo_actual - self.ultimo_tiempo > 0.3):  # Mínimo 300ms entre detecciones
                                
                                print(f"Nueva palabra: {ultima}")
                                self.frase_callback(ultima, final=False)
                                self.ultima_palabra = ultima
                                self.ultimo_tiempo_palabra[ultima] = tiempo_actual
                                self.cache_palabras.append(ultima)
                                self.ultimo_tiempo = tiempo_actual
                                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error procesando audio: {e}")
                if not self.running:
                    break

    def iniciar(self, device_id=None):
        """Inicia el streaming de audio con configuración optimizada"""
        if not self.model:
            raise Exception("Modelo no inicializado")
            
        self.running = True
        
        try:
            # Crear reconocedor con configuración optimizada
            rec = vosk.KaldiRecognizer(self.model, self.samplerate)
            rec.SetWords(True)
            # Configurar para resultados más rápidos
            rec.SetMaxAlternatives(1)
            # Remover SpkModel ya que causa problemas y no es necesario
            
            print(f"Iniciando stream de audio (dispositivo: {device_id})...")
            
            # Iniciar hilo de procesamiento de audio
            audio_thread = threading.Thread(
                target=self._procesar_audio, 
                args=(rec,), 
                daemon=True
            )
            audio_thread.start()
            
            # Configuración optimizada del stream
            with sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype=self.dtype,
                blocksize=self.blocksize,
                callback=functools.partial(self._callback_audio),
                device=device_id,
                latency='low'  # Latencia baja para mejor respuesta
            ) as self.stream:
                
                print("Streaming de audio activo...")
                
                # Mantener el stream activo mientras running sea True
                while self.running:
                    time.sleep(0.1)
                    
        except Exception as e:
            print(f"Error al iniciar micrófono: {e}")
            self.running = False
            raise
        finally:
            self.stop()

    def stop(self):
        """Detiene el streaming de forma segura"""
        print("Deteniendo streaming de audio...")
        self.running = False
        
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except:
                pass
                
        # Limpiar cola
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
                
        print("Streaming detenido.")