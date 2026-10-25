# Contrato: el servicio del bot (`whatsapp/`)

Qué recibe, qué hace con cada mensaje, qué envía y con qué variables se configura. Es un servicio de Python con FastAPI y `httpx` ([research.md](../research.md) R1), en `whatsapp/src/mia_whatsapp/`. No guarda nada en disco ni en base de datos propia: lo persistente (consumo del mes) está en la API y lo transitorio, en memoria ([data-model.md](../data-model.md)).

## Rutas del servicio

| Ruta | Para qué |
|---|---|
| `GET /health` | Chequeo de salud de Railway. 200 `{"status": "ok"}`; no consulta nada externo. |
| `POST /webhooks/kapso` | El aviso de Kapso. Se registra en Kapso con el evento de mensaje de WhatsApp recibido. |

Con una variable obligatoria vacía (`MIA_API_URL`, `BOT_SERVICE_KEY`, `KAPSO_API_KEY`, `KAPSO_WEBHOOK_SECRET`) el servicio no arranca y el mensaje nombra la variable (igual que `RERANK_*` en la API).

## El aviso de Kapso (entrada)

**Firma** (research R7): encabezado `X-Webhook-Signature` con el HMAC-SHA256 del **cuerpo crudo** con `KAPSO_WEBHOOK_SECRET`, en hexadecimal minúscula y sin prefijo, comparado con `hmac.compare_digest`. Sin firma o con firma inválida: **401**, sin procesar nada y sin registrar el cuerpo.

**Evento**: encabezado `X-Webhook-Event`. Solo `whatsapp.message.received` se procesa; cualquier otro recibe 200 y se ignora. Un cuerpo ilegible con firma válida recibe 200 (no se reintenta lo que no se puede leer) y queda en el registro.

**Cuerpo** (los campos que se leen; los demás se ignoran):

```json
{
  "message": {
    "id": "wamid.123",
    "type": "text",
    "from": "16315551181",
    "from_user_id": "US.13491208655302741918",
    "text": { "body": "¿Cuándo es la matrícula?" }
  },
  "conversation": { "id": "conv_123", "phone_number": "16315551181" },
  "phone_number_id": "123456789012345"
}
```

- Con la entrega agrupada, el cuerpo trae `batch: true` y `data: [ … ]` con elementos de esta misma forma: se procesa cada uno.
- `phone_number_id` (o `conversation.phone_number_id`) es el `number_id` de la API.
- Pueden faltar `message.from`, `conversation.phone_number` y `from_user_id` (research R7): el servicio no falla si falta alguno.

**Respuesta**: **200** de inmediato en cuanto la firma y el cuerpo son válidos, antes de consultar a la API (FR-011). El resto corre en una tarea de fondo.

## Qué hace con cada mensaje

Orden fijo; el primero que corta, termina. Cada fila dice qué pasa y qué `resultado` queda en el registro.

| # | Paso | Si ocurre | Qué hace (`resultado`) |
|---|---|---|---|
| 1 | **Duplicado**: `message.id` o `X-Idempotency-Key` ya visto en 24 h | | ignora, sin respuesta (`duplicado`) |
| 2 | **Cuenta** con `POST /bot/messages` y `received: 1` | `unknown_bot` | ignora y registra (`bot_desconocido`) |
| | | `cap_reached` | no responde nada (`tope_mensual`) |
| | | error de la API | no responde y registra (`error_api`) |
| 3 | **Límite por persona**: ya hay 10 mensajes aceptados en la última hora o 30 en el último día | la primera vez del bloqueo | responde el texto de límite (`limite`) |
| | | las siguientes mientras dura | no responde ni procesa (`limite_en_curso`) |
| 4 | **Disponibilidad**: el estado del paso 2 es `disabled` | | responde "no disponible" (`no_disponible`) |
| 5 | **Tipo**: `message.type` no es `text` | | responde "solo texto" (`no_texto`) |
| 6 | **Largo**: el texto supera 500 caracteres | | responde "muy largo" (`muy_largo`) |
| 7 | **Cola**: ya hay 20 consultas esperando | | descarta sin responder (`descartado`) |
| 8 | **Consulta** `POST /bot/query` (con el semáforo de 5) | 200 con `no_info` | responde "sin información" (`sin_informacion`) |
| | | 200 | responde texto, fuentes e imágenes (`respondido`) |
| | | 403, 429, 502, tiempo agotado o error de red | responde "no disponible" (`no_disponible`) |
| 9 | **Envía** la respuesta y cuenta con `POST /bot/messages` y `sent: k` | | |

Notas:
- Un mensaje que no es texto o es muy largo **nunca llega a la API** (sin gasto de modelo, FR-019).
- Todo mensaje que pasa el límite por persona (paso 3) suma a su ventana, también los que no son texto. Los bloqueados no suman (research R8).
- El saludo se antepone, dentro del mismo mensaje, a la **primera respuesta** a esa persona en 24 h, sea cual sea (excepto el aviso de límite). Se marca como saludada cuando el envío tuvo éxito.
- Cada respuesta usa el destino del aviso: `to` con `message.from` o, si falta, `conversation.phone_number`; si tampoco hay, `recipient` con `from_user_id` (research R9). Si no hay ninguno, no se puede responder: se registra (`sin_destino`).

## La respuesta (salida)

1. **Texto**: `[saludo\n\n]` + respuesta convertida al formato de WhatsApp + `\n\nFuentes: a.pdf, b.pdf` (hasta 3 nombres y `y N más`). Si supera 4.000 caracteres se parte en varios mensajes, en orden (research R10). En "sin información", "no disponible", límite, no texto y muy largo se envía solo el texto fijo (con el saludo si toca), sin fuentes ni imágenes.
2. **Imágenes**: tras el texto, hasta `BOT_MAX_IMAGES` (1) de las `images` de la API, en su orden: `link = MIA_API_URL + url`, `caption` recortada a 1.024 caracteres. Un fallo de una imagen no afecta al texto ya enviado: se registra (`imagen_fallida`) y se siguen enviando las demás.
3. Cada texto y cada imagen es un mensaje enviado: el servicio cuenta el total con `sent`.
4. **Nunca** incluye el contacto del programa (FR-017): ni correos, ni teléfonos, ni enlaces propios. Se comprueba en las pruebas con los textos por defecto y, al arrancar, se avisa en el registro si un texto cambiado por variable contiene `@`, `http` o una secuencia de 7 o más dígitos.

## Variables del servicio (`whatsapp/.env.example`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `MIA_API_URL` | (obligatoria) | Dirección pública de la API, con `https://` y sin barra final. También forma los enlaces de las imágenes. |
| `BOT_SERVICE_KEY` | (obligatoria) | Credencial de servicio; el mismo valor que en la API. |
| `KAPSO_API_KEY` | (obligatoria) | Clave de la API de Kapso (`X-API-Key`). |
| `KAPSO_WEBHOOK_SECRET` | (obligatoria) | Secreto con que Kapso firma los avisos. |
| `KAPSO_API_URL` | `https://api.kapso.ai/meta/whatsapp/v24.0` | Base de la API de Kapso (se cambia para el simulador local). |
| `BOT_MAX_MESSAGES_PER_HOUR` | `10` | Mensajes por persona por hora. |
| `BOT_MAX_MESSAGES_PER_DAY` | `30` | Mensajes por persona por día. |
| `BOT_MAX_QUESTION_CHARS` | `500` | Largo máximo de la pregunta. |
| `BOT_MAX_CONCURRENT_QUERIES` | `5` | Consultas simultáneas a la API. |
| `BOT_QUEUE_SIZE` | `20` | Consultas en espera antes de descartar. |
| `BOT_MAX_IMAGES` | `1` | Imágenes por respuesta. |
| `BOT_GREETING_HOURS` | `24` | Horas sin hablar para volver a saludar. |
| `BOT_QUERY_TIMEOUT_S` | `30` | Espera máxima de la consulta a la API. |
| `BOT_KAPSO_RATE_PER_MIN` | `90` | Envíos por minuto a Kapso (el plan gratuito permite 100). |
| `BOT_SEEN_TTL_HOURS` | `24` | Vigencia de los mensajes ya vistos. |
| `BOT_TEXT_GREETING`, `BOT_TEXT_NO_INFO`, `BOT_TEXT_UNAVAILABLE`, `BOT_TEXT_RATE_LIMIT`, `BOT_TEXT_NOT_TEXT`, `BOT_TEXT_TOO_LONG` | los textos de abajo | Los textos fijos (BOT-8: los mismos para todos los bots). |

Los valores numéricos tienen rangos válidos y uno fuera de rango impide arrancar con un mensaje que nombra la variable. El tope mensual de mensajes y el tamaño máximo de imagen **no** están aquí: son de la API (`BOT_MONTHLY_MESSAGE_CAP` y `MAX_IMAGE_MB`).

### Textos por defecto

| Texto | Valor |
|---|---|
| Saludo | "Hola, soy un asistente automático de los posgrados. Respondo con base en documentos oficiales. Tus preguntas pasan por WhatsApp (Meta), Kapso y un proveedor de modelos de lenguaje. Por favor no envíes datos personales." |
| Sin información | "No encontré esa información en los documentos. Prueba con otras palabras o pregunta por otro tema, por ejemplo matrícula, requisitos o plan de estudios." |
| No disponible | "Ahora mismo no puedo responder. Intenta de nuevo más tarde." |
| Límite por persona | "Enviaste muchos mensajes seguidos. Intenta de nuevo en un rato." |
| No es texto | "Por ahora solo entiendo mensajes de texto. Escribe tu pregunta, por favor." |
| Pregunta larga | "Tu mensaje es muy largo. Resúmelo en una o dos frases, por favor." |

El saludo ya dice lo que pide FR-020 (asistente automático, documentos oficiales, quién recibe las preguntas y no enviar datos personales); se amplió respecto del borrador del documento de requerimientos, que no mencionaba a los terceros.

## Registro del servicio (salida estándar, recogida por Railway)

Una línea JSON por mensaje procesado: `{"evento": "mensaje", "resultado": "respondido", "ms": 2310, "mensajes_enviados": 2, "imagenes": 1}`. Nunca incluye teléfonos, identificadores de usuario, el texto de la pregunta ni el de la respuesta; el identificador de mensaje solo con sus primeros 12 caracteres. Cuando un aviso es de un número sin bot registrado (`bot_desconocido`), la línea incluye el `number_id` (es el número de la institución, no un dato de una persona): así se descubre el `phone_number_id` del sandbox para registrarlo en el panel. Los errores de Kapso se registran con su código y un resumen del cuerpo sin datos de la persona.

## Qué no hace

Memoria de conversación, mensajes que no son texto (solo los rechaza con un aviso), mensajes iniciados por el programa, contacto del programa, modo con razonamiento, textos o límites por bot, estadísticas propias del bot, ni nada de la sección 10 del documento de requerimientos.
