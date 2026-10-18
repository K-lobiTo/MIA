# Data Model: Respuestas completas, sin cortes

No hay tablas ni migraciones. Son estructuras en memoria de la API, variables de configuración y un uso de campos existentes del registro.

## Variables de configuración (`src/mia/config.py`)

| Variable | Tipo | Defecto | Descripción |
|---|---|---|---|
| `QUERY_COMPLETE_CONTEXT` | texto (`on`/`off`) | `off` | Enciende el contexto completo de los documentos principales y la instrucción de completitud. Valor inválido: se trata como apagado con un aviso. |
| `QUERY_COMPLETE_DOCUMENTS` | entero, de 1 a 8 | 1 | Cuántos documentos principales (por orden de mejor resultado) reciben el trato ampliado. |
| `QUERY_COMPLETE_DOCUMENT_MAX_CHUNKS` | entero, de 1 a 100 | 25 | Un documento principal de hasta estos fragmentos se entrega completo. |
| `QUERY_COMPLETE_FORWARD_NEIGHBORS` | entero, de 0 a 20 | 4 | Fragmentos posteriores que se suman a cada resultado de un documento principal más largo que el límite anterior. |
| `QUERY_CONTEXT_MAX_CHARS` | entero, de 5.000 a 400.000 | 80.000 | Tope de caracteres del contexto por consulta (solo con `QUERY_COMPLETE_CONTEXT` encendida). |
| `QUERY_RETRY_CUT_ANSWERS` | texto (`on`/`off`) | `off` | Enciende la detección de cortes con reintento y aviso. Valor inválido: apagado con un aviso. |

Las dos variables de texto se interpretan con la misma función de la feature 006 (`on`, `true`, `1`, `yes` encienden; `off`, `false`, `0`, `no` y vacío apagan; otro valor apaga y avisa una vez).

## Pasaje (`Passage`, ya existente en `rag/context.py`)

| Campo | Tipo | Descripción |
|---|---|---|
| `document_id`, `domain`, `text`, `first_index`, `last_index`, `score` | ya existentes | Sin cambios. |
| `continues` | booleano (**nuevo**) | Verdadero si el documento tiene fragmentos posteriores a `last_index` que no se entregaron. Con la opción apagada no se calcula (siempre falso). |

**Regla de validación**: `continues` es verdadero solo si `last_index + 1 < total de fragmentos del documento`; para un documento entregado completo es falso.

## Contexto entregado al modelo (`RagContext`)

Mismos campos que hoy (`domain`, `document`, `excerpt`, `reference` de la 006). Con la opción de contexto completo, el `excerpt` de un pasaje con `continues` verdadero termina con la línea `[...el documento continúa]` en el texto que ve el modelo; el `excerpt` de la respuesta de la API (`Source.excerpt`) sigue siendo el texto original, sin la marca.

## Respuesta del modelo (`LLMAnswer`)

| Campo | Tipo | Descripción |
|---|---|---|
| `text`, `model`, `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `cost_usd` | ya existentes | Sin cambios. |
| `finish_reason` | `"stop"`, `"length"`, `"other"` o nulo (**nuevo**) | Motivo de fin normalizado. Nulo si el proveedor no lo informa. |

## Decisión de completitud (`CompletenessOutcome`, nuevo, en `rag/completeness.py`)

| Campo | Tipo | Descripción |
|---|---|---|
| `retried` | booleano | Se hizo un segundo intento. |
| `still_cut` | booleano | La respuesta entregada sigue con un fin anormal. |
| `note` | texto o nulo | Nota para el registro de Uso (ver abajo). |

## Registro de consultas (campos existentes de `QueryLog`)

| Campo | Uso con las opciones encendidas |
|---|---|
| `prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `cost_usd` | Suma de los dos intentos si hubo reintento. |
| `latency_ms` | Incluye el reintento. |
| `reject_reason` | Notas en consultas respondidas: `Respuesta cortada: se reintentó`, o `Respuesta cortada: se entregó con aviso`. Si coincide con la nota de las citas de la 006 (`Fuentes: sin citas utilizables, se mostraron todas`), se unen con `; `. Nulo en los demás casos. |

## Texto fijo del aviso de posible corte

`Aviso: la respuesta pudo quedar incompleta.` en una línea final aparte, separada por una línea en blanco.

## Resultado de una consulta en la herramienta de la 005 (`respuestas.json`)

Campos opcionales nuevos por resultado: `reintento` (booleano o nulo), `aviso_de_corte` (booleano o nulo, a partir del texto de la respuesta y de la nota del registro) y `termina_sin_puntuacion` (booleano; el texto de la respuesta no se guarda, solo este dato). El resumen por modo suma `reintentos`, `avisos_de_corte` y `terminan_sin_puntuacion`, con sus proporciones. Los casos de `lista_larga` se evalúan con `contiene` como hoy.
