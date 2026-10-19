# Feature Specification: Pregunta limpia (segundo intento de búsqueda)

**Feature Branch**: `dev` (feature `008-pregunta-limpia`, sin rama propia por decisión del usuario)

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "Pregunta limpia (opción B de docs/Definicion_Requerimientos_V3.md, secciones 2.5 y 2.6; requerimientos BUS-1, BUS-3, BUS-6, BUS-7). Cuando la búsqueda normal no deja ningún fragmento sobre el umbral de similitud, la API hace un único segundo intento con la pregunta \"limpia\", por reglas de texto y sin ningún modelo de lenguaje: se quita la envoltura de preguntas de identificación o descripción (\"¿Quién es X?\", \"¿Qué es el X?\", \"háblame de X\", \"dame información sobre X\", \"¿Qué se sabe de X?\", cortesías como \"¿me puedes decir...?\") y se busca solo X. Con guardas para no estropear nada, apagable por configuración (apagada por defecto), registrada en el módulo Uso y sin migraciones. Se mide con la herramienta de la feature 005, con corrida de control y con tope de gasto autorizado."

Contexto: la Consulta administrativa descarta los fragmentos cuya similitud con la pregunta queda bajo el umbral configurado y, si no queda ninguno, responde "sin información suficiente" sin llamar al modelo. Una pregunta con envoltura ("¿Quién es Natalia Soto Solís?") se parece menos al texto de un documento que el nombre solo, y por eso a veces cae bajo el umbral aunque el documento exista. Medido el 2026-10-14 en producción (feature 005, [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)): con nombre y apellidos completos tres personas puntúan 0,798, 0,775 y 0,802 (bajo el umbral de 0,82), mientras que solo con el nombre puntúan 0,833, 0,807 y 0,827. Dos de las tres pasarían el umbral; la tercera sigue bajo él. Esta feature es la opción B del documento de requerimientos de la versión 3 (BUS-1, BUS-3, BUS-6, BUS-7): reglas de texto, sin modelo de lenguaje, solo cuando la primera búsqueda no encuentra nada.

Límites conocidos desde la medición, que esta feature no pretende resolver: las siglas (la pregunta "¿qué es el TFG?" frente a "trabajo final de graduación" es un problema de vocabulario, no de envoltura; lo cubren el reranker o la búsqueda híbrida), y los casos en que el documento correcto queda más allá del número de resultados que la búsqueda trae (en una de las tres personas, con el nombre solo, el documento aparece en el puesto 12 y el modo literal trae 8).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar a una persona o un término preguntando "¿Quién es X?" o "¿Qué es X?" (Priority: P1)

Una persona de Coordinación escribe "¿Quién es Natalia Soto Solís?" o "¿Qué se sabe de Cibercrimen?". La primera búsqueda no deja ningún fragmento sobre el umbral. MIA repite la búsqueda una sola vez con la pregunta reducida a lo que se busca ("Natalia Soto Solís", "Cibercrimen") y, si aparecen fragmentos sobre el umbral, el modelo responde con ellos. La persona recibe la respuesta basada en el documento en lugar de "sin información suficiente".

**Why this priority**: es el caso de uso que motivó la opción B y el único en el que la envoltura de la pregunta, no el contenido, impide encontrar un documento que existe.

**Independent Test**: con la opción encendida, hacer las preguntas de identificación de los casos S22-1, S22-3 y S22-4 de la línea base y comprobar que las que la variante corta ya hace pasar el umbral dejan de responder "sin información", citando el documento esperado.

**Acceptance Scenarios**:

1. **Given** una pregunta de identificación con nombre y apellidos cuya forma corta pasa el umbral y cuya forma larga no, **When** se consulta con la opción encendida, **Then** la respuesta se basa en el documento de esa persona y no es "sin información".
2. **Given** las formas de envoltura "quién es", "qué es", "qué son", "háblame de", "cuéntame sobre", "dame información sobre", "qué se sabe de", "qué sabes de", con o sin tildes, con o sin signos de interrogación y exclamación, y con mayúsculas o minúsculas cualesquiera, **When** la primera búsqueda no deja nada sobre el umbral, **Then** la pregunta se reduce a lo que sigue a la envoltura y se repite la búsqueda.
3. **Given** una cortesía delante de la envoltura ("¿Me puedes decir quién es X?", "Por favor, dime qué es X", "Quisiera saber qué es X"), **When** se reduce la pregunta, **Then** se quita primero la cortesía y luego la envoltura, y queda solo X.
4. **Given** una pregunta que ya pasa el umbral en la primera búsqueda, **When** se consulta con la opción encendida, **Then** no hay segundo intento y la consulta es idéntica a la de hoy.
5. **Given** una pregunta de identificación sobre algo que no está en los documentos, **When** el segundo intento tampoco deja nada sobre el umbral, **Then** la respuesta es "sin información suficiente" sin llamar al modelo, como hoy.

---

### User Story 2 - No tocar las preguntas que no son de identificación ni inventar respuestas (Priority: P1)

Una pregunta como "¿Cuántos créditos tiene el curso X?" o "¿Qué requisitos tiene el curso X?" depende de todas sus palabras, no solo del nombre. Si la primera búsqueda no la encuentra, MIA no la reduce a "X" para no traer documentos que hablan de X pero no responden lo preguntado. Lo mismo para una pregunta que, al quitarle la envoltura, queda demasiado corta o igual que antes. Y cuando los documentos de verdad no tienen la información, la respuesta sigue siendo "sin información suficiente": el segundo intento no aumenta de forma notable las respuestas inventadas.

**Why this priority**: es la salvaguarda de la opción (BUS-3). Una reformulación demasiado agresiva trae documentos que parecen relevantes y empuja al modelo a responder lo que no está.

**Independent Test**: tabla de pruebas con preguntas que no deben reformularse (créditos, horas, requisitos, fechas, "¿Cuántos...?", "¿Cómo...?", "¿Por qué...?") y con resultados que quedan con menos de 3 caracteres o iguales a la pregunta; y, en la medición, los casos de la batería del MVP cuya respuesta correcta es "sin información" siguen respondiéndola.

**Acceptance Scenarios**:

1. **Given** una pregunta que no empieza con ninguna de las formas de identificación o descripción, **When** la primera búsqueda no encuentra nada, **Then** no hay segundo intento.
2. **Given** una pregunta de identificación cuyo resultado tras quitar la envoltura tiene menos de 3 caracteres o es igual a la pregunta, **When** se evalúa, **Then** no hay segundo intento.
3. **Given** una pregunta que empieza con una de las formas pero pide un dato concreto de lo que sigue ("¿Cuál es el costo del curso X?", "¿Qué es lo que establece el reglamento sobre las becas?"), **When** se evalúa, **Then** no se reformula, porque quitar la envoltura le quitaría el sentido a la pregunta. Dónde está el límite entre "quién es X" y "cuál es el dato de X" se fija en la lista de formas del plan y se prueba con casos negativos.
4. **Given** cualquier consulta, **When** se hace el segundo intento, **Then** ocurre como máximo una vez y no se encadenan reformulaciones.
5. **Given** los casos de la batería del MVP cuya respuesta correcta es "sin información", **When** se miden con la opción encendida, **Then** siguen respondiendo "sin información".

---

### User Story 3 - Poder apagarlo, y saber cuántas veces se usó y si ayudó (Priority: P2)

Quien opera MIA enciende o apaga el segundo intento con una variable de configuración, sin desplegar código ni migrar la base; por defecto está apagado y el comportamiento es el de hoy. Cuando está encendido, el registro de consultas del módulo Uso anota, para cada consulta que tuvo segundo intento, que se usó la reformulación y con qué texto, tanto si el segundo intento encontró fragmentos como si no, para poder contar cuántas veces ayudó y cuántas no.

**Why this priority**: es la salvaguarda (BUS-6) para probar en producción y volver atrás en minutos, y la fuente de datos para decidir si conviene conservar la opción o pasar a una solución de fondo.

**Independent Test**: con la opción apagada, repetir la línea base y comprobar que las respuestas y las notas de Uso son las de antes; encenderla y comprobar que solo cambian las consultas con segundo intento, y que cada una deja su nota en Uso.

**Acceptance Scenarios**:

1. **Given** la configuración por defecto, **When** MIA responde, **Then** el comportamiento, el costo, las fuentes y el registro son idénticos a los de antes de la feature.
2. **Given** la opción encendida y una consulta con segundo intento, **When** se registra en Uso, **Then** queda anotado que se usó la reformulación y el texto buscado, sin importar si el segundo intento encontró fragmentos o no.
3. **Given** un valor inválido en la variable de configuración, **When** el servicio arranca o responde, **Then** usa el comportamiento anterior (apagado) y deja un aviso en el registro, sin fallar.
4. **Given** una consulta con segundo intento que encontró fragmentos, **When** el modelo responde, **Then** la consulta cuesta una sola llamada al modelo (la de siempre): el segundo intento no agrega ninguna llamada a OpenRouter.
5. **Given** que se vuelve a la versión etiquetada `prototipo-v2-estable`, **When** se leen los registros de consultas hechos con esta feature, **Then** se leen sin errores (sin cambios en la estructura de la base).

---

### User Story 4 - Medir cuánto mejora y que no rompe nada (Priority: P2)

Quien opera MIA agrega al conjunto de casos de la feature 005 las formas de envoltura que hoy faltan (varias redacciones de identificación y descripción para las mismas personas y términos) y los casos negativos, y repite la medición con la herramienta de la 005. El informe cuenta cuántas consultas tuvieron segundo intento, cuántas pasaron de "sin información" a respuesta con el documento esperado, y compara costo y latencia contra la línea base y contra una corrida de control con la opción apagada.

**Why this priority**: es la prueba de que la opción hace lo que se esperaba y de que no empeora los casos que ya funcionan.

**Independent Test**: correr los puntajes y las respuestas con la opción apagada y encendida sobre los casos nuevos y comparar con la herramienta; leer en el informe el número de segundos intentos, cuántos ayudaron y los cambios de resultado.

**Acceptance Scenarios**:

1. **Given** el conjunto ampliado de casos, **When** se mide con la opción apagada, **Then** el informe muestra cuáles preguntas de identificación hoy responden "sin información" (la línea base del problema).
2. **Given** la misma medición con la opción encendida, **When** se compara, **Then** el informe muestra qué casos pasaron a respuesta con el documento esperado, y que ninguno de los demás cambió de resultado de forma atribuible a la opción.
3. **Given** las dos corridas, **When** se comparan, **Then** el informe cuenta las consultas con segundo intento y, de ellas, cuántas pasaron el umbral.
4. **Given** los 19 casos de la batería del MVP, **When** se comparan con la línea base, **Then** ninguno empeora.

---

### Edge Cases

- La reformulación deja solo una palabra común ("¿Qué es el curso?" queda "curso"): el resultado es válido por longitud pero trae documentos de todo tipo. Se acepta que pase el umbral y que el modelo decida con lo que reciba; la medición con los casos negativos debe mostrar que no hay respuestas inventadas de más.
- La pregunta lleva varias oraciones o más de una pregunta ("¿Quién es X? ¿Y cuántos créditos tiene Y?"): solo se reduce si la pregunta completa es una sola pregunta de identificación; si no, no hay segundo intento.
- La pregunta empieza con una cortesía pero el resto no es de identificación ("Por favor, ¿cuántos créditos tiene X?"): no hay segundo intento.
- La pregunta está en mayúsculas o sin tildes ni signos ("QUIEN ES NATALIA SOTO"): se reconoce igual, y el texto que se busca conserva la escritura original de lo que sigue a la envoltura.
- La pregunta no está en español: no hay segundo intento (las reglas son para español).
- El segundo intento deja fragmentos sobre el umbral pero de otro dominio al que el artefacto puede ver: el filtro de dominios aplica igual que en la primera búsqueda.
- El segundo intento deja más fragmentos de los que el modo trae normalmente: se respeta el mismo número de resultados que el modo configura.
- El tope de gasto diario ya está alcanzado: se evalúa antes de cualquier búsqueda, como hoy; el segundo intento no se hace si la consulta se rechaza.
- La opción está encendida pero la primera búsqueda falla por error del servicio de vectores: el error es el de hoy; el segundo intento no oculta fallas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Si la primera búsqueda de una consulta no deja ningún fragmento sobre el umbral de similitud y la opción está encendida, MIA debe hacer un único segundo intento con la pregunta reducida a lo que se busca, y continuar la consulta con los fragmentos de ese segundo intento si alguno pasa el umbral.
- **FR-002**: La reducción debe hacerse solo con reglas de texto, sin llamar a ningún modelo de lenguaje; el segundo intento no puede agregar ninguna llamada a OpenRouter. Si el segundo intento deja fragmentos, el modelo responde con ellos (la única llamada al modelo de la consulta); si no deja ninguno, la respuesta es "sin información suficiente" sin llamar al modelo, como hoy.
- **FR-003**: Debe reducirse únicamente las preguntas de identificación o descripción: las que preguntan quién es o qué es algo ("quién(es) es/son/era/fue", "qué es/son/significa"; "cuál es" queda fuera porque casi siempre pide un dato de algo, como en "¿Cuál es el costo del curso X?"), las que piden hablar de algo ("háblame de", "cuéntame sobre", "qué sabes/se sabe de/sobre"), las que piden información ("dame información/datos/detalles sobre/acerca de") y las cortesías que pueden anteceder a cualquiera de ellas ("por favor", "me puedes/podrías decir/explicar/indicar", "dime", "quiero/necesito/quisiera saber"). La lista exacta de formas se fija en el plan y es ampliable.
- **FR-004**: Antes de comparar con las formas, MIA debe normalizar la pregunta: quitar los signos de apertura y cierre de interrogación y exclamación, espacios sobrantes, y comparar sin distinguir mayúsculas ni tildes. El texto que queda como búsqueda debe conservar la escritura original (mayúsculas y tildes) de lo que se busca.
- **FR-005**: MIA no debe hacer el segundo intento cuando ninguna forma aplica (por ejemplo, "¿Cuántos créditos tiene X?", "¿Cómo se aprueba el curso?", "¿Qué requisitos tiene X?"), cuando el resultado de la reducción tiene menos de 3 caracteres, o cuando es igual a la pregunta original una vez normalizada.
- **FR-006**: El segundo intento debe ocurrir como máximo una vez por consulta, solo si la primera búsqueda no dejó nada sobre el umbral; no hay encadenamiento de reformulaciones ni un tercer intento.
- **FR-007**: El segundo intento debe usar los mismos dominios permitidos, el mismo umbral y el mismo número de resultados que la primera búsqueda del modo de la consulta; la construcción del contexto, las citas de la feature 006, el contexto completo y el reintento por corte de la feature 007 funcionan igual con los fragmentos del segundo intento.
- **FR-008**: La opción debe poder encenderse y apagarse por configuración, sin cambiar código ni base de datos, con un valor de texto de encendido y apagado; por defecto está apagada y el comportamiento es el de antes de la feature. Un valor inválido debe tratarse como apagado y dejar un aviso (una vez) en el registro del servidor, sin hacer fallar el arranque ni la consulta.
- **FR-009**: Cuando una consulta tuvo segundo intento, el registro de consultas del módulo Uso debe anotar que se usó la reformulación y el texto buscado, tanto si el segundo intento encontró fragmentos como si no. Esta anotación debe convivir con las demás notas del registro (feature 006 y 007) y no requiere cambios en la estructura de la base de datos, de modo que volver a la versión `prototipo-v2-estable` siga siendo posible.
- **FR-010**: Con la opción apagada, la búsqueda, el contexto, la respuesta, las fuentes, el costo y el registro deben ser idénticos a los de antes de la feature.
- **FR-011**: Con la opción encendida, una consulta cuya primera búsqueda ya pasó el umbral debe ser idéntica a la de hoy (mismo contexto, mismo costo, misma latencia dentro del ruido de medición).
- **FR-012**: La respuesta de la API conserva su estructura; el segundo intento no es visible para quien consulta salvo por su efecto (que ahora hay respuesta). No se requieren migraciones ni reindexar los documentos.
- **FR-013**: La herramienta de la feature 005 debe admitir casos con varias redacciones de la misma pregunta de identificación y casos negativos, y registrar por consulta si hubo segundo intento y con qué texto, resumirlo por modo y comparar corridas con y sin la opción.
- **FR-014**: Deben existir pruebas automáticas en tabla de las reglas de reducción (ejemplos de identificación, descripción, cortesías, con y sin tildes, con y sin signos, mayúsculas y minúsculas), de las guardas (menos de 3 caracteres, igual a la pregunta, ningún patrón, un solo intento) y de casos negativos, y de la integración con la consulta (con y sin la opción, con segundo intento que encuentra y que no encuentra), sin llamar a proveedores reales; y la documentación debe describir la opción, cómo encenderla y cómo medir su efecto.

### Key Entities *(include if feature involves data)*

- **Pregunta limpia**: el texto reducido a lo que se busca, obtenido por reglas de texto a partir de una pregunta de identificación o descripción; solo existe para el segundo intento y no se le muestra a quien consulta.
- **Segundo intento**: la repetición única de la búsqueda con la pregunta limpia, cuando la primera búsqueda no dejó nada sobre el umbral.
- **Nota de pregunta limpia**: la anotación del registro de Uso que indica que se usó la pregunta limpia y con qué texto.
- **Caso de envoltura**: un caso de la herramienta de medición que redacta de varias maneras la misma pregunta de identificación, con el documento esperado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: De los tres casos de personas de la línea base (S22-1, S22-3, S22-4), los dos cuya forma corta pasa el umbral de similitud responden con el documento esperado cuando se preguntan con la forma "¿Quién es ...?" y la opción encendida; el tercero (cuya forma corta sigue bajo el umbral) se reporta aparte y no cuenta contra el criterio, porque el problema no es la envoltura.
- **SC-002**: En el conjunto ampliado, al menos el 90 % de las formas de envoltura de las preguntas de identificación de los casos anteriores (cada forma con y sin tildes y signos) se reducen al texto esperado (medido en las pruebas unitarias en tabla).
- **SC-003**: El 100 % de las preguntas negativas de la tabla de pruebas (créditos, horas, requisitos, fechas, cómo, por qué, preguntas compuestas) quedan sin reformular.
- **SC-004**: Los 19 casos de la batería del MVP siguen respondiendo igual: ninguno empeora, y los que hoy responden "sin información" porque de verdad no hay información siguen haciéndolo (BUS-3).
- **SC-005**: Con la opción apagada, el texto, las fuentes y las notas de Uso de cada caso son los de la línea base (sin diferencias atribuibles a la feature).
- **SC-006**: Las consultas que no necesitan segundo intento no cambian de costo ni de latencia por encima del ruido medido en la corrida de control; las que lo necesitan suman a su latencia el tiempo de una búsqueda más, menos de 1 segundo adicional, y ningún costo adicional en llamadas al modelo.
- **SC-007**: Ninguna consulta hace más de un segundo intento (verificable en el registro de Uso).
- **SC-008**: El informe de la medición muestra, con la opción encendida, cuántas consultas tuvieron segundo intento y cuántas de ellas pasaron el umbral; el tamaño de la mejora queda documentado en la línea base con sus límites (siglas y documentos más allá del número de resultados).

## Assumptions

- Quien opera MIA es una sola persona (el usuario); quien consulta es el personal de Coordinación mediante la Consulta administrativa.
- Las preguntas del personal están en español; las reglas no pretenden cubrir otros idiomas.
- El comportamiento por defecto sigue siendo el actual hasta que la medición respalde encender la opción; encenderla en producción es una decisión posterior del usuario, fuera de esta feature.
- Se mantiene la nota de reformulación en el campo de motivo del registro de consultas (el mismo mecanismo de las notas de las features 006 y 007), no en una columna nueva; la redacción final de la nota se decide en el plan.
- La reducción de preguntas se limita a la forma de la pregunta; no interpreta nombres propios ni busca sinónimos o siglas (eso es de la búsqueda híbrida o del reranker).
- La lista de formas parte de las que propone la sección 2.5 del documento de requerimientos de la versión 3 y se ajusta con las preguntas reales del personal cuando existan; el plan fija la lista inicial.
- La verificación usa la herramienta de la feature 005 contra producción, con un artefacto con acceso a los dominios de las personas y de la batería del MVP, un tope de gasto fijado y autorizado antes de correr, y una corrida de control con la opción apagada. El segundo intento no agrega costo de modelo, así que el gasto de la medición es el de las respuestas que ahora se generan.
- El comportamiento del modelo no es del todo determinista: un caso que cambie de resultado entre corridas se repite antes de contarse como regresión.
- Quedan fuera de esta feature: el reranker local (opción E), la búsqueda híbrida (opción D), el contexto por fragmento (opción G), bajar el umbral (opción A) o tener umbrales por modo (opción C), las siglas, reformular con un modelo de lenguaje, y cualquier cambio visual de la Consulta.
