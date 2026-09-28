#!/usr/bin/env python3
"""
Script de prueba para el traductor con Stanza offline
Verifica que todo funcione correctamente sin conexión a internet
"""

import os
import sys
from pathlib import Path

def verificar_sin_internet():
    """Verifica que no haya conexión a internet (opcional)"""
    import urllib.request
    
    try:
        urllib.request.urlopen('https://www.google.com', timeout=3)
        print("⚠️  Tienes conexión a internet activa")
        print("💡 Para una prueba completa, considera desconectar internet")
        return True
    except:
        print("✅ Sin conexión a internet - Perfecto para prueba offline")
        return False

def verificar_modelos_stanza():
    """Verifica que los modelos de Stanza estén instalados"""
    stanza_dir = Path.home() / "stanza_resources" / "es"
    
    print("\n🔍 VERIFICANDO MODELOS DE STANZA:")
    print(f"📁 Buscando en: {stanza_dir}")
    
    if not stanza_dir.exists():
        print("❌ MODELOS NO ENCONTRADOS")
        print("💡 Ejecuta primero: python download_stanza_models.py")
        return False
    
    print("✅ Directorio de modelos encontrado")
    
    # Verificar archivos esenciales
    archivos_esenciales = [
        "tokenize", "pos", "lemma"
    ]
    
    for archivo in archivos_esenciales:
        archivo_dir = stanza_dir / archivo
        if archivo_dir.exists():
            print(f"  ✅ {archivo}/")
        else:
            print(f"  ❌ {archivo}/ - FALTANTE")
            return False
    
    print("✅ Todos los modelos necesarios están presentes")
    return True

def probar_stanza_directo():
    """Prueba Stanza directamente"""
    print("\n🧪 PROBANDO STANZA DIRECTAMENTE:")
    
    try:
        import stanza
        
        # Configuración offline
        nlp = stanza.Pipeline(
            'es',
            processors='tokenize,pos,lemma',
            download_method=None,  # ¡CRÍTICO!
            verbose=False,
            logging_level='ERROR'
        )
        
        # Prueba
        texto = "Hola mundo, ¿cómo estás?"
        doc = nlp(texto)
        
        print(f"📝 Texto: '{texto}'")
        print("✅ Resultado:")
        
        for sent in doc.sentences:
            for word in sent.words:
                print(f"  '{word.text}' -> '{word.lemma}' ({word.pos})")
        
        print("✅ Stanza offline funciona correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error con Stanza: {e}")
        return False

def probar_traductor_completo():
    """Prueba el traductor completo"""
    print("\n🧪 PROBANDO TRADUCTOR COMPLETO:")
    
    try:
        # Importar el traductor
        sys.path.append('.')  # Asegurar que puede importar desde directorio actual
        
        from translator import Translator
        
        # Crear instancia
        traductor = Translator()
        
        # Verificar status
        status = traductor.verificar_stanza_status()
        if not status['stanza_ready']:
            print("❌ Stanza no está listo en el traductor")
            return False
        
        # Pruebas básicas
        pruebas = [
            "hola",
            "hola mundo",
            "yo quiero agua",
            "¿cómo estás hoy?",
            "palabrainexistente123"
        ]
        
        print("📝 PRUEBAS DE TRADUCCIÓN:")
        for i, prueba in enumerate(pruebas, 1):
            print(f"\n  {i}. Probando: '{prueba}'")
            videos = traductor.traducir(prueba)
            print(f"     Resultado: {len(videos)} videos encontrados")
            
            if videos:
                for j, video in enumerate(videos[:3]):  # Mostrar solo primeros 3
                    nombre = os.path.basename(video)
                    existe = "✅" if os.path.isfile(video) else "❌"
                    print(f"       {j+1}. {existe} {nombre}")
                if len(videos) > 3:
                    print(f"       ... y {len(videos) - 3} más")
        
        print("\n✅ Traductor completo funciona correctamente")
        return True
        
    except ImportError as e:
        print(f"❌ Error importando traductor: {e}")
        print("💡 Asegúrate de que translator.py esté en el directorio actual")
        return False
    except Exception as e:
        print(f"❌ Error con traductor: {e}")
        return False

def probar_funciones_adicionales():
    """Prueba funciones adicionales del traductor"""
    print("\n🧪 PROBANDO FUNCIONES ADICIONALES:")
    
    try:
        from translator import Translator
        
        traductor = Translator()
        
        # 1. Probar cache info
        print("1. Info de cache:")
        cache_info = traductor.get_cache_info()
        
        # 2. Probar debug de palabra
        print("\n2. Debug de palabra:")
        debug_info = traductor.debug_palabra("hola")
        
        # 3. Probar estadísticas
        print("\n3. Estadísticas del diccionario:")
        stats = traductor.estadisticas_diccionario()
        
        # 4. Probar test de Stanza
        print("\n4. Test específico de Stanza:")
        stanza_ok = traductor.test_stanza_offline()
        
        if stanza_ok:
            print("✅ Todas las funciones adicionales funcionan")
            return True
        else:
            print("⚠️  Algunas funciones tienen problemas")
            return False
        
    except Exception as e:
        print(f"❌ Error probando funciones adicionales: {e}")
        return False

def generar_reporte_final():
    """Genera un reporte final del estado"""
    print("\n📊 REPORTE FINAL:")
    print("=" * 50)
    
    # Información del sistema
    print(f"🖥️  Python: {sys.version}")
    print(f"📁 Directorio actual: {os.getcwd()}")
    
    # Estado de Stanza
    stanza_dir = Path.home() / ".stanza_resources" / "es"
    print(f"📁 Modelos Stanza: {stanza_dir}")
    print(f"📦 Modelos existen: {'✅ SÍ' if stanza_dir.exists() else '❌ NO'}")
    
    # Archivos del proyecto
    archivos_proyecto = ['translator.py', 'diccionario.py']
    for archivo in archivos_proyecto:
        existe = os.path.exists(archivo)
        print(f"📄 {archivo}: {'✅ SÍ' if existe else '❌ NO'}")
    
    print("=" * 50)

def main():
    """Función principal de prueba"""
    print("🧪 PRUEBA COMPLETA DEL TRADUCTOR OFFLINE")
    print("=" * 60)
    
    resultados = []
    
    # 1. Verificar conexión (informativo)
    print("1️⃣  VERIFICACIÓN DE CONEXIÓN:")
    tiene_internet = verificar_sin_internet()
    resultados.append(('Conexión', not tiene_internet))  # Mejor sin internet para prueba
    
    # 2. Verificar modelos
    print("\n2️⃣  VERIFICACIÓN DE MODELOS:")
    modelos_ok = verificar_modelos_stanza()
    resultados.append(('Modelos Stanza', modelos_ok))
    
    if not modelos_ok:
        print("\n❌ ABORTANDO: Sin modelos de Stanza")
        print("💡 Ejecuta: python download_stanza_models.py")
        sys.exit(1)
    
    # 3. Probar Stanza directo
    print("\n3️⃣  PRUEBA DIRECTA DE STANZA:")
    stanza_ok = probar_stanza_directo()
    resultados.append(('Stanza directo', stanza_ok))
    
    if not stanza_ok:
        print("\n❌ ABORTANDO: Stanza no funciona")
        sys.exit(1)
    
    # 4. Probar traductor completo
    print("\n4️⃣  PRUEBA DEL TRADUCTOR:")
    traductor_ok = probar_traductor_completo()
    resultados.append(('Traductor completo', traductor_ok))
    
    # 5. Probar funciones adicionales
    print("\n5️⃣  PRUEBA DE FUNCIONES ADICIONALES:")
    funciones_ok = probar_funciones_adicionales()
    resultados.append(('Funciones adicionales', funciones_ok))
    
    # 6. Reporte final
    generar_reporte_final()
    
    # Resumen de resultados
    print("\n📋 RESUMEN DE PRUEBAS:")
    print("=" * 30)
    
    todas_ok = True
    for nombre, resultado in resultados:
        estado = "✅ PASS" if resultado else "❌ FAIL"
        print(f"  {estado} {nombre}")
        if not resultado:
            todas_ok = False
    
    print("=" * 30)
    
    if todas_ok:
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print("🔌 Tu traductor está listo para usar OFFLINE")
        print("📱 Puedes desconectar internet y usar la aplicación")
    else:
        print("\n⚠️  ALGUNAS PRUEBAS FALLARON")
        print("🔧 Revisa los errores anteriores y corrige los problemas")
        
        # Sugerencias específicas
        print("\n💡 POSIBLES SOLUCIONES:")
        for nombre, resultado in resultados:
            if not resultado:
                if nombre == "Modelos Stanza":
                    print("   - Ejecuta: python download_stanza_models.py")
                elif nombre == "Stanza directo":
                    print("   - Verifica que los modelos estén completos")
                    print("   - Reinstala Stanza: pip install --upgrade stanza")
                elif nombre == "Traductor completo":
                    print("   - Verifica que translator.py y diccionario.py existan")
                    print("   - Revisa imports y dependencias")
                elif nombre == "Funciones adicionales":
                    print("   - Algunas funciones avanzadas tienen problemas menores")
    
    return todas_ok

def modo_interactivo():
    """Modo interactivo para probar traduciones manualmente"""
    print("\n🎮 MODO INTERACTIVO")
    print("=" * 40)
    print("Escribe frases para traducir (o 'salir' para terminar)")
    
    try:
        from translator import Translator
        traductor = Translator()
        
        while True:
            try:
                frase = input("\n📝 Frase a traducir: ").strip()
                
                if frase.lower() in ['salir', 'exit', 'quit', '']:
                    break
                
                print(f"🔄 Traduciendo: '{frase}'")
                videos = traductor.traducir(frase)
                
                if videos:
                    print(f"✅ Encontrados {len(videos)} videos:")
                    for i, video in enumerate(videos, 1):
                        nombre = os.path.basename(video)
                        existe = "✅" if os.path.isfile(video) else "❌"
                        print(f"   {i:2}. {existe} {nombre}")
                else:
                    print("❌ No se encontraron videos")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    except ImportError:
        print("❌ No se pudo importar el traductor")
    
    print("\n👋 ¡Hasta luego!")

def mostrar_ayuda():
    """Muestra ayuda sobre el uso del script"""
    ayuda = """
🆘 AYUDA - SCRIPT DE PRUEBA DEL TRADUCTOR OFFLINE

COMANDOS:
  python test_translator_offline.py              - Ejecutar todas las pruebas
  python test_translator_offline.py --interactivo - Modo interactivo
  python test_translator_offline.py --help        - Mostrar esta ayuda

REQUISITOS PREVIOS:
  1. Ejecutar: python download_stanza_models.py (CON internet)
  2. Tener los archivos: translator.py, diccionario.py
  3. Desconectar internet (opcional, para prueba completa)

QUÉ HACE ESTE SCRIPT:
  ✅ Verifica que los modelos de Stanza estén instalados
  ✅ Prueba Stanza en modo offline
  ✅ Prueba el traductor completo
  ✅ Verifica todas las funciones adicionales
  ✅ Genera un reporte detallado

SOLUCIÓN DE PROBLEMAS:
  - Si faltan modelos: python download_stanza_models.py
  - Si falla Stanza: pip install --upgrade stanza
  - Si falta traductor: verificar translator.py en directorio actual

ARCHIVOS NECESARIOS:
  📄 translator.py          - Traductor principal
  📄 diccionario.py         - Diccionario de señas
  📁 ~/.stanza_resources/   - Modelos de Stanza
"""
    print(ayuda)

if __name__ == "__main__":
    # Manejar argumentos de línea de comandos
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h', 'help']:
            mostrar_ayuda()
            sys.exit(0)
        elif arg in ['--interactivo', '-i', 'interactivo']:
            # Solo ejecutar modo interactivo
            print("🎮 INICIANDO MODO INTERACTIVO...")
            
            # Verificación rápida
            if not verificar_modelos_stanza():
                print("❌ Modelos no disponibles")
                sys.exit(1)
            
            if not probar_stanza_directo():
                print("❌ Stanza no funciona")
                sys.exit(1)
            
            modo_interactivo()
            sys.exit(0)
    
    # Ejecutar pruebas completas
    try:
        exito = main()
        
        # Preguntar si quiere modo interactivo
        if exito:
            respuesta = input("\n🎮 ¿Quieres probar el modo interactivo? (s/N): ")
            if respuesta.lower() in ['s', 'si', 'sí', 'y', 'yes']:
                modo_interactivo()
        
        sys.exit(0 if exito else 1)
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Cancelado por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)