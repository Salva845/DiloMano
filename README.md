# Dilo Mano

Traductor experimental de voz en español a una secuencia visual de glosas de
Lengua de Señas Mexicana (LSM). El modo léxico conserva el orden del español;
las transformaciones gramaticales solo se habilitan mediante reglas validadas
en `lsm_rules.json`.

## Instalación

Se recomienda Python 3.11 o 3.12 para asegurar disponibilidad de wheels de
Vosk, Torch y Stanza.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python stanzaDownload.py
```

El modelo Vosk debe estar en `vosk-model-es-0.42/` y los clips en `senas/`.

## Validación

```powershell
python tools\validate_assets.py
python -m unittest discover -s tests -v
```

`--strict` hace fallar la validación si existen rutas, claves o videos
inválidos. `--probe-video` intenta abrir cada clip y comprobar sus metadatos.

Para generar copias con resolución, FPS, codec y GOP uniformes, sin modificar
los originales:

```powershell
python tools\normalize_videos.py
```

## Ejecución

```powershell
python main.py --profile MID_RANGE
python main.py --device 1 --profile HIGH_END
```

Los perfiles cambian realmente el bloque de captura y el buffer visual. El
modo `tiempo_real` traduce prefijos estables; `frase_final` espera el cierre de
la emisión para obtener mayor contexto.

El reproductor muestra como subtítulo la palabra o frase de la seña actual y
su posición en la oración. El texto cambia al renderizar el primer frame del
clip, por lo que permanece sincronizado con el video, no con la entrada a la
cola. Puede desactivarse con `VideoConfig(show_subtitles=False)`.

## Pipeline

```text
PCM int16 -> Vosk -> estabilizador -> worker NLP/LSM -> scheduler -> renderer Tk
```

Las colas son acotadas. Si el sistema no logra seguir el ritmo, registra el
overflow y recupera una frontera coherente en vez de empalmar audio o crecer
sin límite.
