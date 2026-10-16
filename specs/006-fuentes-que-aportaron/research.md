# Research: Mostrar solo las fuentes que aportaron a la respuesta

Todas las incógnitas de la spec quedaron resueltas; no hay marcadores `NEEDS CLARIFICATION`. Fecha: 2026-10-15.

## R1. Cómo indica el modelo qué fragmentos usó

**Decisión**: una línea final de la respuesta con el formato `FUENTES: 1, 3`, pedida en la instrucción de sistema. La API la lee, la **quita del texto** y la valida.

**Justificación**: funciona con cualquier modelo y proveedor (principio III), no requiere llamadas extra (FR-002), es fácil de quitar sin dañar el texto (FR-006) y, al ir al final, no interfiere con la estructura del modo con razonamiento ("Lo que dicen los documentos" y "Conclusión"). Si la respuesta se corta antes de la línea, simplemente no hay cita y rige la regla de seguridad.

**Alternativas descartadas**:
- *Marcas dentro del texto (`[1]`)*: el modelo las pone donde usa el dato, pero ensucian el texto, hay que limpiarlas con cuidado (listas, números legítimos entre corchetes) y la persona vería referencias a algo que no puede abrir.
- *Salida estructurada (JSON) con respuesta y fuentes*: obliga a que el modelo respete un esquema, rompe la presentación en Markdown y no todos los modelos y proveedores lo soportan igual.
- *API de citas nativa del proveedor (Claude Citations, Gemini File Search)*: ata la función a un proveedor, contra el principio III, y OpenRouter no las unifica.
- *Un segundo modelo "juez" que decida qué fragmentos sirvieron*: cuesta tokens por consulta (FR-002 lo prohíbe).

## R2. Qué se numera

**Decisión**: los **pasajes** que `build_passages` ya arma (un pasaje es el fragmento relevante con sus vecinos unidos, o el documento completo si es corto), numerados de 1 a N en el orden en que se entregan. El número va en la etiqueta de cada uno: `[Fuente 3: dominio=..., documento=...]`.

**Justificación**: es la unidad que el modelo lee y la que hoy se lista como fuente; la validación es exacta (un número entre 1 y N). Si el modelo cita un pasaje, se muestra ese pasaje y su documento, que es lo que la Consulta ya sabe dibujar.

**Qué se conserva**: orden y contenido de los pasajes (FR-007). Con la opción apagada la etiqueta queda `[Fuente: dominio=..., documento=...]`, byte por byte igual que hoy.

## R3. Reglas de interpretación y validación

**Decisión** (detalle en [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md)):
1. Se mira la **última línea no vacía** del texto. Si, sin contar signos de Markdown (`*`, `_`, `#`, `>`, espacios), empieza por `fuentes:` o `fuente:` (sin distinguir mayúsculas ni tildes), es la línea de citas y **se quita del texto siempre**, tenga o no números utilizables.
2. De esa línea se extraen los enteros. Se descartan los repetidos y los que no están entre 1 y N.
3. Si queda al menos uno, la lista de fuentes son esos pasajes **en el orden original de entrega** (no en el que el modelo los nombró).
4. Si no queda ninguno (sin línea, sin números o todos fuera de rango), la lista son **todos** los pasajes entregados y se marca la regla de seguridad.
5. Si el texto limpio, sin espacios ni punto final, es `SIN_INFORMACION`, es una respuesta "sin información" (sin fuentes, como hoy), aunque el modelo haya escrito la línea de citas.
6. Una línea `FUENTES:` que no esté al final no se interpreta.

**Justificación**: reglas simples y deterministas, sin heurísticas de lenguaje; el límite conocido (un modelo puede citar algo irrelevante pero existente) se acepta y se mide con la batería (edge case de la spec).

## R4. Comportamiento seguro

**Decisión**: sin citas utilizables, **se muestran todas las fuentes entregadas** (el comportamiento de hoy). Con citas parcialmente inválidas, se muestran las válidas. Nunca se deja vacía la lista de una respuesta con contenido (FR-004, SC-007).

**Justificación**: la trazabilidad (principio V) pesa más que la limpieza de la lista; peor que una lista larga es una respuesta sin de dónde verificar.

## R5. La opción de configuración

**Decisión**: `QUERY_CITED_SOURCES` como texto, `off` por defecto; se considera encendido con `on`, `true`, `1` o `yes` (sin distinguir mayúsculas) y apagado con `off`, `false`, `0`, `no` o vacío. Cualquier otro valor se trata como apagado y deja un aviso en el registro (FR-009). Se lee en cada consulta, así que cambiar la variable y reiniciar el servicio basta.

**Justificación**: un `bool` de pydantic haría fallar el arranque con un valor inválido; el requisito pide caer al comportamiento anterior. El resto de las opciones de consulta (`QUERY_*`) ya viven en `config.py` como variables de entorno, así que no hay mecanismo nuevo.

**Alternativas descartadas**: bandera por artefacto o por modo (más control, pero más superficie en el panel y la base; la medición es global y por ahora basta).

## R6. Dónde se aplica

**Decisión**: en la ruta de consulta, después de recibir la respuesta del modelo y antes de decidir si es "sin información": (1) interpretar y quitar la línea de citas, (2) detectar "sin información" sobre el texto limpio, (3) elegir los pasajes a listar. Los costos y tokens se registran igual que hoy. La regla es la misma en los dos modos porque no depende del proveedor.

**Justificación**: concentra el cambio en un punto, mantiene el orden que ya tiene la ruta y evita que una línea `FUENTES:` rompa la detección de "sin información" (BUS-3).

## R7. Cómo se anota la regla de seguridad (FR-012)

**Decisión**: sin migración. El campo `sources` del registro guarda la lista ya filtrada (los documentos que la persona vio), y cuando rige la regla de seguridad se escribe una nota breve en `reject_reason` de esa consulta respondida: `Fuentes: sin citas utilizables, se mostraron todas`. El panel de Uso ya muestra `reject_reason` en gris junto al resultado y el CSV lo incluye, así que la frecuencia se ve y se cuenta sin tocar el esquema; la herramienta de la 005 la lee del detalle de la consulta (`GET /usage/queries/{id}`).

**Justificación**: una columna nueva exigiría una migración y volver al tag `prototipo-v2-estable` obligaría a bajarla antes (la API no arranca con una base más migrada que su código, ver `servicios.py` y OPERACION.md). Con este camino el retroceso sigue siendo un redespliegue. El nombre del campo (`reject_reason`) no es ideal para una nota sobre una consulta que sí se respondió; se documenta como un uso deliberado y se puede mover a una columna propia si más adelante se hace otra migración por otro motivo.

**Alternativas descartadas**: una columna `sources_basis` con migración (más limpia, pero rompe la seguridad del retroceso); un campo nuevo en la respuesta de la API (cambia el contrato aunque sea opcional y la medición no lo necesita); solo un mensaje en el registro del servidor (no se puede contar desde la herramienta).

## R8. Formato de contexto compartido

**Decisión**: `RagContext` gana un campo opcional `reference` (entero) y `llm.py` ofrece `format_context(context)`, que produce la etiqueta con o sin número. Los cuatro proveedores implementados (OpenRouter, Anthropic, Gemini, GLM) dejan de armar el texto por su cuenta y lo piden al helper. Los proveedores `local` y `openai`, que hoy no formatean nada, no cambian.

**Justificación**: hoy las cuatro copias son idénticas; sin el helper habría que modificar cuatro veces el mismo texto y cualquier proveedor nuevo tendría que acordarse de numerar. Una prueba comprueba que, sin `reference`, el texto es idéntico al de antes.

## R9. Efecto en costo y latencia

**Decisión**: se estima un aumento de unos 100 tokens por consulta (instrucción de citas de unos 90 tokens, unos 2 por etiqueta y una línea de unas 8 palabras al final), alrededor del 5 % de los tokens de entrada típicos; se mide con la herramienta de la 005 contra los criterios SC-004 y SC-005 antes de recomendar encenderlo. La instrucción se mantiene corta a propósito.

**Riesgo**: en el modo con razonamiento el modelo puede gastar más tokens de razonamiento al decidir qué citó; la medición lo dirá.

## R10. Qué se mide y cómo

**Decisión**: se reutiliza la herramienta de la feature 005 con una etiqueta nueva (`citas`) para comparar contra `base`: fuentes sobrantes, resultado de cada caso, costo y latencia. Se extiende `respuestas` para registrar en cada consulta si rigió la regla de seguridad (leyendo `reject_reason` del detalle de Uso, que ya consulta para el costo), y el informe y `comparar` la muestran. `puntajes` no hace falta repetirlo: la recuperación no cambia.

**Condición de la corrida**: se enciende la variable en Railway solo durante la medición y se vuelve a apagar, salvo que el usuario decida dejarla encendida.
