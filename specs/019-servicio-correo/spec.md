# Feature Specification: Servicio de correo electrónico de MIA (consulta por correo)

**Feature Branch**: `dev` (feature `019-servicio-correo`, sin rama propia: los specs y la implementación van en `dev`)

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "Un servicio de correo electrónico para MIA, muy similar al bot de WhatsApp (feature 011): una persona escribe una pregunta por correo a una dirección de MIA y recibe la respuesta por correo. Servicio aparte (como mia-whatsapp) que consulta a la API con una credencial de servicio y aplica el artefacto asignado a cada buzón. Parte de la idea documentada en docs/Idea_Artefacto_Correo.md."

Contexto: hoy MIA se consulta por la Consulta administrativa (sitio web) y por el bot de WhatsApp (feature 011), un servicio aparte que traduce entre el canal y la API sin mezclarse con el motor. Mucha gente, sobre todo quien busca información de un posgrado, prefiere escribir un correo a una dirección institucional. Esta feature agrega ese canal: una persona escribe su pregunta a una dirección de correo de MIA y recibe, en el mismo hilo, la respuesta con los documentos que la respaldan. Como el bot de WhatsApp, es un **servicio aparte** que consulta a MIA con una credencial de servicio; cada **buzón** (dirección de correo) se registra con un **artefacto asignado**, que decide a qué dominios, con qué tope diario y con qué memoria responde. Quien administra registra buzones y los cambia desde el panel. No cambia ningún otro artefacto ni el motor de respuestas. El análisis previo y las opciones de recepción están en [docs/Idea_Artefacto_Correo.md](../../docs/Idea_Artefacto_Correo.md); el modelo a seguir es la feature 011 (bot de WhatsApp) y sus ampliaciones 013 (aclaración de programa) y 014 (memoria de conversación).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Una persona escribe una pregunta por correo y recibe la respuesta con sus fuentes (Priority: P1)

Una persona escribe a la dirección de MIA una pregunta en lenguaje natural ("¿Cuáles son los requisitos de admisión de la Maestría en Ciberseguridad?"). Poco después recibe, como respuesta en el mismo hilo, un correo con la respuesta tomada de los documentos del artefacto asignado a ese buzón, con los nombres de los documentos que la respaldaron, y un aviso breve de que es un asistente automático.

**Why this priority**: es el núcleo de la feature: sin recibir una pregunta y devolver su respuesta no hay canal. Con solo esta historia ya existe una consulta por correo útil.

**Independent Test**: desde una cuenta de correo cualquiera, escribir a la dirección de pruebas una pregunta cuya respuesta esté en los documentos y comprobar que llega, en el mismo hilo, una respuesta correcta con las fuentes citadas y el aviso de asistente automático.

**Acceptance Scenarios**:

1. **Given** un buzón activo con un artefacto asignado, **When** una persona le escribe una pregunta, **Then** recibe una respuesta en el mismo hilo (mismo asunto con el prefijo de respuesta) con la respuesta de MIA y los nombres de los documentos citados.
2. **Given** una persona que escribe por primera vez en un día, **When** recibe la respuesta, **Then** esta lleva, aparte de la respuesta, un aviso de que quien responde es un asistente automático que responde con los documentos del programa y que puede equivocarse.
3. **Given** una pregunta que el artefacto no puede responder con sus documentos, **When** se responde, **Then** el correo lo dice con claridad, sugiere reformular o preguntar por otro tema y no da el contacto del programa.
4. **Given** un correo con la pregunta en el asunto y el cuerpo vacío, **When** llega, **Then** se toma el asunto como pregunta (o se pide que escriba la pregunta en el cuerpo si el asunto no es una pregunta).

---

### User Story 2 - Quien administra registra un buzón y cambia en cualquier momento lo que consulta (Priority: P1)

Una persona administradora con alcance global registra un buzón en el panel con un nombre, su dirección de correo y el artefacto que debe aplicar. Puede cambiar el artefacto asignado en cualquier momento (los cambios rigen desde el siguiente correo) y activar o desactivar el buzón. Un solo servicio atiende todos los buzones: agregar otra dirección es registrar otro buzón, sin cambios de código.

**Why this priority**: sin registro no se sabe qué artefacto aplicar a cada dirección; y poder cambiarlo sin reiniciar es lo que hace al canal operable por quien administra, igual que el módulo Bots de la feature 011.

**Independent Test**: desde el panel, registrar un buzón de pruebas con un artefacto, escribirle, cambiar el artefacto por otro con otros dominios y comprobar que el siguiente correo se responde con los nuevos dominios sin reiniciar nada; desactivarlo y comprobar que deja de responder.

**Acceptance Scenarios**:

1. **Given** un artefacto registrado, **When** una persona administradora con alcance global registra un buzón con nombre único, una dirección única entre buzones y ese artefacto, **Then** el buzón aparece en el módulo del panel como activo y empieza a responder los correos que llegan a su dirección.
2. **Given** un buzón activo, **When** se cambia su artefacto asignado, **Then** el siguiente correo se responde con los dominios del nuevo artefacto, sin reiniciar el servicio.
3. **Given** un buzón activo, **When** se desactiva, o se desactiva su artefacto, o se le quita el artefacto, **Then** deja de consultar a MIA y no responde con información (a lo sumo, un aviso breve de que no está disponible, o nada, según se decida en la planificación).
4. **Given** un correo dirigido a una dirección que no está registrada como buzón, **When** llega al servicio, **Then** se ignora sin responder.
5. **Given** la asignación de un artefacto a un buzón, **When** se guarda, **Then** el panel advierte que el buzón responde a **cualquiera que le escriba** y que los dominios del artefacto deben ser información que se pueda decir a cualquier persona.
6. **Given** una persona sin alcance global, **When** intenta registrar o cambiar un buzón, **Then** no puede (acción solo de alcance global, como los bots).

---

### User Story 3 - El servicio no se deja agotar ni entra en bucles (Priority: P1)

Como cualquier canal abierto, el correo se puede abusar: ráfagas de mensajes, respuestas automáticas que hacen rebotar el correo entre dos sistemas, listas de distribución y spam. El servicio limita lo que responde y **nunca responde a lo que no es una persona que pregunta**: respuestas automáticas (fuera de oficina, acuses), rebotes y notificaciones de falla, correos de listas o masivos, y sus propios correos.

**Why this priority**: sin esto, un solo remitente o un bucle de respuestas automáticas puede agotar el tope diario del artefacto, el gasto del modelo y la reputación de la dirección. Es parte de entregar el canal de forma segura.

**Independent Test**: enviar varios correos seguidos desde un mismo remitente hasta superar su límite, y correos que son respuestas automáticas, rebotes y de lista, y comprobar que el servicio responde solo a las personas dentro del límite, avisa una sola vez al superarlo y no responde a los automáticos.

**Acceptance Scenarios**:

1. **Given** un remitente que supera su límite de correos por hora o por día, **When** escribe otra vez, **Then** recibe una sola vez un aviso de que espere y no se procesan más sus correos hasta que pase el periodo (límites configurables, con valores iniciales parecidos a los del bot: 10 por hora y 30 por día).
2. **Given** un correo marcado como respuesta automática, rebote o notificación de falla, **When** llega, **Then** no se responde ni se cuenta contra el remitente.
3. **Given** un correo de una lista de distribución o masivo, **When** llega, **Then** no se responde.
4. **Given** un correo enviado desde la propia dirección del buzón o de otro buzón de MIA, **When** llega, **Then** no se responde (evita bucles entre buzones).
5. **Given** un correo con varios destinatarios o copias, **When** se responde, **Then** la respuesta va solo a quien escribió la pregunta, nunca a todos.
6. **Given** el mes en curso, **When** el servicio alcanza el tope mensual de correos enviados configurable por el plan del proveedor de envío, **Then** deja de responder y lo registra, retomando al mes siguiente (el tope se configura según el plan elegido; ver Assumptions).
7. **Given** un mismo correo entregado más de una vez, **When** llega repetido, **Then** se responde una sola vez.

---

### User Story 4 - El correo se limpia antes de consultar (Priority: P1)

Un correo real trae mucho más que la pregunta: firma, mensajes citados de una conversación anterior, avisos legales, HTML y adjuntos. El servicio extrae solo lo que la persona escribió y lo usa como pregunta, de modo que el texto citado o la firma no distorsionen la búsqueda ni consuman el modelo.

**Why this priority**: la calidad de las respuestas depende de la pregunta. Sin limpieza, una respuesta a un hilo largo o un correo con firma extensa produce respuestas malas o gasto innecesario.

**Independent Test**: enviar un correo con una firma larga, un aviso legal y la cita de un correo anterior, y comprobar que solo el texto nuevo llega como pregunta y que la respuesta se basa en esa pregunta.

**Acceptance Scenarios**:

1. **Given** un correo con la pregunta, una firma y un aviso legal, **When** se procesa, **Then** la pregunta es solo el texto nuevo, sin la firma ni el aviso.
2. **Given** una respuesta dentro de un hilo con mensajes citados, **When** se procesa, **Then** no se incluye el texto citado como parte de la pregunta.
3. **Given** un correo en HTML, **When** se procesa, **Then** se usa su texto, sin etiquetas ni imágenes.
4. **Given** un correo con adjuntos, **When** se procesa, **Then** los adjuntos se ignoran; si el correo no trae más que adjuntos, se pide escribir la pregunta en el cuerpo.
5. **Given** un correo reenviado, **When** se procesa, **Then** se toma el texto que quien reenvía escribió encima; si no escribió nada, se pide que escriba su pregunta.
6. **Given** una pregunta de más de un largo máximo configurable, **When** llega, **Then** se pide resumirla y no se consulta a MIA.

---

### User Story 5 - Respuestas claras cuando no se puede responder (Priority: P2)

Cuando MIA no puede responder (sin información suficiente, tope diario del artefacto alcanzado, buzón o artefacto desactivado, o una falla o demora excesiva), la persona recibe un correo breve en español que explica la situación y qué puede hacer, sin dar el contacto del programa y sin dejar el hilo sin respuesta.

**Why this priority**: mejora la experiencia en los casos de error, pero el canal ya funciona sin ella con respuestas genéricas.

**Independent Test**: provocar cada caso (pregunta sin respuesta, tope alcanzado, artefacto desactivado, API detenida) y comprobar que cada uno recibe un correo distinto y claro, y que ninguno incluye el contacto del programa.

**Acceptance Scenarios**:

1. **Given** una pregunta sin información suficiente, **When** se responde, **Then** el correo lo dice, sugiere reformular o preguntar por otro tema y no da el contacto.
2. **Given** el tope diario del artefacto alcanzado, **When** llega una pregunta, **Then** se responde un aviso breve de que el servicio no está disponible por hoy.
3. **Given** una falla o demora excesiva de MIA, **When** llega una pregunta, **Then** se responde un aviso breve de que no se pudo consultar y que intente de nuevo más tarde, sin quedar el correo sin respuesta.
4. **Given** cualquier texto fijo del servicio, **When** se revisa, **Then** ninguno da el correo, el teléfono ni el contacto del programa.

---

### User Story 6 - El hilo es la conversación: seguimiento y aclaración de programa (Priority: P2)

Quien responde a la respuesta de MIA (mismo hilo) puede hacer una pregunta de seguimiento ("¿y el costo?") que se apoya en las anteriores, igual que la memoria de conversación de la feature 014. Si la pregunta no nombra el programa y varios tienen algo relacionado, el servicio puede preguntar "¿A qué programa te refieres?" con una lista numerada y seguir con la pregunta original cuando la persona responde (feature 013). El identificador del hilo del correo es el que une los mensajes de una misma conversación.

**Why this priority**: es lo que más acerca el correo a la experiencia del bot, pero la primera entrega funciona sin memoria (cada correo se responde por sí solo).

**Independent Test**: preguntar por un programa, responder al correo de MIA con "¿y el costo?" y comprobar que la respuesta habla del mismo programa; escribir una pregunta ambigua y comprobar que pregunta a qué programa se refiere y sigue con la respuesta.

**Acceptance Scenarios**:

1. **Given** un hilo con una pregunta y su respuesta, **When** la persona responde con una pregunta de seguimiento en el mismo hilo, **Then** la respuesta tiene en cuenta los turnos anteriores del hilo (hasta el número de turnos que fije el artefacto, como la memoria de la feature 014).
2. **Given** correos de hilos distintos de la misma persona, **When** se responden, **Then** no comparten memoria entre sí.
3. **Given** un correo que empieza un hilo nuevo, **When** se responde, **Then** no hereda contexto de hilos anteriores.
4. **Given** una pregunta que no nombra el programa y varios programas relacionados, **When** la aclaración está activa, **Then** se pregunta a qué programa se refiere con una lista numerada y se continúa con la pregunta original al responder.
5. **Given** un artefacto con memoria en 0, **When** llega un correo, **Then** se responde por sí solo, como en la primera entrega.

---

### User Story 7 - Probar el canal completo con un buzón de pruebas antes de abrirlo (Priority: P1)

Antes de abrir la dirección real al público, quien administra debe poder usar y probar el servicio de punta a punta con un buzón de pruebas, desde cuentas de prueba, sin que lleguen mensajes de personas reales ni se consuma el gasto de un canal público.

**Why this priority**: es lo que permite validar el canal, igual que el sandbox de Kapso en la feature 011, antes de exponerlo.

**Independent Test**: con el buzón de pruebas registrado, recorrer las historias 1 a 5 desde una cuenta de prueba y comprobar que todo funciona sin que la dirección real esté expuesta.

**Acceptance Scenarios**:

1. **Given** un buzón de pruebas, **When** se escribe desde una cuenta de prueba, **Then** el servicio responde de punta a punta igual que respondería la dirección real.
2. **Given** el servicio en modo de pruebas, **When** escribe una persona fuera de las cuentas permitidas, **Then** no se responde y no se cuenta como consulta.
3. **Given** la primera entrega, **When** se despliega, **Then** funciona **solo** con el buzón de pruebas y sus cuentas permitidas (decisión del 2026-11-15, como el sandbox de WhatsApp en la feature 011): abrir una dirección al público es un paso posterior, documentado en la guía de operación, que no forma parte de esta entrega.

---

### User Story 8 - Los demás artefactos no cambian (Priority: P1)

Agregar el servicio de correo no cambia nada de la Consulta administrativa, el chatbot ni el bot de WhatsApp: ni sus claves, ni sus dominios, ni sus respuestas, ni el panel de lo ya existente. Con el servicio de correo apagado o sin ningún buzón registrado, MIA se comporta como antes.

**Why this priority**: protege lo que ya funciona (misma regla que la feature 011, historia 8).

**Independent Test**: con el servicio apagado y con él encendido, correr la batería de pruebas existente y comprobar que las respuestas de los demás artefactos son idénticas.

**Acceptance Scenarios**:

1. **Given** MIA sin ningún buzón registrado, **When** se usan los demás artefactos, **Then** responden exactamente igual que antes y las pruebas existentes pasan.
2. **Given** el servicio de correo desactivado desde el panel, **When** llegan correos, **Then** no se procesan y nada más se ve afectado.

---

### Edge Cases

- **Correo con idioma distinto del español**: se responde en español (el servicio solo responde en español, como el bot); el texto de la pregunta se consulta tal cual.
- **Dirección con alias o variantes** (mayúsculas, subdirecciones `+etiqueta`): se tratan como la misma dirección del buzón.
- **Remitente con nombre pero dirección falsificada**: el servicio responde a la dirección de respuesta del correo y aplica los límites por remitente; no puede garantizar quién escribe (ver Assumptions).
- **Respuesta que no se puede enviar** (rechazada o con error del proveedor de envío): se reintenta un número limitado de veces y se registra sin el contenido; nunca se queda en un bucle.
- **Respuesta en el límite de largo del correo**: las respuestas largas (por ejemplo resúmenes) se envían completas en un solo correo, no se parten como en WhatsApp.
- **Correos que llegan fuera de orden o de un hilo ya cerrado**: se responde cada uno por sí solo si su hilo no se puede reconstruir; nunca se mezclan hilos.
- **Spam o phishing dirigido al buzón**: filtrado por las reglas de la historia 3 (listas, automáticos, límites) y por el proveedor de recepción; no se responden los correos que el proveedor marca como spam.
- **Datos personales en la pregunta**: la pregunta no se guarda; solo se registran contadores (ver requisitos de privacidad).
- **La respuesta cae en la carpeta de spam de quien pregunta**: depende de la configuración de la dirección de envío (ver Assumptions); queda como riesgo operativo, no funcional.
- **Un buzón sin artefacto asignado recibe correos**: se ignoran o se responde un aviso de no disponible, nunca información.
- **El servicio se reinicia a mitad de un correo**: el correo no se pierde si el proveedor reintenta la entrega y no se responde dos veces (historia 3, escenario 7).

## Requirements *(mandatory)*

### Functional Requirements

**Buzones (administración)**

- **FR-001**: El panel debe tener un módulo para **buzones de correo** que lista los registrados con su nombre, su dirección, su artefacto asignado, su modo de respuesta, su estado (activo o desactivado) y su consumo del mes.
- **FR-002**: Debe poder registrarse un buzón con nombre único, dirección de correo única entre buzones, un artefacto asignado (elegido entre los artefactos registrados) y un modo de respuesta (FR-014).
- **FR-003**: Debe poder cambiarse el artefacto asignado a un buzón en cualquier momento, rigiendo desde el correo siguiente, sin reiniciar ni volver a desplegar nada.
- **FR-004**: Cambiar los dominios del artefacto asignado debe cambiar, desde el correo siguiente, a qué información accede el buzón.
- **FR-005**: Debe poder desactivarse y reactivarse un buzón sin afectar al artefacto. Un buzón desactivado, sin artefacto asignado o con el artefacto desactivado no consulta a MIA ni responde con información.
- **FR-006**: Un mismo servicio debe atender a todos los buzones; atender otra dirección es registrar otro buzón, sin cambios de código. Un correo a una dirección no registrada se ignora.
- **FR-007**: Al asignar un artefacto, el panel debe advertir que el buzón responde a cualquiera que le escriba y que los dominios deben ser información que se pueda decir a cualquier persona.
- **FR-008**: Los textos fijos y los límites son los mismos para todos los buzones en esta versión y se pueden cambiar sin modificar el código.
- **FR-009**: Las acciones de administración de buzones (registrar, cambiar artefacto, activar, desactivar) deben exigir una persona administradora con alcance global y quedar en el registro de administración, sin contenido de correos.

**Recepción y respuesta**

- **FR-010**: El servicio debe recibir los correos dirigidos a cada buzón registrado por el aviso (webhook) de un **servicio de correo transaccional** (decisión del 2026-11-15: no un buzón institucional ni IMAP), con la dirección de cada buzón en un **dominio propio** configurado para ese servicio; debe verificar la autenticidad de cada aviso (firma o clave) y rechazar los que no la tengan válida. El mismo servicio de correo se usa para enviar las respuestas.
- **FR-011**: El servicio debe confirmar la recepción al mecanismo de entrada de forma rápida y procesar la consulta después, sin que la confirmación dependa de la respuesta de MIA.
- **FR-012**: Un mismo correo entregado más de una vez debe responderse una sola vez.
- **FR-013**: La respuesta debe enviarse como respuesta en el mismo hilo del correo original (asunto con prefijo de respuesta y encabezados de hilo), dirigida solo a quien escribió la pregunta.
- **FR-014**: Cada buzón debe tener un **modo de respuesta** elegido al registrarlo y editable después, entre los que su artefacto asignado permite: **literal** (breve) o **con razonamiento** (respuestas largas, como los resúmenes), decisión del 2026-11-15, aprovechando que en correo la espera no importa. El valor inicial es el literal; si el modo elegido deja de estar permitido por el artefacto, el servicio usa el literal. El modo con razonamiento consume el tope diario del artefacto como cualquier consulta de ese modo (FR-034) y el panel debe advertirlo al elegirlo.
- **FR-015**: La respuesta debe incluir los nombres de los documentos que la respaldaron (principio V de la constitución), de forma breve y legible dentro del correo.
- **FR-016**: Si MIA responde "sin información suficiente", el servicio debe decirlo, sugerir reformular o preguntar por otro tema, no dar el contacto del programa y no enviar imágenes ni fuentes irrelevantes.
- **FR-017**: El servicio no debe dar el contacto del programa (correo, teléfono o WhatsApp de la coordinación) en ninguna respuesta ni texto fijo, igual que el bot.
- **FR-018**: Si la consulta no se puede hacer (tope diario alcanzado, buzón o artefacto desactivado, falla o demora excesiva de MIA), el servicio debe responder un aviso breve que explique la situación, sin dejar el correo sin respuesta ni inventar contenido.
- **FR-019**: La primera respuesta a un remitente en un día debe llevar un aviso de que quien responde es un asistente automático que contesta con los documentos del programa y que puede equivocarse. No se repite en todas las respuestas del día.
- **FR-020**: El servicio debe responder siempre en español.
- **FR-021**: Las respuestas deben tener formato de correo electrónico (texto plano o HTML sencillo, sin formato de WhatsApp) y enviarse completas en un solo correo, sin partirlas.

**Limpieza del correo**

- **FR-022**: El servicio debe extraer del correo solo el texto nuevo escrito por la persona, descartando firma, avisos legales, mensajes citados, HTML y adjuntos.
- **FR-023**: Un correo sin texto utilizable (solo adjuntos, vacío o reenviado sin comentarios) debe recibir el pedido de escribir la pregunta en el cuerpo, sin consultar a MIA.
- **FR-024**: Una pregunta mayor que un largo máximo configurable debe recibir el pedido de resumirla, sin consultar a MIA.
- **FR-025**: El servicio no debe procesar los adjuntos ni abrir enlaces de los correos recibidos.

**Límites y protección**

- **FR-026**: El servicio debe limitar los correos por remitente (por hora y por día, configurables) y, al superarlo, responder una sola vez que espere y no procesar más hasta que pase el periodo.
- **FR-027**: El servicio debe contar de forma persistente los correos del mes (recibidos y enviados) y, al llegar a un tope mensual configurable, dejar de responder y registrarlo, retomando el mes siguiente.
- **FR-028**: El servicio debe limitar las consultas simultáneas a MIA y descartar, sin responder, lo que exceda la cola configurable.
- **FR-029**: El servicio no debe responder a respuestas automáticas, rebotes, notificaciones de falla, correos de listas o masivos, correos del propio buzón ni de otros buzones de MIA, ni a correos que el proveedor de recepción marque como spam.
- **FR-030**: El servicio debe reintentar un envío fallido un número limitado de veces y registrarlo sin contenido, sin entrar nunca en un bucle de envíos.

**Memoria, aclaración y privacidad**

- **FR-031**: El servicio debe usar el identificador del hilo del correo como conversación para dar memoria (feature 014) hasta el número de turnos del artefacto asignado; con memoria en 0 cada correo se responde por sí solo. Los hilos distintos no comparten memoria.
- **FR-032**: Si la aclaración de programa (feature 013) está activa, el servicio debe poder preguntar "¿A qué programa te refieres?" y continuar con la pregunta original al recibir la respuesta en el mismo hilo.
- **FR-033**: La dirección del remitente solo debe usarse para los límites y para responderle, y no debe guardarse en el registro de consultas (Uso) ni en los registros del servicio. El contenido de las preguntas y de las respuestas no debe guardarse; solo se registran contadores y estados.
- **FR-034**: Las consultas por correo deben contar en el tope diario del artefacto asignado y en el registro de Uso, como si las hiciera el propio artefacto; alcanzar ese tope se informa a la persona como en FR-018.

**Compatibilidad, operación y documentación**

- **FR-035**: Con el servicio apagado, desactivado o sin ningún buzón registrado, el comportamiento de MIA debe ser el anterior; las pruebas existentes y la batería del MVP deben seguir pasando.
- **FR-036**: El servicio debe poder desactivarse desde el panel (buzón o artefacto) sin tocar el servicio.
- **FR-037**: En esta entrega el servicio responde **solo a las cuentas de correo permitidas** (lista configurable, por buzón o del servicio) y solo para el buzón de pruebas; los correos de cualquier otra cuenta se ignoran sin responder. Abrir una dirección al público (quitar la lista) es un paso posterior documentado en la guía de operación.
- **FR-038**: Al implementarse, la documentación de arquitectura y de operación debe quedar al día (nuevo servicio, variables, despliegue, dominio de envío con SPF, DKIM y DMARC, y límites), y debe actualizarse `docs/Idea_Artefacto_Correo.md` para que apunte a esta feature.

### Key Entities *(include if feature involves data)*

- **Buzón de correo**: una dirección de correo de MIA con un nombre, un artefacto asignado, un modo de respuesta y un estado. Es el equivalente a un bot de WhatsApp. Una dirección corresponde a un solo buzón.
- **Artefacto asignado**: el artefacto existente (feature 003 y siguientes) que decide dominios, modo, tope diario y memoria del buzón; no cambia.
- **Mensaje de correo recibido**: la pregunta de una persona; no se guarda su contenido, solo un identificador para no responderlo dos veces y los contadores.
- **Hilo**: la conversación que une el correo de la persona con las respuestas, identificada por los encabezados del correo; da memoria cuando el artefacto la permite.
- **Cuenta permitida**: una dirección de correo autorizada a escribir al buzón de pruebas en esta entrega; las demás se ignoran.
- **Remitente**: la persona que escribe, identificada solo por su dirección, usada para los límites y para responder; no se guarda en el registro de consultas.
- **Consumo mensual del servicio**: contador persistente de correos recibidos y enviados del mes, por buzón o del servicio, contra el tope mensual.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona que escribe una pregunta cuya respuesta está en los documentos recibe la respuesta correcta, con sus fuentes, en menos de 2 minutos en el 95 % de los casos con el modo literal y en menos de 5 minutos con el modo con razonamiento.
- **SC-002**: En un conjunto de al menos 20 preguntas reales de prueba por correo, al menos 90 % se responden con información correcta y citan el documento de origen, igual que por el bot de WhatsApp.
- **SC-003**: El 100 % de los correos que son respuestas automáticas, rebotes, listas, del propio buzón o de otros buzones de MIA quedan sin respuesta, y no se produce ningún bucle de correos en las pruebas.
- **SC-004**: Un remitente que supera el límite recibe un único aviso de espera y ninguna respuesta más hasta que pase el periodo, en el 100 % de las pruebas.
- **SC-005**: Un mismo correo entregado dos o más veces recibe una sola respuesta en el 100 % de las pruebas.
- **SC-006**: En un conjunto de correos con firma, aviso legal y texto citado, la pregunta extraída es solo el texto nuevo en al menos 95 % de los casos.
- **SC-007**: Ninguna respuesta ni texto fijo del servicio contiene el contacto del programa (correo, teléfono o WhatsApp), verificado en todas las pruebas.
- **SC-008**: Tras revisar el registro de consultas, los registros del servicio y la base, no aparece ninguna dirección de remitente ni texto de preguntas o respuestas fuera de lo que esta spec permite, en el 100 % de las revisiones.
- **SC-009**: Cambiar el artefacto asignado a un buzón se refleja en el correo siguiente sin reiniciar el servicio, en el 100 % de las pruebas.
- **SC-010**: Con el servicio apagado o sin buzones, las pruebas existentes (incluida la batería del MVP) pasan sin cambios.

## Assumptions

- Es un **servicio aparte** (como `mia-whatsapp`) que no importa el motor de MIA: consulta solo por la API con una credencial de servicio, y la API aplica el artefacto, los topes, la memoria y el registro de Uso. Un buzón se identifica por su dirección, de forma análoga a como el bot se identifica por su número.
- Siguiendo la feature 011, **los límites por remitente (10 por hora, 30 por día), la cola de consultas simultáneas (5 a la vez, cola de 20) y el tope mensual son configurables** con esos valores iniciales; el tope mensual se ajusta al plan gratuito del proveedor de envío que se elija (decisión de la planificación).
- **Recepción y envío por un servicio de correo transaccional con dominio propio** (decisión del 2026-11-15). Quién da el dominio y qué proveedor concreto (por ejemplo Resend, Postmark o Mailgun) se decide en la planificación, según su plan gratuito. Es una **dependencia externa**: hace falta un dominio donde configurar los registros de recepción y de envío (MX, SPF, DKIM y DMARC) para que las respuestas no caigan en spam; sin dominio no se puede probar con correo real.
- **Primera entrega**: solo con el buzón de pruebas y sus cuentas permitidas (FR-037), respuesta en el mismo hilo, con límites y filtros de bucle, modo literal o con razonamiento por buzón (FR-014) y **sin memoria** (cada correo por sí solo); la memoria por hilo y la aclaración de programa (historia 6) son una ampliación posterior.
- **Privacidad**: se asume que las preguntas pueden contener datos personales; por eso no se guarda el contenido y la dirección del remitente se usa solo para límites y respuesta. La política de datos del proyecto (los datos se consideran públicos para pruebas) y la advertencia de que el buzón responde a cualquiera siguen siendo válidas.
- **No se sabe quién escribe realmente**: el correo se puede falsificar; el servicio responde a la dirección de respuesta y aplica los límites por remitente, sin pretender verificar identidad (no es un canal para datos sensibles).
- **El servicio solo responde en español**, como el bot, y los dominios y el tope diario son los del artefacto asignado; el modo de respuesta lo elige cada buzón dentro de lo que el artefacto permite.
- **Los datos de contacto** del remitente (nombre y correo opcionales, feature 017 para WhatsApp) **no** forman parte de esta feature: el correo ya identifica a quien escribe, y guardarlo sería una excepción nueva a FR-033 que se tratará en otra feature si se pide.
- **Fuera de alcance**: procesar adjuntos, abrir enlaces del correo, enviar imágenes de documentos (la feature 011 las envía por WhatsApp), conversaciones de varios remitentes en un hilo, y un buzón compartido atendido por personas.
- Los specs y la implementación van en `dev`; el merge a `main` y el despliegue los hace la persona dueña del proyecto.
