---

description: "Tareas de implementación de la feature 014: memoria de conversación configurable por artefacto (historial en la consulta, reformulación de la búsqueda, panel, Consulta administrativa y memoria del bot)"
---

# Tasks: Memoria de conversación configurable por artefacto

**Input**: Design documents from `specs/014-memoria-conversacion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/query-historial-api.md](contracts/query-historial-api.md), [contracts/artefactos-memoria-api.md](contracts/artefactos-memoria-api.md), [contracts/bots-memoria-servicio.md](contracts/bots-memoria-servicio.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. La spec los pide (FR-026) y el plan los detalla (quickstart sección 1). Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Las pruebas de la API usan el patrón de `tests/conftest.py` y del almacén, embeddings y modelo simulados de `tests/unit/test_bot_clarify.py` y `test_bot_service.py`; las del servicio usan `httpx.MockTransport` y el reloj inyectable; las del panel y la Consulta, Vitest sin DOM (funciones puras y `renderToString`, como las existentes). Lo que depende del modelo real (SC-001 y SC-002) se mide con `scripts/medir_memoria.py`, no con proveedores simulados.

**Organization**: tareas agrupadas por historia de usuario (US1 a US8 de spec.md), precedidas por la base común. El orden sigue las dependencias y no solo la prioridad: la base son las variables, la migración, el historial puro y el mensaje al modelo; US2 (el parámetro y el panel) va antes de US1 (la consulta con historial y la Consulta) porque US1 lo lee; US3 (cambio de modo), US4 (memoria 0 igual), US5 (validación y privacidad), US6 (la estrategia con el modelo y la medición), US7 (costo) y US8 (memoria del bot) completan y verifican.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US8)
- **[USUARIO]**: lo hace el usuario, no quien implementa (despliegue, variables de producción y mediciones con gasto)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. **No desplegar, no encender servicios de Railway, no cambiar variables ni la memoria de artefactos de producción, no escribir en el Qdrant ni en la base de producción y no gastar cuota ni dinero** (las llamadas a OpenRouter de `scripts/medir_memoria.py` cuestan centavos) sin autorización del usuario. Las tareas marcadas [USUARIO] son del usuario.
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin dependencias nuevas** (`pyproject.toml`, `whatsapp/pyproject.toml`, `package.json` del panel y de la Consulta). **Una sola migración, la `0008`**, aditiva y con `downgrade`.
- **El historial nunca se guarda**: ni en la base, ni en el registro de Uso (`QueryLog.question` es siempre la pregunta actual original), ni en los registros del servidor. **Nunca es fuente de datos**: va en un bloque rotulado y con la instrucción de sistema de que toda respuesta sale solo de los fragmentos.
- **Con `context_turns = 0` el camino de `run_query` es exactamente el de antes** (sin `sanitize_history`, sin `search_question` distinta, sin instrucción extra). `POST /bot/query` construye su pedido **sin historial** y el bot no cambia de comportamiento. Tras tocar `query.py` y los proveedores, correr `pytest` completo.
- Cada proveedor arma el mensaje de usuario con la función compartida `build_user_message` de `src/mia/rag/llm.py`: no duplicar el formato del bloque en cada proveedor. `openai` y `local` son esqueletos que lanzan `NotImplementedError` y solo reciben el parámetro nuevo en la firma.
- El servicio del bot (`whatsapp/`) **no importa `mia`**.
- Los textos de [data-model.md](data-model.md) y los contratos mandan: cada restricción citada abajo entre comillas es literal de allí.
- Es un prototipo: lo más simple que cumpla la especificación.

---

## Phase 1: Setup

**Purpose**: las variables de la API.

- [ ] T001 Agregar a `src/mia/config.py` (junto a las variables de la búsqueda) `history_reformulation: str = "rules"` (variable `HISTORY_REFORMULATION`, "`rules`, `model` u `off` (inválido: `rules` y avisa una vez)", se lee con el mismo patrón de valor inválido que `QUERY_HYBRID_SEARCH`), `history_max_question_chars: int = Field(default=500, ge=50, le=2000)`, `history_max_answer_chars: int = Field(default=1500, ge=200, le=20000)`, `history_max_chars: int = Field(default=6000, ge=500, le=100000)` y `history_rewrite_max_tokens: int = Field(default=100, ge=20, le=500)`, con comentarios en español (los topes de respuesta y de total valen para el modo literal y el modo con razonamiento usa el doble); documentarlas en `.env.example` y `deploy/railway/variables.example.env`; y agregar sus pruebas a `tests/unit/test_config.py` (valores por defecto, rangos fuera de rango no dejan arrancar, un valor inválido de `HISTORY_REFORMULATION` se trata como `rules`)

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: la migración y las columnas, el historial puro y el mensaje al modelo, con sus pruebas.

### Tests (primero, deben fallar)

- [ ] T002 [P] Pruebas en `tests/unit/test_migrations.py` de la `0008`: sobre una base en la `0007` agrega `artifacts.context_turns` (entero no nulo, valor por defecto 0 en las filas existentes) y `bots.context_turns` (entero nulo, nulo en las filas existentes) sin perder datos; `downgrade` a la `0007` quita las dos columnas y conserva el resto; la cabeza pasa a `0008` (actualizar los `assert _revision(engine) == "0007"` existentes y los de `tests/unit/test_probar_migracion.py`)
- [ ] T003 [P] Pruebas en `tests/unit/test_history.py` de `sanitize_history(history, turns, mode)` y `format_history`: con `turns == 0` devuelve vacío sin mirar la entrada; devuelve las **últimas `turns` vueltas** en orden; descarta las vueltas cuya respuesta es "sin información" (`is_no_info_answer`, el texto `NO_INFO_ANSWER` o el que empieza con "No encontré información suficiente") y las vueltas con pregunta o respuesta vacías; recorta cada pregunta a `history_max_question_chars` (500) y cada respuesta a `history_max_answer_chars` (1.500 en literal, 3.000 en razonamiento); si el total supera `history_max_chars` (6.000 en literal, 12.000 en razonamiento) descarta las vueltas **más viejas** hasta que cabe y nunca deja una vuelta cortada a la mitad por el total; `format_history` produce el bloque "Conversación anterior (solo para entender la pregunta; no es una fuente de datos):" con "Pregunta:" y "Respuesta:" por vuelta, y agrega la advertencia "(respuesta del modo con razonamiento: puede incluir cálculos o inferencias que no dicen los documentos)" solo a las vueltas con `mode="razonamiento"`; sin vueltas devuelve cadena vacía
- [ ] T004 [P] Pruebas en `tests/unit/test_llm_history.py`: `build_user_message(question, context_block, history)` sin historial devuelve **exactamente** `f"Contexto:\n{context_block}\n\nPregunta: {question}"` (el formato de siempre); con historial pone el bloque rotulado **antes** de `Contexto:` y deja la pregunta al final; `instructions_with_history(instructions)` agrega `HISTORY_INSTRUCTIONS` (dice que el historial solo sirve para entender la pregunta, nunca es fuente de datos y que toda respuesta sale únicamente de los fragmentos del contexto) y sin historial no agrega nada; y que **OpenRouter, Gemini, GLM y Anthropic** (con sus clientes simulados, como en `test_openrouter_llm.py`, `test_glm_llm.py` y `test_anthropic_llm.py`; para Gemini un cliente simulado de `interactions.create`) mandan al modelo el mismo mensaje de usuario que arma `build_user_message` con y sin historial, y que los que no reciben historial lo mandan idéntico al de antes

### Implementation

- [ ] T005 Crear `src/mia/storage/migrations/versions/0008_memoria_de_conversacion.py` (`down_revision = "0007"`, con el estilo de la `0006` y la `0007`): agrega `artifacts.context_turns` como `INTEGER NOT NULL` con `server_default="0"` y `bots.context_turns` como `INTEGER NULL`, y su `downgrade` los quita con `batch_alter_table`; agregar `context_turns: Mapped[int]` (`default=0`) a `Artifact` y `context_turns: Mapped[int | None]` (`nullable=True`) a `Bot` en `src/mia/storage/models.py`; y actualizar `DESTINO = "0008"` en `scripts/probar_migracion.py` (y su `BAJAR_A` si corresponde)
- [ ] T006 [P] Crear `src/mia/rag/history.py` con `HistoryTurn` (`question`, `answer`, `mode`), `sanitize_history` y `format_history` con las reglas de T003 y de [data-model.md](data-model.md) ("Historial vigente"), leyendo los topes de `settings`
- [ ] T007 Agregar a `src/mia/rag/llm.py` `HISTORY_INSTRUCTIONS`, `instructions_with_history(instructions, history)` y `build_user_message(question, context_block, history)`; agregar `history: list[HistoryTurn] | None = None` a `LLMProvider.answer` y a los seis proveedores (`openrouter_llm.py`, `gemini_llm.py`, `glm_llm.py`, `anthropic_llm.py` lo usan para armar el mensaje y la instrucción de sistema; `openai_llm.py` y `local_llm.py` solo la firma); sin historial el mensaje y la instrucción son idénticos a los de antes

**Checkpoint**: el historial y el mensaje al modelo existen, probados aparte; las columnas existen.

---

## Phase 3: US2 - Quien administra define la memoria de cada artefacto desde el panel (P1)

**Goal**: el parámetro `context_turns` de cada artefacto se ve y se edita en el panel (0 a 10), con su explicación del costo, su línea de registro y su valor en `/config`.

**Independent Test**: `pytest tests/unit/test_artifacts_memory.py` y `npm test` en `web/admin`: rango, alcance, registro, `/config` y el formulario.

### Tests (primero, deben fallar)

- [ ] T008 [P] [US2] Pruebas en `tests/unit/test_artifacts_memory.py`: `POST /artifacts` sin `context_turns` lo deja en **0** y con un valor lo guarda; `PATCH /artifacts/{id}` lo cambia y `GET /artifacts` lo devuelve en cada `ArtifactOut`; **422** con `-1`, `11`, `2.5` y texto, sin cambiar nada; el artefacto sin tocar conserva 0; una persona de alcance de programa lo edita en un artefacto de su programa y recibe 404 en uno ajeno (como hoy); un cambio deja la línea `artifact.context_turns` en `mia.admin` (capturar la salida como en `tests/unit/test_images.py`) con `target` = id y `detail` = `"<nombre>: <anterior> -> <nuevo>"`, y editar otro campo sin cambiar la memoria no la deja; `GET /config` con la clave del artefacto trae `artifact.context_turns` con el valor vigente y rige desde la consulta siguiente sin reiniciar; `GET /config` sin clave no cambia
- [ ] T009 [P] [US2] Pruebas del panel: en `web/admin/src/modules/artefactos/memoryUtils.test.ts` `validateTurns` acepta enteros de 0 a 10 (también como texto con espacios) y rechaza vacío, negativos, mayores que 10, decimales y texto con un mensaje claro, y `describeMemory(0)` dice "Sin memoria" y `describeMemory(3)` "Memoria: 3 vueltas" (singular con 1); y que `ArtifactCard` muestra la memoria y `ArtifactForm` el campo con su texto de costo (`renderToString`, patrón de `BotsPage.test.tsx`)

### Implementation

- [ ] T010 [US2] En `src/mia/api/routes/artifacts.py` agregar `context_turns: int = Field(default=0, ge=0, le=10)` a `ArtifactCreate`, `context_turns: int | None = Field(default=None, ge=0, le=10)` a `ArtifactUpdate` y `context_turns: int` a `ArtifactOut` (con `_to_out`); guardarlo al crear y al actualizar (solo si viene en `model_fields_set`) y dejar `audit.log_write(principal, "artifact.context_turns", artifact.id, f"{artifact.name}: {anterior} -> {nuevo}")` cuando cambia; en `src/mia/api/routes/config.py` agregar `context_turns: int` a `ArtifactInfo` y llenarlo con el del artefacto; **actualizar la aserción exacta de `tests/unit/test_config.py` (línea 77, `artifact == {"name", "active"}`)** para que incluya `context_turns`, y buscar con `grep` otras comparaciones exactas de `ArtifactOut`, `ConfigOut` o `BotOut` en `tests/` y actualizarlas
- [ ] T011 [P] [US2] En el panel: agregar `context_turns` a `ArtifactItem` y a los cuerpos de crear y actualizar en `web/admin/src/api/types.ts` y `web/admin/src/api/artifacts.ts`; crear `web/admin/src/modules/artefactos/memoryUtils.ts` (`validateTurns`, `describeMemory`); agregar a `ArtifactForm.tsx` el campo numérico **Memoria de conversación (vueltas)** (0 a 10, con el valor actual y 0 al crear) con el texto de [contracts/artefactos-memoria-api.md](contracts/artefactos-memoria-api.md) ("Cuántas preguntas y respuestas anteriores recuerda este artefacto en cada conversación. Con más memoria las preguntas de seguimiento ('¿y cuánto cuesta?') se entienden, pero cada consulta lleva más texto y cuesta más. 0 es el comportamiento de siempre."), validado antes de enviar; y mostrar `describeMemory` en `ArtifactCard.tsx` junto a los topes y modos

**Checkpoint**: la memoria se administra desde el panel y la configuración la informa a los clientes.

---

## Phase 4: US1 - La persona hace una pregunta de seguimiento y el sistema la entiende (P1)

**Goal**: con memoria mayor que 0, `POST /query` usa el historial (para buscar y para el modelo) y la Consulta envía las últimas vueltas y avisa cuántas recuerda.

**Independent Test**: `pytest tests/unit/test_followup.py tests/unit/test_query_history.py` y `npm test` en `web/consulta`: un seguimiento corto recupera el documento del tema anterior y la Consulta arma bien el historial.

### Tests (primero, deben fallar)

- [ ] T012 [P] [US1] Pruebas en `tests/unit/test_followup.py`: `is_followup(question, history)` es falso sin historial; verdadero para una pregunta con dos o menos palabras con contenido ("¿y cuánto cuesta?" tiene una; usa `content_words` de `src/mia/rag/programs.py`), para las que empiezan con "y", "pero" o "entonces" y para las que traen una referencia ("eso", "esto", "esa", "ese", "ello", "anterior", "mismo", "misma", "primero", "segundo", "tercero", "último", "ahí"); falso para una pregunta que se entiende sola ("¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?"); y los **casos de cambio de tema**, que fijan lo que decide la heurística con una pregunta corta que sí se entiende sola ("¿Cuándo es la matrícula?", "¿Cuál es el plan de estudios?") frente a un historial de otro programa: el resultado de `is_followup` para esos casos queda escrito en la prueba (se espera que **no** sean seguimiento si traen un término propio del tema y que **sí** lo sean solo con marcas de continuación como "y", "eso" o "el segundo"), y si la regla de palabras no lo logra se agrega como condición adicional que la búsqueda con la pregunta original no deje ningún fragmento sobre el umbral; `search_question(question, history, strategy)` con `rules` devuelve las **últimas dos** preguntas anteriores más la actual separadas por espacio, hasta 400 caracteres (cortando por el inicio de las anteriores, nunca la actual); con `off` o sin seguimiento devuelve la pregunta original; con una estrategia desconocida usa `rules`
- [ ] T013 [P] [US1] Pruebas en `tests/unit/test_query_history.py` (patrón de `test_bot_clarify.py`: almacén, embeddings y modelo simulados, `settings.query_context_neighbors = 0`; dejar los fixtures del mundo simulado en `tests/unit/historial_de_prueba.py` para que los reutilicen las pruebas de US3, US4, US5 y US7, cada una en su archivo): con el artefacto en `context_turns=3` y un `history` de dos vueltas, un seguimiento corto calcula el embedding de la pregunta combinada (`embeddings.embed` recibe el texto con las preguntas anteriores) y el modelo recibe la **pregunta original** con el bloque "Conversación anterior" antes del contexto y la instrucción de sistema con `HISTORY_INSTRUCTIONS`; una pregunta que se entiende sola calcula el embedding de la original (no se reformula) aunque haya historial; con más vueltas que `context_turns` el modelo solo ve las últimas; el historial pasa por la búsqueda híbrida, el reranker y la pregunta limpia con la pregunta de búsqueda (comprobarlo con `settings.query_hybrid_search="on"` simulado) y el registro de Uso (`QueryLog.question`) guarda la pregunta original; una respuesta con fuentes, imágenes y formato como siempre
- [ ] T014 [P] [US1] Pruebas en `web/consulta/src/state/history.test.ts` de `buildHistory(exchanges, turns)`: devuelve `[]` con `turns` 0; toma las últimas `turns` vueltas con `status === "answered"` y `response.answer`, en orden, cada una con `question`, `answer` y el modo de la respuesta; omite las fallidas (`failed`), las pendientes (`pending`) y las "sin información" (`no_info`); respeta el orden aunque haya fallidas en medio; y un intercambio respondido en otro modo conserva su modo; y que el aviso (`memoryNotice(turns)`) dice "Recuerda las últimas N preguntas de esta conversación" ("la última pregunta" con 1) y es vacío con 0

### Implementation

- [ ] T015 [US1] Crear `src/mia/rag/followup.py` con `is_followup` y `search_question` (estrategias `rules` y `off`; la estrategia `model` queda para US6 y por ahora cae a `rules`) con las reglas de T012 y de [research.md](research.md) R4, y la lectura de `settings.history_reformulation` en cada llamada
- [ ] T016 [US1] En `src/mia/api/routes/query.py` agregar `history: list[HistoryTurnIn] = Field(default_factory=list, max_length=50)` a `QueryRequest` (con `HistoryTurnIn` de [data-model.md](data-model.md): `question` hasta 2.000 caracteres, `answer` hasta 20.000, `mode` opcional `literal` o `razonamiento`, `extra="forbid"`); en `run_query`, tras validar permisos y topes, calcular `history = sanitize_history(payload.history, artifact.context_turns, payload.mode)`; con historial vigente calcular `search_question` y usarla para el embedding, `_HybridRun`, el reranker (`rerank_provider.score`) y `clean_question` (nunca para el registro de Uso ni para el modelo); y pasar `history` a `llm_provider.answer(...)` (y a su reintento por respuesta cortada). Sin historial vigente el código no cambia ninguna llamada
- [ ] T017 [P] [US1] En `web/consulta/src`: crear `state/history.ts` con `buildHistory` y `memoryNotice`; agregar `context_turns` a `Config["artifact"]` en `api/types.ts`; enviar `history` en `useAsk` (`api/consulta.ts`, calculado en `App.tsx` desde los intercambios y `config.artifact.context_turns`, sin enviar nada con 0 y sin incluir el intercambio que se está enviando) y mostrar el aviso `memoryNotice` en la interfaz (junto al compositor, solo si N > 0); actualizar `web/consulta/README.md`

**Checkpoint**: los seguimientos funcionan con la estrategia `rules` (MVP de la feature).

---

## Phase 5: US3 - Cambiar de modo a mitad de la conversación no contamina las respuestas (P1)

**Goal**: el historial de cualquier modo ayuda a entender la pregunta y nunca es fuente de datos; cada modo conserva su estilo y las reglas de modos permitidos y de intercambios fallidos se cumplen.

**Independent Test**: `pytest tests/unit/test_query_history_modos.py` y los casos de contaminación de `scripts/medir_memoria.py`.

- [ ] T018 [P] [US3] Pruebas en `tests/unit/test_query_history_modos.py` (mismo mundo simulado que `test_query_history.py`; si hace falta, extraer los fixtures a `tests/unit/historial_de_prueba.py`) con los casos de cambio de modo: un historial con una vuelta de `mode="razonamiento"` y una pregunta en modo literal entrega al modelo el bloque con la advertencia de cálculos o inferencias **solo en esa vuelta**, la instrucción de sistema del modo literal (`RAG_SYSTEM_PROMPT`, no la de razonamiento) más `HISTORY_INSTRUCTIONS` y el marcador `SIN_INFORMACION` de siempre; el caso inverso (vuelta literal, pregunta con razonamiento) usa `REASONING_SYSTEM_PROMPT`; el historial **no** aparece entre las `sources` ni en `images` ni cambia las fuentes de la respuesta (las fuentes salen solo de los fragmentos recuperados); un artefacto que solo permite el modo literal rechaza con 403 una consulta en razonamiento aunque el historial traiga vueltas de ese modo (el historial no abre un modo); un historial cuya última vuelta es "sin información" o sin respuesta no la incluye, y con el **modo con razonamiento no disponible** (tope del modo alcanzado o `mode_available` falso) y un historial con vueltas de ese modo, la consulta en modo literal funciona con ese historial
- [ ] T019 [P] [US3] Crear `scripts/datos/casos_memoria.json` con los casos de seguimiento y de cambio de modo sobre los seis documentos de los posgrados (los de `tmp/nuevos/` en la sesión: Maestría en Ciberseguridad y Maestría en Analítica de Negocio, cada una con Presentación, Admisión y Plan de estudio): al menos 4 `tema_anterior` ("¿y cuánto cuesta?" tras hablar de un programa), 3 `pronombre` ("¿y el segundo?", "¿qué requisitos tiene eso?"), 3 `cambio_de_modo` (una vuelta en un modo y el seguimiento en el otro), 3 `cambio_de_tema` (una pregunta corta que **se entiende sola** sobre otro programa o tema que el del historial: la búsqueda no debe mezclar el tema anterior, `documentos` es el del tema nuevo) y 2 `calculo_en_razonamiento` (una respuesta calculada con razonamiento, por ejemplo la suma de créditos de varios bloques, y una pregunta literal que la pide de nuevo y **no** debe tratarla como dato documental, con el campo `no_debe_contener` con el valor calculado), cada caso con `id`, `categoria`, `historial` (lista de `{question, answer, mode}`), `pregunta`, `modo`, `documentos` esperados (nombres de archivo) y `nota` que diga qué mide; y una prueba `tests/unit/test_casos_memoria.py` que valide la forma del archivo (ids únicos, categorías válidas entre `tema_anterior`, `pronombre`, `cambio_de_modo`, `cambio_de_tema` y `calculo_en_razonamiento`, `documentos` no vacío salvo en `calculo_en_razonamiento`, `no_debe_contener` presente en esa categoría)

**Checkpoint**: el cambio de modo está cubierto en la estructura y los casos para medirlo con el modelo real existen.

---

## Phase 6: US4 - Con la memoria en 0 todo queda exactamente como hoy (P1)

**Goal**: demostrar que con la memoria en 0 (el valor por defecto) nada cambia, aunque el cliente envíe historial.

**Independent Test**: `pytest` completo, `pytest tests/unit/test_query_history_memoria_cero.py` y la batería del MVP.

- [ ] T020 [P] [US4] Pruebas en `tests/unit/test_query_history_memoria_cero.py` (mismo mundo simulado que `test_query_history.py`) con memoria 0: aunque el cliente envíe un historial válido de varias vueltas (la forma inválida es un 422 aunque la memoria sea 0, ver US5), con `context_turns=0` el embedding es el de la pregunta original, el mensaje al modelo es **idéntico** al de una consulta sin historial (`build_user_message` sin bloque), la instrucción de sistema es la del modo sin el párrafo, el costo registrado y las llamadas al almacén son las mismas, y la respuesta es la misma (comparar contra una consulta sin historial en el mismo mundo); todos los artefactos existentes (`make_artifact`) nacen con `context_turns` 0; y una consulta de un cliente sin `history` funciona sin cambios
- [ ] T021 [P] [US4] Ampliar `tests/unit/test_bot_clarify.py` o crear la prueba en `tests/unit/test_bot_service.py`: `POST /bot/query` construye su pedido sin historial (el modelo nunca recibe el bloque "Conversación anterior" aunque el artefacto asignado tenga `context_turns` mayor que 0) y su respuesta, fuentes, imágenes y costo son los de antes
- [ ] T022 [US4] Correr la suite completa (`pytest` y `ruff check src tests scripts whatsapp`) y los dos proyectos web (`npm run typecheck && npm test && npm run build` en `web/admin` y `web/consulta`) y comprobar que el resultado de las pruebas existentes no cambia respecto de la línea base (1698 pasadas de `pytest`, 146 de Vitest del panel y 67 de Vitest de la Consulta, medidas el 2026-11-03 antes de empezar, más las nuevas)

**Checkpoint**: sin regresiones.

---

## Phase 7: US5 - El historial es acotado, validado y privado (P2)

**Goal**: la API valida y recorta el historial sin confiar en el cliente, y nada se guarda.

**Independent Test**: `pytest tests/unit/test_query_history_validacion.py` y la revisión de la base y de Uso.

- [ ] T023 [P] [US5] Pruebas en `tests/unit/test_query_history_validacion.py` (mismo mundo simulado que `test_query_history.py`) con la validación y la privacidad: un `role` (o cualquier campo extra) dentro de una vuelta, más de 50 vueltas, `question` o `answer` vacíos, `question` de más de 2.000 caracteres, `answer` de más de 20.000 y un `mode` inválido responden **422** (no llegan al modelo); un `history` que no es una lista o con elementos que no son objetos responde 422; con historial válido más largo que la memoria solo cuentan las últimas vueltas permitidas; respuestas anteriores muy largas llegan recortadas al máximo del modo (el modo con razonamiento admite el doble) y el total no supera el máximo; las vueltas con "sin información" no llegan al modelo; y **tras la consulta no queda el historial en ninguna parte**: ni en `queries` (solo la pregunta actual en `question`, y `sources` y el resto como siempre), ni en las demás tablas (volcar `queries`, `artifacts`, `bots` y `bot_message_counts` y comprobar que ningún texto del historial aparece), ni en la salida de registro de la prueba
- [ ] T024 [US5] Cubrir en `src/mia/api/routes/query.py` y `src/mia/rag/history.py` lo que T023 señale que falte (por ejemplo, que ninguna línea de registro del servidor escriba el historial ni la pregunta de búsqueda reformulada con el texto del historial): la pregunta de búsqueda y el historial no se escriben en `logger` (solo longitudes y la estrategia usada, a nivel `info`)

**Checkpoint**: el historial es acotado, validado y no deja rastro.

---

## Phase 8: US6 - Un seguimiento corto encuentra los documentos gracias a la reformulación (P2)

**Goal**: la estrategia con el modelo, la selección por configuración y la medición que fija la predeterminada.

**Independent Test**: `pytest tests/unit/test_followup.py -k modelo` y `python scripts/medir_memoria.py --documentos tmp/nuevos --sin-modelo`.

### Tests (primero, deben fallar)

- [ ] T025 [P] [US6] Ampliar `tests/unit/test_followup.py` con la estrategia `model`: con `history_reformulation="model"` y un seguimiento, `search_question` llama a `provider.rewrite(question, history)` y usa su resultado si es válido (una línea, de 5 a 300 caracteres, no vacía); si la reescritura devuelve vacío, varias líneas, demasiado larga o corta, lanza una excepción o el proveedor no la implementa (`NotImplementedError`), cae a `rules` sin lanzar y deja un aviso en el registro; una pregunta que se entiende sola no llama al proveedor; con `off` tampoco; el cambio de la variable rige en la consulta siguiente (sin reiniciar); y el costo y los tokens de la reescritura se devuelven para sumarse a la consulta
- [ ] T026 [P] [US6] Pruebas en `tests/unit/test_openrouter_llm.py` de `OpenRouterLLMProvider.rewrite(question, history)`: llama al modelo con una instrucción de reescritura ("reescribe la última pregunta como una pregunta completa y autónoma usando la conversación; responde solo con la pregunta"), el bloque de historial y la pregunta, con `max_tokens=settings.history_rewrite_max_tokens`, **sin razonamiento** (sin `reasoning` en `extra_body`) y con las mismas restricciones de proveedores (`data_collection: deny`); devuelve el texto y su uso (tokens y costo real de `usage.cost`); y que `LLMProvider.rewrite` de la interfaz lanza `NotImplementedError` para los demás proveedores

### Implementation

- [ ] T027 [US6] Agregar `rewrite(self, question, history) -> LLMAnswer` (no abstracto, lanza `NotImplementedError`) a `LLMProvider` en `src/mia/rag/llm.py` e implementarlo en `src/mia/rag/providers/openrouter_llm.py` con las reglas de T026; y completar la estrategia `model` de `src/mia/rag/followup.py` (usa el proveedor del **modo literal**, `get_llm_provider(config.provider, config.model, "")` con `mode_config(LITERAL)`, valida la salida y cae a `rules` ante cualquier problema) devolviendo también el uso de la reescritura; en `run_query` de `src/mia/api/routes/query.py` sumar ese costo (y tokens) a `log.cost_usd` en **todos los caminos de salida** (incluido `no_info()`), sin llamar a la reescritura si el chequeo de topes ya rechazó la consulta
- [ ] T028 [US6] Crear `scripts/medir_memoria.py` (estilo de `scripts/calibrar_aclaracion.py`): ingiere en un Qdrant local temporal los `.txt` de `--documentos` con el mismo modelo de embeddings, recorre `scripts/datos/casos_memoria.json` y para cada caso con seguimiento mide, con cada estrategia (`off`, `rules` y, sin `--sin-modelo`, `model`), si algún fragmento recuperado (los `search_limit` mejores, con el umbral de similitud de la API) es de un documento esperado; reporta por estrategia aciertos, costo y tiempo por caso y por total, **más los falsos seguimientos** (casos `cambio_de_tema` en que la búsqueda se reformuló con el historial y dejó de encontrar el documento del tema nuevo) y los seguimientos que `is_followup` no reconoció, y sale con código 1 si la estrategia elegida queda bajo el 80 % de SC-001 en `tema_anterior` y `pronombre` o si hay algún falso seguimiento en `cambio_de_tema`; la estrategia `model` y los casos `calculo_en_razonamiento` (con `--respuestas`, que llama al modelo real de cada modo y comprueba `no_debe_contener`) cuestan centavos y solo corren sin `--sin-modelo` y con la clave de OpenRouter del `.env`; agregar su prueba de la parte pura (carga de casos y cálculo de aciertos con un almacén simulado) a `tests/unit/test_medir_memoria.py`

**Checkpoint**: las dos estrategias existen, se eligen por configuración y se pueden medir.

---

## Phase 9: US7 - El costo está a la vista y los topes siguen valiendo (P2)

**Goal**: el costo del historial y de la reescritura cuenta dentro del costo y de los topes, y se mide con memoria 0 y con memoria 4.

**Independent Test**: `pytest tests/unit/test_query_history_costo.py` y `scripts/medir_memoria.py --costo`.

- [ ] T029 [P] [US7] Pruebas en `tests/unit/test_query_history_costo.py` (mismo mundo simulado que `test_query_history.py`) con el costo y los topes: con el modelo simulado informando tokens y costo por consulta, una consulta con historial registra el costo y los tokens que informa el proveedor (que ya incluyen el texto del historial) y con `history_reformulation="model"` el registro suma el costo de la reescritura (`QueryLog.cost_usd` = costo de la respuesta + costo de la reescritura), también cuando la respuesta termina en "sin información"; con el tope diario del artefacto alcanzado (o el del modo con razonamiento), una consulta con historial responde **429** como siempre y **no** llama a la reescritura ni al modelo; el reintento por respuesta cortada sigue respetando el tope
- [ ] T030 [US7] Agregar a `scripts/medir_memoria.py` la opción `--costo` que, con la misma serie de preguntas de seguimiento, calcula el aumento del texto de entrada con memoria 0 y con memoria N (en caracteres y en tokens estimados, sin llamar al modelo) y, con la clave de OpenRouter y la autorización del usuario, el costo real por consulta con cada memoria; documentar el resultado en [research.md](research.md) R9 al medirlo (T040)

**Checkpoint**: el costo es visible y los topes siguen.

---

## Phase 10: US8 - Se puede ajustar la memoria del bot de WhatsApp desde el panel (P3)

**Goal**: el módulo Bots edita la memoria del bot (1 a 10, por defecto 2 vueltas) y el servicio la usa desde el mensaje siguiente; el bot no recibe historial al modelo.

**Independent Test**: `pytest tests/unit/test_bots_memory.py whatsapp/tests/test_context.py whatsapp/tests/test_flow_clarify.py` y `npm test` en `web/admin`.

### Tests (primero, deben fallar)

- [ ] T031 [P] [US8] Pruebas en `tests/unit/test_bots_memory.py`: `POST /bots` sin `context_turns` lo deja nulo y `BotOut` devuelve `context_turns` nulo y `context_turns_effective` 2; con un valor lo guarda (`context_turns_effective` = ese valor); `PATCH /bots/{id}` lo cambia, y enviar `null` vuelve al valor por defecto; **422** con `0`, `11`, `2.5` y texto; solo alcance global (403 `global_only` para una cuenta de programa, como el resto del módulo); un cambio deja la línea `bot.context_turns` en `mia.admin` con `detail` = `"<nombre>: <anterior> -> <nuevo>"` (los nulos escritos `por defecto`); `POST /bot/messages` devuelve `context_turns` (el efectivo del bot, de 1 a 10) y `null` para un número sin bot, sin cambiar el resto de la respuesta, y un cambio rige en la llamada siguiente
- [ ] T032 [P] [US8] Ampliar las pruebas del servicio: en `whatsapp/tests/test_api_client.py` `count_messages` lee `context_turns` de la respuesta (vacío si la API no lo informa o viene con otra forma); en `whatsapp/tests/test_context.py` el `ConversationStore` guarda hasta `MAX_CONTEXT_TURNS` (20) turnos por persona y `turns`, `pending` y `remembered_program` reciben el límite vigente y miran solo los últimos (con límite 2 una aclaración pendiente se resuelve; con límite 4 recuerda dos vueltas; bajar el límite en medio de una conversación acorta lo que ve sin borrar a la persona); en `whatsapp/tests/test_flow_clarify.py` (con `FakeMia` devolviendo `context_turns`) un valor de 1 vuelta alcanza para resolver una aclaración, un valor mayor recuerda más vueltas y un cambio del valor rige en el mensaje siguiente, sin `context_turns` en la respuesta usa `BOT_CONTEXT_MESSAGES` (4 turnos), y el bot sigue sin enviar historial a `/bot/query` (el cuerpo de la consulta es solo `number_id` y `question`)
- [ ] T033 [P] [US8] Pruebas del panel: en `web/admin/src/modules/bots/botsUtils.test.ts` `validateBotTurns` acepta vacío (valor por defecto) y enteros de 1 a 10, y rechaza 0, negativos, mayores que 10, decimales y texto con un mensaje claro; y que `BotForm` muestra el campo **Memoria (vueltas)** con su texto y `BotCard` el valor efectivo (`renderToString`, patrón de `BotsPage.test.tsx`)

### Implementation

- [ ] T034 [US8] En `src/mia/api/routes/bots.py` agregar `context_turns: int | None = Field(default=None, ge=1, le=10)` a `BotCreate` y `BotUpdate` (con `model_fields_set` para distinguir "no enviado" de `null`), `context_turns` y `context_turns_effective` a `BotOut` (el efectivo es el del bot o `DEFAULT_BOT_CONTEXT_TURNS = 2`), guardarlo y dejar `audit.log_write(principal, "bot.context_turns", bot.id, f"{bot.name}: {anterior} -> {nuevo}")` cuando cambia; y en `src/mia/api/routes/bot_service.py` agregar `context_turns: int | None` a `BotMessagesOut` con el efectivo del bot (nulo si el número no tiene bot); **actualizar las aserciones exactas del cuerpo de `/bot/messages`** en `tests/unit/test_bot_service.py` (que comparan `status`, `month`, `month_messages` y `month_cap`) para que incluyan `context_turns`, y revisar `whatsapp/tests/support.py` (`FakeMia`) para que su respuesta de `/bot/messages` lo traiga
- [ ] T035 [US8] En `whatsapp/src/mia_whatsapp/api_client.py` agregar `context_turns: int | None = None` a `CountResult` y leerlo de la respuesta (ignorando formas raras); en `whatsapp/src/mia_whatsapp/state.py` cambiar el `ConversationStore` para guardar hasta `MAX_CONTEXT_TURNS = 20` turnos por persona (`deque(maxlen=MAX_CONTEXT_TURNS)`) y hacer que `turns`, `pending` y `remembered_program` reciban `limit` (turnos) y miren solo los últimos; (dejar escrito en un comentario de `state.py` y de `flow.py` que `context_turns` cuenta **vueltas** y que un `Turn` es un **mensaje**, así que una vuelta son 2 turnos) y en `whatsapp/src/mia_whatsapp/flow.py` calcular tras contar el mensaje `limit = 2 * count.context_turns` si la API lo informa o `settings.bot_context_messages` si no, y pasarlo a todas las lecturas del contexto; actualizar `whatsapp/README.md` y `whatsapp/.env.example` (`BOT_CONTEXT_MESSAGES` queda como respaldo)
- [ ] T036 [P] [US8] En el panel: agregar `context_turns` y `context_turns_effective` a los tipos de bots (`web/admin/src/api/types.ts` y `web/admin/src/api/bots.ts`), `validateBotTurns` a `web/admin/src/modules/bots/botsUtils.ts`, el campo **Memoria (vueltas)** a `BotForm.tsx` (entero de 1 a 10; vacío significa el valor por defecto, 2) con el texto de [contracts/bots-memoria-servicio.md](contracts/bots-memoria-servicio.md) ("Cuántas vueltas recuerda el bot de cada conversación para pedir aclaraciones de programa y recordar el programa. Mínimo 1. El bot no entrega la conversación al modelo.") y el valor efectivo a `BotCard.tsx`

**Checkpoint**: la memoria del bot se ajusta desde el panel y rige sin reiniciar.

---

## Phase 11: Polish, medición y documentación

- [ ] T037 [P] Actualizar `docs/ARQUITECTURA.md`: la memoria de conversación (parámetro `context_turns` del artefacto y del bot, historial enviado por el cliente y recortado en la API, bloque rotulado en el mensaje de usuario y por qué no mensajes de chat, `rag/history.py` y `rag/followup.py`, las estrategias de reformulación y la que rige por defecto, el costo, que no se guarda nada, y el `ConversationStore` del bot con límite por lectura) y la migración `0008`
- [ ] T038 [P] Actualizar `docs/OPERACION.md` (sección "Memoria de conversación" con el límite de 10, los recortes por modo, las variables `HISTORY_*`, cómo editar la memoria de un artefacto y del bot, el costo medido, qué se guarda (nada) y cómo volver atrás: memoria en 0 y `alembic downgrade 0007`), `web/admin/README.md` (campo de Artefactos y de Bots), `web/consulta/README.md` y `docs/Definicion_Requerimientos_Bot_WhatsApp.md` (la memoria del bot ahora se ajusta desde el panel)
- [ ] T039 Correr `pytest && ruff check src tests scripts whatsapp`, `cd web/admin && npm run typecheck && npm test && npm run build` y `cd web/consulta && npm run typecheck && npm test && npm run build`, y `grep -rnP "\x{2014}" specs/014-memoria-conversacion docs src tests whatsapp scripts web/admin/src web/consulta/src` (sin guiones largos nuevos); confirmar que la cabeza de migraciones es `0008` y que las pruebas de `POST /query` sin historial y de `POST /bot/query` no cambiaron
- [ ] T040 [USUARIO] (Sin esta medición no se cumplen FR-017 ni SC-008; el valor por defecto seguro mientras tanto es `rules`, que no cuesta nada extra.) Con tu autorización (cuesta centavos): `python scripts/medir_memoria.py --documentos tmp/nuevos` para comparar `off`, `rules` y `model` (aciertos, costo y tiempo), con `--respuestas` para los casos `calculo_en_razonamiento`, y con `--costo` para el aumento con memoria 4; anotar los resultados en [research.md](research.md) R9 y fijar `HISTORY_REFORMULATION` por defecto en `src/mia/config.py`, `.env.example` y `deploy/railway/variables.example.env` según la medición
- [ ] T041 [USUARIO] Con tu autorización: merge a `main`, `git push origin main` y desplegar `MIA`, `mia-whatsapp`, `mia-panel` y `mia-computacion` (`python scripts/servicios.py encender MIA mia-whatsapp mia-panel mia-computacion --forzar`); la API migra a la `0008` al arrancar y no cambia nada mientras la memoria de todos los artefactos esté en 0
- [ ] T042 [USUARIO] En el panel de producción, poner la memoria del artefacto de la Consulta (por ejemplo, 3) y probar en la Consulta: una pregunta y un seguimiento ("¿y cuánto cuesta?"), un cálculo en razonamiento seguido de una pregunta literal que lo pide, y el aviso "Recuerda las últimas N preguntas"; revisar en Uso que el costo por consulta con memoria sigue en un orden razonable (research R9)

---

## Dependencies & Execution Order

- **Setup (T001)** primero.
- **Foundational (T002 a T007)** bloquea todo: T002, T003 y T004 (pruebas) en paralelo; luego T005 (migración y modelos), T006 (`history.py`) en paralelo y T007 (`llm.py` y los proveedores, que usa `HistoryTurn` de T006).
- **US2 (T008 a T011)** depende de T005 (la columna). **US1 (T012 a T017)** depende de T006, T007 y de T010 (el valor del artefacto y de `/config`); T017 (la Consulta) puede hacerse en paralelo con T015 y T016 una vez que T010 define `context_turns` en `/config`.
- **US3 (T018, T019)**, **US4 (T020 a T022)** y **US5 (T023, T024)** dependen de US1 y se pueden hacer en paralelo entre sí.
- **US6 (T025 a T028)** depende de T015 (la estrategia `rules`) y de T019 (los casos). **US7 (T029, T030)** depende de T027 (el costo de la reescritura).
- **US8 (T031 a T036)** depende de T005 (la columna del bot) y es independiente de US1 a US7; T034 antes de T035 y T036.
- **Polish (T037 a T039)** al final; T040 a T042 son del usuario (T040 puede adelantarse apenas existan T027 y T028 y fija el valor por defecto de `HISTORY_REFORMULATION`).

## Parallel Opportunities

- T002, T003 y T004; T005 con T006.
- Pruebas de US1: T012, T013 y T014 entre sí; T017 con T015 y T016.
- US3, US4 y US5 entre sí; T025 y T026 (pruebas de US6) entre sí.
- US8 en paralelo con US6 y US7; T031, T032 y T033 entre sí; T037 y T038 (documentación).

## Implementation Strategy

- **MVP**: Phases 1 a 4 (T001 a T017): el parámetro en el panel, el historial en la consulta con la reformulación por reglas y la Consulta que lo envía. Con eso un seguimiento como "¿y cuánto cuesta?" funciona en el artefacto de la Consulta.
- **Seguridad del modo**: US3, US4 y US5 antes de encender la memoria en cualquier artefacto de producción.
- **Comparación**: US6 (la estrategia con el modelo y la medición) decide la estrategia por defecto; US7 mide el costo.
- **Aparte**: US8 (la memoria del bot) no depende del resto y puede ir en cualquier momento después de la base.

## Notes

- Los criterios de éxito se comprueban así: SC-001 en T028 y T040; SC-002 en T028 (`--respuestas`), T019 y T040; SC-003 en T018 y T040; SC-004 en T020, T021 y T022 (la batería del MVP con gasto la corre el usuario si quiere confirmarla); SC-005 en T023; SC-006 en T023; SC-007 en T029, T030 y T040; SC-008 en T028 y T040; SC-009 en T008, T031 y T042; SC-010 en T021 y T032.
- La memoria queda en 0 en todos los artefactos hasta que el usuario la edite en el panel (T042): desplegar no cambia nada.
- La feature no se da por terminada hasta T040: la comparación de estrategias (FR-017, SC-008) y la medición de SC-001 y SC-002 con el modelo real solo salen de esa medición.
