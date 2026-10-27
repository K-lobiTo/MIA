# Implementation Plan: Eliminación de documentos de los dominios

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-eliminar-documentos/spec.md`

## Summary

Hoy un documento cargado en un dominio no se puede quitar: sigue alimentando las respuestas de todos los artefactos, incluido el bot de WhatsApp, y la única salida es tocar a mano la base y el almacén de vectores. Esta feature agrega la eliminación completa de un documento, desde la API y desde el Inventario del panel, con el mismo alcance que ya se tiene para subirlo.

Tres piezas:

1. **Un servicio de eliminación** (`src/mia/ingestion/removal.py`) que quita el documento de los tres lugares donde deja huella: la base SQL (la fila y sus imágenes), el almacén de vectores (todos sus fragmentos, con un método nuevo `VectorStore.delete_document`) y el disco (el archivo original, de mejor esfuerzo). El orden está pensado para que nunca exista un documento fuera del inventario con fragmentos que sigan respondiendo: la base se modifica dentro de una transacción sin confirmar, se borran y verifican los fragmentos, y recién entonces se confirma; si falla el almacén, se descarta la transacción y el documento queda como estaba ([research.md](research.md) R1 y R2).
2. **Rutas nuevas en la API** (`src/mia/api/routes/documents.py`): `DELETE /domains/{domain_id}/documents/{document_id}` y `POST /documents/bulk-delete` para eliminar varios (hasta 100), con el alcance por documento, línea `document.delete` en el registro de administración y resultado por documento ([contracts/eliminar-documentos-api.md](contracts/eliminar-documentos-api.md)).
3. **El panel**: botón "Eliminar" por documento, modo de selección para eliminar varios y una ventana de confirmación que dice qué se pierde y cómo se recupera ([contracts/panel-eliminar.md](contracts/panel-eliminar.md)).

Los documentos en cola o procesándose también se pueden eliminar: la eliminación marca la cancelación, toma el cerrojo de la ingesta con una espera acotada, y la ingesta gana guardas (por lote y al terminar) que la detienen y limpian lo que hubiera escrito si el documento ya no existe (R3). No hay migraciones: nada del esquema cambia. El historial de Uso no se toca (guarda nombres, no referencias), y volver a subir el mismo archivo funciona porque la huella desaparece con la fila (R7 y R8).

No usa LangChain ni LangGraph (decisión del 2026-10-21 en `docs/ARQUITECTURA.md`).

## Technical Context

**Language/Version**: Python 3.12 (API) y TypeScript con React y Mantine (panel)

**Primary Dependencies**: ninguna nueva. La API usa `qdrant-client` (ya presente: `FilterSelector` y `delete`), SQLAlchemy y FastAPI como hoy; el panel, Mantine y TanStack Query como hoy.

**Storage**: SQL de la API (SQLite en desarrollo, Postgres en producción) y Qdrant: **sin tablas ni migraciones nuevas**, ver [data-model.md](data-model.md). Se borran filas de `documents` y `document_images` y puntos de Qdrant por el campo `document_id` (con índice). Se borra el archivo original en `UPLOAD_DIR`.

**Testing**: `pytest` en `tests/unit/` (el servicio con un almacén simulado, las rutas con el patrón de `conftest.py`, la ingesta con cancelación), una prueba de integración contra un Qdrant local que se omite sola si no hay, Vitest para el panel ([quickstart.md](quickstart.md)).

**Target Platform**: los mismos despliegues de hoy (API en Railway, panel como sitio estático); sin servicios nuevos ni variables obligatorias.

**Project Type**: web-service (la API) y panel de administración (sitio web).

**Performance Goals**: un documento típico desaparece del inventario y de las respuestas en menos de 10 s (SC-004); un lote de 20 documentos en un tiempo razonable de una sola petición (cada documento es un borrado por filtro y una transacción corta).

**Constraints**: sin papelera ni deshacer (decisión de la spec); mismo alcance que subir, sin permiso nuevo (FR-016); una clave de artefacto no puede eliminar (FR-019); sin guiones largos en nada generado; reintentar una eliminación fallida es seguro (idempotente); la API local no debe dejar fragmentos si se elimina desde otra instancia mientras se ingesta (guardas de la ingesta, límite conocido documentado); no se agrega ninguna dependencia ni migración.

**Scale/Scope**: un operador y del orden de decenas a pocos cientos de documentos por dominio. Toca `src/mia/storage/vector_store.py` (método nuevo), `src/mia/ingestion/pipeline.py` (guardas y cancelación), `src/mia/ingestion/removal.py` (nuevo), `src/mia/api/routes/documents.py` (nuevo), `src/mia/api/main.py`, `src/mia/config.py` (espera del cerrojo), `web/admin/` (Inventario) y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. La eliminación es una operación de la API sobre el almacenamiento; los artefactos no cambian ni se enteran: dejan de ver el contenido por la consulta siguiente. |
| II. Pipeline modular e intercambiable | Cumple. Se agrega **un método a la interfaz `VectorStore`** (`delete_document`), no abstracto como los de la feature 010 para no romper implementaciones existentes, y la implementación de Qdrant queda detrás de la interfaz. Ninguna etapa del pipeline cambia de contrato. |
| III. Independencia de proveedor de LLM | Cumple. No interviene ningún modelo de lenguaje. |
| IV. Extensibilidad de dominios sin fricción | Cumple. Funciona para cualquier dominio sin configurarlo; el alcance sale de la regla que ya existe (`ensure_domain`). |
| V. Trazabilidad de respuestas | Cumple. Las consultas pasadas que citaron un documento conservan su nombre en el historial de Uso (FR-024); desde la eliminación, ninguna respuesta nueva puede citarlo. |
| Datos sensibles | Cumple y ayuda: permite retirar un documento que no debía estar (por ejemplo, con datos de personas) y cierra el hueco de que seguía respondiendo. |
| Stack base | Sin cambios: mismo Python, FastAPI, SQL, Qdrant y panel. |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA (servicio, rutas, método del almacén, guardas de la ingesta), OPERACION (cómo eliminar y cómo recuperar un documento eliminado por error) y `web/admin/README.md`. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. No hay migraciones, ni dependencias, ni variables obligatorias. El único punto delicado, la coordinación con una ingesta en curso, está acotado en R3 y tiene su límite conocido documentado (R10).

## Project Structure

### Documentation (this feature)

```text
specs/012-eliminar-documentos/
├── plan.md              # Este archivo
├── research.md          # Decisiones (R0 a R10)
├── data-model.md        # Qué se borra y dónde, estados y cancelación
├── quickstart.md        # Cómo validar la feature
├── contracts/
│   ├── eliminar-documentos-api.md   # DELETE por documento y bulk-delete
│   └── panel-eliminar.md            # Botón, selección y confirmación
└── tasks.md             # Lo genera /speckit-tasks (no este comando)
```

### Source Code (repository root)

```text
src/mia/
├── storage/vector_store.py       # + VectorStore.delete_document (no abstracto) y su implementación en Qdrant
├── ingestion/
│   ├── removal.py                # NUEVO: remove_document (orden de R1, espera del cerrojo, archivo, errores tipados)
│   └── pipeline.py               # + cancelación en memoria, guardas por lote y al terminar
├── api/
│   ├── routes/documents.py       # NUEVO: DELETE por documento y POST /documents/bulk-delete
│   └── main.py                   # registra el router nuevo
└── config.py                     # + DELETE_WAIT_SECONDS (60)

tests/
├── unit/
│   ├── test_removal.py                  # el servicio con almacén simulado
│   ├── test_documents_delete.py         # la ruta por documento
│   ├── test_documents_bulk_delete.py    # la ruta de lote
│   ├── test_ingestion_cancel.py         # en cola, procesando y fila ausente
│   ├── test_vector_store.py             # + delete_document arma el filtro (ampliado)
│   └── test_usage_after_delete.py       # el historial no cambia
└── integration/
    └── test_delete_document_qdrant.py   # contra Qdrant local (se omite sola)

web/admin/src/
├── api/documents.ts                      # NUEVO: hooks de eliminar uno y varios
└── modules/inventario/
    ├── TreeNode.tsx                      # botón "Eliminar" y casilla por documento
    ├── InventarioPage.tsx                # modo "Seleccionar" y barra de acciones
    ├── EliminarDocumentosDialog.tsx      # NUEVO: la confirmación y el resultado
    └── seleccion.ts                      # NUEVO: utilidades de selección y textos (con sus pruebas)

docs/ARQUITECTURA.md, docs/OPERACION.md, web/admin/README.md   # actualizados
```

**Structure Decision**: sin servicios ni paquetes nuevos; se agrega un módulo de servicio (`removal.py`) junto a la ingesta, que es con lo que tiene que coordinarse, y un archivo de rutas propio para no hacer crecer `domains.py`. El panel reutiliza el Inventario: no hay página nueva.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
