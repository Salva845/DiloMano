#!/usr/bin/env python3
"""
Script para descargar modelos de Stanza para español
Ejecutar UNA VEZ con conexión a internet
VERSIÓN CORREGIDA - Compatible con translator_fixed.py
"""

import stanza
import os
import sys
from pathlib import Path

def get_stanza_dir():
    """Obtiene la ruta estándar de Stanza - DEBE coincidir con translator.py"""
    stanza_home = os.environ.get('STANZA_RESOURCES_DIR', 
                                Path.home() / 'stanza_resources')
    return Path(stanza_home) / 'es'

def verificar_conexion():
    """Verifica que haya conexión a internet"""
    import urllib.request
    
    try:
        urllib.request.urlopen('https://www.google.com', timeout=5)
        print("Conexión a internet disponible")
        return True
    except:
        print("Sin conexión a internet")
        print("Este script requiere conexión a internet para descargar los modelos")
        return False

def limpiar_modelos_existentes():
    """Limpia modelos existentes si los hay"""
    stanza_dir = get_stanza_dir()
    
    if stanza_dir.exists():
        print(f"Encontrados modelos existentes en: {stanza_dir}")
        respuesta = input("¿Quieres eliminar modelos existentes y descargar nuevos? (s/N): ")
        
        if respuesta.lower() in ['s', 'si', 'sí', 'y', 'yes']:
            import shutil
            try:
                # Eliminar solo el directorio de español, no toda la estructura
                shutil.rmtree(stanza_dir)
                print("Modelos existentes eliminados")
                return True
            except Exception as e:
                print(f"Error eliminando modelos: {e}")
                return False
        else:
            print("Manteniendo modelos existentes")
            return True
    
    return True

def descargar_modelos_espanol():
    """Descarga los modelos de español para Stanza"""
    print("DESCARGANDO MODELOS DE ESPAÑOL PARA STANZA")
    print("=" * 60)
    
    try:
        # Verificar versión de stanza
        print(f"Versión de Stanza: {stanza.__version__}")
        
        # IMPORTANTE: Usar configuración estándar de Stanza
        # NO especificar rutas personalizadas aquí
        print("Iniciando descarga de modelos (esto puede tardar varios minutos)...")
        print("Descargando: tokenize, mwt, pos, lemma para español")
        
        stanza.download(
            lang='es',
            processors='tokenize,mwt,pos,lemma',
            verbose=True,  # Mostrar progreso detallado
            logging_level='INFO'
            # NO usar dir= aquí, dejar que Stanza use su ubicación estándar
        )
        
        print("\nDESCARGA COMPLETADA!")
        
        # Verificar la descarga
        print("\nVERIFICANDO DESCARGA...")
        stanza_dir = get_stanza_dir()
        print(f"Directorio de modelos: {stanza_dir}")
        
        if stanza_dir.exists():
            print("Directorio de modelos creado")
            
            # Listar contenido
            print("\nCONTENIDO DESCARGADO:")
            for root, dirs, files in os.walk(stanza_dir):
                level = len(Path(root).parts) - len(stanza_dir.parts)
                indent = "  " * level
                print(f"{indent}{Path(root).name}/")
                
                sub_indent = "  " * (level + 1)
                for file in files:
                    file_path = Path(root) / file
                    file_size = file_path.stat().st_size
                    size_mb = file_size / (1024 * 1024)
                    print(f"{sub_indent}{file} ({size_mb:.1f} MB)")
        
        return True
        
    except Exception as e:
        print(f"\nERROR DESCARGANDO MODELOS: {e}")
        print("Posibles soluciones:")
        print("   - Verificar conexión a internet")
        print("   - Reintentar más tarde")
        print("   - Verificar permisos de escritura en directorio home")
        return False

def probar_pipeline_offline():
    """Prueba que el pipeline funcione correctamente offline"""
    print("\nPROBANDO PIPELINE OFFLINE...")
    print("=" * 40)
    
    try:
        # Crear pipeline con configuración CORREGIDA
        nlp = stanza.Pipeline(
            'es',
            processors='tokenize,mwt,pos,lemma',
            download_method=None,  # CRÍTICO! No intentar descargar
            verbose=False,
            logging_level='ERROR'
            # NO usar model_dir aquí
        )
        
        # Texto de prueba
        texto_prueba = "Hola mundo, ¿cómo estás hoy? Yo estoy muy bien, gracias."
        print(f"Texto de prueba: '{texto_prueba}'")
        
        # Procesar
        doc = nlp(texto_prueba)
        
        print("\nRESULTADO DEL PROCESAMIENTO:")
        for i, sent in enumerate(doc.sentences, 1):
            print(f"  Oración {i}:")
            for word in sent.words:
                print(f"    '{word.text}' -> lemma: '{word.lemma}' (POS: {word.pos})")
        
        print("\n¡PIPELINE OFFLINE FUNCIONA PERFECTAMENTE!")
        return True
        
    except Exception as e:
        print(f"\nERROR PROBANDO PIPELINE: {e}")
        print("El pipeline offline no funciona correctamente")
        
        # Diagnóstico adicional
        print("\nDIAGNÓSTICO:")
        stanza_dir = get_stanza_dir()
        print(f"Directorio modelos: {stanza_dir}")
        print(f"Directorio existe: {stanza_dir.exists()}")
        
        if stanza_dir.exists():
            print("Contenido:")
            for item in stanza_dir.iterdir():
                print(f"  {item.name}")
        
        return False

def mostrar_instrucciones_uso():
    """Muestra instrucciones para usar Stanza offline"""
    print("\nINSTRUCCIONES DE USO OFFLINE")
    print("=" * 50)
    
    codigo_ejemplo = '''
# Ejemplo de uso en tu aplicación:
import stanza

# Configuración OFFLINE (sin descargas) - CORREGIDA
nlp = stanza.Pipeline(
    'es',
    processors='tokenize,mwt,pos,lemma',
    download_method=None,      # ¡CRÍTICO! No descargar
    verbose=False,
    logging_level='ERROR'
    # NO usar model_dir con ruta específica
)

# Usar normalmente
doc = nlp("Hola mundo")
for sent in doc.sentences:
    for word in sent.words:
        print(f"{word.text} -> {word.lemma}")
'''
    
    print(codigo_ejemplo)
    
    print("CONFIGURACIÓN CLAVE:")
    print("   ✅ download_method=None  - Evita descargas automáticas")
    print("   ✅ logging_level='ERROR' - Reduce mensajes innecesarios")
    print("   ✅ verbose=False         - Modo silencioso")
    
    print("\n📁 UBICACIÓN DE MODELOS:")
    stanza_dir = Path.home() / ".stanza_resources" / "es"
    print(f"   {stanza_dir}")

def main():
    """Función principal"""
    print("🌟 CONFIGURADOR DE STANZA OFFLINE")
    print("=" * 60)
    print("Este script descarga los modelos de Stanza para usar OFFLINE")
    print("Ejecutar UNA VEZ con conexión a internet")
    print("=" * 60)
    
    # 1. Verificar conexión
    if not verificar_conexion():
        print("\n❌ ABORTANDO: Sin conexión a internet")
        sys.exit(1)
    
    # 2. Limpiar modelos existentes si es necesario
    if not limpiar_modelos_existentes():
        print("\n❌ ABORTANDO: Error preparando directorio")
        sys.exit(1)
    
    # 3. Descargar modelos
    if not descargar_modelos_espanol():
        print("\n❌ ABORTANDO: Error descargando modelos")
        sys.exit(1)
    
    # 4. Probar pipeline offline
    if not probar_pipeline_offline():
        print("\n⚠️  ADVERTENCIA: Los modelos se descargaron pero hay problemas")
        sys.exit(1)
    
    # 5. Mostrar instrucciones
    mostrar_instrucciones_uso()
    
    print("\n🎉 ¡CONFIGURACIÓN COMPLETADA EXITOSAMENTE!")
    print("🔌 Ahora puedes DESCONECTAR internet y usar Stanza offline")
    print("📱 Reinicia tu aplicación para usar el nuevo traductor offline")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
