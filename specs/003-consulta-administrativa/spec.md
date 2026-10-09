# Feature Specification: Consulta administrativa de MIA

**Feature Branch**: `dev` (feature `003-consulta-administrativa`)

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Artefacto 2: Consulta administrativa de MIA, según la sección 3 de docs/Definicion_Requerimientos_V2.md (requerimientos CON-1 a CON-10 y modos de respuesta de la sección 3.3), con los criterios de aceptación de la sección 8 que le corresponden (1, 7, 8, 9, 10, 17) y el stack y despliegue de la sección 7. Un cliente web de consulta para el personal administrativo (Coordinación y Asistencia Administrativa) que pregunta en lenguaje natural sobre los dominios permitidos y elige respuesta literal o con razonamiento. Se publican dos instancias de la misma compilación (Postgrados Computación y Postgrados Administración Empresas), cada una abierta con su clave de artefacto; el nombre, los dominios y los modos vienen de la API según la clave. Reemplaza al cliente actual de web/ (pasa a web/consulta/). Incluye los cambios de API que quedaron pendientes del artefacto 1 (FR-026 de specs/002-panel-administracion): instrucción al modelo y cantidad de fragmentos recuperados distintos por modo (literal: la instrucción actual y 8 resultados; con razonamiento: puede combinar, comparar y calcular mostrando los datos usados y separando lo que dice el documento de lo que infiere, sin conocimiento externo, y más resultados, p. ej. 16). La API, los artefactos, los permisos, los topes, el registro de consultas y la calificación ya existen (specs/002-panel-administracion). Fuera de alcance: memoria de conversación y preguntas de agregación sobre todo un dominio (sección 10). Trabajar en la rama dev."

La fuente de verdad de los requerimientos es [docs/Definicion_Requerimientos_V2.md](../../docs/Definicion_Requerimientos_V2.md), sección 3. Los identificadores entre corchetes (por ejemplo [CON-3]) remiten a ese documento. La gestión de artefactos, permisos, topes y el registro de consultas en la API ya se construyeron en [specs/002-panel-administracion](../002-panel-administracion/spec.md); esta especificación solo agrega lo que la Consulta necesita encima de eso.

## Clarifications

### Session 2026-10-08

- Q: ¿Qué debe pasar con la conversación cuando la persona recarga la página o cierra la pestaña? → A: No se conserva: al recargar, la conversación empieza vacía; solo se recuerdan la clave, los dominios y el modo.
- Q: En una respuesta con razonamiento, ¿cómo debe separarse lo que dicen los documentos de lo que el sistema calcula o infiere? → A: Dos partes fijas: primero "Lo que dicen los documentos" (los datos usados, con su documento) y después "Cálculo o conclusión" (la operación y el resultado).
- Q: ¿Cuánto debe tardar como máximo una respuesta para considerarla aceptable en la evaluación con usuarios? → A: Literal en menos de 15 s y con razonamiento en menos de 90 s, en 9 de cada 10 preguntas.
- Q: Al publicar la Consulta, ¿qué hacemos con el cliente web actual de la carpeta web/? → A: Se elimina en esta misma entrega; la Consulta es un cliente nuevo y la documentación remite a ella.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preguntar sobre los dominios de mi unidad y ver de dónde sale la respuesta (Priority: P1)

Una persona de Coordinación o de Asistencia Administrativa abre el enlace de la Consulta de su unidad, ingresa la clave que le dio quien administra MIA, ve el nombre de su instancia y los dominios que puede consultar, elige uno o varios, escribe una pregunta y recibe una respuesta con formato, con los documentos citados y los fragmentos que la respaldan.

**Why this priority**: es el propósito del artefacto y lo mínimo que reemplaza al cliente actual. Sin esto no hay evaluación con usuarios. Funciona solo con el modo literal, que ya existe en la API.

**Independent Test**: abrir la instancia de Postgrados Computación con su clave, preguntar en modo literal por un acuerdo de un acta y verificar que la respuesta cita el acta con su dominio y que los fragmentos se pueden desplegar; repetir la pregunta en la instancia de Administración de Empresas y verificar que ese dominio ni siquiera aparece.

**Acceptance Scenarios**:

1. **Given** una instancia abierta por primera vez, **When** se carga, **Then** pide la clave de consulta; **When** se ingresa una válida, **Then** la recuerda en ese navegador y no la vuelve a pedir [CON-9].
2. **Given** una clave válida, **When** se abre la instancia, **Then** el encabezado y el título de la pestaña muestran el nombre del artefacto que devuelve la API (por ejemplo "Consulta administrativa Postgrados Administración Empresas") [CON-10].
3. **Given** un artefacto con acceso a una unidad, **When** se abre la instancia, **Then** se listan solo los dominios de esa unidad, con una casilla por dominio y las opciones "todos" y "ninguno"; si el artefacto tiene dominios de más de una unidad, aparecen agrupados por unidad [CON-1].
4. **Given** ningún dominio seleccionado, **When** se intenta preguntar, **Then** no se puede enviar y se indica que hay que elegir al menos uno [CON-1].
5. **Given** una selección de dominios, **When** se recarga la página, **Then** la selección se conserva; los dominios guardados que el artefacto ya no tiene permitidos se descartan sin error [CON-1].
6. **Given** una pregunta enviada, **When** llega la respuesta, **Then** se muestra como un mensaje de conversación con negritas y listas, y debajo los documentos citados (con su dominio) y los fragmentos desplegables [CON-4].
7. **Given** una pregunta enviada, **When** se espera, **Then** se ve que está trabajando; al llegar, la respuesta indica con qué modo se generó y cuánto tardó [CON-5].
8. **Given** una pregunta cuya respuesta no está en los documentos, **When** llega la respuesta, **Then** se distingue visualmente de una respuesta con información y no muestra fuentes [CON-6].
9. **Given** la clave de la instancia de Administración de Empresas, **When** se envía directamente a la API una consulta sobre un dominio de Computación, **Then** se rechaza como prohibida, y lo mismo al revés (criterio 17 de la sección 8).
10. **Given** una clave guardada que dejó de ser válida (se regeneró en el panel), **When** se abre la instancia o se pregunta, **Then** se explica que la clave ya no es válida, se olvida y se pide la nueva.

---

### User Story 2 - Elegir una respuesta con razonamiento para preguntas que combinan datos (Priority: P1)

La misma persona necesita respuestas que sumen, comparen o cuenten datos de varios documentos (por ejemplo, los créditos de tres cursos). Antes de preguntar elige el modo "Con razonamiento", que tarda más y cuesta más, y recibe una respuesta que muestra los datos que usó y separa lo que dicen los documentos de lo que el sistema infiere, sin recurrir a conocimiento externo.

**Why this priority**: es la diferencia principal frente al cliente actual y el motivo de los dos modos de la versión 2. Incluye los cambios de la API que quedaron pendientes del artefacto 1: una instrucción al modelo y una cantidad de fragmentos propias de cada modo.

**Independent Test**: en la instancia de Computación, en modo con razonamiento, preguntar "¿Cuántos créditos suman Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de Experimentos?" y verificar que responde 12, muestra los créditos de cada curso y cita los tres programas; hacer la misma pregunta en modo literal y verificar que se comporta como hoy.

**Acceptance Scenarios**:

1. **Given** un artefacto con los dos modos permitidos, **When** se abre la instancia, **Then** hay un selector entre "Literal" y "Con razonamiento", con una explicación corta de cada uno junto al selector; el modo elegido se recuerda [CON-2].
2. **Given** un artefacto con un solo modo permitido, **When** se abre la instancia, **Then** no se muestra el selector y se usa ese modo; un modo no permitido no aparece en ninguna parte [CON-2, CON-3].
3. **Given** el modo con razonamiento elegido, **When** se espera la respuesta, **Then** se avisa que puede tardar más que el literal [CON-5].
4. **Given** el modo con razonamiento, **When** se pregunta por la suma de créditos de Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de Experimentos, **Then** la respuesta es 12, muestra el dato de cada curso y la operación (por ejemplo "4 + 4 + 4 = 12"), y cita los tres programas (criterio 7 de la sección 8).
5. **Given** el modo con razonamiento, **When** llega una respuesta con información, **Then** tiene dos partes en este orden: "Lo que dicen los documentos" (cada dato usado con el documento de donde sale) y "Cálculo o conclusión" (la operación y el resultado, o lo que se deduce).
6. **Given** el modo con razonamiento, **When** se busca en los documentos, **Then** se recuperan más fragmentos que en el modo literal (16 frente a 8 por defecto), para que entren datos de más documentos.
7. **Given** el modo literal, **When** se pregunta, **Then** la instrucción al modelo y la cantidad de fragmentos son las de hoy, y el script de pruebas de aceptación sigue dando 19 de 19.
8. **Given** cualquiera de los dos modos, **When** ninguno de los fragmentos trata el tema, **Then** la respuesta es "sin información suficiente", sin fuentes.

---

### User Story 3 - Saber por qué no puedo preguntar y recuperarme de un error (Priority: P2)

Si el modo con razonamiento no está disponible, si la Consulta alcanzó su tope de gasto del día o si algo falla al responder, la persona ve el motivo en palabras claras y tiene una salida: reintentar, cambiar a modo literal o esperar a la medianoche.

**Why this priority**: los topes y los errores del proveedor ya los aplica la API; sin esta historia la Consulta solo mostraría fallos opacos. Es importante para la evaluación con usuarios, pero la Consulta es usable sin ella en condiciones normales.

**Independent Test**: en un artefacto de prueba, bajar mucho el tope del modo con razonamiento desde el panel, hacer consultas hasta alcanzarlo y verificar que la opción queda deshabilitada con su motivo mientras el literal sigue funcionando; subir el tope y verificar que la consulta siguiente funciona.

**Acceptance Scenarios**:

1. **Given** una instancia sin modelo configurado para el modo con razonamiento, **When** se abre, **Then** esa opción aparece deshabilitada con el motivo (criterio 9 de la sección 8) [CON-3].
2. **Given** un artefacto que alcanzó su tope diario del modo con razonamiento, **When** se abre o se actualiza la instancia, **Then** esa opción aparece deshabilitada con el motivo y cuándo se reinicia (a la medianoche, hora de Costa Rica), y el modo literal sigue disponible; otro artefacto puede seguir usando el modo con razonamiento (criterio 8 de la sección 8) [CON-3].
3. **Given** un artefacto que alcanzó su tope total, o la API que alcanzó el suyo, **When** se abre la instancia, **Then** el envío de preguntas queda deshabilitado hasta la medianoche, con el motivo [CON-3].
4. **Given** un tope alcanzado durante el uso (la respuesta de la API es "tope alcanzado"), **When** se recibe, **Then** se muestra el motivo y la Consulta actualiza los modos disponibles sin recargar la página.
5. **Given** un error al responder (el modelo saturado, sin conexión o tiempo agotado), **When** ocurre, **Then** se muestra un mensaje claro y un botón para reintentar la misma pregunta; si el modo era con razonamiento, se ofrece además reintentar en modo literal [CON-7].
6. **Given** un artefacto desactivado desde el panel, **When** se pregunta, **Then** se explica que la Consulta fue desactivada y que hay que comunicarse con quien administra MIA.
7. **Given** un tope subido desde el panel, **When** se hace la consulta siguiente, **Then** funciona sin reiniciar la API ni volver a publicar la Consulta.

---

### User Story 4 - Calificar cada respuesta (Priority: P2)

Después de leer una respuesta, la persona la marca como útil o no útil y, si quiere, agrega un comentario. Esa calificación queda guardada junto a la consulta y es la base de las métricas de la evaluación con usuarios.

**Why this priority**: es el insumo de la evaluación con usuarios (objetivo específico 5). La API ya guarda la calificación; falta la interfaz.

**Independent Test**: calificar una respuesta como no útil con un comentario y verificar en el registro de consultas del panel (módulo Uso) que la consulta tiene esa calificación y ese comentario.

**Acceptance Scenarios**:

1. **Given** una respuesta (con información o "sin información"), **When** se marca como útil o no útil, **Then** la calificación queda guardada junto a esa consulta (criterio 10 de la sección 8) [CON-8].
2. **Given** una calificación elegida, **When** se agrega un comentario opcional y se envía, **Then** el comentario queda guardado con la calificación [CON-8].
3. **Given** una respuesta ya calificada, **When** se cambia la calificación, **Then** la nueva reemplaza a la anterior.
4. **Given** una respuesta con error (no llegó a responderse), **When** se muestra, **Then** no ofrece calificación.

---

### User Story 5 - Dos instancias publicadas de la misma Consulta (Priority: P3)

Quien mantiene MIA publica la misma compilación de la Consulta en dos direcciones, una por unidad, y entrega a cada equipo su enlace y su clave. Un dominio nuevo creado en el panel en una unidad aparece en la Consulta de esa unidad sin volver a publicar nada, y no en la otra.

**Why this priority**: es la forma de entrega final, pero las historias 1 a 4 se pueden validar en desarrollo sin publicar. Reemplaza al cliente actual, que es transitorio.

**Independent Test**: publicar la Consulta en dos direcciones, abrir cada una con su clave y verificar que cada una muestra su nombre y solo sus dominios; crear un dominio en la unidad Computación desde el panel y verificar que aparece al recargar la instancia de Computación y no en la de Administración de Empresas.

**Acceptance Scenarios**:

1. **Given** una sola compilación publicada en dos direcciones, **When** se abre cada una con su clave, **Then** cada una muestra su propio nombre, dominios y modos, sin configuración distinta en la compilación.
2. **Given** las dos direcciones abiertas en el mismo navegador, **When** se usa cada una, **Then** cada una recuerda su propia clave, selección de dominios y modo, sin mezclarlas.
3. **Given** un dominio nuevo creado desde el panel en la unidad Computación, **When** se recarga la instancia de Computación, **Then** aparece sin reiniciar la API ni volver a publicar la Consulta; en la instancia de Administración de Empresas no aparece (criterio 1 de la sección 8).
4. **Given** esta entrega terminada, **When** se revisa el repositorio, **Then** el cliente anterior de consulta ya no existe y la documentación remite a la Consulta.

---

### Edge Cases

- La persona recarga la página: la conversación anterior no se conserva (cada pregunta se responde por separado y las preguntas pueden contener datos personales); sí se conservan la clave, la selección de dominios y el modo.
- Se escribe una pregunta vacía o solo con espacios: no se puede enviar.
- Se envía una pregunta mientras otra espera respuesta: no se permite enviar otra hasta que llegue la primera, para no superar los topes con consultas en paralelo.
- La respuesta tarda mucho (la API arrancando más razonamiento): la Consulta espera hasta 200 segundos antes de darla por perdida y ofrecer reintentar.
- El artefacto pierde el acceso a un dominio seleccionado entre la carga de la página y el envío: la API rechaza la consulta como prohibida; la Consulta lo explica y actualiza la lista de dominios.
- El modo guardado en el navegador deja de estar permitido o disponible: se elige el primero disponible y se avisa del cambio.
- El artefacto no tiene ningún dominio que exista todavía (unidad recién creada y vacía): se explica que no hay dominios para consultar.
- La respuesta del modelo trae texto con apariencia de código HTML: se muestra como texto, nunca se interpreta.
- Sin almacenamiento disponible en el navegador (modo privado estricto): la Consulta funciona, pero pide la clave en cada visita.
- La API responde que la consulta no es válida por sus datos (por ejemplo, una pregunta demasiado larga): se muestra el motivo sin perder lo escrito.

## Requirements *(mandatory)*

### Functional Requirements

**Acceso e identidad de la instancia**

- **FR-001**: La Consulta DEBE pedir la clave de consulta la primera vez, recordarla en el navegador, permitir cambiarla, y olvidarla y volver a pedirla cuando la API la rechace como no autorizada [CON-9].
- **FR-002**: La Consulta DEBE mostrar en el encabezado y en el título de la pestaña el nombre del artefacto que la API devuelve para esa clave [CON-10].
- **FR-003**: Una misma compilación de la Consulta DEBE servir para cualquier instancia: el nombre, los dominios, los modos y los topes se obtienen de la API según la clave, nunca de la configuración de la compilación.

**Dominios**

- **FR-004**: La Consulta DEBE mostrar solo los dominios que el artefacto tiene permitidos, agrupados por unidad académica si son de más de una, con una casilla por dominio y las acciones "todos" y "ninguno" [CON-1].
- **FR-005**: La Consulta NO DEBE permitir enviar una pregunta sin al menos un dominio seleccionado [CON-1].
- **FR-006**: La selección de dominios DEBE recordarse en el navegador; la primera vez se seleccionan todos, y los dominios guardados que ya no estén permitidos se descartan [CON-1].

**Modos de respuesta**

- **FR-007**: La Consulta DEBE ofrecer, antes de cada pregunta, los modos que el artefacto tiene permitidos (Literal, Con razonamiento), con una explicación corta de cada uno; si tiene uno solo, no muestra el selector. El modo elegido se recuerda [CON-2].
- **FR-008**: Un modo permitido pero no disponible (sin modelo configurado o con su tope del día alcanzado) DEBE aparecer deshabilitado con el motivo; un modo no permitido NO DEBE mostrarse [CON-3].
- **FR-009**: Si el artefacto alcanzó su tope total del día, o la API alcanzó el suyo, la Consulta DEBE deshabilitar el envío de preguntas con el motivo y cuándo se reinicia (a la medianoche, hora de Costa Rica) [CON-3].
- **FR-010**: En modo literal, el sistema DEBE responder con la instrucción al modelo actual (solo lo que dicen los fragmentos, lo más textual posible) y con la cantidad de fragmentos actual (8 resultados más sus vecinos) [sección 3.3].
- **FR-011**: En modo con razonamiento, el sistema DEBE usar una instrucción al modelo que le permita combinar, comparar y calcular a partir de los fragmentos, sin usar conocimiento externo, y que estructure cada respuesta con información en dos partes fijas, en este orden: "Lo que dicen los documentos" (cada dato usado con el documento de donde sale) y "Cálculo o conclusión" (la operación, por ejemplo "4 + 4 + 4 = 12", y el resultado, o lo que se deduce) [sección 3.3].
- **FR-012**: En modo con razonamiento, el sistema DEBE recuperar más fragmentos que en el modo literal (16 resultados por defecto). La cantidad de cada modo DEBE poder ajustarse por configuración de la instancia, sin cambiar código.
- **FR-013**: En ambos modos, si ningún fragmento trata el tema de la pregunta, la respuesta DEBE ser la de "sin información suficiente", sin fuentes, y toda respuesta con información DEBE citar sus documentos y dominios de origen.

**Conversación y respuestas**

- **FR-014**: La Consulta DEBE mostrar las preguntas y respuestas como conversación, con el formato básico de la respuesta (negritas y listas) y, debajo de cada respuesta, los documentos citados con su dominio y los fragmentos desplegables [CON-4].
- **FR-015**: Cada respuesta DEBE indicar el modo con que se generó y cuánto tardó. Mientras espera, la Consulta DEBE mostrar que está trabajando y, en modo con razonamiento, avisar que puede tardar más [CON-5].
- **FR-016**: La respuesta "sin información suficiente" DEBE distinguirse visualmente de una respuesta con información [CON-6].
- **FR-017**: Ante un error (modelo no disponible, sin conexión, tiempo agotado, tope alcanzado, permiso rechazado, artefacto desactivado), la Consulta DEBE mostrar un mensaje claro en español y, si tiene sentido reintentar, un botón para hacerlo; en modo con razonamiento DEBE ofrecer además reintentar en modo literal [CON-7].
- **FR-018**: Cuando la API rechace una consulta por tope o por permisos, la Consulta DEBE actualizar los dominios y modos disponibles sin recargar la página.
- **FR-019**: La Consulta NO DEBE permitir enviar una pregunta nueva mientras espera la respuesta de la anterior, y DEBE esperar hasta 200 segundos antes de dar una respuesta por perdida.
- **FR-020**: Cada pregunta DEBE responderse por separado; la Consulta NO DEBE enviar el historial de la conversación ni guardarlo en el navegador de ninguna forma: al recargar la página o cerrar la pestaña, la conversación empieza vacía. Solo se recuerdan la clave, la selección de dominios y el modo.
- **FR-021**: El texto de las respuestas y de los fragmentos DEBE mostrarse como texto: nunca se interpreta como código de la página.

**Calificación**

- **FR-022**: La Consulta DEBE permitir calificar cada respuesta (con información o sin ella) como útil o no útil, con un comentario opcional, y guardarlo junto a la consulta; una calificación nueva reemplaza a la anterior [CON-8].

**Publicación y reemplazo del cliente actual**

- **FR-023**: La Consulta DEBE poder publicarse como sitio estático en varias direcciones a partir de una sola compilación, cada una con su propio almacenamiento de clave, selección y modo.
- **FR-024**: La Consulta DEBE reemplazar al cliente de consulta actual en esta misma entrega: la Consulta es un cliente nuevo, el cliente anterior se elimina y la documentación (instrucciones de uso, publicación y operación) remite a la Consulta.
- **FR-025**: La interfaz DEBE estar en español, funcionar en pantallas de computadora y de celular, y tener modo claro y oscuro.

**Pruebas y compatibilidad**

- **FR-026**: Cada cambio de la API (instrucción y cantidad de fragmentos por modo) DEBE tener pruebas automáticas, y las funciones de la Consulta que no dependen de la red (formato de respuestas, agrupación y recuerdo de la selección, elección del modo disponible) DEBEN tener pruebas automáticas.
- **FR-027**: El script de pruebas de aceptación DEBE seguir dando 19 de 19 en modo literal, y DEBE poder correr en modo con razonamiento.

### Key Entities

- **Instancia de la Consulta**: una publicación de la Consulta en una dirección, abierta con la clave de un artefacto registrado en el panel. Su nombre, dominios, modos y topes son los del artefacto.
- **Modo de respuesta**: Literal o Con razonamiento. Cada uno tiene un nombre y una descripción para la persona usuaria, un modelo, una instrucción al modelo y una cantidad de fragmentos a recuperar, configurados en la instancia de la API.
- **Pregunta y respuesta**: cada pregunta enviada con sus dominios y su modo, y la respuesta con su texto, fuentes, modo, tiempo y su identificador para calificarla. Queda en el registro de consultas de la API; en la Consulta solo vive mientras la página está abierta.
- **Calificación**: útil o no útil, con comentario opcional, asociada a una consulta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona que recibe el enlace y la clave de su instancia hace su primera pregunta y obtiene una respuesta con fuentes en menos de 2 minutos, sin ayuda.
- **SC-002**: En modo con razonamiento, la pregunta por la suma de créditos de Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de Experimentos responde 12, con el dato de cada curso y los tres programas citados.
- **SC-003**: En modo literal, las pruebas de aceptación siguen dando 19 de 19.
- **SC-004**: El 100 % de los intentos de una instancia de consultar dominios de otra unidad se rechazan, aun enviados directamente a la API sin pasar por la Consulta.
- **SC-005**: Un dominio creado en el panel aparece en la instancia de su unidad al recargarla, sin reiniciar la API ni volver a publicar la Consulta.
- **SC-006**: Cuando un modo o el envío no están disponibles, el 100 % de los casos muestra el motivo en la Consulta antes de que la persona escriba su pregunta, o en la misma respuesta si ocurrió durante el uso.
- **SC-007**: El 100 % de las calificaciones enviadas quedan asociadas a su consulta y se ven en el registro del panel.
- **SC-008**: Con la API activa, en al menos 9 de cada 10 preguntas la respuesta llega en menos de 15 segundos en modo literal y en menos de 90 segundos en modo con razonamiento, medido con el tiempo que registra cada consulta.

## Assumptions

- La API, los artefactos, las claves de consulta, los permisos por dominio y modo, los topes, el registro de consultas y la calificación ya existen y están en producción (specs/002-panel-administracion). Esta especificación solo cambia de la API la instrucción al modelo y la cantidad de fragmentos por modo (pendientes según FR-026 de esa especificación).
- Las dos instancias (Consulta administrativa Postgrados Computación y Consulta administrativa Postgrados Administración Empresas) se registran desde el panel, cada una con acceso a su unidad completa y a ambos modos, con su tope diario.
- La cantidad de 16 fragmentos para el modo con razonamiento es un valor inicial ajustable por configuración; la limitación conocida de las preguntas sobre "todos los cursos" de un dominio se mantiene (sección 3.3 y sección 10 del documento de requerimientos).
- Además de los 16 resultados, cada modo conserva la ampliación actual con fragmentos vecinos y documentos completos cortos.
- La Consulta se publica como sitio estático, con una dirección por instancia (un servicio de bajo consumo cada una, que se puede apagar de forma remota cuando no se comparte), y la dirección de cada una se agrega a los orígenes permitidos de la API.
- La conversación no se guarda en el navegador porque las preguntas pueden contener datos personales; el registro completo queda en la API, visible solo con la clave de administración.
- No hay cuentas individuales: todas las personas de una unidad comparten la clave de su instancia (sección 10).
- Los scripts de línea de comandos que consultan la API se mantienen; solo se retira el cliente web anterior.
- Fuera de alcance: memoria de conversación, preguntas de agregación sobre todo un dominio, consulta por carpeta, cuentas individuales y cambios en el panel de administración (secciones 3.3 y 10 del documento de requerimientos).
