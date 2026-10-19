# Research: Pregunta limpia

Decisiones de diseño con su razón y las alternativas. Las cifras de la línea base están en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md).

## R1. Reglas de texto, no modelo

**Decision**: la reducción es un conjunto de expresiones regulares sobre la pregunta normalizada, sin llamada a ningún modelo de lenguaje.

**Rationale**: BUS-7 pide costo nulo en modelos para esta etapa, y las preguntas de identificación tienen pocas formas (quién es, qué es, háblame de, dame información sobre). El embedding de la versión corta es el modelo local ya presente, así que el segundo intento cuesta una búsqueda más.

**Alternatives considered**: pedirle al modelo que reformule (una llamada más por consulta fallida, más costo y latencia, y puede inventar términos); descartada.

## R2. Solo preguntas de identificación o descripción; sin quitar palabras vacías

**Decision**: la reducción exige una de las formas de la tabla de [contracts/pregunta-limpia.md](contracts/pregunta-limpia.md). No se quitan palabras vacías en general ni se detectan entidades.

**Rationale**: en "¿Cuántas horas tiene el curso?" lo que importa es "horas", y reducir a "curso" traería documentos del curso sin responder lo preguntado; justo el aumento de respuestas inventadas que BUS-3 prohíbe. En las preguntas de identificación la respuesta es todo lo que dicen los documentos sobre X, y buscar solo X es lo correcto. Las listas de stopwords de NLTK o spaCy no se necesitan para esto y reducir con ellas exige recalibrar. Un reconocedor de entidades (spaCy `es_core_news`) agrega una dependencia que consume memoria.

**Alternatives considered**: palabras vacías como tercer intento (se podría medir más adelante); entidades con spaCy; heurística de mayúsculas iniciales (falla con minúsculas y siglas); todas descartadas por ahora (ver V3, sección 2.5).

## R3. "Cuál es" queda fuera

**Decision**: la forma "cuál(es) es/son" de la sección 2.5 del documento V3 no se incluye.

**Rationale**: "¿Cuál es el costo del curso X?" o "¿Cuál es el horario?" piden un dato y se reducirían a "costo del curso X", la clase de daño que R2 evita. "¿Cuál es el TFG?" es rarísimo. Se puede agregar luego si las preguntas reales lo piden (el documento dice que la lista se ajusta con ellas).

## R4. Guardas sobre el resto de la pregunta

**Decision**: después de quitar la envoltura, el resto (la "pregunta limpia") debe cumplir todo esto, o no hay segundo intento:

1. Al menos 3 caracteres útiles (sin signos ni espacios en los extremos) y distinto, ya normalizado, de la pregunta original.
2. A lo sumo 8 palabras.
3. No empieza con "lo" ni "que" y no contiene "que", "cuando", "donde", "cuanto/a/os/as" ni "porque" como palabra completa. Esas palabras indican una cláusula ("¿Qué es lo que establece el reglamento sobre las becas?") y, por tanto, una pregunta sobre un dato y no sobre un nombre.
4. La pregunta es una sola: después de quitar los signos de los extremos no quedan signos `¿ ? ¡ !` en el interior.


**Rationale**: son los casos negativos de la sección 2.5 y de User Story 2. El límite de 8 palabras cubre nombres de personas con cuatro palabras y nombres de programas largos ("Maestría Profesional en Analítica de Negocios", 6 palabras) sin dejar pasar oraciones.

**Alternatives considered**: sin límite de palabras (deja pasar oraciones largas); límite de 5 (corta nombres de programas).

## R5. Normalización conservando posiciones

**Decision**: se construye una copia de la pregunta en minúsculas y sin tildes carácter por carácter (cada carácter se reemplaza por su letra base), de modo que la copia tiene la misma longitud que el original. Las reglas se aplican a la copia y el resultado se corta del original con los mismos índices.

**Rationale**: así el texto que se busca conserva mayúsculas y tildes (el embedding de e5 distingue "Sandí" de "Sandi" muy poco, pero el texto buscado debe ser el del usuario) y no hace falta una tabla de tildes. Los signos `¿ ? ¡ !` se quitan de los extremos antes de aplicar las reglas.

## R6. Dónde se aplica y qué cambia en la ruta

**Decision**: tras `relevant = [...]`, si no hay resultados sobre el umbral y la variable está encendida, se llama a `clean_question`; si devuelve texto, se calcula su embedding (`is_query=True`), se hace una segunda búsqueda con los mismos dominios y límite y se recalcula `relevant`. El resto del flujo (contexto, citas, reintento, fuentes) no cambia. El modelo recibe `payload.question`, la pregunta original.

**Rationale**: la pregunta original da el contexto de lo que se pregunta ("quién es"); lo que cambia es solo qué fragmentos se recuperan. Es lo mínimo y evita que una reformulación mal calibrada cambie la respuesta.

**Alternatives considered**: pasarle al modelo la pregunta limpia (pierde el verbo de la pregunta y la respuesta puede salir en otra forma); hacer el segundo intento siempre y quedarse con el mejor puntaje (cambia consultas que hoy funcionan y duplica búsquedas).

## R7. La nota de Uso

**Decision**: nota en `reject_reason`, unida con "; " a las de las features 006 y 007: `Pregunta limpia: «<texto>» (con resultados)` o `Pregunta limpia: «<texto>» (sin resultados)`. El texto se recorta a 120 caracteres. Hoy la respuesta "sin información" no escribe `reject_reason`; pasa a escribirlo cuando hay nota. El caso en que el modelo mismo responde "sin información" tras un segundo intento exitoso también deja la nota.

**Rationale**: sin migraciones, volver a `prototipo-v2-estable` sigue siendo posible (la columna ya existe y es texto). Las dos variantes permiten contar cuántas veces ayuda y cuántas no (User Story 3). El texto reducido ya forma parte de la pregunta que se registra, así que no agrega información personal.

**Alternatives considered**: una columna nueva (migración, rompe el rollback); un campo en la respuesta de la API (cambia el contrato sin necesidad).

## R8. Variable de configuración

**Decision**: `QUERY_CLEAN_QUESTION`, texto "on" u "off", apagada por defecto, con el mismo manejo de valores inválidos de `switch_enabled` de la feature 007 (aviso una vez, tratado como apagado).

**Rationale**: BUS-6 y el patrón del proyecto. Una variable de texto evita que un valor inválido impida el arranque.

## R9. Medición

**Decision**: tres pasos, de menor a mayor costo:

1. `puntajes` (solo lectura, gratis): la herramienta calcula la variante "limpia" con el mismo módulo y la compara con la completa y la corta; anticipa cuántos casos pasarían el umbral y en qué puesto aparece el documento.
2. Corrida de control de `respuestas` con la opción apagada sobre el conjunto ampliado.
3. Corrida de `respuestas` con la opción encendida, `comparar` con el control y con la línea base.

**Rationale**: el costo del segundo intento es solo local; el gasto de la medición es el de las respuestas que antes eran "sin información" y ahora pasan a ser respuestas, más el ruido de las demás. La corrida de control es necesaria porque el ruido de costo entre corridas es grande (lección de las features 006 y 007). Se pide autorización y tope de gasto antes de cualquier corrida en producción.

## R10. Límites que no se resuelven aquí

- **Siglas**: "¿qué es el TFG?" se reduce a "TFG"; que el vocabulario coincida con "trabajo final de graduación" no depende de la envoltura (lo cubren D o E).
- **Documento más allá del número de resultados**: S22-1 con el nombre solo trae el documento en el puesto 12; el modo literal trae 8. El segundo intento no cambia el límite de resultados. Se reporta en la medición y es argumento para el reranker con más candidatos.
- **S22-3 corta** sigue bajo el umbral (0,807): no se resuelve con esta opción y se reporta aparte (SC-001).
