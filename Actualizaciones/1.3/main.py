import tkinter as tk
from video_player import VideoPlayer
# Importar traductor primero para que Stanza se inicialice temprano
from translator import Translator, obtener_raiz  
from streaming_listener import StreamingListener
import threading
import time
from diccionario import diccionario_senas
import sys
import signal

class App:
    def __init__(self, root, mic_id=None):
        self.root = root
        self.root.title("Dilo Mano")
        self.root.geometry("800x600")
        self.root.minsize(400, 300)
        
        # Configurar cierre limpio
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.running = True

        # Variables de control - INICIALIZAR PRIMERO
        self.ultima_palabra_parcial = ""
        self.ultimo_tiempo_parcial = 0
        self.tiempo_minimo_entre_parciales = 0.5  # Reducido para permitir más fluidez
        self.muted = False
        self.lock = threading.Lock()
        
        # Historial de palabras recientes para evitar repeticiones EXCESIVAS
        self.palabras_recientes = []
        self.max_palabras_recientes = 5

        print("Inicializando componentes de la aplicación...")

        # 📹 Frame para el video (ocupa la parte superior y es responsive)
        frame_video = tk.Frame(root, bg="black")
        frame_video.pack(fill="both", expand=True)

        # 📹 Frame para controles (texto + botón abajo)
        frame_controles = tk.Frame(root)
        frame_controles.pack(fill="x", pady=5)

        # Reproductor de video en el frame superior
        print("Inicializando reproductor de video...")
        self.player = VideoPlayer(frame_video)
        
        # Translator - ya inicializado al importar
        print("Inicializando traductor...")
        self.translator = Translator()
        print("Traductor listo.")

        # Texto de detección
        self.label = tk.Label(frame_controles, text="Habla para mostrar señas...", font=("Arial", 14))
        self.label.pack(side="left", padx=10)

        # Botón mute
        self.btn_mute = tk.Button(frame_controles, text="🔇 Mutear", command=self.toggle_mute)
        self.btn_mute.pack(side="right", padx=10)

        # 📹 Modo de reconocimiento (parciales/finales)
        self.modo = tk.StringVar(value="parciales")
        menu_modo = tk.OptionMenu(frame_controles, self.modo, "parciales", "finales")
        menu_modo.pack(side="right", padx=10)

        # Listener en un hilo separado con manejo de errores
        self.listener = None
        self.init_listener(mic_id)

        print("Aplicación completamente inicializada.")

    def init_listener(self, mic_id):
        """Inicializa el listener con manejo de errores"""
        try:
            print("Inicializando listener de audio...")
            self.listener = StreamingListener(self.procesar_frase, modelo_path="vosk-model-es-0.42")
            listener_thread = threading.Thread(target=self._start_listener_safe, daemon=True, args=(mic_id,))
            listener_thread.start()
        except Exception as e:
            print(f"Error inicializando listener: {e}")
            self.label.config(text="Error: No se pudo inicializar el micrófono")

    def _start_listener_safe(self, mic_id):
        """Inicia el listener con manejo seguro de errores"""
        try:
            if self.listener:
                self.listener.iniciar(mic_id)
        except Exception as e:
            print(f"Error en listener: {e}")
            # Programar actualización del UI en el hilo principal
            self.root.after(0, lambda: self.label.config(text="Error en micrófono"))

    def toggle_mute(self):
        """Activa/desactiva el micrófono de forma thread-safe"""
        with self.lock:
            self.muted = not self.muted
            if self.muted:
                self.root.after(0, lambda: self.btn_mute.config(text="🎤 Activar micrófono"))
                self.root.after(0, lambda: self.label.config(text="Micrófono en silencio"))
            else:
                self.root.after(0, lambda: self.btn_mute.config(text="🔇 Mutear"))
                self.root.after(0, lambda: self.label.config(text="Micrófono activado, habla..."))

    def procesar_frase(self, frase, final=False):
        """Procesa la frase detectada por el listener de forma thread-safe"""
        if not self.running:
            return
            
        with self.lock:
            if self.muted:
                return  # Ignorar audio si está muteado

            modo_actual = self.modo.get()

        # Programar actualización del UI en el hilo principal
        self.root.after(0, lambda: self._procesar_frase_ui(frase, final, modo_actual))

    def _procesar_frase_ui(self, frase, final, modo_actual):
        """Procesa la frase en el hilo principal del UI"""
        try:
            tiempo_actual = time.time()
            
            # 📹 MODO PARCIALES - CORREGIDO
            if modo_actual == "parciales" and not final:
                # En modo parciales, procesar CADA palabra nueva detectada
                palabras = frase.split()
                
                if palabras:
                    # Obtener la última palabra
                    ultima_palabra = palabras[-1]
                    palabra_raiz = obtener_raiz(ultima_palabra)
                    
                    # Verificar tiempo mínimo entre detecciones de la MISMA palabra
                    tiempo_desde_ultima = tiempo_actual - self.ultimo_tiempo_parcial
                    
                    # Condiciones más permisivas para permitir palabras repetidas naturalmente
                    puede_reproducir = False
                    
                    if palabra_raiz != self.ultima_palabra_parcial:
                        # Palabra diferente, siempre reproducir
                        puede_reproducir = True
                    elif tiempo_desde_ultima > self.tiempo_minimo_entre_parciales:
                        # Misma palabra pero pasó suficiente tiempo
                        puede_reproducir = True
                        # Verificar que no sea una repetición excesiva
                        conteo_recientes = self.palabras_recientes.count(palabra_raiz)
                        if conteo_recientes > 2 and tiempo_desde_ultima < 2.0:
                            # Demasiadas repeticiones muy rápidas
                            puede_reproducir = False
                    
                    if puede_reproducir:
                        # Traducir solo la última palabra
                        videos = self.translator.traducir(ultima_palabra)
                        
                        if videos:
                            print(f"✅ Agregando a cola: {palabra_raiz}")
                            # IMPORTANTE: Agregar TODOS los videos a la cola
                            self.player.reproducir_videos(videos)
                            
                            self.ultima_palabra_parcial = palabra_raiz
                            self.ultimo_tiempo_parcial = tiempo_actual
                            
                            # Actualizar historial de palabras recientes
                            self.palabras_recientes.append(palabra_raiz)
                            if len(self.palabras_recientes) > self.max_palabras_recientes:
                                self.palabras_recientes.pop(0)
                    else:
                        print(f"⏳ Esperando antes de repetir: {palabra_raiz}")

                self.label.config(text=f"Detectado (parcial): {frase}")
                return

            # 📹 MODO FINALES - Procesar toda la frase
            if modo_actual == "finales" and final:
                self.label.config(text=f"Frase final: {frase}")
                videos = self.translator.traducir(frase)
                
                if videos:
                    print(f"📹 Agregando {len(videos)} videos a la cola (frase completa)")
                    # Agregar TODOS los videos de la frase a la cola
                    self.player.reproducir_videos(videos)
                
                # Resetear controles para la siguiente frase
                self.ultima_palabra_parcial = ""
                self.ultimo_tiempo_parcial = tiempo_actual
                self.palabras_recientes.clear()
                
        except Exception as e:
            print(f"Error procesando frase: {e}")
            import traceback
            traceback.print_exc()
            self.label.config(text="Error procesando audio")

    def on_closing(self):
        """Maneja el cierre limpio de la aplicación"""
        print("Cerrando aplicación...")
        self.running = False
        
        try:
            if hasattr(self, 'player') and self.player:
                self.player.stop()
        except Exception as e:
            print(f"Error cerrando player: {e}")
            
        try:
            if hasattr(self, 'listener') and self.listener:
                self.listener.stop()
        except Exception as e:
            print(f"Error cerrando listener: {e}")
            
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"Error cerrando ventana: {e}")

def signal_handler(sig, frame):
    """Maneja señales del sistema para cierre limpio"""
    print("Cerrando aplicación por señal del sistema...")
    sys.exit(0)

if __name__ == "__main__":
    # Configurar manejo de señales
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except:
        pass  # En Windows algunas señales pueden no estar disponibles
    
    # Opcional: Configurar perfil de hardware
    try:
        from config import HardwareProfiles
        HardwareProfiles.apply_profile('HIGH_END')  # Cambiar según tu hardware
    except ImportError:
        print("config.py no encontrado, usando configuraciones por defecto")
    
    print("=== INICIANDO DILO MANO ===")
    
    root = tk.Tk()
    MIC_ID = 1  
    
    try:
        app = App(root, mic_id=MIC_ID)
        print("¡Aplicación lista para usar!")
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación interrumpida por el usuario")
    except Exception as e:
        print(f"Error fatal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Cerrando aplicación...")
        try:
            if 'root' in locals():
                root.quit()
        except:
            pass