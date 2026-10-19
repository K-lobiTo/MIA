# Implementation Plan: Búsqueda híbrida (encontrar nombres y siglas por coincidencia de palabras)

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-busqueda-hibrida/spec.md`

## Summary

Una etapa léxica nueva en la recuperación de `POST /query`, apagada por defecto (`QUERY_HYBRID_SEARCH=off`). Con `on`, además de la búsqueda por significado (vectores) la API pregunta a Qdrant, con su **índice de texto** sobre el campo `text` de los fragmentos, qué fragmentos contienen cada palabra específica de la pregunta; una palabra es específica si aparece en pocos documentos (`HYBRID_MAX_DOCS`, 10 por defecto; se cuentan documentos y no fragmentos, research R4 y R16). Un fragmento que solo llegó por palabras pasa al modelo si contiene más de la mitad de las palabras específicas (regla acordada el 2026-10-19). Las dos listas se fusionan (Reciprocal Rank Fusion) con un tope de ranuras para los fragmentos que solo llegaron por palabras, y el resto del flujo (contexto, citas, respuestas completas, pregunta limpia, reranker) recibe la lista fusionada sin cambios. La parte léxica no llama a ningún modelo, no suma RAM a la API (el índice vive en Qdrant) y se ejecuta en un hilo en paralelo con la búsqueda por significado.

Las siglas se unen a su forma desarrollada con una **lista de equivalencias** (tabla `sigla_equivalences`, migración aditiva `0005`, semillas TFG y MGTI) que el operador mantiene desde una pantalla nueva del panel. Cada equivalencia convierte la palabra de la pregunta en un grupo de alternativas (`tfg` o `trabajo final de graduación`).

Preparar lo ya ingerido es crear el índice de texto en la colección existente: Qdrant lo construye sobre los puntos que ya tiene, sin recalcular vectores ni gastar tokens (1,5 s con los 6.239 fragmentos en la medición local), y los documentos nuevos entran al índice con el `upsert` normal de la ingesta (también cuando se ingiere desde la laptop). Se revierte quitando el índice; la versión anterior de la API ignora el índice.

**Evidencia previa a la implementación** (análisis de factibilidad del 2026-10-19 con una copia local de los 6.239 fragmentos de producción leídos en solo lectura, [research.md](research.md) R2 a R6): con el tokenizador por prefijo y la regla de la mayoría, los 11 casos objetivo (`S22-1` a `S22-4`, `EN1` a `EN6`, `EN10`) obtienen su documento como candidato léxico (casi siempre el único), y de los casos que esperan "sin información" solo `I1` recibe candidatos (17, y hoy ya llega al modelo). `SG3` (MGTI) muestra el límite: la sigla aparece en 42 fragmentos, sobre todo códigos de curso, y el documento esperado solo se distingue con el desempate por coseno. Es una simulación sin la parte de vectores ni la fusión: la calibración real es la tarea de medición.

## Technical Context

**Language/Version**: Python 3.12 (API FastAPI existente) y TypeScript con React y Mantine (panel)

**Primary Dependencies**: las existentes. `qdrant-client` ya instalado es 1.19.1 y el Qdrant de producción responde 1.19.1; se sube el piso de `pyproject.toml` a la primera versión que expone `TextIndexParams.ascii_folding` y `MatchTextAny` (se verifica en la primera tarea; hoy dice `>=1.10`). Sin dependencias nuevas de Python ni de npm.

**Storage**: (1) Qdrant: un índice de texto nuevo sobre el campo `text` de la colección, sin tocar vectores ni payload; (2) SQL (SQLite en desarrollo, Postgres en producción): una tabla nueva `sigla_equivalences` con la migración Alembic `0005`, solo aditiva ([data-model.md](data-model.md))

**Testing**: pytest (`tests/unit/`) con un almacén de vectores simulado que implementa los métodos léxicos, como `tests/unit/test_query_rerank.py`; pruebas de componentes y de utilidades del panel con Vitest; la verificación real es la corrida de la herramienta de la 005 contra un Qdrant local con el índice y en producción en solo lectura ([quickstart.md](quickstart.md))

**Target Platform**: API en Railway (se enciende solo para medir), Qdrant Cloud 1.19.1, panel como sitio estático; Qdrant local en Docker para desarrollo

**Project Type**: web-service (API) más el panel de administración (sitio web) y la herramienta de diagnóstico existente

**Performance Goals**: latencia añadida por la parte léxica y la fusión <= 0,2 s en p50 y 0,5 s en p95 (SC-007, confirmado el 2026-10-19); RAM de la API en reposo bajo 512 MB sin cambio (el índice vive en Qdrant); cero llamadas a modelos de lenguaje; un cambio de equivalencias se nota como máximo un minuto después

**Constraints**: apagado por defecto y reversible por variable (BUS-6); la migración es aditiva y el procedimiento de vuelta a `prototipo-v2-estable` queda documentado y probado (FR-021); estructura de la respuesta intacta; un fallo de la parte léxica (índice ausente, error de Qdrant, equivalencias no disponibles, tiempo agotado) nunca produce un error (FR-009); el filtro de dominios se aplica igual en las dos búsquedas (FR-004); con la opción apagada, o encendida pero sin candidatos léxicos, la lista de resultados es la de hoy; sin servicios externos nuevos

**Scale/Scope**: toca `src/mia/config.py`, `.env.example`, `src/mia/rag/lexical.py` (nuevo), `src/mia/rag/equivalences.py` (nuevo), `src/mia/storage/vector_store.py`, `src/mia/storage/models.py`, la migración `0005`, `src/mia/api/routes/equivalences.py` (nuevo), `src/mia/api/main.py`, `src/mia/api/routes/query.py`, `scripts/palabras.py` (nuevo), `scripts/copiar_coleccion.py` (nuevo), `scripts/linea_base.py`, `scripts/datos/casos_busqueda.json`, el panel (`web/admin/`) y la documentación

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. La búsqueda por palabras se pide al almacén por la misma API intermedia; ningún artefacto nuevo toca la infraestructura. Las equivalencias son de la API, no de un artefacto. |
| II. Pipeline modular e intercambiable | Cumple. Los métodos léxicos (`match_chunks`, `score_chunks`, `ensure_text_index`) se agregan a la interfaz `VectorStore` con implementación por defecto que lanza `NotImplementedError` (un almacén que no los tenga cae a significado con aviso), y la lógica pura (grupos, regla, fusión) vive en `mia.rag.lexical`, sin depender de Qdrant. Se enciende por variable (R11). |
| III. Independencia de proveedor de LLM | Cumple. No usa modelo de lenguaje, ni embeddings nuevos, ni servicio externo. |
| IV. Extensibilidad de dominios sin fricción | Cumple. Un dominio o documento nuevo queda en el índice con el `upsert` de siempre, sin migrar dominios existentes. |
| V. Trazabilidad de respuestas | Sin cambios: las fuentes siguen siendo las de los fragmentos que llegan al modelo (y las citas de la 006). La nota de Uso deja cuántos aportó la parte léxica. |
| Datos sensibles | Cumple. Los textos no salen a ningún servicio nuevo: el índice vive en el mismo Qdrant que ya los guarda. El filtro de dominio se aplica a la búsqueda léxica igual que a la de significado (FR-004). |
| Stack base | La tabla nueva de SQL y el índice de Qdrant no cambian ningún componente del stack; se actualiza `docs/ARQUITECTURA.md`. |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION (variables, preparación del índice, vuelta atrás, medición), V3 (D, 2.9), LINEA_BASE_BUSQUEDA y la guía del panel. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. Lo único que cruza la frontera de la feature es la migración `0005`, aditiva y con `downgrade`, tratada en R8; no se agregan dependencias ni llamadas a modelos de lenguaje.

## Project Structure

### Documentation (this feature)

```text
specs/010-busqueda-hibrida/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── busqueda-hibrida.md   # interfaz léxica, fusión, ruta /query, variables y notas de Uso
│   └── equivalencias-api.md  # rutas /equivalences del panel
└── tasks.md                  # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                          # + query_hybrid_search y hybrid_* (máximo de documentos, fragmentos por palabra, ranuras, tope de grupos, presupuesto)
├── rag/
│   ├── lexical.py                     # NUEVO: normalización, palabras vacías, grupos, regla de la mayoría, fusión (puro) y notas
│   └── equivalences.py                # NUEVO: lectura de la lista con caché de un minuto y su invalidación
├── storage/
│   ├── vector_store.py                # + match_chunks, score_chunks, ensure_text_index, text_index_status, drop_text_index
│   ├── models.py                      # + SiglaEquivalence
│   └── migrations/versions/
│       └── 0005_equivalencias_de_siglas.py   # NUEVO: tabla aditiva con semillas TFG y MGTI
└── api/
    ├── main.py                        # al arrancar con la opción encendida asegura el índice de texto; incluye el router nuevo
    └── routes/
        ├── equivalences.py            # NUEVO: GET/POST/PATCH/DELETE /equivalences (escritura solo global)
        └── query.py                   # hilo léxico en paralelo, fusión tras cada retrieve, caída a significado, notas

scripts/
├── palabras.py                        # NUEVO: estado / preparar / quitar el índice de texto (con --env-file)
├── copiar_coleccion.py                # NUEVO: copia una colección de Qdrant (con vectores) a un Qdrant local, origen en solo lectura
├── linea_base.py                      # candidatos léxicos y fusión en puntajes, comparar, informe, conteo de notas
└── datos/casos_busqueda.json          # + al menos 12 casos nuevos (FR-017)

web/admin/src/
├── api/equivalences.ts                # NUEVO: consultas y mutaciones
├── api/types.ts                       # + tipos de equivalencia
├── auth/capabilities.ts               # + canEditEquivalences
└── modules/
    ├── index.tsx                      # + entrada "Siglas y equivalencias"
    └── equivalencias/                 # NUEVO: EquivalenciasPage, formulario, utilidades y pruebas

tests/unit/
├── test_lexical.py                    # NUEVO: normalización, grupos, regla de la mayoría, fusión, notas
├── test_query_hybrid.py               # NUEVO: la ruta con la opción apagada, encendida, caída y combinada con 006 a 009
├── test_equivalences.py               # NUEVO: rutas, permisos, validación, caché, migración 0005
├── test_vector_store_text.py          # NUEVO: construcción de filtros y del índice sin Qdrant real
└── test_linea_base.py                 # + lo que se agrega a la herramienta

.env.example                           # + variables QUERY_HYBRID_SEARCH y HYBRID_*
docs/                                  # ARQUITECTURA, OPERACION, V3 (D, 2.9), LINEA_BASE_BUSQUEDA
web/admin/README.md                    # + el módulo nuevo
```

**Structure Decision**: la lógica pura (grupos, regla, fusión, notas) en `mia/rag/lexical.py`, igual que `rerank.py` y `query_rewrite.py`, sin importar Qdrant; el acceso a Qdrant queda detrás de la interfaz `VectorStore`. La ruta gana una función auxiliar `with_lexical(results)` que se aplica tras cada llamada a `retrieve` (la primera y la de la pregunta limpia de la 008), de modo que la fusión no sabe nada del reranker ni de la pregunta limpia. Las equivalencias van en SQL (no en variable de entorno ni en archivo) porque el panel las edita y el sistema de archivos de Railway es efímero.

Se descartan, con sus razones en [research.md](research.md) R1: vectores dispersos de Qdrant (reindexación de todos los puntos con vectores nuevos y pesos BM25 calculados por la API, más complejo y sin el recuento por palabra que pide la regla de la mayoría), un índice invertido en la memoria de la API (la ingesta corre en la laptop del usuario y el índice quedaría desactualizado; además consume la RAM que está al límite), búsqueda de texto completo en SQL (dos motores distintos entre SQLite y Postgres, y el texto duplicado), y un servicio externo de búsqueda (privacidad, costo).

## Complexity Tracking

Sin violaciones que justificar.
