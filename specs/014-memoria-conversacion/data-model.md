# Data Model: Memoria de conversación configurable por artefacto

Lo único que se guarda de esta feature son **dos números**: uno en el artefacto y uno en el bot (migración aditiva `0008`). El historial no se guarda en ninguna parte. Decisiones en [research.md](research.md).

## En la base (migración `0008_memoria_de_conversacion`)

| Tabla | Columna | Tipo | Valor | Para qué |
|---|---|---|---|---|
| `artifacts` | `context_turns` | `INTEGER NOT NULL DEFAULT 0` | 0 a 10 (se valida en la API) | Vueltas completas (pregunta y respuesta) que el artefacto recuerda y entrega al modelo. 0 es el comportamiento de siempre. |
| `bots` | `context_turns` | `INTEGER NULL` | nulo, o 1 a 10 (se valida en la API) | Vueltas que recuerda el bot para la aclaración de programa y el programa recordado. Nulo: el valor por defecto, 2 vueltas (4 turnos). |

`downgrade` quita las dos columnas (con `batch_alter_table`, como las demás migraciones, por SQLite). Los artefactos y bots existentes quedan en 0 y nulo: nada cambia hasta que alguien lo edite. La cabeza de migraciones pasa de `0007` a `0008` (se actualizan `tests/unit/test_migrations.py` y los procedimientos que mencionan la `0007`).

## En la API (sin base de datos)

### Vuelta del historial (`HistoryTurnIn`, solo en la entrada de `POST /query`)

| Campo | Tipo | Regla |
|---|---|---|
| `question` | texto | No vacío, hasta 2.000 caracteres. |
| `answer` | texto | No vacío, hasta 20.000 caracteres. |
| `mode` | `literal` o `razonamiento`, opcional | El modo en que se respondió esa vuelta; solo informativo para el modelo. |

El modelo usa `extra="forbid"`: cualquier otro campo (por ejemplo `role`) es un 422. `QueryRequest.history` es `list[HistoryTurnIn]`, con valor por defecto vacío y **máximo 50 vueltas** (más es 422).

### Historial vigente (`HistoryTurn`, interno)

Lo que queda tras `sanitize_history(history, turns, mode)`:

| Regla | Detalle |
|---|---|
| Solo con memoria | Con `turns == 0` el resultado es vacío sin mirar la entrada. |
| Exclusiones | Se descartan las vueltas cuya respuesta es "sin información" (`is_no_info_answer`, el texto `NO_INFO_ANSWER` o el que empieza con "No encontré información suficiente"). |
| Cantidad | Las últimas `turns` vueltas. |
| Tamaño por vuelta | Pregunta hasta `HISTORY_MAX_QUESTION_CHARS` (500); respuesta hasta `HISTORY_MAX_ANSWER_CHARS` (1.500 en literal, 3.000 en razonamiento). |
| Tamaño total | Hasta `HISTORY_MAX_CHARS` (6.000 en literal, 12.000 en razonamiento): si se pasa se descartan las vueltas más viejas. |

### Pregunta de búsqueda (calculada, no almacenada)

`search_question`: la pregunta con la que se calcula el embedding, la búsqueda híbrida, el reranker y la pregunta limpia. Sin historial o sin seguimiento es la pregunta original; con un seguimiento es la reformulación (R4). El modelo recibe siempre la original y el registro de Uso guarda siempre la original.

### Configuración de la API

| Variable | Defecto | Rango | Para qué |
|---|---|---|---|
| `HISTORY_REFORMULATION` | `rules` | `rules`, `model` u `off` (inválido: `rules` y avisa una vez) | Estrategia para reformular la búsqueda de un seguimiento. Se lee en cada consulta. |
| `HISTORY_MAX_QUESTION_CHARS` | `500` | 50 a 2000 | Tope de cada pregunta del historial. |
| `HISTORY_MAX_ANSWER_CHARS` | `1500` | 200 a 20000 | Tope de cada respuesta del historial en modo literal (el doble en razonamiento). |
| `HISTORY_MAX_CHARS` | `6000` | 500 a 100000 | Tope del total del historial en modo literal (el doble en razonamiento). |
| `HISTORY_REWRITE_MAX_TOKENS` | `100` | 20 a 500 | Tokens de salida de la reescritura con el modelo. |

## En el servicio del bot (memoria, sin base)

El `ConversationStore` (feature 013) cambia en dos cosas: guarda hasta `MAX_CONTEXT_TURNS` (20) turnos por persona, y cada lectura (`turns`, `pending`, `remembered_program`) recibe el límite vigente (`2 * context_turns` del bot). `BOT_CONTEXT_MESSAGES` (4) queda como respaldo cuando la API no informa el valor. El resto (vencimiento, tope de conversaciones, qué guarda cada turno) no cambia.

| Dato | Detalle |
|---|---|
| `CountResult.context_turns` | `int` opcional que lee de la respuesta de `/bot/messages`; vacío si la API no lo informa. |
| Límite vigente | `2 * context_turns` turnos si la API lo informa, si no `BOT_CONTEXT_MESSAGES`. |
