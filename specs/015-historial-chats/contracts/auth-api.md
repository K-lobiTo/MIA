# Contrato: inicio y cierre de sesión (`/auth`)

Rutas que usa la Consulta. Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R1 a R4. No exigen la clave del artefacto (el usuario se identifica con su usuario y contraseña), pero **consultar** sigue exigiéndola. Todas usan métodos de `CORS_ALLOW_METHODS` y el encabezado `X-Session-Token` está en los permitidos.

## `POST /auth/login`

Cuerpo: `{ "username": "ana.perez", "password": "..." }`. El nombre se normaliza a minúsculas.

| Resultado | Cuándo | Cuerpo |
|---|---|---|
| **200** | Usuario activo y contraseña correcta | `{ "token": "mias_...", "expires_at": "2026-11-04T18:00:00Z", "user": { "username": "ana.perez" } }` |
| **401** | Usuario inexistente, desactivado o contraseña incorrecta | `{ "detail": "Usuario o contraseña incorrectos.", "code": "invalid_credentials" }`; el mismo mensaje y un tiempo comparable en los tres casos. |
| **429** | Bloqueo por intentos fallidos (por usuario o por origen), **aunque la contraseña fuera correcta** | `{ "detail": "Demasiados intentos. Espera 15 minutos...", "code": "too_many_attempts" }` y el encabezado `Retry-After` en segundos. |
| **422** | Cuerpo mal formado (falta un campo, textos vacíos) | El de siempre. |

El token se muestra una sola vez en esta respuesta y nunca se guarda en claro. Un inicio correcto limpia el contador de fallos del usuario y actualiza `last_login_at`.

## `POST /auth/logout`

Encabezado `X-Session-Token`. **204** y la sesión deja de valer de inmediato. Con un token inválido o vencido también responde 204 (cerrar una sesión ya cerrada no es un error).

## `GET /auth/me`

Encabezado `X-Session-Token`. **200**: `{ "username": "ana.perez", "expires_at": "..." }`. Sin token o con uno inválido o vencido: **401** `{ "code": "session_invalid" }`. La Consulta lo usa al cargar para saber si la sesión guardada sigue valiendo.

## `POST /auth/password`

Encabezado `X-Session-Token`. Cuerpo `{ "current_password": "...", "new_password": "..." }`.

| Resultado | Cuándo |
|---|---|
| **204** | Cambia la contraseña y cierra **todas las demás** sesiones del usuario (la actual sigue). |
| **401** `invalid_credentials` | `current_password` incorrecta; cuenta como intento fallido del usuario. |
| **422** | `new_password` más corta que `PASSWORD_MIN_CHARS` o igual a la actual. |
| **401** `session_invalid` | Sin sesión válida. |

## Códigos de error de sesión (para todas las rutas que usan la sesión)

| Código | Estado | Significado |
|---|---|---|
| `session_invalid` | 401 | El token falta, no existe, venció, o su usuario está desactivado. La Consulta limpia la sesión guardada y vuelve a pedir el inicio de sesión (no toca la clave del artefacto). |
| `login_required` | 401 | El artefacto exige sesión y la consulta no trajo ninguna (ver [query-con-sesion.md](query-con-sesion.md)). |

Ninguna respuesta de esta familia incluye contraseñas, hashes ni tokens salvo el `token` de `login`. En el registro del servidor solo quedan resultados de los intentos (éxito, fallo, bloqueado) con el nombre normalizado y el origen recortado; nunca la contraseña ni el token.
