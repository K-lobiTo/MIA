# Contrato: `POST /bot/query` con aclaración de programa

Cambio de `POST /bot/query` (feature 011, [bot-servicio-api.md](../../011-bot-whatsapp-kapso/contracts/bot-servicio-api.md)). Sigue exigiendo la credencial de servicio y el `number_id`; el request **no cambia**. Detalle de los datos en [data-model.md](../data-model.md) y decisiones en [research.md](../research.md) R2 a R4.

## Respuesta

200 con un `BotQueryResponse`: todo lo de `QueryResponse` más:

```json
{ "clarify": ["Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"], "programs": [] }
```

| Situación | `no_info` | `clarify` | `programs` | `answer`, `sources`, `images` |
|---|---|---|---|---|
| Respuesta con fuentes | falso | `[]` | los programas de las fuentes (sin repetir; `[]` si ningún documento tiene programa) | los de hoy |
| Sin información | verdadero | `[]` | `[]` | el texto de hoy, sin fuentes ni imágenes |
| **Aclaración** | verdadero | 2 a `BOT_CLARIFY_MAX_PROGRAMS` programas, por mejor puntaje | `[]` | el texto de "sin información", sin fuentes ni imágenes |

Un cliente que no conozca `clarify` ve una respuesta "sin información", que es lo que veía antes.

**Con `BOT_CLARIFY=off` la respuesta es la de antes**: `clarify` y `programs` siempre vacías, sin búsqueda extra ni lectura de títulos (la función entera queda inerte; el servicio, sin programas, no tiene programa que recordar). `programs` solo se llena con `BOT_CLARIFY=on`.

## Cuándo hay aclaración

Solo si todo esto es cierto:
1. `BOT_CLARIFY=on`.
2. La búsqueda de la pregunta (vectorial, híbrida y con pregunta limpia si están encendidas, como hoy) **no dejó ningún fragmento** sobre el umbral (`QUERY_SIMILARITY_THRESHOLD`): el camino que hoy termina en "sin información" sin pasar por el modelo.
3. Una búsqueda vectorial adicional con el mismo embedding (`BOT_CLARIFY_CANDIDATES` fragmentos) deja, con puntaje **mayor o igual a `BOT_CLARIFY_MIN_SIMILARITY`** y con **evidencia léxica de la pregunta** (alguna palabra con contenido de la pregunta, de 4 letras o más y sin interrogativos ni palabras genéricas, aparece al inicio de una palabra del fragmento), fragmentos de documentos de **dos o más programas distintos** (por clave, sin contar los documentos sin programa). Una pregunta sin palabras con contenido no pide aclaración.

Si no, la respuesta es la de hoy. La respuesta "sin información" que da el modelo después de recibir fragmentos relevantes **no** produce aclaración.

## Lo que no cambia

- Rechazos y códigos: 404 (bot desconocido), 403 (bot o artefacto desactivado, sin artefacto, modo o dominios no permitidos) y 429 (tope diario) iguales; también el artefacto sin dominios (`_no_domains_response`).
- El registro de Uso: una aclaración queda como una consulta `no_info`, como hoy; no hay resultado nuevo.
- `POST /query` y los demás artefactos: misma forma de respuesta y mismo comportamiento, sin búsqueda extra.
- Costo: la búsqueda adicional y la lectura de los títulos no llaman a ningún modelo de lenguaje. La consulta del reintento del servicio es una consulta normal.
