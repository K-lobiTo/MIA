# Data Model

## Tabla nueva: `deleted_domains` (migración `0016`)

| Columna | Tipo | Nota |
|---|---|---|
| `id` | texto, clave primaria | El id que tenía el dominio |
| `label` | texto | "Programa / Dominio", o solo el nombre si no tenía programa |
| `deleted_at` | fecha y hora UTC | |

Sin claves foráneas. Aditiva; `downgrade` la elimina (el historial vuelve a mostrar el id).

## Reglas de eliminación

**Dominio**: permitido si no tiene documentos (en cualquier estado) ni carpetas. En la misma transacción: se inserta en `deleted_domains`, se borran sus `artifact_domains` y la fila de `domains`.

**Programa**: permitido si no tiene filas en `domains`, `consulta_users`, `admin_units` ni `artifact_units`. Se borra la fila de `units`.

## `consulta_users.unit_id`

Pasa a ser modificable. Valores: id de un programa existente o nulo.
