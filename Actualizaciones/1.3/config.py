# config.py - Configuraciones centralizadas para optimización

class PerformanceConfig:
    """Configuraciones centralizadas para optimización de rendimiento"""
    
    # === CONFIGURACIÓN DE VIDEO ===
    VIDEO_FPS = 45  # FPS objetivo para reproducción
    VIDEO_SKIP_FRAMES = 1  # Frames a saltar (0 = no saltar, 1 = saltar 1 de cada 2)
    VIDEO_CACHE_SIZE = 100  # Máximo frames en cache
    VIDEO_SPEED_MULTIPLIER = 0.6  # 0.6 = 40% más rápido, 1.0 = velocidad normal
    VIDEO_MIN_FRAME_DELAY = 10  # Delay mínimo entre frames (ms)
    
    # === CONFIGURACIÓN DE AUDIO ===
    AUDIO_SAMPLERATE = 16000  # Tasa de muestreo
    AUDIO_BLOCKSIZE = 4096  # Tamaño de bloque de audio
    AUDIO_QUEUE_SIZE = 50  # Tamaño máximo de cola de audio
    AUDIO_PARTIAL_RATE_LIMIT = 0.1  # Límite de frecuencia para parciales (segundos)
    AUDIO_MIN_WORD_LENGTH = 2  # Longitud mínima de palabra a procesar
    
    # === CONFIGURACIÓN DE CACHE ===
    TRANSLATION_CACHE_SIZE = 200  # Traducciones en cache
    WORD_CACHE_SIZE = 1000  # Palabras normalizadas en cache
    ROOT_CACHE_SIZE = 500  # Raíces de palabras en cache
    RECENT_WORDS_CACHE = 10  # Palabras recientes para evitar repetición
    
    # === CONFIGURACIÓN DE HILOS ===
    THREAD_TIMEOUT = 1.0  # Timeout para operaciones de hilo (segundos)
    MAX_QUEUE_WAIT = 1.0  # Tiempo máximo de espera en colas
    
    # === CONFIGURACIÓN DE UI ===
    UI_UPDATE_THROTTLE = 0.016  # ~60 FPS para actualizaciones de UI
    MIN_WINDOW_SIZE = (400, 300)  # Tamaño mínimo de ventana
    DEFAULT_WINDOW_SIZE = (800, 600)  # Tamaño por defecto
    
    # === CONFIGURACIÓN DE DEBUGGING ===
    ENABLE_PERFORMANCE_LOGS = True  # Habilitar logs de rendimiento
    LOG_CACHE_STATS_INTERVAL = 30  # Intervalo para mostrar stats de cache (segundos)
    
    @classmethod
    def get_video_config(cls):
        """Retorna configuración de video"""
        return {
            'fps': cls.VIDEO_FPS,
            'skip_frames': cls.VIDEO_SKIP_FRAMES,
            'cache_size': cls.VIDEO_CACHE_SIZE,
            'speed_multiplier': cls.VIDEO_SPEED_MULTIPLIER,
            'min_frame_delay': cls.VIDEO_MIN_FRAME_DELAY
        }
    
    @classmethod
    def get_audio_config(cls):
        """Retorna configuración de audio"""
        return {
            'samplerate': cls.AUDIO_SAMPLERATE,
            'blocksize': cls.AUDIO_BLOCKSIZE,
            'queue_size': cls.AUDIO_QUEUE_SIZE,
            'rate_limit': cls.AUDIO_PARTIAL_RATE_LIMIT,
            'min_word_length': cls.AUDIO_MIN_WORD_LENGTH
        }
    
    @classmethod
    def get_cache_config(cls):
        """Retorna configuración de cache"""
        return {
            'translation_cache': cls.TRANSLATION_CACHE_SIZE,
            'word_cache': cls.WORD_CACHE_SIZE,
            'root_cache': cls.ROOT_CACHE_SIZE,
            'recent_words': cls.RECENT_WORDS_CACHE
        }

# === CONFIGURACIONES ESPECÍFICAS POR HARDWARE ===

class HardwareProfiles:
    """Perfiles de configuración según el hardware disponible"""
    
    LOW_END = {
        'video_fps': 30,
        'video_skip_frames': 2,
        'cache_sizes': 0.5,  # Multiplicador para tamaños de cache
        'audio_blocksize': 2048
    }
    
    MID_RANGE = {
        'video_fps': 45,
        'video_skip_frames': 1,
        'cache_sizes': 1.0,
        'audio_blocksize': 4096
    }
    
    HIGH_END = {
        'video_fps': 60,
        'video_skip_frames': 0,
        'cache_sizes': 2.0,
        'audio_blocksize': 8192
    }
    
    @classmethod
    def apply_profile(cls, profile_name):
        """Aplica un perfil de hardware específico"""
        if profile_name not in ['LOW_END', 'MID_RANGE', 'HIGH_END']:
            return
            
        profile = getattr(cls, profile_name)
        
        # Aplicar configuraciones del perfil
        PerformanceConfig.VIDEO_FPS = profile['video_fps']
        PerformanceConfig.VIDEO_SKIP_FRAMES = profile['video_skip_frames']
        PerformanceConfig.AUDIO_BLOCKSIZE = profile['audio_blocksize']
        
        # Aplicar multiplicador de cache
        multiplier = profile['cache_sizes']
        PerformanceConfig.VIDEO_CACHE_SIZE = int(PerformanceConfig.VIDEO_CACHE_SIZE * multiplier)
        PerformanceConfig.TRANSLATION_CACHE_SIZE = int(PerformanceConfig.TRANSLATION_CACHE_SIZE * multiplier)
        PerformanceConfig.WORD_CACHE_SIZE = int(PerformanceConfig.WORD_CACHE_SIZE * multiplier)
        
        print(f"Perfil de hardware aplicado: {profile_name}")

# === UTILIDADES DE MONITOREO ===

import time
import threading
import psutil

class PerformanceMonitor:
    """Monitor de rendimiento en tiempo real"""
    
    def __init__(self):
        self.stats = {
            'frames_rendered': 0,
            'words_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'start_time': time.time()
        }
        self.lock = threading.Lock()
        self.monitoring = False
    
    def start_monitoring(self, interval=30):
        """Inicia monitoreo automático"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        thread.start()
    
    def _monitor_loop(self, interval):
        """Loop de monitoreo"""
        while self.monitoring:
            time.sleep(interval)
            self.print_stats()
    
    def increment_frames(self):
        """Incrementa contador de frames"""
        with self.lock:
            self.stats['frames_rendered'] += 1
    
    def increment_words(self):
        """Incrementa contador de palabras"""
        with self.lock:
            self.stats['words_processed'] += 1
    
    def record_cache_hit(self):
        """Registra cache hit"""
        with self.lock:
            self.stats['cache_hits'] += 1
    
    def record_cache_miss(self):
        """Registra cache miss"""
        with self.lock:
            self.stats['cache_misses'] += 1
    
    def print_stats(self):
        """Imprime estadísticas actuales"""
        with self.lock:
            elapsed = time.time() - self.stats['start_time']
            fps = self.stats['frames_rendered'] / elapsed if elapsed > 0 else 0
            wps = self.stats['words_processed'] / elapsed if elapsed > 0 else 0
            
            total_cache = self.stats['cache_hits'] + self.stats['cache_misses']
            hit_rate = (self.stats['cache_hits'] / total_cache * 100) if total_cache > 0 else 0
            
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            print(f"\n=== ESTADÍSTICAS DE RENDIMIENTO ===")
            print(f"FPS promedio: {fps:.2f}")
            print(f"Palabras/seg: {wps:.2f}")
            print(f"Cache hit rate: {hit_rate:.1f}%")
            print(f"CPU: {cpu_percent:.1f}%")
            print(f"RAM: {memory_percent:.1f}%")
            print("=" * 35)
    
    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.monitoring = False

# Instancia global del monitor
performance_monitor = PerformanceMonitor()