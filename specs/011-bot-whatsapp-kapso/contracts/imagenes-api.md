# Contrato: imágenes de documentos y ruta pública `/media`

Rutas del panel para gestionar las imágenes asociadas a un documento, la ruta pública que las sirve y el campo `images` de la consulta. Detalle de los datos en [data-model.md](../data-model.md) y de las decisiones en [research.md](../research.md) R5 y R6.

## Rutas de administración

Requieren administración (`require_admin`) y el **mismo alcance que ya tiene la persona sobre el documento**: `ensure_domain(principal, dominio_del_documento, acción)`. Fuera de alcance responde 403 `out_of_scope` y deja la línea `rechazado` en el registro de administración (como `document.upload`). El documento debe pertenecer al dominio de la ruta (404 si no). Las escrituras dejan `image.create`, `image.update`, `image.reorder`, `image.replace` e `image.delete` en `mia.admin` con el nombre del documento y el id de la imagen, nunca el contenido.

Forma de una imagen en las respuestas (`ImageOut`):

```json
{ "id": "…", "public_id": "Qn3x…", "url": "/media/Qn3x…", "content_type": "image/png", "size_bytes": 184233, "caption": "Horario de matrícula", "position": 0 }
```

### GET /domains/{domain_id}/documents/{document_id}/images

Lista las imágenes del documento por `position`. **200**: `{ "images": [ImageOut], "max_image_mb": 2 }`. No lee el binario.

### POST /domains/{domain_id}/documents/{document_id}/images

Agrega una imagen al final del orden. **Cuerpo** `multipart/form-data`: `file` (obligatorio) y `caption` (opcional, hasta 1.000 caracteres).

**201**: el `ImageOut`.

**Validación** (en este orden, antes de guardar nada):

| Qué | Respuesta |
|---|---|
| La imagen supera `MAX_IMAGE_MB` (se lee un byte más del límite) | 413 `La imagen supera el tamaño máximo de 2 MB.` |
| No empieza con la firma de un PNG o un JPEG | 415 `Solo se aceptan imágenes PNG o JPG.` |
| Un PNG sin el trozo `IEND` final o un JPEG sin el marcador `FF D9` final | 422 `La imagen está incompleta o dañada.` |
| `caption` de más de 1.000 caracteres | 422 |

El tipo que declara el navegador y el nombre del archivo no cuentan: manda el contenido. El panel hace las mismas comprobaciones de formato y tamaño antes de subir (la API es la que las hace cumplir).

### PUT /domains/{domain_id}/documents/{document_id}/images/{image_id}

Reemplaza el contenido de una imagen **conservando su descripción y su posición** y le asigna un `public_id` nuevo: el enlace anterior deja de servir (IMG-3, FR-032). **Cuerpo** `multipart/form-data` con `file`; misma validación que al agregar. **200**: el `ImageOut` con la `url` nueva.

### PATCH /domains/{domain_id}/documents/{document_id}/images/{image_id}

Cambia la descripción. **Cuerpo**: `{ "caption": "…" }` (hasta 1.000 caracteres; vacío la quita). **200**: el `ImageOut`.

### PUT /domains/{domain_id}/documents/{document_id}/images/order

Fija el orden de todas las imágenes del documento. **Cuerpo**: `{ "image_ids": ["…", "…"] }` con **exactamente** los ids del documento, cada uno una vez. **200**: `{ "images": [ImageOut] }` ya reordenadas (`position` desde 0). **422** si falta o sobra un id o hay repetidos (lista desactualizada: el panel recarga).

### DELETE /domains/{domain_id}/documents/{document_id}/images/{image_id}

Quita la imagen (borrado físico) y compacta las posiciones de las demás. **204**. Su enlace público responde 404 desde ese momento (puede seguir sirviéndose desde cachés externas hasta una hora).

### Inventario

`GET /inventory` agrega `image_count` (entero, 0 si no hay) a cada documento (`DocumentNode`), con una sola consulta agrupada. Es un campo nuevo: el panel lo usa para el contador del botón "Imágenes".

## GET /media/{public_id}

**Pública**: sin clave ni encabezados. Sirve el binario de una imagen.

- `public_id`: de 20 a 64 caracteres de `A-Z a-z 0-9 _ -`; con otra forma responde 404 sin consultar la base.
- **200**: el cuerpo, con `Content-Type` guardado (`image/png` o `image/jpeg`), `Content-Length`, `Cache-Control: public, max-age=3600` y `X-Content-Type-Options: nosniff`.
- **404** si no existe (nunca existió, se reemplazó o se quitó).
- No registra nada en Uso, no cuenta contra ningún tope y no requiere CORS (la piden Kapso y Meta, y el panel como `<img>`).

## Campo `images` de la consulta

`POST /query` y `POST /bot/query` devuelven `images` en `QueryResponse` (siempre presente, lista vacía por defecto):

```json
"images": [{ "url": "/media/Qn3x…", "caption": "Horario de matrícula", "document": "horario_matricula.pdf" }]
```

- **Qué incluye**: las imágenes de los documentos de las **fuentes de la respuesta** (las que el modelo cita con `QUERY_CITED_SOURCES=on`), cada documento una vez, en el orden de las fuentes, y dentro de un documento por `position`.
- **Qué no incluye**: nada si la respuesta es "sin información"; nada de documentos que solo se le pasaron al modelo sin aportar (con la opción de citas encendida).
- **Cálculo**: después de elegir las fuentes, una sola consulta a la base por los documentos (sin leer los binarios).
- **Si falla** esa consulta: la respuesta se entrega con `images: []` y un aviso en el registro del servidor; la consulta no falla.
- `url` es **relativa**: el cliente la completa con la dirección pública de la API (el bot usa `MIA_API_URL`).
- Los clientes que no conocen el campo lo ignoran: la estructura anterior no cambia.
