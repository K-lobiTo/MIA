---

description: "Tareas de implementación de la feature 012: eliminación de documentos de los dominios (servicio de eliminación, rutas de la API, guardas de la ingesta y Inventario del panel)"
---

# Tasks: Eliminación de documentos de los dominios

**Input**: Design documents from `specs/012-eliminar-documentos/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/eliminar-documentos-api.md](contracts/eliminar-documentos-api.md), [contracts/panel-eliminar.md](contracts/panel-eliminar.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. El plan los exige (research R9) y la spec los pide como criterios de aceptación (SC-002, SC-006). Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Las pruebas de la API usan el patrón de `tests/conftest.py` (base SQLite por prueba, `TestClient`); las del servicio de eliminación y de la ingesta usan un almacén de vectores simulado (sin Qdrant); una sola prueba de integración usa un Qdrant local y se omite sola si no hay.

**Organization**: tareas agrupadas por historia de usuario (US1 a US8 de spec.md), precedidas por la base común. El orden de las fases sigue las dependencias y no solo la prioridad: US2 (la eliminación completa) es el servicio sobre el que se apoyan las demás; US3 le pone la ruta, el alcance y el registro; US1 le pone el panel; US4 agrega la coordinación con la ingesta; US5, US6 y US8 son sobre todo comprobaciones y documentación de lo ya construido; US7 (varios a la vez) cierra con la ruta de lote y la selección en el panel.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US8)
- **[USUARIO]**: lo hace el usuario, no quien implementa (despliegue, pruebas con gasto y eliminar en producción)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. **No desplegar, no encender servicios de Railway, no eliminar documentos en la base ni en el Qdrant de producción y no gastar cuota ni dinero** sin autorización del usuario. Las tareas marcadas [USUARIO] son del usuario.
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin dependencias nuevas** (`pyproject.toml`, `web/admin/package.json`) y **sin migraciones**: la cabeza de migraciones sigue en `0007` (ver [data-model.md](data-model.md): no cambia el esquema).
- **Los demás artefactos y las pruebas existentes no cambian** (FR-025, FR-026). `VectorStore.delete_document` **no es abstracto** (como los métodos de la feature 010): no se debe romper la subclase `Minimo(VectorStore)` de `tests/unit/test_vector_store_text.py`.
- El orden de la eliminación es el de research R1 y [data-model.md](data-model.md): primero la transacción de la base **sin confirmar**, después los fragmentos de Qdrant (con comprobación `count_chunks == 0`), y solo entonces el `commit`. Nunca confirmar la base antes de que los fragmentos hayan desaparecido.
- El registro de administración (`mia.admin`) nunca lleva el contenido del documento: solo `document.delete`, id, nombre y dominio.
- Frontend: seguir las reglas de [web/admin/README.md](../../web/admin/README.md#interfaz-mantine) (Mantine, tema de `src/theme.ts`, sin grises). La confirmación del panel es la de [contracts/panel-eliminar.md](contracts/panel-eliminar.md).
- Es un prototipo: lo más simple que cumpla la especificación.

---

## Phase 1: Setup

**Purpose**: la única variable de configuración nueva.

- [X] T001 Agregar `delete_wait_seconds: int = 60` (variable `DELETE_WAIT_SECONDS`, espera máxima al cerrojo de la ingesta al eliminar un documento que se está procesando) a `src/mia/config.py`, junto a las variables de ingesta, con un comentario en español; documentarla (opcional, valor por defecto 60) en `.env.example` y `deploy/railway/variables.example.env`, y agregar su caso (valor por defecto y lectura del entorno) a `tests/unit/test_config.py`

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: la operación del almacén de vectores sobre la que se apoya toda eliminación.

- [X] T002 [P] Pruebas del almacén en `tests/unit/test_vector_store.py` (ampliar): `QdrantVectorStore.delete_document(document_id)` llama al cliente con `FilterSelector` sobre un `Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=...))])` y `wait=True`; no falla si el documento no tiene fragmentos; la clase base `VectorStore.delete_document` lanza `NotImplementedError`; la subclase `Minimo` de `tests/unit/test_vector_store_text.py` sigue instanciándose (el método no es abstracto)
- [X] T003 Agregar `VectorStore.delete_document(self, document_id: str) -> None` en `src/mia/storage/vector_store.py` (no abstracto: `raise NotImplementedError`, con docstring "Quita todos los fragmentos del documento. No falla si no hay ninguno.") e implementarlo en `QdrantVectorStore` con `client.delete(collection_name, points_selector=FilterSelector(filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])), wait=True)`, igual que `count_chunks` y `set_domain`
- [X] T004 [P] Prueba de integración en `tests/integration/test_delete_document_qdrant.py`, con el patrón de `test_text_index_qdrant.py` (se omite sola sin Qdrant local): subir fragmentos de dos documentos, eliminar uno con `delete_document`, comprobar con `count_chunks` que solo se fue ese y que repetir la llamada no falla

**Checkpoint**: el almacén sabe borrar los fragmentos de un documento.

---

## Phase 3: US2 - La eliminación es completa y no deja nada a medias (P1)

**Goal**: un servicio que quita el documento de la base, de Qdrant y del disco en el orden seguro de research R1, con errores tipados que las rutas traducen a 404, 409 y 503.

**Independent Test**: `pytest tests/unit/test_removal.py`: elimina un documento con imágenes y archivo sin dejar restos; con el almacén fallando, el documento y sus imágenes siguen intactos y el reintento lo termina.

### Tests (primero, deben fallar)

- [X] T005 [P] [US2] Pruebas del servicio en `tests/unit/test_removal.py` con un almacén de vectores simulado (guarda los fragmentos en un diccionario y permite fallar a pedido) y una base SQLite de prueba: elimina la fila, las imágenes (`document_images`), los fragmentos y el archivo `UPLOAD_DIR/<id>.<tipo>`; el documento que no existe lanza `DocumentNotFound`; **orden**: el borrado de fragmentos ocurre con la fila ya borrada pero sin confirmar (en una sesión paralela el documento sigue visible hasta el commit); falla del almacén en `delete_document` o con `count_chunks != 0` tras borrar: `rollback` (documento e imágenes intactos) y `StoreUnavailable`, y el reintento con el almacén sano lo completa; falla del `commit` tras borrar los fragmentos: el documento queda visible sin fragmentos y reintentar lo completa; el archivo original ausente o con permiso denegado no hace fallar la eliminación; eliminar un documento no toca a otros del mismo dominio ni a uno con el mismo nombre en otro dominio

### Implementation

- [X] T006 [US2] Crear `src/mia/ingestion/removal.py`: excepciones `DocumentNotFound`, `DocumentBusy` y `StoreUnavailable`, y `remove_document(session, vector_store, document, upload_dir, wait_seconds) -> None` que (1) dentro de la transacción borra los `DocumentImage` del documento y la fila `Document` con `session.flush()` sin `commit`, (2) llama a `vector_store.delete_document(document.id)` y comprueba `count_chunks(document.id) == 0` (cualquier excepción o conteo distinto de cero: `session.rollback()` y `StoreUnavailable`; un almacén que lanza `NotImplementedError` también es `StoreUnavailable`), (3) `session.commit()`, (4) borra `upload_dir / f"{id}.{source_type}"` con `unlink(missing_ok=True)` capturando `OSError` con un aviso al registro, sin cambiar el resultado. La coordinación con la ingesta (espera del cerrojo, cancelación) se agrega en US4: dejar el punto de enganche como un parámetro opcional ya definido

**Checkpoint**: la eliminación completa existe y se prueba sin HTTP.

---

## Phase 4: US3 - El alcance se respeta y cada eliminación queda registrada (P1)

**Goal**: la ruta `DELETE /domains/{domain_id}/documents/{document_id}` con el mismo alcance que subir, rechazo registrado y línea `document.delete` por cada eliminación.

**Independent Test**: `pytest tests/unit/test_documents_delete.py`: una cuenta de programa elimina un documento propio y no uno ajeno, con las líneas del registro en cada caso.

### Tests (primero, deben fallar)

- [X] T007 [P] [US3] Pruebas de la ruta en `tests/unit/test_documents_delete.py` (patrón de `conftest.py`; usar el almacén simulado de T005 parcheando `get_vector_store` en el módulo de la ruta, como `patch.object(query_routes, "get_vector_store", return_value=...)` en `tests/unit/test_bot_service.py`): 204 y el documento ya no figura en `GET /inventory` (documento, contadores del dominio y carpeta); 404 con documento inexistente, con dominio inexistente y con un documento de otro dominio; repetir tras un 204 responde 404; **alcance**: una cuenta de programa elimina un documento de su programa, y para uno de otro programa recibe 403 `out_of_scope` y el documento, sus fragmentos y sus imágenes siguen intactos; una cuenta global elimina uno de un dominio sin programa; **auditoría** (capturar el logger `mia.admin`, como en `test_images.py`): una línea `document.delete` con `actor`, `target` = id, `detail` = `<archivo> en <dominio>` y `result` ok, sin contenido; el rechazo deja `document.delete` con `result` `rechazado`; sin credenciales 401; una clave de artefacto (encabezado `X-Artifact-Key`) responde 401, porque `require_admin` la ignora (no elimina); 503 `store_unavailable` con el documento intacto y el mensaje del contrato

### Implementation

- [X] T008 [US3] Crear `src/mia/api/routes/documents.py` con `DELETE /domains/{domain_id}/documents/{document_id}` (importar `get_vector_store` de `mia.storage.vector_store` y llamarlo dentro de la función, para que las pruebas lo parcheen por nombre): `require_admin`, buscar el dominio y el documento (404 si no existen o el documento no es del dominio, patrón de `_document()` de `src/mia/api/routes/images.py`), `ensure_domain(principal, domain, "document.delete")` (rechazo auditado), `remove_document(...)`, traducir `DocumentNotFound` a 404, `DocumentBusy` a 409 `document_busy` y `StoreUnavailable` a 503 `store_unavailable` con los textos de [contracts/eliminar-documentos-api.md](contracts/eliminar-documentos-api.md), `audit.log_write(principal, "document.delete", target=id, detail=f"{filename} en {domain.name}")` tras el éxito, y 204 sin cuerpo; registrar el router en `src/mia/api/main.py` (CORS ya permite `DELETE`)

**Checkpoint**: se puede eliminar un documento por la API con alcance y registro (MVP de la API).

---

## Phase 5: US1 - Quien administra elimina un documento desde el Inventario (P1)

**Goal**: el botón "Eliminar" por documento y la confirmación que nombra el documento, dice qué se pierde y que no se puede deshacer; el inventario se actualiza al terminar. Ya se construye la ventana para una lista de documentos, que reutiliza US7.

**Independent Test**: `npm test` en `web/admin`: la confirmación muestra los datos y los dos avisos, cancelar no llama a la API, confirmar llama a `DELETE` y refresca el inventario; y en el recorrido manual del [quickstart](quickstart.md) (pasos 1 a 6) la pregunta pasa a "sin información".

### Tests (primero, deben fallar)

- [X] T009 [P] [US1] Pruebas de utilidades en `web/admin/src/modules/inventario/seleccion.test.ts`: recortar la lista de nombres a 10 con `y N más`, sumar `image_count`, texto del título (`Eliminar documento` o `Eliminar N documentos`) y del botón (`Eliminar` o `Eliminar N documentos`), detectar si algún documento está en cola o procesándose (`pending` o `processing`) para la nota de cancelación, y el mensaje en lenguaje claro de cada motivo de fallo (`out_of_scope`, `busy`, `error`)
- [X] T010 [P] [US1] Pruebas de la ventana en `web/admin/src/modules/inventario/EliminarDocumentosDialog.test.tsx` (patrón de `ImagenesDialog`): con un documento muestra su nombre, su dominio, las imágenes que se pierden (se omite si son 0), el aviso del contenido en las respuestas de todos los artefactos incluido el bot de WhatsApp, el aviso de que no se puede deshacer con cómo recuperarlo (volver a subir el archivo original y asociar de nuevo las imágenes) y la nota de cancelación del procesamiento cuando corresponde; cancelar, Escape y la X no llaman a la API; confirmar llama a `DELETE /domains/{id}/documents/{id}` con el botón desactivado mientras tarda; un 404 se trata como eliminado (el inventario se recarga y no se muestra error); un 403, 409 o 503 deja la ventana abierta con el motivo y **Reintentar**; en `TreeNode.test.tsx` existe el botón con nombre accesible `Eliminar <archivo>`

### Implementation

- [X] T011 [P] [US1] Crear `web/admin/src/modules/inventario/seleccion.ts` con las funciones puras de T009 y el tipo `DocumentoAEliminar` (`id`, `filename`, `status`, `image_count`, `domain_id`, `domain_name`): `DocumentNode` de la API no trae el dominio, así que este tipo se arma en el panel con el contexto del árbol, sin cambiar la API
- [X] T012 [P] [US1] Crear `web/admin/src/api/documents.ts` con `useDeleteDocument()` (`DELETE /domains/{domain_id}/documents/{document_id}` con el cliente de `client.ts`; invalida las claves de `inventory` y `images` al terminar; trata el 404 como éxito) y los tipos de resultado que usa la ventana
- [X] T013 [US1] Crear `web/admin/src/modules/inventario/EliminarDocumentosDialog.tsx` (Mantine `Modal`, con el contenido y el comportamiento de [contracts/panel-eliminar.md](contracts/panel-eliminar.md): confirmación, estado en curso que impide cerrar, resultado y **Reintentar**, aviso de éxito con `Notice`), que recibe la lista de documentos a eliminar (uno o varios) y ya queda lista para US7
- [X] T014 [US1] Agregar el botón **Eliminar** (ícono de papelera, nombre accesible `Eliminar <archivo>`) a `DocumentRow` en `web/admin/src/modules/inventario/TreeNode.tsx`, junto al de Imágenes, y abrir la ventana desde `InventarioPage.tsx` con ese documento (tras eliminar, el inventario se actualiza por la invalidación del hook) Construir el `DocumentoAEliminar` con el `domain_id` y el nombre del dominio del nodo que contiene al documento (en una carpeta, el del dominio de esa carpeta).

**Checkpoint**: se elimina un documento desde el Inventario con confirmación.

---

## Phase 6: US4 - Se pueden eliminar documentos en cualquier estado (P2)

**Goal**: eliminar un documento en cola o procesándose sin que reaparezca ni deje fragmentos, sin afectar a los demás documentos de la cola (research R3).

**Independent Test**: `pytest tests/unit/test_ingestion_cancel.py`: los tres estados con el almacén simulado, y la ingesta de un documento procesándose se detiene sin fragmentos ni errores.

### Tests (primero, deben fallar)

- [X] T015 [P] [US4] Pruebas en `tests/unit/test_ingestion_cancel.py` (leer antes `src/mia/ingestion/pipeline.py` y `tests/unit/test_ingestion_pipeline.py` para reutilizar sus dobles de cargador, embeddings y almacén; el almacén se parchea con `patch.object(pipeline, "get_vector_store", ...)`): **en cola**: eliminar un documento `pending` y ejecutar su ingesta después no escribe fragmentos ni falla (la fila no existe); **procesando**: con una ingesta que va por lotes de 64 fragmentos, pedir la eliminación a mitad del procesamiento detiene la ingesta en el lote siguiente, `remove_document` espera el cerrojo, y al terminar no queda ningún fragmento ni fila; **fila ausente al terminar**: si la fila desaparece justo antes de marcar `done` o `error`, la ingesta borra los fragmentos que escribió y no lanza `StaleDataError`; **espera agotada**: si el cerrojo no se libera en `DELETE_WAIT_SECONDS` (usar uno de 0,1 en la prueba) lanza `DocumentBusy` y no toca la base ni los fragmentos; `done` y `error` se eliminan sin tocar el cerrojo; otros documentos en cola se procesan con normalidad (FR-015)

### Implementation

- [X] T016 [US4] En `src/mia/ingestion/pipeline.py` agregar el registro de cancelaciones en memoria (`_cancelled`, un conjunto protegido por un candado, con `request_cancel(id)`, `is_cancelled(id)` y `clear_cancel(id)`) y las guardas de la ingesta: antes de empezar y antes de cada lote de 64 fragmentos comprobar `is_cancelled(id)` o que la fila ya no existe (consulta fresca); si es así, borrar con `vector_store.delete_document` los fragmentos escritos y salir con `return` **sin tocar el estado** de un documento inexistente (el cerrojo lo suelta el `with` de `ingest_document`, no la función interna); antes de marcar `done` o `error` volver a comprobar que la fila existe y, si no, limpiar los fragmentos. Los dos `session.commit()` actuales (el de `status = "processing"` y el del `finally`) fallan con `StaleDataError` si la fila fue borrada en medio: capturar `sqlalchemy.orm.exc.StaleDataError` en ambos, hacer `rollback` y tratarlo como documento eliminado (limpiar fragmentos y salir). Mantener intacto el comportamiento del resto de la ingesta
- [X] T017 [US4] Completar `remove_document` en `src/mia/ingestion/removal.py` con la coordinación de research R3: documento `done` o `error` sin coordinación; `pending` con `request_cancel` y sin tomar el cerrojo; `processing` con `request_cancel` y toma de `_ingest_lock` con espera máxima `wait_seconds` (si no lo consigue lanza `DocumentBusy`, quita la marca y no toca nada); soltar el cerrojo y `clear_cancel(id)` al terminar (también ante errores)
- [X] T018 [US4] Pasar `settings.delete_wait_seconds` desde la ruta de `src/mia/api/routes/documents.py` a `remove_document` y agregar a `tests/unit/test_documents_delete.py` el caso 409 `document_busy` con el texto del contrato (documento `processing` con el cerrojo ocupado y una espera corta)

**Checkpoint**: se puede eliminar en cualquier estado sin restos.

---

## Phase 7: US5 - Eliminar desde la API, para scripts y automatizaciones (P2)

**Goal**: comprobar que la ruta sirve igual con la clave de automatización y dejar claro cómo usarla desde scripts.

**Independent Test**: `pytest tests/unit/test_documents_delete.py -k automation`.

- [X] T019 [P] [US5] Agregar a `tests/unit/test_documents_delete.py` los casos con la clave de automatización (encabezado de administración como en las demás pruebas): elimina con 204, la línea del registro lleva `actor` `automatizacion`, repetir responde 404, un documento que no pertenece al dominio indicado responde 404 sin tocar nada, y una cuenta de programa sigue rechazada fuera de su alcance
- [X] T020 [US5] Documentar en `docs/OPERACION.md` (sección nueva "Eliminar documentos") solo el uso de la ruta por documento por la API: un ejemplo de `curl -X DELETE` con la clave de automatización, los códigos de respuesta y que la API elimina al recibir la petición (la confirmación es del panel). La ruta de lote, el panel y los límites los completa T032

**Checkpoint**: la API se puede usar desde scripts con la misma garantía que el panel.

---

## Phase 8: US6 - Volver a subir el mismo archivo tras eliminarlo (P2)

**Goal**: la detección de duplicados no bloquea el archivo eliminado y queda documentado cómo recuperar uno eliminado por error.

**Independent Test**: `pytest tests/unit/test_documents_delete.py -k resubida`.

- [X] T021 [P] [US6] Agregar a `tests/unit/test_documents_delete.py` los casos de nueva subida: subir, eliminar y subir el mismo contenido al mismo dominio responde 201 con un id nuevo (no `already_existed`) y entra a la cola de ingesta; el mismo contenido en otro dominio se acepta como antes; el documento nuevo no hereda las imágenes del eliminado (`image_count` 0)
- [X] T022 [US6] Documentar en `docs/OPERACION.md` ("Eliminar documentos") cómo se recupera un documento eliminado por error: volver a subir el archivo original (panel o `scripts/cargar_carpeta.py`), asociar de nuevo sus imágenes, y que el sistema no conserva el archivo (`uploads/` no persiste en Railway), por lo que quien administra debe guardar los originales; incluir el límite de las cachés externas (una imagen ya servida puede verse hasta una hora)

**Checkpoint**: eliminar y volver a cargar una versión corregida funciona, y la recuperación está documentada.

---

## Phase 9: US7 - Eliminar varios documentos a la vez (P3)

**Goal**: la ruta de lote y, en el panel, el modo de selección con una sola confirmación y el resultado por documento.

**Independent Test**: `pytest tests/unit/test_documents_bulk_delete.py` y `npm test` en `web/admin`.

### Tests (primero, deben fallar)

- [X] T023 [P] [US7] Pruebas de la ruta de lote en `tests/unit/test_documents_bulk_delete.py`: elimina varios y devuelve `deleted`, `failed` y `results` en el orden recibido con el `status` de cada uno; los ids repetidos se cuentan una vez; un id inexistente da `not_found`; uno fuera de alcance da `out_of_scope` sin afectar a los demás (cuenta de programa con documentos de dos dominios); uno ocupado da `busy`; uno con falla del almacén da `error` y sigue intacto mientras los demás se eliminan; 422 con lista vacía, de más de 100 ids o con elementos que no son texto; 401 sin credenciales; una línea `document.delete` por cada eliminado y una `rechazado` por cada rechazo
- [X] T024 [P] [US7] Ampliar las pruebas del panel: en `seleccion.test.ts` alternar un documento, marcar un conjunto (incluida la casilla de carpeta o dominio) y quitar de la selección los eliminados; en `EliminarDocumentosDialog.test.tsx` la ventana con varios documentos llama a `POST /documents/bulk-delete` con los ids, un lote con fallos parciales lista solo los fallidos con su motivo y permite reintentarlos, y un `not_found` cuenta como eliminado y se menciona en el aviso final (`ya no existía`) sin tratarse como fallo; en `TreeNode.test.tsx` la casilla por documento solo aparece en modo de selección

### Implementation

- [X] T025 [US7] Agregar `POST /documents/bulk-delete` a `src/mia/api/routes/documents.py` con el cuerpo `{"document_ids": [...]}` (de 1 a 100, sin repetidos) y la respuesta del contrato: por cada documento, cargarlo, evaluar `ensure_domain(principal, su dominio, "document.delete")` capturando el rechazo, `remove_document` y la línea `document.delete`, traduciendo cada excepción a su `status` (`not_found`, `out_of_scope`, `busy`, `error`); un fallo no detiene a los demás
- [X] T026 [US7] Agregar `useBulkDeleteDocuments()` a `web/admin/src/api/documents.ts` (invalida `inventory` e `images`) y, en `EliminarDocumentosDialog.tsx`, usarlo cuando hay más de un documento, con el resultado por documento y el reintento de los fallidos de [contracts/panel-eliminar.md](contracts/panel-eliminar.md); `not_found` cuenta como eliminado (la spec pide informar que ya no existía: se menciona en el aviso final, no se muestra como error)
- [X] T027 [US7] Agregar a `web/admin/src/modules/inventario/InventarioPage.tsx` el botón **Seleccionar** (pasa a **Cancelar selección**), el estado de la selección (conjunto de ids) y la barra `N seleccionados` con **Eliminar seleccionados** (desactivado con 0) y **Cancelar**; en `TreeNode.tsx` la casilla por documento y la de carpeta o dominio (marca todos sus documentos visibles); salir del modo o terminar una eliminación limpia la selección, y los eliminados salen de ella

**Checkpoint**: se pueden eliminar varios con una sola confirmación.

---

## Phase 10: US8 - Lo demás no cambia (P1)

**Goal**: demostrar que eliminar un documento no toca el historial, los otros documentos ni los artefactos, ni siquiera con el bot de WhatsApp.

**Independent Test**: `pytest tests/unit/test_usage_after_delete.py tests/unit/test_bot_end_to_end.py` y la suite completa.

- [X] T028 [P] [US8] Pruebas en `tests/unit/test_usage_after_delete.py`: una consulta que citó un documento, ya eliminado, sigue idéntica en el listado, el detalle y el CSV del módulo Uso (con el nombre del documento citado); los otros documentos del dominio siguen con su estado y su inventario; las claves, los accesos, los modos y los topes de los artefactos no cambian; el dominio y la carpeta siguen existiendo vacíos y la carpeta vacía se puede borrar con la acción de siempre
- [X] T029 [P] [US8] Ampliar `tests/unit/test_bot_end_to_end.py` (o una prueba nueva junto a ella): un documento citado por el bot, eliminado, y la pregunta siguiente responde "sin información" sin fuentes ni imagen (SC-001 con el artefacto más sensible), y el enlace `/media/{public_id}` de su imagen responde 404
- [X] T030 [US8] Correr la suite completa (`pytest` y `ruff check src tests scripts whatsapp`) y comprobar que el resultado de las pruebas existentes no cambia respecto de la línea base de la 011 (1431 pasadas, 4 omitidas, más las nuevas)

**Checkpoint**: sin regresiones.

---

## Phase 11: Polish y documentación

- [X] T031 [P] Actualizar `docs/ARQUITECTURA.md`: el servicio de eliminación y su orden (research R1), `VectorStore.delete_document`, las dos rutas nuevas, las guardas de la ingesta y la cancelación en memoria (con el límite entre instancias), la variable `DELETE_WAIT_SECONDS` y que el historial de Uso conserva nombres
- [X] T032 [P] Completar `docs/OPERACION.md` ("Eliminar documentos"): el panel (botón, selección múltiple, qué dice la confirmación), qué se quita y dónde, los errores 409 y 503 y qué hacer, y los límites conocidos de research R10; agregar `DELETE_WAIT_SECONDS` a la lista de variables
- [X] T033 [P] Actualizar `web/admin/README.md` (Inventario): el botón Eliminar, el modo de selección y la confirmación, con los nombres de los archivos nuevos
- [X] T034 [P] En `docs/Definicion_Requerimientos_V2.md` (línea 127, lo que queda fuera de la V2, y línea 447, pendientes de administración del inventario) anotar que **borrar documentos** quedó resuelto por la feature 012 (con referencia a `specs/012-eliminar-documentos/`), dejando pendientes los demás (renombrar y mover documentos, reintentar, borrar dominios)
- [X] T035 Correr `cd web/admin && npm run typecheck && npm test && npm run build` y `pytest && ruff check src tests scripts whatsapp`; revisar con `grep -rnP "\x{2014}" specs/012-eliminar-documentos docs src tests web/admin/src` que no haya guiones largos nuevos
- [ ] T036 [USUARIO] Recorrer el [quickstart](quickstart.md) sección 2 en la laptop (con Qdrant local) y, cuando lo autorices, hacer el merge a `main` y el despliegue (`python scripts/servicios.py encender MIA --forzar` y el panel; sin migraciones)
- [ ] T037 [USUARIO] En producción, eliminar con el panel los documentos de prueba del bot (`Maestria_en_Ciberseguridad.txt` y `Maestria_en_Ciberseguridad_enfasis.txt` de "Apertura de promoción") y comprobar que el bot responde "sin información" a lo que antes respondía (quickstart sección 4)

---

## Dependencies & Execution Order

- **Setup (T001)** y **Foundational (T002 a T004)** primero; T002 y T004 se pueden escribir en paralelo antes de T003.
- **US2 (T005, T006)** depende de T003. **US3 (T007, T008)** depende de US2. **US1 (T009 a T014)** depende de T008 (la ruta `DELETE`) y es independiente de US4.
- **US4 (T015 a T018)** modifica `pipeline.py` y completa `removal.py`: depende de US2 y de US3 (para T018); puede hacerse en paralelo con el panel de US1.
- **US5 (T019, T020)** y **US6 (T021, T022)** dependen de US3 y se pueden hacer en paralelo con US1 y US4.
- **US7 (T023 a T027)** depende de US3 (ruta), de US1 (ventana y botones) y de US4 (estados `busy`).
- **US8 (T028 a T030)** y **Polish (T031 a T035)** al final; T036 y T037 son del usuario.

## Parallel Opportunities

- T002 y T004 (pruebas del almacén) en paralelo; T005 en paralelo con ellos.
- Panel y API en paralelo después de T008: T009 a T014 (US1) con T015 a T018 (US4) y T019 a T022 (US5 y US6).
- T009, T010, T011 y T012 (utilidades, pruebas y hooks del panel) entre sí.
- T023 y T024 (pruebas de US7) entre sí; T028 y T029 (US8); T031 a T034 (documentación).

## Implementation Strategy

- **MVP**: Phases 1 a 5 (T001 a T014): eliminar un documento listo desde el panel y la API, completo, con alcance y registro. Es lo que ya permite quitar los documentos de prueba del bot.
- **Segunda entrega**: US4 (cualquier estado, la parte más delicada), US5 y US6 (API y nueva subida).
- **Comodidad**: US7 (varios a la vez).
- **Cierre**: US8 y documentación; la medición con el bot real queda en T037 del usuario.

## Notes

- Los criterios de éxito se comprueban así: SC-001 en T029 y el quickstart; SC-002 en T005; SC-004 con el cronómetro del quickstart sección 3; SC-005 en T007; SC-006 en T005 y T015; SC-007 en T021; SC-008 en T028; SC-009 en T023 y T024; SC-010 en T030 (la batería del MVP con gasto, `python scripts/pruebas_mvp.py`, la corre el usuario si quiere confirmarla).

---

## Phase 12: Convergence

- [X] T038 Dejar en `error` un documento que estaba `processing` cuando su eliminación falla con `StoreUnavailable` (la ingesta ya se detuvo por la cancelación y el documento queda sin fragmentos y sin proceso, que el panel mostraría como "Procesando" para siempre): en `src/mia/ingestion/removal.py`, tras el `rollback` y mientras se sigue teniendo el cerrojo, poner `status = "error"` y confirmar solo si el estado era `processing` (no en `DocumentBusy`, donde la ingesta sigue viva, ni para `pending`, `done` o `error`); agregar a `tests/unit/test_ingestion_cancel.py` y `tests/unit/test_documents_delete.py` los casos "falla el almacén con el documento procesándose: queda `error`, visible y se puede reintentar la eliminación", "con el documento `done`: conserva `done`" y "con 409: conserva `processing`" per FR-011 (partial)
- [X] T039 Cubrir sin DOM lo que T010 prometía de la ventana de eliminación: extraer de `web/admin/src/modules/inventario/EliminarDocumentosDialog.tsx` a `web/admin/src/modules/inventario/seleccion.ts` la lógica de estado como funciones puras (qué documentos quedan pendientes tras un resultado, cuándo el botón dice `Reintentar`, y que un reintento con un solo documento usa la ruta por documento y con varios la de lote) y probar en `seleccion.test.ts` que cancelar o cerrar no invoca al eliminador, que confirmar con uno y con varios elige la ruta correcta, y que el reintento reenvía solo los fallidos per US1/AC2 (partial)

---

## Phase 13: Convergence

- [X] T040 Marcar `error` también cuando un documento que se leyó como `pending` falla con `StoreUnavailable` y la ingesta alcanzó a arrancar y detenerse por la cancelación (queda `processing` sin proceso): en `src/mia/ingestion/removal.py`, llamar a `_mark_error` en el `except StoreUnavailable` sin exigir `holds_lock` (el `UPDATE` ya filtra por `status == "processing"`, así que no toca a uno `pending`, `done` o `error`); agregar a `tests/unit/test_ingestion_cancel.py` el caso "documento `pending` cuya ingesta lo deja `processing` justo antes de que falle el almacén: queda `error` y se puede reintentar la eliminación" (usando el gancho `al_borrar` de `AlmacenFalso` para cambiar el estado en otra sesión) per FR-011 (partial)
- [X] T041 Documentar el cambio de T038: agregar a la tabla "Errores y qué hacer" de `docs/OPERACION.md` que un 503 sobre un documento que se estaba procesando lo deja en `error` (visible, sin fragmentos, se puede reintentar la eliminación o volver a subirlo), y a "Documentos en proceso" de `docs/ARQUITECTURA.md` la misma regla (`_mark_error` en `removal.py`) per FR-027 (partial)
