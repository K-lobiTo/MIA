# Research: Memoria de conversación configurable por artefacto

Decisiones de diseño con su razón y las alternativas. El qué y el por qué están en [spec.md](spec.md); aquí se decide el cómo. Lo que se afirma del código se verificó leyéndolo el 2026-11-03 (`src/mia/api/routes/{query,artifacts,config,bots,bot_service}.py`, `src/mia/rag/{llm,modes}.py`, los proveedores de `src/mia/rag/providers/`, `web/consulta/src/`, `web/admin/src/modules/{artefactos,bots}/`, `whatsapp/src/mia_whatsapp/{state,flow,api_client}.py`).

## R1. El historial lo envía el cliente y la API lo recorta (sin sesiones)

**Decision**: `POST /query` acepta un campo opcional `history`, una lista de vueltas `{question, answer, mode?}`. La API solo lo usa si `artifacts.context_turns > 0`, lo **recorta a las últimas N vueltas** del artefacto, lo valida y lo deja fuera si no pasa las reglas de R3. No se guarda en ninguna parte: ni sesión, ni base, ni el registro de Uso (que sigue guardando solo la pregunta actual, `QueryLog.question`).

**Rationale**: la Consulta ya tiene la conversación en la memoria de la página (`state/conversation.ts`, una lista de `Exchange` con su modo y su respuesta), así que no hace falta que el servidor la recuerde. Sin estado en el servidor no hay datos personales en reposo, no hay sesiones que expirar ni que escalar, y la regla de privacidad de la Consulta (la conversación no se guarda) se mantiene intacta. Es el mismo criterio de la 013: lo que sabe la conversación vive en el cliente de la conversación.

**Alternatives considered**: una sesión en el servidor con un identificador de conversación (estado en la API, expiración, y datos personales en reposo; contradice la decisión de privacidad); guardar el historial en la base por artefacto (peor aún); que cada cliente decida cuánto enviar sin que la API lo recorte (cualquier cliente podría enviar 50 vueltas y subir el costo sin control del administrador).

## R2. El historial va en un bloque etiquetado dentro del mensaje del usuario, no como mensajes de chat

**Decision**: el historial no se entrega como mensajes `user`/`assistant` previos del chat, sino como un **bloque de texto etiquetado** dentro del mensaje de usuario que ya existe, antes de la pregunta:

```text
Conversación anterior (solo para entender la pregunta; no es una fuente de datos):
Pregunta: ...
Respuesta: ...
(respuesta del modo con razonamiento: puede incluir cálculos o inferencias que no dicen los documentos)

Contexto:
[Fuente 1: ...]

Pregunta: ...
```

Una función compartida `build_user_message(question, context_block, history)` en `src/mia/rag/llm.py` la arma para los cuatro proveedores implementados (OpenRouter, Gemini, GLM y Anthropic; `openai` y `local` son esqueletos que lanzan `NotImplementedError`). Al `answer()` de la interfaz se le agrega el parámetro opcional `history: list[HistoryTurn] | None = None`. La instrucción de sistema del modo recibe, cuando hay historial, un párrafo más (`HISTORY_INSTRUCTIONS`, como `CITATION_INSTRUCTIONS`): el historial solo sirve para entender a qué se refiere la pregunta actual, nunca es fuente de datos, y toda respuesta sale únicamente de los fragmentos del contexto.

**Rationale**:
- **Un solo formato para todos los proveedores.** Cada API de chat maneja los turnos de forma distinta (Gemini usa `interactions.create(input=...)`, Anthropic exige alternar roles, GLM y OpenRouter usan el formato de OpenAI). Un bloque de texto funciona igual en todos y no cambia la forma de las llamadas.
- **Protege el estilo de cada modo (US3/AC3).** Con mensajes `assistant` reales, el modelo tiende a imitar el formato de lo que "dijo" antes; una respuesta larga con "Lo que dicen los documentos / Conclusión" empuja a un modelo literal a copiar ese formato. En un bloque etiquetado el estilo lo sigue dando la instrucción de sistema del modo.
- **Hace estructural la regla "el historial no es fuente".** El bloque está explícitamente separado del `Contexto` (las fuentes) y rotulado; las respuestas de razonamiento llevan la advertencia de que pueden incluir cálculos.

**Alternatives considered**: mensajes de chat reales (más natural para el modelo, pero imitan el formato, difieren entre proveedores y mezclan el historial con el lugar donde viven las instrucciones); resumir el historial con el modelo (otra llamada en cada consulta); entregar solo las preguntas anteriores sin las respuestas (más barato y sin contaminación, pero no resuelve "¿y el segundo?", que necesita la respuesta para saber cuál es el segundo).

## R3. Validación y recorte del historial (en la API, sin confiar en el cliente)

**Decision**: `sanitize_history(history, turns, mode)` en `src/mia/rag/history.py`:
1. **Forma**: cada vuelta es `{question, answer, mode?}` con `extra="forbid"`: un campo `role` o cualquier otro se rechaza con 422, así que **un mensaje de sistema no puede entrar nunca** (no hay roles que enviar). Máximo 50 vueltas en la entrada (más es 422); `question` y `answer` son texto no vacío; `mode`, si viene, es `literal` o `razonamiento`.
2. **Exclusiones**: se descartan las vueltas cuya respuesta es "sin información" (`is_no_info_answer` o el texto `NO_INFO_ANSWER` de la API, y las que empiezan con "No encontré información suficiente") y las que no tienen pregunta o respuesta (un intercambio fallido no tiene respuesta). La Consulta ya no las envía, pero la API no lo supone.
3. **Recorte por cantidad**: las últimas `turns` vueltas (`turns` = `artifacts.context_turns`, 0 a 10).
4. **Recorte por tamaño**, por modo, con valores configurables: cada pregunta se recorta a `HISTORY_MAX_QUESTION_CHARS` (500), cada respuesta a `HISTORY_MAX_ANSWER_CHARS` (1.500 en literal, 3.000 en razonamiento) y el total del historial a `HISTORY_MAX_CHARS` (6.000 en literal, 12.000 en razonamiento): si el total se pasa se descartan las vueltas más viejas hasta que cabe. Las respuestas se entregan como texto plano (sin imágenes; el campo `answer` es el texto de la respuesta).
5. Con `turns == 0` la función devuelve una lista vacía sin mirar el historial (FR-006).

**Rationale**: la API es el único lugar donde se puede hacer cumplir el límite que decidió quien administra, y el recorte por tamaño acota el costo y evita exceder el contexto de cada modelo. Los valores de partida son los supuestos de la spec y se calibran con la medición de costo (R9).

**Alternatives considered**: confiar en el recorte del cliente (un cliente distinto de la Consulta puede enviar cualquier cosa); rechazar con 422 los historiales demasiado largos (más fricción: recortar silenciosamente es lo esperado de una "memoria"); aceptar un `role` y descartar los de sistema (más superficie que validar que no tener campo de rol).

## R4. Reformular la búsqueda con el historial: dos estrategias seleccionables

**Decision**: con historial vigente, `run_query` calcula una **pregunta de búsqueda** (`search_question`) y la usa para el embedding, la búsqueda híbrida, el reranker y la pregunta limpia; el modelo sigue recibiendo la **pregunta original** más el historial (R2), y el registro de Uso sigue guardando la original. Un módulo `src/mia/rag/followup.py` decide:
- **Cuándo reformular (`is_followup`)**: hay historial **y** la pregunta continúa o se refiere a lo anterior, o es tan corta que no trae tema propio: tiene **tres palabras o menos en total y dos o menos con contenido** (reutiliza `content_words` de la 013), o empieza con "y"/"pero"/"entonces"/"también"/"además", o contiene una referencia ("eso", "esto", "esa", "ese", "ello", "anterior", "mismo", "misma", "primero", "segundo", "tercero", "último", "ahí"...). Una pregunta que se entiende sola no se toca (FR-015). La heurística de palabras puede equivocarse con una pregunta corta que sí se entiende sola ("¿Cuándo es la matrícula?" tiene tres palabras y una con contenido): por eso hay casos de `cambio_de_tema` en R9, y si la medición muestra falsos seguimientos se agrega como condición adicional que la búsqueda con la pregunta original no deje ningún fragmento sobre el umbral.
- **Estrategia `rules`** (sin modelo): `search_question` = las últimas dos preguntas anteriores + la actual, en ese orden, hasta 400 caracteres.
- **Estrategia `model`**: una llamada corta al modelo del **modo literal** (el más barato) con una instrucción de reescritura ("reescribe la última pregunta como una pregunta completa y autónoma usando la conversación; responde solo con la pregunta"), `max_tokens` bajo y sin razonamiento. La salida se valida (una línea, de 5 a 300 caracteres, no vacía); si no pasa, o si el proveedor falla, o si no implementa la reescritura, se cae a `rules` (FR-016). El costo y los tokens de esa llamada se suman al costo de la consulta.
- **Estrategia `off`**: no se reformula.
La variable `HISTORY_REFORMULATION` (`rules` por defecto, `model` u `off`) elige la estrategia, se lee en cada consulta (rige sin reiniciar). La reescritura es un método **no abstracto** `LLMProvider.rewrite(question, history)` (lanza `NotImplementedError`), implementado en OpenRouter (el de producción); los demás proveedores caen a `rules`.

**Rationale**: la spec pide implementar las dos y compararlas con casos reales (FR-014, FR-017). Reglas primero es lo que no cuesta nada extra; el modelo es más preciso pero suma una llamada y latencia. La puerta `is_followup` evita pagar la reescritura en las preguntas que se entienden solas.

**Alternatives considered**: reformular siempre que haya historial (una llamada por consulta aunque no haga falta); usar el modelo del modo en curso para reescribir (en razonamiento sería caro y lento para una tarea trivial); concatenar también la respuesta anterior en las reglas (diluye el embedding; se mide como variante en R9 pero no es la predeterminada).

## R5. Dónde se guarda el parámetro y cómo se edita

**Decision**: `artifacts.context_turns INTEGER NOT NULL DEFAULT 0` y `bots.context_turns INTEGER NULL` (migración aditiva `0008_memoria_de_conversacion`, con `downgrade` que quita las dos columnas; nulo en el bot significa "el valor por defecto de 2 vueltas"). Rango de la columna del artefacto: 0 a 10 (validado en la API con `Field(ge=0, le=10)`); del bot: 1 a 10 o nulo.
- **Artefactos**: `ArtifactCreate`/`ArtifactUpdate` aceptan `context_turns`; `ArtifactOut` lo devuelve; el formulario del panel (`ArtifactForm.tsx`) agrega el campo con su explicación del costo y la tarjeta (`ArtifactCard.tsx`) lo muestra. El cambio deja la línea `artifact.context_turns` en `mia.admin` con el valor anterior y el nuevo.
- **Clientes**: `GET /config` con la clave de un artefacto agrega `context_turns` a `artifact` (hoy `name` y `active`); la Consulta lo lee con `useConfig` (ya refresca al volver a la pestaña).
- **Bots**: `BotCreate`/`BotUpdate`/`BotOut` ganan `context_turns` (con el valor efectivo y el predeterminado); el formulario del módulo Bots agrega el campo (solo alcance global, como el resto del módulo).

**Rationale**: igual que los topes y los modos del artefacto y que el artefacto asignado del bot, el parámetro vive junto a lo que ya se administra desde el panel; no requiere una pantalla nueva ni un permiso nuevo.

**Alternatives considered**: el bot hereda la memoria del artefacto que tiene asignado (con el valor por defecto de 0 apagaría el contexto del bot y rompería la aclaración de la 013); una variable de entorno del servicio (obliga a tocar Railway y a reiniciar, justo lo que se quiere evitar).

## R6. La memoria del bot: el servicio la lee en cada mensaje

**Decision**: `POST /bot/messages` (que el servicio ya llama al recibir cada mensaje) agrega a su respuesta `context_turns`: las vueltas efectivas del bot (el valor del bot o 2). `CountResult` del servicio lo guarda y `flow.py` lo pasa al contexto de conversación como `limit = 2 * context_turns` turnos. El `ConversationStore` deja de fijar el tamaño de la ventana al crear la conversación: guarda hasta `MAX_CONTEXT_TURNS` (20) turnos y cada lectura (`turns`, `pending`, `remembered_program`) recibe el límite vigente, así un cambio desde el panel rige desde el mensaje siguiente y también para conversaciones en curso. Si la API no informa el valor (versión anterior o error al contar), el servicio usa `BOT_CONTEXT_MESSAGES` (4 turnos, el respaldo actual).

**Rationale**: no agrega llamadas (el servicio ya pregunta el estado del bot en cada mensaje), el cambio rige de inmediato, y la memoria sigue en el servicio, en memoria, sin historial al modelo (FR-021). El mínimo de 1 vuelta (2 turnos) es lo que necesita una aclaración pendiente.

**Alternatives considered**: que el servicio consulte la configuración con su propia ruta o con un caché de varios minutos (más piezas y el cambio no rige al instante); pasar el valor como variable en cada llamada a `/bot/query` (la consulta no es donde se conoce el estado).

## R7. Qué cambia en la Consulta administrativa

**Decision**: `web/consulta/src/api/consulta.ts` envía `history` en `useAsk`, armado por una función pura de `state/` (`buildHistory(exchanges, turns)`): las últimas `turns` vueltas **respondidas** (`status === "answered"`, con `response.answer`), sin las fallidas ni las "sin información", cada una con su modo. `turns` sale de `config.artifact.context_turns`; con 0 no se envía nada. La interfaz muestra un aviso sencillo ("Recuerda las últimas N preguntas de esta conversación") cuando N > 0 y no cambia nada cuando es 0. Al cambiar de modo en el selector no se borra nada: el historial es el mismo.

**Rationale**: es lo mínimo y mantiene la regla de que la conversación solo vive en la página.

## R8. Costo y topes

**Decision**: no hay lógica nueva de topes. `check_caps` ya corre antes de consultar; el costo del modelo se registra como hoy (`log.cost_usd` con el costo real del proveedor), que **ya incluye** el texto adicional del historial porque va dentro del mensaje. La reformulación con el modelo suma su costo (y tokens) al registro de la consulta (`log.cost_usd += costo_de_reescritura`) en todos los caminos de salida (incluido "sin información"). Con `rules` y `off` no hay costo extra.

**Rationale**: reutiliza lo que ya funciona (cálculo del costo real en OpenRouter, tope del día y del modo); un artefacto que alcanzó su tope no consulta aunque traiga historial, porque el chequeo es previo.

## R9. Medición con casos reales

**Decision**: casos nuevos en `scripts/datos/casos_memoria.json`: conversaciones de 2 a 3 vueltas con una pregunta final de seguimiento y el documento esperado (sobre los seis documentos de los posgrados), con las categorías `tema_anterior`, `pronombre`, `cambio_de_modo`, `cambio_de_tema` (una pregunta corta que se entiende sola frente a un historial de otro tema: mide los falsos seguimientos) y `calculo_en_razonamiento` (esta última verifica que la pregunta literal no repita el valor calculado como dato documental). `scripts/medir_memoria.py` ingiere los documentos en un Qdrant local temporal (como `calibrar_aclaracion.py`) y para cada caso mide si el documento esperado aparece entre los fragmentos recuperados con cada estrategia (`off`, `rules`, `model`), y reporta aciertos, costo y tiempo por estrategia. La estrategia `model` y los casos de respuesta con el modelo llaman a OpenRouter y **cuestan unos centavos**: se corren solo con la autorización del usuario. Las pruebas automáticas usan proveedores simulados.

**Resultados (2026-11-04, `python scripts/medir_memoria.py --documentos tmp/nuevos --respuestas --costo --costo-real`, embeddings locales, Qdrant local y el modelo literal real por OpenRouter; 13 casos de búsqueda):**

| Estrategia | Aciertos | tema_anterior | pronombre | cambio_de_modo | cambio_de_tema | Falsos seguimientos | Costo extra por consulta | Tiempo extra |
|---|---|---|---|---|---|---|---|---|
| `off` | 8 de 13 | 2 de 4 | 0 de 3 | 3 de 3 | 3 de 3 | ninguno | 0 | 0 |
| `rules` | 13 de 13 | 4 de 4 | 3 de 3 | 3 de 3 | 3 de 3 | ninguno | 0 | 0,02 s |
| `model` | 12 de 13 | 3 de 4 | 3 de 3 | 3 de 3 | 3 de 3 | ninguno | 0,000015 USD | 0,82 s |

- **Elección: `rules` queda como estrategia predeterminada** (cumple SC-001 con 13 de 13, sin costo ni latencia, y `is_followup` reconoció todos los seguimientos). `model` acertó 12 de 13 y en 2 casos su reescritura no fue válida y cayó a las reglas; cuesta unos 0,000015 USD y 0,8 s por seguimiento. Sigue disponible por `HISTORY_REFORMULATION=model`.
- **Costo de la memoria** (10 consultas de seguimiento con el modelo literal, sin reformular): memoria 0 = 0,000175 USD por consulta; memoria 4 = 0,000235 USD (unos 254 caracteres, 73 tokens estimados, de más): +34 % por consulta, unos 0,00006 USD.
- **Contaminación entre modos (SC-002):** los casos `calculo_en_razonamiento` ponen en el historial una cifra calculada que **no** sale de los documentos (35 y 19; las sumas reales son 21 y 16) y piden lo mismo en modo literal. El modelo real no repitió la cifra del historial en ninguno: respondió 21 y 16 con los bloques del plan. (Una primera versión de estos casos usaba la suma correcta en el historial y daba falsos "MAL", porque el modelo volvía a obtener ese valor de los documentos; se rediseñaron.)

**Corrección del 2026-11-05 (la estrategia por defecto pasa a `model`):** una prueba en producción mostró que `rules` falla con el corpus real: tras "¿Cuáles son los contenidos de Desarrollo de Experimentos?", la pregunta "¿Y cuántos créditos tiene?" respondía "sin información" con todos los dominios seleccionados (con solo *Currículum* respondía bien), porque la búsqueda con las dos preguntas pegadas traía documentos de contenidos y de reforma curricular y no la ficha del curso. La medición anterior no lo vio porque solo usaba seis documentos. Además, la fila de `model` de la tabla de arriba (12 de 13) estaba **sesgada por un fallo mío**: el modelo del modo literal en producción (`z-ai/glm-5.3-flash`) razona obligatoriamente y gastaba los 100 tokens de `HISTORY_REWRITE_MAX_TOKENS` pensando, así que devolvía texto vacío (`finish_reason: length`) y la estrategia caía en silencio a las reglas (los dos avisos "no válida" de la corrida). Con el límite en 400 `model` acierta **13 de 13** (cambio_de_modo 3/3, cambio_de_tema 3/3, pronombre 3/3, tema_anterior 4/4, sin falsos seguimientos) a unos 0,000025 USD y 0,6 s por seguimiento (en el caso real, 0,000013 a 0,0001 USD y de 0,5 a 2 s), y reescribe el caso de producción como "¿Cuántos créditos tiene el curso MC-6104 Diseño de Experimentos?", que sí encuentra la ficha. Se cambió el valor por defecto a `model` y el límite a 400; `rules` queda como respaldo cuando la reescritura falla.

**Rationale**: la spec exige elegir la estrategia por defecto con números (SC-008) y verificar los casos de contaminación entre modos (SC-002), y eso depende del modelo real; no se adivina.

## R10. Lo que no cambia, privacidad y riesgos

**Decision**: con `context_turns = 0` el camino de `run_query` es exactamente el de antes (sin `sanitize_history`, sin `search_question` distinta, sin instrucción extra); `POST /bot/query` construye su `QueryRequest` sin historial; el registro de Uso no gana columnas; ningún dato nuevo en reposo salvo las dos columnas numéricas.

| Riesgo | Qué se hace |
|---|---|
| Un modelo literal repite como dato documental un cálculo del modo con razonamiento | Bloque etiquetado y rotulado, advertencia en las respuestas de razonamiento, instrucción de sistema explícita; se mide con los casos `calculo_en_razonamiento` (R9). |
| La reformulación pregunta de más o cambia el tema | Solo se aplica a seguimientos (`is_followup`); la reescritura del modelo se valida y, si falla, se cae a reglas; se mide. |
| El historial sube el costo | Recortes por modo, topes diarios intactos, costo medido con memoria 0 y 4 y documentado. |
| Un cliente envía un historial malicioso (rol de sistema, textos enormes, cientos de vueltas) | `extra="forbid"`, máximos de entrada, recorte por cantidad y por tamaño en la API (R3). |
| La Consulta envía un historial viejo tras recargar | La conversación vive en la página: al recargar empieza de cero (como hoy). |
| El valor de memoria del bot no llega al servicio | Respaldo: `BOT_CONTEXT_MESSAGES` (R6). |

**Batería de aceptación del MVP con la memoria en 0 (2026-11-04):** `python scripts/pruebas_mvp.py` contra la API en producción ya desplegada con la feature 014 y el artefacto de prueba "PRUEBA Aceptación ambas unidades" (acceso a las dos unidades, memoria 0, activado solo durante la corrida): **19 de 19 casos correctos** (FR-019, SC-004).
