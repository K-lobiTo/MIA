# Contratos: API de plantillas y cambios en la consulta

Todas las rutas aplican los permisos en la API (research R6 y R7). Errores con el formato habitual (`{"detail": "..."}`) y mensajes en español sin contenido de plantillas ni datos de personas.

## 1. Consulta (clave de artefacto `X-Artifact-Key`, sesión opcional `X-Session-Token`)

### `GET /templates`

Las plantillas visibles para el artefacto de la clave y, si hay sesión, para la persona. **No exige modo habilitado**: si el artefacto no tiene el modo, devuelve listas vacías (no ofrece nada).

```json
{
  "enabled": true,
  "limits": { "max_chars": 4000, "max_per_user": 20, "file_max_mb": 1 },
  "can_create": true,
  "artifact": [ { "id": "…", "name": "Informe de programa", "content": "…", "updated_at": "2026-11-18T15:04:00Z" } ],
  "mine": [ { "id": "…", "name": "Mi informe", "content": "…", "scope": "all", "updated_at": "…" },
            { "id": "…", "name": "Ficha corta", "content": "…", "scope": "artifact", "updated_at": "…" } ]
}
```

- `enabled`: el artefacto tiene el modo habilitado y la instancia lo tiene disponible.
- `can_create`: hay sesión de usuario válida (solo entonces se pueden crear personales), aunque el artefacto no exija iniciar sesión. Sin sesión la Consulta muestra el aviso de iniciar sesión, porque la Consulta ofrece esa opción en todos los artefactos.
- `mine` vacío sin sesión. `scope` de una personal: `"all"` (para todos) o `"artifact"` (para este artefacto; las de otros artefactos no aparecen).

### `POST /templates` (exige sesión)

Cuerpo: `{ "name": "…", "content": "…", "scope": "artifact" | "all" }` (`artifact` = para el artefacto de la clave). Crea una personal. `201` con la plantilla.

| Caso | Respuesta |
|---|---|
| Sin sesión | `401` `code: "login_required"` |
| Modo no habilitado en el artefacto | `403` "Este artefacto no tiene el modo plantilla." |
| Nombre repetido en las personales de la persona | `409` "Ya tienes una plantilla con ese nombre." |
| Nombre vacío o de más de 80 caracteres, o con saltos de línea; contenido vacío o mayor que `max_chars`; máximo de plantillas | `422` con el límite en el mensaje |

### `PUT /templates/{id}` y `DELETE /templates/{id}` (exige sesión; solo personales del dueño)

`PUT`: mismo cuerpo que `POST` más `expected_updated_at` opcional (si no coincide, `409` con la versión actual). `DELETE`: `204`. Una plantilla del artefacto o ajena responde `404` (sin distinguir de una inexistente).

### `POST /templates/extract` (exige sesión)

Multipart con el campo `file` (`.docx` o `.txt`). Devuelve `{ "text": "…" }` sin guardar nada. Errores `422` con mensaje fijo:

| Caso | Mensaje |
|---|---|
| Extensión distinta de `.docx` o `.txt` | `Solo se aceptan archivos .docx o .txt.` |
| Archivo mayor que `file_max_mb` | `El archivo supera el tamaño máximo de {n} MB.` (`413`) |
| Dañado, protegido con contraseña, o que no se puede leer | `No se pudo leer el archivo: está dañado o protegido con contraseña.` |
| Sin texto | `El archivo no tiene texto.` |
| Texto mayor que `max_chars` | `El texto del archivo supera el máximo de {n} caracteres.` (no se recorta) |

El archivo se lee con los cargadores de la ingesta y se borra de inmediato; nunca se guarda (research R8).

### `POST /query` (cambios)

```json
{ "domains": ["…"], "question": "Prepárame el informe de la Maestría en Ciberseguridad",
  "mode": "plantilla", "template_id": "…", "conversation_id": "…", "history": [ … ] }
```

- `mode` admite `"plantilla"` (además de `literal` y `razonamiento`), también en `history[].mode`.
- `template_id` es **obligatorio con `mode = "plantilla"`** (`422` "Elige una plantilla."); con otro modo se ignora.
- Plantilla inexistente o no visible para la persona y el artefacto: `404` "La plantilla ya no está disponible."
- El artefacto sin el modo permitido: `403` como con cualquier modo (`rejected_permission`).
- La respuesta es la de siempre (`answer`, `sources`, `mode: "plantilla"`, `no_info`, ...). Con sesión, la vuelta guardada incluye `template_id` y `template_name`.

### `GET /config` (cambio)

`modes` incluye `plantilla` (con su nombre "Plantilla" y descripción) cuando el artefacto lo permite, con `available` y `reason` como los demás (deshabilitado si la instancia no tiene configurado el razonamiento o se alcanzó un tope, incluido el del razonamiento).

### `GET /conversations/{id}` (cambio)

Cada vuelta incluye `template_id` y `template_name` (nulos si no usó plantilla). El cliente retoma con la plantilla de la última vuelta que la tiene (research R5).

## 2. Panel (cuenta de administración; mismo alcance que `PATCH /artifacts/{id}`)

Un artefacto fuera del alcance responde `404` como uno inexistente. Cada escritura deja `audit.log_write` con acción, artefacto y nombre, **sin contenido**.

| Ruta | Descripción |
|---|---|
| `GET /artifacts/{id}/templates` | Las plantillas del artefacto (con contenido) y los límites. |
| `POST /artifacts/{id}/templates` | Crea una del artefacto: `{ "name", "content" }`. Mismos errores de validación; `409` si el nombre ya existe en el artefacto; `422` al llegar a `max_per_artifact`. |
| `PUT /artifacts/{id}/templates/{template_id}` | Edita nombre y contenido; `expected_updated_at` opcional para detectar una edición concurrente (`409` con la versión actual). |
| `DELETE /artifacts/{id}/templates/{template_id}` | Elimina (`204`). |
| `POST /artifacts/{id}/templates/extract` | Igual que el de la Consulta, para la administración. |

`ArtifactOut` y `ArtifactCreate/Update` aceptan `"plantilla"` en `modes`. El listado de artefactos puede mostrar `template_count` (cantidad de plantillas del artefacto).

## 3. Registro de Uso

`queries.mode` y los filtros de `GET /usage` aceptan `"plantilla"`. Los topes: el gasto de `plantilla` suma al total del artefacto y al **tope del modo con razonamiento** (research R2).

## 4. Interfaces internas

```python
# mia/rag/modes.py
PLANTILLA = "plantilla"
MODE_IDS = [LITERAL, RAZONAMIENTO, PLANTILLA]
def is_reasoning_class(mode: str) -> bool: ...   # razonamiento y plantilla

# mia/rag/llm.py
TEMPLATE_SYSTEM_PROMPT: str
def build_template_block(content: str) -> str: ...   # "<<<PLANTILLA ... PLANTILLA>>>" con su encabezado

# mia/templates/service.py  (nuevo)
def visible_templates(session, artifact, user) -> tuple[list, list]: ...
def resolve_template(session, artifact, user, template_id) -> ResponseTemplate: ...  # 404 si no es visible
def extract_text(upload, max_chars, max_mb) -> str: ...
```

El bot de WhatsApp y el servicio de correo siguen usando solo `literal`: `POST /bot/query` no recibe modo (usa `BOT_MODE = "literal"` fijo) y no cambia.
