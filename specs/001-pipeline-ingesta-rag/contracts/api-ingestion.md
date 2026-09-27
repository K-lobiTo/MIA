# Contrato: Ingesta de documentos

Endpoint: `POST /domains/{domain_id}/documents` (ya existe; esta feature agrega el comportamiento de
indexación detrás de él, la forma de la petición y de `DocumentOut` no cambia).

## Comportamiento nuevo

1. Se guarda el archivo y se crea el registro `Document` con `status="pending"` (ya implementado).
2. Se dispara en segundo plano (`BackgroundTasks`) la indexación:
   - Cambiar `status` a `"processing"`.
   - Cargar el texto con el `DocumentLoader` correspondiente al `source_type`.
   - Si no se puede extraer texto (excepción del loader, o texto vacío): `status = "error"`, fin.
   - Trocear el texto con `chunk_text()`.
   - Generar embeddings de cada fragmento con el `EmbeddingProvider` configurado.
   - Guardar los fragmentos en Qdrant (`VectorStore.upsert()`) con su payload (`document_id`, `domain`,
     `text`, `chunk_index`).
   - Si todo lo anterior tiene éxito: `status = "done"`.
   - Si cualquier paso falla: `status = "error"`.
3. La respuesta HTTP del `POST` sigue siendo inmediata (no espera a que termine la indexación),
   devolviendo el documento en `status="pending"` como hoy.

## Deduplicación (ya implementada, sin cambios)

Si el hash del archivo ya existe en el dominio, se devuelve el documento existente sin crear uno nuevo
ni volver a indexar.
