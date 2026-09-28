from functools import lru_cache
from diccionario import diccionario_senas
import unicodedata
import stanza
import time
import threading

# Inicializar Stanza una sola vez
_nlp_lock = threading.Lock()
_nlp = None

def get_nlp():
    """Obtiene instancia de Stanza de forma thread-safe"""
    global _nlp
    if _nlp is None:
        with _nlp_lock:
            if _nlp is None:
                print("Inicializando modelo Stanza...")
                _nlp = stanza.Pipeline("es", processors="tokenize,pos,lemma", use_gpu=False)
                print("Modelo Stanza cargado.")
    return _nlp

def normalizar(texto):
    """Normaliza texto removiendo acentos y convirtiendo a minúsculas"""
    if not texto:
        return ""
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    return texto

@lru_cache(maxsize=1000)
def obtener_raiz_cached(palabra):
    """Versión cacheada de obtener_raiz para mejor rendimiento"""
    if not palabra:
        return ""
    
    palabra = normalizar(palabra)
    try:
        nlp = get_nlp()
        doc = nlp(palabra)
        for sent in doc.sentences:
            for w in sent.words:
                return normalizar(w.lemma)
    except Exception as e:
        print(f"Error en lemmatización de '{palabra}': {e}")
    
    return palabra

def obtener_raiz(palabra):
    """Función pública para obtener raíz (mantiene compatibilidad)"""
    return obtener_raiz_cached(palabra)

class Translator:
    def __init__(self):
        self.stats = {
            'traducciones_exitosas': 0,
            'traducciones_fallidas': 0,
            'tiempo_total': 0.0,
            'palabras_procesadas': 0,
            'cache_hits': 0
        }
        self._lock = threading.Lock()
    
    def traducir(self, frase):
        """Traduce una frase completa a lista de rutas de video"""
        if not frase or not frase.strip():
            return []
        
        inicio = time.time()
        videos = []
        
        palabras = frase.split()
        
        with self._lock:
            self.stats['palabras_procesadas'] += len(palabras)
        
        for palabra in palabras:
            if not palabra.strip():
                continue
                
            try:
                # Verificar si está en cache
                cache_info_antes = obtener_raiz_cached.cache_info()
                
                palabra_raiz = obtener_raiz_cached(palabra)
                
                # Actualizar stats de cache
                cache_info_despues = obtener_raiz_cached.cache_info()
                if cache_info_despues.hits > cache_info_antes.hits:
                    with self._lock:
                        self.stats['cache_hits'] += 1
                
                print(f"Traduciendo '{palabra}' -> raíz '{palabra_raiz}'")
                
                if palabra_raiz in diccionario_senas:
                    ruta = diccionario_senas[palabra_raiz]
                    print(f"✅ Encontrado en diccionario: {ruta}")
                    if ruta and ruta.strip():
                        videos.append(ruta)
                        with self._lock:
                            self.stats['traducciones_exitosas'] += 1
                else:
                    print(f"❌ No encontrado: {palabra_raiz}")
                    with self._lock:
                        self.stats['traducciones_fallidas'] += 1
                        
            except Exception as e:
                print(f"Error procesando palabra '{palabra}': {e}")
                with self._lock:
                    self.stats['traducciones_fallidas'] += 1
        
        tiempo_transcurrido = time.time() - inicio
        with self._lock:
            self.stats['tiempo_total'] += tiempo_transcurrido
        
        return videos
    
    def get_stats(self):
        """Retorna estadísticas de uso de forma thread-safe"""
        with self._lock:
            stats = self.stats.copy()
        
        total_traducciones = stats['traducciones_exitosas'] + stats['traducciones_fallidas']
        if total_traducciones > 0:
            stats['tasa_exito'] = (stats['traducciones_exitosas'] / total_traducciones) * 100
        else:
            stats['tasa_exito'] = 0
        
        if stats['palabras_procesadas'] > 0:
            stats['tiempo_promedio_ms'] = (stats['tiempo_total'] / stats['palabras_procesadas']) * 1000
            stats['tasa_cache'] = (stats['cache_hits'] / stats['palabras_procesadas']) * 100
        else:
            stats['tiempo_promedio_ms'] = 0
            stats['tasa_cache'] = 0
        
        # Agregar info del cache
        cache_info = obtener_raiz_cached.cache_info()
        stats['cache_info'] = {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'maxsize': cache_info.maxsize,
            'currsize': cache_info.currsize
        }
        
        return stats
    
    def reset_stats(self):
        """Reinicia estadísticas (útil entre clases)"""
        with self._lock:
            self.stats = {
                'traducciones_exitosas': 0,
                'traducciones_fallidas': 0,
                'tiempo_total': 0.0,
                'palabras_procesadas': 0,
                'cache_hits': 0
            }
    
    def limpiar_cache(self):
        """Limpia el cache de lemmatización"""
        obtener_raiz_cached.cache_clear()
        print("Cache de lemmatización limpiado")