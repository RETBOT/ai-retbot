# Política de Seguridad

## Versiones Soportadas

RETBOT se desarrolla de forma iterativa con releases frecuentes. Se brinda
soporte de seguridad únicamente para la **última versión publicada**.

| Versión  | Soporte          |
| -------- | ---------------- |
| v2.x     | ✅ Activo        |
| v1.x     | ❌ Sin soporte   |

## Reportar una Vulnerabilidad

Si encuentras una vulnerabilidad de seguridad en RETBOT:

1. **NO** la reportes como issue público (evita zero-days antes de parchear).
2. Envía un correo a **robertoesquiveltr16@gmail.com** con:
   - Cómo reproducirla (pasos, endpoints, payloads)
   - Versión afectada
   - Impacto potencial
   - (Opcional) parche o PoC

**Tiempos de respuesta esperados:**

- Acuse de recibo: **48 horas**
- Actualización de estado: **5 días hábiles**
- Fix o plan de fix: lo antes posible, dependiendo de la severidad

## Buenas Prácticas (lo que RETBOT ya hace)

- **API Keys con hash HMAC-SHA256** — nunca se almacenan en texto plano.
- **La key completa solo se muestra al crearla** — posteriormente solo parcial.
- **Secretos fuera del repo** — configuración vía `.env`, nunca versionada.
- **CI obligatorio** — los PRs a `main` deben pasar `unit` + `integration`.