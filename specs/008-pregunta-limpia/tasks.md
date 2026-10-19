---

description: "Tareas de implementación de la feature 008: pregunta limpia (segundo intento de búsqueda)"
---

# Tasks: Pregunta limpia (segundo intento de búsqueda)

**Input**: Design documents from `specs/008-pregunta-limpia/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-014 exige pruebas automáticas en tabla de las reglas, las guardas, los negativos y la integración con la consulta. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md), precedidas por la base común.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. No desplegar ni encender servicios de Railway ni gastar sin la autorización del usuario (T026 la pide).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin migraciones ni reindexación** (plan, R7): la nota va en `reject_reason`. Sin dependencias nuevas (solo `re` y `unicodedata`).
- **Sin ninguna llamada nueva a un modelo de lenguaje** (FR-002): el segundo intento solo calcula un embedding local y hace una búsqueda.
- **Con la opción apagada el comportamiento debe ser idéntico al de antes** (FR-010): misma búsqueda, contexto, respuesta, fuentes, costo y registro.
- El modelo recibe siempre la pregunta original (`payload.question`); la pregunta limpia solo cambia qué se busca (research R6).
- La respuesta de `POST /query` conserva su estructura (FR-012) y las features 006 y 007 deben seguir funcionando en todas las combinaciones (FR-007).
- Es un prototipo: lo más simple que cumpla la especificación.
- Para cambiar variables de Railway durante la medición: siempre `railway variable set ... --skip-deploys` y luego `python scripts/servicios.py encender MIA --forzar --ref origin/dev`. Sin `--skip-deploys`, Railway redespliega desde `main` y se pierde el código de `dev` (ver OPERACION.md).

---

## Phase 1: Setup

**Purpose**: archivos nuevos y esqueleto de pruebas.

- [X] T001 [P] Crear `src/mia/rag/query_rewrite.py` con un docstring que explique su propósito (segundo intento de búsqueda con la pregunta limpia, por reglas de texto y sin modelo; ver [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md)) y sin lógica todavía
- [X] T002 [P] Crear `tests/unit/test_query_rewrite.py` y `tests/unit/test_query_clean_question.py` con los `import` mínimos; el segundo toma como modelo `tests/unit/test_query_completeness.py` (fixtures `base`, `client`, `make_artifact`, `modes_config`, la clase `_AlmacenDeRuta` y el helper `_consultar` que simula almacén, embeddings y modelo, adaptado para que el almacén devuelva una lista de resultados distinta en la primera y en la segunda llamada a `search`)

**Checkpoint**: `pytest` sigue pasando.

---

## Phase 2: Foundational (bloquea a todas las historias)

**Purpose**: la variable de configuración y su interpretación.

- [X] T003 Agregar en `src/mia/config.py`, junto a las demás `query_*`, con un comentario que remita a `src/mia/rag/query_rewrite.py` y a la spec, el campo de [data-model.md](data-model.md) `query_clean_question: str = "off"`. Es **texto** (como `query_cited_sources`) para que un valor inválido no impida el arranque (FR-008). Agregar `QUERY_CLEAN_QUESTION=off` con su comentario a `.env.example`
- [X] T004 En `src/mia/rag/query_rewrite.py`, implementar `clean_question_enabled(value: str) -> bool` como `switch_enabled(value, "QUERY_CLEAN_QUESTION")` importando `switch_enabled` de `mia.rag.completeness` (no duplicar la lógica de on/off ni el aviso único). Con pruebas en `tests/unit/test_query_rewrite.py`: `on`, `true`, `1`, `yes` (con mayúsculas y espacios) devuelven `True`; `off`, `false`, `0`, `no` y vacío devuelven `False`; otro valor devuelve `False` y deja un aviso que nombra `QUERY_CLEAN_QUESTION` (comprobado con `caplog`) una sola vez (limpiar `completeness._INVALID_VALUES_WARNED` entre pruebas)

**Checkpoint**: `pytest` completo pasa; el comportamiento no cambió.

---

## Phase 3: User Story 1 - Encontrar a una persona o un término preguntando "¿Quién es X?" o "¿Qué es X?" (Priority: P1) 🎯 MVP

**Goal**: una pregunta de identificación o descripción que no pasa el umbral se reduce a lo que se busca, se repite la búsqueda una vez y, si hay fragmentos, el modelo responde con ellos.

**Independent Test**: `pytest tests/unit/test_query_rewrite.py tests/unit/test_query_clean_question.py`: la tabla de reducción pasa y, con la opción encendida, una pregunta de identificación cuya primera búsqueda no pasa el umbral y cuyo segundo intento sí pasa llega al modelo (una sola llamada) con la pregunta original y con los fragmentos del segundo intento.

### Tests de US1 (escribir primero; deben fallar)

- [X] T005 [P] [US1] En `tests/unit/test_query_rewrite.py`, una prueba parametrizada en tabla de `clean_question` con las filas positivas de [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md) ("Casos de la tabla de pruebas"): "¿Quién es Natalia Soto Solís?", "quien es natalia soto solis" (el resultado conserva la escritura original: "natalia soto solis"), "¿Qué es el TFG?", "¿Qué son las líneas de TFG?", "¡Háblame de Cibercrimen!", "¿Me puedes decir quién es Joseph Obando Sandí?", "Por favor, dime qué es el IPA", "Dame información sobre la maestría", "¿Qué se sabe de Cibercrimen?". Agregar variantes: con y sin tildes ("QUIÉN ES" y "QUIEN ES"), con y sin signos de apertura, con espacios y puntos sobrantes ("  ¿Quién es X?  .") y con espacios dobles en el medio ("¿Quién   es   X?", cuyo resultado debe cortarse bien del original) y con "por favor" al final ("¿Quién es X, por favor?"). Agregar una prueba de que el texto devuelto conserva las tildes y mayúsculas de la pregunta original ("¿Qué es la Maestría en Analítica?" devuelve "Maestría en Analítica")
- [X] T006 [P] [US1] En `tests/unit/test_query_clean_question.py`, pruebas de la ruta con `QUERY_CLEAN_QUESTION=on` (primera búsqueda sin resultados sobre el umbral, segunda con): se llama al modelo una sola vez; el modelo recibe como pregunta la original (`payload.question`) y como contexto los fragmentos del segundo intento; el almacén recibió dos búsquedas con los mismos dominios y el mismo `limit` (el de `config.search_limit` del modo, probar `literal` y `razonamiento`); el embedding del segundo intento se pidió con el texto reducido y `is_query=True`; la respuesta es `answered` con las fuentes del segundo intento y la misma estructura de `QueryResponse` de siempre (mismas claves, FR-012); repetir la prueba con `QUERY_COMPLETE_CONTEXT=on` y comprobar que el contexto entregado es el ampliado de la feature 007 sobre los fragmentos del segundo intento (FR-007)
- [X] T007 [P] [US1] En `tests/unit/test_query_clean_question.py`, pruebas de la ruta: si la primera búsqueda ya pasa el umbral no hay segunda búsqueda (el almacén se llamó una vez y el embedding se calculó una vez); si el segundo intento tampoco pasa el umbral, la respuesta es "sin información" (`no_info`), el modelo no se llama y no hay una tercera búsqueda

### Implementación de US1

- [X] T008 [US1] En `src/mia/rag/query_rewrite.py`, implementar `clean_question(question: str) -> str | None` según el algoritmo de [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md): normalización de la misma longitud que el original (minúsculas y sin tildes carácter por carácter, espacios colapsados), signos `¿ ? ¡ !` y `. , ; :` quitados de los extremos, hasta dos cortesías iniciales (colapsando antes los espacios de la pregunta original para que original y copia normalizada compartan índices, contrato paso 1) y "por favor" o "gracias" al final, una envoltura de la tabla (identificación, pedir información, pedir que hable de algo) y el candidato cortado del original con los mismos índices. Las expresiones regulares como constantes de módulo con un comentario por grupo, todas con límite de palabra. Sin la guarda del candidato todavía (llega en T013): por ahora solo exige que el candidato no esté vacío
- [X] T009 [US1] En `src/mia/api/routes/query.py`, tras calcular `relevant`: si `not relevant` y `clean_question_enabled(settings.query_clean_question)`, llamar a `clean_question(payload.question)`; si devuelve texto, calcular su embedding con `embedding_provider.embed([cleaned], is_query=True)[0]`, repetir `vector_store.search(..., domains=payload.domains, limit=config.search_limit)` y recalcular `relevant` con el mismo umbral. El resto del flujo sigue igual, con `payload.question` como pregunta del modelo (research R6). Un solo intento: no hay bucle ni segunda llamada a `clean_question`

**Checkpoint**: US1 funcional y probable por separado: la tabla de reducción y la ruta pasan.

---

## Phase 4: User Story 2 - No tocar las preguntas que no son de identificación ni inventar respuestas (Priority: P1)

**Goal**: las preguntas que piden un dato, las compuestas y las que quedarían demasiado cortas o largas no se reformulan; una pregunta de identificación sobre algo ausente sigue respondiendo "sin información".

**Independent Test**: `pytest tests/unit/test_query_rewrite.py -k negativ` pasa con todas las filas negativas; en la ruta, una pregunta de créditos nunca hace segunda búsqueda.

### Tests de US2 (escribir primero; deben fallar)

- [X] T010 [P] [US2] En `tests/unit/test_query_rewrite.py`, una prueba parametrizada de negativos (todas deben devolver `None`) con las filas de [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md): "¿Cuántos créditos tiene el curso de IPA en Big Data?", "¿Cuál es el costo del curso X?", "¿Qué es lo que establece el reglamento sobre las becas?", "¿Qué es el TFG que ofrece la maestría?", "¿Quién es X? ¿Y cuántos créditos tiene Y?", "¿Quién es?", "¿Qué es la I?" (menos de 3 caracteres), "Por favor, ¿cuántos créditos tiene X?", "Natalia Soto Solís" (sin envoltura). Agregar: "¿Cómo se aprueba el curso?", "¿Qué requisitos tiene el curso X?", "¿Cuántas horas tiene el curso?", "¿Por qué se cerró la matrícula?", la cadena vacía, una cadena solo de signos, "¿Qué es necesario para graduarse?", "¿Qué es obligatorio en el TFG?" y una pregunta que no está en español ("Who is Natalia Soto?")
- [X] T011 [P] [US2] En `tests/unit/test_query_rewrite.py`, pruebas de cada guarda del candidato (R4): menos de 3 caracteres ("¿Qué es el IP?" con un candidato de 2 letras devuelve `None`), el candidato igual a la pregunta normalizada (si una envoltura dejara la pregunta intacta), más de 8 palabras (un candidato de 9 palabras devuelve `None` y uno de 8 pasa), que empiece con "lo" o "que", que contenga "que", "cuando", "donde", "cuanto", "cuantos", "cuantas", "cuanta" o "porque" como palabra completa, que empiece con "necesario", "obligatorio", "posible", "suficiente", "importante", "mejor", "igual" o "diferente" (y que una palabra que solo las contiene, como "Quevedo" o "Dondelio", no las active), y signos `¿ ? ¡ !` en el interior
- [X] T012 [P] [US2] En `tests/unit/test_query_clean_question.py`, pruebas de la ruta con la opción encendida: una pregunta que `clean_question` no reduce ("¿Cuántos créditos tiene el curso X?") con la primera búsqueda sin resultados sobre el umbral no hace segunda búsqueda y responde "sin información" sin llamar al modelo; una pregunta de identificación sobre algo ausente ("¿Quién es Zacarías Fernández Pizarro?") cuyo segundo intento tampoco pasa el umbral responde "sin información" sin llamar al modelo; y a lo más una segunda búsqueda por consulta (comprobar con el número de llamadas a `search`); y una consulta rechazada por tope de gasto (429) no hace ninguna búsqueda ni segundo intento

### Implementación de US2

- [X] T013 [US2] En `src/mia/rag/query_rewrite.py`, agregar las guardas del candidato de [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md) ("Guardas del candidato") y la regla de una sola pregunta (signos interiores `¿ ? ¡ !` después de quitar los de los extremos devuelven `None`): al menos 3 caracteres sin contar signos ni espacios de los extremos y distinto de la pregunta normalizada; a lo sumo 8 palabras; no empieza con "lo" ni "que" ni con "necesario/a", "obligatorio/a", "posible", "suficiente", "importante", "mejor", "igual" o "diferente", y no contiene "que", "cuando", "donde", "cuanto", "cuanta", "cuantos", "cuantas" ni "porque" como palabra completa (usando el texto normalizado); sin `¿ ? ¡ !`. Ninguna guarda se salta: si una falla, `clean_question` devuelve `None`. Con esto deben pasar T005, T010 y T011. (Agregada en la implementación, tras listar las preguntas del conjunto de casos: guarda 5 de R4, el candidato no empieza con un participio tras un verbo en pasado, que corrige el caso A2.)

**Checkpoint**: US1 y US2 pasan; las reglas no reformulan nada de la tabla de negativos.

---

## Phase 5: User Story 3 - Poder apagarlo, y saber cuántas veces se usó y si ayudó (Priority: P2)

**Goal**: la opción está apagada por defecto, un valor inválido no rompe nada, y cada consulta con segundo intento deja su nota en Uso, haya o no encontrado fragmentos, sin agregar llamadas al modelo.

**Independent Test**: `pytest tests/unit/test_query_clean_question.py`: con la opción apagada la ruta es idéntica a la de antes; con ella encendida, las notas aparecen en `reject_reason` en `answered` y en `no_info`.

### Tests de US3 (escribir primero; deben fallar)

- [X] T014 [P] [US3] En `tests/unit/test_query_clean_question.py`, pruebas de FR-008 y FR-010: con `QUERY_CLEAN_QUESTION=off` (el valor por defecto de `Settings`) y la primera búsqueda sin resultados, no hay segunda búsqueda ni segundo embedding, y la respuesta, el registro (`QueryLog`: `outcome`, `reject_reason`, `cost_usd`, `sources`) son los de siempre; un valor inválido ("quizás") se comporta como apagado y deja un aviso en el registro una sola vez aunque haya dos consultas; el valor se lee en cada consulta (cambiar `settings.query_clean_question` entre dos llamadas cambia el resultado sin reiniciar)
- [X] T015 [P] [US3] En `tests/unit/test_query_rewrite.py`, pruebas de `clean_note(text: str, found: bool) -> str`: `Pregunta limpia: «texto» (con resultados)` y `(sin resultados)`; un texto de más de 120 caracteres se recorta a 120 antes de armar la nota; la nota tiene el formato exacto de [data-model.md](data-model.md)
- [X] T016 [P] [US3] En `tests/unit/test_query_clean_question.py`, pruebas del registro (`QueryLog` leído de la base de la prueba): consulta con segundo intento que encuentra fragmentos y el modelo responde: `outcome == "answered"` y `reject_reason` contiene la nota `(con resultados)`; segundo intento sin resultados: `outcome == "no_info"` y `reject_reason` contiene `(sin resultados)`; segundo intento con resultados pero el modelo responde "sin información": `no_info` con la nota `(con resultados)`; sin segundo intento: `reject_reason` nulo. Además: con las notas de las features 006 y 007 también presentes (citas con regla de seguridad y un corte reintentado), `reject_reason` los une con "; " en el orden pregunta limpia, corte, citas; y que el modelo se llama a lo sumo una vez más por el reintento de corte de la 007 (nunca por el segundo intento) comprobando `modelo.answer.call_count`

### Implementación de US3

- [X] T017 [US3] En `src/mia/rag/query_rewrite.py`, implementar `clean_note(text: str, found: bool) -> str` con el formato de [data-model.md](data-model.md) (`Pregunta limpia: «<texto recortado a 120 caracteres>» (con resultados)` o `(sin resultados)`)
- [X] T018 [US3] En `src/mia/api/routes/query.py`: (a) guardar la nota del segundo intento en una variable `clean_note` cuando se hizo (con `found = bool(relevant)` tras recalcular), (b) hacer que la función interna `no_info(model=None)` reciba también la nota y la escriba en `log.reject_reason` antes de guardar (hoy no escribe `reject_reason`; sin nota debe dejarlo como estaba), pasándola en las dos salidas `no_info` (la de "sin fragmentos" y la de "el modelo respondió sin información"), y (c) en la salida `answered`, `log.reject_reason = combine_notes(clean_note, cut_note, safety_note)` (en ese orden). Con esto deben pasar T014 a T016

**Checkpoint**: US1 a US3 pasan; con todo apagado la ruta es la de antes.

---

## Phase 6: User Story 4 - Medir cuánto mejora y que no rompe nada (Priority: P2)

**Goal**: la herramienta de la feature 005 mide el efecto con casos de envoltura y negativos, anticipa el resultado sin gasto, cuenta los segundos intentos y compara contra un control; luego se mide en producción con autorización.

**Independent Test**: `pytest tests/unit/test_linea_base.py` pasa; `python scripts/linea_base.py puntajes --etiqueta limpia-previa --env-file .env.produccion` muestra la variante `limpia` para los casos que aplican; y el informe de las corridas de control y con la opción encendida cuenta consultas con segundo intento y cuántas pasaron el umbral.

### Tests de US4 (escribir primero; deben fallar)

- [X] T019 [P] [US4] En `tests/unit/test_linea_base.py`, pruebas de la herramienta: `cargar_casos` acepta la categoría nueva `envoltura` y el campo opcional booleano `sin_pregunta_limpia` (y rechaza un valor que no sea booleano); la variante `limpia` de un caso se calcula con `clean_question` y es `None` (no se mide) cuando no aplica o cuando coincide con `variante_corta`; `correr_respuestas` registra por consulta `pregunta_limpia` (la nota `Pregunta limpia:` está en `reject_reason`) y `pregunta_limpia_ayudo` (la nota termina en `(con resultados)`), ambos `None` si no hay `costo`; `resumen_respuestas` cuenta por modo las consultas con segundo intento y cuántas ayudaron; `comparar` ignora esos dos campos si faltan en una de las corridas (`CAMPOS_OPCIONALES`); un caso con `sin_pregunta_limpia: true` cuya consulta tuvo nota de pregunta limpia se marca como error del caso en el resumen (`negativos_reformulados`)

### Implementación de US4

- [X] T020 [US4] En `scripts/linea_base.py`: agregar `envoltura` a `CATEGORIAS`; validar en `cargar_casos` que `sin_pregunta_limpia`, si existe, sea booleano; definir la constante `NOTA_PREGUNTA_LIMPIA = "Pregunta limpia:"` junto a las demás notas; agregar `pregunta_limpia` y `pregunta_limpia_ayudo` a `CAMPOS_OPCIONALES` y a la lista de campos que compara `comparar`; registrarlos por consulta en `correr_respuestas` (a partir de `costo["reject_reason"]`, como `reintento`); resumirlos en `resumen_respuestas` por modo (`segundos_intentos`, `segundos_intentos_con_resultados`, `negativos_reformulados`); y mostrarlos en `generar_informe` (línea "Segundos intentos: N; con resultados: M; negativos reformulados: K"), conservando la sección manual "## Lectura"
- [X] T021 [US4] En `scripts/linea_base.py`, en el subcomando `puntajes`: después de importar `mia` (como el resto de la herramienta, que carga el entorno antes), para cada caso con `pregunta`, calcular `limpia = clean_question(caso["pregunta"])`; si es un texto distinto de `variante_corta` y distinto de `pregunta`, agregarlo como tercera variante `("limpia", limpia)` junto a `completa` y `corta`, con el mismo `medir_caso` (solo lectura, sin costo). Agregar `limpia` a la impresión por caso y al informe de puntajes, y comprobar que `correr_respuestas` y `consultar` no la usan (la variante `limpia` es solo de `puntajes`; en `respuestas` el API hace su propio segundo intento)
- [X] T022 [US4] Agregar a `scripts/datos/casos_busqueda.json` los casos de envoltura: para cada una de las tres personas de S22-1, S22-3 y S22-4 (mismos `dominios` y `documentos`), una redacción "Háblame de <nombre completo>" y otra "¿Qué se sabe de <nombre completo>?" (ids `EN1` a `EN6`, categoría `envoltura`, `espera: "respuesta"`, nota que remita al caso base); dos casos de término ("¿Qué es el Cibercrimen?" y un segundo término) solo si `python scripts/linea_base.py inventario` y `puntajes` muestran un documento que lo contiene (si no hay, omitirlos y dejarlo anotado en [research.md](research.md) R10); dos casos de ausencia que prueban BUS-3 (`EN7`: "¿Quién es Zacarías Fernández Pizarro?" y `EN8`: "¿Qué es el Departamento de Hidrología Lunar?", `espera: "sin_informacion"`, `dominios` los mismos de las personas y de la batería); y dos negativos `sin_pregunta_limpia: true`: `EN9`, una pregunta que sí empieza con una envoltura pero pide un dato ("¿Qué es necesario para graduarse?", con `espera: "respuesta"` y el documento del reglamento de graduación si el inventario lo muestra, o `sin_informacion` si no), y `EN10`, una pregunta de dato que no empieza con envoltura ("¿Cuánto cuesta la matrícula de la maestría?", `espera: "sin_informacion"` salvo que el inventario muestre documento). Antes de fijarlos, confirmar con `puntajes` (gratis) cuáles fallan la primera búsqueda y que `clean_question` devuelve `None` para los negativos

### Medición en producción (requiere autorización del usuario)

- [X] T023 [US4] Correr la medición gratuita: `python scripts/linea_base.py puntajes --etiqueta limpia-previa --env-file .env.produccion` y escribir en [research.md](research.md) (nueva sección R11) los puntajes y puestos de las variantes `completa`, `corta` y `limpia` de S22-1, S22-3 y S22-4 (cuya `limpia` coincide con su `corta`, así que se mide una sola vez) y de la variante `completa` y la `limpia` de EN1 a EN6 (que no tienen `corta`; su `limpia` coincide con la `corta` de la persona de S22), indicando cuáles pasan el umbral de 0,82 con el límite del modo literal y del modo con razonamiento. Si algún caso no mejora, decir por qué (S22-3 y el puesto 12 de S22-1 son los esperados) y ajustar las expectativas de SC-001 en la sección de resultados, no la spec
- [X] T024 [US4] (Autorizada el 2026-10-18 en versión reducida: 10 casos, tope 0,10 USD de control y 0,20 USD encendida; ver R12.) **Pedir al usuario autorización explícita y tope de gasto** (propuesta: 0,40 USD por corrida, dos corridas, con las listas de casos de T022) antes de cualquier corrida en producción; confirmar el artefacto de prueba que se activa (`PRUEBA Aceptación ambas unidades`) y que se puede encender la API; no avanzar sin la respuesta
- [X] T025 [US4] Con la autorización: corrida de control con `QUERY_CLEAN_QUESTION=off` (etiqueta `control8`), siguiendo [quickstart.md](quickstart.md) §3 (siempre `--skip-deploys` y `encender MIA --forzar --ref origin/dev`; comprobar que el código es el de `dev` con los tokens y `railway deployment list -s MIA --json`), y corrida con `QUERY_CLEAN_QUESTION=on` (etiqueta `limpia`). Comparar con `comparar control8 limpia` y con la línea base (`comparar base limpia`), generar el informe y confirmar, empezando por los casos de SC-001 (S22-1, S22-3 y S22-4 con "¿Quién es...?"): los casos S22 y EN1 a EN6 que pasan de "sin información" a respuesta con el documento esperado; EN7 y EN8 siguen en "sin información"; EN9 y EN10 sin nota de pregunta limpia; los 19 casos de la batería del MVP sin cambio de resultado (repetir un caso que cambie antes de contarlo como regresión); consultas sin segundo intento con costo y latencia dentro del ruido del control, y, para las que sí tuvieron segundo intento, la latencia contra la de esas mismas consultas en `control8` por modo, con una diferencia menor a 1 segundo (SC-006); y que `control8` contra `base` no muestra diferencias atribuibles a la feature (SC-005 y SC-007)
- [X] T026 [US4] Cerrar la producción: dejar `QUERY_CLEAN_QUESTION=off` en Railway (con `--skip-deploys`), apagar la API (`python scripts/servicios.py apagar MIA --forzar`), desactivar el artefacto de prueba, regenerar su clave y guardar la nueva solo en `.env`; anotar el gasto total de la medición. Registrar los resultados en `docs/LINEA_BASE_BUSQUEDA.md` (sección de la 008, con una lectura honesta de qué mejora y qué no) y completar cada SC de la spec con el número medido

**Checkpoint**: las cuatro historias funcionan; el resultado de la medición está documentado y la producción quedó como estaba.

---

## Phase 7: Polish y documentación

**Purpose**: documentación viva y verificación final.

- [X] T027 [P] Actualizar `docs/ARQUITECTURA.md` (el flujo de la consulta con el segundo intento, el módulo `query_rewrite` y la nota de Uso) y `docs/OPERACION.md` (la variable `QUERY_CLEAN_QUESTION`, cómo encenderla y apagarla, cómo leer la nota en Uso y cómo medir su efecto con `scripts/linea_base.py`, incluida la advertencia de Railway sobre `--skip-deploys`)
- [X] T028 [P] Actualizar `docs/Definicion_Requerimientos_V3.md`: marcar la opción B como implementada y medida (BUS-1 y BUS-7, con el resultado de T026 y la decisión de dejar fuera "cuál es", R3) y anotar qué queda sin resolver (siglas, documento más allá del número de resultados)
- [X] T029 Revisar que no queden guiones largos (U+2014) en lo generado: buscar con `grep -rnP "\x{2014}"` en `specs/008-pregunta-limpia`, `src/mia/rag/query_rewrite.py`, `tests/unit/test_query_rewrite.py`, `tests/unit/test_query_clean_question.py`, `scripts` y `docs/LINEA_BASE_BUSQUEDA.md`, sin coincidencias nuevas; correr `pytest` completo y `ruff check src tests scripts`, y marcar el [checklist](checklists/requirements.md) final
- [X] T030 Actualizar la memoria del proyecto (`mia_v3_busqueda_no_directa.md` y el índice `MEMORY.md`) con el estado de la 008 y lo que sigue (reranker, híbrida), y hacer commit y push a `dev`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; bloquea a las historias.
- **US1 (Phase 3)**: depende de Foundational. Es el MVP.
- **US2 (Phase 4)**: depende de US1 (la función `clean_question` y la ruta existen); agrega guardas.
- **US3 (Phase 5)**: depende de US1 (la ruta con el segundo intento); la nota y `no_info` con nota no dependen de US2.
- **US4 (Phase 6)**: las tareas de herramienta (T019 a T022) dependen de US1 y US2; la medición (T023 a T026) depende de que US1 a US3 estén completas.
- **Polish (Phase 7)**: depende de lo anterior.

### Within Each User Story

- Las pruebas van primero y deben fallar antes de implementar.
- `query_rewrite.py` antes de la ruta; la ruta antes de la herramienta.

### Parallel Opportunities

- T001 y T002 en paralelo.
- Las pruebas de una misma historia (T005 a T007, T010 a T012, T014 a T016) en paralelo: archivos distintos o secciones independientes.
- T027 y T028 en paralelo.

## Implementation Strategy

1. Setup y Foundational (T001 a T004).
2. US1 (T005 a T009): ya hay segundo intento detrás de la variable. Detenerse y verificar.
3. US2 (T010 a T013): las guardas, que lo hacen seguro.
4. US3 (T014 a T018): la nota de Uso y el comportamiento apagado.
5. US4 (T019 a T026): la herramienta, la medición gratuita y, con autorización, la medición en producción.
6. Polish (T027 a T030).

Es posible parar tras la fase 5: la opción está implementada, probada y apagada por defecto, y la medición puede esperar.
