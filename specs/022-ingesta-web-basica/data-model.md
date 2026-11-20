# Data Model: Ingesta básica de una página web

Una migración **aditiva** (`0015`) y un catálogo de códigos de rechazo que no se guarda. Sin tablas nuevas.

## Documento (existente, `documents`)

Gana un sexto valor de `source_type`, `web`, y dos columnas nulas. Todo lo demás (nombre, dominio, carpeta, hash, estado, nota de estado, fecha de carga) se conserva y funciona igual.

| Campo | Tipo | Nulo | Para un documento web | Para los demás |
|---|---|---|---|---|
| `source_type` (existente) | texto | no | `web` | `pdf`, `docx`, `txt`, `xlsx`, `csv` |
| `filename` (existente) | texto | no | el nombre legible (R12): nombre propio, título de la página o el sitio; es lo que cita la respuesta | nombre del archivo |
| `file_hash` (existente) | texto, con índice | no | SHA-256 del **texto extraído** (UTF-8), para el duplicado por contenido | SHA-256 del archivo |
| `uploaded_at` (existente) | fecha y hora | no | momento de la lectura (la "fecha de lectura") | momento de la carga |
| `status`, `status_note` (existentes) | texto | no / sí | mismo flujo `pending`, `processing`, `done`, `error`; la nota solo trae avisos de la ingesta posterior, nunca un rechazo de lectura | igual |
| **`source_url`** (nuevo) | texto, con índice | **sí** | dirección **final** de la página, tal como se leyó (con su consulta) | `NULL` |
| **`source_text`** (nuevo) | texto largo, `deferred` | **sí** | el texto extraído completo (con la primera línea de origen), para verlo después | `NULL` |

**Validaciones** (a nivel de la API, no de la base):

- `source_url`: dirección `http` o `https` válida, sin credenciales, de hasta 2048 caracteres.
- `filename` (documento web): 1 a 200 caracteres, sin saltos de línea ni caracteres de control.
- `source_text`: no vacío y con al menos `WEB_MIN_TEXT_CHARS` de texto útil; no supera `MAX_UPLOAD_MB` en bytes UTF-8.
- Un dominio tiene como máximo **un** documento web por clave de comparación de dirección (R8). No hay restricción única en la base: se comprueba en la API (la clave es una función de la dirección, y el volumen es pequeño).

**Identidad y unicidad**: dos reglas independientes, ambas dentro del dominio y en cualquiera de sus carpetas. (1) Por dirección: `409 already_added`. (2) Por contenido: `200` con `already_existed: true`, como un archivo repetido (INV-6).

**Relaciones**: las mismas (`domain`, `folder`, imágenes por documento). Una imagen se puede asociar a un documento web como a cualquier otro.

**Ciclo de vida**: igual que los demás documentos. La eliminación (feature 012) quita la fila (con sus dos columnas nuevas), los fragmentos, el archivo `uploads/<id>.web` y las imágenes; no requiere pasos especiales. No hay actualización: para renovar una página se elimina y se vuelve a agregar.

### Migración `0015` (`0015_fuente_web_de_documento`)

```text
upgrade:   ALTER TABLE documents ADD COLUMN source_url  VARCHAR NULL;
           ALTER TABLE documents ADD COLUMN source_text TEXT    NULL;
           CREATE INDEX ix_documents_source_url ON documents (source_url);
downgrade: quitar el índice y las dos columnas (con batch_alter_table por SQLite)
```

- Solo aditiva: ninguna fila existente cambia (quedan con las dos columnas nulas).
- **Reversible**, pero `downgrade` pierde el texto guardado de los documentos web (los fragmentos siguen en Qdrant, así que las respuestas no cambian).
- Una API anterior a `0015` no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0014`. Respeta la regla de `CLAUDE.md` y `OPERACION.md` ("Cuidado con las migraciones"): no desplegar una versión con menos migraciones que las de la base.

## Resultado de la comprobación (no se guarda)

Valor que devuelve el lector de la página (`FetchedPage`) o el error que lanza (`WebRejection`):

- **Aceptado**: dirección final, contenido HTML ya leído (bytes, tipo y codificación). A partir de ahí se extrae el texto, se comprueban el mínimo y el tope y se crea el documento.
- **Rechazado** (`WebRejection(code, message, status)`): una razón del catálogo de abajo. No deja documento ni archivo ni fila; solo la línea de auditoría (R9) y la respuesta HTTP.

### Catálogo de rechazos

| `code` | Estado HTTP | Cuándo | Mensaje (resumen, en español) |
|---|---|---|---|
| `invalid_url` | 400 | vacía, sin forma de dirección, esquema no web, con credenciales, demasiado larga | La dirección no es válida: escribe una dirección que empiece con http:// o https://. |
| `private_address` | 400 | resuelve (o redirige) a una red interna, privada o reservada | No se pueden leer direcciones de redes internas. |
| `ingestion_disabled` | 503 | `INGESTION_ENABLED=false` | La ingesta está desactivada en esta instancia (mismo texto que la subida de archivos). |
| `already_added` | 409 | la dirección (escrita o final) ya está en el dominio | Esa página ya está agregada (leída el `<fecha>`). Para actualizarla, elimina el documento y vuelve a agregarla. |
| `login_required` | 422 | 401, redirección a un ingreso o formulario de contraseña | La página requiere iniciar sesión. Esta versión no puede leerla. |
| `bot_blocked` | 422 | protección anti-bot o pantalla de verificación, con cualquier código | El sitio bloquea la lectura automática (protección anti-bot). No se intenta esquivar. |
| `forbidden` | 422 | 403 sin señales de bloqueo | El sitio no permite el acceso a esta página (puede requerir iniciar sesión o bloquear la lectura automática). |
| `rate_limited` | 422 | 429 | El sitio pidió esperar antes de volver a leerlo. Intenta más tarde. |
| `robots_disallowed` | 422 | `robots.txt` prohíbe la ruta, o no se pudo consultar | El sitio no permite la lectura automática de esta página (`robots.txt`). |
| `not_found` | 422 | 404 o 410 | No se encontró la página (404). Revisa la dirección. |
| `server_error` | 422 | otros 4xx y 5xx | El sitio respondió con un error (`<código>`). |
| `unreachable` | 422 | el nombre no resuelve, conexión rechazada, tiempo agotado | No se pudo conectar con el sitio. / El sitio no respondió a tiempo. |
| `tls_error` | 422 | certificado inválido o conexión segura fallida | No se pudo establecer una conexión segura con el sitio (certificado inválido). |
| `too_many_redirects` | 422 | más de `WEB_MAX_REDIRECTS` saltos o ciclo | La dirección redirige demasiadas veces. |
| `not_html` | 422 | el contenido no es una página de texto | La dirección no es una página web de texto. Si es un archivo (por ejemplo, un PDF), súbelo como archivo. |
| `too_large` | 422 | el HTML supera `WEB_MAX_PAGE_KB` | La página es demasiado grande para leerla (más de `<n>` KB). |
| `no_content` | 422 | texto útil menor que `WEB_MIN_TEXT_CHARS` | No se pudo extraer contenido suficiente: la página probablemente carga su texto con JavaScript, que esta versión no ejecuta. |
| `text_too_large` | 413 | el texto extraído supera `MAX_UPLOAD_MB` | El archivo supera el tamaño máximo de `<n>` MB. (mismo mensaje de la subida) |

Las razones de `FR-007` quedan cubiertas: inicio de sesión (`login_required`, `forbidden`), anti-bot (`bot_blocked`, `rate_limited`), sin contenido extraíble (`no_content`), no encontrada (`not_found`), sin respuesta o tiempo agotado (`unreachable`), certificado (`tls_error`), redirecciones (`too_many_redirects`), no es página de texto (`not_html`), `robots.txt` (`robots_disallowed`) y demasiado grande (`too_large`, `text_too_large`).

## Texto extraído (no es una entidad; es el contenido de `source_text` y de `uploads/<id>.web`)

```text
Fuente: <dirección final> (consultada el <día> de <mes> de <año>)
<nombre del documento>

<contenido: títulos, párrafos, viñetas con guion, filas de tabla "Encabezado: valor | ...",
 enlaces como "texto (https://...)">
```

Reglas: UTF-8 en forma NFC; sin líneas vacías sobrantes ni viñetas huérfanas; sin contenido de otras páginas ni de archivos enlazados; sin scripts ni estilos.

## Cambios en las respuestas de la API (solo lectura)

- `DocumentOut` y el nodo de documento del inventario ganan `source_url` (`string | null`). `DocumentOut` gana además `uploaded_at` (fecha y hora; el inventario ya lo tenía).
- El panel sigue sin ver `source_text` en el inventario; solo lo pide con `GET .../text`.
