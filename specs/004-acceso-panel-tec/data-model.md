# Data Model: Acceso al panel con cuentas del TEC y separación por unidad

Cambios de esquema (migración Alembic `0003_administradores`) y objetos en memoria. Las tablas
existentes no cambian.

## Tablas nuevas

### `admins`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | String, PK | UUID |
| `email` | String, único | siempre en minúsculas y sin espacios; debe contener `@` (lo valida `access/admins.py`, no la base) |
| `is_global` | Boolean | verdadero: todas las unidades, presentes y futuras, y lo que no pertenece a ninguna |
| `active` | Boolean | falso: no puede usar el panel; el registro se conserva |
| `created_at`, `updated_at` | DateTime (UTC, sin zona) | como el resto de las tablas |

### `admin_units`

| Campo | Tipo | Notas |
|---|---|---|
| `admin_id` | FK `admins.id`, PK | |
| `unit_id` | FK `units.id`, PK | |

Reglas (las aplica `access/admins.py`, que es lo único que escribe estas tablas):

- Un administrador tiene alcance global **o** al menos una unidad; nunca ninguno. Si es global, no
  guarda filas en `admin_units` (el valor de `is_global` manda).
- Agregar un correo que ya existe actualiza su alcance (reemplaza las unidades) y lo reactiva.
- Desactivar no borra filas.
- Las unidades se indican por nombre en el script y se guardan por `id`.

Convención de nombres de índices y restricciones: la de `NAMING_CONVENTION` de `models.py`.

## Objetos en memoria (sin tabla)

### `Principal` (`access/scope.py`)

| Campo | Notas |
|---|---|
| `email` | `str` o `None` si viene de la clave de automatización |
| `is_global` | `bool` |
| `unit_ids` | `frozenset[str]`; vacío si es global |
| `source` | `"entra"` o `"automation"` |
| `label` | propiedad: el correo, o `"automatizacion"`; es lo que se escribe en el registro |

Reglas de alcance (funciones puras, reciben `Principal` y `Session`):

| Pregunta | Regla |
|---|---|
| ¿Una unidad está en alcance? | global, o `unit_id` en `unit_ids` |
| ¿Un dominio está en alcance? | global, o su `unit_id` en alcance (un dominio sin unidad solo para global) |
| ¿Un artefacto está en alcance? | global, o: no `all_domains`, con acceso configurado, y todas sus unidades y la unidad de cada dominio puntual en alcance |
| ¿Se puede dar este acceso a un artefacto? | global, o: `all_domains` falso, y todas las unidades y la unidad de cada dominio puntual en alcance |
| ¿Qué ids de artefacto cubre su Uso? | los artefactos en alcance; global: todos (`None`) |

Un artefacto cuyo acceso mezcla una unidad ajena y una propia **no** está en alcance (solo global lo
ve), aunque una parte sea de la persona (spec, caso límite de acceso de dos unidades).

### Identidad validada (`access/entra.py`)

`Identity(email, mfa)`: resultado de validar un token. La validación no consulta la base; la
comprobación contra `admins` y la construcción del `Principal` ocurren en `security.py`.

### Origen de claves (`access/entra.py`)

Interfaz `KeySource` con `get_key(kid) -> clave pública`. Implementación de producción
`MicrosoftKeys`: caché en memoria con vigencia de 1 hora, nueva bajada si llega un `kid` desconocido
(mínimo 5 minutos entre bajadas), uso de la caché vencida si la bajada falla. Las pruebas la sustituyen
con `app.dependency_overrides`.

## Estados

El único estado nuevo es `admins.active`. No hay transiciones más allá de activar y desactivar.

## Lo que no cambia

`Unit`, `Domain`, `Folder`, `Document`, `Artifact`, `ArtifactUnit`, `ArtifactDomain` y `QueryLog` quedan
igual. Los artefactos y sus claves siguen siendo independientes de los administradores.
