---

description: "Tareas de implementación de la feature 007: respuestas completas, sin cortes"
---

# Tasks: Respuestas completas, sin cortes

**Input**: Design documents from `specs/007-respuestas-completas/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/contexto-completo-y-cortes.md](contracts/contexto-completo-y-cortes.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-019 exige pruebas automáticas de la ampliación de contexto, el tope, la detección de cortes y el reintento. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md), precedidas por la base común.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. No desplegar ni encender servicios de Railway ni gastar sin la autorización del usuario (T024 la pide).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin migraciones ni reindexación** (plan, R5): las notas van en `reject_reason`. Sin dependencias nuevas.
- **Con las dos opciones apagadas el comportamiento debe ser idéntico al de antes** (FR-013): mismo contexto, instrucciones, respuesta, fuentes, costo y registro.
- La lógica no depende de un proveedor (principio III): el motivo de fin es un campo opcional común; un proveedor que no lo informe sigue funcionando.
- La respuesta de `POST /query` conserva su estructura (FR-017) y la feature 006 (`QUERY_CITED_SOURCES`) debe seguir funcionando en todas las combinaciones (FR-015).
- Es un prototipo: lo más simple que cumpla la especificación.
- Para cambiar variables de Railway durante la medición: siempre `railway variable set ... --skip-deploys` y luego `python scripts/servicios.py encender MIA --forzar --ref origin/dev`. Sin `--skip-deploys`, Railway redespliega desde `main` y se pierde el código de `dev` (ver OPERACION.md).

---

## Phase 1: Setup

**Purpose**: archivos nuevos y esqueleto de pruebas.

- [ ] T001 [P] Crear `src/mia/rag/completeness.py` con un docstring que explique su propósito (contexto completo de los documentos principales, marca de continuación, decisión de reintento y aviso de posible corte; ver [contracts/contexto-completo-y-cortes.md](contracts/contexto-completo-y-cortes.md)) y sin lógica todavía
- [ ] T002 [P] Crear `tests/unit/test_completeness.py` y `tests/unit/test_query_completeness.py` con los `import` mínimos; el segundo toma como modelo `tests/unit/test_query_citations.py` (fixtures `base`, `client`, `make_artifact`, `modes_config` y el helper `_consultar` que simula almacén, embeddings y modelo)

**Checkpoint**: `pytest` sigue pasando.

---

## Phase 2: Foundational (bloquea a todas las historias)

**Purpose**: configuración, interpretación de las opciones, motivo de fin de la generación y tope de gasto con costo pendiente.

- [ ] T003 Agregar en `src/mia/config.py`, junto a las demás `query_*`, con un comentario que remita a `src/mia/rag/completeness.py` y a la spec, estos campos de [data-model.md](data-model.md): `query_complete_context: str = "off"`, `query_complete_documents: int = Field(default=1, ge=1, le=8)`, `query_complete_document_max_chunks: int = Field(default=25, ge=1, le=100)`, `query_complete_forward_neighbors: int = Field(default=4, ge=0, le=20)`, `query_context_max_chars: int = Field(default=80000, ge=5000, le=400000)` y `query_retry_cut_answers: str = "off"`. Las dos opciones de encendido son **texto** (como `query_cited_sources`) para que un valor inválido no impida el arranque (FR-012); los enteros siguen el patrón de `query_search_limit`. Agregar las seis líneas con su comentario a `.env.example`
- [ ] T004 En `src/mia/rag/completeness.py`, implementar `switch_enabled(value: str, variable: str) -> bool` (`on`, `true`, `1`, `yes` sin distinguir mayúsculas ni espacios devuelven `True`; `off`, `false`, `0`, `no` y vacío devuelven `False`; **otro valor devuelve `False` y deja un aviso con `logging` que nombra la variable, una sola vez por variable y valor y por proceso**), y los envoltorios `complete_context_enabled(value)` y `retry_cut_enabled(value)` con los nombres `QUERY_COMPLETE_CONTEXT` y `QUERY_RETRY_CUT_ANSWERS`. Con sus pruebas en `tests/unit/test_completeness.py` (valores válidos, mayúsculas, espacios, inválido con aviso comprobado con `caplog`, aviso único, y limpiar el conjunto de valores avisados entre pruebas)
- [ ] T005 En `src/mia/rag/llm.py`, agregar a `LLMAnswer` el campo `finish_reason: str | None = None` ("`stop`, `length`, `other` o nulo") y la función `normalize_finish_reason(raw: str | None, kind: str) -> str | None` con la tabla de [data-model.md](data-model.md): para `kind="openai"` (OpenRouter y GLM) `stop` da `stop`, `length` da `length`, otro valor no vacío da `other`; para `kind="anthropic"` `end_turn` y `stop_sequence` dan `stop`, `max_tokens` da `length`, otro valor da `other`; `None` o vacío da `None`. Con pruebas en `tests/unit/test_completeness.py`
- [ ] T006 Hacer que los proveedores informen el motivo de fin en `LLMAnswer.finish_reason`: en `src/mia/rag/providers/openrouter_llm.py` y `glm_llm.py` a partir de `completion.choices[0].finish_reason`, en `anthropic_llm.py` a partir de `message.stop_reason`; `gemini_llm.py` lo deja en `None` (la API de interacciones no expone uno comparable). No cambiar nada más. Agregar pruebas en `tests/unit/test_openrouter_llm.py` y `tests/unit/test_glm_llm.py` (motivo `stop`, `length` y ausente) siguiendo cómo esos archivos simulan al cliente, y confirmar que las pruebas existentes de los cuatro proveedores siguen pasando
- [ ] T007 En `src/mia/access/caps.py`, agregar a `check_caps` un parámetro opcional `extra: Decimal = Decimal(0)` ("gasto de esta consulta aún no registrado") que se suma al gasto de hoy de la API, del artefacto y del modo con razonamiento antes de compararlo con su tope; sin él, el comportamiento no cambia. Con pruebas en `tests/unit/test_caps.py`: sin `extra` igual que antes, y con `extra` un tope que no estaba alcanzado pasa a estarlo en cada uno de los tres ámbitos

**Checkpoint**: `pytest` completo pasa; el comportamiento no cambió.

---

## Phase 3: User Story 1 - Recibir la lista o sección completa (Priority: P1) 🎯 MVP

**Goal**: con `QUERY_COMPLETE_CONTEXT=on`, el documento principal se entrega completo si tiene hasta 25 fragmentos y, si es más largo, con fragmentos posteriores; lo que no llega al final del documento lleva la marca de continuación.

**Independent Test**: `pytest tests/unit/test_context.py tests/unit/test_completeness.py tests/unit/test_query_completeness.py`: con un documento principal simulado de 15 fragmentos, el modelo recibe los 15; con uno de 60, recibe los relevantes con 4 posteriores y la marca; los documentos secundarios no cambian.

### Pruebas primero

- [ ] T008 [US1] En `tests/unit/test_context.py` (que ya usa `_chunk` y un almacén simulado), pruebas de la nueva política de `build_passages`: (a) sin política el resultado es idéntico al de siempre; (b) el documento del mejor resultado con 15 fragmentos se entrega completo, en un solo pasaje, con `continues` falso; (c) uno de 60 fragmentos con un resultado en el índice 20 entrega del 19 al 24 (1 anterior y 4 posteriores) y `continues` verdadero; (d) con `forward_neighbors=0` entrega solo el anterior; (e) los documentos secundarios siguen con 1 vecino a cada lado, o completos si tienen 12 o menos; (f) con `documents=2` el segundo documento de mejor resultado también recibe el trato; (g) con un tope de caracteres que no alcanza se descartan primero los pasajes secundarios de menor puntaje y nunca los del documento principal; (h) `continues` es falso en un pasaje que llega al último fragmento y verdadero si quedan fragmentos posteriores sin entregar
- [ ] T009 [US1] En `tests/unit/test_completeness.py`, pruebas de `CONTINUES_MARKER` (la línea `[...el documento continúa]`), de `mark_continuation(text, continues)` (agrega la marca como línea final solo si `continues`) y de `COMPLETENESS_INSTRUCTIONS` (menciona la marca y que no se escriba la advertencia si el fragmento no la lleva; sin guion largo)
- [ ] T010 [US1] En `tests/unit/test_query_completeness.py`, pruebas de la ruta con `QUERY_COMPLETE_CONTEXT=on` (`monkeypatch.setattr(settings, "query_complete_context", "on")`): el modelo simulado recibe el documento principal completo, el texto del pasaje con `continues` termina con la marca, las instrucciones terminan con `COMPLETENESS_INSTRUCTIONS` (y con la feature 006 también encendida, el párrafo de citas va **después** del de completitud y la línea `FUENTES:` sigue funcionando), el `excerpt` de las fuentes de la respuesta **no** lleva la marca, y con el tope de caracteres bajo se descartan pasajes secundarios y el principal se conserva

### Implementación

- [ ] T011 [US1] En `src/mia/rag/context.py`, agregar a `Passage` el campo `continues: bool = False` ("verdadero solo si `last_index + 1` es menor que el total de fragmentos del documento"), un `dataclass` `ContextPolicy` (`documents`, `document_max_chunks`, `forward_neighbors`, `max_chars`) y el parámetro opcional `policy: ContextPolicy | None = None` de `build_passages`. Con política: los `documents` documentos de mejor puntaje se completan según el tamaño (hasta `document_max_chunks` fragmentos, completos; si no, 1 anterior y `forward_neighbors` posteriores por resultado), los demás siguen como hoy; se calcula `continues` con `count_chunks`; y si la suma de caracteres supera `max_chars` se descartan pasajes de los documentos no principales, de menor a mayor puntaje. Sin política, el resultado no cambia. Hacer que T008 pase
- [ ] T012 [US1] En `src/mia/rag/completeness.py`, definir `CONTINUES_MARKER = "[...el documento continúa]"`, `mark_continuation(text, continues)` y `COMPLETENESS_INSTRUCTIONS` con el párrafo de [contracts/contexto-completo-y-cortes.md](contracts/contexto-completo-y-cortes.md) (corto, en español, sin guion largo). Hacer que T009 pase
- [ ] T013 [US1] En `src/mia/api/routes/query.py`, cuando `complete_context_enabled(settings.query_complete_context)` (leído en cada consulta): construir el `ContextPolicy` con las variables, pasarlo a `build_passages`, poner en el `excerpt` del `RagContext` (no en el de `Source`) el texto con `mark_continuation`, y agregar `COMPLETENESS_INSTRUCTIONS` a las instrucciones **antes** del párrafo de citas. Con la opción apagada no ejecutar nada de esto. Hacer que T010 pase

**Checkpoint**: US1 completa; con la opción encendida, los temarios de curso llegan completos al modelo.

---

## Phase 4: User Story 2 - Detectar una respuesta cortada y no entregarla como completa (Priority: P1)

**Goal**: con `QUERY_RETRY_CUT_ANSWERS=on`, un fin anormal de la generación se reintenta una vez (con los topes de gasto) y, si vuelve a cortarse, se entrega con aviso.

**Independent Test**: respuestas simuladas con motivo `length` u `other`: se reintenta una vez; un segundo intento normal reemplaza al primero; si ambos se cortan el texto lleva el aviso y el registro de Uso lo anota con los costos sumados.

### Pruebas primero

- [ ] T014 [US2] En `tests/unit/test_completeness.py`, pruebas de las funciones puras del reintento: `needs_retry(finish_reason, is_no_info)` (verdadero para `length` y `other`; falso para `stop`, `None` y cuando es "sin información"), `CUT_NOTICE == "Aviso: la respuesta pudo quedar incompleta."`, `with_notice(text)` (línea en blanco y luego el aviso, sin repetirlo si ya está), `merge_attempts(first, second)` (suma `prompt_tokens`, `completion_tokens`, `reasoning_tokens` y `cost_usd` tratando los nulos como cero, conserva el modelo), y `combine_notes(*notes)` (une las no nulas con `"; "`)
- [ ] T015 [US2] En `tests/unit/test_query_completeness.py`, pruebas de la ruta con `QUERY_RETRY_CUT_ANSWERS=on`, una por fila de la sección 3 del contrato: (a) motivo `stop`, `None`: una sola llamada; (b) `length` y segundo intento `stop`: dos llamadas, se entrega el segundo texto, `reject_reason == "Respuesta cortada: se reintentó"`, costo y tokens sumados en el registro; (c) `length` dos veces: se entrega el texto más largo con el aviso al final y `reject_reason == "Respuesta cortada: se entregó con aviso"`; (d) respuesta `SIN_INFORMACION` con motivo `length`: una sola llamada y "sin información"; (e) un tope de gasto alcanzado con el costo del primer intento (preparar el artefacto con un tope bajo): sin segunda llamada, texto con aviso; (f) el segundo intento lanza una excepción: se entrega el texto del primero con aviso y no un 502; (g) la combinación con la feature 006 (si no hay citas válidas y además hubo reintento, `reject_reason` une las dos notas con `"; "`, y el aviso va después de quitar la línea `FUENTES:`); (h) opción apagada: aunque el motivo sea `length`, una sola llamada y sin aviso, pero con el `logger.info` del motivo de fin comprobado con `caplog` (también con motivo `stop`)

### Implementación

- [ ] T016 [US2] En `src/mia/rag/completeness.py`, implementar `CUT_NOTICE`, `needs_retry`, `with_notice`, `merge_attempts`, `combine_notes` y las constantes de nota `NOTE_RETRIED = "Respuesta cortada: se reintentó"` y `NOTE_NOTICE = "Respuesta cortada: se entregó con aviso"`. Hacer que T014 pase
- [ ] T017 [US2] En `src/mia/api/routes/query.py`, con `retry_cut_enabled(settings.query_retry_cut_answers)`: tras la primera llamada, quitar la línea de fuentes de la 006 si está encendida y detectar "sin información" sobre el texto limpio; si `needs_retry(answer.finish_reason, es_sin_informacion)`, consultar `check_caps(session, artifact, mode, extra=<costo del primer intento>)` (el costo del primer intento es `answer.cost_usd` y, si es nulo, `estimate_cost(...)`, como ya hace la ruta) y, si no hay tope alcanzado, repetir la llamada una vez dentro de su propio `try` (si falla, usar el primer intento); sumar los dos intentos con `merge_attempts` **antes** de calcular y registrar costo y tokens (y volver a interpretar la línea de fuentes solo sobre el texto del intento que se entrega); escoger el texto (el segundo si termina normal; si no, el más largo) y, si sigue cortado, agregar `with_notice` **después** de quitar la línea `FUENTES:` y de decidir "sin información"; poner las notas con `combine_notes` en `log.reject_reason`. La latencia ya incluye el reintento. Con la opción apagada no ejecutar nada de esto, **salvo un `logger.info` que se emite siempre, con cualquier combinación de opciones, con el motivo de fin de la generación y el modo** (por ejemplo `Fin de la generación: length (modo literal)`), que es lo que permite contar cortes en el control (FR-006); no cambia la respuesta, el costo ni el registro de Uso. Hacer que T015 pase

**Checkpoint**: US1 y US2 completas; las dos causas de respuestas incompletas están cubiertas.

---

## Phase 5: User Story 3 - Poder apagarlo y volver al comportamiento anterior (Priority: P2)

**Goal**: cada opción se enciende por separado y apagadas son idénticas a antes.

**Independent Test**: `pytest tests/unit/test_query_completeness.py -k "apagad or independ"`.

- [ ] T018 [US3] En `tests/unit/test_query_completeness.py`, pruebas de independencia y de apagado: (a) con ambas opciones apagadas (valor por defecto sin forzarlo) el modelo recibe los mismos contextos, sin marca ni `reference`, las instrucciones exactas del modo, el texto de la respuesta intacto aunque termine con `FUENTES:` o con un motivo `length`, y `reject_reason` nulo (FR-013); (b) solo contexto completo encendido: hay marca e instrucción pero ningún reintento aunque el motivo sea `length`; (c) solo reintento encendido: el contexto es el de siempre y sí hay reintento; (d) un valor inválido en cualquiera de las dos se comporta como apagado y deja el aviso una sola vez; (e) valores `ON`, ` true `, `1`, `yes` encienden; (f) las opciones se leen en cada consulta (cambiar la variable entre dos consultas cambia el comportamiento)
- [ ] T019 [US3] Verificar y, si falta, ajustar en `src/mia/api/routes/query.py` que `complete_context_enabled` y `retry_cut_enabled` se evalúen dentro del endpoint en cada consulta y que, apagadas, no ejecuten ninguna ruta nueva ni cambien las instrucciones. Hacer que T018 pase
- [ ] T020 [P] [US3] Documentar las opciones en [docs/OPERACION.md](../../docs/OPERACION.md): filas en la tabla de variables de entorno para las seis variables (valores, defectos, qué hacen), una sección breve "Respuestas completas y sin cortes" (qué hacen los dos mecanismos, que se cambian en Railway con `--skip-deploys` y se redesplegan con `encender --ref`, que volver a `off` devuelve el comportamiento anterior sin migraciones, y el criterio de la reserva hasta 50 % de R11), una fila en "Problemas frecuentes" para las notas `Respuesta cortada: ...` del módulo Uso, y los límites conocidos: por defecto solo el documento de mejor resultado se completa (`QUERY_COMPLETE_DOCUMENTS=1`, una lista repartida en dos documentos exige subirlo), y en un documento de cientos de fragmentos no se puede garantizar la lista completa (la respuesta debe decir que continúa). En [docs/PRUEBAS_MVP.md](../../docs/PRUEBAS_MVP.md), donde se menciona el límite conocido de las listas largas, agregar que la feature 007 lo mitiga con `QUERY_COMPLETE_CONTEXT`

**Checkpoint**: US3 completa; la función es segura de desplegar apagada.

---

## Phase 6: User Story 4 - Medir con listas largas (Priority: P2)

**Goal**: casos de listas largas con su último ítem esperado y métricas de reintento, aviso y terminación sin puntuación, medidos en producción contra un control.

**Independent Test**: `pytest tests/unit/test_linea_base.py` con las pruebas nuevas, y las tres corridas comparables con `comparar`.

### Pruebas primero

- [ ] T021 [US4] En `tests/unit/test_linea_base.py`, pruebas de lo nuevo: la categoría `lista_larga` es válida y exige `contiene` en `cargar_casos`; `evaluar_respuesta` devuelve `termina_sin_puntuacion` (verdadero si el texto, sin espacios finales, no termina en `.`, `!`, `?`, `)`, `:`, `;`, comillas ni `*`, y falso en caso contrario, sin guardar el texto) y `aviso_de_corte` (verdadero si el texto contiene `Aviso: la respuesta pudo quedar incompleta.`); `leer_costo` devuelve `reject_reason` (ya lo hace) y `correr_respuestas` registra `reintento` (verdadero si la nota empieza por `Respuesta cortada: se reintentó`; nulo si no hubo detalle); `resumen_respuestas` suma `reintentos`, `avisos_de_corte` y `terminan_sin_puntuacion` con sus proporciones sobre las respuestas con contenido; `comparar` e `informe` muestran esos datos; y las corridas viejas, sin esos campos, se leen sin error

### Implementación

- [ ] T022 [US4] En `scripts/linea_base.py`, agregar `lista_larga` a `CATEGORIAS` (con `contiene` obligatorio para esa categoría), calcular `termina_sin_puntuacion` y `aviso_de_corte` en `evaluar_respuesta` sin guardar el texto, registrar `reintento` en `correr_respuestas` desde la nota de Uso, sumar los tres en `resumen_respuestas`, mostrarlos en `generar_informe` y `comparar`, y agregar una nota con los campos nuevos a [specs/005-linea-base-busqueda/contracts/linea-base-cli.md](../005-linea-base-busqueda/contracts/linea-base-cli.md). Hacer que T021 pase
- [ ] T023 [US4] Preparar los casos de `lista_larga` en `scripts/datos/casos_busqueda.json` (mínimo 8): contenidos de los cursos Diseño de Experimentos (MC6104), Deep Learning (MC8840), Procesamiento de Lenguaje Natural (MC8850), Redes Neuronales (MC8803), Introducción a la Investigación (MC7201) y Sistemas Operativos Avanzados (MC6004) en el dominio `Unidad de Postgrados de Computación / Currículum`, las líneas de TFG (`Líneas de TFG.pdf`, ya cubierta por `U4` pero con el último ítem en `contiene`) y una lista de un acta (acuerdos de una sesión concreta). Agregar además uno o dos casos en documentos grandes donde la lista no cabe completa (por ejemplo, una lista del reglamento del programa, de 37 fragmentos, y una del plan de estudios de Ciberseguridad, de 309), con `contiene` igual a un ítem que aparezca al comienzo de la lista, para juzgar a mano en T028 si la respuesta sale completa o dice que la lista continúa (FR-004). Para cada caso, leer el último ítem del documento con una consulta de solo lectura a Qdrant (sin imprimir ni guardar más que ese ítem) y escoger como `contiene` **una palabra o frase corta y distintiva del ítem, no la línea entera** (el modelo suele reformular, y una búsqueda de la línea completa daría falsos fallos); **mostrarle al usuario la lista de pares caso y texto de `contiene` para que los confirme antes de escribirlos**; documentar en cada caso el documento esperado (`documentos`) y una `nota` breve
- [ ] T024 [US4] **Pedir al usuario autorización** para la medición, y esperar su respuesta: (a) desplegar `origin/dev` en producción solo para medir (`--ref origin/dev`); (b) las tres corridas (control con todo apagado, contexto completo, contexto completo y reintento) con un tope por corrida (propuesta: 0,40 USD cada una, unos 1,00 USD en total con margen para repetir); (c) activar y desactivar el artefacto `PRUEBA Aceptación ambas unidades` y regenerar su clave al terminar; (d) dejar las variables de la 007 en `off` al terminar salvo que él decida otra cosa. No avanzar sin su respuesta
- [ ] T025 [US4] Con la autorización de T024 y los casos de T023 confirmados: subir `origin/dev` con ambas opciones de la 007 en `off` y correr el **control** (`respuestas --etiqueta control7 ... --tope-usd <N>`); correr `comparar base control7` y anotar las diferencias de documentos mostrados (SC-007: con todo apagado deben ser cero, salvo variación del modelo), el número de consultas, el gasto, las listas que hoy salen cortadas y la cantidad de respuestas con motivo de fin anormal, que se cuenta con `railway logs -s MIA` (la línea base del problema, historia 4, escenario 1)
- [ ] T026 [US4] Fijar `QUERY_COMPLETE_CONTEXT=on` con `--skip-deploys`, redesplegar con `encender --ref origin/dev` y correr `respuestas --etiqueta completo ...`; comparar con `comparar control7 completo`. Verificar antes que los tokens por consulta cambian (si son idénticos al control, el despliegue volvió a `main`: ver el aviso de las reglas)
- [ ] T027 [US4] Fijar además `QUERY_RETRY_CUT_ANSWERS=on` con `--skip-deploys`, redesplegar y correr `respuestas --etiqueta completo-reintento ...`; comparar con `comparar control7 completo-reintento`. Si algún caso de la batería del MVP empeora, repetirlo una vez antes de contarlo como regresión (el modelo no es determinista)
- [ ] T028 [US4] Evaluar las corridas contra los criterios de [spec.md](spec.md) y escribir el resultado a mano en una sección "Resultado de la feature 007" de [docs/LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md) (después de `## Lectura`): SC-001 (último ítem en el 100 % de las listas largas), SC-002 (ninguna respuesta cortada sin aviso en al menos 80 consultas), SC-003 (los 19 de la batería y los "sin información"), SC-004 (reintentos en 5 % o menos), SC-005 y SC-006 (costo medio y latencia p50 hasta 25 % por encima de la línea base, contra el promedio de `base`, `control` y `control7` y por la mediana de la razón por caso), SC-007 (con todo apagado, mismas fuentes que la línea base), SC-008 (con la 006 encendida, la regla de seguridad de las citas en 10 % o menos). Incluir una recomendación (encender cada opción o no) y, si alguna lista de un documento grande sigue cortada, el efecto estimado de subir `QUERY_COMPLETE_FORWARD_NEIGHBORS` o `QUERY_COMPLETE_DOCUMENTS` dentro de la reserva de 50 %, **sin aplicarlo sin la aprobación del usuario**. No encender nada por defecto: decide el usuario
- [ ] T029 [US4] Dejar todo como se acordó en T024: variables en `off` con `--skip-deploys` (o como decida el usuario), artefacto de prueba desactivado y su clave regenerada, API apagada con `python scripts/servicios.py apagar MIA --forzar`, y confirmar con `python scripts/servicios.py estado`

**Checkpoint**: US4 completa; hay datos para decidir qué encender.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T030 [P] Actualizar [docs/ARQUITECTURA.md](../../docs/ARQUITECTURA.md) (sección "Flujo de una consulta y de una ingesta"): la política de contexto completo, la marca de continuación, el motivo de fin en `LLMAnswer`, el reintento acotado por los topes de gasto, el aviso y las notas en el registro de Uso, y la relación con la feature 006
- [ ] T031 [P] Actualizar [docs/Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md): agregar el requerimiento BUS-8 ("ninguna respuesta incompleta ni cortada") a la tabla de la sección 2.3, su estado y el resultado de la medición con enlace a [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md), y su criterio en la sección 2.9
- [ ] T032 Correr `ruff check src tests scripts` y `pytest` completo y corregir lo que falle; verificar con `git diff --stat main..dev -- src/mia/storage/migrations alembic` que no hay migraciones, con `git diff main..dev -- src/mia/api/routes/query.py` que la estructura de `QueryResponse` no cambió, y con `grep -rnP "\x{2014}"` sobre los archivos tocados que no hay guion largo
- [ ] T033 Pedir al usuario una comprobación manual de SC-009 con tres preguntas de temarios largos (por ejemplo, contenidos de Diseño de Experimentos, de Deep Learning y de Procesamiento de Lenguaje Natural, con `scripts/cliente.py` o Swagger contra la API encendida con la opción): que confirme si cada respuesta es la lista completa del documento. Anotar su respuesta en la sección de resultado de [docs/LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)
- [ ] T034 Hacer commit en `dev` por etapa (base común, contexto completo, reintento, herramienta, documentación) con mensajes en español sin atribución y `git push origin dev`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; T001 y T002 en paralelo.
- **Foundational (Phase 2)**: depende de Setup y bloquea las historias. T003 a T007 tocan archivos distintos salvo T004 y T005, que comparten `tests/unit/test_completeness.py`: hacerlos en orden. T006 depende de T005.
- **US1 (Phase 3)**: depende de Foundational. Pruebas (T008 a T010) antes de la implementación (T011 a T013); T013 depende de T011 y T012.
- **US2 (Phase 4)**: depende de Foundational (T005, T006 y T007) y de US1 para el orden de las instrucciones y del flujo de la ruta (T013).
- **US3 (Phase 5)**: depende de US1 y US2 (necesita los dos mecanismos); T020 (documentación) es paralelo a T018 y T019.
- **US4 (Phase 6)**: T021, T022 y T023 solo dependen de la feature 005 y de US1 para los casos; pueden hacerse en paralelo con US1 a US3, pero **T021 y T022 deben estar terminadas antes de T025**. T024 a T029 dependen de US1 a US3 terminadas y de la autorización del usuario; T025 a T027 son secuenciales (cada una redespliega).
- **Polish (Phase 7)**: al final; T030 y T031 en paralelo.

### Parallel Opportunities

- T001 y T002; T020 en paralelo con T018 y T019; T021 a T023 en paralelo con US1 a US3 (archivos distintos); T030 y T031.
- Casi todo `src/` pasa por `query.py`, `context.py` y `completeness.py`, así que no se paraleliza dentro de una historia.

---

## Implementation Strategy

### MVP (US1 + US2 + US3)

1. Setup y Foundational: configuración, interpretación de las opciones, motivo de fin, tope de gasto con costo pendiente.
2. US1 (contexto completo) y US2 (reintento): **parar y validar** con `pytest`: ya hay una función completa, probada y apagada por defecto.
3. US3: confirmar que apagada es idéntica y documentar las variables.

### Entrega incremental

1. MVP desplegable apagado, sin riesgo.
2. US4: casos de listas largas, autorización, tres corridas y decisión.
3. Polish y commits.

### Riesgos a vigilar

- Que apagado algo cambie: T005, T008 (a), T018 (a) lo comprueban.
- Que el costo sobrepase el 25 % en literal (la estimación es +21 %, con poco margen): T028 lo mide contra el promedio de las corridas de referencia y por la mediana por caso; las variables permiten reducir el alcance sin tocar código.
- Que un despliegue de `main` reemplace el código de `dev` durante la medición: T026 verifica que los tokens cambien antes de aceptar la corrida.
- Que el reintento gaste de más: solo se hace con un fin anormal, una vez, y respetando los topes (T007, T015 e).
- Que la numeración de pasajes de la 006 y la marca de continuación choquen: T010 y T015 (g) cubren las combinaciones.
