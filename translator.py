# translator.py
from diccionario import diccionario_señas

def traducir_a_video(palabra):
    palabra = palabra.lower().strip()
    return diccionario_señas.get(palabra, None)