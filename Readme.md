# 🤖 AI Coding Assistant API

> API multi-usuario con autenticación, gestión de usuarios y Ollama integrado en Docker
> Para equipos de programación (25-30 desarrolladores)

---

## 📋 Estado del Proyecto

✅ **Implementado:**
- Autenticación JWT con passwords seguras
- Gestión de usuarios (admin)
- Rate limiting
- Logs de auditoría
- Password con expiración
- Chat con Ollama (modelo qwen:0.5b)
- Docker con todo incluido (Python API + Ollama)

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Container                  │
├─────────────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────┐│
│  │ FastAPI API   │  │  opencode-   │  │  Ollama  ││
│  │  :8000     │  │  llm-proxy │  │  :11434 ││
│  │            │  │  :4010    │  │         ││
│  └─────┬──────┘  └─────┬─────┘  └────┬───┘│
│        │               │             │         │
│        │        JWT Auth + Rate Limiting │         │
│        │               │             │         │
│        ▼               ▼             ▼         │
│  ┌─────────────────────────────────────┐│
│  │         SQLite Database             ││
│  │    (users, jobs, audit_logs)       ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                          │
         ┌───────────────┴───────────────┐
         ▼                           ▼
┌──────────────────┐      ┌──────────────────┐
│ OpenCode App     │      │ Programmers     │
│ (Tu PC)       │      │ (25-30 users) │
│               │      │              │
│ → :8000/JWT  │      │ → :8000/JWT  │
└──────────────────┘      └──────────────────┘
```

---

## 📦 Requisitos Previos

- Docker Desktop instalado
- Git (para clonar)
- 4GB RAM mínimo
- 10GB espacio en disco

---

## 🚀 Instalación Completa

### 1. Clonar el proyecto

```bash
git clone <URL_DEL_REPO>
cd ai
```

### 2. Configurar variables de entorno

Editar `.env`:

```bash
# Puerto del servidor
PORT=8000

# Modelo (Ollama local)
MODEL_NAME=qwen:0.5b
MODEL_TYPE=ollama
OLLAMA_URL=http://localhost:11434
OPENCODE_URL=http://localhost:4010

# Seguridad - CAMBIA ESTO
SECRET_KEY=4f8c9b2e7d1a6c3f5e0a9d4b8c2f7e1a9c6d3b5f0a8e2c1d7f4b9a6c3e1d8f2
PASSWORD_EXPIRE_DAYS=30
ADMIN_PASSWORD=TuPasswordAdminMuySeguro123!

# Rate limiting
RATE_LIMIT_PER_MINUTE=10
```

### 3. Build de la imagen Docker

```bash
docker-compose build
```

### 4. Iniciar los servicios

```bash
docker-compose up -d
```

### 5. Verificar que todo funcione

```bash
# Ver estado de contenedores
docker-compose ps

# Ver logs
docker-compose logs -f
```

---

## ▶️ Verificación

### Health check

```bash
curl http://localhost:8000/health
```

**Respuesta esperada:**
```json
{
  "status": "ok",
  "model_type": "ollama",
  "model": "qwen:0.5b",
  "ollama": "connected",
  "opencode": "not_available",
  "models_found": [{"name": "qwen:0.5b", ...}]
}
```

### Login con admin

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"TuPasswordAdminMuySeguro123!"}'
```

**Retorna:**
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_at": "2026-04-20T..."
}
```

---

## 📡 Endpoints

### Auth (Público)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/auth/login` | POST | Login → JWT token |
| `/auth/me` | GET | Info del usuario actual |
| `/auth/password` | PUT | Cambiar mi password |

### Admin (Solo admin)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/users` | POST | Crear usuario |
| `/admin/users` | GET | Listar usuarios |
| `/admin/users/{id}` | PUT | Editar usuario |
| `/admin/users/{id}` | DELETE | Desactivar usuario |
| `/admin/jobs` | GET | Todos los jobs |
| `/admin/audit-logs` | GET | Logs de auditoría |

### Jobs (Usuario)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Crear job de chat |
| `/v1/jobs/{job_id}` | GET | Estado del job |
| `/v1/jobs` | GET | Mis jobs |

### Sistema

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Info del servidor |
| `/health` | GET | Health check |

---

## 🧪 Ejemplos de Uso

### 1. Login

```bash
curl -X POST http://localhost:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"TuPasswordAdminMuySecure123!\"}"
```

Guardar el `access_token` returned.

### 2. Crear usuario programador (solo admin)

```bash
curl -X POST http://localhost:8000/admin/users ^
  -H "Authorization: Bearer TU_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"programador1\",\"password\":\"password123\"}"
```

### 3. Enviar mensaje al chat

```bash
curl -X POST http://localhost:8000/v1/chat/completions ^
  -H "Authorization: Bearer TU_TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Crea un hola mundo en Python\",\"model\":\"qwen:0.5b\"}"
```

**Respuesta:**
```json
{
  "job_id": "...",
  "status": "completed",
  "result": "Aquí viene la respuesta del modelo..."
}
```

---

## 🔧 Comandos Útiles

### Ver contenedores

```bash
docker-compose ps
```

### Ver logs en tiempo real

```bash
docker-compose logs -f
```

### Ver logs de un servicio específico

```bash
docker-compose logs -f api
```

### Reiniciar servicios

```bash
docker-compose restart
```

### Detener servicios

```bash
docker-compose down
```

### Eliminar todo (incluyendo volúmenes)

```bash
docker-compose down -v
```

### Rebuild y reiniciar

```bash
docker-compose down
docker-compose build
docker-compose up -d
```

---

## ⚙�� Configuración

### Variables de entorno (.env)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | 8000 | Puerto del servidor |
| `MODEL_TYPE` | ollama | Tipo: "ollama" o "opencode" |
| `MODEL_NAME` | qwen:0.5b | Modelo a usar |
| `OLLAMA_URL` | http://localhost:11434 | URL de Ollama |
| `OPENCODE_URL` | http://localhost:4010 | URL de OpenCode proxy |
| `SECRET_KEY` | (requerido) | Clave para JWT |
| `PASSWORD_EXPIRE_DAYS` | 30 | Días hasta expirar password |
| `ADMIN_PASSWORD` | (requerido) | Password inicial del admin |
| `RATE_LIMIT_PER_MINUTE` | 10 | Límite de requests |

---

## 🔒 Seguridad

### Características implementadas

1. **JWT Tokens**: Expiran en 7 días
2. **Password hashing**: bcrypt
3. **Password expiración**: 30 días (configurable)
4. **Rate limiting**: 10 req/min por IP
5. **Logs de auditoría**: Todas las acciones de admin
6. **Solo admin puede**: Crear usuarios, cambiar passwords, ver auditoría

---

## ⚠️ Troubleshooting

### Error: "ollama": "no_models"

El modelo no está descargado. Descargarlo:

```bash
docker exec ai-api-1 ollama pull qwen:0.5b
```

### Error: "Password expirada"

```bash
curl -X PUT http://localhost:8000/auth/password ^
  -H "Authorization: Bearer TOKEN" ^
  -H "Content-Type: application/json" ^
  -d "{\"new_password\":\"nueva_password\"}"
```

### Error: "Rate limit exceeded"

Esperar 1 minuto o aumentar `RATE_LIMIT_PER_MINUTE` en `.env`

### Ver logs para debug

```bash
docker-compose logs -f api
```

---

## 🚢 Producción

### Recomendaciones

1. **Cambiar SECRET_KEY**: Clave larga y aleatoria
2. **Cambiar ADMIN_PASSWORD**: Inmediatamente después del primer login
3. **Configurar.redes**: Exponer puerto 8000
4. **Backup de data.db**: Hacer backup regularmente

### Puertos expuesta.

Editar `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"  # Cambiar a "0.0.0.0:8000:8000" para exponer
```

---

## 🤖 OpenCode Desktop - Configuración

### Configurar OpenCode para conectar a tu API

Edita el archivo `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "disabled_providers": [
    "ollama-local"
  ],
  "model": "mi-api/qwen:0.5b",
  "provider": {
    "mi-api": {
      "name": "Mi API Local",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8000"
      },
      "models": {
        "qwen:0.5b": {
          "name": "qwen:0.5b"
        }
      }
    }
  }
}
```

### Para conectar desde otra PC (servidor)

Cambia `localhost` por la IP del servidor:

```json
"baseURL": "http://192.168.1.100:8000"
```

### Endpoints disponibles

| Endpoint | Descripción |
|----------|-------------|
| `/v1/chat` | Chat compatible con OpenAI (sin auth requerida) |
| `/v1/chat/completions` | Chat con autenticación JWT |

### Probar OpenCode

1. Iniciar el contenedor: `docker-compose up -d`
2. Abrir OpenCode Desktop
3. Seleccionar modelo `mi-api/qwen:0.5b`
4. Enviar mensaje: "Hola"

---

## 📄 Licencia

MIT License