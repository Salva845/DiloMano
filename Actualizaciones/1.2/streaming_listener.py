import sounddevice as sd
import vosk
import queue
import json
import numpy as np
import functools
import os
import threading
import time

class StreamingListener:
    def __init__(self, frase_callback, modelo_path="vosk-model-es-0.42", samplerate=16000):
        self.frase_callback = frase_callback
        self.q = queue.Queue()
        self.samplerate = samplerate
        self.ultima_palabra = ""
        self.activo = False
        self.modelo_path = modelo_path
        self.model = None
        self.rec = None
        self._lock = threading.Lock()
        
        # Estadísticas
        self.stats = {
            'palabras_detectadas': 0,
            'frases_finales': 0,
            'tiempo_actividad': 0.0,
            'inicio_sesion': None
        }
        
        # Validar e inicializar modelo
        self._inicializar_modelo()
    
    def _inicializar_modelo(self):
        """Inicializa el modelo Vosk con validación"""
        if not os.path.exists(self.modelo_path):
            raise FileNotFoundError(f"Modelo Vosk no encontrado en: {self.modelo_path}")
        
        try:
            print("Cargando modelo Vosk...")
            self.model = vosk.Model(self.modelo_path)
            print("Modelo Vosk cargado exitosamente.")
        except Exception as e:
            raise RuntimeError(f"Error cargando modelo Vosk: {e}")
    
    def validar_microfono(self, device_id=None):
        """Valida que el micrófono esté disponible y funcional"""
        try:
            devices = sd.query_devices()
            print(f"Dispositivos de audio disponibles: {len(devices)}")
            
            if device_id is not None:
                if device_id >= len(devices) or device_id < 0:
                    print(f"❌ Micrófono ID {device_id} no existe")
                    return False
                
                device = devices[device_id]
                if device['max_input_channels'] == 0:
                    print(f"❌ El dispositivo {device_id} no tiene canales de entrada")
                    return False
                
                print(f"✅ Micrófono seleccionado: {device['name']}")
            
            # Test básico del micrófono
            try:
                with sd.InputStream(
                    samplerate=self.samplerate, 
                    channels=1, 
                    device=device_id,
                    blocksize=1024
                ) as test_stream:
                    # Leer un pequeño buffer para verificar que funciona
                    data = test_stream.read(1024)[0]
                    print(f"✅ Micrófono funcionando correctamente")
                return True
            except Exception as e:
                print(f"❌ Error al probar micrófono: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error validando micrófono: {e}")
            return False
    
    def listar_microfonos(self):
        """Lista todos los micrófonos disponibles"""
        try:
            devices = sd.query_devices()
            microfonos = []
            print("\n📱 Micrófonos disponibles:")
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    info = {
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'samplerate': device['default_samplerate']
                    }
                    microfonos.append(info)
                    print(f"  {i}: {device['name']} ({device['max_input_channels']} canales)")
            return microfonos
        except Exception as e:
            print(f"Error listando micrófonos: {e}")
            return []
    
    def _callback_audio(self, indata, frames, time_info, status):
        """Callback que procesa el audio en bruto"""
        if status:
            print(f"Estado de audio: {status}")
        
        if self.activo:
            try:
                audio_int16 = np.int16(indata * 32767)
                self.q.put(audio_int16.tobytes())
            except Exception as e:
                print(f"Error en callback de audio: {e}")
    
    def iniciar(self, device_id=None):
        """Inicia el reconocimiento de voz con timeouts para evitar cuelgues"""
        if not self.validar_microfono(device_id):
            print("MicróÃ³fono no válido")
            return False
        
        with self._lock:
            if self.activo:
                print("Listener ya activo")
                return False
            self.activo = True
            self.stats['inicio_sesion'] = time.time()
        
        try:
            # TIMEOUT para inicialización del recognizer
            self.rec = vosk.KaldiRecognizer(self.model, self.samplerate)
            self.rec.SetWords(True)
            
            with sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                callback=functools.partial(self._callback_audio),
                device=device_id,
                blocksize=1024
            ) as stream:
                
                print(f"Escuchando (dispositivo: {device_id})...")
                ultimo_procesamiento = time.time()
                
                while self.activo:
                    try:
                        # TIMEOUT más corto para evitar bloqueos
                        data = self.q.get(timeout=0.5)
                        ultimo_procesamiento = time.time()
                        
                        # Procesar en try-catch separado
                        try:
                            if self.rec.AcceptWaveform(data):
                                # Resultado final con timeout
                                result = json.loads(self.rec.Result())
                                frase = result.get("text", "").strip().lower()
                                
                                if frase and self.activo:
                                    print(f"Final: '{frase}'")
                                    with self._lock:
                                        self.stats['frases_finales'] += 1
                                    
                                    # Usar threading para callback - EVITA BLOQUEOS
                                    threading.Thread(
                                        target=self._safe_callback,
                                        args=(frase, True),
                                        daemon=True
                                    ).start()
                                    
                                    self.ultima_palabra = ""
                            else:
                                # Resultado parcial
                                partial = json.loads(self.rec.PartialResult())
                                frase_parcial = partial.get("partial", "").strip().lower()
                                
                                if frase_parcial and self.activo:
                                    palabras = frase_parcial.split()
                                    if palabras:
                                        ultima = palabras[-1]
                                        # CORRECCIÓN PARA PALABRAS CORTAS
                                        palabras_cortas_importantes = {'yo', 'tu', 'el', 'si', 'no', 'mi', 'su', 'ya'}
                                        if (ultima != self.ultima_palabra and 
                                            (len(ultima) > 2 or ultima in palabras_cortas_importantes)):
                                            
                                            print(f"Parcial: '{ultima}'")
                                            with self._lock:
                                                self.stats['palabras_detectadas'] += 1
                                            
                                            # Threading para callback parcial también
                                            threading.Thread(
                                                target=self._safe_callback,
                                                args=(ultima, False),
                                                daemon=True
                                            ).start()
                                            
                                            self.ultima_palabra = ultima
                        
                        except json.JSONDecodeError as e:
                            print(f"Error JSON: {e}")
                            continue
                        except Exception as e:
                            print(f"Error procesamiento: {e}")
                            continue
                    
                    except queue.Empty:
                        # Verificar si llevamos mucho tiempo sin datos (posible cuelgue)
                        if time.time() - ultimo_procesamiento > 10:
                            print("Posible cuelgue detectado, reiniciando...")
                            break
                        continue
                    except Exception as e:
                        print(f"Error crítico: {e}")
                        break
                        
        except Exception as e:
            print(f"Error en streaming: {e}")
            return False
        finally:
            with self._lock:
                self.activo = False
                if self.stats['inicio_sesion']:
                    self.stats['tiempo_actividad'] = time.time() - self.stats['inicio_sesion']
            print("Streaming detenido")
        
        return True
    
    def _safe_callback(self, frase, final):
        """Callback seguro con timeout para evitar cuelgues"""
        try:
            # TIMEOUT de 2 segundos para callback
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Callback timeout")
            
            # Solo en sistemas que soportan signal (no Windows en algunos casos)
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(2)
                self.frase_callback(frase, final=final)
                signal.alarm(0)
            except (AttributeError, OSError):
                # Fallback sin signal - solo ejecutar callback
                self.frase_callback(frase, final=final)
                
        except TimeoutError:
            print(f"Callback timeout para: {frase}")
        except Exception as e:
            print(f"Error en callback: {e}")

    def detener(self):
        """Detiene el reconocimiento de voz de forma controlada"""
        with self._lock:
            if self.activo:
                print("🛑 Deteniendo streaming...")
                self.activo = False
                return True
            return False
    
    def esta_activo(self):
        """Verifica si el listener está activo"""
        with self._lock:
            return self.activo
    
    def get_stats(self):
        """Retorna estadísticas del listener"""
        with self._lock:
            stats = self.stats.copy()
            if self.activo and self.stats['inicio_sesion']:
                stats['tiempo_actividad'] = time.time() - self.stats['inicio_sesion']
        return stats
    
    def reset_stats(self):
        """Reinicia estadísticas"""
        with self._lock:
            self.stats = {
                'palabras_detectadas': 0,
                'frases_finales': 0,
                'tiempo_actividad': 0.0,
                'inicio_sesion': time.time() if self.activo else None
            }