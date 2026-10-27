# Data Model: Eliminación de documentos

Esta feature **no agrega tablas, columnas ni migraciones**. Solo define qué se borra, dónde y en qué orden. Las decisiones están en [research.md](research.md) (R0 a R4).

## Qué se borra al eliminar un documento

| Dónde | Qué | Cómo se borra | Quién lo ve |
|---|---|---|---|
| SQL, `document_images` | Todas las imágenes del documento (con su binario y su `public_id`) | `DELETE` explícito por `document_id` (no hay cascada), dentro de la transacción | El enlace `GET /media/{public_id}` responde 404 al confirmar |
| SQL, `documents` | La fila del documento (con su `file_hash`) | `DELETE`, en la misma transacción | El Inventario deja de listarlo; la detección de duplicados deja de bloquear el mismo archivo |
| Qdrant | Todos los fragmentos con `document_id` igual al del documento | `VectorStore.delete_document` (filtro por `document_id`, `wait=True`) y comprobación con `count_chunks == 0` | Ninguna consulta nueva puede recuperar ni citar el documento |
| Disco | `UPLOAD_DIR/<id>.<tipo>` | `unlink(missing_ok=True)` después de confirmar, de mejor esfuerzo | Nadie (no se sirve) |

## Qué no se toca

| Dónde | Por qué |
|---|---|
| SQL, `queries` (historial de Uso) | Guarda `sources` como JSON de nombres, sin clave foránea: el historial no se reescribe y sigue mostrando el nombre del documento citado (FR-024). |
| SQL, `domains`, `folders`, `artifacts`, `bots` | El dominio y la carpeta siguen existiendo aunque queden sin documentos (FR-025). Los accesos de los artefactos son por dominio, no por documento. |
| Registro de administración (`mia.admin`) | Gana una línea `document.delete` por documento (ver contratos), no cambia su formato. |

## Orden y estados de la eliminación

```text
transacción abierta
  1. borrar document_images del documento
  2. borrar la fila Document          (flush, sin commit)
  3. vector_store.delete_document     (Qdrant, wait=True)
  4. count_chunks(document_id) == 0   (si no: rollback y 503)
  5. commit
despues del commit
  6. borrar archivo original (mejor esfuerzo)
  7. línea document.delete en mia.admin
```

| Falla en | Estado que queda | Qué ve la persona | Reintento |
|---|---|---|---|
| Paso 3 o 4 (almacén de vectores) | `rollback`: el documento, sus imágenes y sus fragmentos como estaban (o con algunos fragmentos menos si el borrado fue parcial) | 503 y el documento sigue en el Inventario | Seguro: borrar lo que no existe no falla |
| Paso 5 (commit tras borrar fragmentos) | Documento visible **sin fragmentos** (no responde nada) | 503 | Seguro: completa el borrado |
| Paso 6 (archivo) | Eliminado de verdad; queda un archivo suelto en disco | 204 (se registra un aviso) | No hace falta |

## Documentos que se están procesando

La cancelación no tiene columna ni estado nuevo: vive en la memoria del proceso de la API.

| Elemento | Detalle |
|---|---|
| `pipeline._cancelled` | Conjunto de `document_id` marcados para cancelar (protegido por un candado). `request_cancel(id)` agrega; `is_cancelled(id)` consulta; `clear_cancel(id)` quita al terminar de eliminar. |
| `_ingest_lock` | El cerrojo existente que serializa las ingestas; la eliminación lo toma para un documento `processing`, con espera máxima `DELETE_WAIT_SECONDS` (60 s). |
| Guardas de la ingesta | Antes de cada lote de 64 fragmentos y al terminar: si el documento está cancelado o su fila ya no existe (consulta fresca), se detiene, borra los fragmentos que escribió y **no** toca el estado de una fila inexistente. |

| Estado al pedir eliminar | Coordinación |
|---|---|
| `done`, `error` | Ninguna |
| `pending` | `request_cancel` y eliminar (la ingesta, cuando le toque, no encuentra la fila o ve la marca) |
| `processing` | `request_cancel` + tomar `_ingest_lock` (hasta 60 s) + eliminar; si no consigue el cerrojo, 409 `document_busy` sin tocar nada |

## Configuración

| Variable | Valor por defecto | Para qué |
|---|---|---|
| `DELETE_WAIT_SECONDS` | `60` | Espera máxima al cerrojo de la ingesta al eliminar un documento que se está procesando. Opcional: no hace falta ponerla en producción. |

## Interfaz del almacén de vectores

```python
class VectorStore:
    def delete_document(self, document_id: str) -> None:
        """Quita todos los fragmentos del documento. No falla si no hay ninguno."""
        raise NotImplementedError
```

No es abstracto (como los métodos de búsqueda por palabras de la feature 010): las implementaciones existentes y la subclase mínima de `tests/unit/test_vector_store_text.py` siguen funcionando. `QdrantVectorStore` lo implementa con `FilterSelector` sobre `document_id`; un almacén que no lo implementa hace que la eliminación responda 503 sin tocar la base.
