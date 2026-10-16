# Data Model: Mostrar solo las fuentes que aportaron a la respuesta

No hay tablas ni migraciones nuevas. Son estructuras en memoria de la API y un uso de campos existentes del registro.

## Pasaje entregado (`RagContext`, ya existente)

| Campo | Tipo | Descripción |
|---|---|---|
| `domain` | texto | Nombre del dominio. |
| `document` | texto | Nombre del documento. |
| `excerpt` | texto | Texto del pasaje (nunca se guarda en el registro). |
| `reference` | entero o nulo (**nuevo**) | Número del pasaje dentro de la consulta, de 1 a N, en el orden de entrega. Nulo cuando la opción está apagada: el contexto se formatea como antes. |

## Citas interpretadas (`ParsedCitations`, nuevo, en `src/mia/rag/citations.py`)

| Campo | Tipo | Descripción |
|---|---|---|
| `text` | texto | La respuesta sin la línea de citas (y sin espacios finales sobrantes). Si no había línea, el texto original. |
| `cited` | lista de enteros | Números válidos (entre 1 y N), sin repetir, en orden creciente. |
| `invalid` | lista de enteros | Números fuera de rango, solo informativos para el registro del servidor. |
| `line_found` | booleano | Si había una línea de citas al final. |

**Reglas de validación**: `cited` solo contiene enteros entre 1 y N (N = cantidad de pasajes entregados); los repetidos se descartan; la línea de citas se quita del texto siempre que se reconozca, aunque no tenga números utilizables.

## Selección de fuentes (`SourceSelection`, nuevo)

| Campo | Tipo | Descripción |
|---|---|---|
| `indexes` | lista de enteros | Posiciones (base 1) de los pasajes a listar como fuentes. |
| `safety_rule` | booleano | Verdadero cuando no hubo citas utilizables y se listaron todos los pasajes. |

**Transiciones** (resumen de la tabla de [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md)):
- opción apagada: `indexes` = todos; `safety_rule` = falso; el texto no se toca.
- opción encendida y respuesta "sin información": sin fuentes.
- opción encendida con citas válidas: `indexes` = `cited`; `safety_rule` = falso.
- opción encendida sin citas válidas: `indexes` = todos; `safety_rule` = verdadero.

## Opción de configuración

| Variable | Tipo | Valor por defecto | Descripción |
|---|---|---|---|
| `QUERY_CITED_SOURCES` | texto | `off` | `on`/`true`/`1`/`yes` enciende; `off`/`false`/`0`/`no`/vacío apaga; otro valor se trata como apagado con un aviso en el registro. |

## Registro de consultas (campos existentes de `QueryLog`)

| Campo | Uso con la opción encendida |
|---|---|
| `sources` (JSON) | Lista de `{domain, document}` **filtrada** (lo que la persona vio), sin repetidos. |
| `reject_reason` | En una consulta respondida: `Fuentes: sin citas utilizables, se mostraron todas` cuando rigió la regla de seguridad; nulo en los demás casos. |
| `outcome`, costo, tokens, latencia | Sin cambios. |

## Respuesta de la API (`QueryResponse`)

Sin cambios de estructura: `answer` (texto limpio), `sources` (lista de `{domain, document, excerpt}`, ahora filtrada), `mode`, `latency_ms`, `no_info`, `id`.

## Resultado de una consulta en la herramienta de la 005 (`respuestas.json`)

Se agrega un campo opcional a cada resultado: `regla_de_seguridad` (booleano o nulo si no se pudo leer el detalle de Uso). El resumen por modo suma `regla_de_seguridad_aplicada` (cantidad) y su proporción sobre las respuestas con contenido.
