# Research: Eliminación de documentos

Decisiones de diseño con su razón y las alternativas. El qué y el por qué están en [spec.md](spec.md); aquí se decide el cómo. Todo lo que se afirma del código se verificó leyéndolo el 2026-10-26 (`src/mia/api/routes/domains.py`, `src/mia/ingestion/pipeline.py`, `src/mia/storage/vector_store.py`, `src/mia/storage/models.py`, `src/mia/api/routes/images.py`, `src/mia/usage/log.py`).

Las tres decisiones que la spec dejó al plan son R1 (el orden de la eliminación y qué pasa si falla), R3 (documentos que se están procesando) y R5 (la forma de la API).

## R0. Qué deja huella un documento (y por lo tanto qué hay que quitar)

| Dónde | Qué | Cómo se enlaza con el documento |
|---|---|---|
| Base SQL, `documents` | El registro (nombre, estado, huella de contenido `file_hash`, carpeta y dominio) | Es el documento |
| Base SQL, `document_images` | Sus imágenes asociadas, con el binario y el `public_id` del enlace público | Clave foránea `document_id`, **sin borrado en cascada** (como las demás tablas) |
| Qdrant | Sus fragmentos buscables, de donde salen las respuestas | Campo `document_id` del payload, **con índice** (`ensure_collection` lo crea) |
| Disco de la API | El archivo original, `uploads/<id>.<tipo>` | El id del documento |
| Base SQL, `queries` | El nombre de los documentos que cada consulta citó | **Solo el nombre** en un JSON (`sources`); no hay clave foránea |

Consecuencias: la detección de duplicados compara `file_hash` solo contra la tabla `documents` (`upload_document`), así que al borrar la fila desaparece la huella sin hacer nada más; el historial de Uso no tiene nada que migrar ni limpiar porque guarda nombres y no referencias; y lo único que hay que cuidar de verdad es **el almacén de vectores**, que vive en otro servicio y es lo que sigue respondiendo si se olvida.

## R1. Orden de la eliminación: la base en una transacción sin confirmar, después los fragmentos, y recién entonces confirmar

**Decision**: la eliminación hace, en este orden:
1. Dentro de **una transacción de la base sin confirmar**: borra las filas de `document_images` del documento y la fila del documento (`session.flush()`, sin `commit`).
2. Pide al almacén de vectores borrar los fragmentos del documento (por el campo `document_id`, con espera a que se aplique) y **comprueba que no queda ninguno** (`count_chunks == 0`).
3. Solo si el paso 2 salió bien, **confirma** la transacción.
4. Después, y sin que su falla cambie el resultado, borra el archivo original si existe y deja la línea de auditoría.

Si falla el paso 2 (o su comprobación), se hace `rollback`: el documento y sus imágenes siguen en la base como estaban, la persona recibe un aviso (503) y puede reintentar. Si fallara el `commit` del paso 3 después de que los fragmentos ya se borraron, el documento queda visible pero **sin fragmentos** (no responde nada); reintentar lo completa (borrar fragmentos que no existen no es un error).

**Rationale**:
- **Cumple FR-011 y FR-012 sin compensaciones raras.** Los dos almacenes no se pueden confirmar a la vez, así que se ordena para que el estado intermedio malo no exista: nunca hay un momento en que el documento esté fuera del inventario (confirmado) mientras sus fragmentos siguen respondiendo, porque la fila solo se confirma cuando los fragmentos ya no están. El estado intermedio que sí puede ocurrir (fragmentos borrados, fila visible) es inofensivo y se arregla reintentando.
- **Una sola eliminación de fragmentos por filtro** (`document_id`), que es una operación del almacén y no una por fragmento; un documento de 200 páginas son unos cientos de fragmentos, así que cabe de sobra en los 10 segundos de SC-004.
- **Reintentar es idempotente**: borrar por filtro lo que no existe no falla, y borrar una fila que ya no existe responde 404 (FR-005).
- **Las imágenes van en la misma transacción que el documento**: no hay que ordenar nada entre ellas (se confirman o se descartan juntas) y sus enlaces dejan de servir en el mismo instante en que la fila se confirma.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Borrar primero la fila y después los fragmentos | Si falla el almacén de vectores, el documento ya no está en el inventario pero sus fragmentos siguen respondiendo y citándose: exactamente el peor caso que pide evitar el principio de la spec. |
| Borrar primero los fragmentos y después la fila, cada paso con su `commit` | Si falla la base tras borrar los fragmentos, queda un documento visible sin contenido (inofensivo), pero se pierde la ventaja de poder descartar las imágenes junto con el documento y se necesitan dos transacciones. |
| Marcar el documento como "eliminando" y borrar en segundo plano | Más estados, más piezas y una pantalla que explicar, para un prototipo de un solo operador. La eliminación es rápida (R2) y se puede esperar. |
| Un borrado "blando" (columna `deleted_at`) | Obliga a filtrar los documentos borrados en cada consulta del sistema y deja los fragmentos vivos. No hay papelera por decisión de la spec. |

## R2. Eliminar fragmentos de Qdrant: un método nuevo del almacén, por filtro `document_id`

**Decision**: `VectorStore.delete_document(document_id)`, **no abstracto** (igual que los métodos de la feature 010: la clase base lanza `NotImplementedError`, y hay una subclase mínima en `tests/unit/test_vector_store_text.py` que no debe romperse). `QdrantVectorStore` lo implementa con `client.delete(collection_name, points_selector=FilterSelector(filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=...))])), wait=True)`. La ruta, además, comprueba con `count_chunks(document_id) == 0` (ya existe) antes de confirmar la base. Un almacén que no sabe eliminar hace que la ruta responda 503 y el documento quede intacto.

**Rationale**:
- Es el patrón de `set_domain` (que ya filtra por `document_id`) y de `count_chunks`; el campo tiene índice, así que Qdrant Cloud acepta el filtro.
- `wait=True` hace que al volver la llamada el borrado ya esté aplicado: una consulta posterior no ve los fragmentos (SC-001).
- La comprobación con `count_chunks` es barata y convierte "el almacén respondió OK" en "de verdad no queda ninguno", que es lo que promete FR-007.
- La interfaz sigue siendo intercambiable (principio II de la constitución): otro almacén implementaría el mismo método.

**Alternatives considered**: borrar por ids de fragmentos (hay que leerlos primero y son muchas llamadas); recrear la colección (destruye todo); marcar los fragmentos como inactivos en el payload (siguen ocupando espacio y habría que filtrarlos en cada búsqueda).

## R3. Documentos que se están procesando: señal de cancelación, espera acotada y guardas en la ingesta

**Decision**: por estado del documento al pedir eliminarlo:

| Estado | Qué hace la eliminación |
|---|---|
| `done` o `error` | Ninguna ingesta lo toca: elimina directo (R1). |
| `pending` (en cola) | Marca el documento como cancelado en una lista en memoria (`pipeline.request_cancel`) y elimina (R1). Cuando le toque a su ingesta, no hace nada: la fila ya no existe (la ingesta ya tiene esa guarda: `if document is None: return`) o está cancelado. |
| `processing` | Marca el cancelado y **toma el cerrojo de ingesta** (`_ingest_lock`, el mismo que serializa las ingestas) con una espera máxima (`DELETE_WAIT_SECONDS`, 60 s). La ingesta en curso ve la marca en el siguiente lote de 64 fragmentos (segundos), se detiene y suelta el cerrojo; la eliminación sigue (R1) con el cerrojo tomado, así que nada se escribe mientras borra. Si no consigue el cerrojo en ese tiempo, responde 409 `document_busy` y no toca nada. |

La ingesta (`pipeline.py`) gana tres guardas, que valen también si la eliminación ocurre en **otra instancia** de la API contra las mismas bases (por ejemplo, una API local de carga masiva apuntando a producción):
1. **Al empezar y antes de cada lote:** si el documento está en la lista de cancelados, o su fila ya no existe (consulta fresca), se detiene.
2. **Al detenerse por cancelación o por fila ausente:** borra los fragmentos que hubiera escrito (`delete_document`) y no toca el estado de un documento que ya no existe (hoy `document.status = ...; session.commit()` sobre una fila borrada falla con `StaleDataError`).
3. **Al terminar:** vuelve a comprobar que la fila existe; si no, borra los fragmentos que acaba de escribir.

**Rationale**:
- Es lo mínimo que cumple FR-014 en el caso de un solo proceso (el del despliegue real, una instancia de Railway) con determinismo: tomar el cerrojo garantiza que la ingesta de ese documento no está escribiendo mientras se borra.
- **Esperar al cerrojo es corto**: lo tiene la ingesta de *este* documento, que se detiene en el siguiente lote. Por eso `pending` no lo toma (esperaría a que termine otro documento, minutos, sin necesidad: su ingesta todavía no empezó, y si empieza justo en ese momento la guarda del lote la detiene).
- **Las guardas de la ingesta son la red de seguridad entre instancias** (donde no hay memoria ni cerrojo compartidos): como cada lote y el final comprueban la base, y la limpieza es idempotente, un documento eliminado desde otra instancia no deja fragmentos al terminar. No es determinista al 100 % (una carrera de milisegundos entre dos procesos puede dejar fragmentos hasta que la ingesta se entere), por eso se documenta como límite conocido y la comprobación `count_chunks` de R2 cubre el caso común.
- No agrega estados ni columnas (no hay migración).

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Rechazar (409) la eliminación de todo documento en cola o procesándose | Un documento subido por error y todavía en cola, o uno que lleva minutos procesándose, no se podría quitar hasta que termine: justo el caso de "me equivoqué de archivo". La spec pide poder eliminarlos (FR-013). |
| Esperar siempre al cerrojo | Para un documento en cola obligaría a esperar a que termine otro, que puede ser grande y tardar minutos, con la petición HTTP abierta. |
| Estado nuevo `deleting` en la base, visible para todas las instancias | Cierra también la carrera entre instancias, pero agrega un estado, una migración o una convención nueva y una pantalla; no se justifica con una sola instancia en producción. |
| Cerrojos de fila (`SELECT ... FOR UPDATE`) | No funciona igual en SQLite (desarrollo) y Postgres, y habría que mantener la fila bloqueada durante cada llamada a Qdrant. |

## R4. Imágenes, archivo original y enlaces públicos

**Decision**: las imágenes se borran con el documento, en la misma transacción (R1). Su enlace `GET /media/{public_id}` responde 404 desde la confirmación, porque la ruta consulta la base en cada petición. El archivo original (`uploads/<id>.<tipo>`) se borra después de confirmar, con `unlink(missing_ok=True)`; si falla (permisos, disco), se registra un aviso y la eliminación **no** falla: no cambia lo que responde el sistema.

**Rationale**: `DocumentImage` no tiene `ondelete`, así que hay que borrarlas explícitamente antes que la fila del documento. El archivo es lo único que no es transaccional: ponerlo después de confirmar evita borrar un archivo de un documento que acabó sin eliminarse, y los despliegues (Railway) no lo conservan de todos modos.

**Límite conocido** (se documenta): una imagen servida ya queda en las cachés externas (Kapso, Meta, navegadores) hasta una hora (`Cache-Control: public, max-age=3600`, feature 011); el enlace deja de servir en el origen al instante, pero una caché puede seguir mostrándola ese tiempo.

## R5. La forma de la API: una ruta por documento y una de lote

**Decision**:
- `DELETE /domains/{domain_id}/documents/{document_id}` → **204** si se eliminó. Cabe en el patrón de las rutas de documentos (`/domains/{id}/documents`). 404 si el dominio o el documento no existen o el documento no es de ese dominio (FR-005); 403 `out_of_scope` si el alcance no alcanza (con el rechazo en el registro de administración, como `document.upload`); 401 sin credenciales (una clave de artefacto no sirve: usa `require_admin`, FR-019); 409 `document_busy` y 503 con los mensajes de [contracts/eliminar-documentos-api.md](contracts/eliminar-documentos-api.md).
- `POST /documents/bulk-delete` con `{"document_ids": [...]}` (hasta 100) → **200** con el resultado de cada documento (`deleted`, `not_found`, `out_of_scope`, `busy` o `error`) y los totales. Cada documento se valida con su propio alcance (el dominio sale del documento, así que una selección puede cruzar dominios, spec historia 7 escenario 4) y se elimina por separado con el mismo servicio: uno que falla no impide los demás (FR-023).
- Ambas dejan la línea `document.delete` en el registro de administración por cada documento eliminado (FR-018).
- Las dos rutas viven en un archivo nuevo, `src/mia/api/routes/documents.py`, y el servicio de eliminación en `src/mia/ingestion/removal.py`, para que `domains.py` (que ya es largo) no crezca y el servicio se pueda probar sin HTTP.

**Rationale**: `DELETE` por documento es lo que cualquiera espera de una API y lo que usarán los scripts (FR-002). La ruta de lote existe porque el panel manda una selección de una vez con una sola confirmación, y un `DELETE` con cuerpo no es portable. CORS ya permite `DELETE` y `POST` (`CORS_ALLOW_METHODS`), así que no hay que tocar nada.

**Alternatives considered**: `POST /domains/{id}/documents/delete` por dominio (obliga a agrupar la selección por dominio en el cliente y a repetir la confirmación); `DELETE` con cuerpo (muchos clientes y proxies lo descartan); que el panel llame al `DELETE` de uno en uno (N peticiones, resultados parciales que el cliente tiene que ordenar, y ningún lugar donde registrar el lote como un todo).

## R6. El panel: botón por documento, modo de selección y una confirmación que dice qué se pierde

**Decision**: en el Inventario (`web/admin/src/modules/inventario/`):
- Cada fila de documento gana un botón **"Eliminar"** (ícono de papelera con nombre accesible `Eliminar <archivo>`), junto al de "Imágenes".
- Un botón **"Seleccionar"** en la parte de arriba activa un **modo de selección**: cada fila muestra una casilla, aparece una barra "N seleccionados: Eliminar seleccionados / Cancelar" y los botones por fila se mantienen. Salir del modo o terminar una eliminación limpia la selección.
- Una sola ventana de confirmación (`EliminarDocumentosDialog`) para uno o varios documentos: lista los nombres (hasta 10 y "y N más"), dice cuántas imágenes asociadas tienen en total (sale de `image_count` del inventario) y advierte que **se pierden el documento, sus imágenes y su contenido en las respuestas de todos los artefactos, incluido el bot de WhatsApp, y que no se puede deshacer; para recuperarlo hay que volver a subir el archivo original y asociar de nuevo las imágenes**. El botón de confirmar es de acción destructiva y dice "Eliminar" (o "Eliminar N documentos"); cancelar o cerrar no hace nada.
- El resultado se muestra en la misma ventana: éxito (se cierra y el inventario se actualiza), o el motivo de lo que falló (alcance, ocupado, error del almacén) con un botón de reintentar; en un lote, los eliminados quedan eliminados y se nombran los que fallaron.
- No hay permiso nuevo ni entrada de menú nueva: el botón lo ven todas las personas con acceso al Inventario y la API hace cumplir el alcance.

**Rationale**: sigue el patrón de los diálogos existentes (Mantine `Modal`, hooks de TanStack Query, `Notice`) y las reglas de `web/admin/README.md`. Un modo de selección evita llenar el árbol de casillas cuando solo se quiere eliminar uno. La confirmación única para uno o varios mantiene una sola pieza de interfaz y un solo texto que probar.

**Alternatives considered**: casillas siempre visibles (ruido para el caso común de uno solo); eliminar sin selección múltiple (la spec la pide, aunque sea de prioridad menor); un permiso aparte para eliminar (la spec dice que no se crea).

## R7. Historial de Uso y consultas pasadas

**Decision**: no se cambia nada. `QueryLog.sources` guarda `[{domain, document}]` con nombres, el detalle del módulo Uso los muestra tal cual y la exportación a CSV omite las fuentes; ninguna de esas partes consulta la tabla `documents`. Se agrega una prueba que demuestra que el listado, el detalle y el CSV de una consulta que citó un documento ya eliminado son idénticos a los de antes (FR-024, SC-008).

## R8. Volver a subir el mismo archivo y recuperar uno eliminado por error

**Decision**: nada que implementar para FR-020: `upload_document` detecta duplicados con `select(Document).where(domain_id, file_hash)`, y al borrar la fila la huella desaparece. Se agrega una prueba de subir, eliminar y subir el mismo contenido (debe responder 201 y no `already_existed`) y, en otro dominio, lo mismo. Para FR-021 se documenta en `docs/OPERACION.md` cómo se recupera un documento eliminado por error: **volver a subir el archivo original** (el panel o `scripts/cargar_carpeta.py`), asociar de nuevo sus imágenes y recordar que el sistema no conserva el archivo (Railway no persiste `uploads/`): quien administra debe tener el original.

## R9. Pruebas y verificación

**Decision**:
- **API** (`tests/unit/`): `test_documents_delete.py` (la ruta: 204, 404, alcance con auditoría y rechazo, claves de artefacto, imágenes y enlaces, archivo, huella para volver a subir, inventario y contadores), `test_removal.py` (el servicio con un almacén de vectores simulado: orden, falla del almacén con `rollback` y reintento, falla del `commit` con fragmentos ya borrados, idempotencia, `count_chunks` distinto de cero, archivo ausente), `test_ingestion_cancel.py` (los tres estados: en cola, procesando con la ingesta detenida en un lote, y fila ausente al terminar, con fragmentos limpiados), `test_documents_bulk_delete.py` (lote, fallos parciales, alcance por documento, duplicados en la lista y tope de 100), y una prueba de Uso de que el historial no cambia.
- **Almacén** (`tests/unit/test_vector_store.py`): `delete_document` arma el filtro por `document_id` y espera; y una prueba de **integración** contra un Qdrant local (`tests/integration/test_delete_document_qdrant.py`, se omite sola sin Qdrant) que sube fragmentos de dos documentos, elimina uno y comprueba que solo se fue ese.
- **Panel** (Vitest): utilidades de selección y de los textos de la confirmación, y la ventana con uno y con varios documentos, con y sin fallos.
- **De punta a punta** (`tests/unit/test_bot_end_to_end.py` ampliado o prueba nueva): un documento citado por el bot de WhatsApp, eliminado, y la pregunta siguiente responde "sin información" (SC-001 con el artefacto más sensible).
- **Manual** ([quickstart.md](quickstart.md)): el recorrido local con Qdrant en Docker y, con la autorización del usuario, la eliminación de los documentos de prueba del bot en producción.

## R10. Riesgos abiertos

| Riesgo | Qué se hace |
|---|---|
| Eliminar desde una instancia mientras otra (una API local de carga masiva contra producción) procesa el mismo documento | La ingesta comprueba la base en cada lote y al terminar y limpia lo que escribió si el documento ya no existe (R3). Queda una carrera de milisegundos entre procesos, documentada como límite conocido. |
| El almacén de vectores no responde al eliminar | La base se descarta con `rollback` y el documento sigue como estaba; 503 con un mensaje que dice que reintente (R1). |
| Cachés externas siguen mostrando una imagen hasta una hora | Documentado (R4); el origen deja de servirla al instante. |
| Un error al eliminar un documento equivocado | No hay deshacer: la confirmación lo dice, y se recupera subiendo el archivo original (R8). |
| `uploads/` no persiste en Railway | La eliminación del archivo es de mejor esfuerzo y no falla si no existe (R4). |
| El cerrojo de ingesta lo tiene otra ingesta larga cuando se pide eliminar un documento `processing` | Espera acotada de 60 s y 409 con "intenta de nuevo", sin tocar nada (R3). |
