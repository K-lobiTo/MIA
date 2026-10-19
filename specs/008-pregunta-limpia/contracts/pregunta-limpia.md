# Contrato: pregunta limpia

Decisiones y razones en [research.md](../research.md). Estructuras en [data-model.md](../data-model.md).

## Variable de configuración

| Variable | Valores | Por defecto | Efecto |
|---|---|---|---|
| `QUERY_CLEAN_QUESTION` | `on` / `off` (también `true`, `1`, `yes` y `false`, `0`, `no`, vacío) | `off` | Con `on`, una consulta cuya primera búsqueda no deja nada sobre el umbral hace un segundo intento con la pregunta limpia. Cualquier otro valor se trata como `off` y deja un aviso en el registro del servidor, una vez por valor. |

Se lee en cada consulta; cambiarla y reiniciar el servicio basta. Con `off` el comportamiento es idéntico al de antes de la feature.

## Función `clean_question(question: str) -> str | None`

Entrada: la pregunta del usuario, tal cual. Salida: el texto que se busca, con la escritura original, o `None` si no hay segundo intento.

Algoritmo:

1. Normalizar: primero colapsar los espacios de la pregunta original (así original y copia comparten índices); luego una copia en minúsculas y sin tildes de la misma longitud (cada carácter se reemplaza por su letra base). Quitar `¿ ? ¡ !`, espacios y `. , ; :` de los extremos. Si quedan `¿ ? ¡ !` en el interior, devolver `None` (más de una pregunta).
2. Quitar de cero a dos cortesías iniciales (tabla siguiente) y, al final, "por favor" o "gracias".
3. Exigir una envoltura (tabla siguiente) al inicio de lo que queda; si ninguna aplica, `None`.
4. Lo que sigue a la envoltura es el candidato. Cortarlo del original con los mismos índices. Aplicar las guardas; si alguna falla, `None`.

### Cortesías (se quitan primero, solo si después aparece una envoltura)

| Patrón sobre el texto normalizado | Ejemplo |
|---|---|
| `por favor,?` | "Por favor, dime quién es X" |
| `(me )?(puedes\|podrias\|puede\|podria) (decir\|explicar\|indicar\|contar)(me)?` | "¿Me puedes decir qué es X?" |
| `dime` | "Dime quién es X" |
| `(quiero\|necesito\|quisiera\|me gustaria) saber` | "Quisiera saber quién es X" |

### Envolturas

| Grupo | Patrón sobre el texto normalizado | Entrada | Candidato |
|---|---|---|---|
| Identificación | `(quien\|quienes\|que) (es\|son\|era\|eran\|fue\|fueron\|significa\|significan)( el\| la\| los\| las\| un\| una)?` | "¿Quién es Natalia Soto Solís?" | "Natalia Soto Solís" |
| | | "¿Qué es el TFG?" | "TFG" |
| Pedir información | `(dame\|quiero\|necesito\|busco)( toda)?( la)? (informacion\|datos\|detalles)( que (haya\|tengas\|tenga))? (sobre\|acerca de\|de)` | "Dame información sobre la maestría" | "la maestría" |
| Pedir que hable de algo | `(hablame\|cuentame\|explicame) (de\|sobre\|acerca de)` | "Háblame de Natalia Soto Solís" | "Natalia Soto Solís" |
| | `que (sabes\|sabe\|se sabe) (de\|sobre\|acerca de)` | "¿Qué se sabe de Cibercrimen?" | "Cibercrimen" |

Todas con límite de palabra (`\b`) y separadas por un espacio. La lista es ampliable; cada forma nueva exige filas en la tabla de pruebas, positivas y negativas.

### Guardas del candidato

1. Al menos 3 caracteres, sin contar signos ni espacios de los extremos, y distinto de la pregunta normalizada.
2. A lo sumo 8 palabras.
3. No empieza con "lo" ni "que" y no contiene "que", "cuando", "donde", "cuanto", "cuanta", "cuantos", "cuantas" ni "porque" como palabra completa. Tampoco empieza con un adjetivo o atributo que indica que la pregunta pide un dato y no un nombre: "necesario", "necesaria", "obligatorio", "obligatoria", "posible", "suficiente", "importante", "mejor", "igual", "diferente", "nuevo", "nueva" (cubre "¿Qué es nuevo en la maestría?"; las formas "qué hay/tiene de..." no se reducen porque son modismos que piden un dato).
4. Si la envoltura usa un verbo en pasado ("era", "eran", "fue", "fueron"), la primera palabra del candidato no es un participio (termina en -ado, -ada, -ados, -adas, -ido, -ida, -idos, -idas): "¿Quién fue designado coordinador del proyecto?" pide un dato y no un nombre. Con "es" y "son" no se aplica, porque hay apellidos como "Alvarado".
5. No contiene `¿ ? ¡ !`.

## Casos de la tabla de pruebas (resumen)

| Pregunta | Resultado |
|---|---|
| ¿Quién es Natalia Soto Solís? | Natalia Soto Solís |
| ¿Quién   es   Natalia  Soto Solís? (espacios dobles) | Natalia Soto Solís |
| quien es natalia soto solis | natalia soto solis |
| ¿Qué es el TFG? | TFG |
| ¿Qué son las líneas de TFG? | líneas de TFG |
| ¡Háblame de Cibercrimen! | Cibercrimen |
| ¿Me puedes decir quién es Joseph Obando Sandí? | Joseph Obando Sandí |
| Por favor, dime qué es el IPA | IPA |
| Dame información sobre la maestría | la maestría |
| ¿Qué se sabe de Cibercrimen? | Cibercrimen |
| ¿Cuántos créditos tiene el curso de IPA en Big Data? | `None` |
| ¿Cuál es el costo del curso X? | `None` |
| ¿Qué es lo que establece el reglamento sobre las becas? | `None` |
| ¿Qué es necesario para graduarse? | `None` |
| ¿Quién fue designado coordinador del proyecto ante FUNDATEC? | `None` (voz pasiva) |
| ¿Quién fue Alan Turing? | Alan Turing |
| ¿Qué es obligatorio en el TFG? | `None` |
| Who is Natalia Soto? | `None` (sin envoltura en español) |
| ¿Qué es el TFG que ofrece la maestría? | `None` |
| ¿Quién es X? ¿Y cuántos créditos tiene Y? | `None` |
| ¿Quién es? | `None` |
| ¿Qué es la I? | `None` (menos de 3 caracteres) |
| Por favor, ¿cuántos créditos tiene X? | `None` |
| Natalia Soto Solís | `None` (sin envoltura) |

## Ruta `POST /query`

Con `QUERY_CLEAN_QUESTION=on`, después de la primera búsqueda y de filtrar por umbral:

1. Si hay fragmentos sobre el umbral, nada cambia.
2. Si no hay y `clean_question(payload.question)` devuelve texto: calcular su embedding con `is_query=True`, buscar con los mismos dominios y `config.search_limit`, filtrar por el mismo umbral y dejar `clean_note = Pregunta limpia: «texto» (con resultados|sin resultados)`.
3. Si siguen sin fragmentos: respuesta "sin información" sin llamar al modelo, con la nota en `reject_reason`.
4. Si hay fragmentos: el flujo normal con `payload.question` como pregunta del modelo. Las notas de las features 006 y 007 se unen a `clean_note` con "; " en este orden: pregunta limpia, corte, citas.

La estructura de `QueryResponse` no cambia.

## Registro de Uso

`reject_reason` de la consulta contiene la nota si hubo segundo intento (tanto en `answered` como en `no_info`). Formato: `Pregunta limpia: «<texto recortado a 120 caracteres>» (con resultados)` o `(sin resultados)`. No hay columnas nuevas.

## Herramienta `scripts/linea_base.py`

| Subcomando | Cambio |
|---|---|
| `puntajes` | Para cada caso donde `clean_question(pregunta)` devuelve texto y es distinto de la variante corta ya definida, mide una variante `limpia` (solo lectura, sin costo). Si la variante corta del caso es igual a la limpia, no se repite. |
| `respuestas` | Registra por consulta `pregunta_limpia` (nota presente en `reject_reason`) y `pregunta_limpia_ayudo` (nota con resultados), y los resume por modo. Los casos con `sin_pregunta_limpia: true` deben terminar sin esa nota (los negativos). |
| `comparar` | Trata `pregunta_limpia` y `pregunta_limpia_ayudo` como campos opcionales (corridas anteriores no los tienen). |
| `informe` | Cuenta consultas con segundo intento y cuántas pasaron el umbral. |
