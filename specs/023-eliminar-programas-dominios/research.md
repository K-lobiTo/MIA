# Research: Eliminación de programas y dominios

Verificado leyendo el código el 2026-11-26.

## R1. Qué referencia a un programa o un dominio

| Referencia | A qué | Al eliminar |
|---|---|---|
| `domains.unit_id` | programa | Impide eliminar el programa |
| `consulta_users.unit_id` | programa | Impide (se puede reasignar, R5) |
| `admin_units.unit_id` | programa | Impide (se gestiona con `scripts/admin.py`) |
| `artifact_units.unit_id` | programa | Impide (se edita el artefacto) |
| `documents.domain_id`, `folders.domain_id` | dominio | Impiden |
| `artifact_domains.domain_id` | dominio | Se borran con el dominio |
| `queries.domain_ids` (JSON, sin clave foránea) | dominio | No se toca; ver R4 |
| Fragmentos en Qdrant (`domain`) | dominio | Con el dominio vacío no debería haber; ver R3 |

## R2. Atomicidad y carreras

**Decision**: una transacción: bloquear la fila (`SELECT ... FOR UPDATE`), volver a comprobar los impedimentos, borrar, `flush`, limpiar el almacén y `commit`. Un `IntegrityError` se responde 409. Las cargas (archivo y página web) que fallen porque el dominio desapareció responden 404 y no dejan el archivo.

**Rationale**: Postgres impide insertar algo que apunte a una fila bloqueada para borrar, así que no pueden quedar huérfanos en producción. SQLite no aplica claves foráneas por defecto ni bloquea filas: límite solo de desarrollo.

**Alternatives considered**: marcar como "eliminado" (obliga a filtrar en cada consulta); activar claves foráneas en SQLite de forma global (cambia el comportamiento de todo el sistema, fuera de alcance).

## R3. Fragmentos huérfanos en Qdrant

**Decision**: `VectorStore.document_ids_in_domain(domain_id)` (no abstracto). Antes de confirmar la eliminación de un dominio: los fragmentos de un documento que no existe se borran (`delete_document`); los de un documento que existe en otro dominio se reetiquetan (`set_domain`), nunca se borran. Si el almacén no responde: 503 y no cambia nada.

**Rationale**: FR-011 pide no dejar contenido buscable. Borrar por el campo `domain` podría destruir fragmentos de un documento vivo cuyo movimiento quedó a medias.

## R4. Historial de Uso

**Decision**: tabla `deleted_domains` (id, etiqueta "Programa / Dominio", fecha), escrita en la misma transacción. El detalle de una consulta muestra "Programa / Dominio (eliminado)" en lugar de `(id, ya no existe)`. Las fuentes ya guardan nombres, no ids.

**Alternatives considered**: reescribir `queries.domain_ids` (reescribe el historial); guardar nombres en cada consulta nueva (no cubre las consultas pasadas); borrado blando de dominios (R2).

## R5. Cambiar el programa de un usuario de la Consulta

**Decision**: `PATCH /consulta-users/{id}` acepta `unit_id`; ausente no cambia, `null` lo deja sin programa. El usuario debe estar en el alcance (si no, 404 como hoy) y el programa de destino también (`ensure_unit`; "sin programa" es solo global). No se cierran sesiones: el programa no da permisos.

## R6. Cómo se explica un impedimento

**Decision**: una ruta de comprobación devuelve impedimentos y afectados estructurados; el panel la consulta antes de mostrar la confirmación. `DELETE` vuelve a comprobar y responde 409 con una frase completa en `detail` (el cliente del panel muestra `detail` como texto).

**Nombres fuera del alcance**: los artefactos que la persona no administra no se nombran, solo se cuentan (convención de `visible_to` al crear un dominio). Aplica a dominios; los programas solo los elimina el alcance global.

## R7. Artefacto que queda sin acceso

Al eliminar el único dominio de un artefacto, el artefacto queda sin dominios. Crear o editar exige al menos un acceso, pero el estado vacío es válido para consultar: la Consulta no ofrece dominios y una consulta a un dominio eliminado responde 403. La confirmación lo advierte y nombra los bots que usan ese artefacto.
