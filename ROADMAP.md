# 🚀 RETBOT - Roadmap de Mejoras

Plan de mejoras priorizadas para el sistema de 7-30 programadores.

---

## 📊 Resumen Ejecutivo

| Prioridad | Mejora | Utilidad | Complejidad | Tiempo |
|----------|-------|---------|-------------|--------|
| 🔴 P0 | Rate limiting por usuario | Crítica | Baja | 1-2h |
| 🟠 P1 | Cache de respuestas | Alta | Media | 2-3h |
| 🟠 P1 | Health checks avanzados | Alta | Baja | 1h |
| 🟡 P2 | Métricas con Prometheus | Media | Media | 3-4h |
| 🟡 P2 | Load testing | Media | Media | 2-3h |
| 🟢 P3 | Web UI | Media | Alta | 4-6h |
| 🟢 P3 | Múltiples modelos | Baja | Media | 2-3h |
| ⚪ P4 | Logging estructurado | Baja | Baja | 1h |

---

## 🔴 P0: Rate Limiting por Usuario

### Por qué es crítico
Sin rate limiting, un solo usuario puede acaparar todo el servidor y dejar sin servicio a los demás.

### Qué hace falta
- [ ] Rate limit por API key/JWT token
- [ ] Rate limit global por IP
- [ ] Configurable en `.env`

### Implementación sugerida

```python
# core/rate_limit.py
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Por usuario
@router.post("/chat/completions")
@limiter.limit("10/minute")  # 10 requests por minuto
async def chat(request: Request):
    ...
```

### Archivos a modificar
- `core/config.py` - Agregar `RATE_LIMIT_PER_USER`
- Nuevo `core/rate_limit.py` - Rate limiter
- `api/streaming.py` - Aplicar rate limit
- `api/jobs.py` - Aplicar rate limit

### Tiempo estimado: **1-2 horas**

---

## 🟠 P1: Cache de Respuestas (Redis)

### Por qué es útil
Si varios usuarios preguntan cosas similares, el sistema puede reuse respuestas sin llamar al LLM nuevamente.

###Qué hace falta
- [ ] Instalar Redis (ya está en config)
- [ ] Cache con TTL personalizable
- [ ] Cache key = hash(mensajes + modelo)
- [ ] Invalidación manual

### Implementación sugerida

```python
# core/cache.py
import redis
import hashlib
import json

redis_client = redis.from_url(settings.REDIS_URL)

def cache_key(messages: list, model: str) -> str:
    content = json.dumps(messages, sort_keys=True) + model
    return hashlib.md5(content.encode()).hexdigest()

def get_cached_response(key: str) -> str | None:
    return redis_client.get(f"cache:{key}")

def set_cached_response(key: str, response: str, ttl: int = 3600):
    redis_client.setex(f"cache:{key}", ttl, response)
```

### Archivos a modificar
- `.env` - Descomentar `REDIS_URL`
- Nuevo `core/cache.py` - Lógica de cache
- `api/jobs.py` - Usar cache

### Tiempo estimado: **2-3 horas**

---

## 🟠 P1: Health Checks Avanzados

### Por qué es útil
El `/health` actual solo verifica que el servidor esté vivo. Necesitamos másdetails.

###Qué hace falta
- [ ] Verificar Ollama connectivity
- [ ] Verificar Redis (si está configurado)
- [ ] Verificar base de datos
- [ ] Mostrar modelo actual y memoria
- [ ] Mostrar uptime

### Implementación sugerida

```python
@router.get("/health")
async def health_check():
    # Verificar Ollama
    ollama_ok = await check_ollama()
    
    # Verificar DB
    db_ok = await check_database()
    
    # Verificar Redis (si está configurado)
    redis_ok = await check_redis() if settings.REDIS_URL else None
    
    return {
        "status": "healthy" if ollama_ok and db_ok else "degraded",
        "services": {
            "ollama": "ok" if ollama_ok else "error",
            "database": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "not_configured"
        },
        "model": settings.MODEL_NAME,
        "uptime": uptime_seconds
    }
```

### Archivos a modificar
- `api/admin.py` - Mejorar `/health` endpoint

### Tiempo estimado: **1 hora**

---

## 🟡 P2: Métricas con Prometheus

### Por qué es útil
Saber количетво de requests, latencia, errores para optimizar.

###Qué hace falta
- [ ] Instalar `prometheus-client`
- [ ] Métricas: requests_total, requests_in_progress, latency_seconds, errors_total
- [ ] Endpoint `/metrics`
- [ ] Integración con Grafana (opcional)

### Implementación sugerida

```python
from prometheus_client import Counter, Histogram, generate_latest

requests_total = Counter('retbot_requests_total', 'Total requests', ['endpoint', 'status'])
latency_seconds = Histogram('retbot_latency_seconds', 'Request latency', ['endpoint'])

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")

# En cada endpoint
@router.post("/chat/completions")
async def chat(...):
    with latency_seconds.labels(endpoint="chat").time():
        try:
            # lógica
            requests_total.labels(endpoint="chat", status="success").inc()
        except Exception:
            requests_total.labels(endpoint="chat", status="error").inc()
```

### Archivos a modificar
- `requirements.txt` - Agregar `prometheus-client`
- Nuevo `core/metrics.py` - Métricas
- `api/admin.py` - Endpoint `/metrics`
- Todos los endpoints - Agregar métricas

### Tiempo estimado: **3-4 horas**

---

## 🟡 P2: Load Testing

### Por qué es útil
Simular 7-30 usuarios para ver el límite real del sistema.

###Qué hace falta
- [ ] Script de load testing
- [ ] Métricas: throughput, latency, errors
- [ ] Reporte de resultados

### Herramientas recomendadas

```bash
# Opción 1: locust
pip install locust
locust -f tests/load_test.py --host=http://localhost:8000

# Opción 2: k6
pip install k6
k6 run tests/k6_test.js
```

### Script de ejemplo (Python)

```python
# tests/load_test.py
import asyncio
import httpx
import time
from concurrent.futures import ThreadPoolExecutor

URL = "http://localhost:8000/v1/chat/completions"
HEADERS = {"X-API-Key": "demo_key_123"}

async def make_request(i):
    async with httpx.AsyncClient(timeout=300) as client:
        start = time.time()
        try:
            response = await client.post(
                URL,
                json={"messages": [{"role": "user", "content": f"Hola {i}"}]},
                headers=HEADERS
            )
            elapsed = time.time() - start
            return {"success": response.status_code == 200, "time": elapsed}
        except Exception as e:
            return {"success": False, "time": time.time() - start, "error": str(e)}

async def load_test(users=10, duration=60):
    tasks = []
    start_time = time.time()
    
    while time.time() - start_time < duration:
        for i in range(users):
            tasks.append(asyncio.create_task(make_request(i)))
        await asyncio.sleep(1)
    
    results = await asyncio.gather(*tasks)
    
    # Reporte
    total = len(results)
    successes = sum(1 for r in results if r["success"])
    errors = total - successes
    avg_time = sum(r["time"] for r in results) / total
    
    print(f"Total requests: {total}")
    print(f"Success: {successes} ({successes/total*100:.1f}%)")
    print(f"Errors: {errors} ({errors/total*100:.1f}%)")
    print(f"Avg time: {avg_time:.2f}s")
```

### Tiempo estimado: **2-3 horas**

---

## 🟢 P3: Web UI

### Por qué es útil
Panel web para administración sin usar CLI ni API.

###Qué hace falta
- [ ] Frontend (HTML/JS simple o React)
- [ ] Endpoints JSON
- [ ] Autenticación web

### Alternativas
1. **Minimal**: HTML estático con fetch al API (1-2h)
2. **Moderado**: Flask/Django admin (3-4h)
3. **Completo**: React + API (6+h)

### Para consideración futura

### Tiempo estimado: **4-6 horas** (si se hace completo)

---

## 🟢 P3: Múltiples Modelos

### Por qué es útil
Permitir que diferentes usuarios usen diferentes modelos.

###Qué hace falta
- [ ] Selector de modelo en request
- [ ] Cache de múltiples modelos en VRAM
- [ ] Métricas por modelo

### Implementación sugerida

```python
class ChatRequest(BaseModel):
    model: Optional[str] = settings.MODEL_NAME  # Por defecto
```

### Tiempo estimado: **2-3 horas**

---

## ⚪ P4: Logging Estructurado

### Por qué es útil
JSON logs para producción (Splunk, Datadog, etc.).

###Qué hace falta
- [ ] Python `logging` formateado como JSON
- [ ] Log levels correctos
- [ ] Correlation IDs

### Tiempo estimado: **1 hora**

---

## 📋 Plan de Ejecución Sugerido

### Fase 1: Estabilidad (Esta semana)
| Orden | Mejora | Tiempo |
|------|-------|--------|
| 1 | Rate limiting por usuario | 1-2h |
| 2 | Health checks avanzados | 1h |

### Fase 2: Rendimiento (Próxima semana)
| Orden | Mejora | Tiempo |
|------|-------|--------|
| 3 | Cache de respuestas | 2-3h |
| 4 | Load testing | 2-3h |

### Fase 3: Observabilidad (2 semanas)
| Orden | Mejora | Tiempo |
|------|-------|--------|
| 5 | Métricas Prometheus | 3-4h |

### Fase 4: Mejoras (Cuando有时间)
6. Web UI (4-6h)
7. Múltiples modelos (2-3h)
8. Logging estructurado (1h)

---

## 🎯 Prioridad para Tu Caso

Dado que tienes 7-30 programadores:

1. **AHORA → Rate limiting** - Sin esto, un usuario puede tumbar el servidor
2. **Después → Health checks** - Para monitoreo
3. **Después → Cache** - Para reducir costos GPU
4. **Después → Load testing** - Para validar el límite

¿Quieres que начаем con **Rate limiting**? Es lo más crítico y se hace en 1-2 horas.

---

## 📝 Pendiente por Completar

- [x] 🔴 P0: Rate limiting por usuario ✅ **COMPLETADO (2026-04-26)**
- [x] 🟠 P1: Health checks avanzados ✅ **COMPLETADO (2026-04-26)**
- [x] 🟠 P1: Cache de respuestas (Redis) ✅ **COMPLETADO (2026-04-26)**
- [x] 🟡 P2: Load testing ✅ **COMPLETADO (2026-04-26)**
- [x] ⚪ P4: Logging estructurado ✅ **COMPLETADO (2026-04-26)**
- [x] 🟢 P3: Múltiples modelos ✅ **COMPLETADO (2026-04-26)**
- [ ] 🟢 P3: Web UI

<small>Última actualización: 2026-04-26</small>