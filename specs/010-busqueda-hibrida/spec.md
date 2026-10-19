# Feature Specification: Búsqueda híbrida (encontrar nombres y siglas por coincidencia de palabras)

**Feature Branch**: `dev` (feature `010-busqueda-hibrida`, sin rama propia por decisión del usuario)

**Created**: 2026-10-19

**Status**: Draft

**Input**: User description: "Feature 010: búsqueda híbrida (opción D de docs/Definicion_Requerimientos_V3.md) para nombres propios y siglas. Objetivo: que preguntas sobre un nombre propio, una sigla (TFG, MGTI) o un término que aparece literalmente en los documentos encuentren esos documentos aunque el coseno de e5-small no los ponga entre los primeros (BUS-1 y BUS-2), combinando la búsqueda por vectores con una búsqueda léxica (por palabras) y fusionando resultados. Debe poder apagarse por variable de entorno (apagada por defecto, BUS-6), no llamar a un modelo de lenguaje (sin costo de tokens), caber en los límites del entorno gratuito (RAM de la API bajo 512 MB, dentro de los 5 USD de Railway), no aumentar las respuestas inventadas (BUS-3) y medirse con scripts/linea_base.py sobre scripts/datos/casos_busqueda.json. Casos que debe resolver: Joseph Obando, líneas de TFG, siglas TFG y MGTI, y la forma desarrollada contra la sigla (S22-3, S22-4). Parte del estado dejado por las features 005 a 009 (reranker local queda apagado y puede combinarse después)."

Contexto: la Consulta administrativa busca por *significado*: convierte la pregunta en un vector y trae los 8 fragmentos más parecidos (16 con razonamiento), y descarta los que no llegan a un umbral de similitud (0,82). Eso funciona cuando la pregunta describe un tema, y falla cuando la pregunta contiene una **palabra exacta** que el modelo de vectores no distingue: un nombre propio, una sigla o un término técnico. Las features 005 a 009 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)) midieron el problema y probaron tres remedios parciales (pregunta limpia, reranker local, fuentes citadas). Lo que queda sin resolver es de **vocabulario**, no de reordenamiento:

1. **La sigla y su forma desarrollada no se reconocen como lo mismo.** "¿Qué líneas de trabajo final de graduación ofrece la maestría?" no trae entre sus 50 primeros candidatos el documento "Líneas de TFG" (`S22-2`); con la sigla sola ("TFG") ese documento sube al puesto 2. "MGTI" no trae el "Plan 473" entre los 50 primeros (`SG3`).
2. **Un nombre propio que casi no aparece se pierde.** El documento de Joseph Obando Sandí (`S22-3`, `EN3`, `EN4`) queda bajo el umbral con la pregunta completa y ni el reranker local lo rescata (su documento puntúa 0,000: el texto no parece hablar de él en forma de pasaje, pero el nombre aparece escrito). El de Luis Diego Cubillo Guevara roza el umbral (0,819 contra 0,82).
3. **El programa de Deep Learning (`LL2`) queda en el puesto 50** y `EN1` ("Háblame de Natalia Soto Solís") en el 43: más allá de cualquier lista razonable de candidatos por similitud.

La *búsqueda híbrida* agrega a la búsqueda por significado una búsqueda por **coincidencia de palabras** (léxica): los fragmentos que contienen literalmente las palabras raras de la pregunta (el apellido, la sigla) se suman a los candidatos y se fusionan con los de la búsqueda por significado en una sola lista. Es la opción D del documento de requerimientos de la versión 3 y la que más cambia el almacenamiento (la anterior solo agregó una etapa en memoria), por eso se construye apagada, se mide con el conjunto de casos de la línea base y el usuario decide si se conserva.

Límites conocidos desde ya: la coincidencia de palabras ayuda con palabras específicas, no con palabras comunes ("maestría", "curso", "trabajo"): si dejara pasar fragmentos solo por coincidir en palabras comunes, las preguntas sin respuesta llegarían al modelo de lenguaje con relleno (BUS-3). La búsqueda híbrida tampoco inventa sinónimos: "trabajo final de graduación" y "TFG" se relacionan solo si algún documento o una lista de equivalencias los une (ver Assumptions).

## Clarifications

### Session 2026-10-19

- Q: ¿Cuántas de las palabras específicas de la pregunta debe contener un fragmento que llegó solo por palabras para pasar al modelo de lenguaje? → A: La mayoría: más de la mitad de las palabras específicas (1 de 1, 2 de 2, 2 de 3, 3 de 4).
- Q: ¿Dónde mantiene quien opera MIA la lista de equivalencias de siglas? → A: En una pantalla del panel de administración, con alta, edición y baja de siglas (la lista se guarda en la base de datos).
- Q: ¿Qué latencia máxima añadida por la búsqueda por palabras se acepta? → A: Hasta 0,2 s en p50 y 0,5 s en p95, medida como el tiempo que el servidor dedica a la búsqueda por palabras y a la fusión.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar un documento por una palabra exacta que los vectores no distinguen (Priority: P1)

Una persona de Coordinación pregunta "¿Quién es Joseph Obando Sandí?" o "¿Cuál es el plan de estudios de la MGTI?". Hoy MIA responde "sin información suficiente" o con otros documentos, porque la similitud de vectores no relaciona el nombre ni la sigla con el documento. Con la búsqueda híbrida encendida, los fragmentos que contienen literalmente "Obando" o "MGTI" entran entre los candidatos, y el modelo de lenguaje responde con ellos.

**Why this priority**: es el problema de recuperación que las features 008 y 009 dejaron sin resolver y la razón de ser de la opción D (BUS-1).

**Independent Test**: con la búsqueda híbrida encendida, hacer las preguntas de los casos `S22-3`, `EN3`, `EN4`, `SG3` y `EN1` en los dos modos, y comprobar que responden con el documento esperado.

**Acceptance Scenarios**:

1. **Given** una pregunta con un nombre propio cuyo documento está más allá de los primeros candidatos por similitud (puesto 12 o más) o bajo el umbral, **When** se consulta con la búsqueda híbrida encendida, **Then** el documento que contiene ese nombre llega al modelo de lenguaje y la respuesta se basa en él.
2. **Given** una pregunta con una sigla (MGTI, TFG) cuyo documento no está entre los candidatos por similitud, **When** se consulta con la búsqueda híbrida encendida, **Then** el documento que contiene esa sigla llega al modelo.
3. **Given** una pregunta cuyo documento ya se encontraba bien (los 19 casos de la batería del MVP), **When** se consulta con la búsqueda híbrida encendida, **Then** la respuesta no empeora ni cambia de documento sin razón.
4. **Given** la búsqueda híbrida encendida, **When** se hace una consulta, **Then** el número de fragmentos que llega al modelo de lenguaje no supera el que el modo ya configura hoy (8 en literal, 16 con razonamiento, o el que resulte de la feature 007), de modo que el costo por consulta no sube por sumar candidatos.

---

### User Story 2 - Relacionar la sigla con su forma desarrollada y al revés (Priority: P1)

Una persona pregunta "¿Qué líneas de trabajo final de graduación ofrece la maestría?" y el documento dice "Líneas de TFG"; o pregunta por "TFG" y el documento dice "trabajo final de graduación". En ambos sentidos MIA debe encontrar el mismo documento.

**Why this priority**: es el segundo requerimiento de la versión 3 (BUS-2), y el caso `S22-2` es hoy el único donde el documento ni siquiera aparece entre 50 candidatos.

**Independent Test**: hacer la pregunta larga y la corta de `S22-2` y las de `SG3`, y comprobar que las dos responden con los mismos documentos.

**Acceptance Scenarios**:

1. **Given** una pregunta con la forma desarrollada de una sigla, **When** se consulta con la búsqueda híbrida encendida, **Then** se encuentra el documento que usa la sigla, y la pregunta con la sigla encuentra el documento que usa la forma desarrollada.
2. **Given** una sigla o equivalencia que no está en la lista de equivalencias ni en ningún documento, **When** se consulta, **Then** MIA no inventa la relación: la respuesta es la de hoy.
3. **Given** el operador agrega una equivalencia nueva (sigla y forma desarrollada) desde el panel, **When** se consulta con ella, **Then** surte efecto en la consulta siguiente (máximo un minuto), sin reindexar los documentos ni desplegar código.

---

### User Story 3 - Seguir diciendo "sin información" cuando los documentos no la tienen (Priority: P1)

Las preguntas sobre algo que no está en los documentos ("¿Quién es Zacarías Fernández Pizarro?", "¿Qué es el PRGX?", "¿Cuál es el horario de atención de la biblioteca?") deben seguir respondiendo "sin información suficiente" sin llamar al modelo de lenguaje, aunque compartan palabras comunes con los documentos ("horario", "biblioteca", "es") o aunque el nombre inventado se parezca a un nombre real.

**Why this priority**: es la salvaguarda de la opción (BUS-3, BUS-7). Una coincidencia léxica demasiado permisiva hace llegar al modelo fragmentos de relleno, sube el costo de cada consulta sin respuesta y aumenta las respuestas inventadas.

**Independent Test**: medir los casos que esperan "sin información" (`N1`, `I1` a `I3`, `SR1` a `SR7`, `EN7`, `EN8`, `EN9`) con la búsqueda híbrida encendida, y comprobar que ninguno responde con contenido inventado y que los que hoy se cortan sin gastar tokens siguen cortándose.

**Acceptance Scenarios**:

1. **Given** una pregunta cuyas palabras específicas (nombres, siglas, términos raros) no aparecen en ningún documento, **When** se consulta con la búsqueda híbrida encendida, **Then** la respuesta es "sin información suficiente" sin llamar al modelo.
2. **Given** una pregunta que solo comparte palabras comunes con los documentos, **When** se consulta, **Then** esas coincidencias no hacen que un fragmento llegue al modelo.
3. **Given** una pregunta con un nombre real pero sobre un dato que los documentos no tienen (`EN9`, "¿Qué es obligatorio en el trabajo de Joseph Obando Sandí?"), **When** se consulta, **Then** puede llegar al modelo (el nombre sí aparece) pero la respuesta sigue siendo "sin información suficiente" y no se inventa el dato; el costo de ese caso se mide y queda registrado.
4. **Given** una consulta cuyo mejor resultado vino de la coincidencia de palabras, **When** se registra en Uso, **Then** queda anotado que la búsqueda híbrida intervino, para poder revisar las respuestas dudosas.

---

### User Story 4 - Poder apagarlo, y que un fallo no rompa la consulta (Priority: P1)

Quien opera MIA enciende o apaga la búsqueda híbrida con una variable de configuración, sin cambiar código. Por defecto está apagada y MIA se comporta como antes de la feature. Si la parte léxica falla o no está disponible (el índice de palabras no existe aún, una colección sin él, un error), la consulta no se cae: sigue con la búsqueda por significado de siempre y deja un aviso.

**Why this priority**: es la salvaguarda para probar en producción y volver atrás en minutos (BUS-6), y evita que una prueba de esta magnitud (toca el almacenamiento) pueda dejar a MIA sin responder.

**Independent Test**: con la opción apagada, repetir la línea base y comprobar que respuestas, fuentes, costo y notas de Uso son las de antes; encenderla; y simular que la parte léxica falla para comprobar que la consulta responde por significado con un aviso.

**Acceptance Scenarios**:

1. **Given** la configuración por defecto, **When** MIA responde, **Then** el comportamiento, el costo, las fuentes y el registro son idénticos a los de antes de la feature.
2. **Given** la opción encendida y la parte léxica caída o sin índice, **When** llega una consulta, **Then** responde con la búsqueda por significado de siempre, deja un aviso limitado en el registro del servidor y una nota en Uso, y no devuelve error.
3. **Given** un valor inválido de `QUERY_HYBRID_SEARCH` (distinto de `on` y de `off`), **When** el servicio arranca o responde, **Then** usa el comportamiento anterior (apagada) y deja un aviso, sin fallar. Los parámetros numéricos (`HYBRID_*`) tienen rangos obligatorios, igual que los de `RERANK_*` y los demás: un valor fuera de rango hace que el servicio no arranque con un mensaje que nombra la variable (decisión de la convergencia del 2026-10-19: un valor numérico mal escrito es un error de configuración que conviene ver al desplegar, no uno que se oculte).
4. **Given** que se vuelve a la versión etiquetada `prototipo-v2-estable`, **When** se leen los registros y los documentos ya ingeridos con esta feature, **Then** se leen sin errores y la búsqueda por significado de esa versión funciona con los mismos datos, y la API arranca aunque la base ya tenga la tabla de equivalencias (siguiendo el procedimiento fijado en el plan).
5. **Given** una consulta rechazada por permisos o por tope de gasto, **When** llega con la búsqueda híbrida encendida, **Then** se rechaza antes de buscar nada, como hoy.

---

### User Story 5 - Los documentos nuevos y los ya ingeridos quedan encontrables por palabras (Priority: P2)

Cuando se ingiere un documento nuevo, sus palabras quedan disponibles para la búsqueda léxica sin un paso manual aparte. Los documentos que ya están ingeridos se pueden preparar para la búsqueda léxica con un procedimiento de una sola vez, local y gratuito, que no vuelve a calcular los vectores de significado ni consume tokens.

**Why this priority**: sin esto, la búsqueda híbrida solo vería los documentos nuevos. Es necesario para medirla, pero se puede entregar después de la historia 1 si el procedimiento de preparación de lo ya ingerido se hace a mano.

**Independent Test**: ingerir un documento con una palabra rara, comprobar que la pregunta con esa palabra lo encuentra; preparar la colección existente y comprobar que los documentos viejos responden igual.

**Acceptance Scenarios**:

1. **Given** un documento nuevo con la palabra "X" ingerido con la búsqueda híbrida disponible, **When** se pregunta por "X", **Then** el documento aparece entre los candidatos sin pasos adicionales.
2. **Given** la colección ya ingerida, **When** se ejecuta el procedimiento de preparación, **Then** los documentos existentes quedan encontrables por palabras, no se recalculan los vectores de significado, no se usa ningún servicio de pago, y se puede repetir sin duplicar ni dañar nada.
3. **Given** una colección a medio preparar, **When** se consulta con la opción encendida, **Then** los documentos preparados se encuentran por palabras y los demás siguen encontrándose por significado, sin error.

---

### User Story 6 - Medir cuánto cuesta y cuánto mejora, y decidir si se conserva (Priority: P1)

Quien opera MIA mide la búsqueda híbrida con los datos de producción en local y, si es prometedora, en Railway: calidad con el conjunto de casos de la línea base (más casos de nombres, siglas y términos específicos), latencia añadida, memoria de la API en reposo y tamaño del almacenamiento. Con eso decide si la conserva, la deja apagada o la combina con el reranker.

**Why this priority**: es una opción grande (cambia el almacenamiento) y sin medición no hay decisión.

**Independent Test**: correr las mediciones con la búsqueda híbrida apagada (control) y encendida y leer en el informe calidad por caso, latencia p50 y p95, memoria, tamaño del almacenamiento y costo.

**Acceptance Scenarios**:

1. **Given** el conjunto de casos de la línea base, **When** se mide con la herramienta de la feature 005, **Then** el informe muestra por caso y por modo el puesto del documento esperado con y sin la parte léxica, qué parte lo trajo (significado, palabras o ambas) y cómo cambió contra la corrida de control.
2. **Given** la medición completa, **When** se evalúan los criterios, **Then** el informe dice si cada criterio se cumple y la recomendación (conservar, dejar apagado, combinar con el reranker local), y la decisión queda en manos del usuario.
3. **Given** que las respuestas medidas gastan tokens, **When** se pide medir con respuestas, **Then** se fija y autoriza un tope de gasto antes de correr; el cálculo de candidatos y puestos (sin llamar al modelo de lenguaje) no cuesta.

---

---

### User Story 7 - Mantener la lista de equivalencias de siglas desde el panel (Priority: P2)

El operador abre en el panel de administración la pantalla de equivalencias, ve las siglas declaradas (TFG, MGTI), agrega una nueva con su forma desarrollada ("PLN" y "procesamiento de lenguaje natural"), corrige una existente o la borra, y la siguiente consulta ya la usa. No hace falta tocar archivos, variables ni reiniciar la API.

**Why this priority**: la historia 2 funciona con una lista inicial; la pantalla es lo que permite que crezca sin ayuda de desarrollo. Se puede entregar después de la historia 2 si la lista inicial se carga con un script.

**Independent Test**: en el panel, agregar una equivalencia, hacer una pregunta con la sigla y comprobar que encuentra el documento de la forma desarrollada; borrarla y comprobar que deja de hacerlo.

**Acceptance Scenarios**:

1. **Given** el operador con sesión en el panel, **When** agrega, edita o borra una equivalencia, **Then** el cambio queda guardado con su autor y fecha, y la consulta siguiente (máximo un minuto después) lo refleja.
2. **Given** una persona con alcance de programa (no global), **When** abre la pantalla, **Then** ve la lista pero no puede agregar, editar ni borrar, y la API rechaza el intento si se hace por fuera de la pantalla.
3. **Given** datos inválidos (sigla vacía, par repetido, texto demasiado largo), **When** el operador intenta guardar, **Then** se rechaza con un mensaje que dice qué corregir y no se guarda nada.
4. **Given** una equivalencia que se va a borrar, **When** el operador la borra, **Then** el panel pide confirmación y, al confirmar, la pregunta con esa sigla vuelve a comportarse como sin equivalencia.

---

### Edge Cases

- La pregunta no tiene palabras específicas (solo palabras comunes: "¿cuál es el procedimiento?"): la parte léxica no aporta candidatos y la consulta se comporta como hoy.
- Una palabra aparece en demasiados documentos (una sigla muy usada, o "maestría"): deja de ser específica, no cuenta para la regla de FR-005 y no trae fragmentos por sí sola; el máximo de documentos para ser específica es configurable y se calibra con los casos. Se cuentan documentos y no fragmentos: un apellido repetido en cada página de una tesis es un solo documento y sí es específico.
- Una palabra de la pregunta no aparece en ningún documento (un apellido inventado, o "Sandí" cuando el documento dice solo "Joseph Obando"): cuenta como específica sin coincidencias, de modo que una pregunta con varias palabras ausentes no pasa la regla.
- El nombre aparece con otra forma: con o sin tildes, en mayúsculas, con un solo apellido o con un apellido compuesto. La coincidencia se hace sin distinguir mayúsculas ni tildes y acepta un nombre incompleto en el documento mientras coincida la mayoría de las palabras específicas de la pregunta ("Joseph Obando" sirve para "Joseph Obando Sandí", 2 de 3; un apellido suelto no), y los fragmentos con más coincidencias van primero.
- Dos personas distintas comparten un apellido: se traen fragmentos de las dos; el modelo de lenguaje y las fuentes citadas (feature 006) distinguen cuál responde.
- Un fragmento llega por las dos búsquedas (significado y palabras): aparece una sola vez en la lista fusionada y se favorece por haber llegado por ambas.
- Un fragmento llega solo por la parte léxica y su similitud de vectores está bajo el umbral: entra a la lista porque contiene la mayoría de las palabras específicas de la pregunta (FR-005), no por el umbral de similitud; ese es el caso que la feature resuelve.
- Se escribe una sigla en minúscula ("tfg") o con puntos ("T.F.G."): se trata igual que "TFG".
- Una palabra rara de la pregunta es un error de tipeo ("Obndo"): no coincide con nada, la pregunta sigue como hoy y no se busca por aproximación en esta feature.
- La opción encendida con la pregunta limpia (feature 008) o el reranker (feature 009) encendidos: cada pieza funciona como lo hace sola y se combinan en un orden fijado en el plan; la nota de Uso de cada una convive con las demás.
- Una sigla con dos formas desarrolladas, o dos siglas que comparten forma desarrollada: se aceptan y la pregunta busca todas las formas; no se encadenan equivalencias (una sigla no se expande a través de otra), para evitar bucles y expansiones inesperadas.
- El panel y la API discrepan o la tabla de equivalencias no está disponible (base caída, tabla aún no migrada): la consulta sigue sin equivalencias, con aviso y nota en Uso, igual que con cualquier falla de la parte léxica (FR-009).
- Aislamiento de dominios: la parte léxica respeta los mismos filtros de dominio y permisos del artefacto que la de significado; un fragmento de un dominio al que el artefacto no tiene acceso nunca aparece, ni siquiera por coincidir en palabras.
- Ningún fragmento coincide en palabras ni supera el umbral de similitud: "sin información suficiente" sin llamar al modelo, como hoy.
- Un documento se borra o se mueve de dominio (operaciones del panel): su parte léxica se actualiza con él, sin dejar fragmentos huérfanos que aparezcan en búsquedas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Debe existir una forma de buscar por coincidencia de palabras sobre el texto de los fragmentos ya ingeridos, además de la búsqueda por significado, seleccionable por configuración con un valor apagado por defecto. Con el valor por defecto, el comportamiento es el de antes de la feature (BUS-6).
- **FR-002**: Con la búsqueda híbrida encendida, la API debe unir en una sola lista los candidatos de la búsqueda por significado y los de la búsqueda por palabras, sin duplicados, de modo que un fragmento que llegó por las dos tenga prioridad sobre uno que llegó por una sola.
- **FR-003**: La búsqueda por palabras debe comparar sin distinguir mayúsculas ni tildes, tratar igual una sigla escrita con o sin puntos ("TFG", "T.F.G.", "tfg") y dar mayor peso a las palabras raras de la pregunta (las que aparecen en pocos fragmentos) que a las comunes.
- **FR-004**: La búsqueda por palabras debe respetar el mismo filtro de dominios y de permisos del artefacto que la búsqueda por significado; ningún fragmento de un dominio no permitido puede aparecer por esta vía.
- **FR-005**: Un fragmento que solo llegó por palabras (su similitud de vectores está bajo el umbral) pasa al modelo de lenguaje únicamente si contiene la mayoría de las palabras específicas de la pregunta (nombres, siglas, términos raros), es decir, más de la mitad: 1 de 1, 2 de 2, 2 de 3, 3 de 4. Nunca pasa por coincidir solo con palabras comunes. Qué palabra cuenta como específica (en cuántos documentos aparece) y la proporción exigida se calibran con casos con respuesta y sin respuesta, quedan documentados con esos valores por defecto y se pueden ajustar por configuración.
- **FR-006**: El número de fragmentos que llega al modelo de lenguaje no debe superar el que el modo ya configura hoy (8 en literal, 16 con razonamiento, o el que resulte de la feature 007), de modo que sumar candidatos no suba el costo del modelo de lenguaje (BUS-4).
- **FR-007**: Debe existir una lista de equivalencias de siglas (una sigla y una o más formas desarrolladas) que se mantiene desde una pantalla del panel de administración, con alta, edición y baja, sin reindexar los documentos ni desplegar código; con ella, la pregunta con una forma encuentra los documentos que usan la otra, en los dos sentidos (BUS-2). La lista inicial contiene al menos TFG y MGTI, con sus formas desarrolladas tal como aparecen en los documentos del programa. Una sigla sin equivalencia declarada no se relaciona con nada. Un cambio en la lista surte efecto en la consulta siguiente, con un retraso máximo de un minuto.
- **FR-008**: La búsqueda por palabras no debe llamar a ningún modelo de lenguaje ni a ningún servicio externo, y no debe suponer ningún cálculo de vectores nuevo por consulta (BUS-7): una consulta sin respuesta tras la búsqueda híbrida no gasta tokens. Los topes de gasto por artefacto y de toda la API se siguen evaluando antes de buscar, como hoy.
- **FR-009**: Si la parte léxica no está disponible (la colección aún no la tiene, falla, o excede un tiempo máximo), la consulta debe continuar con la búsqueda por significado y el umbral de siempre, dejar un aviso limitado en el registro del servidor y una nota en Uso, y nunca devolver un error por esa causa.
- **FR-010**: Los documentos nuevos deben quedar encontrables por palabras al ingerirse, sin pasos manuales adicionales; las operaciones del panel que cambian un documento (borrar, mover de dominio, reingerir) deben mantener su parte léxica sincronizada.
- **FR-011**: Debe existir un procedimiento de preparación de los documentos ya ingeridos para la búsqueda por palabras: de una sola vez, repetible sin efectos duplicados, local, sin recalcular los vectores de significado, sin consumir tokens ni servicios de pago, y que no deje la colección inutilizable mientras corre ni si se interrumpe. Los documentos aún no preparados siguen encontrándose por significado.
- **FR-012**: La búsqueda por palabras no debe introducir pérdida de datos ni exigir borrar y volver a ingerir los documentos: los textos, los vectores de significado, los identificadores de fragmentos y los registros de la base de datos relacional se conservan. Volver a la versión `prototipo-v2-estable` debe seguir siendo posible con los mismos datos (ver FR-021 para la tabla de equivalencias).
- **FR-013**: El registro de consultas del módulo Uso debe anotar, cuando la parte léxica intervino, cuántos candidatos aportó y si el fragmento principal de la respuesta vino de ella; y, cuando falló, que se cayó a la búsqueda por significado. Esta anotación convive con las demás notas del registro (features 006 a 009) en el mismo orden estable y no requiere cambios en la estructura de la base relacional.
- **FR-014**: La respuesta de la API conserva su estructura; la búsqueda híbrida no es visible para quien consulta salvo por su efecto.
- **FR-015**: Las citas por fragmento (feature 006), el contexto completo y el reintento por corte (feature 007), la pregunta limpia (feature 008) y el reranker local (feature 009) deben seguir funcionando con la lista de candidatos fusionada, cada uno como lo hace solo. El plan fija el orden de las etapas y cómo se combinan los cortes (por ejemplo, la fusión después del reranker, con los fragmentos que llegaron por palabras fuera del mínimo del reranker, y la pregunta limpia solo cuando la lista fusionada no deja ningún fragmento que pase).
- **FR-016**: La herramienta de medición de la feature 005 debe registrar por consulta, con la búsqueda híbrida encendida, el puesto del documento esperado con y sin la parte léxica, qué parte trajo cada candidato (significado, palabras o ambas), la latencia añadida y si hubo caída a la búsqueda por significado; resumirlos por modo y comparar corridas con y sin la opción. Debe poder calcular los candidatos y puestos sin llamar al modelo de lenguaje (sin costo) para calibrar el criterio de FR-005.
- **FR-017**: El conjunto de casos de la línea base debe ampliarse con casos de nombres propios, siglas, formas desarrolladas, términos específicos inventados y preguntas con palabras comunes sin respuesta (al menos 12 casos nuevos, la mitad que esperan "sin información"), para que la calibración de FR-005 no dependa de los mismos 57 casos con que se calibró el reranker.
- **FR-018**: Debe existir un procedimiento documentado para medir memoria (API en reposo y bajo carga, con y sin la parte léxica, en local y en Railway), latencia añadida (p50 y p95), tamaño del almacenamiento antes y después, y cambio en el costo mensual, y los resultados deben quedar en la documentación junto a la recomendación.
- **FR-019**: Deben existir pruebas automáticas, sin servicios externos, de: la configuración (apagado, encendido, inválido), la fusión de las dos listas (sin duplicados, prioridad de los fragmentos que llegan por ambas), el criterio de palabras específicas frente a comunes, la normalización (tildes, mayúsculas, siglas con puntos), la lista de equivalencias (incluida su validación, el permiso solo para el operador y la ausencia de encadenamiento), la pantalla del panel (pruebas de componentes y de tipos), la migración aditiva, el respeto del filtro de dominio, el máximo de fragmentos al modelo, "sin información" sin llamar al modelo, la caída a significado cuando la parte léxica falla, las notas de Uso y su convivencia con las de las features 006 a 009, y que con la opción apagada nada cambia. La documentación (arquitectura, operación y requerimientos) debe describir las variables, cómo encenderla, cómo preparar los documentos ya ingeridos y cómo medir.
- **FR-020**: La pantalla de equivalencias del panel debe seguir las reglas de la interfaz del panel ([web/admin/README.md](../../web/admin/README.md#interfaz-mantine)), validar lo que se escribe (sigla y forma desarrollada no vacías, sin duplicar el mismo par, longitud acotada) con mensajes claros, mostrar el efecto esperado ("la pregunta con la sigla también busca la forma desarrollada") y pedir confirmación antes de borrar. La lista de equivalencias es global (vale para todos los programas y dominios): solo la puede cambiar el operador (alcance global); las personas con alcance de programa pueden verla pero no editarla. Cada cambio queda con quién lo hizo y cuándo.
- **FR-021**: Guardar la lista en la base de datos agrega una tabla nueva y por tanto una migración. La migración debe ser solo aditiva (no cambia ni borra nada de lo existente) y estar probada con `scripts/probar_migracion.py` sobre una copia de la base de producción; el plan fija cómo se vuelve a la versión etiquetada `prototipo-v2-estable` (que no conoce la tabla) sin que la API deje de arrancar, siguiendo la advertencia de "Cuidado con las migraciones" de [OPERACION.md](../../docs/OPERACION.md), y lo documenta.

### Key Entities *(include if feature involves data)*

- **Búsqueda por palabras (léxica)**: la búsqueda que trae fragmentos por las palabras específicas que contienen, a diferencia de la búsqueda por significado; se suma a ella cuando la opción está encendida.
- **Lista fusionada de candidatos**: la lista única, sin duplicados, que resulta de unir lo que trajeron la búsqueda por significado y la de palabras, con prioridad para lo que llegó por ambas; de ella salen los fragmentos que llegan al modelo de lenguaje.
- **Palabra específica**: una palabra de la pregunta (nombre propio, sigla, término técnico) que aparece en pocos documentos; es la que da derecho a un fragmento a llegar al modelo si solo vino por palabras. Se opone a la palabra común.
- **Lista de equivalencias de siglas**: pares sigla y forma desarrollada que mantiene el operador desde el panel de administración (global, con autor y fecha de cada cambio) para que la pregunta con una forma encuentre los documentos de la otra.
- **Preparación de lo ya ingerido**: el procedimiento de una sola vez que deja los documentos existentes encontrables por palabras sin recalcular vectores.
- **Nota de la búsqueda híbrida**: la anotación del registro de Uso con cuántos candidatos aportó la parte léxica y si ayudó, o si cayó a la búsqueda por significado.
- **Informe de la prueba**: el resultado de medir calidad, latencia, memoria, almacenamiento y costo, con la recomendación de conservar, dejar apagado o combinar con el reranker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Los casos de nombres propios y siglas cuyo documento hoy no llega al modelo (`S22-2`, `S22-3`, `S22-4`, `SG3`, `EN3`, `EN4`, `EN1`) responden con su documento esperado con la búsqueda híbrida encendida, tanto con la pregunta completa como con la corta, en los dos modos. Si un caso no se puede resolver con los datos (por ejemplo, el documento esperado no contiene la palabra buscada), se reporta aparte con la razón y no cuenta contra el criterio.
- **SC-002**: De los 8 casos de BUS-1 y BUS-2 de la línea base que hoy fallan, al menos 6 de 8 pasan en literal y 7 de 8 con razonamiento (hoy fallan 7 de 8 en literal y 6 en razonamiento).
- **SC-003**: El 100 % de los casos que esperan "sin información" (`N1`, `I1` a `I3`, `SR1` a `SR7`, `EN7`, `EN8`, los 6 casos nuevos sin respuesta de FR-017, y `EN9` sin inventar el dato) siguen sin responder con contenido inventado, y los que hoy se cortan sin gastar tokens (`N1`, `I2` y los de otro dominio) siguen cortándose sin llamar al modelo.
- **SC-004**: Los 19 casos de la batería del MVP siguen respondiendo igual: ninguno empeora (BUS-3), en literal y con razonamiento.
- **SC-005**: Con la búsqueda híbrida apagada, el texto, las fuentes y las notas de Uso de cada caso son los de la línea base (sin diferencias atribuibles a la feature).
- **SC-006**: La búsqueda híbrida encendida no suma ninguna llamada a un modelo de lenguaje por consulta ni sube el costo medio por consulta más allá del ruido de la corrida de control, salvo las consultas que antes eran "sin información" y ahora llegan al modelo porque sí tienen respuesta (BUS-4); el informe cuantifica ese costo adicional por caso.
- **SC-007**: La latencia que la búsqueda híbrida añade a una consulta, medida como el tiempo extra que la consulta espera por la búsqueda por palabras y la fusión, además de lo que ya tardaba la búsqueda por significado (la parte léxica corre en paralelo con ella), es como máximo de 0,2 s en p50 y 0,5 s en p95 (límite confirmado por el usuario el 2026-10-19); el informe muestra los valores reales y dice si se cumple.
- **SC-008**: Con la búsqueda híbrida disponible, la API completa sigue por debajo de 512 MB de RAM en reposo y dentro de los 5 USD incluidos en el plan, sin subir de plan; el informe muestra los valores reales con y sin ella y el tamaño del almacenamiento antes y después. Si solo cumple subiendo de plan, el resultado se reporta como "no cumple" y la decisión queda aparte, en manos del usuario.
- **SC-009**: Si la parte léxica falla, el 100 % de las consultas simuladas con esa falla responden como sin ella, con aviso y nota, y ninguna devuelve error (prueba automática).
- **SC-010**: El procedimiento de preparación de lo ya ingerido deja el 100 % de los fragmentos existentes encontrables por palabras, sin recalcular vectores, sin gasto, y repetirlo no cambia el resultado.
- **SC-011**: El informe concluye explícitamente, con los datos medidos, una de tres recomendaciones (conservar, dejar apagado, combinar con el reranker local) y lista para cada criterio si se cumple o no.
- **SC-012**: El operador agrega una equivalencia desde el panel y la consulta siguiente la usa en menos de un minuto, sin reiniciar la API; una persona sin alcance global no puede cambiarla; y la API arranca con la versión anterior de la base (procedimiento de FR-021) sin pérdida de datos.

### Resultados medidos (2026-10-19)

Detalle en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md) y [research.md](research.md) (R16). Medición gratuita (sin tokens) en un Qdrant local con una copia de producción y, con la autorización del usuario, contra el Qdrant de producción en solo lectura (resultados idénticos). 70 casos, 98 preguntas. La medición con respuestas en Railway se hizo el 2026-10-19 con la autorización del usuario (tope de 0,60 USD por corrida; gastó 0,185 y 0,176 USD): los criterios SC-002, SC-004 y SC-006 se verificaron con respuestas.

| Criterio | Resultado | Veredicto |
|---|---|---|
| SC-001 | `S22-2`, `S22-3`, `S22-4`, `EN1` a `EN4` (con la pregunta completa y la corta) tienen su documento en la lista final en los dos modos. `SG3` (MGTI) no: la sigla con su forma desarrollada aparece en 14 documentos del dominio y deja de ser específica; se reporta aparte con la razón. | Cumple, con `SG3` reportado aparte |
| SC-002 | 8 de 8 preguntas de BUS-1 y BUS-2 con su documento en la lista final en literal (antes 1) y en razonamiento (antes 2) (recuperación). Con respuestas en Railway y el criterio de la herramienta: las 8 preguntas (`S22-1` a `S22-4`, completa y corta) quedan correctas en los dos modos; el control acertaba 1 de 8 en literal y 2 de 8 con razonamiento. | Cumple |
| SC-003 | Ninguno de los casos "sin información" (`N1`, `I1` a `I3`, `SR1` a `SR7`, `EN7` a `EN9`, `HS1` a `HS6`) recibe candidatos léxicos: ninguno llega al modelo por esta vía. `EN9` ("¿Qué es obligatorio en el trabajo de Joseph Obando Sandí?") tampoco, porque `obligatorio` cuenta como palabra específica ausente. | Cumple en recuperación |
| SC-004 | Ningún caso con respuesta empeora en recuperación (65 de 69 con su documento, antes 40 y 44). Con respuestas en Railway: la batería del MVP queda en 15 de 15 en los dos modos; cuatro diferencias en contra de la primera corrida desaparecieron al repetirlas (variación del modelo). | Cumple |
| SC-005 | Pruebas automáticas: con la opción apagada, con `""` o con un valor inválido no se llama a la parte léxica, no se lee la tabla de siglas y se entrega lo mismo que antes. | Cumple |
| SC-006 | Ninguna llamada nueva a un modelo de lenguaje (por diseño y por pruebas). Costo medio por consulta con respuestas: 0,000405 frente a 0,000432 USD en literal y 0,001939 frente a 0,001793 USD con razonamiento (dentro del ruido). | Cumple |
| SC-007 | Contra Qdrant Cloud desde la laptop del usuario (unos 80 ms de ida y vuelta): espera y fusión p50 82 ms y p95 203 ms (máximo 874 ms); local, p50 5 ms y p95 10 ms. | Cumple |
| SC-008 | La API no suma RAM (el índice vive en Qdrant). En Qdrant, el índice ocupa unos 140 MB más en un contenedor local (cifra de `docker stats`, que incluye la caché de archivos mapeados) y el almacenamiento de la colección copiada queda en 52 MB. RAM de la API en Railway (2026-10-19): mediana de 342 MB con la opción encendida y de 341 MB apagada, máximo de 343 MB encendida; Qdrant Cloud: 131 MB residentes con el índice en disco. | Cumple |
| SC-009 | Pruebas automáticas (almacén sin métodos léxicos, error, tiempo agotado, falla de `score_chunks`, tabla de siglas ilegible): todas responden por significado con aviso y nota, ninguna da error. | Cumple |
| SC-010 | `scripts/palabras.py preparar` deja 6.239 de 6.239 fragmentos indexados en 1,5 s (local) y en producción, sin recalcular vectores y repetible. | Cumple |
| SC-011 | Conservar y encender cuando el usuario decida; ver [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md). | Cumple |
| SC-012 | Verificado en el navegador (cuenta global edita; cuenta de programa solo ve; el duplicado se rechaza), por pruebas automáticas (403 `global_only`, caché) y la vuelta atrás probada en SQLite (`alembic downgrade 0004` y `prototipo-v2-estable` arranca). También se probó en una copia de la base de Neon (2026-10-19): `downgrade 0004` borra solo la tabla, `prototipo-v2-estable` arranca sobre la base devuelta y la base sube sola a `0005`. | Cumple |

## Assumptions

- Quien opera MIA es una sola persona (el usuario); quien consulta es el personal de Coordinación mediante la Consulta administrativa.
- El comportamiento por defecto sigue siendo el actual hasta que la medición respalde encender la búsqueda híbrida; encenderla en producción es una decisión posterior del usuario, fuera de esta feature.
- La preparación de los documentos ya ingeridos puede cambiar el esquema de almacenamiento de los fragmentos (el texto ya está guardado con cada fragmento, así que no se vuelve a leer ningún archivo ni se recalculan los vectores de significado). Se acepta ese cambio de esquema, pero debe poder revertirse sin perder datos (FR-012).
- El corpus es pequeño (la medición actual cabe en el almacenamiento gratuito), así que la búsqueda por palabras puede resolverse sin infraestructura nueva ni servicios de pago; el plan elige la técnica concreta (índice de palabras en el almacén de vectores, índice en la base relacional u otra) tras medir su memoria, latencia y tamaño. No se usa un servicio externo de búsqueda.
- Los límites de memoria (512 MB en reposo) y de plan (5 USD) son los ya confirmados por el usuario el 2026-10-18 para el reranker; la latencia añadida de SC-007 la confirmó el usuario el 2026-10-19; la parte léxica no corre un modelo y se espera mucho menor que la del reranker.
- La lista de equivalencias de siglas es manual y la mantiene el operador desde el panel (decisión del 2026-10-19); descubrir siglas automáticamente de los documentos queda fuera. Los nombres propios no necesitan equivalencias: se encuentran por sus propias palabras. La lista es global (no por programa) porque las siglas del posgrado (TFG, MGTI) se usan en todos los dominios; si más adelante hiciera falta por programa, sería otra feature.
- La pantalla de equivalencias sigue el tema y los componentes de Mantine del panel; es la única parte visual de esta feature.
- La coincidencia de palabras es exacta (con normalización de mayúsculas, tildes y puntos de siglas); no corrige errores de tipeo ni busca por parecido de letras en esta feature.
- El criterio de FR-005 (qué cuenta como palabra específica y cuántas coincidencias hacen falta) es lo más delicado de la feature para BUS-3 y se calibra con datos: es posible que no exista un criterio que separe todos los casos, en cuyo caso el resultado es negativo y se reporta, o se combina con el reranker (que sí separa las preguntas sin respuesta) en una feature posterior.
- La verificación usa la herramienta de la feature 005: los candidatos y puestos se calculan sin llamar al modelo de lenguaje (sin costo) primero en local y luego contra producción en solo lectura; la medición con respuestas se hace reducida, con un tope de gasto fijado y autorizado por el usuario antes de correr, y una corrida de control con la opción apagada. Como producción aún no tiene el código de `dev`, la medición en Railway exige desplegar `dev` temporalmente según el procedimiento ya establecido, y se apaga al terminar. Los criterios que solo se verifican con respuestas medidas en Railway (SC-002, SC-004 y SC-006) quedan como "no medido" si el usuario no autoriza el gasto, y el informe lo dice en lugar de darlos por cumplidos.
- El comportamiento del modelo de lenguaje no es del todo determinista: un caso que cambie de resultado entre corridas se repite antes de contarse como regresión.
- Quedan fuera de esta feature: cualquier servicio externo de búsqueda, la búsqueda por parecido de letras o corrección de errores de tipeo, descubrir siglas automáticamente, el contexto por fragmento al ingerir (opción G), bajar el umbral (opciones A y C), reformular con un modelo de lenguaje, encender el reranker local (decisión aparte del usuario), y cualquier cambio visual de la Consulta o del panel fuera de la pantalla de equivalencias.
