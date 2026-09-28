import tkinter as tk
from tkinter import messagebox, ttk
import threading
from video_player import VideoPlayer
from translator import Translator, obtener_raiz
from streaming_listener import StreamingListener
from config_manager import ConfigManager

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Dilo Mano - Traductor de Voz a Señas")
        self.root.geometry("1000x700")
        self.root.minsize(600, 400)
        
        # Configuración
        self.config = ConfigManager()
        
        # Variables de estado
        self.muted = False
        self.ultima_palabra = ""
        self.listener = None
        self.listener_thread = None
        
        # Inicializar componentes
        try:
            self.setup_ui()
            self.setup_components()
            self.actualizar_estadisticas_periodicamente()
        except Exception as e:
            self.mostrar_error(f"Error inicializando la aplicación: {e}")

    def mostrar_error(self, mensaje):
        """Muestra errores al usuario"""
        messagebox.showerror("Error", mensaje)
        print(f"❌ Error: {mensaje}")

    def mostrar_info(self, mensaje):
        """Muestra información al usuario"""
        messagebox.showinfo("Información", mensaje)
        print(f"ℹ️ Info: {mensaje}")

    def setup_ui(self):
        """Configura la interfaz de usuario"""
        # Crear menú
        self.crear_menu()
        
        # Frame para el video (ocupa la parte superior y es responsive)
        frame_video = tk.Frame(self.root, bg="black", relief="sunken", bd=2)
        frame_video.pack(fill="both", expand=True, padx=5, pady=5)

        # Frame para controles principales
        frame_controles = tk.Frame(self.root, relief="raised", bd=1)
        frame_controles.pack(fill="x", padx=5, pady=2)

        # Frame para indicadores de estado
        frame_status = tk.Frame(self.root, relief="sunken", bd=1)
        frame_status.pack(fill="x", padx=5, pady=2)

        # Reproductor de video
        self.player = VideoPlayer(frame_video)

        # === CONTROLES PRINCIPALES ===
        # Texto de detección
        self.label = tk.Label(frame_controles, text="Inicializando...", 
                             font=("Arial", 12), wraplength=400)
        self.label.pack(side="left", padx=10, pady=5)

        # Selector de micrófono
        frame_mic = tk.Frame(frame_controles)
        frame_mic.pack(side="right", padx=10, pady=5)
        
        tk.Label(frame_mic, text="🎤 Micrófono:", font=("Arial", 10)).pack(side="left")
        self.mic_var = tk.StringVar()
        self.mic_menu = ttk.Combobox(frame_mic, textvariable=self.mic_var, 
                                    width=25, state="readonly")
        self.mic_menu.pack(side="left", padx=5)
        self.mic_menu.bind('<<ComboboxSelected>>', self.cambiar_microfono)

        # Botón para refrescar micrófonos
        tk.Button(frame_mic, text="🔄", command=self.actualizar_lista_microfonos,
                 font=("Arial", 8)).pack(side="left", padx=2)

        # Botón mute
        self.btn_mute = tk.Button(frame_controles, text="🔇 Mutear", 
                                 command=self.toggle_mute, font=("Arial", 10))
        self.btn_mute.pack(side="right", padx=10, pady=5)

        # Selector de modo
        frame_modo = tk.Frame(frame_controles)
        frame_modo.pack(side="right", padx=10, pady=5)
        
        tk.Label(frame_modo, text="Modo:", font=("Arial", 10)).pack(side="left")
        self.modo = tk.StringVar(value=self.config.get_config("modo_default", "parciales"))
        modo_menu = ttk.Combobox(frame_modo, textvariable=self.modo, 
                               values=["parciales", "finales"], width=10, state="readonly")
        modo_menu.pack(side="left", padx=5)

        # === INDICADORES DE ESTADO ===
        # Indicadores visuales
        self.status_mic = tk.Label(frame_status, text="🎤", fg="red", font=("Arial", 16))
        self.status_mic.pack(side="left", padx=5)

        self.status_processing = tk.Label(frame_status, text="⚪", font=("Arial", 16))
        self.status_processing.pack(side="left", padx=5)

        tk.Label(frame_status, text="|", fg="gray").pack(side="left", padx=5)

        # Estadísticas en tiempo real
        self.stats_label = tk.Label(frame_status, text="Palabras: 0 | Cola: 0 | Éxito: 0%", 
                                   font=("Arial", 9))
        self.stats_label.pack(side="left", padx=10)

        # Controles de cola
        frame_cola_controles = tk.Frame(frame_status)
        frame_cola_controles.pack(side="right", padx=5)

        self.btn_limpiar = tk.Button(frame_cola_controles, text="🗑️ Limpiar Cola", 
                                   command=self.limpiar_cola_manual, font=("Arial", 8))
        self.btn_limpiar.pack(side="left", padx=2)

        self.btn_pausa = tk.Button(frame_cola_controles, text="⏸️ Pausar", 
                                  command=self.toggle_pausa_video, font=("Arial", 8))
        self.btn_pausa.pack(side="left", padx=2)

        # Control de velocidad
        frame_velocidad = tk.Frame(frame_status)
        frame_velocidad.pack(side="right", padx=5)
        
        tk.Label(frame_velocidad, text="⚡:", font=("Arial", 8)).pack(side="left")
        self.velocidad_var = tk.DoubleVar(value=self.config.get_config("velocidad_video", 1.0))
        velocidad_scale = tk.Scale(frame_velocidad, from_=0.5, to=2.0, resolution=0.1,
                                  orient="horizontal", variable=self.velocidad_var,
                                  command=self.cambiar_velocidad, length=80)
        velocidad_scale.pack(side="left")

        # Actualizar lista de micrófonos
        self.actualizar_lista_microfonos()

    def crear_menu(self):
        """Crea la barra de menú"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # Menú Archivo
        archivo_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=archivo_menu)
        archivo_menu.add_command(label="Reiniciar Estadísticas", command=self.reiniciar_estadisticas)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=self.root.quit)

        # Menú Configuración
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configuración", menu=config_menu)
        config_menu.add_command(label="Probar Micrófono", command=self.probar_microfono)
        config_menu.add_command(label="Listar Micrófonos", command=self.mostrar_lista_microfonos)
        config_menu.add_separator()
        config_menu.add_command(label="Limpiar Cache", command=self.limpiar_cache)

        # Menú Ayuda
        ayuda_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=ayuda_menu)
        ayuda_menu.add_command(label="Estadísticas Detalladas", command=self.mostrar_estadisticas_detalladas)
        ayuda_menu.add_command(label="Acerca de", command=self.mostrar_acerca_de)

    def setup_components(self):
        """Inicializa componentes principales"""
        try:
            # Inicializar traductor
            self.translator = Translator()
            print("✅ Traductor inicializado")

            # Inicializar listener
            if not self.config.validar_modelo_vosk():
                self.mostrar_error("Modelo Vosk no encontrado. Verifica la ruta en la configuración.")
                return

            self.listener = StreamingListener(
                self.procesar_frase, 
                modelo_path=self.config.get_config("modelo_path"),
                samplerate=self.config.get_config("samplerate")
            )
            print("✅ Listener inicializado")

            # Iniciar listener
            self.iniciar_listener()
            
            self.label.config(text="Sistema listo - Habla para mostrar señas...")

        except Exception as e:
            self.mostrar_error(f"Error configurando componentes: {e}")

    def iniciar_listener(self):
        """Inicia el listener de audio"""
        mic_id = self.obtener_mic_id_seleccionado()
        
        if self.listener_thread and self.listener_thread.is_alive():
            print("⚠️ Deteniendo listener anterior...")
            self.listener.detener()
            self.listener_thread.join(timeout=2)

        self.listener_thread = threading.Thread(
            target=self.listener.iniciar,
            args=(mic_id,),
            daemon=True
        )
        self.listener_thread.start()
        
        # Actualizar estado visual
        self.status_mic.config(text="🎤", fg="green")
        print(f"🎤 Listener iniciado con micrófono ID: {mic_id}")

    def obtener_mic_id_seleccionado(self):
        """Obtiene el ID del micrófono seleccionado"""
        try:
            seleccion = self.mic_var.get()
            if seleccion and "ID:" in seleccion:
                mic_id = int(seleccion.split("ID: ")[1].split(")")[0])
                return mic_id
        except:
            pass
        return self.config.get_config("mic_id")

    def actualizar_lista_microfonos(self):
        """Actualiza la lista de micrófonos disponibles"""
        try:
            mics = self.config.get_microfonos_disponibles()
            
            # Limpiar lista actual
            self.mic_menu['values'] = []
            
            if not mics:
                self.mic_menu['values'] = ["No hay micrófonos disponibles"]
                self.mic_var.set("No hay micrófonos disponibles")
                return

            # Crear lista de opciones
            opciones = []
            for mic in mics:
                nombre_corto = mic['name'][:40] + "..." if len(mic['name']) > 40 else mic['name']
                opciones.append(f"{nombre_corto} (ID: {mic['id']})")

            self.mic_menu['values'] = opciones

            # Seleccionar micrófono por defecto
            mic_default = self.config.get_config('mic_id')
            if mic_default is not None:
                for opcion in opciones:
                    if f"ID: {mic_default}" in opcion:
                        self.mic_var.set(opcion)
                        break
            else:
                self.mic_var.set(opciones[0])

            print(f"🎤 {len(mics)} micrófonos encontrados")

        except Exception as e:
            print(f"Error actualizando lista de micrófonos: {e}")
            self.mic_menu['values'] = ["Error obteniendo micrófonos"]
            self.mic_var.set("Error obteniendo micrófonos")

    def cambiar_microfono(self, event=None):
        """Cambia el micrófono seleccionado"""
        try:
            mic_id = self.obtener_mic_id_seleccionado()
            if mic_id is not None:
                self.config.set_config('mic_id', mic_id)
                self.iniciar_listener()
                print(f"🔄 Micrófono cambiado a ID: {mic_id}")
        except Exception as e:
            print(f"Error cambiando micrófono: {e}")

    def toggle_mute(self):
        """Activa/desactiva el micrófono"""
        self.muted = not self.muted
        if self.muted:
            self.btn_mute.config(text="🎤 Activar")
            self.label.config(text="🔇 Micrófono silenciado")
            self.status_mic.config(text="🔇", fg="red")
        else:
            self.btn_mute.config(text="🔇 Mutear")
            self.label.config(text="🎤 Micrófono activo - Habla...")
            self.status_mic.config(text="🎤", fg="green")

    def cambiar_velocidad(self, valor):
        """Cambia la velocidad de reproducción"""
        velocidad = float(valor)
        self.player.set_velocidad(velocidad)
        self.config.set_config('velocidad_video', velocidad)

    def toggle_pausa_video(self):
        """Pausa/reanuda reproducción de videos"""
        pausado = self.player.pausar_reproduccion()
        if pausado:
            self.btn_pausa.config(text="▶️ Reanudar")
        else:
            self.btn_pausa.config(text="⏸️ Pausar")

    def limpiar_cola_manual(self):
        """Permite limpiar cola manualmente"""
        videos_descartados = self.player.limpiar_cola()
        self.mostrar_info(f"Cola limpiada: {videos_descartados} videos descartados")
        self.actualizar_estadisticas()

    def procesar_frase(self, frase, final=False):
        """Procesa frases con mejor threading y timeouts"""
        if self.muted or not frase.strip():
            return

        # Usar after() de Tkinter para threading seguro
        self.root.after(0, self._procesar_frase_ui, frase, final)

    def _procesar_frase_ui(self, frase, final):
        """Procesamiento UI en hilo principal"""
        # Indicar procesamiento
        self.status_processing.config(text="🟡", fg="orange")
        
        try:
            modo_actual = self.modo.get()

            if modo_actual == "parciales" and not final:
                videos = self.translator.traducir(frase)
                if videos:
                    ultima_ruta = videos[-1]
                    palabra_raiz = obtener_raiz(frase.split()[-1])
                    if palabra_raiz != self.ultima_palabra:
                        self.player.reproducir_videos(ultima_ruta)
                        self.ultima_palabra = palabra_raiz
                
                self.label.config(text=f"🔍 Parcial: {frase}")

            elif modo_actual == "finales" and final:
                self.label.config(text=f"✅ Final: {frase}")
                videos = self.translator.traducir(frase)
                if videos:
                    self.player.reproducir_videos(videos)
                self.ultima_palabra = ""

        except Exception as e:
            print(f"Error procesando '{frase}': {e}")
            self.label.config(text=f"❌ Error: {frase}")

        # Procesamiento terminado
        self.status_processing.config(text="🟢", fg="green")
        self.root.after(1000, lambda: self.status_processing.config(text="⚪", fg="gray"))

    def actualizar_estadisticas(self):
        """Actualiza estadísticas en tiempo real"""
        try:
            stats_translator = self.translator.get_stats()
            stats_cola = self.player.get_estadisticas_cola()

            # Formatear estadísticas
            palabras = stats_translator.get('traducciones_exitosas', 0)
            cola_size = stats_cola.get('videos_en_cola', 0)
            tasa_exito = stats_translator.get('tasa_exito', 0)

            texto_stats = f"Palabras: {palabras} | Cola: {cola_size} | Éxito: {tasa_exito:.1f}%"
            
            # Agregar info adicional si hay actividad
            if stats_cola.get('videos_procesados', 0) > 0:
                tiempo_promedio = stats_cola.get('tiempo_promedio_video', 0)
                texto_stats += f" | T.Video: {tiempo_promedio:.1f}s"

            self.stats_label.config(text=texto_stats)

            # Cambiar color según el tamaño de la cola
            if cola_size > 100:
                self.stats_label.config(fg="red")
            elif cola_size > 50:
                self.stats_label.config(fg="orange")
            else:
                self.stats_label.config(fg="black")

        except Exception as e:
            print(f"Error actualizando estadísticas: {e}")

    def actualizar_estadisticas_periodicamente(self):
        """Actualiza estadísticas cada segundo"""
        self.actualizar_estadisticas()
        self.root.after(1000, self.actualizar_estadisticas_periodicamente)

    def probar_microfono(self):
        """Prueba el micrófono seleccionado"""
        mic_id = self.obtener_mic_id_seleccionado()
        if self.listener and self.listener.validar_microfono(mic_id):
            self.mostrar_info(f"✅ Micrófono {mic_id} funciona correctamente")
        else:
            self.mostrar_error(f"❌ Problema con micrófono {mic_id}")

    def mostrar_lista_microfonos(self):
        """Muestra lista detallada de micrófonos"""
        if self.listener:
            mics = self.listener.listar_microfonos()
            if mics:
                lista = "Micrófonos disponibles:\n\n"
                for mic in mics:
                    lista += f"ID {mic['id']}: {mic['name']}\n"
                    lista += f"  Canales: {mic['channels']}\n"
                    lista += f"  Sample Rate: {mic['samplerate']:.0f} Hz\n\n"
                self.mostrar_info(lista)
            else:
                self.mostrar_error("No se encontraron micrófonos")

    def limpiar_cache(self):
        """Limpia el cache de lemmatización"""
        try:
            self.translator.limpiar_cache()
            self.mostrar_info("Cache de lemmatización limpiado")
        except Exception as e:
            self.mostrar_error(f"Error limpiando cache: {e}")

    def reiniciar_estadisticas(self):
        """Reinicia todas las estadísticas"""
        try:
            self.translator.reset_stats()
            self.player.reset_estadisticas()
            if self.listener:
                self.listener.reset_stats()
            self.mostrar_info("Estadísticas reiniciadas")
        except Exception as e:
            self.mostrar_error(f"Error reiniciando estadísticas: {e}")

    def mostrar_estadisticas_detalladas(self):
        """Muestra ventana con estadísticas detalladas"""
        ventana_stats = tk.Toplevel(self.root)
        ventana_stats.title("Estadísticas Detalladas")
        ventana_stats.geometry("600x500")

        # Crear notebook para pestañas
        notebook = ttk.Notebook(ventana_stats)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Pestaña Traductor
        frame_translator = ttk.Frame(notebook)
        notebook.add(frame_translator, text="Traductor")
        
        stats_translator = self.translator.get_stats()
        texto_translator = f"""
Estadísticas del Traductor:

Palabras procesadas: {stats_translator.get('palabras_procesadas', 0)}
Traducciones exitosas: {stats_translator.get('traducciones_exitosas', 0)}
Traducciones fallidas: {stats_translator.get('traducciones_fallidas', 0)}
Tasa de éxito: {stats_translator.get('tasa_exito', 0):.2f}%
Tiempo total: {stats_translator.get('tiempo_total', 0):.2f}s
Tiempo promedio: {stats_translator.get('tiempo_promedio_ms', 0):.2f}ms
Tasa de cache: {stats_translator.get('tasa_cache', 0):.2f}%

Cache info:
- Hits: {stats_translator.get('cache_info', {}).get('hits', 0)}
- Misses: {stats_translator.get('cache_info', {}).get('misses', 0)}
- Tamaño actual: {stats_translator.get('cache_info', {}).get('currsize', 0)}
- Tamaño máximo: {stats_translator.get('cache_info', {}).get('maxsize', 0)}
"""
        
        tk.Label(frame_translator, text=texto_translator, justify="left", 
                font=("Courier", 10)).pack(padx=10, pady=10)

        # Pestaña Videos
        frame_videos = ttk.Frame(notebook)
        notebook.add(frame_videos, text="Videos")
        
        stats_videos = self.player.get_estadisticas_cola()
        texto_videos = f"""
Estadísticas de Videos:

Videos procesados: {stats_videos.get('videos_procesados', 0)}
Videos en cola: {stats_videos.get('videos_en_cola', 0)}
Videos fallidos: {stats_videos.get('videos_fallidos', 0)}
Tasa de éxito: {stats_videos.get('tasa_exito', 0):.2f}%
Tiempo total reproducción: {stats_videos.get('tiempo_total_reproduccion', 0):.2f}s
Tiempo promedio por video: {stats_videos.get('tiempo_promedio_video', 0):.2f}s
Videos por minuto: {stats_videos.get('videos_por_minuto', 0):.2f}
Tiempo de sesión: {stats_videos.get('tiempo_sesion', 0)/60:.1f} minutos

Último video: {stats_videos.get('ultimo_video', 'N/A')}
Velocidad actual: {self.player.velocidad_reproduccion:.1f}x
"""
        
        tk.Label(frame_videos, text=texto_videos, justify="left", 
                font=("Courier", 10)).pack(padx=10, pady=10)

        # Pestaña Listener
        if self.listener:
            frame_listener = ttk.Frame(notebook)
            notebook.add(frame_listener, text="Audio")
            
            stats_listener = self.listener.get_stats()
            texto_listener = f"""
Estadísticas de Audio:

Palabras detectadas: {stats_listener.get('palabras_detectadas', 0)}
Frases finales: {stats_listener.get('frases_finales', 0)}
Tiempo de actividad: {stats_listener.get('tiempo_actividad', 0)/60:.1f} minutos
Estado: {'Activo' if self.listener.esta_activo() else 'Inactivo'}

Configuración:
Modelo: {self.config.get_config('modelo_path')}
Sample rate: {self.config.get_config('samplerate')} Hz
Micrófono actual: {self.obtener_mic_id_seleccionado()}
Modo: {self.modo.get()}
"""
            
            tk.Label(frame_listener, text=texto_listener, justify="left", 
                    font=("Courier", 10)).pack(padx=10, pady=10)

    def mostrar_acerca_de(self):
        """Muestra información sobre la aplicación"""
        info = """
🤟 Dilo Mano - Traductor de Voz a Señas

Versión: 2.0 (Mejorada)
Desarrollado para clases y conferencias

Características:
✅ Reconocimiento de voz en tiempo real
✅ Traducción automática a lenguaje de señas
✅ Reproducción de videos sin límites de cola
✅ Configuración dinámica de micrófono
✅ Estadísticas detalladas en tiempo real
✅ Control de velocidad de reproducción
✅ Modo parciales y finales
✅ Cache inteligente de lemmatización

Ideal para:
🎓 Clases universitarias
🏛️ Conferencias
📚 Seminarios
🎤 Presentaciones

Tecnologías:
- Python + Tkinter
- Vosk (reconocimiento de voz)
- Stanza (procesamiento de lenguaje natural)
- PIL/Pillow (procesamiento de imágenes)
- imageio (reproducción de videos)
"""
        self.mostrar_info(info)

    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        try:
            print("🔄 Cerrando aplicación...")
            
            # Detener listener
            if self.listener:
                self.listener.detener()
            
            # Esperar a que termine el hilo
            if self.listener_thread and self.listener_thread.is_alive():
                self.listener_thread.join(timeout=2)
            
            print("✅ Aplicación cerrada correctamente")
            
        except Exception as e:
            print(f"Error cerrando aplicación: {e}")
        finally:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    
    # Configurar cierre limpio
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n🛑 Interrupción por teclado")
        app.on_closing()