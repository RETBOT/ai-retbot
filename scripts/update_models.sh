#!/bin/bash
# ============================================
# RETBOT - Actualización de Modelos Ollama
# ============================================
# Uso: ./scripts/update_models.sh
# 
# Este script actualiza los modelos de Ollama
# a sus versiones más recientes.
# ============================================

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================
# CONFIGURACIÓN - Editar según necesidad
# ============================================

# Modelos a actualizar
MODELOS=(
    "qwen2.5-coder:14b"
    "qwen2.5-coder:32b"
    "qwen2.5-coder:7b"
    "qwen2.5-coder:3b"
)

# Log file
LOG_FILE="logs/ollama_updates.log"

# Backup antes de actualizar (true/false)
HACER_BACKUP=true

# ============================================
# Funciones
# ============================================

log() {
    local mensaje="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${CYAN}[$timestamp]${NC} $mensaje"
    echo "[$timestamp] $mensaje" >> "$LOG_FILE" 2>/dev/null || true
}

log_success() {
    local mensaje="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[$timestamp]${NC} ✅ $mensaje"
    echo "[$timestamp] ✅ $mensaje" >> "$LOG_FILE" 2>/dev/null || true
}

log_error() {
    local mensaje="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[$timestamp]${NC} ❌ $mensaje" >&2
    echo "[$timestamp] ❌ $mensaje" >> "$LOG_FILE" 2>/dev/null || true
}

log_warning() {
    local mensaje="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[$timestamp]${NC} ⚠️  $mensaje"
    echo "[$timestamp] ⚠️  $mensaje" >> "$LOG_FILE" 2>/dev/null || true
}

# ============================================
# Verificar prerequisitos
# ============================================

verificar_prerequisitos() {
    log "Verificando prerequisitos..."
    
    # Verificar que ollama esté instalado
    if ! command -v ollama &> /dev/null; then
        log_error "Ollama no está instalado. Instalar desde https://ollama.com"
        exit 1
    fi
    
    # Verificar que Ollama esté corriendo
    if ! ollama list &> /dev/null; then
        log_error "Ollama no está corriendo. Ejecutar 'ollama serve' primero"
        exit 1
    fi
    
    # Crear directorio de logs si no existe
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    
    log_success "Prerequisitos verificados"
}

# ============================================
# Backup de datos de Ollama
# ============================================

hacer_backup() {
    if [ "$HACER_BACKUP" = false ]; then
        log "Backup deshabilitado, saltando..."
        return
    fi
    
    log "Creando backup de datos de Ollama..."
    
    BACKUP_DIR="backups/ollama_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Determinar directorio de Ollama según SO
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        OLLAMA_DIR="$HOME/.ollama"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        OLLAMA_DIR="$HOME/.ollama"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        # Windows (Git Bash/WSL)
        OLLAMA_DIR="$HOME/.ollama"
    else
        OLLAMA_DIR="$HOME/.ollama"
    fi
    
    if [ -d "$OLLAMA_DIR" ]; then
        # Crear backup comprimido
        tar -czf "$BACKUP_DIR/ollama_data.tar.gz" -C "$(dirname "$OLLAMA_DIR")" "$(basename "$OLLAMA_DIR")" 2>/dev/null || {
            # Si falla tar, copiar directorio
            cp -r "$OLLAMA_DIR" "$BACKUP_DIR/" 2>/dev/null || {
                log_warning "No se pudo crear backup. Continuando sin backup..."
                return
            }
        }
        
        # Guardar lista de modelos actuales
        ollama list > "$BACKUP_DIR/modelos_antes.txt" 2>/dev/null || true
        
        log_success "Backup creado en: $BACKUP_DIR"
    else
        log_warning "Directorio de Ollama no encontrado, saltando backup"
    fi
}

# ============================================
# Actualizar modelos
# ============================================

actualizar_modelos() {
    local actualizados=0
    local fallidos=0
    local sin_cambios=0
    
    log "🔄 Iniciando actualización de ${#MODELOS[@]} modelos..."
    echo ""
    
    for modelo in "${MODELOS[@]}"; do
        log "📦 Actualizando $modelo..."
        
        # Intentar actualizar
        OUTPUT=$(ollama pull "$modelo" 2>&1)
        RESULTADO=$?
        
        if [ $RESULTADO -eq 0 ]; then
            # Verificar si hubo actualización real o ya estaba actualizado
            if echo "$OUTPUT" | grep -q "already installed\|already up to date"; then
                log_success "$modelo - Ya estaba actualizado"
                ((sin_cambios++))
            else
                log_success "$modelo - Actualizado exitosamente"
                ((actualizados++))
            fi
        else
            log_error "$modelo - Falló la actualización"
            echo "$OUTPUT" >> "$LOG_FILE" 2>/dev/null || true
            ((fallidos++))
        fi
        
        echo ""
    done
    
    # Resumen
    echo ""
    log "============================================"
    log "📊 Resumen de actualización:"
    log_success "$actualizados modelos actualizados"
    if [ $sin_cambios -gt 0 ]; then
        log "$sin_cambios modelos ya estaban actualizados"
    fi
    if [ $fallidos -gt 0 ]; then
        log_error "$fallidos modelos fallaron"
    fi
    log "============================================"
    
    return $fallidos
}

# ============================================
# Verificar espacio en disco
# ============================================

verificar_espacio() {
    log "Verificando espacio en disco..."
    
    ESPACIO_LIBRE=$(df -h . | awk 'NR==2 {print $4}')
    log "Espacio libre: $ESPACIO_LIBRE"
    
    # Advertir si hay poco espacio (menos de 10GB)
    ESPACIO_GB=$(df -BG . | awk 'NR==2 {gsub("G",""); print $4}')
    if [ "$ESPACIO_GB" -lt 10 ]; then
        log_warning "Espacio libre menor a 10GB. Las actualizaciones podrían fallar."
    fi
}

# ============================================
# Mostrar modelos instalados
# ============================================

mostrar_modelos() {
    echo ""
    log "📋 Modelos instalados actualmente:"
    echo ""
    ollama list
    echo ""
}

# ============================================
# Main
# ============================================

main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  RETBOT - Actualización de Modelos    ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    
    verificar_prerequisitos
    verificar_espacio
    hacer_backup
    
    echo ""
    actualizar_modelos
    RESULTADO=$?
    
    mostrar_modelos
    
    if [ $RESULTADO -eq 0 ]; then
        log_success "¡Actualización completada exitosamente!"
        exit 0
    else
        log_error "Actualización completada con errores. Revisar log: $LOG_FILE"
        exit 1
    fi
}

# Ejecutar main
main "$@"
