from diccionario import diccionario_senas
import unicodedata
import stanza

# Inicializa Stanza (fuera de la clase para no recargar siempre)
nlp = stanza.Pipeline("es", processors="tokenize,pos,lemma", use_gpu=False)

def normalizar(texto):
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                    if unicodedata.category(c) != 'Mn')
    return texto

def obtener_raiz(palabra):
    palabra = normalizar(palabra)
    doc = nlp(palabra)
    for sent in doc.sentences:
        for w in sent.words:
            return normalizar(w.lemma)
    return palabra

class Translator:
    def __init__(self):
        pass

    def traducir(self, frase):
        videos = []
        for palabra in frase.split():
            palabra_raiz = obtener_raiz(palabra)
            print(f"Traduciendo '{palabra}' -> raíz '{palabra_raiz}'")
            if palabra_raiz in diccionario_senas:
                ruta = diccionario_senas[palabra_raiz]
                print(f"✅ Encontrado en diccionario: {ruta}")
                if ruta:
                    videos.append(ruta)
            else:
                print(f"❌ No encontrado: {palabra_raiz}")
        return videos