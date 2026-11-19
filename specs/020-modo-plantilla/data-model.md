# Modelo de datos: Modo "plantilla" en la Consulta

Una tabla nueva y una ampliación de otra, ambas en la migración aditiva **`0014`** (la `0013` es de la feature 018). Sin semillas y sin tocar filas existentes. Decisiones y alternativas en [research.md](research.md) (R4 y R5).

## `response_templates` (nueva)

Plantillas de respuesta: las del artefacto (catálogo de la administración) y las personales de cada persona.

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | texto, clave primaria | UUID |
| `scope` | texto, no nulo | `artifact` (del artefacto) o `personal` |
| `owner_key` | texto, no nulo | `a:<artifact_id>` en las del artefacto, `u:<user_id>` en las personales. Con `name_key` forma la restricción única |
| `artifact_id` | texto, nulo, FK a `artifacts.id` con `ON DELETE CASCADE` | **Obligatorio** si `scope = artifact`. En una personal es el artefacto al que se limita; **nulo = para todos** (Q1 del 2026-11-18) |
| `user_id` | texto, nulo, FK a `consulta_users.id` con `ON DELETE CASCADE` | **Obligatorio** si `scope = personal`, nulo si es del artefacto. Eliminar al usuario elimina sus plantillas (FR-013) |
| `name` | texto, no nulo | "de 1 a 80 caracteres sin saltos de línea", recortado en los extremos |
| `name_key` | texto, no nulo | `name` en minúsculas y sin tildes; sirve para la unicidad |
| `content` | texto, no nulo | "no puede estar vacío", máximo `TEMPLATE_MAX_CHARS` (4000 inicial) |
| `created_by` | texto, no nulo | identificador de quien la creó (cuenta de administración o `user_id`); no es un dato mostrable |
| `created_at`, `updated_at` | fecha y hora UTC, no nulas | `updated_at` cambia en cada edición y sirve para detectar ediciones concurrentes |

**Restricciones e índices**:
- `UniqueConstraint(owner_key, name_key)`: el nombre es único dentro de las plantillas de un artefacto o dentro de todas las personales de una persona, y puede repetirse entre una personal y una del artefacto.
- Índice por `artifact_id` y por `user_id` (consultas de la lista).
- Un `CHECK` de coherencia (`scope = 'artifact'` implica `artifact_id` no nulo y `user_id` nulo; `scope = 'personal'` implica `user_id` no nulo) en la base, además de la validación en la API.

**Cantidades**: máximo `TEMPLATE_MAX_PER_ARTIFACT` (30) del artefacto por artefacto y `TEMPLATE_MAX_PER_USER` (20) personales por persona, validados en la API.

**Visibilidad** (la calcula la API, nunca el cliente): para un artefacto A y, opcionalmente, un usuario U, las plantillas visibles son las del artefacto A, más las personales de U con `artifact_id` nulo o igual a A. Sin sesión, solo las del artefacto.

**Ciclo de vida**: se crea, se edita (cambia `name`, `content` y, en personales, `artifact_id`; sube `updated_at`) y se elimina. No hay borrado lógico ni historial de versiones. Una edición rige desde la consulta siguiente; una eliminación hace que `resolve_template` responda "ya no está disponible".

## `conversation_turns` (ampliada)

| Campo nuevo | Tipo | Reglas |
|---|---|---|
| `template_id` | texto, nulo | Identificador de la plantilla usada en esa vuelta. **Sin clave foránea**: eliminar la plantilla no toca la conversación (spec, historia 2 escenario 6) |
| `template_name` | texto, nulo | Nombre de la plantilla al momento de la vuelta, solo para explicar qué falta si ya no existe. **Nunca el contenido** (FR-009) |

Ambos son nulos en las vueltas de los otros modos y en las ya guardadas. Al retomar una conversación se usa la plantilla de la **última vuelta que tiene `template_id`**; su contenido siempre se lee de `response_templates`.

## Tablas existentes sin cambios de esquema

- `artifacts.modes`: ya es texto separado por comas; gana el valor `plantilla`. Sin migración (research R1).
- `queries` (`QueryLog`): ya tiene `mode` (texto); gana el valor `plantilla`. **No** se agrega ninguna columna con la plantilla: el registro sigue guardando la pregunta original (no la respuesta) y no el contenido de la plantilla (FR-024).
- `consulta_users`: sin cambios; la relación es la FK de `response_templates.user_id`.

## Ajustes de configuración (nuevos)

| Ajuste | Inicial | Rango | Descripción |
|---|---|---|---|
| `TEMPLATE_MAX_CHARS` | `4000` | 200 a 20000 | largo máximo del contenido |
| `TEMPLATE_MAX_PER_USER` | `20` | 1 a 200 | personales por persona |
| `TEMPLATE_MAX_PER_ARTIFACT` | `30` | 1 a 200 | del artefacto por artefacto |
| `TEMPLATE_FILE_MAX_MB` | `1` | 1 a 10 | tamaño máximo del archivo que se carga |

## Transiciones de estado relevantes

- **Modo habilitado en un artefacto**: solo cambia `artifacts.modes`; las plantillas existentes se conservan aunque el modo se quite (se vuelven a ofrecer al habilitarlo).
- **Usuario eliminado**: sus `response_templates` personales se eliminan por `CASCADE`; sus conversaciones también (ya existente) y con ellas los `template_id`.
- **Plantilla eliminada con conversaciones que la usaron**: las vueltas conservan `template_id` y `template_name`; al retomar se pide elegir otra.
