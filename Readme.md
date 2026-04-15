# 🤖 AI Coding Assistant API - RETBOT

> API multi-usuario con autenticación JWT, Ollama para inferencia local y streaming SSE
> Para equipos de programación que usan OpenCode o cualquier cliente compatible con OpenAI

---

## 🎯 ¿Qué es RETBOT?

RETBot es tu asistente de programación local con:
- **Autenticación JWT** - cada usuario tiene su propio token
- **Streaming en tiempo real** - respuestas mientras se generan
- **Multi-usuario** - cada quien tiene sus propios Jobs y auditoría
- **Local y privado** - todo corre en tu PC/servidor
- **Compatible OpenAI** - funciona con OpenCode, curl, Python, etc.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────┐
│              Tu Servidor / PC               │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐       ┌──────────────┐    │
│  │   FastAPI    │─────> │      Ollama  │    │
│  │    :8000     │       │    :11434    │    │
│  └──────┬───────┘       └──────────────┘    │
│         │                                   │
│   JWT Auth + Rate Limiting                  │
│         │                                   │
│         V                                   │
│  ┌──────────────────────────────┐           │
│  │       SQLite Database        │           │
│  │ (users, jobs, audit_logs)    │           │
│  └──────────────┬───────────────┘           │
└─────────────────┼───────────────────────────┘
                  │
        ┌─────────┴─────────┐
        V                   V
┌──────────────────┐   ┌──────────────────┐
│   OpenCode App   │   │   Programmers    │
│     (Tu PC)      │   │   (tu equipo)    │
│                  │   │                  │
│   → :8000/JWT    │   │   → :8000/JWT    │
└──────────────────┘   └──────────────────┘
```

> **Nota:** También disponible en Docker (ver sección Docker)

---

## 💻 Requisitos

### Hardware mínimo

| Componente | Mínimo | Recomendado |
|-----------|-------|------------|
| RAM | 4GB | 8GB+ |
| VRAM (GPU) | - | 4GB+ para modelos grandes |
| Disco | 10GB | 20GB+ |

### Software

- Python 3.10+
- Ollama instalado (https://ollama.com)
- Git (para clonar)

### 🎮 ¿Qué modelo me funciona?

Consultá **[Can I Run It?](https://www.canirun.ai/)** para ver qué modelo se adapta a tu hardware.

Modelos recomendados para inicio:
- **tinyllama** (~1GB) -Para probar
- **qwen2.5:0.5b** (~400MB) - Balanceado
- **phi3:3.8b** (~2GB) - Mejor calidad
- **qwen2.5:3b** (~2GB) -Muy buena calidad

---

## 🚀 Instalación Rápida (Sin Docker)

### 1. Clonar y entrar

```bash
git clone <URL_DEL_REPO>
cd ai
```

### 2.Crear entorno virtual

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar .env

```bash
# .env
ADMIN_PASSWORD=TuPasswordMuySegura123!
```

### 5. Crear usuario admin

El usuario **admin** se crea automáticamente la primera vez que iniciás la API usando el valor de `ADMIN_PASSWORD` en `.env`.

```bash
# username: admin
# password: TuPasswordMuySegura123!
```

### 6. Ver modelos disponibles

```bash
curl http://localhost:8000/v1/models
```

### 7. Iniciar Ollama

```bash
ollama serve
ollama pull qwen2.5:0.5b
```

### 8. Iniciar la API

```bash
python server.py
```

---

## 📡 Endpoints

### Auth

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/auth/login` | POST | Login → JWT token |
| `/auth/me` | GET | Info del usuario |
| `/auth/password` | PUT | Cambiar mi password |

### Chat (Protegido)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat con streaming |
| `/v1/models` | GET | Modelos disponibles |

### Admin (Solo admin)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/admin/users` | GET | Listar usuarios |
| `/admin/users` | POST | Crear usuario |
| `/admin/jobs` | GET | Todos los jobs |

### Sistema

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/` | GET | Info del servidor |

---

## 🧪 Cómo Usar

### 1. Login (obtener token)

```bash
curl -X POST http://localhost:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"TuPasswordMuySegura123!\"}"
```

**Retorna:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "expires_at": "2026-04-21T..."
}
```

### 2. Usar el chat

```bash
curl -X POST http://localhost:8000/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -H "Authorization: Bearer TU_TOKEN" ^
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Crea un hola mundo en Python\"}],\"stream\":true}"
```

---

## 🤖 Configurar OpenCode Desktop

### Opción 1:Archivo local del proyecto

Editá `opencode.json` en la raíz del proyecto:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "retbot/qwen2.5:0.5b",
  "provider": {
    "retbot": {
      "name": "Api RETBOT",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8000/v1",
        "apiKey": "eyJhbG...TU_TOKEN..."
      },
      "models": {
        "qwen2.5:0.5b": {
          "name": "qwen2.5:0.5b"
        }
      }
    }
  },
  "agent": {
    "gentleman": {
      "prompt": "{file:./AGENTS.md}",
      "tools": {
        "edit": true,
        "write": true,
        "bash": true,
        "read": true
      },
      "description": "Senior Architect mentor - helpful first, challenging when it matters",
      "mode": "primary"
    }
  }
}
```

### Opción 2: Configuración global

Editá `C:\Users\<TU_USUARIO>\.config\opencode\opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "retbot/qwen2.5:0.5b",
  "provider": {
    "retbot": {
      "name": "Api RETBOT",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://192.168.1.X:8000/v1",
        "apiKey": "eyJhbG...TU_TOKEN..."
      }
    }
  }
}
```

### ¿Dónde consigo el token?

1. Hacé login: `POST /auth/login`
2. Copiá el `access_token` retornado
3. Pegalo en `apiKey` del opencode.json

⚠️ **El token dura 7 días**. Cuando expire, hacés login de nuevo y actualizás.

---

## ��� Recomendamos Gentle AI

Para una experiencia de AI Coding más completa, te recomendamos:

### **[Gentle AI](https://github.com/Gentleman-Programming/gentle-ai)**

Gentle AI es un framework de desarrollo de AI Agents con:
- **Arquitectura limpia** - patrones de diseño profesionales
- **Skills personalizables** - cada fase del desarrollo
- **Memoria persistente** - remembers decisiones del proyecto
- **Integración nativa** con OpenCode

```
# Instalar Gentle AI
npm install -g gentle-ai

# Iniciar proyecto
gentle init
```

---

## ⚙️ Configuración

### Variables de entorno (.env)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | 8000 | Puerto del servidor |
| `MODEL_NAME` | qwen2.5:0.5b | Modelo a usar |
| `MODEL_TYPE` | ollama | Tipo de proveedor |
| `OLLAMA_URL` | http://localhost:11434 | URL de Ollama |
| `SECRET_KEY` | (requerido) | Clave JWT |
| `PASSWORD_EXPIRE_DAYS` | 30 | Expiración password |
| `ADMIN_PASSWORD` | (requerido) | Password admin |
| `RATE_LIMIT_PER_MINUTE` | 10 | Límite req/min |
| `API_KEY` | demo_key_123 | API key para testing |

---

## 🔒 Seguridad

1. **JWT Tokens** - Expiran en 7 días
2. **Password hashing** - bcrypt
3. **Password expiración** - 30 días
4. **Rate limiting** - 10 req/min por IP
5. **Logs de auditoría** - Todas las acciones

---

## 🐛 Troubleshooting

### Error: "Usuario no encontrado"

El usuario no existe en la DB. Asegurate de:
1.Tener usuarios creados (admin depuis `/auth/login`)
2.El token no esté vencido

### Error: "ollama": "disconnected"

Ollama no está corriendo:

```bash
ollama serve
ollama pull qwen2.5:0.5b
```

### Error: "Rate limit exceeded"

Esperar 1 minuto o aumentar `RATE_LIMIT_PER_MINUTE` en `.env`

---

## 📄 Licencia

MIT License

---

## 🔗 Links Útiles

- [Ollama](https://ollama.com) - Modelos locales
- [Can I Run It?](https://www.canirun.ai/) - Compatibilidad de modelos
- [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) - Framework de AI Agents
- [OpenCode](https://opencode.ai) - AI Coding Assistant