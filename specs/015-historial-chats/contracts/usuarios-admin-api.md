# Contrato: administración de usuarios de la Consulta (`/consulta-users`) y módulo del panel

Rutas que usa el panel (credenciales de administración como el resto: token de Microsoft o `ADMIN_KEY`). Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R1 y R10.

## Alcance

El mismo del panel (`Principal`): el alcance global gestiona a todos los usuarios; una cuenta de programa gestiona solo a los usuarios cuyo `unit_id` está en sus programas. Un usuario de otro alcance responde **404** como no encontrado (`out_of_scope`/404, igual que artefactos). Crear un usuario sin programa (`unit_id` nulo) es solo del alcance global (`global_only`, 403). Una cuenta de programa debe indicar uno de sus programas al crear.

## `GET /consulta-users`

**200**: `{ "users": [ ... ] }`, ordenados por nombre. Cada elemento:

```json
{
  "id": "uuid",
  "username": "ana.perez",
  "unit": { "id": "uuid", "name": "Unidad de Postgrados de Computación" },
  "active": true,
  "created_at": "2026-11-04T15:30:00Z",
  "last_login_at": "2026-11-04T16:02:00Z",
  "conversation_count": 7,
  "last_activity_at": "2026-11-04T16:20:00Z"
}
```

`unit` es `null` para un usuario sin programa. `conversation_count` y `last_activity_at` (nulo sin conversaciones) son lo único que la administración ve de las conversaciones: **ninguna ruta de administración devuelve texto de preguntas ni respuestas**. Nunca se devuelve `password_hash`.

## `POST /consulta-users`

Cuerpo: `{ "username": "ana.perez", "unit_id": "uuid|null", "password": "..." | null }`. Con `password` nulo o ausente el servidor genera una.

| Resultado | Cuándo |
|---|---|
| **201** | Crea el usuario activo. Cuerpo: el usuario como en la lista **más `password`** con la contraseña (la dada o la generada), **la única vez que sale**. |
| **409** | El nombre ya existe (sin distinguir mayúsculas): `Ya existe un usuario llamado 'ana.perez'.` |
| **422** | Nombre fuera de `^[a-z0-9._-]{3,40}$` tras normalizar, o contraseña dada más corta que `PASSWORD_MIN_CHARS`. |
| **403/404** | Fuera de alcance (ver arriba). |

Deja la línea `consulta_user.create` en `mia.admin` (`target` = id; `detail` = `"<usuario> -> <programa o (global)>"`), sin contraseña.

## `PATCH /consulta-users/{id}`

Cuerpo: `{ "active": true|false }`. **200** con el usuario. Desactivar borra todas sus sesiones. Línea `consulta_user.update` (`detail` = `"<usuario>: activo true|false"`) solo si cambió. **404** fuera de alcance.

## `POST /consulta-users/{id}/reset-password`

Cuerpo: `{ "password": "..." | null }` (nulo: se genera). **200**: `{ "password": "..." }`, la única vez. Cierra todas las sesiones del usuario y la contraseña anterior deja de servir. Línea `consulta_user.reset_password` (`detail` = nombre del usuario), sin contraseña. **404** fuera de alcance; **422** contraseña corta.

## Módulo del panel ("Usuarios de la Consulta")

| Pieza | Detalle |
|---|---|
| Menú | Entrada `/usuarios` en `MODULES`, visible para todas las cuentas de administración (el alcance lo hace cumplir la API). |
| Lista | Una tarjeta por usuario: nombre, programa, estado (texto y color), último acceso, cantidad de conversaciones y última actividad. Acciones: Desactivar o Reactivar, Restablecer contraseña. |
| Alta | Formulario con nombre de usuario (validado como en la API), programa (las cuentas de programa solo ven los suyos; el alcance global puede elegir "Ninguno (global)") y contraseña opcional con botón "Generar". |
| Contraseña | Tras crear o restablecer, un cuadro con la contraseña, un botón "Copiar" y el texto: "Esta contraseña se muestra una sola vez. Entrégala a la persona; no se podrá volver a ver." Se descarta al cerrar el cuadro. |
| Texto sobre privacidad | "Las personas con usuario guardan sus conversaciones en el servidor durante N días; quien administra no puede leerlas." con N tomado de la configuración si está disponible. |
