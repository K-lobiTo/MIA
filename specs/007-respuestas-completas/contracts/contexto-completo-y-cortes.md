# Contrato: contexto completo y detección de cortes

No cambia ningún endpoint ni el esquema de la API. Fija los acuerdos nuevos entre la ruta de consulta, el contexto que se entrega al modelo, los proveedores y el registro de Uso.

## 1. Qué se entrega como contexto (`QUERY_COMPLETE_CONTEXT`)

Con la opción **apagada**: igual que hoy (el fragmento relevante con `QUERY_CONTEXT_NEIGHBORS` vecinos de cada lado, o el documento completo si tiene hasta `QUERY_FULL_DOCUMENT_MAX_CHUNKS` fragmentos).

Con la opción **encendida**, para cada uno de los `QUERY_COMPLETE_DOCUMENTS` documentos de mejor resultado (documentos principales):

| Tamaño del documento principal | Qué se entrega |
|---|---|
| hasta `QUERY_COMPLETE_DOCUMENT_MAX_CHUNKS` fragmentos | el documento completo, en un solo pasaje |
| más largo | cada resultado relevante con 1 fragmento anterior y `QUERY_COMPLETE_FORWARD_NEIGHBORS` posteriores, unidos en pasajes continuos |

Los demás documentos se entregan como hoy. Si el total supera `QUERY_CONTEXT_MAX_CHARS`, se descartan pasajes de los demás documentos, de menor a mayor puntaje, hasta cumplir el tope; los pasajes del documento principal no se descartan.

**Marca de continuación**: a un pasaje que no llega al último fragmento de su documento se le agrega, solo en el texto que ve el modelo, una línea final `[...el documento continúa]`. El `excerpt` de las fuentes de la respuesta no la lleva.

**Instrucción de completitud**: con la opción encendida se agrega a las instrucciones del modo (antes del párrafo de citas de la 006) este contenido:

> Si la respuesta es una lista o sección y el fragmento termina con la marca [...el documento continúa], indica al final de tu respuesta, en una línea aparte, que la lista puede continuar en ese documento y nómbralo. No escribas esa advertencia si el fragmento no lleva la marca.

## 2. Motivo de fin de la generación (`LLMAnswer.finish_reason`)

| Valor | Cuándo | ¿Reintento? |
|---|---|---|
| `"stop"` | el modelo terminó con normalidad (`stop`, `end_turn`, `stop_sequence`) | no |
| `"length"` | se agotó el límite de longitud (`length`, `max_tokens`) | sí |
| `"other"` | cualquier otro motivo informado (`content_filter`, error, etc.) | sí |
| `None` | el proveedor no lo informa | no |

Un proveedor nuevo puede dejarlo en `None` y seguir funcionando.

## 3. Reintento y aviso (`QUERY_RETRY_CUT_ANSWERS`)

| Situación | Resultado |
|---|---|
| Motivo normal o desconocido | sin cambios |
| Motivo anormal y la respuesta es "sin información" | sin reintento |
| Motivo anormal y un tope de gasto ya se alcanzó (artefacto, modo con razonamiento o toda la API) | sin reintento; texto original con el aviso; nota `Respuesta cortada: se entregó con aviso` |
| Motivo anormal, reintento con motivo normal | se entrega el segundo texto; nota `Respuesta cortada: se reintentó`; costos y tokens sumados |
| Motivo anormal, reintento también anormal | se entrega el texto más largo con el aviso `Aviso: la respuesta pudo quedar incompleta.`; nota `Respuesta cortada: se entregó con aviso`; costos sumados |
| El reintento falla por error del proveedor | se entrega el texto del primer intento con el aviso (no se devuelve un error 502 si ya había una respuesta) |

El aviso se agrega después de quitar la línea `FUENTES:` de la 006 y no afecta a la detección de "sin información".

## 4. Orden de operaciones en la ruta (resumen)

contexto (política de la 007) → numeración de pasajes (006) → instrucciones del modo + completitud + citas → llamada al modelo → reintento si corresponde → quitar la línea de fuentes y elegir fuentes (006) → detectar "sin información" → agregar el aviso de corte → registrar.

## 5. Respuesta de la API

Misma estructura de siempre: `answer` (con el aviso al final si corresponde), `sources`, `mode`, `latency_ms`, `no_info`, `id`.

## 6. Registro de Uso

Ver [data-model.md](../data-model.md): `reject_reason` lleva las notas de corte (y la de las citas), y los costos, tokens y latencia suman los dos intentos.

## 7. Cambios a la herramienta de la feature 005

- Categoría de caso `lista_larga` (`contiene` obligatorio).
- `respuestas` registra `reintento`, `aviso_de_corte` y `termina_sin_puntuacion` por consulta; el resumen por modo suma los tres.
- `informe` y `comparar` los muestran; las corridas anteriores (sin esos campos) siguen leyéndose sin error.
