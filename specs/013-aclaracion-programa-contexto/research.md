# Research: Aclaración de programa y contexto de conversación

Decisiones de diseño con su razón y las alternativas. El qué y el por qué están en [spec.md](spec.md) y en la sección 10.1 de [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md). Lo que se afirma del código se verificó leyéndolo el 2026-10-27 (`src/mia/api/routes/bot_service.py`, `src/mia/api/routes/query.py`, `src/mia/ingestion/chunker.py`, `whatsapp/src/mia_whatsapp/{flow,state,api_client,config}.py`).

## R1. Quién decide qué: la API detecta la ambigüedad, el servicio guarda el contexto y reintenta

**Decision**: la **API** decide si una pregunta es ambigua entre programas (es quien ve los documentos y los vectores) y devuelve la lista de programas candidatos; el **servicio del bot** guarda el contexto de conversación en memoria, resuelve la respuesta de la persona a la aclaración y hace el reintento con el programa recordado (es quien conoce a la persona y la conversación). La API sigue sin estado de conversación y sin recibir el teléfono (FR-010, feature 011 FR-027).

**Rationale**: separa por lo que cada pieza ya sabe. La API no necesita estado nuevo, y el servicio ya tiene el estado transitorio acotado por persona (`state.py`: mensajes vistos, saludo, límites). Con esto no hay migración ni cambios en el panel (FR-020).

**Alternatives considered**: guardar el contexto en la API (obliga a mandar un identificador de persona a la API o a abrir una tabla: contradice la decisión de privacidad y exige migración); decidir la ambigüedad en el servicio (no ve los vectores ni los documentos).

## R2. Contrato: solo `/bot/query` cambia, con una respuesta propia del bot

**Decision**: `POST /bot/query` devuelve un `BotQueryResponse`, que **extiende** `QueryResponse` con dos listas, `clarify` (programas candidatos; vacía salvo cuando pide aclaración) y `programs` (programas de los documentos citados en una respuesta, para recordar el programa). `POST /query` sigue devolviendo `QueryResponse` sin cambios en su forma (FR-019). El estado de aclaración se señala con `no_info: true` y `clarify` no vacía: un cliente que no conozca el campo nuevo sigue viendo "sin información".

**Rationale**: `QueryResponse` ya se amplió una vez con `images` y los clientes y pruebas existentes lo esperan; agregarle campos arrastraría a la Consulta administrativa y a las pruebas de `/query`. Un modelo derivado solo en `/bot/query` aísla el cambio.

**Alternatives considered**: campos nuevos en `QueryResponse` (cambia la forma de `/query`); una ruta nueva `/bot/clarify` (otra llamada de red por mensaje y duplicaría permisos y topes que `run_query` ya aplica).

## R3. Cómo se calcula "los programas" sin migración: título del documento

**Decision**: el programa de un documento sale de la **primera línea** de su primer fragmento (fragmento 0, `get_chunks(document_id, [0])`), con la forma `<PROGRAMA>: <SECCIÓN>` (decisión del usuario, 2026-10-27). Reglas:
- La etiqueta es el texto antes de los dos puntos de esa línea, de 3 a 120 caracteres. Sin dos puntos o con una línea que no cabe: el documento **no tiene programa** y no cuenta (no rompe nada).
- **Nombre natural**: si la etiqueta está toda en mayúsculas, se pasa a mayúscula inicial por palabra y las palabras de enlace (`en`, `de`, `del`, `la`, `el`, `los`, `las`, `y`, `e`, `con`, `para`, `a`, `por`) quedan en minúscula (salvo la primera): `MAESTRÍA EN ANALÍTICA DE NEGOCIO (BUSINESS ANALYTICS)` da `Maestría en Analítica de Negocio (Business Analytics)`. Si ya trae minúsculas se respeta tal cual.
- **Clave de comparación**: minúsculas, sin tildes, sin signos, sin las palabras vacías (`maestria`, `en`, `de`, `del`, `la`, `el`, `y`, `los`, `las`). Dos documentos son del mismo programa si tienen la misma clave: así `Presentación`, `Admisión` y `Plan de estudio` de un programa cuentan una vez.
- **Caché**: el título de un documento se lee una vez por proceso (un diccionario por `document_id`; el id no se reutiliza, así que un documento eliminado deja una entrada inofensiva) y solo en el camino de "sin información" o al responder con fuentes para recordar el programa. En la práctica es una lectura de Qdrant por documento por reinicio.

**Rationale**: el fragmento 0 empieza donde empieza el documento (`chunk_text` corta desde el índice 0), así que su primera línea es el título; no hay campo nuevo, ni migración, ni cambios en el panel, y la convención ya la cumplen los seis documentos subidos el 27 de octubre.

**Alternatives considered**: un campo `program` por documento (migración, API y panel; es lo más explícito pero la spec lo descartó); el nombre de la unidad del dominio (no distingue maestrías de la misma unidad); el nombre del archivo (`Maestria_en_Ciberseguridad_Admision.txt`: parseable pero frágil y poco legible).

## R4. La búsqueda de decisión: un solo `search` vectorial con umbral bajo, sin embedding nuevo

**Decision**: solo en el camino `if not relevant` de `run_query` (la búsqueda terminó sin nada sobre el umbral) y solo cuando se pidió con una política de aclaración (el bot), se hace **una** búsqueda vectorial adicional con el mismo embedding de la pregunta (ya calculado), con `BOT_CLARIFY_CANDIDATES` (30) fragmentos, y se queda con los resultados con puntaje **mayor o igual a `BOT_CLARIFY_MIN_SIMILARITY`** (un piso amplio) **y con evidencia léxica de la pregunta** (alguna de sus palabras con contenido aparece en el fragmento: la medición de R9 mostró que el puntaje solo no distingue una pregunta ambigua de una sin relación). Se agrupan por programa (R3); si hay **dos o más programas** se responde con aclaración, con hasta `BOT_CLARIFY_MAX_PROGRAMS` (5) programas, ordenados por su mejor puntaje. Con uno o ninguno, "sin información" como hoy. Sin búsqueda híbrida, sin reranker y sin pregunta limpia en esta búsqueda: es solo para decidir. Interruptor `BOT_CLARIFY` (`on` u `off`, `off` por defecto, como las opciones de la V3).

**Rationale**: reutiliza el embedding (cero costo de modelo) y una consulta a Qdrant que ya sabemos que cuesta milisegundos; no cambia lo que hoy se responde (FR-007) porque ocurre después de decidir que no hay respuesta. El valor por defecto del umbral bajo se **calibra con los seis documentos reales** al implementar (tarea de medición, R9) y queda anotado aquí.

**Alternatives considered**: bajar el umbral general (elige un programa al azar: peor que no responder); reutilizar la búsqueda híbrida (más latencia para una decisión); usar el modelo para decidir (opción 2 de la propuesta, fuera de alcance).

## R5. Contexto del servicio: 4 turnos por persona, en memoria, con lo que las reglas necesitan

**Decision**: `ConversationStore` en `state.py`, junto al resto del estado del servicio, con la misma forma que `_greeted`/`_people`: un `OrderedDict` por clave de persona (`message.person_key`, el hash que ya existe) con tope de personas (`BOT_CONTEXT_MAX_PEOPLE`, 5.000) y vencimiento por inactividad (`BOT_CONTEXT_MINUTES`, 30). Cada conversación guarda un `deque(maxlen=BOT_CONTEXT_MESSAGES)` (4) de **turnos**: de la persona el texto de su pregunta (recortado al máximo de la pregunta, 500), y del bot solo lo que las reglas necesitan: tipo (`respuesta`, `aclaracion`, `sin_informacion`), los programas citados y los candidatos de la aclaración; **no** el texto de la respuesta del bot (largo e innecesario). No hay estructura de "memoria" aparte: la aclaración pendiente y el programa recordado se **derivan** de los últimos turnos (último turno del bot con `aclaracion` y la pregunta de la persona que lo precede; último programa de un turno del bot de tipo `respuesta`).

**Rationale**: "últimos 4 mensajes" se cumple literalmente en cuanto a la cantidad (la ventana es de 4 turnos, dos vueltas), y acotar lo que se guarda del bot a datos mínimos reduce memoria y datos en reposo. Con 5.000 conversaciones de hasta 4 turnos cortos la memoria es del orden de pocos MB. Se pierde al reiniciar (aceptado).

**Alternatives considered**: guardar también el texto de las respuestas del bot (ocupa más sin que ninguna regla lo use); campos explícitos `pending`/`program` fuera de la ventana (dos fuentes de verdad); guardar el contexto en la API (R1).

## R6. Resolver la aclaración: coincidencia por palabras con la clave del programa

**Decision**: si el último turno del bot fue una aclaración, el mensaje de la persona se compara con los candidatos: se normaliza (R3: minúsculas, sin tildes ni signos, sin palabras vacías) y se acepta un candidato si **todas** las palabras del mensaje están en las de la clave del candidato (por ejemplo "la de analítica" da `{analitica}`, que está en `{analitica, negocio, business, analytics}`), o si el mensaje es exactamente el **número** de su opción (`1`, `2`: el texto por defecto numera las opciones). Si coincide **exactamente un** candidato se repite la pregunta original con ese programa (R7); si no coincide ninguno, o coinciden dos o más ("ciberseguridad y analítica"), la aclaración se descarta y el mensaje se trata como pregunta nueva (FR-014). Un mensaje sin palabras tras quitar las vacías (por ejemplo, "maestría") no coincide con nada.

**Rationale**: reglas simples, deterministas y sin modelo; cubre "Ciberseguridad", "la de analítica", "Maestría en Analítica de Negocio" y "1".

**Alternatives considered**: distancia de edición (tolera errores de escritura pero acepta falsos positivos y agrega complejidad); pedir un modelo que interprete la respuesta (opción 2).

## R7. Cómo se vuelve a preguntar con un programa: se agrega a la pregunta, sin cambiar la API

**Decision**: la pregunta con programa es `"{pregunta} ({nombre natural del programa})"`, enviada a `POST /bot/query` como una pregunta más. La búsqueda por significado encuentra los fragmentos cuyo encabezado nombra el programa (así se normalizaron los documentos), y la parte léxica (búsqueda híbrida) también. El texto compuesto queda en el registro de Uso como la pregunta de esa consulta (no lleva datos de la persona).

**Rationale**: no hay parámetros nuevos de filtro por programa en la API (lo que exigiría que la API conozca el programa de cada fragmento en la búsqueda), y es la misma forma en que una persona lo escribiría. El resultado se valida en la medición (R9: "¿Cuándo empiezan las lecciones? (Maestría en Ciberseguridad)" debe dar la fecha de ese programa).

**Alternatives considered**: filtrar la búsqueda por los documentos del programa (más preciso pero la API tendría que calcular y cachear el programa de todos los documentos y aceptar un filtro: más piezas); anteponer el programa en vez de agregarlo (equivalente).

## R8. El orden de decisiones del bot (flow.py)

**Decision**: después de validar que el mensaje es una pregunta de texto razonable (pasos 5 y 6 de `_process`) y antes de consultar:
1. Con el contexto de la persona, si el último turno del bot fue una aclaración: intentar resolverla (R6). Si resuelve un candidato, `pregunta a enviar = pregunta original + programa` y se marca `ya_aclarado` (no se vuelve a preguntar). Si no, la aclaración se descarta y sigue la pregunta tal cual.
2. Dentro del mismo lugar de la cola de consultas (una sola entrada a `QueryGate`), consultar a la API con la pregunta a enviar.
3. Si la API responde **respuesta**: entregarla; el programa recordado es el de los documentos citados si es uno solo (o el elegido).
4. Si responde **sin información** o **aclaración** y hay un programa recordado y la pregunta no estaba ya compuesta con un programa: reintentar **una vez** con ese programa (FR-017). Si el reintento da respuesta, entregarla (y recordar ese programa). Si no, seguir como si no hubiera contexto.
5. Si quedó **aclaración** y `ya_aclarado` es falso: responder el texto de aclaración (numerado) y guardar el turno. Si `ya_aclarado` es verdadero (la pregunta ya iba con programa), tratarla como "sin información": nunca dos aclaraciones por pregunta (FR-014).
6. **Sin información**: el texto de siempre.
7. El contexto se actualiza solo después de enviar con éxito (`error_envio` no deja nada a medias): se agregan el turno de la persona y el del bot.

**Rationale**: es la misma secuencia de hoy con dos puntos de extensión; el reintento y la aclaración ocurren solo en el camino de "sin información". Las consultas que hoy se responden hacen exactamente lo mismo que antes (una llamada a la API).

## R9. Calibrar y medir antes de encender

**Decision**: el valor por defecto de `BOT_CLARIFY_MIN_SIMILARITY` se mide con los seis documentos reales ingeridos en un Qdrant local (con el mismo modelo de embeddings): puntajes de las preguntas ambiguas ("¿Cuándo empiezan las lecciones?", "¿Cuánto cuesta?", "¿Cuáles son los requisitos?"), de preguntas con un solo programa y de preguntas sin relación ("¿Cuánto cuesta la luna?"). El valor se elige para que las ambiguas den dos programas y las sin relación no den ninguno, y se anota aquí con los puntajes. Casos nuevos en `scripts/datos/casos_busqueda.json` (categoría `aclaracion`) y un script de prueba de punta a punta con el servicio y la API reales en un proceso (el patrón de `test_bot_end_to_end.py`).

**Rationale**: el umbral correcto depende del modelo y de los documentos; no se adivina. Con él se decide el valor por defecto antes de encender `BOT_CLARIFY` en producción.

### Resultado de la medición (2026-10-27) y cambio de diseño pendiente

Medido con los seis documentos de `tmp/nuevos/` (31 + 20 fragmentos) en un Qdrant local y el modelo `multilingual-e5-small` de producción (puntajes de la búsqueda vectorial, 8 mejores resultados):

| Pregunta | Mejor puntaje | Programas entre los 8 mejores |
|---|---|---|
| "¿Cuándo empiezan las lecciones?" (ambigua) | 0,816 | Analítica y Ciberseguridad (0,809 a 0,816) |
| "¿Cuánto cuesta?" / "¿Cuáles son los requisitos?" / "¿Cómo me postulo?" (ambiguas) | 0,83 a 0,87 | los dos, pero ya pasan el umbral de 0,82 (las responde el modelo, no entran al camino de aclaración) |
| "¿Cuánto cuesta la luna?" (sin relación) | 0,803 | Ciberseguridad y Analítica (0,791 a 0,803) |
| "¿Qué hora es?" (sin relación) | 0,838 | pasa el umbral (lo responde el modelo) |
| "¿Cómo se prepara un pastel de chocolate?" | 0,790 | |
| "¿Quién ganó el mundial?" | 0,749 | |

**Hallazgo: el puntaje de similitud solo no distingue una pregunta ambigua de una sin relación.** Este modelo comprime los puntajes entre 0,79 y 0,87 para casi cualquier pregunta: "¿Cuándo empiezan las lecciones?" (ambigua, 0,816) y "¿Cuánto cuesta la luna?" (sin relación, 0,803) quedan a 0,013 y con los dos programas en ambos casos. Con la regla actual ("dos o más programas sobre `BOT_CLARIFY_MIN_SIMILARITY`") no hay un valor del umbral que separe los dos casos con margen: con 0,55 (el valor de partida) la pregunta de la luna también pediría aclaración, lo que contradice SC-003.

**Cambio de diseño implementado (2026-11-03):** además del puntaje, un programa solo cuenta como candidato si **el fragmento tiene evidencia léxica de la pregunta**, es decir, si alguna palabra con contenido de la pregunta aparece en su texto (`content_words` y `has_evidence` en `src/mia/rag/programs.py`).
- Palabras con contenido: la pregunta en minúsculas y sin tildes, de al menos 4 letras, sin repetir y sin interrogativos, palabras vacías ni palabras genéricas (`maestria`, `programa`, `posgrado`...).
- Coincidencia: inicio de palabra con los primeros 6 caracteres de la palabra (`lecciones` coincide con "Inicio de lecciones"; `postulo` con "postularse" y "postulación"; `luna` no coincide con nada ni con "columna").
- La búsqueda de decisión pide más candidatos (`BOT_CLARIFY_CANDIDATES`, 30, rango 5 a 100) para que entren los fragmentos de admisión de cada programa, y `BOT_CLARIFY_MIN_SIMILARITY` baja a un piso amplio (**0,70**), porque ya no es lo que discrimina.
- Sin palabras con contenido no hay aclaración (no se puede saber).

**Medición con la regla (mismos seis documentos y modelo; solo cuentan las preguntas que no pasan el umbral de 0,82, que son las que llegan a la búsqueda de decisión):**

| Pregunta | Mejor puntaje | Palabras con contenido | Programas candidatos | Resultado |
|---|---|---|---|---|
| "¿Cuándo empiezan las lecciones?" (ambigua) | 0,816 | empiezan, lecciones | Ciberseguridad y Analítica | **aclaración** |
| "¿Cuánto cuesta la luna?" (sin relación) | 0,803 | cuesta, luna | ninguno | sin información |
| "¿Cómo se prepara un pastel de chocolate?" | 0,790 | prepara, pastel, chocolate | uno (Analítica) | sin información |
| "¿Quién ganó el mundial?" | 0,749 | gano, mundial | ninguno | sin información |
| "¿Cuándo empiezan las vacaciones de verano?" | 0,805 | empiezan, vacaciones, verano | ninguno | sin información |
| "¿Cuánto cuesta la entrada al cine?" | 0,813 | cuesta, entrada, cine | ninguno | sin información |

Las demás preguntas ambiguas medidas ("¿Cómo me postulo?", "¿Cuáles son las fechas de admisión?", "¿Cuál es la fecha de matrícula?", "¿Qué documentos necesito para aplicar?", "¿Cuándo inician las clases?", "¿Cuánto dura?") tienen un mejor puntaje de 0,835 a 0,874: **ya pasan el umbral de 0,82** y las responde el modelo con los fragmentos que recuperó, sin entrar a la aclaración (la aclaración es solo para lo que hoy termina en "sin información" sin pasar por el modelo, FR-001). Con la regla, todas darían los dos programas si llegaran a la búsqueda de decisión, así que la regla no deja afuera ninguna ambigua. Limitación conocida: "¿Cuánto cuesta?" no tiene coincidencia léxica con los documentos ("Inversión", "costo"), y tampoco entra a la aclaración.

**El reintento con el programa (R7)**: "¿Cuándo empiezan las lecciones? (Maestría en Ciberseguridad)" recupera como mejor fragmento el de la admisión de Ciberseguridad con el dato ("Inicio de lecciones: I Trimestre de 2027", puntaje 0,897); con "(Maestría en Analítica de Negocio (Business Analytics))" el fragmento de admisión con "5 de octubre" queda entre los tres primeros (0,894); "¿Y cuánto cuesta? (Maestría en Analítica de Negocio (Business Analytics))" recupera el fragmento de la presentación con ₡61 000. Todos con puntajes de 0,88 a 0,90, sobre el umbral.

## R10. Lo que no cambia, privacidad y cuota

**Decision**: `POST /query` y la Consulta administrativa no cambian de forma ni de comportamiento; el registro de Uso no gana un resultado nuevo (una aclaración queda como `no_info`, FR-021); el resultado `aclaracion` va al registro del servicio (que ya tiene `resultado` por mensaje, sin datos de la persona). Cada aclaración es un mensaje enviado más: una pregunta con aclaración suma 4 mensajes a la cuota (pregunta, aclaración, respuesta de la persona, respuesta final), ya contados por el flujo actual de `count_messages`. El contexto no se registra: ni el texto ni el teléfono salen a los registros (se extiende la prueba que ya existe de "ningún dato de la persona en los registros").

## R11. Riesgos abiertos

| Riesgo | Qué se hace |
|---|---|
| El umbral bajo pregunta de más ante una pregunta sin sentido | Se exigen **dos programas** sobre el umbral bajo (no uno), y se mide con "¿Cuánto cuesta la luna?" (R9). |
| La persona no responde la aclaración y escribe otra cosa | Se descarta la aclaración y el mensaje es una pregunta nueva (FR-014). |
| El programa recordado no es el que la persona quiere | Solo interviene cuando no habría respuesta; nombrar otro programa lo cambia; y si el reintento no responde, se hace lo de siempre. |
| El título de un documento nuevo no sigue la convención | El documento no cuenta como programa; se documenta la convención en la guía de normalización (FR-024). |
| Memoria del contexto | Tope de conversaciones, vencimiento y recorte de textos; se pierde al reiniciar (aceptado). |
| Doble costo por el reintento | Solo en el camino de "sin información" con programa recordado; sin llamadas extra a modelos si no hay fragmentos relevantes (el reintento es una consulta normal). |
