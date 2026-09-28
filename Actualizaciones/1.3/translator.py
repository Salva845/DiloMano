from diccionario import diccionario_senas
import unicodedata
import stanza
from functools import lru_cache
import threading

# Inicializar Stanza INMEDIATAMENTE al importar este módulo
print("🚀 Inicializando pipeline de Stanza...")
try:
    # Configuración optimizada de Stanza
    nlp_global = stanza.Pipeline(
        "es", 
        processors="tokenize,pos,lemma", 
        use_gpu=False,
        tokenize_batch_size=32,
        pos_batch_size=32,
        lemma_batch_size=32,
        logging_level='ERROR'
    )
    print("✅ Pipeline de Stanza listo!")
except Exception as e:
    print(f"❌ Error inicializando Stanza: {e}")
    nlp_global = None

# Cache para normalización de texto
@lru_cache(maxsize=1000)
def normalizar(texto):
    """Normaliza texto con cache para evitar recomputación"""
    if not texto:
        return ""
    texto = texto.lower().strip()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    return texto

# Cache para raíces de palabras
@lru_cache(maxsize=500)
def obtener_raiz(palabra):
    """Obtiene la raíz de una palabra con cache LRU"""
    if not palabra:
        return ""
        
    palabra_normalizada = normalizar(palabra)
    
    # Cache de palabras comunes para evitar procesamiento con Stanza
    cache_raices = {
        'ustedes': 'ustedes',
        'ellos': 'ellos',
        'hola': 'hola',
        'adios': 'adio', 
        'gracias': 'gracia',
        'por': 'por',
        'favor': 'favor',
        'si': 'si',
        'no': 'no',
        'que': 'que',
        'como': 'como',
        'donde': 'donde',
        'cuando': 'cuando',
        'quien': 'quien',
        'agua': 'agua',
        'comer': 'comer',
        'dormir': 'dormir',
        'casa': 'casa',
        'trabajo': 'trabajo',
        'familia': 'familia',
        'amigo': 'amigo',
        'tiempo': 'tiempo',
        'dia': 'dia',
        'noche': 'noche',
        'poder': 'poder',
        'ver': 'ver',
        'llamar': 'llamar',
        'encontrar': 'encontrar',
        'pero': 'pero',
        'izquierda': 'izquierdo',
        'derecha': 'derecho',
        'detenerse': 'detener',
        'estado': 'estado',
        'bolsa': 'bolsa',
        'cartera': 'cartera',
        'zapato': 'zapato',
        'ropa': 'ropa',
        'contigo': 'contigo'
    }
    
    if palabra_normalizada in cache_raices:
        return cache_raices[palabra_normalizada]
    
    if nlp_global is None:
        print(f"Warning: Stanza no disponible, devolviendo palabra original: {palabra_normalizada}")
        return palabra_normalizada
    
    try:
        doc = nlp_global(palabra_normalizada)
        
        for sent in doc.sentences:
            for word in sent.words:
                raiz = normalizar(word.lemma)
                print(f"Stanza: '{palabra_normalizada}' -> '{raiz}'")
                return raiz
                
    except Exception as e:
        print(f"Error obteniendo raíz para '{palabra}': {e}")
        
    return palabra_normalizada

class Translator:
    def __init__(self):
        # Cache para traducciones recientes
        self.cache_traducciones = {}
        self.cache_max_size = 200
        self.lock = threading.Lock()

    def _limpiar_cache(self):
        """Limpia el cache cuando excede el tamaño máximo"""
        if len(self.cache_traducciones) >= self.cache_max_size:
            # Remover la mitad más antigua
            items_to_remove = len(self.cache_traducciones) // 2
            keys_to_remove = list(self.cache_traducciones.keys())[:items_to_remove]
            for key in keys_to_remove:
                del self.cache_traducciones[key]

    def traducir(self, frase):
        """Traduce una frase con cache y optimizaciones"""
        if not frase or not frase.strip():
            return []
        
        frase_normalizada = normalizar(frase)
        
        # Verificar cache (pero solo para frases completas, no palabras individuales)
        is_single_word = len(frase_normalizada.split()) == 1
        cache_key = frase_normalizada
        
        if not is_single_word:  # Solo usar cache para frases completas
            with self.lock:
                if cache_key in self.cache_traducciones:
                    return self.cache_traducciones[cache_key]
        
        videos = []
        palabras = frase_normalizada.split()
        
        # Procesar palabras en lotes para mejor performance
        for palabra in palabras:
            if not palabra:
                continue
                
            try:
                palabra_raiz = obtener_raiz(palabra)
                print(f"Traduciendo '{palabra}' -> raíz '{palabra_raiz}'")
                
                if palabra_raiz in diccionario_senas:
                    ruta = diccionario_senas[palabra_raiz]
                    print(f"✅ Encontrado en diccionario: {ruta}")
                    if ruta and isinstance(ruta, str):
                        videos.append(ruta)
                else:
                    print(f"❌ No encontrado: {palabra_raiz}")
                    
            except Exception as e:
                print(f"Error traduciendo palabra '{palabra}': {e}")
                continue
        
        # Guardar en cache solo frases completas
        if not is_single_word:
            with self.lock:
                self._limpiar_cache()
                self.cache_traducciones[cache_key] = videos
        
        return videos

    def limpiar_cache(self):
        """Limpia manualmente el cache de traducciones"""
        with self.lock:
            self.cache_traducciones.clear()
            
    def get_cache_info(self):
        """Obtiene información del cache para debugging"""
        with self.lock:
            return {
                'traducciones_cache_size': len(self.cache_traducciones),
                'normalizar_cache_info': normalizar.cache_info(),
                'obtener_raiz_cache_info': obtener_raiz.cache_info()
            }