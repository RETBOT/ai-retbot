# 🧪 Load Testing - RETBOT

Guía completa para realizar load testing del sistema.

---

## 📋 Objetivo

Simular múltiples usuarios concurrentes para:
- Validar que el sistema soporta 7-30 usuarios
- Encontrar cuellos de botella
- Medir latencia bajo carga
- Validar rate limiting y cache

---

## 🛠️ Herramientas

### Opción 1: Locust (Recomendado)

```bash
pip install locust
```

### Opción 2: k6

```bash
# Instalar desde https://k6.io/docs/getting-started/installation/
```

### Opción 3: Script Python (Incluido)

```bash
python tests/load_test.py
```

---

## 🚀 Load Test con Locust

### 1. Instalar Locust

```bash
pip install locust
```

### 2. Ejecutar Load Test

```bash
# Iniciar Locust
locust -f tests/load_test_locust.py --host=http://localhost:8000

# Abrir navegador en http://localhost:8089
```

### 3. Configurar Usuarios

- **Users**: 7, 15, 30 (según prueba)
- **Spawn rate**: 1 usuario/segundo
- **Duration**: 5-10 minutos

---

## 📊 Métricas a Monitorear

### Durante el Load Test

| Métrica | Qué observar | Valor esperado |
|---------|-------------|----------------|
| **Requests/sec** | Throughput del sistema | 10-50 req/s |
| **Avg Response Time** | Latencia promedio | < 5s sin cache, < 500ms con cache |
| **Median Response Time** | Latencia mediana | < 3s |
| **95th Percentile** | Casos lentos | < 10s |
| **Failures** | Requests fallidos | < 1% |

### Recursos del Sistema

```bash
# Monitorear en tiempo real
watch -n 1 nvidia-smi          # GPU
htop                           # CPU/RAM
df -h                          # Disco
```

---

## 🎯 Escenarios de Prueba

### Escenario 1: 7 Usuarios Concurrentes

```bash
python tests/load_test.py --users 7 --duration 300
```

**Esperado:**
- ✅ 0% fallos
- ✅ Latencia < 5s
- ✅ Rate limiting no se activa (20 req/min por user)

### Escenario 2: 15 Usuarios Concurrentes

```bash
python tests/load_test.py --users 15 --duration 300
```

**Esperado:**
- ✅ < 1% fallos
- ✅ Latencia < 10s
- ⚠️ Rate limiting puede activarse para usuarios activos

### Escenario 3: 30 Usuarios Concurrentes

```bash
python tests/load_test.py --users 30 --duration 300
```

**Esperado:**
- ⚠️ < 5% fallos (aceptable bajo carga extrema)
- ⚠️ Latencia < 30s
- ⚠️ Rate limiting activo para algunos usuarios

---

## 📈 Interpretación de Resultados

### ✅ Sistema Saludable

- Failures < 1%
- 95th percentile < 10s
- CPU < 80%
- GPU VRAM < 90%
- Memory < 80%

### ⚠️ Sistema bajo estrés

- Failures 1-5%
- 95th percentile 10-30s
- CPU 80-95%
- GPU VRAM 90-95%

### ❌ Sistema saturado

- Failures > 5%
- 95th percentile > 30s
- CPU > 95%
- GPU VRAM > 95%
- Timeouts frecuentes

---

## 🔧 Ajustes Recomendados

### Si hay muchos fallos

1. **Reducir OLLAMA_NUM_PARALLEL**
   ```bash
   # .env
   OLLAMA_NUM_PARALLEL=2  # En vez de 4
   ```

2. **Aumentar timeouts**
   ```python
   # api/streaming.py
   stream_client = httpx.AsyncClient(timeout=300.0)
   ```

3. **Habilitar cache**
   ```bash
   # .env
   REDIS_URL=redis://localhost:6379
   ```

### Si la latencia es alta

1. **Usar modelo más pequeño**
   ```bash
   # .env
   MODEL_NAME=qwen2.5-coder:7b  # En vez de 14b o 32b
   ```

2. **Reducir contexto**
   ```bash
   # .env
   OLLAMA_CONTEXT_LENGTH=4096  # En vez de 8192
   ```

3. **Verificar cache hit rate**
   ```bash
   curl http://localhost:8000/agent/cache/stats
   ```

---

## 📝 Checklist Pre-Test

- [ ] Ollama corriendo y modelos cargados
- [ ] Redis corriendo (si usa cache)
- [ ] Rate limiting configurado
- [ ] Logs habilitados
- [ ] Monitoreo de recursos activo
- [ ] Backup de datos (opcional)

---

## 📋 Ejecución Paso a Paso

### 1. Preparar entorno

```bash
# Iniciar Redis (si usa cache)
redis-server

# Iniciar RETBOT
python server.py

# En otra terminal, monitorear recursos
watch -n 1 nvidia-smi  # GPU
htop                   # CPU/RAM
```

### 2. Ejecutar load test

```bash
# Test con 7 usuarios
python tests/load_test.py --users 7 --duration 300

# Test con 15 usuarios
python tests/load_test.py --users 15 --duration 300

# Test con 30 usuarios
python tests/load_test.py --users 30 --duration 300
```

### 3. Revisar resultados

```bash
# Ver logs de errores
tail -f logs/server.log | grep ERROR

# Ver estadísticas del cache
curl http://localhost:8000/agent/cache/stats

# Ver health del sistema
curl http://localhost:8000/health/full
```

### 4. Documentar resultados

Crear reporte en `docs/load_test_results.md`:

```markdown
# Load Test Results - 2026-04-26

## Configuración
- Usuarios: 15
- Duración: 5 minutos
- Modelo: qwen2.5-coder:14b
- Cache: Habilitado

## Resultados
- Total Requests: 450
- Success Rate: 99.2%
- Avg Response Time: 3.5s
- 95th Percentile: 8.2s

## Recursos
- CPU Peak: 65%
- RAM Peak: 12GB/32GB
- GPU VRAM: 8GB/24GB

## Conclusiones
✅ Sistema estable con 15 usuarios
✅ Cache hit rate: 35%
✅ Rate limiting funcionó correctamente
```

---

## 🐛 Troubleshooting

### Error: "Connection refused"

```bash
# Verificar servidor corriendo
curl http://localhost:8000/health

# Si no responde, reiniciar
python server.py
```

### Error: "Rate limit exceeded"

```bash
# Aumentar límite temporalmente
# .env
RATE_LIMIT_PER_USER=50  # En vez de 20
```

### Error: "CUDA out of memory"

```bash
# Reducir parallelismo
# .env
OLLAMA_NUM_PARALLEL=2

# O reducir tamaño de modelo
MODEL_NAME=qwen2.5-coder:7b
```

---

## 🔗 Recursos

- [tests/load_test.py](../../tests/load_test.py) - Script de load testing
- [tests/load_test_locust.py](../../tests/load_test_locust.py) - Locust file
- [MAINTENANCE.md](../../MAINTENANCE.md) - Guía de mantenimiento

---

<p align="center">
  <b>¿Problemas?</b> Revisa logs en <code>logs/server.log</code>
</p>
