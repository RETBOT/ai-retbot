# ============================================
# RETBOT - Actualización de Modelos Ollama
# ============================================
# Uso: .\scripts\update_models.ps1
# 
# Este script actualiza los modelos de Ollama
# a sus versiones más recientes.
# ============================================

# ============================================
# CONFIGURACIÓN - Editar según necesidad
# ============================================

# Modelos a actualizar
$MODELOS = @(
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:3b"
)

# Log file
$LOG_FILE = "logs\ollama_updates.log"

# Backup antes de actualizar ($true/$false)
$HACER_BACKUP = $true

# ============================================
# Funciones
# ============================================

function Write-Log {
    param([string]$Mensaje, [string]$Color = "Cyan")
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] $Mensaje"
    
    Write-Host $logMessage -ForegroundColor $Color
    
    # Escribir al archivo de log
    try {
        $logDir = Split-Path $LOG_FILE -Parent
        if (!(Test-Path $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        Add-Content -Path $LOG_FILE -Value $logMessage
    } catch {
        # Ignorar errores de log
    }
}

function Write-Success {
    param([string]$Mensaje)
    Write-Log -Mensaje $Mensaje -Color "Green"
}

function Write-Error-Custom {
    param([string]$Mensaje)
    Write-Log -Mensaje $Mensaje -Color "Red"
}

function Write-Warning-Custom {
    param([string]$Mensaje)
    Write-Log -Mensaje $Mensaje -Color "Yellow"
}

# ============================================
# Verificar prerequisitos
# ============================================

function Verificar-Prerequisitos {
    Write-Log "Verificando prerequisitos..."
    
    # Verificar que ollama esté instalado
    try {
        $ollamaPath = Get-Command ollama -ErrorAction Stop
        Write-Success "Ollama encontrado: $($ollamaPath.Source)"
    } catch {
        Write-Error-Custom "Ollama no está instalado. Instalar desde https://ollama.com"
        exit 1
    }
    
    # Verificar que Ollama esté corriendo
    try {
        $testResponse = ollama list 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Ollama está corriendo correctamente"
        } else {
            Write-Error-Custom "Ollama no está corriendo. Ejecutar 'ollama serve' primero"
            exit 1
        }
    } catch {
        Write-Error-Custom "Error al verificar Ollama: $_"
        exit 1
    }
}

# ============================================
# Backup de datos de Ollama
# ============================================

function Hacer-Backup {
    if (-not $HACER_BACKUP) {
        Write-Log "Backup deshabilitado, saltando..."
        return
    }
    
    Write-Log "Creando backup de datos de Ollama..."
    
    $backupDir = "backups\ollama_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    
    # Determinar directorio de Ollama
    $ollamaDir = "$env:USERPROFILE\.ollama"
    
    if (Test-Path $ollamaDir) {
        try {
            # Copiar directorio de Ollama
            Copy-Item -Path $ollamaDir -Destination $backupDir -Recurse -Force
            
            # Guardar lista de modelos actuales
            ollama list | Out-File "$backupDir\modelos_antes.txt" -Encoding UTF8
            
            Write-Success "Backup creado en: $backupDir"
        } catch {
            Write-Warning-Custom "No se pudo crear backup completo: $_"
        }
    } else {
        Write-Warning-Custom "Directorio de Ollama no encontrado: $ollamaDir"
    }
}

# ============================================
# Actualizar modelos
# ============================================

function Actualizar-Modelos {
    $actualizados = 0
    $fallidos = 0
    $sinCambios = 0
    
    Write-Log "🔄 Iniciando actualización de $($MODELOS.Count) modelos..."
    Write-Host ""
    
    foreach ($modelo in $MODELOS) {
        Write-Log "📦 Actualizando $modelo..."
        
        try {
            # Ejecutar ollama pull
            $output = ollama pull $modelo 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                # Verificar si hubo actualización real
                if ($output -match "already installed|already up to date") {
                    Write-Success "$modelo - Ya estaba actualizado"
                    $sinCambios++
                } else {
                    Write-Success "$modelo - Actualizado exitosamente"
                    $actualizados++
                }
            } else {
                Write-Error-Custom "$modelo - Falló la actualización"
                $output | Out-File $LOG_FILE -Append
                $fallidos++
            }
        } catch {
            Write-Error-Custom "$modelo - Error: $_"
            $fallidos++
        }
        
        Write-Host ""
    }
    
    # Resumen
    Write-Host ""
    Write-Log "============================================"
    Write-Log "📊 Resumen de actualización:"
    Write-Success "$actualizados modelos actualizados"
    
    if ($sinCambios -gt 0) {
        Write-Log "$sinCambios modelos ya estaban actualizados"
    }
    
    if ($fallidos -gt 0) {
        Write-Error-Custom "$fallidos modelos fallaron"
    }
    
    Write-Log "============================================"
    
    return $fallidos
}

# ============================================
# Verificar espacio en disco
# ============================================

function Verificar-Espacio {
    Write-Log "Verificando espacio en disco..."
    
    $drive = Get-PSDrive (Get-Location).Drive.Name
    $espacioLibreGB = [math]::Round($drive.Free / 1GB, 2)
    
    Write-Log "Espacio libre: ${espacioLibreGB}GB"
    
    if ($espacioLibreGB -lt 10) {
        Write-Warning-Custom "Espacio libre menor a 10GB. Las actualizaciones podrían fallar."
    }
}

# ============================================
# Mostrar modelos instalados
# ============================================

function Mostrar-Modelos {
    Write-Host ""
    Write-Log "📋 Modelos instalados actualmente:"
    Write-Host ""
    
    try {
        ollama list
    } catch {
        Write-Warning-Custom "No se pudo listar modelos: $_"
    }
    
    Write-Host ""
}

# ============================================
# Main
# ============================================

function Main {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Blue
    Write-Host "║  RETBOT - Actualización de Modelos    ║" -ForegroundColor Blue
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Blue
    Write-Host ""
    
    Verificar-Prerequisitos
    Verificar-Espacio
    Hacer-Backup
    
    Write-Host ""
    $fallidos = Actualizar-Modelos
    Mostrar-Modelos
    
    if ($fallidos -eq 0) {
        Write-Success "¡Actualización completada exitosamente!"
        exit 0
    } else {
        Write-Error-Custom "Actualización completada con errores. Revisar log: $LOG_FILE"
        exit 1
    }
}

# Configurar encoding para caracteres UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Ejecutar main
Main
