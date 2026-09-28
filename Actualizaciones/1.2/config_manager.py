import sounddevice as sd
import json
import os

class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = self.cargar_config()
    
    def cargar_config(self):
        """Carga configuración o crea una por defecto"""
        config_default = {
            "mic_id": None,
            "modelo_path": "vosk-model-es-0.42",
            "samplerate": 16000,
            "modo_default": "parciales",
            "velocidad_video": 1.0
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Mergear con defaults
                    config_default.update(config)
            except Exception as e:
                print(f"Error cargando config: {e}")
        
        return config_default
    
    def guardar_config(self):
        """Guarda configuración actual"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando config: {e}")
    
    def get_microfonos_disponibles(self):
        """Retorna lista de micrófonos disponibles"""
        try:
            devices = sd.query_devices()
            mics = []
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    mics.append({
                        'id': i,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'samplerate': device['default_samplerate']
                    })
            return mics
        except Exception as e:
            print(f"Error obteniendo micrófonos: {e}")
            return []
    
    def validar_modelo_vosk(self):
        """Valida que el modelo Vosk existe"""
        return os.path.exists(self.config['modelo_path'])
    
    def get_config(self, key, default=None):
        """Obtiene valor de configuración"""
        return self.config.get(key, default)
    
    def set_config(self, key, value):
        """Establece valor de configuración"""
        self.config[key] = value
        self.guardar_config()