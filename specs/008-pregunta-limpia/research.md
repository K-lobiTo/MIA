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
3. No empieza con "lo" ni "que" y no contiene "que", "cuando", "donde", "cuanto/a/os/as" ni "porque" como palabra completa. Esas palabras indican una cláusula ("¿Qué es lo que establece el reglamento sobre las becas?") y, por tanto, una pregunta sobre un dato y no sobre un nombre. Tampoco empieza con un adjetivo o atributo como "necesario", "obligatorio", "posible", "suficiente", "importante", "mejor", "igual", "diferente" o "nuevo/a" ("¿Qué es necesario para graduarse?", "¿Qué es nuevo en el plan?"). Las formas "qué hay/tiene/tienes de..." se retiraron de las envolturas tras la segunda convergencia: reducían modismos que piden un dato ("¿Qué tiene de especial el curso?"): por la misma razón, pide un dato.
4. La pregunta es una sola: después de quitar los signos de los extremos no quedan signos `¿ ? ¡ !` en el interior.


5. Con un verbo en pasado ("era", "eran", "fue", "fueron"), la primera palabra del candidato no es un participio (-ado, -ada, -ido, -ida y plurales): "¿Quién fue designado coordinador específico del proyecto ante FUNDATEC?" (caso A2 de la batería del MVP) se reduciría a "designado coordinador específico del proyecto ante FUNDATEC", que no es un nombre. Se descubrió al listar con `clean_question` las preguntas del conjunto de casos (R11). Con "es" y "son" no se aplica por apellidos como "Alvarado".

**Rationale**: son los casos negativos de la sección 2.5 y de User Story 2. El límite de 8 palabras cubre nombres de personas con cuatro palabras y nombres de programas largos ("Maestría Profesional en Analítica de Negocios", 6 palabras) sin dejar pasar oraciones.

**Alternatives considered**: sin límite de palabras (deja pasar oraciones largas); límite de 5 (corta nombres de programas).

## R5. Normalización conservando posiciones

**Decision**: se construye una copia de la pregunta en minúsculas y sin tildes carácter por carácter (cada carácter se reemplaza por su letra base), de modo que la copia tiene la misma longitud que el original. Antes de normalizar se colapsan los espacios de la pregunta original (colapsarlos después rompería la correspondencia de índices). Las reglas se aplican a la copia y el resultado se corta del original con los mismos índices.

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

## R11. Medición gratuita previa (`puntajes`, 2026-10-18)

Corrida `limpia-previa` (solo lectura sobre producción, 12 s, sin costo): umbral 0,82, modo literal con 8 resultados y modo con razonamiento con 16. "Doc" es el mejor fragmento del documento esperado: puesto y puntaje. La variante `limpia` de S22-1, S22-3 y S22-4 coincide con su variante corta.

| Caso | Pregunta | Completa (mejor, doc) | Limpia (mejor, doc) | Efecto esperado del segundo intento |
|---|---|---|---|---|
| S22-1 | ¿Quién es Natalia Soto Solís? | 0,798, #3 0,789 | 0,833, #12 0,824 | Pasa el umbral. El documento queda en el puesto 12: entra con razonamiento (16) y **no** en literal (8). |
| S22-3 | ¿Quién es Joseph Obando Sandí? | 0,775, ausente | 0,807, #15 0,793 | No pasa el umbral: sigue "sin información". |
| S22-4 | ¿Quién es Luis Diego Cubillo Guevara? | 0,802, #19 0,781 | 0,827, #3 0,819 | Pasan 2 fragmentos de **otro** documento; el esperado queda en 0,819, una milésima bajo el umbral. |
| EN1, EN3, EN5 | Háblame de (las tres personas) | 0,843, 0,837, 0,838 (documento en el puesto 43, 20 y 17) | no aplica | La primera búsqueda **ya pasa** el umbral con otros documentos: no hay segundo intento. |
| EN2, EN4, EN6 | ¿Qué se sabe de (las tres personas)? | 0,813, 0,796, 0,810 | 0,833, 0,807, 0,827 | Igual que S22-1, S22-3 y S22-4. |
| EN7 | ¿Quién es Zacarías Fernández Pizarro? (persona inventada) | 0,798 | **0,828** | Pasa el umbral con 8 fragmentos: el modelo se llama para una persona que no existe. |
| EN8 | ¿Qué es el Departamento de Hidrología Lunar? (inventado) | 0,817 | **0,854** | Pasa el umbral con 8 (literal) y 16 (razonamiento) fragmentos. |
| EN9, EN10 | Negativos (¿Qué es obligatorio...?, ¿Cuál es la fecha...?) | 0,811, 0,813 | no aplica | Ni siquiera se intenta. |
| EN11, EN12 | ¿Qué es el Cibercrimen?, Háblame de Derecho Informático | 0,868, 0,880 (puesto 1) | no aplica | Ya funcionan: la primera búsqueda pasa. |

Lectura:

1. **La mejora real es menor que la anticipada en la spec.** De las tres personas, el segundo intento deja pasar el umbral en dos (S22-1 y S22-4), pero el documento esperado solo entra en una (Natalia Soto Solís) y solo en el modo con razonamiento. En Cubillo entran fragmentos de otro documento y en Obando no pasa nada. SC-001 se lee entonces: "de los dos casos cuya forma corta pasa el umbral, el documento esperado aparece en las fuentes cuando está dentro del límite de resultados del modo y sobre el umbral". Se medirá y se reportará, sin ajustar la spec.
2. **Las preguntas "háblame de..." ya pasan el umbral en la primera búsqueda** (puntajes de 0,84) pero con documentos ajenos (el de la persona está en el puesto 17 a 43): no es un problema de envoltura sino de que el umbral no separa (hallazgo de la feature 005). Esta opción no los toca.
3. **Riesgo para BUS-3 confirmado en los puntajes.** Una persona o un término inventado, reducido a su nombre, puntúa 0,828 y 0,854: más alto que varios casos legítimos. El segundo intento les entrega fragmentos al modelo, que debe responder "sin información". Es la razón de ser de EN7 y EN8 en la medición con respuestas: se verá si el modelo se contiene y cuánto cuesta cada llamada que antes no se hacía.
4. **Un falso positivo de las reglas encontrado y corregido al listar el conjunto de casos**: el caso A2 del MVP ("¿Quién fue designado coordinador...?") se reduciría a un fragmento de oración. Se agregó la guarda 5 de R4.

## R12. Medición con respuestas (2026-10-18)

Corridas `control8` (opción apagada) y `limpia` (encendida) sobre los 10 casos donde el segundo intento puede activarse o debe no activarse, ambos modos; ver la tabla y la lectura en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md). Resumen:

- 16 consultas con segundo intento, 12 con fragmentos sobre el umbral, 2 respuestas con el documento esperado (`S22-1` y `EN2`, razonamiento).
- 10 llamadas al modelo nuevas que terminaron en "sin información" (0,008 USD en total); ninguna respuesta inventada (`EN7` y `EN8`, 4 consultas).
- Se alcanzó con 0,021 USD: la medición reducida bastó porque, con la primera búsqueda aprobada, el camino es el mismo con la opción encendida o apagada.
- Variante no probada: un número de resultados mayor para el segundo intento (por ejemplo 16 en literal) traería el documento de Natalia Soto Solís (puesto 12), a costa de más ruido y costo. Quedaría como una medición propia si se decide seguir con la opción B en lugar del reranker.

