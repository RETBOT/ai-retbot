# ⚡ Configuraciones Rápidas - RETBOT

Guía rápida de configuraciones según tu hardware.

---

## 📋 Tabla Resumen

| Hardware | Modelo | OLLAMA_NUM_PARALLEL | Users | Notas |
|----------|--------|---------------------|-------|-------|
| **CPU** | qwen2.5-coder:3b | (default) | 1-2 | Lento, solo dev |
| **CPU** | qwen2.5-coder:7b | (default) | 1-2 | Lento, solo dev |
| **1×4090** | qwen2.5-coder:14b | 4 | 4-7 | Recomendado |
| **1×4090** | qwen2.5-coder:32b | 2 | 2-4 | Máxima calidad |
| **2×4090** | qwen2.5-coder:14b | 8 | 8-12 | Balanceado |
| **2×4090** | qwen2.5-coder:32b | 4 | 4-8 | Calidad |
| **3×4090** | qwen2.5-coder:32b | 12 | 15-30 | Producción |

---

## 🔧 Configuración por Hardware

### Sin GPU (CPU)

```bash
# .env
MODEL_NAME=qwen2.5-coder:3b
# OLLAMA_NUM_PARALLEL=   # COMENTAR
OLLAMA_CONTEXT_LENGTH=4096
```

**Comandos:**
```bash
ollama pull qwen2.5-coder:3b
python server.py
```

---

### 1 GPU RTX 4090

```bash
# .env
MODEL_NAME=qwen2.5-coder:14b
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=2
OLLAMA_CONTEXT_LENGTH=8192
```

**Comandos:**
```bash
ollama pull qwen2.5-coder:14b
python server.py
```

**O con Docker:**
```bash
docker compose -f docker-compose.gpu.yml up -d
docker exec -it ollama ollama pull qwen2.5-coder:14b
```

---

### 2 GPUs RTX 4090

**Opción A: Una instancia**
```bash
# .env
MODEL_NAME=qwen2.5-coder:32b
OLLAMA_NUM_PARALLEL=8
CUDA_VISIBLE_DEVICES=0,1
```

**Opción B: Dos instancias + Nginx**
```bash
# Terminal 1
CUDA_VISIBLE_DEVICES=0 ollama serve --port 11434

# Terminal 2
CUDA_VISIBLE_DEVICES=1 ollama serve --port 11435
```

---

### 3 GPUs RTX 4090

```bash
# Terminal 1
CUDA_VISIBLE_DEVICES=0 ollama serve --port 11434

# Terminal 2
CUDA_VISIBLE_DEVICES=1 ollama serve --port 11435

# Terminal 3
CUDA_VISIBLE_DEVICES=2 ollama serve --port 11436
```

**Usar nginx.conf.example para load balancing**

---

## 🐳 Docker Commands

```bash
# Iniciar con GPU
docker compose -f docker-compose.gpu.yml up -d

# Ver logs
docker compose -f docker-compose.gpu.yml logs -f

# Descargar modelo
docker exec -it ollama ollama pull qwen2.5-coder:14b

# Ver modelos
docker exec -it ollama ollama list

# Detener
docker compose -f docker-compose.gpu.yml down

# Ver uso de GPU
docker exec -it ollama nvidia-smi
```

---

## 🔍 Monitoreo

```bash
# Ver uso de VRAM
watch -n 1 nvidia-smi

# Health check
curl http://localhost:8000/health

# Ver modelos
curl http://localhost:8000/v1/models

# Test de velocidad
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo_key_123" \
  -d '{"messages":[{"role":"user","content":"Hola"}],"stream":false}'
```

---

## 🐛 Problemas Comunes

### "CUDA out of memory"
```bash
# Reducir parallel
OLLAMA_NUM_PARALLEL=2

# O usar modelo más pequeño
MODEL_NAME=qwen2.5-coder:14b
```

### "Model not found"
```bash
ollama pull qwen2.5-coder:14b
```

### "Docker no ve GPUs"
```bash
# Verificar instalación
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# Reiniciar Docker
# Windows: Docker Desktop → Quit → Start
# Linux: sudo systemctl restart docker
```

---

## 📚 Más Info

- [GPU_SETUP_GUIDE.md](GPU_SETUP_GUIDE.md) - Guía completa de GPUs
- [Readme.md](Readme.md) - Documentación principal
- [nginx.conf.example](nginx.conf.example) - Load balancing config

---

<p align="center">
  <b>¿Necesitas ayuda?</b> Revisa el <a href="Readme.md#-troubleshooting">Troubleshooting</a>
</p>
