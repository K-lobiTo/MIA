# Research: Respuestas completas, sin cortes

Todas las incógnitas de la spec quedaron resueltas; no hay marcadores `NEEDS CLARIFICATION`. Fecha: 2026-10-18. Mediciones de apoyo hechas el 2026-10-16 en producción, en solo lectura.

## R1. Qué documento se prolonga y hasta dónde

**Datos**: de 162 documentos, 89 tienen 12 fragmentos o menos, 27 tienen entre 13 y 30, 28 entre 31 y 100 y 18 más de 100. Los programas de curso largos tienen entre 14 y 21 fragmentos (Deep Learning 21, PLN 20, Redes Neuronales y Introducción a la Investigación 17, Diseño de Experimentos 15). Un fragmento son unos 800 caracteres nuevos (unos 250 tokens). En las 29 consultas de la línea base que superaron el umbral, el documento del mejor resultado tenía 12 fragmentos o menos en 9, entre 13 y 25 en 5 (cuatro eran el Acta 04-2026 de 20 fragmentos y uno el CUP_001 de 18) y más de 25 en 15 (por ejemplo el plan de estudios de Ciberseguridad con 309 y la reforma curricular con 392).

**Decisión**: solo los documentos principales (por defecto, el del mejor resultado; variable `QUERY_COMPLETE_DOCUMENTS`) reciben el trato ampliado:
- si tienen hasta `QUERY_COMPLETE_DOCUMENT_MAX_CHUNKS` fragmentos (25 por defecto), se entregan completos;
- si son más largos, a cada resultado relevante del documento se le suman `QUERY_COMPLETE_FORWARD_NEIGHBORS` fragmentos posteriores (4 por defecto) en vez de uno; el anterior sigue siendo uno.

Los demás documentos siguen como hoy (el fragmento y un vecino a cada lado, o completos si tienen 12 o menos).

**Justificación**: las listas y secciones continúan hacia adelante del fragmento donde empiezan; entregar el documento principal entero cuando cabe resuelve los temarios de curso, y el avance hacia adelante mejora las listas en documentos largos sin duplicar el costo. Limitarlo al documento principal acota el costo: el 17 % de las consultas (5 de 29) pasaría a documento completo y el 52 % (15 de 29) ganaría 3 fragmentos más, unos 750 tokens, lo que estima un aumento medio de costo cercano al 10 % y está dentro del 25 % aceptado.

**Alternativas descartadas**: (a) subir `QUERY_FULL_DOCUMENT_MAX_CHUNKS` de 12 a 25 para todos los documentos: cada consulta que toque un documento de 13 a 25 fragmentos entregaría hasta 20.000 caracteres más por documento, y el modo con razonamiento (16 resultados) sumaría decenas de miles de tokens, muy por encima del 25 %; (b) ampliar los vecinos de todos los resultados (por ejemplo 3 de cada lado): crece el costo sin garantizar la lista; (c) detectar con reglas si la pregunta pide una lista ("cuáles son", "contenidos"): frágil y específico del español; (d) reindexar por secciones o con fragmentos más grandes: obliga a recargar los documentos y cambia todos los puntajes de la línea base; (e) una segunda llamada al modelo para pedir más contexto cuando falte: duplica el costo de las consultas largas.

## R2. Tope de contexto por consulta

**Decisión**: `QUERY_CONTEXT_MAX_CHARS` (80.000 caracteres por defecto, unos 22.000 tokens, más del doble del contexto típico del modo con razonamiento, 11.000 tokens). Cuando la suma de los pasajes lo supera, se descartan primero los pasajes de menor puntaje que no sean de un documento principal, nunca los del documento principal. Solo rige con `QUERY_COMPLETE_CONTEXT` encendido (apagado, no hay tope, igual que hoy).

**Justificación**: el tope es la red de seguridad del costo (FR-005); en el uso normal no se alcanza, porque el aumento previsto es de decenas de miles de caracteres a lo sumo en las consultas del documento completo.

## R3. Cómo se marca lo que el contexto no incluye

**Decisión**: cada pasaje que no llega al final del documento (hay fragmentos posteriores sin entregar) lleva, en el texto que ve el modelo, la marca `[...el documento continúa]`, y con la opción encendida se agrega a las instrucciones un párrafo breve que le pide, cuando la respuesta sea una lista o sección y el pasaje termine con esa marca, decir al final que la lista puede continuar en el documento (por su nombre). La marca va solo en el contexto del modelo; el `excerpt` que ve la persona en las fuentes es el texto original.

**Justificación**: cumple FR-004 sin heurísticas de lenguaje: la afirmación de que es parcial la hace el modelo, que puede ver la marca; si el documento se entregó completo no hay marca y no se pide aviso. Con las citas de la 006, el párrafo de citas va después y la línea `FUENTES:` sigue siendo la última.

**Alternativas descartadas**: agregar el aviso por código al final de todas las respuestas cuyo pasaje continúe (falsos avisos en respuestas que no son listas, que son la mayoría).

## R4. Motivo de fin de la generación

**Decisión**: `LLMAnswer.finish_reason` (texto o `None`), normalizado a tres valores: `"stop"` (fin normal), `"length"` (se agotó el límite de longitud) y `"other"` (cualquier otro: filtro de contenido, error del proveedor, etc.); `None` si el proveedor no lo informa. Traducción por proveedor:
- OpenRouter y GLM (formato OpenAI): `choices[0].finish_reason`: `stop` es normal, `length` es corte, el resto `other`.
- Anthropic: `stop_reason`: `end_turn` y `stop_sequence` son normales, `max_tokens` es corte, el resto `other`.
- Gemini: la API de interacciones no expone un motivo comparable en el código actual: queda `None`.

Solo `"length"` y `"other"` disparan reintento; `None` (desconocido) no (FR-016).

**Justificación**: un campo opcional común mantiene la interfaz intercambiable (principio III); los proveedores nuevos no necesitan hacer nada para seguir funcionando.

## R5. Reintento

**Decisión**: con `QUERY_RETRY_CUT_ANSWERS` encendida y `finish_reason` anormal, si la respuesta no es "sin información": (1) se vuelve a consultar el tope diario del artefacto y de la API con los gastos ya registrados más el costo del primer intento, y si alguno se alcanzó no se reintenta; (2) se repite la misma llamada una vez; (3) el costo, los tokens y la latencia de ambos intentos se suman en el registro; (4) si el segundo intento termina con normalidad se entrega ese, y si no, el primero o el segundo (el más largo) con el aviso fijo `Aviso: la respuesta pudo quedar incompleta.` en una línea final aparte. El aviso va después de procesar la línea de fuentes de la 006.

**Notas en el registro** (campo `reject_reason`, sin migración, igual que la 006): `Respuesta cortada: se reintentó` o `Respuesta cortada: se entregó con aviso`; si coincide con la nota de la regla de seguridad de las citas, se unen con `; `.

**Justificación**: un reintento cubre cortes aleatorios del proveedor sin disparar el costo; un segundo corte seguido suele indicar un problema del contexto o del proveedor y es mejor decirlo que insistir.

**Alternativas descartadas**: subir el límite de tokens de salida en el segundo intento (depende del proveedor y no ataca el corte del 2026-10-16, que ocurrió muy por debajo del límite); reintentar varias veces (el costo crecería con la incertidumbre); descartar la respuesta con un error 502 (peor que un texto útil con aviso).

## R6. El corte que el modelo no declara

**Hallazgo**: el corte del 2026-10-16 (IN3, modo literal, 1 de 7) ocurrió con 4.500 tokens de 8.000, así que no fue el límite de longitud; si el proveedor lo reportó como fin normal, la detección por motivo no lo vería.

**Decisión**: además del motivo de fin, la herramienta de medición cuenta las respuestas que terminan sin signo de puntuación final (`.`, `!`, `?`, `)`, `:`, `;`, comillas, `*`) como "posiblemente cortadas". No cambian el comportamiento de la API (los falsos positivos serían reintentos innecesarios: una lista puede terminar en un ítem sin punto), pero permiten medir cuántos cortes ocultos hay y, si son relevantes, decidir una segunda regla con datos.

## R7. Compatibilidad con la feature 006

**Decisión**: el orden en la ruta es: (1) armar el contexto con la política de la 007; (2) numerar los pasajes si la 006 está encendida (la numeración usa los pasajes finales, ya recortados por el tope); (3) llamar al modelo con las instrucciones del modo más el párrafo de completitud más el de citas; (4) si el motivo de fin es anormal, reintentar; (5) con la respuesta final, quitar la línea de fuentes y elegir las fuentes; (6) detectar "sin información" sobre el texto limpio; (7) agregar el aviso de corte, si corresponde, al texto limpio. Una prueba cubre cada combinación de las dos opciones de 006 y 007.

## R8. Casos de medición

**Decisión**: categoría nueva `lista_larga` en `scripts/datos/casos_busqueda.json` con 8 casos como mínimo, cada uno con el último ítem del temario o la lista en `contiene`: Diseño de Experimentos (MC6104), Deep Learning (MC8840), Procesamiento de Lenguaje Natural (MC8850), Redes Neuronales (MC8803), Introducción a la Investigación (MC7201), Sistemas Operativos Avanzados (MC6004), las líneas de TFG y una lista de un acta. El último ítem de cada uno se lee del propio documento (público para las pruebas) y se verifica a mano antes de usarlo. Además de `contiene`, la herramienta registra por consulta `reintento`, `aviso_de_corte` y `termina_sin_puntuacion` (desde las notas del registro de Uso y el texto), y el resumen y `comparar` los muestran.

## R9. Tolerancia de costo y latencia

**Decisión** (aclaración del 2026-10-16): costo medio y latencia p50 hasta 25 % por encima de la línea base, comparados contra el promedio de la línea base y un control con las opciones apagadas, y por la mediana de la razón caso por caso, como en la 006. El estimado de R1 (cerca del 10 %) deja margen; si la medición lo contradice, las variables permiten bajar el alcance (por ejemplo, pasar `QUERY_COMPLETE_FORWARD_NEIGHBORS` a 2) sin tocar código.

## R10. Despliegue de la medición

**Decisión**: como en la 006, se mide con `servicios.py encender MIA --ref origin/dev` después de fijar las variables con `railway variable set ... --skip-deploys` (cambiarlas sin esa opción redesplegaría desde `main` y se perdería el código de `dev`, ver OPERACION.md). Tres corridas: control (todo apagado), contexto completo y contexto completo más reintento, para separar los efectos.
