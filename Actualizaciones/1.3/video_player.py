import imageio
import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import os
import time
from collections import deque
import gc

class VideoPlayer:
    def __init__(self, ventana):
        # Frame donde se mostrará el video
        self.frame_video = tk.Frame(ventana, bg="black")
        self.frame_video.pack(fill="both", expand=True)

        # Label fijo para el video
        self.label_video = tk.Label(self.frame_video, bg="black")
        self.label_video.place(relx=0.5, rely=0.5, anchor="center")

        self.reproduciendo = False
        self.running = True
        self.cola_videos = queue.Queue(maxsize=100)  # Aumentar tamaño de cola
        self.lock = threading.Lock()

        # Tamaño inicial del área de video
        self.label_ancho = 640
        self.label_alto = 480
        self.label_video.config(width=self.label_ancho, height=self.label_alto)

        # Cache para frames redimensionados
        self.frame_cache = {}
        self.cache_max_size = 100
        
        # Configuración optimizada para reproducción más rápida
        self.target_fps = 45  # FPS más alto para reproducción más rápida
        self.frame_delay = 1000 // self.target_fps  # ~22ms por frame
        self.skip_frames = 1  # Saltar frames para mayor velocidad

        # Detectar cambios de tamaño del frame
        self.frame_video.bind("<Configure>", self._on_resize)

        # Hilo que procesa la cola de videos
        self.worker_thread = threading.Thread(target=self._procesar_cola, daemon=True)
        self.worker_thread.start()

    def _on_resize(self, event):
        """Actualizar tamaño cuando el frame cambia"""
        nuevo_ancho = max(event.width, 100)
        nuevo_alto = max(event.height, 100)
        
        if nuevo_ancho != self.label_ancho or nuevo_alto != self.label_alto:
            self.label_ancho = nuevo_ancho
            self.label_alto = nuevo_alto
            self.label_video.config(width=self.label_ancho, height=self.label_alto)
            # Limpiar cache cuando cambia el tamaño
            self.frame_cache.clear()

    def reproducir_videos(self, lista_videos):
        """Agrega videos a la cola para reproducir EN ORDEN"""
        if not self.running:
            return
            
        if isinstance(lista_videos, str):
            lista_videos = [lista_videos]

        # CORRECCIÓN CRÍTICA: NO LIMPIAR LA COLA
        # Los videos deben reproducirse en el orden que fueron agregados
        for video in lista_videos:
            if isinstance(video, str) and os.path.isfile(video):
                try:
                    # Intentar agregar a la cola sin bloquear
                    self.cola_videos.put_nowait(video)
                    print(f"Video agregado a cola: {os.path.basename(video)} (Total en cola: {self.cola_videos.qsize()})")
                except queue.Full:
                    print(f"⚠️ Cola llena, esperando para agregar: {os.path.basename(video)}")
                    # Si la cola está llena, esperar un poco y reintentar
                    try:
                        self.cola_videos.put(video, timeout=0.5)
                    except queue.Full:
                        print(f"❌ No se pudo agregar video a la cola: {os.path.basename(video)}")

    def _procesar_cola(self):
        """Procesa los videos en la cola uno por uno EN ORDEN"""
        while self.running:
            try:
                # Obtener el siguiente video de la cola
                video = self.cola_videos.get(timeout=1.0)
                
                with self.lock:
                    if not self.running:
                        break
                    self.reproduciendo = True

                print(f"Reproduciendo video de la cola: {os.path.basename(video)} (Quedan: {self.cola_videos.qsize()})")
                self._reproducir_video_optimizado(video)
                
                with self.lock:
                    self.reproduciendo = False
                    
                self.cola_videos.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error en procesamiento de cola: {e}")
                with self.lock:
                    self.reproduciendo = False

    def _get_cached_frame(self, frame_data, target_size):
        """Obtiene un frame del cache o lo crea y cachea"""
        cache_key = (id(frame_data), target_size)
        
        if cache_key in self.frame_cache:
            return self.frame_cache[cache_key]
        
        # Crear nuevo frame redimensionado
        img = Image.fromarray(frame_data)
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        photo_image = ImageTk.PhotoImage(img)
        
        # Agregar al cache
        if len(self.frame_cache) >= self.cache_max_size:
            # Remover el elemento más antiguo
            oldest_key = next(iter(self.frame_cache))
            del self.frame_cache[oldest_key]
        
        self.frame_cache[cache_key] = photo_image
        return photo_image

    def _reproducir_video_optimizado(self, path):
        """Reproduce un video con optimizaciones de rendimiento"""
        if not self.running:
            return
            
        print(f"Iniciando reproducción: {os.path.basename(path)}")
        reader = None
        try:
            reader = imageio.get_reader(path)
            fps = reader.get_meta_data().get('fps', 30)
            total_frames = reader.count_frames()
            
            print(f"Video: {total_frames} frames a {fps} FPS")
            
            # Ajustar velocidad basada en FPS original
            if fps > 0:
                frame_delay_original = 1000 / fps
                # Reproducir más rápido pero no demasiado
                frame_delay = max(int(frame_delay_original * 0.7), 15)  # 30% más rápido, mínimo 15ms
            else:
                frame_delay = 33  # ~30 FPS por defecto
            
            frame_count = 0
            frames_mostrados = 0
            
            for frame in reader:
                with self.lock:
                    if not self.reproduciendo or not self.running:
                        print("Reproducción interrumpida")
                        break

                frame_count += 1
                
                # Saltar algunos frames para mayor velocidad
                if self.skip_frames > 0 and frame_count % (self.skip_frames + 1) != 0:
                    continue

                try:
                    # Redimensionar frame manteniendo proporción
                    target_size = (self.label_ancho, self.label_alto)
                    
                    # Convertir frame a imagen PIL
                    img = Image.fromarray(frame)
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    image = ImageTk.PhotoImage(img)

                    # Actualizar UI en el hilo principal
                    self.frame_video.after_idle(self._update_frame, image)
                    frames_mostrados += 1
                    
                    # Pausa controlada para mantener velocidad
                    time.sleep(frame_delay / 1000.0)

                except Exception as e:
                    print(f"Error procesando frame {frame_count}: {e}")
                    continue
            
            print(f"Reproducción completada: {frames_mostrados}/{total_frames} frames mostrados")

        except Exception as e:
            print(f"Error al abrir/reproducir video {path}: {e}")
        finally:
            if reader:
                try:
                    reader.close()
                except:
                    pass
            
            # Limpiar memoria periódicamente
            if len(self.frame_cache) > 50:
                self.frame_cache.clear()
                gc.collect()

    def _update_frame(self, image):
        """Actualiza el frame en el hilo principal del UI"""
        try:
            if self.running and self.reproduciendo:
                self.label_video.config(image=image)
                self.label_video.image = image  # Mantener referencia
        except Exception as e:
            print(f"Error actualizando frame: {e}")

    def stop(self):
        """Detiene el reproductor de forma segura"""
        print("Deteniendo reproductor de video...")
        
        with self.lock:
            self.running = False
            self.reproduciendo = False

        # Limpiar cola
        while not self.cola_videos.empty():
            try:
                self.cola_videos.get_nowait()
            except queue.Empty:
                break

        # Limpiar cache
        self.frame_cache.clear()
        
        # Limpiar imagen del label
        try:
            self.label_video.config(image="")
            self.label_video.image = None
        except:
            pass
            
        print("Reproductor detenido.")

    def __del__(self):
        """Destructor para limpieza"""
        self.stop()