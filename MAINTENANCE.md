# 🔧 Mantenimiento de RETBOT

Guía completa para mantenimiento, actualizaciones y operaciones del sistema.

---

## 📋 Tabla de Contenidos

- [Actualización de Modelos](#-actualización-de-modelos)
- [Backup y Restauración](#-backup-y-restauración)
- [Monitoreo](#-monitoreo)
- [Limpieza](#-limpieza)
- [Rollback](#-rollback)
- [Operaciones Programadas](#-operaciones-programadas)

---

## 🔄 Actualización de Modelos

### Scripts Disponibles

| Script | Plataforma | Uso |
|--------|-----------|-----|
| `update_models.sh` | Linux/Mac/WSL | `./scripts/update_models.sh` |
| `update_models.ps1` | Windows | `.\scripts\update_models.ps1` |
| `update_models.py` | Cross-platform | `python scripts/update_models.py` |

### Configuración de Modelos

Editar `scripts/update_models.*` para cambiar los modelos a actualizar:

```bash
# Ejemplo: scripts/update_models.sh
MODELOS=(
    "qwen2.5-coder:14b"
    "qwen2.5-coder:32b"
    # Agregar o quitar modelos aquí
)
```

### Flujo de Actualización

```
1. Verificar prerequisitos
   └─ Ollama instalado ✓
   └─ Ollama corriendo ✓
   └─ Espacio en disco ✓

2. Crear backup
   └─ Backup de ~/.ollama
   └─ Lista de modelos actuales

3. Actualizar cada modelo
   └─ ollama pull <modelo>
   └─ Verificar éxito/fracaso

4. Mostrar resumen
   └─ Modelos actualizados
   └─ Modelos sin cambios
   └─ Modelos fallidos

5. Guardar log
   └─ logs/ollama_updates.log
```

### Logs de Actualización

Los logs se guardan en `logs/ollama_updates.log`:

```
[2026-04-26 11:30:00] 🔄 Iniciando actualización de 4 modelos...
[2026-04-26 11:30:05] ✅ qwen2.5-coder:14b - Actualizado exitosamente
[2026-04-26 11:32:10] ✅ qwen2.5-coder:32b - Ya estaba actualizado
[2026-04-26 11:34:15] ✅ 2 modelos actualizados
[2026-04-26 11:34:15] ✅ 2 modelos ya estaban actualizados
```

---

## 💾 Backup y Restauración

### Backup Manual

```bash
# Linux/Mac
tar -czf ollama_backup_$(date +%Y%m%d).tar.gz ~/.ollama

# Windows (PowerShell)
Compress-Archive -Path $env:USERPROFILE\.ollama `
  -DestinationPath "ollama_backup_$(Get-Date -Format yyyyMMdd).zip"
```

### Backup Automático

Los scripts de actualización crean backup automáticamente en:
```
backups/
├── ollama_20260426_113000/
│   ├── ollama_data.tar.gz
│   └── modelos_antes.json
├── ollama_20260503_030000/
│   └── ...
```

### Restaurar Backup

```bash
# Detener Ollama
ollama serve  # Ctrl+C para detener

# Restaurar backup
tar -xzf backups/ollama_20260426_113000/ollama_data.tar.gz -C ~/

# Reiniciar Ollama
ollama serve &

# Verificar modelos
ollama list
```

### Backup de Base de Datos RETBOT

```bash
# SQLite database
cp data.db data.db.backup_$(date +%Y%m%d)

# O con Docker
docker cp api:/app/data.db ./data.db.backup
```

---

## 📊 Monitoreo

### Health Checks

```bash
# Verificar API
curl http://localhost:8000/health

# Verificar Ollama
curl http://localhost:11434/api/tags

# Verificar modelos disponibles
curl http://localhost:8000/v1/models
```

### Métricas de Rendimiento

```bash
# Test de velocidad
time curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo_key_123" \
  -d '{"messages":[{"role":"user","content":"Hola"}],"stream":false}'
```

### Logs en Tiempo Real

```bash
# Logs de RETBOT
tail -f logs/server.log

# Logs de Ollama
ollama serve 2>&1 | tee logs/ollama.log

# Logs de actualizaciones
tail -f logs/ollama_updates.log
```

### Uso de Recursos

```bash
# VRAM (GPU)
watch -n 1 nvidia-smi

# RAM y CPU
htop

# Disco
df -h
du -sh ~/.ollama
```

---

## 🧹 Limpieza

### Eliminar Modelos Viejos

```bash
# Ver modelos instalados
ollama list

# Eliminar modelo específico
ollama rm qwen2.5-coder:7b

# Eliminar múltiples modelos
ollama rm qwen2.5-coder:3b qwen2.5-coder:7b
```

### Limpiar Logs Viejos

```bash
# Linux/Mac - Logs mayores a 30 días
find logs/ -name "*.log" -mtime +30 -delete

# Windows (PowerShell) - Logs mayores a 30 días
Get-ChildItem logs\*.log | Where-Object {
    $_.LastWriteTime -lt (Get-Date).AddDays(-30)
} | Remove-Item
```

### Limpiar Backups Viejos

```bash
# Mantener solo últimos 5 backups
ls -t backups/ | tail -n +6 | xargs rm -rf

# Windows (PowerShell)
Get-ChildItem backups\ | Sort-Object LastWriteTime -Descending |
  Select-Object -Skip 5 | Remove-Item -Recurse
```

### Espacio Recuperado

```bash
# Ver espacio usado por Ollama
du -sh ~/.ollama  # Linux/Mac
Get-ChildItem $env:USERPROFILE\.ollama -Recurse |
  Measure-Object -Property Length -Sum  # Windows
```

---

## ↩️ Rollback

### Rollback de Modelo

Si una actualización causa problemas:

```bash
# 1. Verificar backup disponible
ls backups/

# 2. Detener Ollama
# Ctrl+C si está corriendo en terminal

# 3. Restaurar backup
rm -rf ~/.ollama
tar -xzf backups/ollama_20260426_113000/ollama_data.tar.gz -C ~/

# 4. Reiniciar Ollama
ollama serve &

# 5. Verificar
ollama list
```

### Rollback de Configuración

```bash
# Restaurar .env anterior
cp .env.backup .env

# Restaurar docker-compose anterior
git checkout HEAD -- docker-compose.yml

# Reiniciar servicios
docker compose down
docker compose up -d
```

---

## 📅 Operaciones Programadas

### Checklist Semanal

```markdown
## Cada semana (Domingo 3 AM)
- [ ] Ejecutar actualización de modelos
      `./scripts/update_models.sh`
- [ ] Revisar logs de errores
      `grep ERROR logs/*.log`
- [ ] Verificar espacio en disco
      `df -h`
- [ ] Verificar backups recientes
      `ls -lt backups/`
```

### Checklist Mensual

```markdown
## Cada mes (Primer lunes)
- [ ] Revisar métricas de rendimiento
- [ ] Limpiar logs > 30 días
- [ ] Limpiar backups > 4 semanas
- [ ] Verificar versiones de dependencias
- [ ] Revisar changelog de Ollama
- [ ] Actualizar documentación si es necesario
```

### Checklist Trimestral

```markdown
## Cada 3 meses
- [ ] Evaluar nuevos modelos disponibles
- [ ] Revisar configuración de concurrencia
- [ ] Testear disaster recovery
- [ ] Actualizar drivers de GPU (si aplica)
- [ ] Revisar security updates
- [ ] Backup completo del sistema
```

---

## 🔐 Seguridad

### Actualizar Dependencias

```bash
# Python dependencies
pip list --outdated
pip install -r requirements.txt --upgrade

# O en entorno virtual
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt --upgrade
```

### Rotar API Keys

```bash
# Listar API keys existentes
python cli/main.py list-api-keys --user admin

# Crear nueva API key
python cli/main.py create-api-key --user admin --name "Nueva Key"

# Revocar key vieja (manual en DB)
# sqlite3 data.db "DELETE FROM api_keys WHERE key='rb_old_key';"
```

### Cambiar Password de Admin

```bash
# Desde CLI
python cli/main.py change-password --user admin

# O desde API
curl -X PUT http://localhost:8000/auth/password \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"old_password":"viejo","new_password":"nuevo"}'
```

---

## 🚨 Emergency Procedures

### Si Ollama No Responde

```bash
# 1. Verificar proceso
ps aux | grep ollama

# 2. Matar proceso
pkill ollama

# 3. Reiniciar
ollama serve &

# 4. Verificar
ollama list
```

### Si API No Responde

```bash
# 1. Verificar proceso
ps aux | grep python

# 2. Verificar puerto
netstat -tlnp | grep 8000

# 3. Matar proceso
pkill -f server.py

# 4. Reiniciar
python server.py
```

### Si GPU Falla

```bash
# 1. Verificar estado
nvidia-smi

# 2. Si hay error CUDA
#    - Reiniciar sistema
#    - Verificar drivers
#    - Reducir OLLAMA_NUM_PARALLEL

# 3. Fallback a CPU (temporal)
#    Editar .env:
#    MODEL_NAME=qwen2.5-coder:3b
#    # Comentar OLLAMA_NUM_PARALLEL
```

---

## 📞 Soporte

### Recursos

- [Readme.md](Readme.md) - Documentación principal
- [GPU_SETUP_GUIDE.md](GPU_SETUP_GUIDE.md) - Configuración de GPUs
- [CONFIGURACION_RAPIDA.md](CONFIGURACION_RAPIDA.md) - Referencia rápida

### Logs para Debugging

```bash
# Recopilar logs para soporte
mkdir logs_for_support
cp logs/*.log logs_for_support/
ollama list > logs_for_support/modelos.txt
nvidia-smi > logs_for_support/gpu.txt
tar -czf logs_for_support_$(date +%Y%m%d).tar.gz logs_for_support/
```

### Crear Issue

Incluir en el issue:
1. Versión de Python: `python --version`
2. Versión de Ollama: `ollama --version`
3. Sistema operativo
4. Logs relevantes
5. Pasos para reproducir

---

<p align="center">
  <b>¿Problemas?</b> Revisa <a href="Readme.md#-troubleshooting">Troubleshooting</a> o crea un issue
</p>
