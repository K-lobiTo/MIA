# Contrato: agregar una página web como fuente

Interfaces nuevas de la feature 022. Todo exige administración y el mismo alcance por dominio que subir un documento (`require_admin` y `ensure_domain`). Los mensajes `detail` están en español; `code` es estable para pruebas y scripts. El catálogo completo de códigos está en [../data-model.md](../data-model.md#catálogo-de-rechazos).

## `POST /domains/{domain_id}/web-pages`

Lee **una** página y, si se puede leer, la agrega al dominio como documento de tipo `web`.

**Cuerpo (JSON)**

```json
{
  "url": "https://www.tec.ac.cr/posgrado/ejemplo",
  "name": "Maestría de ejemplo: admisión",
  "folder_id": null
}
```

| Campo | Obligatorio | Reglas |
|---|---|---|
| `url` | sí | hasta 2048 caracteres (vacía, ausente o más larga: `400 invalid_url`, nunca una lista de errores de validación); se recortan espacios; sin esquema se antepone `https://` si parece un nombre de sitio; solo `http` y `https`; sin credenciales |
| `name` | no | espacios recortados y, si pasa de 200 caracteres, se corta a 200 sin error; vacío o solo espacios equivale a no enviarlo (se usa el título de la página o el sitio) |
| `folder_id` | no | carpeta del mismo dominio, como en la subida de archivos |

**Qué hace, en orden** (cada paso que falla responde y no crea nada; todo rechazo se audita, ver más abajo):

1. Ingesta desactivada: `503 ingestion_disabled`.
2. Dominio inexistente: `404`; fuera de alcance: el error de alcance de siempre.
3. Dirección inválida o hacia la red interna: `400`.
4. Carpeta inexistente: `404`; de otro dominio: `422`.
5. Dirección ya agregada en el dominio (escrita): `409 already_added`.
6. Lectura de la página: **una** petición de contenido (más `robots.txt` y las redirecciones de la propia dirección). No sigue enlaces ni abre archivos enlazados. Fallos: `422` con su código.
7. Dirección final ya agregada: `409 already_added`.
8. Extracción, mínimo de texto (`422 no_content`) y tope de documento (`413 text_too_large`).
9. Mismo texto ya en el dominio: `200` con `already_existed: true` y el documento existente (como un archivo repetido).
10. Alta: escribe `uploads/<id>.web`, crea el `Document` (`source_type="web"`, `filename`, `source_url`, `source_text`, `file_hash`, `status="pending"`), confirma, audita y lanza la ingesta como en la subida de archivos (`INGESTION_SYNC` o segundo plano).

**Respuestas**

| Estado | Cuándo | Cuerpo |
|---|---|---|
| `201` | agregada | `DocumentOut` (abajo) |
| `200` | el mismo texto ya existía | `DocumentOut` con `already_existed: true` |
| `400` | `invalid_url`, `private_address` | `{"detail": "...", "code": "..."}` |
| `404` | dominio o carpeta inexistente | `{"detail": "..."}` |
| `409` | `already_added` | `{"detail": "...", "code": "already_added", "document_id": "...", "read_at": "2026-11-20T15:04:05"}` |
| `413` | `text_too_large` | `{"detail": "El archivo supera el tamaño máximo de 25 MB.", "code": "text_too_large"}` |
| `422` | cualquier rechazo de lectura o de contenido | `{"detail": "...", "code": "login_required"}` (y los demás del catálogo); carpeta de otro dominio |
| `503` | `ingestion_disabled` | `{"detail": "...", "code": "ingestion_disabled"}` |

El tiempo máximo hasta la respuesta, sin contar la ingesta posterior, es `WEB_FETCH_TIMEOUT_SECONDS` (15 s por defecto) más lo que tarde el alta; con `INGESTION_SYNC=true` la respuesta llega cuando el documento terminó de procesarse, como con los archivos.

**`DocumentOut`** (el de la subida, con dos campos de solo lectura nuevos)

```json
{
  "id": "…",
  "filename": "Maestría de ejemplo: admisión",
  "source_type": "web",
  "status": "pending",
  "folder_id": null,
  "status_note": null,
  "already_existed": false,
  "source_url": "https://www.tec.ac.cr/posgrado/ejemplo",
  "uploaded_at": "2026-11-20T15:04:05"
}
```

Para los documentos que no son web, `source_url` es `null`.

### Auditoría (registro `mia.admin`)

Una línea JSON por intento, con la acción `document.add_web`:

| Caso | `target` | `detail` | `result` |
|---|---|---|---|
| Aceptada | id del documento | `<nombre> en <dominio>` | `ok` |
| Rechazada (cualquier código, incluso antes de leer) | id del dominio | `<code> <dirección sin consulta ni fragmento>` | `rechazado` |

Nunca lleva contenido de la página, credenciales ni la consulta de la dirección. Una dirección con credenciales se registra solo como `invalid_url`, y una que no se puede interpretar se registra con el texto fijo `(dirección no interpretable)`, nunca con lo escrito.

## `GET /domains/{domain_id}/documents/{document_id}/text`

Devuelve el texto extraído de un documento web, para revisarlo en el panel (FR-017).

| Estado | Cuándo | Cuerpo |
|---|---|---|
| `200` | el documento es web y tiene texto | `{"text": "...", "source_url": "...", "read_at": "…", "filename": "..."}` |
| `404` | dominio o documento inexistente, documento de otro dominio, o un documento que no es web | `{"detail": "Documento no encontrado."}` |
| fuera de alcance | | el error de alcance de siempre |

Solo lectura: no audita (no es una escritura). No se ofrece para documentos que no son web (su texto no se guarda).

## Inventario (`GET /inventory`)

El nodo de documento gana `source_url` (`string | null`). Sin otros cambios; la fecha de lectura es `uploaded_at`, que ya estaba.

## Cargador (`WebLoader`)

Registrado en `get_loader("web")`. Lee `uploads/<id>.web` (texto UTF-8 que escribió la ruta) y lo devuelve tal cual. Vacío o ilegible: `LoaderError("La página no tiene contenido para procesar.")`. No hace red ni extracción: esa parte ocurre antes, en la petición. No agrega avisos (`notes` vacío).

## Panel de administración

- **Inventario, dominio y carpeta**: botón "Agregar página web" junto a "Subir archivos".
- **`AgregarPaginaDialog`**: campo de dirección, campo de nombre (opcional) y el aviso no bloqueante: *"El contenido de la página se podrá consultar con los artefactos de este dominio. MIA no filtra datos personales (nombres, correos y teléfonos de contactos): revisa el texto una vez agregado y elimina el documento si no es adecuado."* El botón se desactiva y muestra el progreso mientras se lee. Un rechazo muestra `detail` en la misma ventana, que sigue abierta con lo escrito. Al aceptar, se cierra y el inventario se refresca.
- **Inventario de documentos**: el tipo se ve `WEB`, el nombre es un enlace a la dirección (`rel="noopener noreferrer"`, nueva pestaña) o va acompañado de ella, se ve la fecha de lectura y hay un botón "Ver texto".
- **`TextoDocumentoDialog`**: muestra el texto extraído tal como se guardó (texto plano, con desplazamiento) y la dirección con la fecha de lectura.
- Eliminación y selección múltiple: las existentes, sin cambios.

## Ajustes de configuración nuevos

`WEB_USER_AGENT`, `WEB_FETCH_TIMEOUT_SECONDS` (15), `WEB_MAX_PAGE_KB` (2048), `WEB_MAX_REDIRECTS` (5) y `WEB_MIN_TEXT_CHARS` (300). Detalle y rangos en [../research.md](../research.md#r10-topes-y-ajustes-nuevos).

## Compatibilidad

- `POST /domains/{id}/documents` no cambia (sigue aceptando `pdf, docx, txt, xlsx, csv`; **no** acepta `web`, porque un documento web no se sube como archivo).
- Los tipos de archivo existentes, la consulta y las respuestas no cambian.
- `DocumentOut` y el inventario solo ganan campos opcionales.
