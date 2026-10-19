# Feature Specification: Línea base de la búsqueda de MIA

**Feature Branch**: `dev` (feature `005-linea-base-busqueda`, sin rama propia por decisión del usuario)

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "Línea base de la búsqueda (feature 005): armar un conjunto de casos de prueba de recuperación y medir con datos reales cómo se comporta hoy MIA, sin cambiar el producto. Casos: la batería de docs/PRUEBAS_MVP.md, los 2 que hoy fallan de la sección 2.2 de docs/Definicion_Requerimientos_V3.md (pregunta con nombre y apellidos, sigla frente a forma desarrollada), preguntas indirectas, siglas y preguntas sin respuesta. Medir los puntajes reales de similitud por caso (solo puntajes, nunca texto de fragmentos ni nombres reales de personas), qué fragmentos pasan el umbral, cuántas fuentes se muestran y cuáles aportaron, latencia y costo por consulta. Sirve de línea base para BUS-3 y para decidir las opciones de la sección 2.8 de V3 (puntos 3 y 5)."

Contexto: la versión 3 ([Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md)) quiere que MIA encuentre documentos aunque la pregunta tenga palabras de más o use siglas (BUS-1 a BUS-7). Hoy el diagnóstico sale de leer el código: **no se midió ningún puntaje real**. Antes de cambiar nada (citas por fragmento, segundo intento con pregunta limpia, reranker) hace falta saber cómo se comporta MIA hoy, para elegir con datos y para poder demostrar después que una mejora no rompió lo que ya funcionaba. Esta feature **no cambia el comportamiento del producto**: solo agrega casos de prueba y mediciones.

## Clarifications

### Session 2026-10-14

- Q: ¿Las mediciones pueden ejecutarse contra la base vectorial de producción? → A: Sí. El usuario indicó el 2026-10-15 que toda la información cargada se considera pública y se puede usar para pruebas, así que se mide directamente contra producción, sin copia local. La medición sigue siendo de solo lectura (no modifica datos) y la de respuestas respeta un tope de gasto. Esto reemplaza la respuesta del 2026-10-14 (copia local y producción solo para confirmar).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tener un conjunto de casos de prueba de búsqueda, versionado (Priority: P1)

Quien opera MIA arma un conjunto de casos de prueba que cubre lo que hoy funciona y lo que hoy falla: la batería existente de la prueba de aceptación del MVP, los dos casos que fallan (pregunta con nombre y apellidos completos, y pregunta con la forma desarrollada de una sigla), preguntas indirectas (que no repiten las palabras del documento), preguntas con siglas y preguntas cuya respuesta no está en ningún documento. Cada caso dice en qué dominios se pregunta, qué se espera (respuesta con cierto documento, o "sin información suficiente") y a qué categoría pertenece. El conjunto vive en el repositorio con las preguntas tal como se harían, incluidos los nombres reales que ya están en los documentos, porque la información cargada se considera pública para las pruebas.

**Why this priority**: sin casos no hay medición, y sin medición V3 sigue decidiendo por intuición. Es la base de las otras historias y de todos los criterios de aceptación de V3.

**Independent Test**: abrir el conjunto, comprobar que cada caso tiene dominios, pregunta, resultado esperado y categoría; y que las categorías pedidas están representadas.

**Acceptance Scenarios**:

1. **Given** el conjunto de casos, **When** se lista por categoría, **Then** aparecen al menos: batería existente del MVP, los 2 casos de la sección 2.2 de V3, preguntas indirectas, preguntas con siglas y preguntas sin respuesta en ningún dominio.
2. **Given** el conjunto, **When** se revisa un caso de la batería existente o uno de la sección 2.2, **Then** conserva su pregunta y su resultado esperado tal como están en PRUEBAS_MVP.md y V3, y su variante corta si la tiene.
3. **Given** un caso nuevo (indirecta, sigla o sin respuesta), **When** se agrega, **Then** declara los documentos que se espera que aporten (si espera respuesta), para poder medir fuentes sobrantes.
4. **Given** el conjunto, **When** se compara con la batería existente, **Then** cada caso de la batería está incluido con el mismo resultado esperado y puede identificarse por su id original.

---

### User Story 2 - Medir qué puntajes de similitud obtiene cada caso y qué pasa el umbral (Priority: P1)

Quien opera MIA corre una medición que, para cada caso, consulta la base vectorial igual que lo hace la API y registra, por fragmento candidato, el puntaje de similitud, su posición y si supera el umbral de similitud configurado (`QUERY_SIMILARITY_THRESHOLD`). Por caso resume cuántos fragmentos pasan, cuál es el mejor puntaje y de qué documento viene (por nombre de documento, nunca por su texto). Con eso se ve, por ejemplo, qué puntaje obtuvo "¿Quién es nombre y apellidos?" frente a solo el nombre, y qué distancia hay entre un caso que falla y el umbral.

**Why this priority**: es el dato que falta para decidir entre bajar el umbral, umbral por modo, segundo intento con pregunta limpia o reranker (opciones A a E de V3), y para saber si hay margen entre "respuestas buenas" y "sin respuesta" (BUS-3).

**Independent Test**: correr la medición sobre dos casos conocidos (uno que hoy responde bien y uno sin respuesta) y comprobar que el informe muestra, para cada uno, los puntajes ordenados, cuáles superan el umbral y que coincide con lo que la API decide (responder o "sin información").

**Acceptance Scenarios**:

1. **Given** un caso con respuesta, **When** se mide, **Then** el informe muestra los puntajes de los fragmentos candidatos, marca los que superan el umbral y nombra el documento de origen de cada uno .
2. **Given** un caso que hoy falla (pregunta completa), **When** se mide junto con su variante corta (solo el nombre, o la sigla), **Then** el informe muestra ambos puntajes lado a lado y la diferencia respecto al umbral.
3. **Given** una pregunta sin respuesta, **When** se mide, **Then** el informe muestra el mejor puntaje que obtiene, para saber cuánto margen hay bajo el umbral.
4. **Given** cualquier informe producido, **When** se revisa, **Then** no contiene el texto de los fragmentos ni el texto de las respuestas, solo ids de caso, puntajes, posiciones, números y nombres de documento.
5. **Given** que el umbral configurado cambia, **When** se repite la medición, **Then** el informe reporta cuántos casos cambiarían de resultado (responder o "sin información") para esos umbrales alternativos, sin tener que volver a consultar el modelo de lenguaje.

---

### User Story 3 - Medir la respuesta completa: fuentes mostradas, fuentes que aportaron, tiempo y costo (Priority: P2)

Quien opera MIA corre los casos contra la API como lo haría un artefacto y registra, por caso y por modo (literal y con razonamiento): si respondió o dijo "sin información", cuántas fuentes se mostraron, cuántas de ellas aportaron realmente a la respuesta, cuánto tardó y cuánto costó. "Aportó" lo decide la persona que revisa, que marca por caso los documentos que sí deberían aparecer. Así se obtiene la línea base de BUS-5 (mostrar solo lo que aportó), de latencia (contra los 3 s del modo literal y 5 s del modo con razonamiento actuales) y de costo por consulta (BUS-4), incluido el costo de una consulta que termina en "sin información".

**Why this priority**: da la línea contra la cual comparar citas por fragmento, reranker y segundo intento, pero depende de gasto en el proveedor de modelos y de revisión manual, por eso va después de los puntajes.

**Independent Test**: correr tres casos (con respuesta, sin respuesta y de la sección 2.2) en ambos modos y comprobar que el informe trae, para cada uno, respondió o no, fuentes mostradas y esperadas, tiempo y costo, y que el costo coincide con lo que registra el módulo Uso.

**Acceptance Scenarios**:

1. **Given** un caso con respuesta, **When** se corre en un modo, **Then** el informe registra fuentes mostradas, fuentes esperadas marcadas por la persona, cuántas sobran, tiempo total y costo.
2. **Given** un caso que termina en "sin información" sin llamar al modelo, **When** se corre, **Then** el informe registra tiempo y costo (cero de modelo) y que no se consultó al modelo.
3. **Given** la corrida de todo el conjunto, **When** termina, **Then** el informe resume por modo: casos correctos, casos que fallan, fuentes sobrantes promedio, latencia p50 y p95 y costo medio por consulta.
4. **Given** un tope de gasto definido para la corrida, **When** el gasto acumulado lo alcanza, **Then** la corrida se detiene con aviso y entrega el informe parcial.

---

### User Story 4 - Dejar una línea base comparable y las decisiones de V3 respondidas con datos (Priority: P2)

Con las mediciones de las historias 2 y 3 se escribe un informe de línea base (fecha, versión del código, conjunto de datos, umbral, modo) que se guarda en el repositorio y responde, con números, las decisiones 3 y 5 de la sección 2.8 de V3 y alimenta las otras (gasto aceptable, límites de memoria y latencia). El mismo conjunto y el mismo procedimiento se podrán repetir después de implementar cada mejora de V3 para compararla contra esta línea.

**Why this priority**: convierte la medición en una decisión y deja la vara para demostrar que una mejora no rompe nada; puede escribirse cuando las historias 2 y 3 ya tienen resultados.

**Independent Test**: leer el informe y comprobar que declara con qué código, datos y configuración se midió, que incluye los resultados por caso y el resumen, y que la sección 2.8 de V3 enlaza a él.

**Acceptance Scenarios**:

1. **Given** las corridas hechas, **When** se escribe el informe, **Then** incluye fecha, commit, umbral, modo, conjunto de datos, resultados por caso y resumen.
2. **Given** el informe, **When** se lee la sección 2.8 de V3, **Then** las decisiones 3 y 5 quedan marcadas como resueltas con enlace al informe, y las demás reciben los datos que necesitan.
3. **Given** una mejora futura, **When** se repite el procedimiento con el mismo conjunto, **Then** el nuevo resultado se puede comparar caso por caso con la línea base.

---

### Edge Cases

- Un caso espera "sin información" pero hoy responde con contenido (respuesta inventada): se registra como hallazgo, no como error de la medición.
- La batería existente incluye casos de aislamiento entre dominios (preguntar en el dominio equivocado): se conservan, y el informe distingue "sin información" por dominio equivocado de "sin información" por pregunta sin respuesta.
- El proveedor de modelos gratuito o de pago responde con error o se satura: se reintenta un número limitado de veces y el caso queda marcado como no concluyente, sin contarse como fallo de búsqueda.
- Un documento fue reemplazado o eliminado desde la última corrida: el informe registra la fecha de los datos y el caso puede quedar obsoleto; no se compara contra corridas de datos distintos sin aviso.
- La medición se corre contra una base con otro modelo de vectores o dimensiones: debe avisar y no mezclar puntajes de bases incompatibles.
- Las preguntas de la medición aparecen en el registro de Uso de producción y pueden distorsionar sus totales del día: la medición usa un artefacto existente, así que comparte con el uso real su tope diario de gasto y sus totales: la corrida registra los ids de sus consultas para poder excluirlas, se detiene si el artefacto alcanza su tope y muestra el gasto del día antes de empezar.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Debe existir un conjunto de casos de prueba de búsqueda versionado en el repositorio, con por caso: id, categoría, dominios consultados, pregunta, resultado esperado (respuesta con ciertos documentos, o "sin información suficiente") y, si aplica, la variante corta de la misma pregunta.
- **FR-002**: El conjunto debe incluir todos los casos de la batería de aceptación del MVP conservando sus ids y resultados esperados, los dos casos de la sección 2.2 de V3, preguntas indirectas, preguntas con siglas y preguntas sin respuesta en ningún dominio.
- **FR-003**: Los archivos versionados no deben contener texto de documentos (ni fragmentos ni respuestas completas); las preguntas y los nombres de documento sí pueden contener nombres reales, porque la información cargada se considera pública para las pruebas.
- **FR-004**: Debe existir una medición de puntajes que, por caso, consulte la base vectorial con la misma lógica de búsqueda que la API (mismos vectores de la pregunta, mismos dominios y mismo número de candidatos por modo) y registre por fragmento candidato: posición, puntaje, documento de origen (por nombre) y si supera el umbral configurado.
- **FR-005**: La medición de puntajes debe ser de solo lectura: no debe crear, modificar ni borrar datos de la base vectorial ni de la base de uso, ni cambiar la configuración del producto.
- **FR-006**: Las salidas de la medición (consola, archivos, informes) no deben incluir el texto de los fragmentos ni el de las respuestas; solo ids de caso, puntajes, posiciones, números y nombres de documento. No debe existir una opción que los imprima: no hace falta para medir y evita llenar los informes de texto que no se necesita.
- **FR-007**: La medición de puntajes debe poder reportar, para varios umbrales alternativos, qué casos cambiarían de resultado (responder o "sin información"), sin volver a consultar el modelo de lenguaje.
- **FR-008**: Para los casos con variante corta, el informe debe mostrar pregunta completa y variante corta lado a lado, con el mejor puntaje de cada una y su distancia al umbral.
- **FR-009**: Debe existir una medición de la respuesta completa que corra los casos contra la API como lo haría un artefacto, en los dos modos (literal y con razonamiento), y registre por caso: respondió o "sin información", fuentes mostradas, fuentes esperadas, fuentes sobrantes, tiempo total y costo.
- **FR-010**: Las fuentes esperadas por caso las marca una persona en el conjunto de casos; la medición no debe inferir por sí misma qué "aportó".
- **FR-011**: La medición de la respuesta completa debe respetar un tope de gasto definido por corrida y detenerse con informe parcial al alcanzarlo.
- **FR-012**: El costo y el tiempo registrados por caso deben ser consistentes con lo que muestra el módulo Uso para la misma consulta.
- **FR-013**: Los errores del proveedor de modelos deben reintentarse un número limitado de veces y, si persisten, marcar el caso como no concluyente sin contarlo como fallo de búsqueda.
- **FR-014**: Cada corrida debe registrar fecha, commit del código, umbral, modo, número de candidatos y una identificación de los datos consultados (por ejemplo, conteo de fragmentos por dominio) para poder comparar corridas.
- **FR-015**: Debe existir un informe de línea base en `docs/` que resuma resultados por caso y totales por modo (correctos, fallidos, fuentes sobrantes promedio, latencia p50 y p95, costo medio por consulta), y que responda las decisiones 3 y 5 de la sección 2.8 de V3 y enlace a ellas.
- **FR-016**: Esta feature no debe modificar el comportamiento de la API, la Consulta ni el Panel; no debe cambiar la configuración por defecto ni agregar migraciones de base de datos.
- **FR-017**: El procedimiento debe poder repetirse con el mismo conjunto después de cada mejora de V3, produciendo un resultado comparable caso por caso con la línea base.

### Key Entities *(include if feature involves data)*

- **Caso de prueba de búsqueda**: pregunta, dominios, categoría, resultado esperado, documentos esperados como fuentes y, opcionalmente, variante corta.
- **Medición de puntajes de un caso**: para una corrida, la lista de candidatos con posición, puntaje, documento y si pasa el umbral; resumen (mejor puntaje, cuántos pasan).
- **Medición de respuesta de un caso**: resultado (respondió, "sin información" o no concluyente), fuentes mostradas y esperadas, tiempo, costo, modo.
- **Corrida**: conjunto de mediciones con su contexto (fecha, commit, umbral, modo, identificación de datos) y resumen.
- **Informe de línea base**: documento versionado que resume una corrida de referencia y responde decisiones de V3.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los casos de la batería existente del MVP están en el conjunto con su id original, y el conjunto cubre las cinco categorías pedidas (batería, casos de 2.2, indirectas, siglas, sin respuesta) con al menos tres casos nuevos en cada una de las tres últimas.
- **SC-002**: Para los dos casos de la sección 2.2, el informe muestra el puntaje de la pregunta completa, el de la variante corta y su distancia al umbral, de modo que se puede afirmar con datos si la causa es el umbral.
- **SC-003**: Para todas las preguntas sin respuesta del conjunto (incluidas las de aislamiento de dominio, que se reportan también por separado) se conoce el mejor puntaje obtenido, de modo que se puede decir con datos cuánto se puede bajar el umbral sin que dejen de dar "sin información" (BUS-3).
- **SC-004**: Ningún archivo producido por la medición (salida local e informe versionado) contiene texto de fragmentos ni de respuestas; una revisión de una muestra de ellos lo confirma.
- **SC-005**: Una corrida completa de puntajes termina en menos de 10 minutos y no consume tokens del proveedor de modelos.
- **SC-006**: Una corrida completa de respuestas de ambos modos queda dentro del tope de gasto fijado antes de correrla, y la suma de costos del informe coincide con el aumento del total del módulo Uso para ese artefacto durante la corrida (diferencia menor a 5 %), contrastado además una vez con el detalle de gasto del proveedor de modelos.
- **SC-007**: Repetir la corrida con el mismo código y los mismos datos da los mismos puntajes (diferencia menor a 0,001) y el mismo resultado de responder o "sin información" en todos los casos.
- **SC-008**: Las decisiones 3 y 5 de la sección 2.8 de V3 quedan resueltas con enlace al informe, y las otras tres reciben los números que necesitan para decidirse.

## Assumptions

- Quien opera MIA es una sola persona (el usuario), que además marca las fuentes esperadas de cada caso y autoriza el gasto de las corridas.
- "La batería existente" es la que corre `scripts/pruebas_mvp.py` según [PRUEBAS_MVP.md](../../docs/PRUEBAS_MVP.md); sus ids son A, U, P, K, CU, G, N, X e I. Tiene 19 casos: los "15 casos" de V3 son los que esperan respuesta (14 más el multi-dominio `X1`), y los otros 4 esperan "sin información" (`N1` y los de aislamiento `I1` a `I3`).
- Los datos consultados son los de los dominios ya cargados (actas, currículum y proyectos de graduación de los dos programas); la medición no ingesta ni cambia documentos.
- Para consultar la base vectorial igual que la API se reutilizan los mismos componentes de embeddings y almacenamiento del producto, sin modificarlos.
- La medición de respuestas completas usa una clave de artefacto con acceso a los dos programas, como hoy la batería del MVP.
- Se mide primero el modo literal y luego el de razonamiento; el de razonamiento puede ser más caro, por lo que el tope de gasto se fija antes de cada corrida.
- Quedan fuera de esta feature: cualquier mejora de la búsqueda (umbral, segundo intento, reranker, búsqueda híbrida, citas por fragmento), la evaluación automática de "calidad de la respuesta" con un modelo juez y los cambios de interfaz.
- Las mediciones se hacen directamente contra producción (aclaración del 2026-10-15). La medición de puntajes es de solo lectura; la de respuestas se limita con un tope de gasto. Las preguntas de las corridas quedan en el registro de Uso de producción, como cualquier consulta.
