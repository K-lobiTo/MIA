# Contrato: rutas de la API para el servicio del bot (`/bot/...`)

Rutas que usa el servicio del bot ([servicio-whatsapp.md](servicio-whatsapp.md)), no el panel ni los artefactos. Detalle de la decisión en [research.md](../research.md) R2 a R4.

## Autenticación

Encabezado `X-Bot-Service-Key` con el valor de `BOT_SERVICE_KEY` de la API (comparación con `hmac.compare_digest`). **401** `Credencial del servicio del bot inválida.` si falta o no coincide, y también si `BOT_SERVICE_KEY` está vacía en la API (las rutas están apagadas, igual que `ADMIN_KEY` vacía). Estas rutas no aceptan `X-Artifact-Key` ni `X-Admin-Key`. CORS: no se agrega el encabezado a `allow_headers`; el servicio no es un navegador.

La credencial solo abre estas dos rutas. Todas las llamadas llevan `number_id`, el `phone_number_id` de Kapso del mensaje (el número de la institución, nunca el de la persona).

## POST /bot/messages

Cuenta mensajes del mes de un bot y dice en qué estado está. El servicio la llama con `received: 1` al llegar un mensaje y con `sent: k` tras enviar `k` mensajes (cada texto y cada imagen cuenta uno).

**Cuerpo**: `{ "number_id": "123456789012345", "received": 1, "sent": 0 }`. `received` y `sent` son enteros de 0 a 100 (por defecto 0); ambos en 0 solo consulta el estado sin sumar.

**200**:

```json
{ "status": "ok", "month": "2026-10", "month_messages": 943, "month_cap": 1800 }
```

| `status` | Cuándo | Qué hace el servicio |
|---|---|---|
| `ok` | el bot está activo, tiene artefacto activo y el consumo del mes (ya con lo sumado) es menor que el tope | sigue |
| `disabled` | el bot está desactivado, sin artefacto, o el artefacto asignado está desactivado | responde "no disponible" |
| `cap_reached` | `received + sent` del mes llegó al tope (`BOT_MONTHLY_MESSAGE_CAP`) | **no responde nada** (FR-024) |
| `unknown_bot` | ningún bot tiene ese `number_id` (no se suma nada) | ignora el mensaje y lo deja en el registro |

Si coinciden `disabled` y `cap_reached`, gana `cap_reached` (no se gasta ni un mensaje más). Con `unknown_bot`, `month_messages` y `month_cap` son `null`. Un fallo de la base responde 5xx y el servicio sigue sin responder (no hay certeza del tope).

**Atomicidad**: el incremento es una sola sentencia `UPDATE bot_message_counts SET received = received + :r, sent = sent + :s WHERE bot_id = :id AND month = :m`; si no actualiza ninguna fila, inserta la fila del mes y, si otro proceso la insertó a la vez (conflicto de clave), repite el `UPDATE`.

## POST /bot/query

Consulta con el artefacto asignado al bot, siempre en **modo literal**. Es la misma consulta que `POST /query` (research R3): mismos rechazos, topes diarios, búsqueda, citas y registro en Uso (con el artefacto asignado y sin ningún teléfono).

**Cuerpo**: `{ "number_id": "123456789012345", "question": "¿Cuándo es la matrícula?" }`. `question` de 1 a 2.000 caracteres (el bot limita a 500 antes de llamar).

La API calcula los dominios: son los que el artefacto cubre en ese momento (`allowed_domain_ids`, que ya devuelve vacío si el artefacto está desactivado).

**200**: un `QueryResponse` de siempre, con el campo `images` (ver [imagenes-api.md](imagenes-api.md)):

```json
{
  "id": "…",
  "answer": "La matrícula del segundo semestre es del 3 al 7 de agosto…",
  "sources": [{ "domain": "Admisión", "document": "horario_matricula.pdf", "excerpt": "…" }],
  "mode": "literal",
  "latency_ms": 1730,
  "no_info": false,
  "images": [{ "url": "/media/Qn3x…", "caption": "Horario de matrícula", "document": "horario_matricula.pdf" }]
}
```

| Código | Cuándo | Qué hace el servicio |
|---|---|---|
| 200 con `no_info: true` | los documentos no responden, o el artefacto no cubre ningún dominio | responde "sin información" (con su texto, sin contacto ni imágenes) |
| 403 | bot desactivado, sin artefacto, artefacto desactivado, o modo literal no permitido por el artefacto (el rechazo se registra en Uso como siempre cuando hay artefacto) | "no disponible" |
| 404 `Bot no encontrado.` | `number_id` sin bot | ignora y registra |
| 429 | tope diario del artefacto o de toda la API (con `Retry-After`) | "no disponible", sin reintentar |
| 502 | falla del proveedor de modelos | "no disponible" |
| 401 | credencial inválida | registra el error (configuración) |

Un artefacto sin dominios cubiertos (por ejemplo, una unidad sin dominios) responde 200 con `no_info: true`, sin buscar; la consulta queda en el registro de Uso como `no_info`.

## Qué no cambia

`POST /query`, `POST /query/{id}/feedback` y todas las rutas de los artefactos se comportan igual, salvo el campo nuevo `images` en la respuesta de `POST /query` (siempre presente, vacío sin imágenes).
