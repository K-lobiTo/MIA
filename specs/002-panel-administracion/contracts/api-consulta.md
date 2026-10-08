# Contrato: Consulta con clave de artefacto

Cambios en las rutas que usan los artefactos de consulta. El encabezado es
`X-Artifact-Key: mia_...`.

## Orden de validación de una consulta

1. Sin clave o clave que no corresponde a ningún artefacto: **401** (no se registra).
2. Artefacto desactivado: **403** `"Este artefacto está desactivado."` (se registra como
   `rejected_permission`).
3. Modo no permitido al artefacto, o modo no disponible en la instancia: **403**.
4. Algún dominio pedido fuera de los permitidos: **403** indicando cuáles.
5. Topes, en este orden: toda la API, total del artefacto, modo con razonamiento del artefacto:
   **429** con el tope alcanzado y la hora de reinicio (se registra como `rejected_cap`).
6. Búsqueda y respuesta como hoy (spec 001). Fallo del proveedor: **502** (se registra como `error`).

## GET /config (nueva)

Sin clave:

```json
{
  "ingestion_enabled": true,
  "max_upload_mb": 25,
  "modes": [
    {"id": "literal", "name": "Literal", "description": "Lo que dice exactamente un documento.", "available": true, "reason": null},
    {"id": "razonamiento", "name": "Con razonamiento", "description": "Combina, compara y calcula datos de varios documentos.", "available": false, "reason": "La instancia no tiene configurado un modelo para este modo."}
  ]
}
```

Con `X-Artifact-Key` (401 si es inválida): solo los modos permitidos al artefacto, más:

```json
{
  "artifact": {"name": "Consulta administrativa Postgrados Computación", "active": true},
  "caps": {"cap_reached": false, "reasoning_cap_reached": false, "global_cap_reached": false, "resets_at": "2026-10-10T06:00:00Z"}
}
```

Un modo cuyo tope se alcanzó figura con `available: false` y `reason` (CON-3).

## GET /domains (cambia)

Con `X-Artifact-Key`: solo los dominios permitidos, con `unit_id` y `unit_name` para agruparlos.

## POST /query (cambia)

Request:

```json
{"domains": ["d-1", "d-2"], "question": "...", "mode": "literal"}
```

`mode` es opcional (`literal` por defecto). Respuesta:

```json
{
  "id": "q-1",
  "answer": "...",
  "sources": [{"domain": "...", "document": "...", "excerpt": "..."}],
  "mode": "literal",
  "latency_ms": 2140
}
```

El cuerpo de 403 y 429 es `{"detail": "<motivo legible>"}`; 429 incluye además el encabezado
`Retry-After` (segundos hasta la medianoche de los topes).

## POST /query/{query_id}/feedback (nueva)

Encabezado `X-Artifact-Key` del mismo artefacto que hizo la consulta. Request
`{"rating": "util" | "no_util", "comment": "opcional"}`. **204**. **404** si la consulta no existe o
es de otro artefacto. Una segunda calificación reemplaza la anterior.

## Compatibilidad

- `scripts/pruebas_mvp.py` y `scripts/cliente.py` reciben `--clave` (o `MIA_ARTIFACT_KEY`) y envían
  `X-Artifact-Key`.
- El cliente web actual (`web/`) agrega un campo para la clave y la envía; se reemplaza por la
  Consulta administrativa en su propia especificación.
