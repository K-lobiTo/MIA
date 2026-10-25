# Feature Specification: Bot de WhatsApp para atraer estudiantes (con imágenes asociadas a documentos)

**Feature Branch**: `dev` (feature `011-bot-whatsapp-kapso`, sin rama propia por decisión del usuario)

**Created**: 2026-10-21

**Status**: Draft

**Input**: User description: "Feature 011: bot de WhatsApp con Kapso para atraer estudiantes de los posgrados. Los requerimientos acordados están en docs/Definicion_Requerimientos_Bot_WhatsApp.md (BOT-1 a BOT-8, WAP-1 a WAP-13, IMG-1 a IMG-9, secciones 3.3 a 8). Módulo Bots del panel con artefacto asignado editable en cualquier momento; comportamiento del bot (webhook firmado, confirmación en menos de 10 s, respuesta asíncrona, sin duplicados, solo texto, solo modo literal, sin dar el contacto del programa, límites por número, consultas simultáneas, tope mensual persistente de mensajes); imágenes asociadas a documentos que el bot envía cuando el documento aporta a la respuesta. Sin memoria de conversación, sin LangChain ni LangGraph. El camino para escalar (sección 10 del documento) no es parte de esta feature."

Contexto: hoy MIA solo se consulta desde la Consulta administrativa, que usa el personal. Las personas interesadas en estudiar un posgrado (el público de la atracción de estudiantes) preguntan lo mismo una y otra vez a la asistente del programa: horario de matrícula, requisitos, plan de estudios. Se quiere un canal de WhatsApp donde esas personas obtengan la respuesta por su cuenta, de documentos oficiales, antes de pasar a hablar con alguien. Tres hechos condicionan el diseño:

1. **El público es externo y masivo.** Cualquiera que escriba al número recibe respuesta, así que todo lo que el bot pueda consultar debe ser información que se le pueda decir a cualquiera, y el uso hay que acotarlo para que una persona, o muchas, no agoten el servicio.
2. **El límite real es la cuota de mensajes, no el gasto de modelos.** El plan gratuito del proveedor de WhatsApp incluye 2.000 mensajes al mes entre recibidos y enviados, y el proveedor de la red cobra los mensajes de servicio salvo 1.000 gratuitos por número cada mes: unas 500 a 1.000 preguntas al mes. Un modelo de costo medio de 0,0004 USD por consulta no es el cuello de botella.
3. **Muchas respuestas son un dato que se entiende mejor en una imagen** (un horario, un calendario, un cuadro de costos). El bot debe poder enviarla cuando la respuesta se apoya en el documento al que esa imagen pertenece, y quien administra la información debe poder asociarla sin tocar código.

**Alcance de esta entrega (2026-10-24).** Por ahora solo se dispone del **número de pruebas (sandbox) de Kapso**: solo pueden escribirle los teléfonos registrados como de prueba, no el público. Esta entrega se construye, se prueba y se acepta **únicamente con el sandbox**. Se conservan los límites y protecciones pensados para el público (ya son parte del servicio y cuestan poco) y el diseño admite un número de producción sin cambios de código, pero la puesta en producción (registro en Meta, número propio, plan, campaña) no se implementa ni se valida: queda documentada en la sección 11 del documento de requerimientos.

## Clarifications

### Session 2026-10-21

- Q: ¿El bot es un artefacto más y con qué acceso? → A: Consulta a MIA con la configuración de un artefacto asignado (dominios, tope y estado), que se cambia en cualquier momento desde el panel. Solo pide el modo literal aunque el artefacto asignado permita razonamiento.
- Q: ¿Cuántos bots? → A: Uno hoy (el plan gratuito incluye un número), pero la estructura debe admitir varios, cada uno con su número y su artefacto, sin escribir código para agregar uno.
- Q: ¿El bot da el contacto del programa? → A: No. Se quiere que las personas prueben el bot antes de pasar con la asistente; quien quiera el contacto lo busca por su cuenta.
- Q: ¿Qué límites se aplican? → A: Los propuestos en la sección 3.3 del documento de requerimientos (10 mensajes por hora y 30 por día por número, preguntas de hasta 500 caracteres, 5 consultas simultáneas con cola de 20, 1 imagen por respuesta de hasta 2 MB, tope mensual de 1.800 mensajes, tope diario de 1 USD), configurables.
- Q: ¿Dónde se guardan las imágenes y cómo se envían? → A: Se guardan con el resto de la información de MIA (no en un disco que se borra) y se sirven por un enlace público no adivinable, porque el proveedor de WhatsApp envía las imágenes a partir de un enlace.
- Q: ¿Hay memoria de conversación? → A: No: cada mensaje se responde por sí solo.
- Q: ¿Dónde corre la lógica del bot? → A: En un servicio propio pequeño, aparte de la API de MIA, creado por el usuario desde la interfaz de Railway como los demás servicios.

### Session 2026-10-24

- Q: ¿Qué entorno cubre esta entrega? → A: Solo el sandbox de Kapso (número de pruebas), porque por ahora no es posible más. Todo lo funcional se construye y se acepta con él; el camino a producción se documenta y no se implementa.
- Q: ¿Los bots futuros (más números de WhatsApp y bots incrustados en páginas web de los postgrados, mínimo dos de cada tipo) cambian esta entrega? → A: No. Un servicio de WhatsApp atenderá todos los números y los bots web serán otra feature que llama a la API directamente (investigación R16 del plan).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Una persona interesada pregunta por WhatsApp y recibe la respuesta de los documentos (Priority: P1)

Una persona escribe al número de WhatsApp del programa: "¿Cuáles son los requisitos de admisión de la maestría?". Recibe en pocos segundos una respuesta en texto, tomada de los documentos oficiales, con el nombre de los documentos que la respaldan. Si escribe lo mismo dos veces seguidas por error o el sistema recibe el mensaje repetido, no recibe dos respuestas.

**Why this priority**: es el propósito del bot. Sin esto no hay canal; todo lo demás lo mejora o lo protege.

**Independent Test**: con el número de pruebas, enviar las preguntas de la batería del MVP que tienen respuesta en los documentos habilitados y comprobar que cada una recibe un texto correcto con sus fuentes, en modo literal.

**Acceptance Scenarios**:

1. **Given** el bot activo con un artefacto asignado que ve los documentos de admisión, **When** una persona envía una pregunta cuya respuesta está en esos documentos, **Then** recibe un mensaje de texto con la respuesta y los nombres de los documentos que la respaldan.
2. **Given** el mismo mensaje entregado más de una vez por el proveedor de WhatsApp (reintentos), **When** el bot lo recibe, **Then** responde una sola vez.
3. **Given** una respuesta más larga que el límite de un mensaje de WhatsApp, **When** el bot la envía, **Then** la divide en varios mensajes en orden, sin cortar la respuesta.
4. **Given** una respuesta con formato de texto enriquecido (negritas, listas, encabezados), **When** el bot la envía, **Then** la persona la ve con el formato propio de WhatsApp y sin símbolos de otro formato.
5. **Given** la primera respuesta a un número en 24 horas, **When** el bot la envía, **Then** antepone dentro del mismo mensaje un saludo que aclara que es un asistente automático que responde con documentos oficiales y pide no enviar datos personales, y las preguntas siguientes en esas 24 horas no lo repiten.
6. **Given** una pregunta que el sistema tarda varios segundos en responder, **When** el proveedor de WhatsApp espera la confirmación de entrega del mensaje, **Then** la recibe de inmediato, sin esperar a que la respuesta esté lista.

---

### User Story 2 - La respuesta llega con la imagen del documento cuando corresponde (Priority: P1)

Una persona pregunta "¿Cuándo es la matrícula?". El sistema encuentra que la respuesta viene del documento `horario_matricula.pdf`, que tiene asociada la imagen `horario_matricula.png`. Además del texto, la persona recibe la imagen del horario, con su descripción como pie de foto.

**Why this priority**: es el diferenciador pedido por el usuario: respuestas visuales sin que nadie decida a mano cuándo enviarlas.

**Independent Test**: asociar una imagen a un documento, preguntar de cinco formas distintas por su contenido y comprobar que siempre llega el texto y la imagen; preguntar por algo que no esté en ningún documento y comprobar que no llega ninguna imagen.

**Acceptance Scenarios**:

1. **Given** un documento con una imagen asociada que aporta a la respuesta, **When** una persona hace una pregunta que se responde con ese documento, **Then** recibe el texto y a continuación la imagen con su descripción como pie de foto.
2. **Given** una respuesta que se apoya en varios documentos con imágenes asociadas, **When** el bot responde, **Then** envía como máximo el número de imágenes configurado (una por defecto), en el orden de las fuentes de la respuesta.
3. **Given** una imagen que no se puede enviar (falla del proveedor), **When** el bot responde, **Then** la persona conserva el texto ya enviado y el fallo queda registrado.
4. **Given** una respuesta "sin información suficiente", **When** el bot responde, **Then** no envía ninguna imagen.
5. **Given** un documento que se le pasó al modelo pero no aportó a la respuesta, **When** el bot responde, **Then** no se envían sus imágenes.
6. **Given** un documento sin imágenes asociadas, **When** se responde con él, **Then** la respuesta es solo texto, como hoy.

---

### User Story 3 - Quien administra asocia imágenes a documentos desde el panel (Priority: P1)

Una persona administradora abre el inventario, elige el documento `horario_matricula.pdf` y le asocia la imagen `horario_matricula.png` con una descripción corta. Puede agregar más imágenes al mismo documento, cambiar su orden, reemplazarlas o quitarlas. No tiene que configurar nada más: el sistema ya decide cuándo enviarlas.

**Why this priority**: sin esta herramienta, la historia 2 no se puede usar; es la forma en que el usuario controla el contenido visual.

**Independent Test**: desde el panel, asociar, ordenar, describir, reemplazar y quitar imágenes de un documento y comprobar que cada cambio rige en la consulta siguiente.

**Acceptance Scenarios**:

1. **Given** un documento del inventario, **When** la persona administradora le agrega una imagen PNG o JPG de hasta 2 MB con una descripción opcional, **Then** la imagen queda asociada y visible en el documento.
2. **Given** un archivo que no es PNG ni JPG, o que supera el tamaño máximo, **When** se intenta asociar, **Then** se rechaza con un mensaje claro antes de subirlo.
3. **Given** el panel al subir una imagen, **When** la persona la confirma, **Then** el panel le advierte que la imagen será pública: nada que no pueda ver cualquiera.
4. **Given** una imagen reemplazada o quitada, **When** se hace la consulta siguiente, **Then** el bot ya no envía la anterior ni su enlace anterior sirve.
5. **Given** una persona administradora con alcance sobre un solo programa, **When** intenta asociar una imagen a un documento de otro programa, **Then** el sistema lo rechaza igual que rechaza hoy cualquier cambio fuera de su alcance.
6. **Given** varias imágenes asociadas a un documento, **When** se cambia su orden, **Then** el bot las envía en el nuevo orden.

---

### User Story 4 - Quien administra registra el bot y cambia en cualquier momento lo que consulta (Priority: P1)

En un módulo nuevo del panel, **Bots**, la persona administradora registra el bot con su nombre, el número de WhatsApp al que responde y el artefacto que se le asigna. Más tarde decide que el bot debe ver también un dominio nuevo, o pasar a otro artefacto, y lo hace desde el panel: desde el mensaje siguiente el bot responde con los nuevos accesos, sin reiniciar nada.

**Why this priority**: es lo que permite controlar el bot como a los demás artefactos y cambiar a qué información accede sin tocar el servicio.

**Independent Test**: registrar el bot, preguntar algo que solo está en un dominio no habilitado (responde "sin información"), habilitar el dominio en el artefacto asignado desde el panel y repetir la pregunta (responde con el documento); luego asignar otro artefacto y comprobar que rigen sus accesos.

**Acceptance Scenarios**:

1. **Given** el módulo Bots, **When** la persona administradora registra un bot con nombre único, número de WhatsApp único y un artefacto asignado, **Then** el bot queda registrado y listado con su estado, su artefacto y los dominios que hoy ve.
2. **Given** un bot funcionando, **When** se cambia el artefacto asignado desde el panel, **Then** desde el mensaje siguiente rigen los dominios y el tope del nuevo artefacto, sin reiniciar ni volver a desplegar el servicio.
3. **Given** un bot funcionando, **When** se cambian los dominios del artefacto asignado, **Then** el bot accede a lo nuevo desde el mensaje siguiente.
4. **Given** un bot activo, **When** se desactiva desde el panel, **Then** responde el aviso de no disponible y el artefacto, que puede usarse en otros lugares, sigue activo.
5. **Given** un bot sin artefacto asignado o con el artefacto desactivado, **When** llega un mensaje, **Then** responde el aviso de no disponible.
6. **Given** al asignar un artefacto, **When** la persona administradora confirma, **Then** el panel le advierte que el bot responde a cualquiera que escriba al número y que los dominios deben ser información que se pueda decir a cualquiera.
7. **Given** un mensaje de un número de WhatsApp que no corresponde a ningún bot registrado, **When** llega, **Then** se ignora y queda en el registro.
8. **Given** que se agrega un segundo bot en el futuro con su número y su artefacto, **When** los mensajes de los dos números llegan al mismo servicio, **Then** cada uno se atiende con su propio artefacto, sin cambios de código.

---

### User Story 5 - El bot no se deja agotar: límites por persona, por ráfaga y por mes (Priority: P1)

El bot está abierto al público, así que una persona que escribe sin parar, una ráfaga de muchos números o el propio éxito de la campaña podrían agotar la cuota de mensajes o saturar a MIA. El bot limita los mensajes por número, las consultas simultáneas y los mensajes del mes, y el panel muestra cuánto se lleva gastado.

**Why this priority**: el límite real es la cuota de mensajes (unas 500 a 1.000 preguntas al mes). Sin estos límites, una sola persona o una ráfaga la agotaría en días.

**Independent Test**: con el proveedor simulado, enviar más mensajes que el límite por hora desde un mismo número, una ráfaga mayor que la cola y mensajes hasta el tope mensual, y comprobar el comportamiento esperado en cada caso.

**Acceptance Scenarios**:

1. **Given** un número que supera 10 mensajes en una hora (o 30 en un día), **When** envía otro, **Then** recibe una sola vez un aviso de que espere y no se procesan más mensajes suyos hasta que pase la ventana.
2. **Given** una ráfaga de consultas mayor que la capacidad simultánea y la cola, **When** llegan, **Then** el bot atiende hasta 5 a la vez, encola hasta 20 y descarta el resto sin responder, sin saturar a MIA.
3. **Given** el artefacto con su tope diario alcanzado, **When** llega un mensaje, **Then** el bot avisa que no puede atender ahora y no vuelve a intentar la consulta.
4. **Given** que los mensajes del mes (recibidos y enviados) llegan al tope configurado (1.800 por defecto), **When** llega otro mensaje, **Then** el bot deja de responder, no envía ni un mensaje más, y el panel lo muestra en el bot.
5. **Given** el bot reiniciado a mitad del mes, **When** vuelve a arrancar, **Then** el conteo de mensajes del mes se conserva y el tope sigue aplicando.
6. **Given** el panel, **When** la persona administradora abre el módulo Bots, **Then** ve para cada bot los mensajes del mes frente a su tope.
7. **Given** cualquier límite por número, **When** el bot lo aplica, **Then** el número de teléfono solo se usa para eso, no se guarda en el registro de consultas.

---

### User Story 6 - El bot responde con claridad cuando no puede responder, sin dar el contacto (Priority: P2)

Cuando el bot no encuentra la información, no entiende el tipo de mensaje, recibe una pregunta demasiado larga o no está disponible, responde con un texto breve que lo explica y ofrece reformular, sin dar el contacto del programa y sin dejar la conversación en silencio.

**Why this priority**: son casos frecuentes con público masivo y el trato en ellos define si la persona sigue usando el bot. El no dar el contacto es una decisión expresa del usuario para que las personas prueben el bot antes de pasar con la asistente.

**Independent Test**: provocar cada caso (pregunta sin respuesta, audio, texto de más de 500 caracteres, tope diario alcanzado, bot desactivado) y comprobar el texto recibido, que no incluye el contacto del programa.

**Acceptance Scenarios**:

1. **Given** una pregunta que los documentos no responden, **When** el bot responde, **Then** dice que no encontró esa información, sugiere probar otras palabras u otros temas (matrícula, requisitos, plan de estudios), no da el contacto del programa y no envía imágenes.
2. **Given** un mensaje que no es texto (audio, imagen, sticker u otro), **When** llega, **Then** el bot pide que se escriba la pregunta y no consulta a MIA.
3. **Given** un texto de más de 500 caracteres, **When** llega, **Then** el bot pide que se resuma y no consulta a MIA.
4. **Given** una falla o demora excesiva de MIA, **When** se agota la espera, **Then** el bot responde un aviso breve de error en lugar de quedarse en silencio.
5. **Given** cualquiera de los textos fijos del bot (saludo, sin información, no disponible, límite por número, no es texto, pregunta larga), **When** se envían, **Then** no incluyen el contacto del programa, están en español y se pueden cambiar sin modificar el código.
6. **Given** que el proveedor no entrega el número de teléfono en el aviso del mensaje, **When** el bot responde, **Then** responde a la conversación que originó el mensaje sin depender del número.

---

### User Story 7 - Usar y probar el bot completo con el número de pruebas (sandbox) de Kapso (Priority: P1)

La persona que opera registra como bot el número de pruebas del proveedor y recorre con su teléfono, registrado como de prueba, todo lo que hace el bot (texto, imagen, límites). Es el único entorno de esta entrega: no hay número de producción.

**Why this priority**: es el entorno en que se construye, se prueba y se acepta esta entrega; las demás historias se verifican aquí.

**Independent Test**: registrar un bot con el número de pruebas, recorrer las historias 1 a 6 desde un teléfono de prueba y comprobar que cada una se cumple.

**Acceptance Scenarios**:

1. **Given** el número de pruebas del proveedor registrado como un bot, **When** se le envían mensajes desde un teléfono registrado como de prueba, **Then** se comporta como describen las historias 1 a 6.
2. **Given** pruebas automáticas con el proveedor simulado, **When** se ejecutan, **Then** cubren firma inválida, mensaje duplicado, mensaje que no es texto, tope diario, límite por número y tope mensual.
3. **Given** que el sandbox no admite el envío de imágenes (no está documentado), **When** el bot intenta enviarla, **Then** el texto ya enviado se conserva, el fallo queda registrado y la historia 2 se verifica con el proveedor simulado hasta contar con un número de producción.

---

### User Story 8 - Los demás artefactos no cambian (Priority: P1)

La Consulta administrativa y cualquier otro artefacto existente siguen funcionando igual: sus respuestas, permisos, topes y registros no se ven afectados por las imágenes ni por el bot.

**Why this priority**: es un cambio en la API compartida; no debe romper lo que ya funciona (BUS-6 y principio I de la constitución).

**Independent Test**: ejecutar la batería del MVP y las pruebas existentes contra la versión nueva y comprobar que dan lo mismo que antes.

**Acceptance Scenarios**:

1. **Given** los artefactos existentes, **When** consultan, **Then** sus respuestas y estructura no cambian (la lista de imágenes va vacía cuando no hay imágenes).
2. **Given** la batería del MVP (19 casos), **When** se ejecuta, **Then** da el mismo resultado que antes de la feature.
3. **Given** que el bot alcanza su tope o se desactiva, **When** otros artefactos consultan, **Then** siguen funcionando sin afectación.

---

### Edge Cases

- El proveedor reintenta un mismo mensaje hasta tres veces y después pausa el aviso si fallan muchas entregas seguidas: el bot debe confirmar siempre y rápido, y no responder dos veces.
- Un aviso sin firma válida, o de un número que no es de ningún bot: se rechaza o se ignora y queda en el registro, sin consultar a MIA.
- La respuesta cita varios documentos con imágenes: se envían solo las del máximo configurado, en el orden de las fuentes.
- Una imagen se reemplaza mientras un mensaje que la usaba está en cola: el enlace anterior deja de servir y el bot envía solo el texto, registrando el fallo.
- Una imagen de más de 2 MB, de otro formato o corrupta: se rechaza al subirla.
- Se asocia una imagen a un documento y luego se sube otra versión del mismo PDF: es un documento distinto y no hereda las imágenes (limitación conocida, se asocian de nuevo).
- Se cambia el artefacto asignado o sus dominios mientras hay una consulta en curso: la consulta en curso termina con los accesos con que empezó; la siguiente usa los nuevos.
- El bot se reinicia: el conteo del mes se conserva; los mensajes ya vistos y los límites por número, que viven en memoria, pueden reiniciarse (se acepta para el prototipo, ver Assumptions).
- Llegan mensajes después de que se alcanzó el tope mensual: el bot no responde ni los avisa para no gastar más cuota, y el panel muestra el motivo.
- Una persona escribe después de 24 horas de silencio: la primera respuesta lleva de nuevo el saludo.
- La pregunta pide algo que está solo en un dominio no habilitado para el bot: responde "sin información", sin revelar que existe.
- Dos personas distintas escriben a la vez desde números distintos: sus consultas son independientes y no se mezclan respuestas ni imágenes.
- El proveedor no incluye el número de teléfono en el aviso: el bot no falla y responde a la conversación.
- El sandbox solo admite texto y mensajes interactivos según su documentación: si rechaza una imagen, el texto ya enviado se conserva, el fallo queda en el registro y las imágenes se verifican con el proveedor simulado.
- Un teléfono que no está registrado como de prueba no puede escribir al sandbox: el bot no recibe nada de él.

## Requirements *(mandatory)*

### Functional Requirements

**Bots y artefacto asignado**

- **FR-001**: El panel debe tener un módulo **Bots** que lista los bots registrados con su nombre, el número de WhatsApp al que responden, su artefacto asignado, su estado (activo o desactivado), los dominios que hoy ven y los mensajes del mes frente a su tope.
- **FR-002**: Debe poder registrarse un bot con nombre único, número de WhatsApp único entre bots y un artefacto asignado, elegido entre los artefactos registrados.
- **FR-003**: Debe poder cambiarse el artefacto asignado a un bot en cualquier momento desde el panel, rigiendo desde el mensaje siguiente, sin reiniciar ni volver a desplegar el servicio del bot. Los dominios y el tope que usa el bot son siempre los del artefacto asignado.
- **FR-004**: Cambiar los dominios del artefacto asignado debe cambiar, desde el mensaje siguiente, a qué información accede el bot.
- **FR-005**: Debe poder desactivarse y reactivarse un bot sin afectar al artefacto. Un bot desactivado, sin artefacto asignado o con el artefacto desactivado responde el aviso de no disponible.
- **FR-006**: Un mismo servicio debe atender a todos los bots; cada número de WhatsApp se atiende registrando un bot, sin cambios de código. Un mensaje de un número sin bot registrado se ignora y queda en el registro.
- **FR-007**: Al asignar un artefacto, el panel debe advertir que el bot responde a cualquiera que escriba al número y que los dominios deben ser información que se pueda decir a cualquiera.
- **FR-008**: Los textos fijos y los límites son los mismos para todos los bots en esta versión, y se pueden cambiar sin modificar el código.
- **FR-009**: Las acciones de administración de bots (registrar, cambiar artefacto, activar, desactivar) deben exigir un administrador y quedar en el registro de auditoría, como las de los demás módulos del panel.

**Comportamiento del bot**

- **FR-010**: El bot debe recibir los mensajes por el aviso (webhook) del proveedor de WhatsApp, verificar su firma y rechazar los que no la tengan válida.
- **FR-011**: El bot debe confirmar la recepción al proveedor en menos de 10 segundos siempre, y procesar la consulta después, sin que la confirmación dependa de la consulta.
- **FR-012**: Un mismo mensaje entregado más de una vez debe responderse una sola vez.
- **FR-013**: El bot debe pedir siempre a MIA el modo de respuesta literal, aunque el artefacto asignado permita razonamiento.
- **FR-014**: La respuesta debe incluir, en forma breve y dentro del mismo mensaje, los nombres de los documentos que la respaldaron (principio V de la constitución).
- **FR-015**: El bot debe adaptar la respuesta al chat (formato propio de WhatsApp, sin encabezados de otro formato) y dividirla en varios mensajes en orden si supera el límite de un mensaje.
- **FR-016**: Si MIA responde "sin información suficiente", el bot debe decirlo, sugerir reformular o preguntar por otro tema, no dar el contacto del programa y no enviar imágenes.
- **FR-017**: El bot no debe dar el contacto del programa en ninguna respuesta ni texto fijo.
- **FR-018**: Si la consulta no se puede hacer (tope diario alcanzado, artefacto o bot desactivado, falla o demora excesiva de MIA), el bot debe responder un aviso breve de que no puede atender ahora, sin reintentar y sin dejar la conversación en silencio, salvo lo dicho en FR-024.
- **FR-019**: Un mensaje que no es texto debe recibir el pedido de escribir la pregunta, y un texto de más de 500 caracteres el pedido de resumirlo; ninguno de los dos consulta a MIA.
- **FR-020**: La primera respuesta a un número en 24 horas debe llevar, dentro del mismo mensaje, un saludo que aclara que es un asistente automático que responde con documentos oficiales, pide no enviar datos personales e informa que las preguntas pasan por WhatsApp, el proveedor del bot y el proveedor del modelo.
- **FR-021**: El bot debe responder en español, a la conversación que originó el mensaje, sin depender de que el aviso incluya el número de teléfono.
- **FR-022**: Cada mensaje debe responderse por sí solo: el bot no recuerda mensajes anteriores de la conversación.
- **FR-023**: El bot debe funcionar de punta a punta con el número de pruebas (sandbox) del proveedor, que es el único entorno de esta entrega: solo los teléfonos registrados como de prueba le pueden escribir y no hace falta ningún número de producción.

**Límites y protección**

- **FR-024**: El bot debe contar de forma persistente los mensajes del mes (recibidos y enviados). Al llegar al tope mensual configurable (1.800 por defecto), debe dejar de responder para no gastar más cuota, y el panel lo debe mostrar.
- **FR-025**: El bot debe limitar los mensajes por número (10 por hora y 30 por día, configurables). Al superarlo, responde una sola vez que espere y no procesa más hasta que pase la ventana.
- **FR-026**: El bot debe limitar las consultas simultáneas a MIA (5 a la vez, cola de 20, configurables) y descartar sin responder lo que exceda la cola.
- **FR-027**: El número de teléfono solo debe usarse para los límites del bot y no debe guardarse en el registro de consultas.
- **FR-028**: Las consultas del bot deben contar en el tope diario del artefacto asignado y en el registro de Uso, como si las hiciera el propio artefacto; alcanzar el tope del bot no debe afectar a los demás artefactos.

**Imágenes asociadas a documentos**

- **FR-029**: En el inventario, cada documento debe permitir agregar, ver, ordenar, describir y quitar imágenes asociadas, con una descripción opcional que el bot usa de pie de foto.
- **FR-030**: Solo deben aceptarse imágenes PNG y JPG de hasta un tamaño máximo configurable (2 MB por defecto); lo demás se rechaza con un mensaje claro antes de subirlo.
- **FR-031**: Las imágenes deben conservarse con el resto de la información de MIA, de modo que sobrevivan a reinicios y despliegues.
- **FR-032**: Cada imagen debe poder obtenerse por un enlace público, sin clave y no adivinable, para que el proveedor de WhatsApp pueda enviarla. Reemplazar una imagen genera un enlace nuevo; el anterior deja de servir.
- **FR-033**: Al subir una imagen, el panel debe advertir que será pública.
- **FR-034**: La respuesta de una consulta debe incluir las imágenes de los documentos citados por la respuesta, en el orden de las fuentes. Una respuesta "sin información" no incluye imágenes, y tampoco se incluyen imágenes de documentos que solo se le pasaron al modelo sin aportar.
- **FR-035**: El bot debe enviar como máximo un número configurable de imágenes por respuesta (una por defecto), con su descripción como pie de foto. Si una imagen falla al enviarse, el texto ya enviado no se pierde y el fallo queda registrado.
- **FR-036**: Los administradores deben gestionar imágenes con el mismo alcance que ya tienen sobre los documentos; no puede asociarse una imagen a un documento fuera de su alcance.
- **FR-037**: Quitar o reemplazar una imagen debe regir en la consulta siguiente, sin reiniciar nada.
- **FR-038**: Sin imágenes asociadas, las consultas deben responder exactamente como hoy: la lista de imágenes va vacía y ningún otro artefacto cambia.

**Compatibilidad y operación**

- **FR-039**: Con el bot desactivado o sin ningún bot registrado, el comportamiento de MIA debe ser el anterior; las pruebas existentes y la batería del MVP deben seguir dando el mismo resultado.
- **FR-040**: El servicio del bot debe poder desactivarse desde el panel (bot o artefacto) sin tocar el servicio.
- **FR-041**: Al implementarse, la documentación de arquitectura y de operación debe quedar al día (nuevo servicio, variables, despliegue y límites).

### Key Entities *(include if feature involves data)*

- **Bot**: un canal de WhatsApp registrado. Tiene nombre único, el número de WhatsApp al que responde (único entre bots), el artefacto asignado, su estado (activo o desactivado) y el conteo de mensajes del mes. Se administra desde el módulo Bots del panel.
- **Artefacto**: ya existe. Define los dominios, los modos, el tope diario y el estado con los que consulta un cliente. Un bot consulta con el artefacto que tiene asignado; cambiar los dominios del artefacto o asignar otro cambia lo que el bot ve.
- **Imagen de documento**: una imagen PNG o JPG asociada a un documento, con descripción opcional, orden y un enlace público. Un documento puede tener varias.
- **Documento**: ya existe. Gana la posibilidad de tener imágenes asociadas; una versión nueva del mismo archivo es otro documento y no hereda las imágenes.
- **Consumo mensual de mensajes**: cuenta de mensajes recibidos y enviados por bot en el mes, que se conserva entre reinicios y se compara con el tope mensual.
- **Conversación (transitoria)**: lo que el bot sabe de un número mientras limita su uso (mensajes recientes y si ya recibió el saludo en 24 horas). No se guarda con el número en el registro de consultas.
- **Consulta (registro de Uso)**: ya existe. Las consultas del bot se registran con el artefacto asignado, sin el número de teléfono.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Las preguntas que tienen respuesta en los documentos habilitados reciben el texto en menos de 5 segundos en la mitad de los casos y en menos de 10 en el 95 %, medido desde que llega el mensaje hasta que se envía la respuesta (línea base de la consulta en modo literal: 1,7 s y 5,0 s).
- **SC-002**: El 100 % de los mensajes que el proveedor entrega más de una vez reciben una sola respuesta, y el 100 % de las confirmaciones al proveedor se dan en menos de 10 segundos aun cuando la consulta tarda más.
- **SC-003**: Con una imagen asociada al documento de matrícula, 5 de 5 formulaciones distintas de la pregunta por el horario devuelven el texto y la imagen, sin otra configuración.
- **SC-004**: Ninguna de las preguntas sin respuesta en los documentos (los casos "sin información" de la batería del MVP y los de la línea base de la V3) recibe una imagen, el contacto del programa ni una respuesta inventada.
- **SC-005**: Una persona administradora asocia una imagen a un documento, con descripción, en menos de 1 minuto desde el panel.
- **SC-006**: En el 100 % de las pruebas, cambiar el artefacto asignado o los dominios del artefacto desde el panel cambia lo que el bot responde en el mensaje siguiente, sin reiniciar ni redesplegar nada.
- **SC-007**: Una persona que supera el límite por hora recibe un solo aviso y se procesan 0 mensajes suyos más hasta que pasa la ventana; una ráfaga mayor que la cola no provoca más de 5 consultas simultáneas a MIA.
- **SC-008**: Con el proveedor simulado, el bot envía 0 mensajes después de alcanzar el tope mensual, y el conteo del mes se conserva tras reiniciar el servicio.
- **SC-009**: El gasto de modelos por pregunta del bot no supera 0,001 USD de costo medio (línea base del modo literal: 0,0004 USD), y el módulo Uso lo muestra por artefacto.
- **SC-010**: 0 registros de consultas contienen un número de teléfono.
- **SC-011**: La batería del MVP da 19 de 19 como antes y todas las pruebas existentes siguen pasando; los demás artefactos responden con la misma estructura y la lista de imágenes vacía.
- **SC-012**: Con el bot o su artefacto desactivados, el 100 % de los mensajes reciben el aviso de no disponible y los demás artefactos no se ven afectados.

## Assumptions

- Quien opera MIA es una sola persona (el usuario); quien escribe al bot es el público externo (personas interesadas en los posgrados), anónimo y sin identificación previa.
- Los requerimientos acordados están en `docs/Definicion_Requerimientos_Bot_WhatsApp.md` (borrador del 2026-10-21); esta spec los concreta como historias y requisitos verificables y no los reemplaza. Donde ese documento propone un valor (límites, textos), es el valor de partida y se puede ajustar con el uso.
- **El entorno de esta entrega es el sandbox de Kapso** (decisión del 2026-10-24: por ahora no es posible más). Solo escriben los teléfonos registrados como de prueba (cuántos admite y cuánto dura la sesión de prueba lo define Kapso), y el sandbox admite texto y mensajes interactivos; si admite el envío de imágenes por enlace no está documentado y es lo primero que se comprueba. El registro en Meta, un número de producción, un plan de pago y la campaña no se implementan ni se validan aquí: se documentan en la sección 11 del documento de requerimientos.
- Hay un solo número de WhatsApp, el del sandbox. La estructura admite varios bots, pero registrar el segundo bot, su plan y su número quedan fuera de esta feature.
- Qué dominios ve el bot en su primera versión se decide al configurar el artefacto asignado, desde el panel. Para la atracción de estudiantes deben ser información que se pueda decir a cualquiera (la constitución exige un control de acceso antes de exponer datos de personas por WhatsApp); no se asignan las actas del Consejo.
- La cuota gratuita (2.000 mensajes al mes del proveedor y 1.000 gratuitos por número de Meta) da unas 500 a 1.000 preguntas al mes. Si esa cuota alcanza para la campaña, o conviene contratar un plan y pagar los mensajes de servicio de Meta (cuya tarifa depende del país y no se conoce), es una decisión del usuario fuera de esta feature; el tope mensual de mensajes protege la cuota gratuita mientras tanto.
- El bot depende de las fuentes citadas por la respuesta (feature 006, `QUERY_CITED_SOURCES` en `on`, decidido en el cierre de la V3 el 2026-10-21) para saber qué documentos aportaron y cuáles imágenes enviar. Con esa opción apagada se mostrarían imágenes de todos los pasajes, por lo que debe estar encendida para el bot.
- El modo literal usa hoy `z-ai/glm-5.3-flash` con razonamiento bajo por OpenRouter con retención cero; el costo medio de 0,0004 USD por consulta viene de la medición de la V3. El tope diario inicial del artefacto es 1 USD y se ajusta desde el panel.
- Las imágenes se guardan con la información de MIA y se sirven públicas porque el proveedor las envía a partir de un enlace; el espacio de la base gratuita es limitado (0,5 GB), por lo que se aceptan imágenes livianas (2 MB por defecto).
- El estado transitorio del bot (mensajes ya vistos, límites por número, saludo en 24 horas) vive en memoria del servicio y puede reiniciarse al reiniciar el servicio; se acepta para el prototipo. El conteo mensual de mensajes, en cambio, debe conservarse.
- El proveedor puede no incluir el número de teléfono en el aviso (migración a identificadores de usuario): el bot responde a la conversación sin depender de él.
- El servicio del bot lo crea el usuario desde la interfaz de Railway y se despliega con el flujo de los demás servicios; el lenguaje del servicio, el mecanismo con que se identifica ante la API y dónde se guarda el contador mensual se deciden en el plan.
- La API aplica las migraciones de la base al arrancar: la feature agrega migraciones nuevas tras la `0005` y no debe desplegarse una versión con menos migraciones que las de la base.
- Quedan fuera de esta feature: memoria de conversación, mensajes que no son texto, mensajes iniciados por el programa, ofrecer el contacto o pasar a una persona, modo con razonamiento, textos y límites distintos por bot, imágenes que dependan de la pregunta y no del documento, estadísticas propias del bot en Uso todo lo de las secciones 10 y 11 del documento de requerimientos (cómo escalar y pasar a producción), y el registro en Meta, un número de producción, un plan de pago de Kapso y la campaña. El bot tampoco usa LangChain ni LangGraph (decisión del 2026-10-21 en `docs/ARQUITECTURA.md`).
