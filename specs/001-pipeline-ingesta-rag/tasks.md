---

description: "Task list template for feature implementation"
---

# Tasks: Pipeline de Ingesta y Consulta RAG

**Input**: Design documents from `/specs/001-pipeline-ingesta-rag/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Organization**: Tareas agrupadas por historia de usuario (spec.md), para poder implementar y probar
cada una de forma independiente.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: a qué historia de usuario pertenece (US1, US2, US3)
- Cada tarea incluye la ruta de archivo exacta

## Phase 1: Setup

**Purpose**: preparar dependencias nuevas antes de tocar código de la feature

- [X] T001 Agregar `sentence-transformers` y `anthropic` a `dependencies` en `pyproject.toml`, y
  reinstalar el entorno (`pip install -e ".[dev]"`)
- [X] T002 [P] Agregar a `src/mia/config.py` y `.env.example` las variables nuevas:
  `ANTHROPIC_API_KEY`, `ANTHROPIC_EFFORT` (default `"medium"`), y un umbral de similitud más un
  límite de resultados para la búsqueda en Qdrant (ver `research.md` y `contracts/api-query.md`)

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: piezas que tanto la ingesta (US1) como la consulta (US2/US3) necesitan para funcionar

**⚠️ CRITICAL**: ninguna historia de usuario puede completarse sin esta fase

- [X] T003 [P] Implementar `LocalEmbeddingProvider` en `src/mia/rag/providers/local_embeddings.py`
  usando `sentence-transformers` con el modelo `intfloat/multilingual-e5-small` (decisión en
  `research.md`); exponer la dimensión del vector como atributo, la necesita T004 para crear la
  colección de Qdrant con el tamaño correcto
- [X] T004 Agregar lógica de bootstrap de la colección `mia_chunks` en
  `src/mia/storage/vector_store.py` (crearla si no existe, con el tamaño de vector de T003), invocada
  desde el `lifespan` de la app en `src/mia/api/main.py` (depende de T003)

**Checkpoint**: con Foundational completo, US1, US2 y US3 pueden implementarse

---

## Phase 3: User Story 1 - Un documento subido queda disponible para consulta sin pasos manuales (Priority: P1) 🎯 MVP

**Goal**: al subir un documento, su contenido queda indexado en Qdrant sin intervención manual, y su
estado refleja el progreso real.

**Independent Test**: Escenario 1 de `quickstart.md` (subir un acta, verificar que `status` pasa de
`"pending"` a `"done"` sin acción manual adicional).

### Implementation for User Story 1

- [X] T005 [US1] Implementar `QdrantVectorStore.upsert()` en `src/mia/storage/vector_store.py`:
  escribir cada `Chunk` como punto en `mia_chunks` con payload `document_id`, `domain`, `text`,
  `chunk_index` (ver `data-model.md`)
- [X] T006 [US1] Crear `src/mia/ingestion/pipeline.py` con la función que orquesta
  `DocumentLoader -> chunk_text() -> LocalEmbeddingProvider -> VectorStore.upsert()`, aplicando
  exactamente esta transición de estado de `Document` (verbatim de `data-model.md`):
  `pending --(inicia)--> processing --(éxito)--> done`, `processing --(falla)--> error`; si el loader
  no puede extraer texto (excepción o texto vacío) debe terminar en `error`, nunca dejar el documento
  indefinidamente en `pending` o `processing` (depende de T003, T005)
- [X] T007 [US1] Modificar `src/mia/api/routes/domains.py`: en `upload_document`, disparar la función
  de `pipeline.py` vía `BackgroundTasks` (parámetro `background_tasks: BackgroundTasks` en la ruta)
  justo después de crear el registro `Document`, sin bloquear la respuesta HTTP (depende de T006)
- [X] T008 [P] [US1] Test unitario del pipeline en `tests/unit/test_ingestion_pipeline.py`: caso de
  éxito (documento con texto válido termina en `"done"` y genera al menos un `Chunk`) y caso de
  documento sin texto extraíble (termina en `"error"`)
- [X] T009 [US1] Ejecutar el Escenario 1 de `quickstart.md` con un acta real y confirmar SC-001 (menos
  de 2 minutos hasta `"done"`)

**Checkpoint**: subir un documento ya lo deja disponible para búsqueda en Qdrant (sin exponer todavía
una forma de consultarlo en lenguaje natural, eso es US2)

---

## Phase 4: User Story 2 - Una pregunta sobre contenido real recibe una respuesta con su fuente citada (Priority: P1)

**Goal**: `POST /query` responde usando el contenido indexado y cita documento y dominio de origen.

**Independent Test**: Escenario 2 de `quickstart.md` (con un documento ya indexado, preguntar sobre su
contenido y verificar que la respuesta cita el documento y dominio correctos).

### Implementation for User Story 2

- [X] T010 [P] [US2] Implementar `AnthropicLLMProvider` en `src/mia/rag/providers/anthropic_llm.py`
  usando el SDK `anthropic`, modelo fijo `claude-sonnet-5` (nunca `claude-opus-5`, por instrucción
  explícita del usuario), `output_config={"effort": settings.anthropic_effort}` leyendo
  `ANTHROPIC_EFFORT` (default `"medium"`); el `system` prompt debe instruir explícitamente a responder
  únicamente con base en el contexto recibido
- [X] T011 [US2] Implementar `QdrantVectorStore.search()` en `src/mia/storage/vector_store.py`: buscar
  por el embedding de la pregunta, con filtro `domain in [...]` sobre los dominios recibidos, devolviendo
  `SearchResult` (incluye `score`) para cada punto encontrado (depende de T004)
- [X] T012 [US2] Implementar `POST /query` en `src/mia/api/routes/query.py` según
  `contracts/api-query.md`: embeber la pregunta con el `EmbeddingProvider` configurado, llamar a
  `VectorStore.search()`, armar el contexto con los resultados y pasarlo al `LLMProvider` configurado,
  devolver `answer` más `sources` (`domain`, `document`, `excerpt`) solo con los fragmentos
  efectivamente usados como contexto (depende de T010, T011)
- [X] T013 [P] [US2] Test unitario en `tests/unit/test_query_sources.py`: dado un conjunto de
  `SearchResult` de ejemplo, verificar que `sources` en la respuesta final solo incluye los fragmentos
  pasados como contexto, con `domain`/`document`/`excerpt` correctos
- [X] T014 [US2] Ejecutar el Escenario 2 de `quickstart.md` y confirmar SC-002 (cita correcta en al
  menos 9 de cada 10 intentos)

**Checkpoint**: US1 y US2 juntas ya cubren el flujo completo de ingesta y consulta con trazabilidad

---

## Phase 5: User Story 3 - El sistema reconoce cuándo no tiene información suficiente (Priority: P2)

**Goal**: si ningún fragmento indexado supera el umbral de similitud, responder sin inventar contenido.

**Independent Test**: Escenario 3 de `quickstart.md` (pregunta sobre un tema no cubierto por ningún
documento indexado).

### Implementation for User Story 3

- [X] T015 [US3] En `src/mia/api/routes/query.py`, agregar la rama de "sin información suficiente"
  antes de llamar al `LLMProvider`: si ningún `SearchResult` de T011 supera el umbral configurado en
  T002, devolver directamente la respuesta fija de `contracts/api-query.md`
  (`"No encontré información suficiente..."`, `sources: []`) sin llamar al LLM (depende de T012)
- [X] T016 [P] [US3] Test unitario en `tests/unit/test_query_no_info.py`: dado un conjunto de
  `SearchResult` todos por debajo del umbral, verificar que la respuesta es la fija con `sources`
  vacío y que no se invoca el `LLMProvider`
- [X] T017 [US3] Ejecutar el Escenario 3 de `quickstart.md` y confirmar SC-003 (100% de los casos sin
  información se reconocen como tal)

**Checkpoint**: las 3 historias de usuario del MVP quedan completas y verificables de forma
independiente

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T018 [P] Actualizar `docs/ARQUITECTURA.md`, sección "Qué funciona hoy vs. qué es interfaz sin
  implementar": mover embeddings, LLM, `VectorStore` y `/query` de la lista de stubs a la de
  funcionalidad real
- [X] T019 [P] Confirmar que `.env.example` quedó con todas las variables nuevas documentadas
  (`ANTHROPIC_API_KEY`, `ANTHROPIC_EFFORT`, umbral y límite de búsqueda)
- [X] T020 Ejecutar el Escenario 4 de `quickstart.md` (deduplicación) y confirmar SC-004
- [X] T021 Correr `pytest` completo y `ruff check src tests`, y corregir lo que falle

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias
- **US1 (Phase 3)**: depende de Foundational
- **US2 (Phase 4)**: depende de Foundational (no depende de US1, aunque en la práctica conviene
  probarla con un documento ya indexado por US1)
- **US3 (Phase 5)**: depende de US2 (T015 modifica el mismo archivo que crea T012, `query.py`); no es
  independiente a nivel de archivo aunque sí lo es a nivel de comportamiento observable
- **Polish (Phase 6)**: depende de que US1, US2 y US3 estén completas

### Parallel Opportunities

- T003 (embeddings) y el trabajo de Setup T002 pueden avanzar en paralelo
- T008 (test US1) es paralelo a T009 solo si T007 ya terminó
- T010 (`AnthropicLLMProvider`) es paralelo a todo T005-T009 de US1 (archivos distintos)
- T013 y T016 (tests unitarios) son paralelos entre sí una vez existan T012 y T015 respectivamente
- T018 y T019 (Polish) son paralelos entre sí

## Implementation Strategy

### MVP mínimo

1. Setup + Foundational (T001-T004)
2. US1 completa (T005-T009): ya se puede demostrar ingesta funcionando de punta a punta
3. US2 completa (T010-T014): MVP funcional completo (ingesta + consulta con cita), esto ya cumple el
   criterio de aceptación del MVP en `docs/Definicion_Requerimientos_MVP.md` sección 11
4. US3 (T015-T017): refuerzo de confiabilidad, no bloquea demostrar el MVP
5. Polish (T018-T021)

### Entrega incremental

Setup+Foundational → US1 (demo: subir e indexar) → US2 (demo: preguntar y recibir cita) → US3 (demo:
reconocer falta de información) → Polish.

---

## Phase 7: Convergence

Generado por `/speckit-converge` el 2026-09-26, tras cerrar T001-T021 y agregar `GeminiLLMProvider`
fuera del ciclo original de planificación. Ninguno de estos hallazgos bloquea las 3 historias de
usuario del MVP, ya verificadas funcionando de punta a punta; son deuda técnica real detectada al
comparar el código contra `spec.md`/`plan.md`/`data-model.md`/la constitución.

- [X] T022 CRITICAL: corregir `OpenAIEmbeddingProvider.embed()` en
  `src/mia/rag/providers/openai_embeddings.py` para que coincida con la interfaz real
  `EmbeddingProvider.embed(self, texts, is_query=False)` (`src/mia/rag/embeddings.py`) y exponga el
  atributo `dimension`, aunque el cuerpo siga lanzando `NotImplementedError`. Hoy, seleccionar
  `EMBEDDING_PROVIDER=openai` rompería con un `TypeError` antes de llegar al error intencional,
  violando el Principio II de la constitución (interfaz + factory intercambiable) per Constitution II
  (contradicts)
- [X] T023 HIGH: decidir e implementar cómo cerrar FR-008 por completo per FR-008 (partial).
  **Resuelto por enmienda, no por código** (2026-09-26): Constitución Principio III acotado a v1.1.0
  (renombrado "Independencia de Proveedor de LLM"), `spec.md` FR-008 y Assumptions actualizados. Los
  embeddings quedan local por diseño permanente (sin costo variable, sin exponer contenido a
  terceros, latencia insignificante frente al LLM); solo el LLM mantiene la exigencia de simetría
  local/comercial, ya satisfecha con `AnthropicLLMProvider` y `GeminiLLMProvider`.
  `OpenAIEmbeddingProvider` y `LocalLLMProvider` quedan como stubs intencionales, no como deuda
  pendiente.
- [X] T024 LOW: actualizar `plan.md`, sección "Primary Dependencies", para incluir `google-genai`
  (agregado como dependencia real junto con `GeminiLLMProvider` después de cerrado el plan original;
  ya documentado en `research.md` pero no en `plan.md`) per plan: Primary Dependencies (unrequested)
- [X] T025 LOW: corregir la descripción del campo `domain` en la tabla de `Chunk` en `data-model.md`:
  dice "nombre del dominio" pero la implementación real (`src/mia/ingestion/pipeline.py`,
  `src/mia/api/routes/query.py`) guarda y filtra por `document.domain_id` (el identificador, no un
  nombre legible) per data-model.md (contradicts)

---

## Phase 8: Convergence

Generado por `/speckit-converge` el 2026-09-26, tras resolver T022-T025. Un solo hallazgo, residual
de la propia enmienda del Principio III / FR-008 de la corrida anterior.

- [X] T026 LOW: agregar una `Assumption` en `spec.md` que aclare que `LocalLLMProvider`
  (`src/mia/rag/providers/local_llm.py`) es un stub intencional pendiente de disponibilidad de
  hardware propio, no una omisión. FR-008 sigue exigiendo textualmente que el LLM "DEBE poder
  configurarse... entre una opción local/auto-hospedada y una comercial", pero solo el lado
  comercial tiene implementaciones reales (`AnthropicLLMProvider`, `GeminiLLMProvider`); falta la
  misma aclaración explícita que ya se agregó para embeddings per FR-008 (partial)

---

## Phase 9: Convergence

Generado por `/speckit-converge` el 2026-09-26, tras resolver T026. Tres hallazgos, todos residuos de
documentación no sincronizada tras la enmienda del Principio III a v1.1.0; ninguno afecta código ni
comportamiento.

- [X] T027 LOW: actualizar la fila del Principio III en la tabla "Constitution Check" de `plan.md`
  (línea ~54): cita el nombre viejo "III. Independencia de proveedor de LLM y embeddings" (ahora
  "III. Independencia de Proveedor de LLM" en la constitución v1.1.0) y no menciona
  `GeminiLLMProvider` como segunda opción comercial per plan: Constitution Check (contradicts)
- [X] T028 LOW: corregir `contracts/api-query.md`: dice que `question` vacía o `domains` vacío
  devuelve "error de validación (400)", pero el comportamiento real verificado es HTTP 422
  (validación de Pydantic) per contracts/api-query.md (contradicts)
- [X] T029 LOW: corregir `research.md`, sección "Alternatives considered" del proveedor de
  embeddings: dice que un proveedor comercial "violaría el principio III... desde el arranque", cita
  vigente antes de la enmienda a v1.1.0; el Principio III ahora exceptúa explícitamente a los
  embeddings de esa exigencia per research.md (contradicts)
