# Feature Specification: Reranker local (reordenar los candidatos de la búsqueda)

**Feature Branch**: `dev` (feature `009-reranker-local`, sin rama propia por decisión del usuario)

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description: "Reranker local (opción E de docs/Definicion_Requerimientos_V3.md, secciones 2.5, 2.6 y 2.7; requerimientos BUS-1, BUS-2, BUS-3, BUS-4, BUS-5, BUS-6, BUS-7). Prueba de costo de un cross-encoder que corre dentro del propio servidor de la API, sin ninguna API externa de reranking. Con el reranker encendido, la API recupera más candidatos, un modelo los reordena según la pregunta y el corte de \"sin información\" pasa a decidirse por el puntaje del reranker, con un mínimo configurable calibrado con casos reales. Apagado por defecto, con un proveedor intercambiable por configuración, sin migraciones ni reindexación, con el mejor puntaje anotado en el registro de Uso. Se mide memoria, latencia, calidad y costo con la herramienta de la feature 005, con tope de gasto y autorización del usuario."

Contexto: la Consulta administrativa trae los 8 fragmentos más parecidos a la pregunta (16 con razonamiento), ordenados por la similitud de los vectores del modelo de embeddings local, y descarta los que no llegan al umbral de similitud (0,82). Si no queda ninguno, responde "sin información suficiente" sin llamar al modelo. La línea base y la feature 008 ([LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)) mostraron tres límites de ese diseño:

1. **La similitud de vectores no separa respuestas de no respuestas.** Los puntajes se amontonan entre 0,80 y 0,91: nombres y términos inventados puntúan 0,83 a 0,85 con una pregunta corta, igual que documentos reales. Ningún umbral sirve para todo (las opciones de bajar el umbral quedaron descartadas).
2. **El documento correcto queda fuera de los primeros resultados.** El documento esperado de una persona aparece en los puestos 12 a 43 aun buscando solo el nombre, es decir, fuera de los 8 que trae el modo literal. Para capturarlo bastan entre 20 y 40 candidatos, pero hoy no se piden.
3. **Un puntaje de vectores casi en el umbral descarta documentos buenos.** El documento de Cubillo puntúa 0,819 contra un umbral de 0,82.

Un *reranker* (modelo que lee juntas la pregunta y cada candidato y puntúa cuánto responde uno a la otra) ataca los tres: reordena una lista más larga y da un puntaje más fiable para decidir qué pasa y qué no. Esta feature es la opción E del documento de requerimientos de la versión 3 y se plantea como **prueba de costo**: se construye apagada, se mide cuánto cuesta en memoria, tiempo y dinero y cuánto mejora la calidad, y el usuario decide después si se conserva. El reranker corre dentro del propio servidor de la API: no se usa ningún servicio externo de reranking, porque recibiría la pregunta y los fragmentos (que incluyen actas con datos personales) y hoy esos datos solo salen hacia el proveedor de modelos de lenguaje con retención cero.

Límites conocidos desde ya: el reranker solo reordena lo que se recuperó, así que si el documento no entra entre los candidatos nunca aparece (es el caso de la pregunta sobre Deep Learning, cuyo programa queda en el puesto 50, y de las siglas como TFG o MGTI, que son un problema de vocabulario; los cubre la búsqueda híbrida, opción D).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Encontrar documentos que hoy quedan fuera de los primeros resultados (Priority: P1)

Una persona de Coordinación pregunta "¿Quién es Natalia Soto Solís?" o "¿Qué se sabe de Cibercrimen?" en modo literal. Con el reranker encendido, MIA recupera una lista más larga de candidatos, el reranker pone arriba los que de verdad hablan de lo preguntado y el modelo de lenguaje recibe esos. La persona obtiene la respuesta basada en el documento que hoy queda en el puesto 12 o más y no llega.

**Why this priority**: es el problema de recuperación que la feature 008 dejó sin resolver y la razón de ser de la opción E (BUS-1).

**Independent Test**: con el reranker encendido, hacer las preguntas de los casos S22-1, S22-3 y S22-4 de la línea base y las de personas y términos de la feature 008 (EN1 a EN12) en los dos modos, y comprobar que los casos cuyo documento esperado estaba entre los puestos 9 y 40 responden con ese documento.

**Acceptance Scenarios**:

1. **Given** una pregunta cuyo documento esperado está entre los puestos 9 y 40 de la búsqueda por similitud, **When** se consulta con el reranker encendido, **Then** ese documento llega al modelo entre los fragmentos mejor puntuados y la respuesta se basa en él.
2. **Given** una pregunta cuyo documento esperado puntúa justo bajo el umbral de similitud de vectores (como 0,819 contra 0,82), **When** el reranker lo puntúa sobre el mínimo propio, **Then** el documento llega al modelo.
3. **Given** el reranker encendido, **When** se hace una consulta, **Then** el número de fragmentos que llega al modelo de lenguaje es el mismo que hoy para ese modo (8 en literal, 16 con razonamiento) como máximo, de modo que el costo por consulta no sube por traer más candidatos.
4. **Given** una pregunta cuyo documento esperado no entra entre los candidatos recuperados (Deep Learning, siglas), **When** se consulta con el reranker, **Then** el resultado es el mismo que sin él y el caso queda reportado como límite de la recuperación, no como falla del reranker.

---

### User Story 2 - Seguir diciendo "sin información" cuando los documentos no la tienen (Priority: P1)

Una pregunta sobre una persona o un término que no está en ningún documento ("¿Quién es Fulano Inventado Pérez?") debe seguir respondiendo "sin información suficiente" sin llamar al modelo de lenguaje, aunque la similitud de vectores le dé 0,83 a 0,85. Con el reranker, esa decisión pasa a tomarla el puntaje del reranker: si ningún candidato lo supera, no se llama al modelo.

**Why this priority**: es la salvaguarda de la opción (BUS-3 y BUS-7). Un reranker mal calibrado, o un corte por puntaje demasiado bajo, hace llegar al modelo documentos de relleno y aumenta las respuestas inventadas y el costo.

**Independent Test**: medir los casos que esperan "sin información" (EN7 persona inventada, EN8 término inventado, A1 y los 4 de la batería del MVP) con el reranker encendido y comprobar que ninguno llama al modelo ni responde con contenido.

**Acceptance Scenarios**:

1. **Given** una pregunta sobre algo que no está en los documentos, **When** ningún candidato supera el puntaje mínimo del reranker, **Then** la respuesta es "sin información suficiente" sin llamar al modelo de lenguaje.
2. **Given** los casos de calibración (con respuesta y sin respuesta), **When** se fija el puntaje mínimo, **Then** existe un valor que deja pasar todos los casos que hoy responden bien y bloquea todos los de "sin información"; si no existe, la medición lo reporta como resultado (el reranker no basta) en lugar de ocultarlo.
3. **Given** el reranker encendido y una consulta con el mínimo propio sin superar, **When** se registra en Uso, **Then** queda anotado el mejor puntaje para poder revisar las "sin información" dudosas.

---

### User Story 3 - Poder apagarlo, cambiar de modelo y que un fallo no rompa la consulta (Priority: P1)

Quien opera MIA enciende o apaga el reranker con una variable de configuración, sin cambiar código ni migrar la base. Por defecto está apagado y MIA se comporta como antes de la feature. El reranker es una pieza intercambiable (como el modelo de embeddings o el de lenguaje): hay una implementación local y se pueden agregar otras, y un modelo distinto se prueba cambiando configuración. Si el modelo del reranker no carga o falla al puntuar, la consulta no se cae: sigue con el orden y el umbral de similitud de siempre y deja un aviso.

**Why this priority**: es la salvaguarda para probar en producción y volver atrás en minutos (BUS-6), y evita que una prueba de costo pueda dejar a MIA sin responder.

**Independent Test**: con el proveedor apagado, repetir la línea base y comprobar que respuestas, fuentes, costo y notas de Uso son las de antes; encenderlo; y simular un modelo que no carga o que falla para comprobar que la consulta responde con el orden por similitud y un aviso.

**Acceptance Scenarios**:

1. **Given** la configuración por defecto, **When** MIA responde, **Then** el comportamiento, el costo, las fuentes y el registro son idénticos a los de antes de la feature, y el modelo del reranker ni se descarga ni se carga en memoria.
2. **Given** el reranker encendido y un modelo que falla (archivo ausente, error al puntuar), **When** llega una consulta, **Then** la consulta responde con el orden y el umbral por similitud de vectores, deja un aviso en el registro del servidor y una nota en Uso, y no devuelve error.
3. **Given** un nombre de proveedor inválido, **When** el servicio arranca o responde, **Then** usa el comportamiento anterior (apagado) y deja un aviso, sin fallar.
4. **Given** que se vuelve a la versión etiquetada `prototipo-v2-estable`, **When** se leen los registros de consultas hechos con esta feature, **Then** se leen sin errores (sin cambios en la estructura de la base).
5. **Given** una consulta rechazada por permisos o por tope de gasto, **When** llega con el reranker encendido, **Then** se rechaza antes de buscar ni puntuar nada, como hoy.

---

### User Story 4 - Medir cuánto cuesta y cuánto mejora, y decidir si se conserva (Priority: P1)

Quien opera MIA mide el reranker en local con los datos de producción y, si el resultado es prometedor, en Railway: memoria de la API en reposo y con carga (con y sin el modelo), latencia añadida variando el número de candidatos, calidad con el conjunto de casos de la línea base, y cambio en el costo mensual del servicio. Con eso decide con datos si lo conserva, lo deja apagado o pasa a la búsqueda híbrida.

**Why this priority**: la feature es una prueba de costo; sin la medición no hay decisión. Es lo que justifica construirla.

**Independent Test**: correr las mediciones con el reranker apagado (control) y encendido, comparar con la herramienta de la feature 005 y leer en el informe memoria, latencia p50 y p95, cambios de calidad por caso y costo.

**Acceptance Scenarios**:

1. **Given** el conjunto de casos de la línea base (`scripts/datos/casos_busqueda.json`), **When** se mide con la herramienta, **Then** el informe muestra por caso y por modo el puesto del documento esperado, el puntaje del reranker, si el caso pasó el corte y cómo cambió contra la corrida de control.
2. **Given** distintos números de candidatos, **When** se mide la latencia, **Then** el informe muestra la latencia añadida p50 y p95 por cada número, para escoger el número con menor costo que capture el documento esperado.
3. **Given** la API en reposo con el reranker apagado y encendido, **When** se mide la memoria, **Then** el informe muestra la diferencia, y si cabe en el plan actual del servidor o exige subir de plan.
4. **Given** la medición completa, **When** se evalúan los criterios para conservarlo, **Then** el informe dice si cada criterio se cumple y la recomendación (conservar, dejar apagado, pasar a la búsqueda híbrida), y la decisión queda en manos del usuario.
5. **Given** que las respuestas medidas gastan tokens, **When** se pide medir con respuestas, **Then** se fija y autoriza un tope de gasto antes de correr; la medición de puntajes (sin llamar al modelo) no cuesta.

---

### Edge Cases

- El documento esperado queda más allá del último candidato recuperado: el reranker no lo ve; se reporta como límite de la recuperación (Deep Learning, siglas) y no se considera falla de la feature.
- Dos candidatos del mismo documento: el reranker puntúa cada fragmento por separado; las fuentes y las citas de la feature 006 funcionan igual con los fragmentos que llegan al modelo.
- Un fragmento más largo de lo que el reranker puede leer de una vez: se puntúa con lo que cabe del inicio y se documenta como límite; el modelo de lenguaje sigue recibiendo el fragmento completo.
- Ningún candidato (la colección o los dominios del artefacto no devuelven nada): no se invoca al reranker y la respuesta es la de hoy.
- El reranker puntúa dos candidatos idénticos: el orden entre ellos es estable (el de la similitud de vectores).
- La pregunta limpia de la feature 008 está encendida y hay segundo intento: el reranker puntúa los candidatos del intento que se use; el segundo intento solo ocurre si el primero no deja nada que pase el corte.
- La consulta llega con razonamiento (más fragmentos): se recuperan más candidatos que en literal pero al modelo de lenguaje no llega más de lo que hoy configura el modo.
- El modelo del reranker tarda más de lo esperado en la primera consulta tras arrancar (carga diferida): la primera consulta puede ser más lenta; se mide y se documenta, y el servicio no se queda sin responder mientras carga.
- Se encienden juntas varias opciones (fuentes citadas, respuestas completas, pregunta limpia, reranker): cada una funciona como lo hace sola y las notas de Uso conviven sin pisarse.
- El mínimo configurable del reranker queda mal puesto (muy alto o muy bajo): con muy alto la API responde "sin información" a todo; con muy bajo, llama al modelo con relleno. Ambos efectos se detectan con los casos de calibración y con la nota del mejor puntaje en Uso.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Debe existir una pieza de reranking intercambiable por configuración (nombre de proveedor), igual que el modelo de embeddings, el de lenguaje y el almacén de vectores: con el valor por defecto, ninguno, el comportamiento es el de antes de la feature; con el valor local, se usa un modelo que corre dentro del propio servidor de la API.
- **FR-002**: No debe enviarse ninguna pregunta ni ningún fragmento a un servicio externo de reranking. El único destino externo de los textos de una consulta sigue siendo el proveedor de modelos de lenguaje ya configurado.
- **FR-003**: Con el reranker encendido, la API debe recuperar de la búsqueda por similitud un número de candidatos mayor que el actual del modo, configurable (rango de trabajo de 20 a 40), pedir al reranker que los puntúe contra la pregunta y reordenarlos de mayor a menor puntaje.
- **FR-004**: Con el reranker encendido, el corte de "sin información" y la selección de fragmentos que llegan al modelo de lenguaje deben decidirse por el puntaje del reranker contra un mínimo configurable, y no por el umbral de similitud de vectores. Si ningún candidato supera el mínimo, la respuesta es "sin información suficiente" sin llamar al modelo de lenguaje.
- **FR-005**: El número de fragmentos que llega al modelo de lenguaje no debe superar el que el modo ya configura hoy (8 en literal, 16 con razonamiento, o el que resulte de la feature 007 si está encendida), de modo que traer más candidatos no suba el costo del modelo de lenguaje.
- **FR-006**: El mínimo del reranker debe ser configurable por variable de entorno, con un valor por defecto fijado con la calibración (que debe salir de casos con respuesta y de casos sin respuesta); la calibración y sus datos quedan documentados.
- **FR-007**: Si el reranker no está disponible (el modelo no carga, el archivo falta, falla al puntuar o excede un tiempo máximo), la consulta debe continuar con el orden y el umbral por similitud de vectores de siempre, dejar un aviso en el registro del servidor (limitado, no una línea por consulta) y una nota en Uso, y nunca devolver un error por esa causa.
- **FR-008**: El modelo del reranker no debe descargarse ni cargarse en memoria cuando el proveedor es ninguno; con el proveedor local debe cargarse una sola vez y de forma diferida o al arrancar según lo que el plan establezca tras medir su efecto en memoria y tiempo de arranque.
- **FR-009**: Un nombre de proveedor inválido debe tratarse como ninguno y dejar un aviso (una vez) en el registro del servidor, sin hacer fallar el arranque ni la consulta.
- **FR-010**: El registro de consultas del módulo Uso debe anotar, cuando el reranker intervino, el mejor puntaje obtenido (y si fue el corte el que hizo responder "sin información"), y, cuando el reranker falló, que se cayó al orden por similitud. Esta anotación convive con las demás notas del registro (features 006, 007 y 008) en el mismo orden estable, y no requiere cambios en la estructura de la base de datos, de modo que volver a la versión `prototipo-v2-estable` siga siendo posible.
- **FR-011**: Con el reranker apagado, la búsqueda, el contexto, la respuesta, las fuentes, el costo y el registro deben ser idénticos a los de antes de la feature (BUS-6).
- **FR-012**: El reranker no debe agregar ninguna llamada a un modelo de lenguaje: una consulta sin respuesta tras el reranking no gasta tokens (BUS-7, BUS-4). Los topes de gasto por artefacto y de toda la API se siguen evaluando antes de buscar, como hoy.
- **FR-013**: La respuesta de la API conserva su estructura; el reranker no es visible para quien consulta salvo por su efecto. No se requieren migraciones ni reindexar los documentos.
- **FR-014**: Las citas por fragmento (feature 006), el contexto completo y el reintento por corte (feature 007) y la pregunta limpia (feature 008) deben seguir funcionando con los fragmentos que salen del reranker; la pregunta limpia, si está encendida, solo se usa cuando la búsqueda con el reranker no deja ningún fragmento sobre su mínimo.
- **FR-015**: La herramienta de medición de la feature 005 debe registrar por consulta, con el reranker encendido, el puesto del documento esperado antes y después del reranking, el mejor puntaje del reranker, la latencia añadida y si hubo caída al orden por similitud; resumirlos por modo y comparar corridas con y sin el reranker. Debe poder calcular los puntajes del reranker sin llamar al modelo de lenguaje (sin costo) para calibrar el mínimo.
- **FR-016**: Debe existir un procedimiento documentado para medir memoria (API en reposo y bajo carga, con y sin el modelo cargado, en local y en Railway), latencia añadida (p50 y p95 según el número de candidatos) y cambio en el costo mensual, y los resultados deben quedar en la documentación junto a la recomendación.
- **FR-017**: El modelo de reranking que se pruebe primero debe cumplir: entiende español, se puede ejecutar sin PyTorch (formato ONNX, cuantizado a enteros de 8 bits, con la misma pila de ejecución que el modelo de embeddings), licencia que permita su uso en este proyecto, y tamaño en memoria que quepa según los límites del plan actual. La selección entre los candidatos (decisión pendiente del usuario) y la fuente del archivo del modelo se fijan en el plan tras verificarlos.
- **FR-018**: Deben existir pruebas automáticas con un reranker simulado de: la fábrica y los valores de configuración (ninguno, local, inválido), el reordenamiento y el corte por puntaje, el número máximo de fragmentos al modelo, la respuesta "sin información" sin llamar al modelo, la caída al orden por similitud cuando el reranker falla, las notas de Uso y su convivencia con las de las features 006 a 008, y que con el proveedor apagado nada cambia; sin cargar modelos reales ni llamar a proveedores externos. La documentación debe describir las variables, cómo encenderlo y cómo medir.

### Key Entities *(include if feature involves data)*

- **Reranker (proveedor de reranking)**: la pieza que recibe la pregunta y una lista de fragmentos candidatos y devuelve un puntaje por fragmento; hay una implementación que no hace nada (ninguno) y una local; se elige por configuración.
- **Candidatos**: la lista más larga de fragmentos que la búsqueda por similitud devuelve cuando el reranker está encendido, antes de reordenar y cortar.
- **Puntaje del reranker**: el número que el reranker asigna a cada candidato; no equivale a la similitud de vectores ni es comparable con ella, y se corta con su propio mínimo.
- **Mínimo del reranker**: el puntaje por debajo del cual un candidato no llega al modelo de lenguaje; se calibra con casos reales (con y sin respuesta).
- **Nota del reranker**: la anotación del registro de Uso con el mejor puntaje y, si corresponde, la caída al orden por similitud.
- **Informe de la prueba de costo**: el resultado de medir memoria, latencia, calidad y costo, con la recomendación de conservar, dejar apagado o pasar a la búsqueda híbrida.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: De los casos de la línea base cuyo documento esperado queda en la búsqueda por similitud entre los puestos 9 y 40 (como Natalia Soto Solís en literal), todos responden con ese documento con el reranker encendido; los que quedan más allá del último candidato (Deep Learning, siglas) se reportan aparte como límite de la recuperación y no cuentan contra el criterio.
- **SC-002**: El 100 % de los casos que esperan "sin información" (EN7, EN8, A1 y los 4 de la batería del MVP) siguen respondiéndola sin llamar al modelo de lenguaje con el reranker encendido y el mínimo calibrado.
- **SC-003**: Los 19 casos de la batería del MVP siguen respondiendo igual: ninguno empeora (BUS-3), tanto en literal como con razonamiento.
- **SC-004**: Con el reranker apagado, el texto, las fuentes y las notas de Uso de cada caso son los de la línea base (sin diferencias atribuibles a la feature).
- **SC-005**: El reranker encendido no suma ninguna llamada a un modelo de lenguaje por consulta ni sube el costo medio por consulta más allá del ruido medido en la corrida de control (BUS-4).
- **SC-006**: La latencia añadida por el reranker, medida con el número de candidatos elegido, queda dentro del límite que el usuario acepte (propuesta de trabajo: p50 de hasta 0,5 s y p95 de hasta 1,5 s en literal, con el tiempo total del cliente bajo los 3 s de p50 actuales más ese margen); el informe muestra los valores reales para cada número de candidatos.
- **SC-007**: La memoria de la API con el modelo cargado queda dentro del límite que el usuario acepte (propuesta de trabajo: la API completa por debajo de los 512 MB de RAM en reposo y el costo mensual dentro de los 5 USD incluidos en el plan, sin subir de plan); el informe muestra los valores reales de memoria en reposo y bajo carga, con y sin el modelo.
- **SC-008**: Si el reranker falla (modelo ausente o error al puntuar), el 100 % de las consultas simuladas con esa falla responden como sin reranker, con aviso y nota, y ninguna devuelve error (prueba automática).
- **SC-009**: El informe de la prueba de costo concluye explícitamente, con los datos medidos, una de tres recomendaciones (conservar, dejar apagado, pasar a la búsqueda híbrida) y lista para cada criterio de conservación si se cumple o no.

## Assumptions

- Quien opera MIA es una sola persona (el usuario); quien consulta es el personal de Coordinación mediante la Consulta administrativa.
- El comportamiento por defecto sigue siendo el actual hasta que la medición respalde encender el reranker; encenderlo en producción es una decisión posterior del usuario, fuera de esta feature.
- Las tres decisiones pendientes de la sección 2.8 del documento de requerimientos de la versión 3 se tratan así hasta que el usuario las cierre (por `/speckit-clarify` o al revisar esta spec): (1) el reranker local no suma costo de modelos de lenguaje, así que el gasto aceptable por consulta sin respuesta es cero adicional; (2) los límites de memoria y latencia de SC-006 y SC-007 son una propuesta de trabajo, y el informe muestra los valores reales para que el usuario decida con datos; (4) el primer modelo a probar es el cross-encoder multilingüe pequeño de la familia MiniLM (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`) si se verifica su ONNX, tamaño y licencia, y uno más grande de la familia BGE o Jina multilingüe se prueba solo como referencia de calidad.
- Para capturar el documento esperado bastan entre 20 y 40 candidatos (dato de la línea base); el número exacto se elige con la medición de latencia y calidad por candidatos.
- El puntaje del reranker no es el coseno: el mínimo se calibra con casos reales, con casos con respuesta y casos sin respuesta, y es posible que los datos no permitan un mínimo que separe todos los casos; en ese caso el resultado de la prueba es negativo y se reporta.
- La verificación usa la herramienta de la feature 005: los puntajes se calculan sin llamar al modelo de lenguaje (sin costo) primero en local y luego contra producción en solo lectura; la medición con respuestas se hace reducida, con un tope de gasto fijado y autorizado por el usuario antes de correr, y una corrida de control con el reranker apagado. Como la API de producción corre en Railway sin el reranker (producción aún no tiene las features 005 a 008), la medición en Railway exige desplegar `dev` temporalmente según el procedimiento ya establecido.
- La memoria y la latencia reales del reranker en Railway se miden con el servicio encendido solo mientras dura la medición; se apaga al terminar.
- El comportamiento del modelo de lenguaje no es del todo determinista: un caso que cambie de resultado entre corridas se repite antes de contarse como regresión.
- Quedan fuera de esta feature: cualquier API externa de reranking, la búsqueda híbrida (opción D, siglas), el contexto por fragmento (opción G), bajar el umbral (opciones A y C), reformular con un modelo de lenguaje, entrenar o ajustar (*fine-tuning*) un modelo propio, y cambios visuales de la Consulta o del panel.
