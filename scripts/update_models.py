#!/usr/bin/env python3
"""
RETBOT - Actualización de Modelos Ollama

Script cross-platform para actualizar modelos de Ollama.
Funciona en Windows, Linux y macOS.

Uso:
    python scripts/update_models.py

Requisitos:
    - Ollama instalado y corriendo
    - Python 3.8+
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
import shutil
import tarfile
import json

# ============================================
# CONFIGURACIÓN
# ============================================

# Modelos a actualizar
MODELOS = [
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:3b",
]

# Directorio de logs
LOG_FILE = Path("logs/ollama_updates.log")

# Hacer backup antes de actualizar
HACER_BACKUP = True

# Colores para terminal
class Colores:
    CYAN = "\033[0;36m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    RED = "\033[0;31m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


# ============================================
# Funciones de Log
# ============================================

def log(mensaje: str, color: str = Colores.CYAN):
    """Imprimir mensaje con color y guardar en log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mensaje_log = f"[{timestamp}] {mensaje}"
    
    # Imprimir con color
    print(f"{color}{mensaje_log}{Colores.NC}")
    
    # Guardar en archivo (sin colores)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(mensaje_log + "\n")
    except Exception:
        pass


def log_success(mensaje: str):
    log(f"✅ {mensaje}", Colores.GREEN)


def log_error(mensaje: str):
    log(f"❌ {mensaje}", Colores.RED)


def log_warning(mensaje: str):
    log(f"⚠️  {mensaje}", Colores.YELLOW)


# ============================================
# Verificar prerequisitos
# ============================================

def verificar_prerequisitos() -> bool:
    """Verificar que Ollama esté instalado y corriendo"""
    log("Verificando prerequisitos...")
    
    # Verificar que ollama esté instalado
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            log_success(f"Ollama instalado: {result.stdout.strip()}")
        else:
            log_error("Ollama no está instalado correctamente")
            return False
    except FileNotFoundError:
        log_error("Ollama no está instalado. Instalar desde https://ollama.com")
        return False
    except subprocess.TimeoutExpired:
        log_error("Timeout al verificar Ollama")
        return False
    
    # Verificar que Ollama esté corriendo
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            log_success("Ollama está corriendo correctamente")
        else:
            log_error("Ollama no está corriendo. Ejecutar 'ollama serve' primero")
            return False
    except Exception as e:
        log_error(f"Error al verificar Ollama: {e}")
        return False
    
    return True


# ============================================
# Backup de datos de Ollama
# ============================================

def hacer_backup() -> bool:
    """Crear backup del directorio de Ollama"""
    if not HACER_BACKUP:
        log("Backup deshabilitado, saltando...")
        return True
    
    log("Creando backup de datos de Ollama...")
    
    # Determinar directorio de Ollama según SO
    if sys.platform == "darwin":  # macOS
        ollama_dir = Path.home() / ".ollama"
    elif sys.platform == "win32":  # Windows
        ollama_dir = Path(os.environ.get("USERPROFILE", "~")) / ".ollama"
    else:  # Linux y otros
        ollama_dir = Path.home() / ".ollama"
    
    if not ollama_dir.exists():
        log_warning(f"Directorio de Ollama no encontrado: {ollama_dir}")
        return False
    
    # Crear directorio de backup
    backup_dir = Path("backups") / f"ollama_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Guardar lista de modelos actuales
        result = subprocess.run(
            ["ollama", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            with open(backup_dir / "modelos_antes.json", "w", encoding="utf-8") as f:
                f.write(result.stdout)
        
        # Crear backup comprimido (si es posible)
        backup_tar = backup_dir / "ollama_data.tar.gz"
        try:
            with tarfile.open(backup_tar, "w:gz") as tar:
                tar.add(ollama_dir, arcname="ollama")
            log_success(f"Backup creado en: {backup_dir}")
            return True
        except Exception as e:
            log_warning(f"No se pudo crear backup comprimido: {e}")
            # Intentar copia simple
            try:
                shutil.copytree(ollama_dir, backup_dir / "ollama")
                log_success(f"Backup creado (copia simple) en: {backup_dir}")
                return True
            except Exception as e2:
                log_error(f"Error al crear backup: {e2}")
                return False
                
    except Exception as e:
        log_warning(f"Error al crear backup: {e}")
        return False


# ============================================
# Actualizar modelos
# ============================================

def actualizar_modelo(modelo: str) -> tuple[bool, bool]:
    """
    Actualizar un modelo específico.
    Returns: (exitoso, hubo_cambios)
    """
    log(f"📦 Actualizando {modelo}...")
    
    try:
        result = subprocess.run(
            ["ollama", "pull", modelo],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos timeout
        )
        
        if result.returncode == 0:
            # Verificar si hubo actualización real
            output = result.stdout + result.stderr
            if "already installed" in output.lower() or "already up to date" in output.lower():
                log_success(f"{modelo} - Ya estaba actualizado")
                return True, False
            else:
                log_success(f"{modelo} - Actualizado exitosamente")
                return True, True
        else:
            log_error(f"{modelo} - Falló la actualización")
            log_error(f"Error: {result.stderr.strip()}")
            return False, False
            
    except subprocess.TimeoutExpired:
        log_error(f"{modelo} - Timeout en la actualización")
        return False, False
    except Exception as e:
        log_error(f"{modelo} - Error: {e}")
        return False, False


def actualizar_todos_los_modelos() -> int:
    """
    Actualizar todos los modelos configurados.
    Returns: número de modelos fallidos
    """
    log(f"🔄 Iniciando actualización de {len(MODELOS)} modelos...")
    print()
    
    actualizados = 0
    fallidos = 0
    sin_cambios = 0
    
    for modelo in MODELOS:
        exitoso, hubo_cambios = actualizar_modelo(modelo)
        
        if exitoso:
            if hubo_cambios:
                actualizados += 1
            else:
                sin_cambios += 1
        else:
            fallidos += 1
        
        print()
    
    # Resumen
    print()
    log("=" * 50)
    log("📊 Resumen de actualización:")
    log_success(f"{actualizados} modelos actualizados")
    
    if sin_cambios > 0:
        log(f"{sin_cambios} modelos ya estaban actualizados")
    
    if fallidos > 0:
        log_error(f"{fallidos} modelos fallaron")
    
    log("=" * 50)
    
    return fallidos


# ============================================
# Verificar espacio en disco
# ============================================

def verificar_espacio() -> bool:
    """Verificar que hay suficiente espacio en disco"""
    log("Verificando espacio en disco...")
    
    try:
        # Obtener espacio libre
        if sys.platform == "win32":
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p("."), None, None, ctypes.byref(free_bytes)
            )
            espacio_libre_gb = free_bytes.value / (1024**3)
        else:
            stat = os.statvfs(".")
            espacio_libre_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
        
        log(f"Espacio libre: {espacio_libre_gb:.2f}GB")
        
        if espacio_libre_gb < 10:
            log_warning("Espacio libre menor a 10GB. Las actualizaciones podrían fallar.")
            return False
        
        return True
        
    except Exception as e:
        log_warning(f"No se pudo verificar espacio en disco: {e}")
        return True  # Continuar de todos modos


# ============================================
# Mostrar modelos instalados
# ============================================

def mostrar_modelos():
    """Mostrar lista de modelos instalados"""
    print()
    log("📋 Modelos instalados actualmente:")
    print()
    
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            print(result.stdout)
        else:
            log_warning("No se pudo listar modelos")
    except Exception as e:
        log_warning(f"Error al listar modelos: {e}")
    
    print()


# ============================================
# Main
# ============================================

def main():
    """Función principal"""
    print()
    print(f"{Colores.BLUE}╔════════════════════════════════════════╗{Colores.NC}")
    print(f"{Colores.BLUE}║  RETBOT - Actualización de Modelos    ║{Colores.NC}")
    print(f"{Colores.BLUE}╚════════════════════════════════════════╝{Colores.NC}")
    print()
    
    # Verificar prerequisitos
    if not verificar_prerequisitos():
        sys.exit(1)
    
    # Verificar espacio
    verificar_espacio()
    
    # Hacer backup
    hacer_backup()
    
    print()
    
    # Actualizar modelos
    fallidos = actualizar_todos_los_modelos()
    
    # Mostrar modelos
    mostrar_modelos()
    
    # Resultado final
    if fallidos == 0:
        log_success("¡Actualización completada exitosamente!")
        sys.exit(0)
    else:
        log_error(f"Actualización completada con {fallidos} errores. Revisar log: {LOG_FILE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
