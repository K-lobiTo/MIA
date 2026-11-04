# Data Model: Historial de chats con usuarios básicos en la Consulta web

Migración aditiva `0009` (revisión anterior: `0008`). Decisiones en [research.md](research.md). Todas las fechas son UTC sin zona, como el resto del esquema (`_now()`).

## Tablas nuevas

### `consulta_users` (modelo `ConsultaUser`)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | texto, clave primaria | UUID. |
| `username` | texto, **único** | Entre 3 y 40 caracteres de `a-z 0-9 . _ -`, siempre en minúsculas (se normaliza al crear y al iniciar sesión). |
| `password_hash` | texto | `scrypt$n$r$p$sal$hash` (research R1). Nunca se devuelve por ninguna ruta ni se escribe en ningún registro. |
| `unit_id` | texto, nulo, clave foránea a `units.id` | Programa del usuario. Nulo: solo el alcance global lo gestiona. No limita lo que puede consultar. |
| `active` | booleano, por defecto verdadero | Desactivado: no inicia sesión ni conserva sesiones; sus conversaciones siguen hasta la retención. |
| `created_by` | texto | Quién lo creó (`Principal.label`). |
| `created_at`, `updated_at` | fecha | `updated_at` cambia con cada edición. |
| `last_login_at` | fecha, nula | Último inicio de sesión correcto. |

### `consulta_sessions` (modelo `ConsultaSession`)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | texto, clave primaria | UUID. |
| `user_id` | clave foránea a `consulta_users.id`, indexada | `ON DELETE CASCADE`. |
| `token_hash` | texto, **único** e indexado | SHA-256 del token; el token en claro nunca se guarda. |
| `created_at` | fecha | Para el tope absoluto `SESSION_MAX_DAYS`. |
| `last_seen_at` | fecha | Se actualiza como máximo una vez por minuto. |
| `expires_at` | fecha, indexada | `ahora + SESSION_HOURS`, se desliza con el uso sin pasar de `created_at + SESSION_MAX_DAYS`. |

Una sesión vale si existe, no venció y su usuario está activo.

### `conversations` (modelo `Conversation`)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | texto, clave primaria | UUID; es lo único que identifica una conversación hacia afuera. |
| `user_id` | clave foránea a `consulta_users.id` | `ON DELETE CASCADE`. Índice compuesto `(user_id, updated_at)`. |
| `title` | texto | Primera pregunta, hasta 60 caracteres en límite de palabra (R9). |
| `created_at` | fecha | |
| `updated_at` | fecha, indexada | Última actividad; define la retención (R8). Se actualiza con cada vuelta guardada. |

### `conversation_turns` (modelo `ConversationTurn`)

| Campo | Tipo | Regla |
|---|---|---|
| `id` | texto, clave primaria | UUID. |
| `conversation_id` | clave foránea a `conversations.id`, indexada | `ON DELETE CASCADE`. Único junto con `position`. |
| `position` | entero | Orden de la vuelta dentro de la conversación (1, 2, 3...). Se asigna al guardar como el siguiente libre. |
| `question` | texto | Hasta 2.000 caracteres (el máximo de una consulta). |
| `answer` | texto | Hasta `CHAT_MAX_ANSWER_CHARS` (20.000); lo que pase se corta. |
| `sources` | texto (JSON) | `[{"domain": "...", "document": "..."}]`, en el orden mostrado. Sin extractos. |
| `mode` | texto | `literal` o `razonamiento`. |
| `no_info` | booleano | La respuesta fue "sin información suficiente". |
| `created_at` | fecha | |

No hay columnas de clave de artefacto, teléfono, costo ni imágenes (FR-025).

## Columna nueva

- `artifacts.require_login`: booleano, no nulo, por defecto falso (`server_default=sa.false()`). Falso: el artefacto responde sin sesión como hoy. Verdadero: `POST /query` sin sesión válida responde 401 `login_required`.

## Ajustes de la instancia (`src/mia/config.py`, variables de entorno)

| Variable | Por defecto | Rango | Qué hace |
|---|---|---|---|
| `CHAT_RETENTION_DAYS` | 90 | 0 a 3650 | Días sin actividad tras los cuales se borra una conversación. **0 apaga el guardado y borra lo guardado** en la próxima limpieza. |
| `CHAT_MAX_TURNS` | 200 | 2 a 2000 | Vueltas por conversación. |
| `CHAT_MAX_CONVERSATIONS` | 100 | 1 a 5000 | Conversaciones por usuario. |
| `CHAT_MAX_ANSWER_CHARS` | 20000 | 1000 a 100000 | Largo máximo guardado de una respuesta. |
| `SESSION_HOURS` | 8 | 1 a 720 | Vigencia deslizante de la sesión. |
| `SESSION_MAX_DAYS` | 7 | 1 a 90 | Tope absoluto de una sesión desde que se creó. |
| `LOGIN_MAX_ATTEMPTS` | 5 | 1 a 100 | Fallos seguidos por usuario antes del bloqueo. |
| `LOGIN_MAX_ATTEMPTS_PER_ORIGIN` | 20 | 1 a 1000 | Fallos seguidos por origen antes del bloqueo. |
| `LOGIN_LOCK_MINUTES` | 15 | 1 a 1440 | Duración del bloqueo y ventana de los fallos. |
| `PASSWORD_MIN_CHARS` | 10 | 8 a 128 | Largo mínimo de una contraseña. |
| `TRUST_FORWARDED_FOR` | `off` | `on` u `off` | Usar el último valor de `X-Forwarded-For` como origen (R4). |

Un valor fuera de rango impide arrancar la API, como el resto de ajustes numéricos (`Field(ge=..., le=...)`).

## Validaciones y transiciones

- **Usuario**: `activo` ⇄ `desactivado` por la administración. Al desactivar, restablecer o cambiar la contraseña se borran sus sesiones (todas, o todas menos la actual al cambiarla uno mismo).
- **Contraseña**: al menos `PASSWORD_MIN_CHARS` caracteres y distinta de espacios vacíos; la generada tiene 16 caracteres.
- **Conversación**: se crea con la primera vuelta guardada (no existen conversaciones vacías); crece vuelta a vuelta hasta `CHAT_MAX_TURNS`; desaparece al borrarla la persona, al vencer la retención o al poner la retención en 0.
- **Aislamiento**: toda lectura, escritura o borrado de una conversación filtra por `user_id`; el identificador de una ajena y uno inexistente son indistinguibles (404).
