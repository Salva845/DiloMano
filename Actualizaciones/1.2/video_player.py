import imageio
import tkinter as tk
from PIL import Image, ImageTk
import threading
import queue
import os
import time

class VideoPlayer:
    def __init__(self, ventana):
        # Frame donde se mostrará el video
        self.frame_video = tk.Frame(ventana, bg="black")
        self.frame_video.pack(fill="both", expand=True)

        # Label fijo para el video
        self.label_video = tk.Label(self.frame_video, bg="black", text="Esperando video...", 
                                   fg="white", font=("Arial", 14))
        self.label_video.place(relx=0.5, rely=0.5, anchor="center")

        self.reproduciendo = False
        self.cola_videos = queue.Queue()  # Sin límite para clases largas
        self.lock = threading.Lock()

        # Tamaño inicial del área de video
        self.label_ancho = 640
        self.label_alto = 480
        self.label_video.config(width=self.label_ancho, height=self.label_alto)
        
        # Control de velocidad
        self.velocidad_reproduccion = 1.0
        
        # Estadísticas para monitoreo en clases
        self.estadisticas = {
            'videos_procesados': 0,
            'videos_en_cola': 0,
            'tiempo_total_reproduccion': 0.0,
            'videos_fallidos': 0,
            'ultimo_video': None,
            'sesion_iniciada': time.time()
        }

        # Detectar cambios de tamaño del frame
        self.frame_video.bind("<Configure>", self._on_resize)

        # Hilo que procesa la cola de videos
        self.hilo_procesador = threading.Thread(target=self._procesar_cola, daemon=True)
        self.hilo_procesador.start()
        
        print("🎬 VideoPlayer inicializado")

    def _on_resize(self, event):
        """Actualizar tamaño cuando el frame cambia"""
        if event.widget == self.frame_video:
            nuevo_ancho = max(320, event.width - 20)
            nuevo_alto = max(240, event.height - 20)
            
            if nuevo_ancho != self.label_ancho or nuevo_alto != self.label_alto:
                self.label_ancho = nuevo_ancho
                self.label_alto = nuevo_alto
                self.label_video.config(width=self.label_ancho, height=self.label_alto)

    def reproducir_videos(self, lista_videos):
        """Agrega videos a la cola sin límites (ideal para clases largas)"""
        if isinstance(lista_videos, str):
            lista_videos = [lista_videos]

        videos_agregados = 0
        
        with self.lock:
            # Obtener cola actual para evitar duplicados consecutivos
            cola_actual = list(self.cola_videos.queue)
            
            for video in lista_videos:
                if isinstance(video, str) and video.strip():
                    # Verificar que el archivo existe
                    if not os.path.isfile(video):
                        print(f"⚠️ Video no encontrado: {video}")
                        with self.lock:
                            self.estadisticas['videos_fallidos'] += 1
                        continue
                    
                    # Evitar duplicados consecutivos pero permitir cola grande
                    if not cola_actual or cola_actual[-1] != video:
                        self.cola_videos.put(video)
                        cola_actual.append(video)
                        videos_agregados += 1
            
            # Actualizar estadísticas
            self.estadisticas['videos_en_cola'] = self.cola_videos.qsize()
            
        if videos_agregados > 0:
            print(f"📹 Videos agregados: {videos_agregados}, Cola total: {self.cola_videos.qsize()}")

    def _procesar_cola(self):
        """Procesa videos con mejor manejo de errores y timeouts"""
        print("Procesador de cola iniciado")
        
        while True:
            try:
                # Timeout para get - evita bloqueos infinitos
                video = self.cola_videos.get(timeout=1)
                
                with self.lock:
                    self.reproduciendo = True
                    self.estadisticas['ultimo_video'] = os.path.basename(video)
                
                # LÍMITE DE COLA para evitar memoria excesiva
                if self.cola_videos.qsize() > 200:  # Límite razonable
                    print("Cola muy grande, limpiando...")
                    self._limpiar_cola_automatica(100)  # Mantener solo 100 videos
                
                inicio_reproduccion = time.time()
                exito = self.reproducir_video(video)
                tiempo_reproduccion = time.time() - inicio_reproduccion
                
                with self.lock:
                    if exito:
                        self.estadisticas['videos_procesados'] += 1
                        self.estadisticas['tiempo_total_reproduccion'] += tiempo_reproduccion
                    else:
                        self.estadisticas['videos_fallidos'] += 1
                    
                    self.estadisticas['videos_en_cola'] = self.cola_videos.qsize()
                    self.reproduciendo = False
                
                self.cola_videos.task_done()
                
            except queue.Empty:
                # Timeout normal, continuar
                continue
            except Exception as e:
                print(f"Error en procesador: {e}")
                with self.lock:
                    self.reproduciendo = False
                    self.estadisticas['videos_fallidos'] += 1

    def reproducir_video(self, path):
        """Reproduce un video dentro del label con velocidad ajustable"""
        try:
            reader = imageio.get_reader(path)
            print(f"▶️ Reproduciendo: {os.path.basename(path)}")
        except Exception as e:
            print(f"❌ Error al abrir video {path}: {e}")
            return False

        try:
            fps_base = 30
            delay_ms = max(1, int((1000 / fps_base) / self.velocidad_reproduccion))

            for i, frame in enumerate(reader):
                # Verificar si se debe detener
                with self.lock:
                    if not self.reproduciendo:
                        print("⏹️ Reproducción interrumpida")
                        break

                # Convertir frame a imagen PIL
                img = Image.fromarray(frame)

                # Escalar manteniendo proporción al tamaño del label
                img.thumbnail((self.label_ancho, self.label_alto), Image.Resampling.LANCZOS)

                # Convertir a PhotoImage para Tkinter
                image = ImageTk.PhotoImage(img)

                # Mostrar frame centrado
                self.label_video.config(image=image, text="")
                self.label_video.image = image

                # Actualizar ventana
                try:
                    self.frame_video.update_idletasks()
                    self.frame_video.after(delay_ms)
                except tk.TclError:
                    # La ventana fue cerrada
                    break

            reader.close()
            print(f"✅ Video completado: {os.path.basename(path)}")
            return True
            
        except Exception as e:
            print(f"❌ Error durante reproducción de {path}: {e}")
            try:
                reader.close()
            except:
                pass
            return False

    def set_velocidad(self, velocidad):
        """Ajusta velocidad de reproducción (0.5 = lento, 2.0 = rápido)"""
        velocidad_anterior = self.velocidad_reproduccion
        self.velocidad_reproduccion = max(0.1, min(3.0, velocidad))
        print(f"🎛️ Velocidad cambiada: {velocidad_anterior:.1f}x → {self.velocidad_reproduccion:.1f}x")

    def get_estadisticas_cola(self):
        """Retorna estadísticas de la cola para monitoreo en clases"""
        with self.lock:
            stats = self.estadisticas.copy()
            stats['videos_en_cola'] = self.cola_videos.qsize()
            stats['tiempo_sesion'] = time.time() - stats['sesion_iniciada']
            
            # Calcular estadísticas derivadas
            if stats['videos_procesados'] > 0:
                stats['tiempo_promedio_video'] = stats['tiempo_total_reproduccion'] / stats['videos_procesados']
                stats['videos_por_minuto'] = stats['videos_procesados'] / (stats['tiempo_sesion'] / 60)
            else:
                stats['tiempo_promedio_video'] = 0
                stats['videos_por_minuto'] = 0
            
            # Tasa de éxito
            total_intentos = stats['videos_procesados'] + stats['videos_fallidos']
            if total_intentos > 0:
                stats['tasa_exito'] = (stats['videos_procesados'] / total_intentos) * 100
            else:
                stats['tasa_exito'] = 100
                
        return stats

    def _limpiar_cola_automatica(self, mantener=100):
        """Limpia automáticamente la cola manteniendo solo N videos"""
        descartados = 0
        cola_temp = []
        
        # Extraer videos de la cola
        while not self.cola_videos.empty() and len(cola_temp) < mantener:
            try:
                cola_temp.append(self.cola_videos.get_nowait())
            except queue.Empty:
                break
        
        # Descartar el resto
        while not self.cola_videos.empty():
            try:
                self.cola_videos.get_nowait()
                descartados += 1
            except queue.Empty:
                break
        
        # Reintroducir videos mantenidos
        for video in cola_temp:
            self.cola_videos.put(video)
        
        print(f"Cola automática: {descartados} descartados, {len(cola_temp)} mantenidos")
        return descartados

    def pausar_reproduccion(self):
        """Pausa/reanuda la reproducción actual"""
        with self.lock:
            self.reproduciendo = not self.reproduciendo
            estado = "pausada" if not self.reproduciendo else "reanudada"
            print(f"⏸️ Reproducción {estado}")
            return not self.reproduciendo  # Retorna True si está pausado

    def esta_reproduciendo(self):
        """Verifica si está reproduciendo actualmente"""
        with self.lock:
            return self.reproduciendo

    def reset_estadisticas(self):
        """Reinicia estadísticas (útil entre clases)"""
        with self.lock:
            self.estadisticas = {
                'videos_procesados': 0,
                'videos_en_cola': self.cola_videos.qsize(),
                'tiempo_total_reproduccion': 0.0,
                'videos_fallidos': 0,
                'ultimo_video': None,
                'sesion_iniciada': time.time()
            }
        print("📊 Estadísticas de video reiniciadas")