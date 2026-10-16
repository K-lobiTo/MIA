# Feature Specification: Mostrar solo las fuentes que aportaron a la respuesta

**Feature Branch**: `dev` (feature `006-fuentes-que-aportaron`, sin rama propia por decisión del usuario)

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "Fuentes que sí aportaron (feature 006, opción F de la sección 2.5 y requerimiento BUS-5 de docs/Definicion_Requerimientos_V3.md): hoy una respuesta de MIA lista como fuentes todos los fragmentos que se le pasaron al modelo, aunque no hayan servido. Según la línea base medida el 2026-10-15 (docs/LINEA_BASE_BUSQUEDA.md, 32 casos en producción) eso son en promedio 1,39 fuentes que no aportaron por consulta en modo literal y 2,69 en modo con razonamiento, con casos de 9 y 10 fuentes mostradas para 1 que de verdad sirvió. Lo que se quiere: que la respuesta muestre solo las fuentes que el modelo usó para responder, de modo que quien consulta pueda verificar la respuesta sin revisar documentos que no tienen que ver, sin llamadas adicionales a ningún modelo ni costo extra, validando las citas del modelo (que pueden estar mal), con un comportamiento seguro cuando no cita o cita mal, sin cambiar cuándo se responde \"sin información suficiente\", apagable por configuración y compatible con los clientes actuales."

Contexto: cuando MIA responde, la respuesta incluye la lista de fuentes (documentos y fragmentos) que la sustentan, y la Consulta administrativa la muestra para que el personal de Coordinación verifique lo que se afirma. Hoy esa lista es **todo lo que se le entregó al modelo**, no lo que el modelo usó. La línea base de la feature 005 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)) midió que, contra los documentos esperados de cada caso, sobran en promedio 1,39 fuentes por consulta en modo literal y 2,69 en modo con razonamiento, con casos de 9 y 10 fuentes mostradas para 1 que sirvió. Quien verifica tiene que revisar documentos que no tienen que ver con la respuesta, y la lista deja de ser una señal confiable de "de dónde salió esto". Esta feature es la opción F y el requerimiento BUS-5 de [Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md). No cambia qué se busca, qué pasa el umbral ni cuándo se responde "sin información".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver solo las fuentes que sustentan la respuesta (Priority: P1)

Una persona de Coordinación pregunta en la Consulta administrativa "¿Cuántas horas extraclase por semana tiene el curso Big Data para Negocios?". MIA responde "14 horas" y, en "Fuentes", muestra solo el programa del curso que contiene ese dato, no los otros cinco documentos que la búsqueda trajo por parecidos. Al expandir los fragmentos, ve únicamente los pasajes que el modelo usó para esa afirmación. Puede verificar la respuesta abriendo uno o dos documentos en vez de seis.

**Why this priority**: es el propósito de la feature (BUS-5) y lo que el personal nota: una lista de fuentes corta y pertinente da confianza; una lista larga con documentos ajenos la desprestigia.

**Independent Test**: correr los casos de la batería del MVP en los dos modos y comparar las fuentes mostradas con los documentos que cada caso declara que aportan: el promedio de fuentes sobrantes baja respecto a la línea base y el documento esperado de cada caso sigue apareciendo.

**Acceptance Scenarios**:

1. **Given** una pregunta cuya respuesta sale de un solo documento y a la que la búsqueda entregó varios documentos al modelo, **When** MIA responde, **Then** la lista de fuentes contiene ese documento y no los demás.
2. **Given** una respuesta que combina información de dos documentos (por ejemplo, el caso multi-dominio o el de las actas), **When** MIA responde, **Then** la lista incluye ambos y ningún otro.
3. **Given** una respuesta en modo con razonamiento, **When** MIA responde, **Then** la regla es la misma que en modo literal.
4. **Given** una respuesta, **When** se lee su texto, **Then** no aparecen marcas internas de cita (números entre corchetes u otras) ni texto de instrucciones: el texto se lee como hoy.
5. **Given** una respuesta con fuentes filtradas, **When** se compara con la misma pregunta sin el filtro, **Then** la información afirmada es la misma y solo cambia la lista de fuentes.

---

### User Story 2 - Nunca quedarse sin fuente verificable si el modelo no cita bien (Priority: P1)

El modelo a veces no cita nada, cita un número que no existe, o cita solo una parte de lo que usó. Cuando eso pasa, MIA no deja la respuesta sin fuentes ni muestra una lista engañosa: aplica una regla definida y segura. Si las citas son todas inválidas o no hay ninguna, muestra las fuentes como hoy (todo lo que se le entregó al modelo), de modo que la persona sigue teniendo de dónde verificar. Si hay citas válidas y otras inválidas, muestra solo las válidas.

**Why this priority**: una respuesta sin fuente verificable es un defecto según el principio V de la constitución (trazabilidad). Las citas de un modelo pueden estar mal (el benchmark ALCE halló que incluso los mejores modelos dejan citas sin respaldo completo), así que el filtrado no puede confiar ciegamente en ellas.

**Independent Test**: simular respuestas del modelo sin citas, con citas inexistentes y con una mezcla de válidas e inválidas, y comprobar para cada una que la lista de fuentes sigue la regla y nunca queda vacía en una respuesta con contenido.

**Acceptance Scenarios**:

1. **Given** una respuesta del modelo sin ninguna cita, **When** MIA la procesa, **Then** muestra todas las fuentes que entregó al modelo (comportamiento actual) y la respuesta se marca internamente como "sin citas utilizables".
2. **Given** una respuesta que cita solo fragmentos que no existen entre los entregados, **When** MIA la procesa, **Then** hace lo mismo que sin citas.
3. **Given** una respuesta que cita algunos fragmentos que existen y otros que no, **When** MIA la procesa, **Then** muestra solo los que existen.
4. **Given** una respuesta que cita varias veces el mismo fragmento, **When** MIA la procesa, **Then** aparece una sola vez.
5. **Given** una respuesta "sin información suficiente", **When** MIA la procesa, **Then** no tiene fuentes, igual que hoy.

---

### User Story 3 - Poder apagarlo y volver al comportamiento anterior sin desplegar código (Priority: P2)

Quien opera MIA puede activar o desactivar el filtrado de fuentes con una variable de configuración, igual que las demás piezas del pipeline. Mientras no se decida lo contrario, el valor por defecto es el comportamiento actual (mostrar todas las fuentes). Se activa solo cuando la medición demuestra que mejora y no rompe nada, y se puede volver atrás cambiando la variable.

**Why this priority**: es la salvaguarda (BUS-6) que permite probarlo en producción con la opción de retroceder en minutos, sin redespliegue ni migración.

**Independent Test**: con la opción apagada, repetir la línea base y comprobar que la lista de fuentes de cada caso es idéntica a la de antes de la feature; con la opción encendida, comprobar que cambia como en la historia 1.

**Acceptance Scenarios**:

1. **Given** la configuración por defecto, **When** MIA responde, **Then** el comportamiento es idéntico al de antes de esta feature, incluidas las fuentes.
2. **Given** la opción encendida, **When** MIA responde, **Then** aplica el filtrado de las historias 1 y 2.
3. **Given** la opción encendida, **When** quien opera la apaga y reinicia el servicio, **Then** vuelve al comportamiento anterior sin cambios de código ni de base de datos.
4. **Given** un valor de configuración inválido, **When** el servicio arranca o responde, **Then** usa el comportamiento anterior y deja un aviso en el registro en vez de fallar.

---

### User Story 4 - Comprobar con la línea base que mejora sin romper nada (Priority: P2)

Quien opera MIA repite la medición de la feature 005 con la opción encendida y la compara con la línea base: las fuentes sobrantes bajan, los 19 casos de la batería del MVP siguen respondiendo bien y citando su documento esperado, las respuestas "sin información" son las mismas, y el costo y la latencia por consulta no suben de forma apreciable.

**Why this priority**: es la prueba de que se cumplen BUS-3, BUS-4 y BUS-5 antes de activar la opción por defecto; sin ella no hay base para decidir.

**Independent Test**: correr `puntajes` no hace falta (la recuperación no cambia); correr `respuestas` en ambos modos con la opción encendida y `comparar` contra la corrida `base`, y leer el resultado contra los criterios de éxito.

**Acceptance Scenarios**:

1. **Given** la corrida de referencia `base` y una corrida con la opción encendida, **When** se comparan, **Then** el resultado de cada caso (respondió, sin información, correcto) es el mismo, salvo diferencias explicadas por el comportamiento no determinista del modelo.
2. **Given** las dos corridas, **When** se comparan las fuentes mostradas, **Then** el promedio de fuentes sobrantes es menor en ambos modos.
3. **Given** las dos corridas, **When** se comparan el costo y la latencia, **Then** el costo medio por consulta y la latencia p50 no suben más de lo fijado en los criterios de éxito.
4. **Given** la corrida con la opción encendida, **When** se cuenta cuántas respuestas cayeron en la regla de seguridad (sin citas utilizables), **Then** la proporción está dentro de lo fijado en los criterios de éxito.

---

### Edge Cases

- El modelo cita un fragmento y su texto no tiene nada que ver con la afirmación: no se puede detectar sin otro modelo; el filtrado confía en lo que el modelo citó, siempre que exista entre los entregados. Se acepta ese límite y se mide con la batería.
- Dos pasajes consecutivos de un documento se unieron en uno antes de entregarse al modelo: la cita se resuelve contra los pasajes tal como se entregaron.
- El modelo escribe la cita en un formato inesperado (por ejemplo, con otro tipo de corchete o con texto): se trata como "sin cita válida" y rige la regla de seguridad.
- El modelo cita todos los fragmentos entregados: se muestran todos, que es correcto.
- La respuesta se corta por el límite de longitud antes de terminar las citas: se usan las que alcanzaron a escribirse; si no hay ninguna, rige la regla de seguridad.
- Un proveedor de modelo distinto devuelve las citas de otra manera: el filtrado debe funcionar igual con cualquier proveedor configurado, porque la lógica no depende del proveedor.
- Los clientes anteriores, como `scripts/pruebas_mvp.py`, solo leen la lista de fuentes: deben seguir funcionando con una lista más corta.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Con la opción encendida, la lista de fuentes de una respuesta debe contener únicamente los fragmentos (y, por tanto, los documentos) que el modelo indicó haber usado, siempre que esas indicaciones correspondan a fragmentos realmente entregados al modelo.
- **FR-002**: El modelo debe poder indicar qué fragmentos usó dentro de la misma respuesta que ya genera: la feature no debe agregar ninguna llamada a un modelo de lenguaje ni a otro servicio de pago por consulta.
- **FR-003**: Cada indicación de fuente del modelo debe validarse contra los fragmentos entregados; las indicaciones que no correspondan a ninguno se descartan.
- **FR-004**: Si tras validar no queda ninguna indicación utilizable, la lista de fuentes debe ser la de siempre (todos los fragmentos entregados al modelo). Una respuesta con contenido nunca debe quedar sin fuentes por causa del filtrado.
- **FR-005**: Una respuesta "sin información suficiente" no debe tener fuentes ni cambiar de resultado por esta feature.
- **FR-006**: El texto de la respuesta que ve la persona no debe contener marcas internas de cita ni residuos de las instrucciones adicionales; debe leerse como hoy.
- **FR-007**: La feature no debe alterar la búsqueda: los fragmentos que se entregan al modelo, su orden, el umbral de similitud y los criterios de "sin información" deben ser los mismos que antes.
- **FR-008**: Debe existir una opción de configuración, apagada por defecto, que encienda o apague el filtrado sin cambiar código ni base de datos; apagada, el comportamiento y la respuesta (incluida la lista de fuentes) deben ser idénticos a los de antes de la feature.
- **FR-009**: Un valor de configuración inválido debe tratarse como apagado y dejar un aviso en el registro, sin hacer fallar la consulta.
- **FR-010**: El filtrado debe funcionar igual en los dos modos de respuesta (literal y con razonamiento) y con cualquier proveedor de modelo configurado.
- **FR-011**: La respuesta de la API debe conservar su estructura actual (los clientes existentes no deben requerir cambios): la lista de fuentes mantiene sus campos, solo cambia su contenido.
- **FR-012**: El registro de la consulta (módulo Uso) debe guardar los documentos citados como hoy; con la opción encendida, los documentos del registro deben ser los de la lista filtrada, y debe quedar anotado cuándo se aplicó la regla de seguridad para poder medir con qué frecuencia ocurre.
- **FR-013**: Deben existir pruebas automáticas de la lógica de validación y de las reglas de las historias 1 y 2 (sin citas, citas inexistentes, mezcla, repetidas, sin información, texto limpio), sin llamar a ningún proveedor real.
- **FR-014**: La documentación debe describir la opción, su valor por defecto, cómo medir su efecto con la herramienta de la feature 005 y qué hacer si aumenta la regla de seguridad.

### Key Entities *(include if feature involves data)*

- **Fragmento entregado**: cada pasaje de documento que MIA entrega al modelo como contexto, identificado dentro de la consulta por un número de referencia, con su documento y dominio.
- **Cita del modelo**: la indicación que el modelo hace, dentro de su respuesta, de qué fragmento entregado usó; puede ser válida (corresponde a un fragmento entregado) o inválida.
- **Fuentes de la respuesta**: la lista de documentos y fragmentos que se muestra junto a la respuesta; con la opción apagada es todo lo entregado; encendida, son los citados y válidos, o todo lo entregado si no hay ninguno válido.
- **Marca de uso de la regla de seguridad**: indicador interno por consulta de que no hubo citas utilizables y se mostraron todas las fuentes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Con la opción encendida y el mismo conjunto de casos de la línea base, el promedio de fuentes que no aportaron por consulta baja al menos 50 % en cada modo (de 1,39 a 0,70 o menos en literal, y de 2,69 a 1,35 o menos en razonamiento).
- **SC-002**: Los 19 casos de la batería del MVP siguen respondiendo bien en los dos modos (como hoy) y cada caso que espera respuesta sigue mostrando el documento esperado entre sus fuentes.
- **SC-003**: Los casos que hoy responden "sin información" siguen respondiéndolo y los que hoy responden con contenido no pasan a "sin información" (diferencias atribuibles solo al comportamiento no determinista del modelo, que se confirman repitiendo el caso).
- **SC-004**: El costo medio por consulta de cada modo, medido con el módulo Uso, no sube más de 5 % respecto a la línea base (0,00074 USD en literal y 0,00624 USD en razonamiento), y los topes de gasto siguen operando.
- **SC-005**: La latencia p50 de cada modo no sube más de 10 % respecto a la línea base (1,7 s en literal y 3,4 s en razonamiento).
- **SC-006**: En la corrida de verificación, la regla de seguridad (sin citas utilizables) se aplica en no más del 10 % de las respuestas con contenido.
- **SC-007**: Ninguna respuesta con contenido queda sin fuentes en toda la corrida de verificación.
- **SC-008**: Con la opción apagada, repetir la línea base da la misma lista de fuentes por caso que antes de la feature (cero diferencias en documentos mostrados).
- **SC-009**: Una persona de Coordinación, ante tres respuestas filtradas al azar, puede identificar en cada una de qué documento sale la afirmación principal revisando solo las fuentes mostradas.

## Assumptions

- Quien opera MIA es una sola persona (el usuario), y quien consulta es el personal de Coordinación mediante la Consulta administrativa u otro artefacto.
- Las fuentes se identifican por documento y por pasaje (fragmento tal como se entrega al modelo, que puede haber unido fragmentos consecutivos); la Consulta ya muestra la lista de documentos y los pasajes expandibles, así que una lista más corta no requiere cambios de interfaz.
- Las marcas de cita no se muestran a la persona: el texto de la respuesta se presenta limpio. Mostrar referencias numeradas dentro del texto queda fuera de esta feature.
- El comportamiento por defecto sigue siendo el actual hasta que la medición de la historia 4 lo respalde; encenderlo en producción es una decisión posterior del usuario, fuera de esta feature.
- La verificación se hace con la herramienta de la feature 005 (`scripts/linea_base.py respuestas` y `comparar`) contra producción, con el mismo conjunto de 32 casos, un artefacto con acceso a los dos programas y un tope de gasto fijado antes de correr.
- Quedan fuera de esta feature: el segundo intento con pregunta limpia, el reranker, la búsqueda híbrida, el contexto por fragmento, la evaluación automática de si una cita respalda de verdad la afirmación con otro modelo, y cualquier cambio visual de la Consulta.
- El comportamiento del modelo no es del todo determinista: un caso que cambie de resultado entre corridas se repite antes de contarse como regresión.
