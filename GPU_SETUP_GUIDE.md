# 🎮 Guía de Configuración de GPUs para RETBOT

Esta guía te ayudará a configurar RETBOT cuando agregues GPUs RTX 4090.

---

## 📋 Checklist Previo

Antes de empezar, verifica:

- [ ] Tienes instalado el driver de NVIDIA más reciente
- [ ] Tienes al menos 32GB de RAM por GPU
- [ ] Tienes espacio en disco (50GB+ por modelo)
- [ ] Tu fuente de poder soporta las GPUs (750W+ por 4090)

---

## 🔧 Paso 1: Instalar Drivers y Herramientas

### Windows (WSL2)

```powershell
# 1. Instalar drivers NVIDIA desde nvidia.com
# 2. Instalar WSL2
wsl --install

# 3. Instalar Docker Desktop con soporte WSL2
# Descargar desde: https://www.docker.com/products/docker-desktop/

# 4. Habilitar WSL2 en Docker Desktop
# Settings → Resources → WSL Integration → Enable
```

### Linux (Ubuntu)

```bash
# 1. Instalar drivers NVIDIA
sudo apt update
sudo apt install -y nvidia-driver-535

# 2. Instalar NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# 3. Reiniciar Docker
sudo systemctl restart docker

# 4. Verificar instalación
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

---

## 🚀 Paso 2: Configurar según Número de GPUs

### Configuración para 1 GPU RTX 4090

**Archivo `.env`:**
```bash
# Modelo recomendado
MODEL_NAME=qwen2.5-coder:14b

# Concurrencia
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=2

# Contexto
OLLAMA_CONTEXT_LENGTH=8192
```

**Comandos:**
```bash
# Descargar modelo
ollama pull qwen2.5-coder:14b

# Iniciar RETBOT
python server.py

# O con Docker (sin GPU en contenedor)
docker compose up -d
```

**Rendimiento esperado:**
- 4-7 usuarios concurrentes
- ~15-25 tokens/segundo
- VRAM usada: ~9GB (14b) o ~20GB (32b)

---

### Configuración para 2 GPUs RTX 4090

**Opción A: Una instancia de Ollama usando ambas GPUs**

```bash
# .env
MODEL_NAME=qwen2.5-coder:32b
OLLAMA_NUM_PARALLEL=8
OLLAMA_MAX_LOADED_MODELS=2
CUDA_VISIBLE_DEVICES=0,1
```

**Opción B: Dos instancias separadas + Nginx**

```bash
# Terminal 1 - GPU 0
CUDA_VISIBLE_DEVICES=0 ollama serve --port 11434

# Terminal 2 - GPU 1
CUDA_VISIBLE_DEVICES=1 ollama serve --port 11435
```

**nginx.conf:**
```nginx
upstream ollama_backends {
    least_conn;
    server localhost:11434;
    server localhost:11435;
}
```

**Rendimiento esperado:**
- 8-15 usuarios concurrentes
- ~30-50 tokens/segundo
- VRAM usada: ~40GB total

---

### Configuración para 3 GPUs RTX 4090

**Opción recomendada: Tres instancias separadas**

```bash
# Terminal 1 - GPU 0
CUDA_VISIBLE_DEVICES=0 ollama serve --port 11434

# Terminal 2 - GPU 1
CUDA_VISIBLE_DEVICES=1 ollama serve --port 11435

# Terminal 3 - GPU 2
CUDA_VISIBLE_DEVICES=2 ollama serve --port 11436
```

**Usar Docker Compose con GPU:**
```bash
docker compose -f docker-compose.gpu.yml up -d
```

**Rendimiento esperado:**
- 15-30 usuarios concurrentes
- ~50-80 tokens/segundo
- VRAM usada: ~60GB total

---

## 🐳 Paso 3: Docker con GPU

### Verificar que Docker ve las GPUs

```bash
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

Deberías ver output similar a:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.104.05   Driver Version: 535.104.05   CUDA Version: 12.2     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...  Off  | 00000000:01:00.0 On |                  N/A |
|  0%   45C    P8    12W / 450W |    500MiB / 24564MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

### Iniciar con Docker Compose GPU

```bash
# 1. Editar docker-compose.gpu.yml según tus GPUs
# 2. Iniciar servicios
docker compose -f docker-compose.gpu.yml up -d

# 3. Ver logs
docker compose -f docker-compose.gpu.yml logs -f

# 4. Descargar modelo dentro del contenedor
docker exec -it ollama ollama pull qwen2.5-coder:14b

# 5. Verificar que Ollama está funcionando
docker exec -it ollama ollama list
```

---

## 📊 Paso 4: Monitoreo

### Ver uso de VRAM en tiempo real

```bash
# Linux/WSL
watch -n 1 nvidia-smi

# Windows
# Abrir Task Manager → Performance → GPU
```

### Ver logs de Ollama

```bash
# Si corre en host
ollama serve 2>&1 | tee ollama.log

# Si corre en Docker
docker logs -f ollama
```

### Ver métricas de RETBOT

```bash
# Health check
curl http://localhost:8000/health

# Ver modelos disponibles
curl http://localhost:8000/v1/models
```

---

## 🐛 Troubleshooting

### Error: "CUDA out of memory"

**Causa:** El modelo es muy grande para la VRAM disponible.

**Soluciones:**
1. Reducir `OLLAMA_NUM_PARALLEL`
2. Usar modelo más pequeño (14b en vez de 32b)
3. Reducir `OLLAMA_CONTEXT_LENGTH`
4. Cerrar otras aplicaciones usando GPU

### Error: "Docker no ve las GPUs"

**Soluciones:**
1. Verificar NVIDIA Container Toolkit instalado
2. Reiniciar Docker Desktop
3. En WSL2: `wsl --shutdown` y reiniciar
4. Verificar drivers actualizados

### Error: "Model not found"

```bash
# Descargar el modelo
ollama pull qwen2.5-coder:14b

# Verificar descarga
ollama list
```

### Alto tiempo de respuesta

**Causas posibles:**
1. Modelo muy grande para el hardware
2. Demasiados usuarios concurrentes
3. Contexto muy largo

**Soluciones:**
1. Reducir `OLLAMA_NUM_PARALLEL`
2. Usar modelo más pequeño
3. Reducir `OLLAMA_CONTEXT_LENGTH`

---

## 📈 Optimización Avanzada

### Ajustar OLLAMA_NUM_PARALLEL

La fórmula práctica es:

```
OLLAMA_NUM_PARALLEL = (VRAM_disponible - VRAM_modelo) / VRAM_por_contexto
```

**Ejemplo para RTX 4090 (24GB) con qwen2.5-coder:14b (~9GB):**
- VRAM disponible: 24GB
- VRAM modelo: 9GB
- VRAM libre: 15GB
- VRAM por contexto (8K): ~1GB
- PARALLEL recomendado: 4-6

### Mantener modelo en VRAM

Para evitar cold starts:

```bash
# .env
OLLAMA_KEEP_ALIVE=-1  # Mantener modelo cargado indefinidamente
```

### Usar modelos cuantizados

```bash
# Mejor balance calidad/tamaño
ollama pull qwen2.5-coder:14b-q4_K_M

# Máxima calidad (más VRAM)
ollama pull qwen2.5-coder:14b-q8_0

# Máxima velocidad (menos calidad)
ollama pull qwen2.5-coder:14b-q2_K
```

---

## 🎯 Resumen de Configuraciones

| GPUs | Modelo | OLLAMA_NUM_PARALLEL | Users | VRAM Total |
|------|--------|---------------------|-------|------------|
| 1×4090 | qwen2.5-coder:14b | 4 | 4-7 | 9GB |
| 1×4090 | qwen2.5-coder:32b | 2 | 2-4 | 20GB |
| 2×4090 | qwen2.5-coder:14b | 8 | 8-12 | 18GB |
| 2×4090 | qwen2.5-coder:32b | 4 | 4-8 | 40GB |
| 3×4090 | qwen2.5-coder:32b | 12 | 15-30 | 60GB |

---

## 🔗 Recursos Útiles

- [Ollama Documentation](https://ollama.com/)
- [NVIDIA Container Toolkit](https://github.com/NVIDIA/nvidia-container-toolkit)
- [Docker GPU Support](https://docs.docker.com/config/containers/resource_constraints/#gpu)
- [Qwen2.5 Coder Models](https://huggingface.co/Qwen)

---

<p align="center">
  <b>¿Dudas?</b> Revisa el <a href="Readme.md#-troubleshooting">Troubleshooting</a> o crea un issue
</p>
