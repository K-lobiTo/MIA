# Contrato: Inventario de información

Encabezado de administración: `X-Admin-Key: <ADMIN_KEY>`. Errores comunes de las operaciones que lo
exigen: **401** sin clave o con clave incorrecta, **503** si la instancia no tiene `ADMIN_KEY`.
Los errores tienen la forma `{"detail": "<mensaje en español>"}`.

## GET /inventory (sin clave)

Árbol completo en una sola respuesta (INV-1, SC-008).

```json
{
  "ingestion_enabled": true,
  "max_upload_mb": 25,
  "units": [
    {
      "id": "u-1", "name": "Computación", "description": "...", "document_count": 133,
      "domains": [
        {
          "id": "d-1", "name": "Memoria del Consejo", "description": "...", "document_count": 20,
          "folders": [
            {"id": "f-1", "name": "Actas", "parent_id": null, "document_count": 20,
             "folders": [{"id": "f-2", "name": "2025", "parent_id": "f-1", "document_count": 20, "folders": [], "documents": [ "..." ]}],
             "documents": []}
          ],
          "documents": [
            {"id": "doc-1", "filename": "acta.pdf", "source_type": "pdf", "status": "done", "uploaded_at": "2026-10-07T23:10:00Z", "folder_id": null}
          ]
        }
      ]
    }
  ],
  "unassigned_domains": []
}
```

- `document_count` de una unidad, dominio o carpeta incluye lo que está en sus carpetas internas.
- `unassigned_domains`: dominios sin unidad (antes de la reorganización), con la misma forma que
  `domains`.
- `ingestion_enabled` alimenta el modo solo lectura (INV-7) y `max_upload_mb` el rechazo previo de archivos grandes en el panel (también está en `GET /config`).

## GET /units (sin clave)

`[{"id", "name", "description"}]`.

## POST /units (admin)

Request `{"name": "Computación", "description": ""}`. **201** con la unidad. **409** si el nombre ya
existe. **422** si el nombre está vacío.

## POST /domains (admin)

Request `{"unit_id": "u-1", "name": "Currículum", "description": ""}`. **201** con el dominio y un
campo `visible_to`:

```json
{"id": "d-9", "unit_id": "u-1", "name": "Currículum", "description": "",
 "visible_to": {"now": ["Consulta administrativa Postgrados Computación"], "needs_enabling": ["Chatbot web"]}}
```

`visible_to.now`: artefactos activos con acceso a todos los dominios o a la unidad; `needs_enabling`:
artefactos activos con dominios puntuales (INV-12). **404** si la unidad no existe, **409** si ya hay
un dominio con ese nombre en la unidad.

## GET /domains (cambia)

Sin clave: todos los dominios, como hoy, con `unit_id` y `unit_name`. Con `X-Artifact-Key`: solo los
dominios permitidos al artefacto (ver [api-consulta.md](api-consulta.md)).

## POST /domains/{domain_id}/folders (admin)

Request `{"name": "Programas de curso", "parent_id": null}`. **201** con la carpeta. **404** si el
dominio o la carpeta padre no existen; **409** si ya hay una carpeta con ese nombre en ese nivel;
**422** si la carpeta padre es de otro dominio.

## PATCH /folders/{folder_id} (admin)

Request `{"name": "Nuevo nombre"}`. **200** con la carpeta. **404**, **409** (nombre repetido en el
nivel).

## DELETE /folders/{folder_id} (admin)

**204** si estaba vacía. **409** `{"detail": "La carpeta debe estar vacía (sin documentos ni subcarpetas) para borrarla."}`.

## POST /domains/{domain_id}/documents (cambia; admin)

Multipart: `file` y, opcional, `folder_id`. Respuesta **201** (nuevo) o **200** (ya existía):

```json
{"id": "doc-7", "filename": "acta.pdf", "source_type": "pdf", "status": "pending", "folder_id": "f-1", "already_existed": false}
```

- `already_existed: true` cuando el mismo contenido ya estaba en el dominio, en cualquier carpeta
  (INV-6); se devuelve el documento existente sin volver a procesarlo.
- **400** tipo no soportado (solo `pdf`, `docx`, `txt`); **413** si supera `MAX_UPLOAD_MB`; **404**
  dominio o carpeta inexistente; **422** carpeta de otro dominio; **503** ingesta desactivada (como
  hoy).

## GET /domains/{domain_id}/documents (sin cambios)

Se sigue usando para sondear el estado de los documentos en proceso (INV-5). Suma `folder_id` a cada
documento.
