# Data Model: Pipeline de Ingesta y Consulta RAG

Extiende el modelo ya definido en `docs/Definicion_Requerimientos_MVP.md` (sección 5). Esta feature no
agrega entidades nuevas de metadata (SQL); solo hace real la escritura y lectura de la entidad `Chunk`
en Qdrant, y agrega transiciones de estado a `Document` que hoy solo tiene los estados posibles pero
nadie las dispara.

## Document (SQLite, ya existente)

Transiciones de estado que esta feature implementa (hoy `status` se crea en `pending` y nunca cambia):

```
pending --(pipeline de ingesta inicia)--> processing --(éxito)--> done
                                                        \-(falla)--> error
```

- **pending -> processing**: al iniciar la tarea en segundo plano.
- **processing -> done**: cuando todos los fragmentos del documento quedaron guardados en Qdrant.
- **processing -> error**: si el loader no puede extraer texto, o si falla el guardado en Qdrant.
  El motivo del error no se persiste en esta feature (fuera de alcance); alcanza con el estado.

## Chunk (Qdrant, payload)

Ya definido en el modelo general; esta feature fija el payload exacto que se escribe:

| Campo | Tipo | Notas |
|---|---|---|
| `document_id` | string | FK lógica a `Document.id` (SQLite) |
| `domain` | string | `Document.domain_id` (el identificador del dominio, no su nombre legible), campo filtrable en las búsquedas |
| `text` | string | contenido del fragmento |
| `chunk_index` | int | posición del fragmento dentro del documento, para ordenar si hace falta |

El vector de embedding es el vector nativo del punto en Qdrant, no un campo de payload.

## Consulta y Respuesta (no persistidas, solo forma de request/response)

Ya definidas en el contrato de `/query` (`docs/Definicion_Requerimientos_MVP.md` sección 6); ver
[contracts/api-query.md](contracts/api-query.md) para el comportamiento exacto que esta feature
implementa (incluyendo el caso de "sin información suficiente").
