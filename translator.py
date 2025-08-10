# translator.py
from diccionario import diccionario_senas

def traducir_a_video(palabra):
    palabra = palabra.lower().strip()
    return diccionario_senas.get(palabra, None)