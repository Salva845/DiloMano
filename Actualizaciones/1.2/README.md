# 🤟 Dilo Mano - Guía de Instalación y Uso

## 📋 Requisitos Previos

- **Python 3.8 o superior**
- **Micrófono funcional**
- **Altavoces o auriculares** (opcional, para escuchar feedback)
- **Al menos 2GB de espacio libre** (para modelos)
- **Conexión a internet** (para descarga inicial)

## 🚀 Instalación Rápida

### 1. Clonar o Descargar el Proyecto
```bash
git clone tu-repositorio/dilo-mano
cd dilo-mano
```

### 2. Crear Entorno Virtual (Recomendado)
```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Linux/Mac:
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Descargar Modelo de Reconocimiento de Voz
```bash
# Descargar modelo Vosk en español (aprox. 50MB)
wget https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip
unzip vosk-model-es-0.42.zip

# O manualmente desde: https://alphacephei.com/vosk/models/
```

### 5. Inicializar Modelo de Procesamiento de Lenguaje
```bash
# Primera vez - descarga automática del modelo Stanza
python -c "import stanza; stanza.download('es')"
```

### 6. Crear tu Diccionario de Señas
Crea el archivo `diccionario.py`:
```python
# diccionario.py - Mapeo de palabras a videos de señas
diccionario_senas = {
    "hola": "videos/hola.mp4",
    "adios": "videos/adios.mp4",
    "gracias": "videos/gracias.mp4",
    "por": "videos/por.mp4",
    "favor": "videos/favor.mp4",
    "si": "videos/si.mp4",
    "no": "videos/no.mp4",
    "agua": "videos/agua.mp4",
    "comer": "videos/comer.mp4",
    "dormir": "videos/dormir.mp4",
    # Agregar más palabras según tus videos disponibles
}
```

### 7. Organizar Videos de Señas
```
dilo-mano/
├── videos/
│   ├── hola.mp4
│   ├── adios.mp4
│   ├── gracias.mp4
│   └── ... (más videos)
├── vosk-model-es-0.42/
├── main.py
├── diccionario.py
└── ...
```

## 🎬 Ejecutar la Aplicación

```bash
python main.py
```

## 🎛️ Configuración Inicial

### Primera Ejecución:

1. **Seleccionar Micrófono:**
   - La app detectará automáticamente micrófonos disponibles
   - Selecciona el micrófono correcto del menú desplegable
   - Presiona "🔄" para refrescar la lista si es necesario

2. **Probar Micrófono:**
   - Ve a `Configuración > Probar Micrófono`
   - Debe aparecer "✅ Micrófono funciona correctamente"

3. **Configurar Modo:**
   - **Parciales**: Traduce palabra por palabra en tiempo real
   - **Finales**: Traduce frases completas cuando terminas de hablar

4. **Ajustar Velocidad:**
   - Usa el control deslizante para ajustar velocidad de videos
   - 1.0x = velocidad normal, 0.5x = lento, 2.0x = rápido

## 🎓 Uso en Clases y Conferencias

### Funciones Especializadas:

- **Cola Ilimitada**: No se pierden traducciones durante clases largas
- **Limpieza Manual**: Botón "🗑️ Limpiar Cola" entre clases
- **Estadísticas en Tiempo Real**: Monitoreo de palabras traducidas
- **Control de Pausa**: "⏸️ Pausar" para detener reproducción temporalmente

### Flujo de Trabajo Típico:

1. **Antes de la Clase:**
   - Verificar micrófono y audio
   - Seleccionar modo "parciales" o "finales"
   - Ajustar velocidad según necesidad

2. **Durante la Clase:**
   - Monitorear estadísticas en la barra inferior
   - Usar "Mutear" si necesitas pausar reconocimiento
   - Observar indicadores de estado (🎤🟡🟢)

3. **Entre Clases:**
   - "🗑️ Limpiar Cola" para resetear
   - "Archivo > Reiniciar Estadísticas" si necesitas

4. **Después de la Clase:**
   - "Ayuda > Estadísticas Detalladas" para revisar rendimiento

## 🔧 Solución de Problemas

### Problema: No se detecta el micrófono
```bash
# Listar dispositivos de audio
python -c "import sounddevice as sd; print(sd.query_devices())"

# En la app: Configuración > Listar Micrófonos
```

### Problema: Error "Modelo Vosk no encontrado"
```bash
# Verificar que existe la carpeta:
ls vosk-model-es-0.42/

# Si no existe, descargar nuevamente:
wget https://alphacephei.com/vosk/models/vosk-model-es-0.42.zip
unzip vosk-model-es-0.42.zip
```

### Problema: Traducciones lentas
```bash
# Limpiar cache de lemmatización:
# En la app: Configuración > Limpiar Cache
```

### Problema: Videos no se reproducen
- Verificar que los archivos de video existen en las rutas del diccionario
- Formatos soportados: MP4, AVI, MOV, MKV
- Verificar permisos de lectura de archivos

### Problema: Audio de mala calidad
- Ajustar nivel de micrófono en sistema operativo
- Probar con diferentes micrófonos
- Verificar que no hay ruido de fondo excesivo

## 📊 Monitoreo y Estadísticas

### Indicadores Visuales:
- 🎤 **Verde**: Micrófono activo
- 🔇 **Rojo**: Micrófono silenciado  
- 🟡 **Amarillo**: Procesando
- 🟢 **Verde**: Procesamiento completado
- ⚪ **Blanco**: En espera

### Estadísticas Importantes:
- **Palabras**: Cantidad de palabras traducidas exitosamente
- **Cola**: Número de videos pendientes de reproducir
- **Éxito**: Porcentaje de traducciones exitosas
- **T.Video**: Tiempo promedio de reproducción por video

### Colores de Alerta en Cola:
- **Negro**: Cola normal (< 50 videos)
- **Naranja**: Cola grande (50-100 videos) - informativo
- **Rojo**: Cola muy grande (> 100 videos) - posible problema

## 🎯 Consejos para Mejor Rendimiento

### Para el Instructor:
1. **Hablar claramente** y a velocidad moderada
2. **Pausar entre conceptos** importantes
3. **Usar micrófono de calidad** (lavalier o diadema preferible)
4. **Monitorearse** con los indicadores visuales
5. **Limpiar cola** entre temas diferentes

### Para el Sistema:
1. **Cerrar aplicaciones innecesarias** para mejor rendimiento
2. **Usar micrófono USB** en lugar de micrófono integrado
3. **Mantener diccionario actualizado** con vocabulario específico
4. **Verificar espacio en disco** para logs y cache

## 🔄 Configuración Avanzada

### Archivo `config.json` (generado automáticamente):
```json
{
  "mic_id": 1,
  "modelo_path": "vosk-model-es-0.42",
  "samplerate": 16000,
  "modo_default": "parciales",
  "velocidad_video": 1.0
}
```

### Personalizar Diccionario:
```python
# En diccionario.py - Agregar vocabulario específico por materia

# Matemáticas
diccionario_senas.update({
    "suma": "videos/matematicas/suma.mp4",
    "resta": "videos/matematicas/resta.mp4",
    "multiplicar": "videos/matematicas/multiplicar.mp4",
})

# Historia
diccionario_senas.update({
    "guerra": "videos/historia/guerra.mp4",
    "revolucion": "videos/historia/revolucion.mp4",
    "independencia": "videos/historia/independencia.mp4",
})
```

## 📞 Soporte

### Logs y Debugging:
- Los errores se muestran en la consola
- Usa `Ayuda > Estadísticas Detalladas` para información completa
- El archivo `config.json` guarda configuraciones

### Información del Sistema:
```bash
# Verificar versiones
python --version
pip list | grep -E "(vosk|stanza|pillow|sounddevice)"

# Probar componentes individualmente
python -c "import vosk; print('Vosk OK')"
python -c "import stanza; print('Stanza OK')"
python -c "import sounddevice; print('SoundDevice OK')"
```

## 🚀 ¡Listo para Usar!

Tu sistema "Dilo Mano" está configurado y listo para traducir voz a lenguaje de señas en tiempo real durante tus clases y conferencias.

**¡Que tengas excelentes clases! 🎓✋**