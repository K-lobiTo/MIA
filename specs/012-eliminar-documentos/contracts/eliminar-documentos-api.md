# Contrato: eliminar documentos (API)

Dos rutas de administración para quitar documentos de los dominios. Detalle de los datos en [data-model.md](../data-model.md) y de las decisiones en [research.md](../research.md) R1 a R5.

Ambas requieren administración (`require_admin`): una clave de artefacto o la ausencia de credenciales no sirven (401). El alcance es **el mismo que ya se tiene para subir el documento**: `ensure_domain(principal, dominio_del_documento, "document.delete")`. Fuera de alcance responde 403 `out_of_scope` y deja la línea `rechazado` en el registro de administración (`mia.admin`). La API elimina al recibir el pedido; la confirmación es del panel (el Inventario) y de quien use los scripts.

## DELETE /domains/{domain_id}/documents/{document_id}

Elimina el documento de punta a punta (base, imágenes, fragmentos y archivo original, en el orden de R1).

| Respuesta | Cuándo |
|---|---|
| **204** | Se eliminó. Desde la consulta siguiente ninguna respuesta cita ni usa su contenido. |
| 401 | Sin credenciales de administración, o una clave de artefacto |
| 403 `out_of_scope` | El documento es de un dominio fuera del alcance de la persona (con `document.delete` `rechazado` en el registro) |
| 404 | El dominio no existe, el documento no existe o no pertenece a ese dominio (también al repetir una eliminación ya hecha) |
| 409 `document_busy` | El documento se está procesando y la ingesta no soltó el cerrojo en `DELETE_WAIT_SECONDS`: `El documento se está procesando; intenta de nuevo en un momento.` No se tocó nada. |
| 503 `store_unavailable` | El almacén de vectores falló al borrar (o no pudo comprobarse): `No se pudo quitar el contenido del documento del almacén de búsqueda; el documento sigue como estaba. Intenta de nuevo.` |

Efectos en el registro de administración: `document.delete`, `target` = id del documento, `detail` = `<nombre del archivo> en <nombre del dominio>`, `result` = `ok`. Nunca el contenido del documento.

Es **idempotente en el efecto**: repetir la llamada tras una falla (409, 503) es seguro; tras un 204, la repetición responde 404.

## POST /documents/bulk-delete

Elimina varios documentos con una sola petición. Cada uno se valida y se elimina por separado con el mismo servicio: uno que falla no impide los demás.

**Cuerpo**:

```json
{ "document_ids": ["…", "…"] }
```

De 1 a 100 ids (los repetidos se cuentan una vez); fuera de ese rango, 422. Pueden ser de dominios distintos: el dominio sale del documento y el alcance se evalúa por documento.

**200** (siempre que el cuerpo sea válido, aunque algunos fallen):

```json
{
  "deleted": 2,
  "failed": 1,
  "results": [
    { "document_id": "…", "filename": "Admision.pdf", "status": "deleted" },
    { "document_id": "…", "filename": "Horario.pdf", "status": "deleted" },
    { "document_id": "…", "filename": "Actas.pdf", "status": "out_of_scope", "detail": "Eso queda fuera de los programas a los que tienes acceso." }
  ]
}
```

| `status` | Significado | Equivale a |
|---|---|---|
| `deleted` | Eliminado | 204 |
| `not_found` | El id no existe (o ya se eliminó) | 404 |
| `out_of_scope` | Fuera del alcance de la persona; no se tocó | 403 |
| `busy` | Se está procesando y no soltó el cerrojo a tiempo; no se tocó | 409 |
| `error` | Falló el almacén de vectores; el documento sigue como estaba | 503 |

`filename` va solo cuando el documento existía. El orden de `results` es el de la lista recibida. Cada documento eliminado deja su propia línea `document.delete`; los rechazados dejan `rechazado`. 401 igual que la ruta por documento.

## Lo que no cambia

- `POST /query`, `POST /bot/query` y las demás rutas responden igual; un documento eliminado simplemente ya no aparece en ninguna búsqueda.
- `GET /inventory` deja de listar el documento y baja los contadores del dominio y de la carpeta.
- Volver a subir el mismo archivo con `POST /domains/{id}/documents` responde 201 como un documento nuevo (la huella `file_hash` desapareció con la fila). Las imágenes no se recuperan: hay que asociarlas de nuevo.
- Las consultas pasadas que lo citaron se conservan en el módulo Uso con el nombre del documento.
- CORS ya permite `DELETE` y `POST` (`CORS_ALLOW_METHODS`).
