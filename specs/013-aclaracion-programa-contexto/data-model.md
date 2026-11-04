# Data Model: Aclaración de programa y contexto de conversación

Esta feature **no agrega tablas, columnas ni migraciones** y no toca el panel. Define dos modelos de respuesta de la API (solo `/bot/query`) y una estructura en memoria del servicio del bot. Decisiones en [research.md](research.md).

## En la API (sin base de datos)

### Programa de un documento (calculado, no almacenado)

| Dato | Cómo se obtiene |
|---|---|
| Etiqueta | Texto antes de los dos puntos de la primera línea del fragmento 0 del documento, de 3 a 120 caracteres. Sin ella el documento no tiene programa. |
| Nombre natural | Si la etiqueta está toda en mayúsculas: mayúscula inicial por palabra con las palabras de enlace en minúscula (`en`, `de`, `del`, `la`, `el`, `los`, `las`, `y`, `e`, `con`, `para`, `a`, `por`; la primera palabra siempre con mayúscula). Si trae minúsculas: tal cual. |
| Clave de comparación | Minúsculas, sin tildes, sin signos de puntuación y sin las palabras vacías `maestria`, `en`, `de`, `del`, `la`, `el`, `y`, `los`, `las`. Dos documentos con la misma clave son del mismo programa. |
| Caché | Diccionario `document_id -> (nombre natural, clave) o None`, por proceso. Se llena la primera vez que se necesita (camino de "sin información" o fuentes de una respuesta del bot). Sin vencimiento: el id de un documento no se reutiliza. |

Ejemplos con los documentos actuales:

| Primera línea | Nombre natural | Clave |
|---|---|---|
| `MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN` | Maestría en Ciberseguridad | `ciberseguridad` |
| `MAESTRÍA EN ANALÍTICA DE NEGOCIO (BUSINESS ANALYTICS): PLAN DE ESTUDIOS` | Maestría en Analítica de Negocio (Business Analytics) | `analitica negocio business analytics` |
| `Requisitos del curso` (sin dos puntos) | sin programa | |

### `BotQueryResponse` (solo `POST /bot/query`)

Extiende `QueryResponse` (id, answer, sources, mode, latency_ms, no_info, images) con:

| Campo | Tipo | Valor |
|---|---|---|
| `clarify` | lista de texto | Nombres naturales de los programas candidatos, por mejor puntaje, hasta `BOT_CLARIFY_MAX_PROGRAMS`. Vacía salvo cuando la respuesta es una aclaración (en ese caso también `no_info` es verdadero y `answer` es el texto de "sin información"). |
| `programs` | lista de texto | Nombres naturales de los programas de los documentos citados en la respuesta, sin repetir. Vacía si no hay respuesta o los documentos no tienen programa. |

`POST /query` sigue devolviendo `QueryResponse` sin estos campos.

### Configuración de la API

| Variable | Defecto | Rango | Para qué |
|---|---|---|---|
| `BOT_CLARIFY` | `off` | `on` / `off` (inválido: apagado y avisa una vez) | Enciende la búsqueda de decisión y la aclaración del bot. |
| `BOT_CLARIFY_MIN_SIMILARITY` | `0.70` (calibrado, R9) | 0,0 a 1,0 | Piso del puntaje de un fragmento para contar su programa como candidato (menor que `QUERY_SIMILARITY_THRESHOLD`). Solo es un piso: lo que discrimina es la evidencia léxica de la pregunta en el fragmento. |
| `BOT_CLARIFY_CANDIDATES` | `30` | 5 a 100 | Fragmentos que mira la búsqueda de decisión (más que los de la consulta, para que entren los de cada programa). |
| `BOT_CLARIFY_MAX_PROGRAMS` | `5` | 2 a 10 | Máximo de programas que se listan. |

## En el servicio del bot (memoria, sin base)

### Contexto de conversación (`ConversationStore`)

Un `OrderedDict` por clave de persona (`person_key`, el hash que ya usa el servicio; sin clave no hay contexto) con tope de personas y vencimiento por inactividad, como `_greeted` y `_people`.

| Campo de una conversación | Detalle |
|---|---|
| `turns` | `deque(maxlen=BOT_CONTEXT_MESSAGES)` (4) de turnos, en orden. |
| `last_seen` | Instante del último mensaje; la conversación vence a los `BOT_CONTEXT_MINUTES` (30) de inactividad. |

| Turno | Campos |
|---|---|
| De la persona | `role="person"`, `text` (la pregunta, recortada a `BOT_MAX_QUESTION_CHARS`). |
| Del bot | `role="bot"`, `kind` en {`answer`, `clarify`, `no_info`}, `programs` (programas de las fuentes, para `answer`) y `candidates` (programas listados, para `clarify`). **No** guarda el texto de la respuesta. |

Valores derivados (no se guardan aparte):

| Derivado | Regla |
|---|---|
| Aclaración pendiente | El último turno es del bot con `kind="clarify"` y el anterior es de la persona: pregunta original y candidatos. |
| Programa recordado | El `programs[0]` del último turno del bot con `kind="answer"` y exactamente un programa, dentro de la ventana. |

Reglas de la estructura: nunca más de `BOT_CONTEXT_MESSAGES` turnos por persona; nunca más de `BOT_CONTEXT_MAX_PEOPLE` conversaciones (salen primero las más viejas); `cleanup()` retira las vencidas; nada se escribe en la base, en el registro de Uso ni en los registros del servicio.

### Configuración del servicio

| Variable | Defecto | Rango | Para qué |
|---|---|---|---|
| `BOT_CONTEXT_MESSAGES` | `4` | 2 a 10 | Turnos que se recuerdan por persona. |
| `BOT_CONTEXT_MINUTES` | `30` | 1 a 1440 | Inactividad tras la cual se olvida la conversación. |
| `BOT_CONTEXT_MAX_PEOPLE` | `5000` | 100 a 100000 | Conversaciones en memoria como máximo. |
| `BOT_TEXT_CLARIFY` | texto por defecto | sin contacto | Texto de la aclaración; `{programs}` se reemplaza por la lista numerada de candidatos. |

Texto por defecto: `¿A qué programa te refieres? Tengo información de:\n{programs}\nResponde con el nombre del programa o su número.` (sin correos, teléfonos ni enlaces: lo verifica la prueba que ya existe de textos por defecto).
