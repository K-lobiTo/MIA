---

description: "Tareas de implementación de la feature 013: aclaración de programa y contexto de conversación en el bot de WhatsApp (reglas sin modelo de lenguaje)"
---

# Tasks: Aclaración de programa y contexto de conversación en el bot de WhatsApp

**Input**: Design documents from `specs/013-aclaracion-programa-contexto/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/bot-query-aclaracion.md](contracts/bot-query-aclaracion.md), [contracts/servicio-whatsapp-contexto.md](contracts/servicio-whatsapp-contexto.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. El plan y el quickstart los exigen (FR-023) y la medición con casos nuevos es parte de la feature. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Las pruebas de la API usan el patrón de `tests/conftest.py` y del almacén simulado de `tests/unit/test_bot_end_to_end.py` y `test_bot_service.py`; las del servicio usan `httpx.MockTransport` y el reloj inyectable (`State(settings, clock)`), sin red ni Kapso.

**Organization**: tareas agrupadas por historia de usuario (US1 a US6 de spec.md), precedidas por la base común. El orden sigue las dependencias: la base son el cálculo del programa de un documento (API) y la estructura del contexto (servicio); US1 hace que la API devuelva la aclaración y el servicio la envíe; US2 la resuelve; US3 recuerda el programa; US4 y US5 son verificaciones de lo que no cambia y de que el contexto es mínimo y privado; US6 es el texto configurable y la convención del título.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US6)
- **[USUARIO]**: lo hace el usuario, no quien implementa (despliegue, variables de producción y pruebas con el teléfono)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. **No desplegar, no encender servicios de Railway, no cambiar variables de producción, no escribir en el Qdrant ni en la base de producción y no gastar cuota ni dinero** sin autorización del usuario. Las tareas marcadas [USUARIO] son del usuario.
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin dependencias nuevas** (`pyproject.toml`, `whatsapp/pyproject.toml`) y **sin migraciones**: la cabeza sigue en `0007`. **Sin cambios en el panel** (`web/admin`).
- **Ninguna llamada nueva a modelos de lenguaje** (SC-007). La búsqueda de decisión reutiliza el embedding de la pregunta y es **solo vectorial** (sin híbrida, sin reranker, sin pregunta limpia).
- **`POST /query` y la Consulta administrativa no cambian** (FR-019): `run_query` recibe los parámetros nuevos como opcionales con valor por defecto que reproduce el comportamiento anterior, y solo `/bot/query` los usa. Tras tocar `query.py`, correr `pytest` completo.
- **El servicio del bot (`whatsapp/`) no importa `mia`** (feature 011): la normalización de nombres de programa que necesita se escribe de nuevo en el servicio, con las mismas reglas de [data-model.md](data-model.md) y pruebas que lo demuestren.
- **El contexto nunca va a la base, a Uso ni a los registros** (FR-010): ni el texto de la persona, ni el teléfono, ni los nombres de programas en las líneas de registro. La persona es `message.person_key` (el hash que ya existe).
- Los textos de [data-model.md](data-model.md) y los contratos mandan: cada restricción citada abajo entre comillas es literal de allí.
- Es un prototipo: lo más simple que cumpla la especificación.

---

## Phase 1: Setup

**Purpose**: las variables de las dos piezas.

- [X] T001 Agregar a `src/mia/config.py` (junto a `bot_monthly_message_cap`) `bot_clarify: str = "off"` (variable `BOT_CLARIFY`, "on u off, inválido: apagado y avisa una vez", se lee con el mismo patrón de interruptor que `QUERY_HYBRID_SEARCH`), `bot_clarify_min_similarity: float = Field(default=0.55, ge=0.0, le=1.0)` (punto de partida: se calibra en T037) y `bot_clarify_max_programs: int = Field(default=5, ge=2, le=10)`, con comentarios en español; documentarlas en `.env.example` y `deploy/railway/variables.example.env`, y agregar sus pruebas (valores por defecto, rangos fuera de rango no dejan arrancar, valor inválido del interruptor se trata como apagado) a `tests/unit/test_config.py`
- [X] T002 [P] Agregar a `whatsapp/src/mia_whatsapp/config.py` `bot_context_messages: int = Field(default=4, ge=2, le=10)`, `bot_context_minutes: int = Field(default=30, ge=1, le=1440)`, `bot_context_max_people: int = Field(default=5000, ge=100, le=100000)` y el texto `bot_text_clarify` con `DEFAULT_TEXT_CLARIFY = "¿A qué programa te refieres? Tengo información de:\n{programs}\nResponde con el nombre del programa o su número."`; agregar `"BOT_TEXT_CLARIFY": "bot_text_clarify"` a `_TEXT_FIELDS` (para que `contact_warnings` lo revise); documentar las variables en `whatsapp/README.md`; y agregar sus pruebas a `whatsapp/tests/test_config.py` (valores por defecto, rangos, y que el texto por defecto no contiene contacto)

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: dos piezas puras y probadas aparte: el programa de un documento y el contexto de conversación.

### Tests (primero, deben fallar)

- [X] T003 [P] Pruebas en `tests/unit/test_programs.py`: `natural_name` de `MAESTRÍA EN CIBERSEGURIDAD` da `Maestría en Ciberseguridad`, de `MAESTRÍA EN ANALÍTICA DE NEGOCIO (BUSINESS ANALYTICS)` da `Maestría en Analítica de Negocio (Business Analytics)`, una etiqueta con minúsculas se respeta tal cual y las palabras de enlace (`en`, `de`, `del`, `la`, `el`, `los`, `las`, `y`, `e`, `con`, `para`, `a`, `por`) quedan en minúscula salvo la primera; `program_key` quita tildes, signos y las palabras vacías (`maestria`, `en`, `de`, `del`, `la`, `el`, `y`, `los`, `las`): `Maestría en Ciberseguridad` da `ciberseguridad` y la de Analítica da `analitica negocio business analytics`; `parse_title` toma la etiqueta antes de los dos puntos de la primera línea del texto (de 3 a 120 caracteres) y devuelve `None` si no hay dos puntos, si la primera línea no tiene la forma o si la etiqueta no cabe en el rango; `program_of_document(vector_store, document_id)` lee el fragmento 0 con `get_chunks(document_id, [0])`, devuelve `None` para un documento sin título con la forma o sin fragmento 0 (sin lanzar), y **lee el almacén una sola vez por documento** (segunda llamada con la caché); `group_by_program(results, ...)` agrupa resultados por clave de programa, sin contar los documentos sin programa y ordena por el mejor puntaje de cada programa, cortando a `max_programs`
- [X] T004 [P] Pruebas en `whatsapp/tests/test_context.py` del `ConversationStore` con el reloj inyectable: guarda los turnos de una persona en orden y **nunca más de `bot_context_messages` (4)** (el quinto saca al primero); una persona sin clave (`None`) no tiene contexto; cada persona tiene el suyo; la conversación **vence a los `bot_context_minutes` de inactividad** (y cada turno nuevo renueva el plazo); respeta el tope `bot_context_max_people` (salen primero las más viejas); `cleanup()` retira las vencidas; el turno del bot **no guarda el texto de la respuesta** (solo `kind`, `programs` y `candidates`) y el de la persona recorta el texto a `bot_max_question_chars`; los derivados: la aclaración pendiente es el último turno del bot con `kind="clarify"` precedido por el turno de la persona (pregunta original y candidatos), y el programa recordado es el único programa del último turno del bot con `kind="answer"` (ninguno si hay dos o más programas o si ese turno no es una respuesta)

### Implementation

- [X] T005 Crear `src/mia/rag/programs.py` con `parse_title(text) -> str | None` (etiqueta), `natural_name(label) -> str`, `program_key(label) -> str`, `program_of_document(vector_store, document_id) -> Program | None` (con `Program = (name, key)` y la caché por proceso `dict[document_id -> Program | None]` de [data-model.md](data-model.md), capturando cualquier excepción del almacén y dejando un aviso: un fallo no rompe la consulta), `group_by_program(results, vector_store, min_score, max_programs)`, y los tipos `ClarifyPolicy` (`min_similarity`, `max_programs`) y `QueryExtras` (`clarify: list[str]`, `source_document_ids: list[str]`) que `run_query` va a llenar
- [X] T006 [P] Agregar a `whatsapp/src/mia_whatsapp/state.py` el `ConversationStore` (un `OrderedDict` por clave de persona con `last_seen` y un `deque(maxlen=bot_context_messages)` de turnos `Turn`, con las reglas de T004, el mismo estilo que `_greeted` y `_people`), exponerlo como `State.conversations`, y hacer que `State.cleanup()` también retire las conversaciones vencidas

**Checkpoint**: el programa de un documento y el contexto existen, probados aparte.

---

## Phase 3: US1 - El bot pide aclaración cuando la pregunta es ambigua entre programas (P1)

**Goal**: con `BOT_CLARIFY=on`, una pregunta sin nada sobre el umbral y con dos o más programas sobre el umbral bajo termina en una aclaración numerada; si no, "sin información" como hoy.

**Independent Test**: `pytest tests/unit/test_bot_clarify.py whatsapp/tests/test_flow_clarify.py -k aclaracion`: con dos programas la API devuelve `clarify` y el servicio envía el texto; con uno o ninguno, "sin información".

### Tests (primero, deben fallar)

- [X] T007 [P] [US1] Pruebas en `tests/unit/test_bot_clarify.py` (almacén, embeddings y modelo simulados, patrón de `test_bot_service.py`; el almacén simulado devuelve de `search` resultados con puntajes según una tabla y de `get_chunks(doc, [0])` el texto con el título): con `BOT_CLARIFY=on` y nada sobre `QUERY_SIMILARITY_THRESHOLD`, fragmentos de **dos programas** con puntaje mayor o igual a `BOT_CLARIFY_MIN_SIMILARITY` dan `no_info` verdadero, `clarify` con los **nombres naturales** de los dos programas por mejor puntaje y `answer` el texto de "sin información", sin fuentes ni imágenes, sin llamar al modelo; con fragmentos de **un solo programa** (varios documentos del mismo programa cuentan uno), de **ninguno** o de documentos **sin programa**, `clarify` es `[]` y la respuesta es la de hoy; con `BOT_CLARIFY=off` (o inválido) no hay búsqueda extra (el almacén recibe una sola llamada a `search`) y `clarify` es `[]`; se listan como máximo `BOT_CLARIFY_MAX_PROGRAMS`; una respuesta "sin información" que da el modelo después de recibir fragmentos relevantes **no** produce aclaración; una respuesta con fuentes trae `programs` con los programas de sus documentos (sin repetir; `[]` si ningún documento tiene programa); la consulta queda en Uso como `no_info` y no hay resultado nuevo; `_no_domains_response` y los rechazos (403, 404, 429) no cambian; **regresión**: `POST /query` devuelve exactamente las claves de siempre (sin `clarify` ni `programs`) y no hace ninguna búsqueda extra aunque `BOT_CLARIFY=on`
- [X] T008 [P] [US1] Pruebas en `whatsapp/tests/test_api_client.py` (ampliar): `MiaApiClient.query` lee `clarify` y `programs` de la respuesta; con `no_info` verdadero y `clarify` no vacía devuelve `QueryResult(kind="clarify", candidates=[...])`, con `no_info` y sin candidatos `kind="no_info"`, con respuesta `kind="answer"` y `programs`; una respuesta sin esos campos (API anterior) se lee como antes
- [X] T009 [P] [US1] Pruebas en `whatsapp/tests/test_flow_clarify.py` (patrón de `test_flow.py` y `support.py`): una pregunta cuya consulta devuelve `clarify` con dos programas envía **un solo mensaje** con `bot_text_clarify`, los programas **numerados** en `{programs}` (`1. Maestría en Ciberseguridad`, `2. ...`), con el saludo si toca, sin imágenes, `resultado` `aclaracion`, contado como un mensaje enviado en `count_messages`; la consulta que devuelve "sin información" sigue enviando `bot_text_no_info`; ningún texto por defecto trae contacto; `error_envio` al enviar la aclaración no deja el contexto a medias

### Implementation

- [X] T010 [US1] En `src/mia/api/routes/query.py` agregar a `run_query` los parámetros opcionales `clarify: ClarifyPolicy | None = None` y `extras: QueryExtras | None = None`: en el camino `if not relevant` y solo con `clarify`, hacer **una** búsqueda vectorial adicional con `question_embedding` (`limit = config.search_limit`), agrupar con `group_by_program` y, si salen dos o más programas, llenar `extras.clarify` con sus nombres y devolver el `no_info()` de siempre; al final de una respuesta con fuentes, llenar `extras.source_document_ids`. Sin `clarify` ni `extras` el comportamiento no cambia en nada
- [X] T011 [US1] En `src/mia/api/routes/bot_service.py` definir `BotQueryResponse(QueryResponse)` con `clarify: list[str] = []` y `programs: list[str] = []`, usarlo como `response_model` de `POST /bot/query`, pasar a `run_query` la `ClarifyPolicy` solo si `BOT_CLARIFY` está encendido, y completar la respuesta con `clarify` y con `programs` (los programas de `extras.source_document_ids` sin repetir, con `program_of_document`); `_no_domains_response` devuelve también un `BotQueryResponse`
- [X] T012 [P] [US1] En `whatsapp/src/mia_whatsapp/api_client.py` ampliar `QueryResult` con `candidates: list[str]` y `programs: list[str]`, el tipo `kind="clarify"` y la lectura de `clarify` y `programs` de la respuesta (tolerante a que falten)
- [X] T013 [US1] En `whatsapp/src/mia_whatsapp/flow.py` agregar el paso de la aclaración (pasos e y f del contrato): si la consulta devuelve `kind="clarify"`, enviar `bot_text_clarify` con los candidatos numerados (`{programs}` reemplazado por `"1. Nombre\n2. Nombre"`) con `_respond` y `resultado` `aclaracion` (con el saludo si toca) y registrar en el contexto el turno de la persona y el del bot (`kind="clarify"` con sus `candidates`) **solo si el envío salió bien**

**Checkpoint**: una pregunta ambigua entre programas recibe la aclaración (MVP de la feature).

---

## Phase 4: US2 - La persona contesta la aclaración y el bot sigue con su pregunta original (P1)

**Goal**: la respuesta de la persona a una aclaración se compara con los candidatos y, si coincide exactamente uno, el bot repite la pregunta original con ese programa y la responde.

**Independent Test**: `pytest whatsapp/tests/test_flow_clarify.py -k resolver`: "Ciberseguridad", "la de analítica", "Maestría en Analítica de Negocio" y "2" resuelven; "no sé", "las dos" y un programa no candidato la descartan sin volver a preguntar.

### Tests (primero, deben fallar)

- [X] T014 [P] [US2] Pruebas en `whatsapp/tests/test_clarify.py` de las funciones puras `match_candidate(text, candidates)` y `with_program(question, program)`: coincide un candidato si **todas** las palabras del mensaje (normalizado: minúsculas, sin tildes ni signos, sin las palabras vacías de [data-model.md](data-model.md)) están en las de su clave; "Ciberseguridad", "ciberseguridad", "la de analítica", "Maestría en Analítica de Negocio", "analítica de negocios (business analytics)" y "MAESTRÍA EN CIBERSEGURIDAD" resuelven; el número de la opción (`"1"`, `"2"`, con espacios) resuelve; devuelve `None` si no coincide ninguno ("no sé", "Computación"), si coinciden **dos o más** ("ciberseguridad y analítica") o si no quedan palabras tras quitar las vacías ("maestría"); un número fuera de rango no resuelve; `with_program("¿Cuándo empiezan las lecciones?", "Maestría en Ciberseguridad")` da `"¿Cuándo empiezan las lecciones? (Maestría en Ciberseguridad)"`
- [X] T015 [P] [US2] Ampliar `whatsapp/tests/test_flow_clarify.py` (con el contexto real de `State` y el reloj inyectable): tras una aclaración, "Ciberseguridad" consulta a la API con la pregunta original más el programa (la prueba verifica el texto enviado a `/bot/query`) y entrega la respuesta con fuentes e imagen como cualquier otra; "no sé", "las dos" y un programa no candidato descartan la aclaración y el mensaje se trata como **pregunta nueva** (consulta con el texto tal cual) y **no se vuelve a preguntar**; si la consulta con el programa elegido devuelve aclaración otra vez, se responde `bot_text_no_info` (máximo una aclaración por pregunta); una aclaración **vencida** (reloj adelantado `bot_context_minutes`) no se resuelve: "Ciberseguridad" es un mensaje nuevo; sin aclaración previa "Ciberseguridad" es una pregunta nueva; dos personas con aclaraciones pendientes no se mezclan; el mensaje duplicado no cuenta dos veces en el contexto

### Implementation

- [X] T016 [US2] Crear `whatsapp/src/mia_whatsapp/clarify.py` con la normalización (minúsculas, sin tildes ni signos, sin palabras vacías `maestria`, `en`, `de`, `del`, `la`, `el`, `y`, `los`, `las`), `match_candidate(text, candidates) -> str | None` y `with_program(question, program) -> str` con las reglas de T014 (reescritas en el servicio, que no importa `mia`)
- [X] T017 [US2] En `whatsapp/src/mia_whatsapp/flow.py` agregar el paso a del contrato antes de consultar: si el contexto de la persona tiene una aclaración pendiente, comparar el mensaje con `match_candidate`; con un candidato, la pregunta a enviar es `with_program(pregunta original, candidato)` y se marca `ya_aclarado`; sin coincidencia, descartar la aclaración y seguir con el mensaje tal cual; si el resultado con `ya_aclarado` es `clarify`, tratarlo como `no_info` (paso f); y registrar la respuesta en el contexto (la aclaración queda resuelta)

**Checkpoint**: la aclaración cierra el ciclo sin que la persona repita su pregunta.

---

## Phase 5: US3 - El bot recuerda el programa de la conversación (P2)

**Goal**: con un programa recordado (elegido o citado por la última respuesta), una pregunta sin programa que recibiría "sin información" o aclaración se reintenta una vez con ese programa.

**Independent Test**: `pytest whatsapp/tests/test_flow_clarify.py -k recordar`: tras una respuesta de un programa, "¿y cuánto cuesta?" se reintenta con ese programa; el reintento no se encadena.

### Tests (primero, deben fallar)

- [X] T018 [P] [US3] Ampliar `whatsapp/tests/test_flow_clarify.py`: con una respuesta previa que citó **un** programa, una pregunta que recibe `no_info` se reintenta **una vez** con `with_program(pregunta, programa)` dentro del **mismo lugar de la cola** (una sola entrada a `QueryGate`) y, si el reintento responde, entrega esa respuesta y deja el programa recordado; si el reintento también da `no_info`, responde `bot_text_no_info` (nunca un segundo reintento); una pregunta que recibe `clarify` con un programa recordado se reintenta en lugar de preguntar, y si el reintento no responde, envía la aclaración original; una pregunta que **se responde sin contexto** no se reintenta ni se modifica aunque haya un programa recordado distinto; una respuesta que cita **dos o más programas** no deja programa recordado; nombrar otro programa en una pregunta que se responde cambia el programa recordado (queda el de la nueva respuesta); la aclaración resuelta deja recordado el programa elegido; el reintento no envía mensajes extra a la cuota (solo lo enviado se cuenta); sin contexto el flujo es exactamente el de antes

### Implementation

- [X] T019 [US3] En `whatsapp/src/mia_whatsapp/flow.py` agregar el paso d del contrato: tras una consulta que devuelve `no_info` o `clarify`, si el contexto tiene programa recordado y la pregunta enviada **no** era ya un reintento ni venía de una aclaración, reintentar **una vez** con `with_program(pregunta, programa recordado)` sin salir del `QueryGate`; si el reintento es una respuesta, entregarla; si no, seguir con el resultado original (aclaración o sin información); al guardar el turno del bot de tipo `answer` usar `programs` de la API (el contexto deriva de ahí el programa recordado)

**Checkpoint**: las preguntas de seguimiento sin programa se resuelven con el contexto de la conversación.

---

## Phase 6: US4 - Lo demás no cambia (P1)

**Goal**: demostrar que la Consulta administrativa, los demás artefactos y lo que el bot ya respondía no cambian.

**Independent Test**: `pytest` completo y `pytest tests/unit/test_bot_end_to_end.py`: mismas respuestas, mismas fuentes e imágenes y mismo consumo de mensajes sin contexto.

- [X] T020 [P] [US4] Ampliar `tests/unit/test_bot_end_to_end.py` (el servicio y la API reales en un proceso, con Kapso, almacén y modelo simulados): con `BOT_CLARIFY=on`, una pregunta ambigua entre dos programas recibe la aclaración, contestarla con el nombre de un programa entrega la respuesta con su fuente, y la cuota del mes queda con **2 recibidos y 2 enviados** (3 enviados si la respuesta lleva imagen); una pregunta que nombra el programa responde **igual que antes de la feature** (mismo texto, fuentes, imagen y 1 recibido y 2 enviados) y no hace búsqueda extra; con `BOT_CLARIFY=off` el recorrido es el de la 011 (sin aclaración); el registro de Uso de la aclaración es una consulta `no_info`
- [X] T021 [P] [US4] Agregar a `tests/unit/test_bot_clarify.py` la regresión de los demás artefactos: una consulta con la clave de un artefacto a `POST /query` sin resultados sobre el umbral responde "sin información" exactamente como antes (misma forma, sin `clarify` ni `programs`) y el almacén simulado recibe **una sola** búsqueda aunque `BOT_CLARIFY=on` y haya dos programas parecidos; el bot desactivado (403) y el tope mensual alcanzado en el servicio se comportan como hoy y no tocan el contexto
- [X] T022 [US4] Correr la suite completa (`pytest` y `ruff check src tests scripts whatsapp`) y comprobar que el resultado de las pruebas existentes no cambia respecto de la línea base (1506 pasadas, más las nuevas)

**Checkpoint**: sin regresiones.

---

## Phase 7: US5 - El contexto es mínimo, transitorio y privado (P2)

**Goal**: comprobar que el contexto no guarda más de lo previsto, no deja datos en ningún registro y no agrega llamadas a modelos.

**Independent Test**: `pytest whatsapp/tests/test_context.py whatsapp/tests/test_logs.py -k contexto`.

- [X] T023 [P] [US5] Ampliar `whatsapp/tests/test_logs.py` (patrón de las pruebas que ya revisan que no haya datos de la persona): tras una conversación con aclaración, resolución y programa recordado, ninguna línea del registro del servicio contiene el texto de las preguntas, el teléfono o su identificador, ni los nombres de los programas, y la línea de la aclaración trae `resultado=aclaracion` con su duración
- [X] T024 [P] [US5] Agregar a `tests/unit/test_bot_clarify.py` que la búsqueda de decisión y la lectura de títulos **no llaman a ningún modelo de lenguaje** (el proveedor de LLM simulado no se invoca en el camino de aclaración) y no calculan embeddings nuevos (el proveedor de embeddings simulado se llama una sola vez por consulta), y que la caché de títulos evita lecturas repetidas del almacén entre consultas
- [X] T025 [US5] Ampliar `tests/unit/test_bot_end_to_end.py` o `whatsapp/tests/test_context.py` con la comprobación de que, tras una conversación con contexto, la base de la API (`queries`, `bots`, `bot_message_counts`) no contiene el teléfono ni el texto de la persona más allá de la pregunta que ya registra Uso (la consulta, sin teléfono), y que el contexto de una persona **no sobrevive** a un `State` nuevo (reinicio)

**Checkpoint**: el contexto es mínimo, transitorio y privado.

---

## Phase 8: US6 - Texto configurable y convención del título (P3)

**Goal**: el texto de la aclaración se cambia sin código y la convención del título queda documentada.

**Independent Test**: `pytest whatsapp/tests/test_config.py -k clarify` y revisar la guía de normalización.

- [X] T026 [P] [US6] Ampliar `whatsapp/tests/test_config.py` y `whatsapp/tests/test_flow_clarify.py`: un `BOT_TEXT_CLARIFY` distinto se usa con la lista de candidatos en `{programs}`; si el texto configurado trae un contacto (correo, enlace o teléfono), `contact_warnings` lo señala por el nombre de su variable y el servicio arranca igual; un texto sin `{programs}` se envía tal cual seguido de la lista numerada (no se pierde la lista)
- [X] T027 [US6] Agregar a "Preparar documentos que vienen de páginas web (normalización)" de `docs/OPERACION.md` la convención del título: **la primera línea de cada documento es `<PROGRAMA>: <SECCIÓN>`** (por ejemplo `MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN`), que de ahí sale el nombre del programa que el bot ofrece al pedir aclaración y que un documento sin esa forma no cuenta como programa; y ajustar el punto de la guía que hoy remite a la propuesta 10.1 para decir que ya está implementada

---

## Phase 9: Polish, medición y documentación

- [X] T028 [P] Actualizar `docs/ARQUITECTURA.md`: sección del bot de WhatsApp con la aclaración y el contexto (la API decide la ambigüedad y devuelve `clarify` y `programs`, `rag/programs.py`, el programa de un documento por su título, `BotQueryResponse` solo en `/bot/query`, el `ConversationStore` del servicio con sus 4 turnos, vencimiento y tope, el orden de decisiones, y que `POST /query` no cambia) y las variables nuevas
- [X] T029 [P] Actualizar `docs/OPERACION.md`: variables nuevas (`BOT_CLARIFY`, `BOT_CLARIFY_MIN_SIMILARITY`, `BOT_CLARIFY_MAX_PROGRAMS` en la API; `BOT_CONTEXT_MESSAGES`, `BOT_CONTEXT_MINUTES`, `BOT_CONTEXT_MAX_PEOPLE` y `BOT_TEXT_CLARIFY` en el servicio), cómo encender la aclaración, cómo volver atrás (`BOT_CLARIFY=off`) y qué mirar (la proporción de `aclaracion` en los registros del servicio y el costo por pregunta en Uso)
- [X] T030 [P] Actualizar `docs/Definicion_Requerimientos_Bot_WhatsApp.md`: la sección 10.1 pasa de propuesta a implementada (opciones 1 y 3, con lo decidido: título del documento, 4 turnos, sin modelo) dejando la opción 2 como pendiente futura, y corregir la sección 8 ("Memoria de conversación" ya no está totalmente fuera de alcance: queda solo la ventana mínima) y la fila de la tabla de la sección 10; y actualizar `whatsapp/README.md` con el contexto y el texto de la aclaración
- [X] T031 [P] (Hecho en `scripts/datos/casos_aclaracion.json` y `scripts/calibrar_aclaracion.py`, un archivo aparte porque `casos_busqueda.json` es de la línea base de recuperación y su `cargar_casos` solo admite las esperas `respuesta` y `sin_informacion`; con `tests/unit/test_casos_aclaracion.py`.) Agregar a `scripts/datos/casos_busqueda.json` los casos de la categoría `aclaracion` de [quickstart.md](quickstart.md) sección 2 (ambigua entre programas, con un solo programa, con el programa nombrado y sin relación), con el campo `espera` que corresponda ("aclaracion", "respuesta" o "sin_informacion") y documentar el significado de `aclaracion` donde `scripts/` documenta los valores de `espera`
- [X] T032 Correr `pytest && ruff check src tests scripts whatsapp` y `grep -rnP "\x{2014}" specs/013-aclaracion-programa-contexto docs src tests whatsapp` (sin guiones largos nuevos); confirmar que la cabeza de migraciones sigue en `0007` y que `web/admin` no cambió
- [X] T033 Medir y calibrar el umbral bajo (research R9, [quickstart.md](quickstart.md) sección 2): con los seis documentos de `tmp/nuevos/` ingeridos en el Qdrant local con el mismo modelo de embeddings (`scripts/cargar_carpeta.py` o carga directa por la API local con `INGESTION_SYNC=true`), medir los puntajes de la búsqueda de decisión para las preguntas ambiguas, las de un solo programa y las sin relación; elegir `BOT_CLARIFY_MIN_SIMILARITY` para que las ambiguas den dos programas y las sin relación ninguno; anotar los puntajes y el valor elegido en research R9 y fijarlo como valor por defecto de `src/mia/config.py` (y de `.env.example`); y comprobar con el servicio y la API reales en un proceso que "¿Cuándo empiezan las lecciones? (Maestría en Ciberseguridad)" recupera la fecha de ese programa (research R7)
- [ ] T034 [USUARIO] Con tu autorización: merge a `main`, `git push origin main` y desplegar `MIA` y `mia-whatsapp` (`python scripts/servicios.py encender MIA mia-whatsapp --forzar`); sin migraciones; el comportamiento no cambia mientras `BOT_CLARIFY=off`
- [ ] T035 [USUARIO] Poner en la API `BOT_CLARIFY=on` y `BOT_CLARIFY_MIN_SIMILARITY` (si cambió el valor por defecto, ya viene calibrado), desplegar y probar con el teléfono del sandbox: "¿Cuándo empiezan las lecciones?", contestar el programa, "¿y cuánto cuesta?", una pregunta con el programa nombrado y "¿Cuánto cuesta la luna?"; revisar en Uso que el costo por pregunta sigue en el orden de 0,0004 USD; y, si quieres confirmarlo, correr la batería del MVP (`python scripts/pruebas_mvp.py`, 19 de 19, con gasto)

---

## Dependencies & Execution Order

- **Setup (T001, T002)** primero; T002 en paralelo con T001.
- **Foundational (T003 a T006)** bloquea todo: T003 y T004 (pruebas) en paralelo, luego T005 (API) y T006 (servicio) en paralelo.
- **US1 (T007 a T013)**: T007, T008, T009 en paralelo (pruebas); T010 y T011 en la API (T011 depende de T010); T012 en paralelo; T013 depende de T012 y T006.
- **US2 (T014 a T017)** depende de US1 (la aclaración que se resuelve); T016 antes de T017; T014 y T015 en paralelo.
- **US3 (T018, T019)** depende de US1 y de T016/T017 (`with_program` y el flujo).
- **US4 (T020 a T022)**, **US5 (T023 a T025)** y **US6 (T026, T027)** dependen de US1 a US3 y se pueden hacer en paralelo entre sí.
- **Polish (T028 a T033)** al final; T033 (calibración) puede adelantarse apenas existan T005 y T010 a T011 y define el valor por defecto de T001; T034 y T035 son del usuario.

## Parallel Opportunities

- T001 y T002; T003 y T004; T005 y T006.
- Pruebas de US1: T007, T008 y T009 entre sí; T012 con T010 y T011.
- US4, US5 y US6 entre sí; T028 a T031 (documentación y casos) entre sí.

## Implementation Strategy

- **MVP**: Phases 1 a 3 (T001 a T013): el bot pide aclaración ante una pregunta ambigua entre programas.
- **Cierre del ciclo**: US2 (resolver la aclaración) es necesaria para que el MVP sirva de verdad: sin ella la respuesta "Ciberseguridad" sola no lleva la pregunta; se hace enseguida.
- **Comodidad**: US3 (recordar el programa).
- **Verificación**: US4, US5, US6 y la calibración (T033) antes de encender `BOT_CLARIFY` en producción.

## Notes

- Los criterios de éxito se comprueban así: SC-001 en T007 y T009; SC-002 en T015 y T020; SC-003 en T007 (un solo programa o ninguno), T020 y T022; SC-004 en T015; SC-005 en T018; SC-006 en T004, T023 y T025; SC-007 en T024 y T033 (costo); SC-008 en T020; SC-009 en T021 y T022 (la batería del MVP con gasto la corre el usuario, T035); SC-010 en T035.
- `BOT_CLARIFY` queda apagado por defecto: desplegar no cambia nada hasta que el usuario lo encienda (T035).
- [X] T036 Implementar la regla de **evidencia léxica** que dejó la calibración (research R9): `content_words` y `has_evidence` y el parámetro `evidence_words` de `group_by_program` en `src/mia/rag/programs.py`, `ClarifyPolicy.candidates` y `BOT_CLARIFY_CANDIDATES` (30, rango 5 a 100) en `src/mia/config.py`, `.env.example` y `deploy/railway/variables.example.env`, el piso `BOT_CLARIFY_MIN_SIMILARITY` en 0,70 y `_clarify_candidates` en `src/mia/api/routes/query.py` con la búsqueda de decisión de más candidatos; con sus pruebas en `tests/unit/test_programs.py`, `tests/unit/test_bot_clarify.py` (pregunta sin relación con puntajes parecidos no pide aclaración, sin palabras con contenido no hay aclaración, la búsqueda de decisión pide más candidatos) y `tests/unit/test_config.py`
