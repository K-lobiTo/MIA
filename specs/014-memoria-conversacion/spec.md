# Feature Specification: Memoria de conversación configurable por artefacto

**Feature Branch**: `dev` (feature `014-memoria-conversacion`, sin rama propia por decisión del usuario)

**Created**: 2026-11-03

**Status**: Draft

**Input**: User description: "Memoria de conversación configurable por artefacto (context window): hoy cada consulta es independiente y la Consulta administrativa, aunque muestra un chat, no envía nada del historial. Se quiere que cada artefacto tenga un parámetro 'memoria de conversación' (cuántas vueltas completas recuerda y entrega al modelo) editable desde el panel de administración, para que las preguntas de seguimiento ('¿y cuánto cuesta?', '¿y el segundo?') funcionen, con cuidado en el cambio entre modo literal y con razonamiento a mitad del chat. El bot de WhatsApp queda como está; solo se agrega ajustar el tamaño de su memoria desde el módulo Bots."

Contexto: la Consulta administrativa muestra una conversación, pero cada pregunta llega a MIA sola: el modelo ve únicamente la pregunta actual y los fragmentos de documentos recuperados. Una pregunta de seguimiento como "¿y cuánto cuesta?" o "¿y el segundo?" no dice de qué se habla, así que la búsqueda no encuentra fragmentos relacionados y la respuesta es "sin información" antes de llegar al modelo. La persona tiene que repetir el contexto en cada pregunta. Cuatro hechos condicionan el diseño:

1. **La memoria es un parámetro de cada artefacto.** Hay artefactos de distinto uso y presupuesto: algunos se benefician de recordar la conversación y otros no, y recordarla cuesta (más texto de entrada en cada consulta). Por eso la decide quien administra, por artefacto, desde el panel, y por defecto está apagada.
2. **El historial no es una fuente de datos.** MIA responde únicamente con lo que dicen los documentos, y cada respuesta debe poder citar su fuente. Si el modelo tratara la respuesta anterior como un hecho, una inferencia calculada en el modo con razonamiento podría repetirse en el modo literal como si un documento la dijera. El historial sirve solo para entender la pregunta.
3. **El modo puede cambiar a mitad de la conversación.** En la Consulta la persona elige el modo (literal o con razonamiento) en cada pregunta. La memoria debe funcionar igual cuando las vueltas anteriores fueron de otro modo, sin contaminar las respuestas ni romper el estilo de cada modo.
4. **Recordar la conversación no sirve si la búsqueda no la usa.** Entregar el historial al modelo no arregla un seguimiento que ya se cortó en "sin información" antes de llegar a él: hay que usar el historial también para buscar los documentos. Hay dos formas posibles (por reglas y con el modelo) y se prueban y comparan antes de elegir una por defecto.

## Clarifications

### Session 2026-11-03

- Q: ¿Qué es la "memoria" que se configura? → A: La memoria de la conversación (cuántas preguntas y respuestas anteriores recuerda el sistema), no la ventana de documentos por consulta.
- Q: ¿En qué unidad se mide? → A: En vueltas completas (una vuelta es una pregunta y su respuesta), con un máximo de 10.
- Q: ¿Un parámetro por artefacto o uno por modo? → A: Uno solo por artefacto; el sistema aplica un recorte de tamaño distinto por modo.
- Q: ¿Qué pasa con las respuestas de otro modo en el historial? → A: Se conservan. El modelo recibe la regla explícita de que el historial solo sirve para entender la pregunta y nunca es fuente de datos: toda respuesta sale únicamente de los fragmentos recuperados.
- Q: ¿Cómo se recuperan los seguimientos? → A: Se implementan dos estrategias seleccionables por configuración (por reglas, sin modelo; y con el modelo, una llamada corta que reescribe la pregunta) y se elige la predeterminada con una medición con casos reales.
- Q: ¿Qué cambia en el bot de WhatsApp? → A: Nada de su comportamiento (solo modo literal; su contexto propio sirve solo para la aclaración de programa y el programa recordado, sin historial al modelo). Solo se agrega poder ajustar el tamaño de esa memoria desde el módulo Bots, como parámetro propio del bot.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - La persona hace una pregunta de seguimiento y el sistema la entiende (Priority: P1)

En la Consulta administrativa, la persona pregunta por un tema y recibe su respuesta. Luego hace una pregunta de seguimiento que solo se entiende con lo anterior ("¿y cuánto cuesta?", "¿y el segundo?", "¿cuándo es eso?"). El sistema usa las últimas vueltas de la conversación, que el artefacto está configurado para recordar, para entender la pregunta, buscar los documentos adecuados y responder con su fuente.

**Why this priority**: es el propósito de la feature. Sin esto, la Consulta es una caja de preguntas sueltas aunque muestre un chat.

**Independent Test**: con un artefacto con memoria de 3 vueltas, preguntar por un programa, esperar la respuesta y preguntar "¿y cuánto cuesta?": la respuesta da el costo de ese programa y cita su documento, en vez de "sin información".

**Acceptance Scenarios**:

1. **Given** un artefacto con memoria mayor que 0 y una pregunta respondida, **When** la persona hace un seguimiento sin tema ("¿y cuánto cuesta?"), **Then** el sistema responde sobre el tema de la vuelta anterior, con las fuentes de los fragmentos recuperados para esa pregunta.
2. **Given** un seguimiento con pronombre o referencia ("¿y el segundo?", "¿qué requisitos tiene eso?"), **When** la respuesta anterior lo hace entendible, **Then** el sistema lo entiende con el historial de las últimas vueltas.
3. **Given** una pregunta que se entiende sola, **When** hay historial, **Then** el sistema responde sobre lo que la pregunta dice, sin forzar el tema de las vueltas anteriores.
4. **Given** una conversación con más vueltas que la memoria del artefacto, **When** la persona pregunta, **Then** el sistema solo recuerda las últimas vueltas que el artefacto permite y olvida las anteriores.
5. **Given** que la persona empieza una conversación nueva (borra el chat o recarga la página), **When** pregunta, **Then** no se recuerda nada de la anterior.
6. **Given** una conversación con memoria, **When** la persona ve el chat, **Then** la Consulta le dice cuántas preguntas recuerda ("recuerda las últimas N preguntas").

---

### User Story 2 - Quien administra define la memoria de cada artefacto desde el panel (Priority: P1)

Una persona administradora abre el módulo de artefactos del panel y define, para un artefacto, cuántas vueltas recuerda su conversación (de 0 a 10). El panel explica que más memoria significa más texto en cada consulta y, por tanto, más costo, y que 0 es el comportamiento de siempre. El cambio rige desde la consulta siguiente, sin reiniciar nada.

**Why this priority**: sin el parámetro no hay forma de decidir por artefacto ni de volver atrás; es la condición para que la feature sea segura de encender.

**Independent Test**: en el panel, cambiar la memoria de un artefacto de 0 a 3, hacer una pregunta y un seguimiento desde ese artefacto (funciona), volver a 0 y repetir (el seguimiento vuelve a no entenderse), sin reiniciar nada.

**Acceptance Scenarios**:

1. **Given** el formulario de un artefacto (al crearlo o al editarlo), **When** la persona administradora lo abre, **Then** ve el campo de memoria con su valor actual (0 en los artefactos existentes), un mínimo de 0, un máximo de 10 y una explicación del costo.
2. **Given** un valor fuera de rango (negativo, mayor que 10 o no numérico), **When** se intenta guardar, **Then** se rechaza con un mensaje claro y no se cambia nada.
3. **Given** un cambio de memoria guardado, **When** llega la consulta siguiente de ese artefacto, **Then** rige el valor nuevo, sin reiniciar nada.
4. **Given** una persona administradora de alcance de programa, **When** edita un artefacto de su programa, **Then** puede cambiar su memoria (mismo alcance que para el resto de sus parámetros); fuera de su alcance se rechaza como hoy.
5. **Given** un cambio de memoria, **When** se revisa el registro de administración, **Then** hay una línea con quién lo hizo, el artefacto, el valor anterior y el nuevo, y cuándo.
6. **Given** el listado de artefactos del panel, **When** se revisa un artefacto, **Then** se ve su memoria de conversación junto a sus demás parámetros.

---

### User Story 3 - Cambiar de modo a mitad de la conversación no contamina las respuestas (Priority: P1)

La persona alterna entre el modo literal y el modo con razonamiento durante la misma conversación. Las vueltas anteriores, sean del modo que sean, ayudan a entender la pregunta, pero **nunca son fuente de datos**: la respuesta siempre sale de los fragmentos recuperados de los documentos. Una cifra calculada o una inferencia hecha en el modo con razonamiento no se repite en el modo literal como si un documento la dijera.

**Why this priority**: protege la regla central de MIA (toda respuesta es trazable a un documento) y la promesa del modo literal ("lo que dice exactamente un documento").

**Independent Test**: en razonamiento, pedir un cálculo con datos de varios documentos (por ejemplo, la suma de créditos); luego, en literal, preguntar "¿y cuántos son entonces?" o "confírmame ese total": el modo literal no da el total como dato documental (responde solo con lo que dicen los fragmentos o dice que no lo encuentra).

**Acceptance Scenarios**:

1. **Given** una vuelta en modo con razonamiento con un valor calculado, **When** la siguiente pregunta es en modo literal y pide ese valor, **Then** la respuesta no lo presenta como lo que dice un documento: solo usa lo que dicen los fragmentos recuperados, o responde que no lo encuentra.
2. **Given** una vuelta en modo literal corta y una pregunta siguiente en modo con razonamiento, **When** se responde, **Then** el modo con razonamiento entiende la pregunta con la vuelta anterior y mantiene su formato propio.
3. **Given** un historial con vueltas de los dos modos, **When** se responde en cualquiera de ellos, **Then** la respuesta mantiene el estilo propio del modo en que se preguntó (no imita el de las vueltas del otro modo).
4. **Given** un artefacto que solo permite un modo, **When** hay historial, **Then** funciona con ese modo; el historial no puede abrir un modo no permitido.
5. **Given** que el modo con razonamiento falla y la persona reintenta en el modo literal, **When** se arma el historial, **Then** el intercambio fallido no forma parte de él.
6. **Given** cualquier modo, **When** se entrega el historial al modelo, **Then** la instrucción que lo acompaña dice que solo sirve para entender la pregunta y que toda respuesta sale únicamente de los fragmentos recuperados.

---

### User Story 4 - Con la memoria en 0 todo queda exactamente como hoy (Priority: P1)

El valor por defecto es 0: ningún artefacto existente cambia hasta que una persona administradora lo decida. Con 0, aunque un cliente envíe historial, el sistema lo ignora. Las pruebas existentes, la batería del MVP y los demás artefactos (incluido el bot de WhatsApp) responden igual que antes, con el mismo costo.

**Why this priority**: es un cambio en el camino de consulta compartido por todo el sistema; no debe degradar nada fuera de lo que se enciende.

**Independent Test**: con memoria 0, correr las pruebas existentes y la batería del MVP (19 de 19), y comprobar que una consulta que trae historial responde igual que sin él y cuesta lo mismo.

**Acceptance Scenarios**:

1. **Given** un artefacto con memoria 0, **When** un cliente envía un historial, **Then** el sistema lo ignora por completo (no cambia la búsqueda, ni lo que ve el modelo, ni el costo).
2. **Given** los artefactos existentes tras la actualización, **When** se revisa su memoria, **Then** todos están en 0.
3. **Given** una consulta sin historial (cualquier artefacto), **When** se responde, **Then** el resultado, las fuentes, las imágenes y el costo son los de siempre.
4. **Given** la batería de aceptación del MVP y las pruebas existentes, **When** se ejecutan, **Then** dan el mismo resultado que antes (19 de 19).
5. **Given** el bot de WhatsApp, **When** recibe preguntas, **Then** responde igual que antes y no le llega historial al modelo.
6. **Given** un cliente anterior a esta feature que no sabe del historial, **When** consulta, **Then** funciona sin cambios.

---

### User Story 5 - El historial es acotado, validado y privado (Priority: P2)

El historial llega del cliente (la Consulta ya lo tiene en la memoria de la página) y el sistema no confía en él: lo recorta a las últimas vueltas que el artefacto permite, valida el tamaño y los roles, recorta el texto de cada respuesta y el total según el modo, y deja fuera los intercambios fallidos y las respuestas de "sin información". No se guarda en ningún lado: ni en una sesión del servidor ni en el registro de Uso, que sigue registrando solo la pregunta actual.

**Why this priority**: la condición de seguridad y privacidad para aceptar un historial enviado por quien consulta; sin ella, la feature abriría un canal de abuso y de datos personales en reposo.

**Independent Test**: enviar historiales con más vueltas que la memoria, con textos enormes, con un rol de sistema y con intercambios fallidos, y comprobar que el sistema usa solo lo permitido; y revisar que ni la base ni el registro de Uso guardan el historial.

**Acceptance Scenarios**:

1. **Given** un historial con más vueltas que la memoria del artefacto, **When** se consulta, **Then** solo cuentan las últimas vueltas permitidas.
2. **Given** un historial con un mensaje con un rol distinto de persona o asistente (por ejemplo, de sistema), **When** se consulta, **Then** ese mensaje se descarta o la consulta se rechaza; nunca llega al modelo como instrucción.
3. **Given** respuestas anteriores muy largas, **When** se arma el historial, **Then** cada respuesta se recorta a un tamaño máximo y el total no supera el máximo del modo (el modo con razonamiento admite más).
4. **Given** un historial con intercambios fallidos o con respuestas de "sin información", **When** se arma, **Then** esos intercambios no forman parte de él.
5. **Given** una consulta con historial, **When** se revisa la base y el registro de Uso, **Then** solo queda la pregunta actual (como hoy); el historial no se guarda.
6. **Given** un historial malformado (no es una lista, vueltas incompletas, textos que no son texto), **When** se consulta, **Then** la respuesta es un error claro de validación o se ignora la parte inválida, sin romper la consulta.

---

### User Story 6 - Un seguimiento corto encuentra los documentos gracias a la reformulación (Priority: P2)

Cuando hay historial, el sistema usa las vueltas anteriores también para **buscar** los documentos, no solo para que el modelo entienda: un seguimiento corto ("¿y cuánto cuesta?") se reformula con lo que se venía hablando para que la búsqueda encuentre los fragmentos correctos. Hay dos formas de hacerlo, ambas disponibles y seleccionables por configuración: por reglas (sin modelo de lenguaje, por ejemplo juntar la pregunta anterior con la actual) y con el modelo (una llamada corta que reescribe la pregunta). La forma por defecto se elige comparando las dos con casos reales de seguimiento.

**Why this priority**: sin reformular, el parámetro de memoria existiría pero los seguimientos seguirían cortándose en "sin información" antes de llegar al modelo; es lo que le da valor real a la feature.

**Independent Test**: con los casos de seguimiento del conjunto de pruebas, medir cuántos seguimientos encuentran el documento esperado con cada estrategia (y sin reformular), y comparar costo y tiempo; la estrategia por defecto es la mejor según esa medición.

**Acceptance Scenarios**:

1. **Given** un seguimiento corto y un historial, **When** se usa la estrategia por reglas, **Then** la búsqueda usa una pregunta que combina el tema anterior con la actual, sin llamar a ningún modelo de lenguaje adicional.
2. **Given** el mismo caso, **When** se usa la estrategia con el modelo, **Then** una llamada corta reescribe la pregunta completa y la búsqueda usa esa reescritura; el costo de esa llamada cuenta en el costo de la consulta.
3. **Given** una pregunta que se entiende sola, **When** hay historial, **Then** no se reformula (o la reformulación no cambia lo que se busca) y se responde como si no hubiera historial.
4. **Given** la configuración de la instancia, **When** se elige una estrategia (o ninguna), **Then** rige desde la consulta siguiente sin reiniciar el artefacto.
5. **Given** los casos de seguimiento, **When** se mide cada estrategia, **Then** el informe muestra por caso si encontró el documento esperado, el costo y el tiempo, y deja anotada la estrategia elegida por defecto con sus números.
6. **Given** que la reformulación falla (error del modelo o respuesta vacía), **When** se consulta, **Then** el sistema sigue con la pregunta original sin reformular y la persona no ve un error.

---

### User Story 7 - El costo está a la vista y los topes siguen valiendo (Priority: P2)

Con memoria, cada consulta lleva más texto de entrada (en una consulta típica, entre un cuarto y un tercio más con 4 vueltas) y el modo con razonamiento un poco más. El costo adicional cuenta dentro del costo de la consulta y de los topes diarios del artefacto y del modo, que siguen aplicando exactamente igual. El panel avisa del costo al configurar la memoria.

**Why this priority**: el sistema tiene un presupuesto limitado y topes de gasto; la memoria no debe permitir saltárselos ni sorprender con el costo.

**Independent Test**: comparar el costo medio de una misma serie de preguntas con memoria 0 y con memoria 4, y comprobar que el tope diario sigue deteniendo al artefacto cuando se alcanza.

**Acceptance Scenarios**:

1. **Given** una consulta con historial, **When** se registra, **Then** su costo en Uso incluye el texto de entrada adicional y, con la estrategia con modelo, la llamada de reformulación.
2. **Given** un artefacto que alcanzó su tope diario (o el del modo con razonamiento), **When** se consulta con historial, **Then** se rechaza como hoy; el historial no evita el tope.
3. **Given** la configuración de la memoria en el panel, **When** se edita, **Then** el aviso dice que más vueltas significa más texto en cada consulta y más costo.
4. **Given** una serie de preguntas de seguimiento, **When** se compara con memoria 0 y con memoria 4, **Then** el aumento del costo medio queda medido y documentado.

---

### User Story 8 - Se puede ajustar la memoria del bot de WhatsApp desde el panel (Priority: P3)

El bot de WhatsApp no cambia su comportamiento: sigue solo en modo literal y su contexto propio sirve solo para la aclaración de programa y el programa recordado, sin entregar historial al modelo. Lo único nuevo es que, en el módulo Bots del panel, la persona administradora de alcance global puede ajustar cuántas vueltas recuerda el bot (mínimo 1, porque resolver una aclaración necesita al menos una vuelta; por defecto, el valor actual) sin tocar variables del servicio ni reiniciarlo.

**Why this priority**: es una comodidad de operación pedida por el usuario; el bot funciona igual sin ella.

**Independent Test**: en el módulo Bots, cambiar la memoria del bot de 2 a 4 vueltas y comprobar que el servicio del bot recuerda 4 vueltas desde el mensaje siguiente; volver al valor por defecto.

**Acceptance Scenarios**:

1. **Given** el formulario de un bot en el módulo Bots, **When** se abre, **Then** muestra su memoria (el valor actual por defecto, 2 vueltas), con mínimo 1 y máximo 10.
2. **Given** un valor fuera de rango (0, mayor que 10 o no numérico), **When** se intenta guardar, **Then** se rechaza con un mensaje claro.
3. **Given** un cambio de memoria del bot, **When** llega el mensaje siguiente, **Then** el servicio del bot usa el valor nuevo, sin reiniciar nada.
4. **Given** el bot con cualquier memoria, **When** responde, **Then** no entrega historial al modelo ni cambia de modo: solo cambia cuánto recuerda para la aclaración y el programa.
5. **Given** que el servicio del bot no puede consultar la configuración, **When** llega un mensaje, **Then** usa el valor por defecto y el bot sigue respondiendo.
6. **Given** un cambio de memoria del bot, **When** se revisa el registro de administración, **Then** hay una línea con quién lo hizo, el bot, el valor anterior y el nuevo.

---

### Edge Cases

- La persona cambia de tema a mitad de la conversación: una pregunta que se entiende sola se responde sobre lo que dice, aunque las vueltas anteriores hablen de otro tema.
- La memoria es mayor que las vueltas que hay: se usan las que hay.
- La memoria de un artefacto baja de 5 a 2 con una conversación en curso: desde la consulta siguiente solo se usan 2 vueltas.
- El cliente envía más vueltas de las que el artefacto permite: se recortan en el servidor a las últimas permitidas, aunque el cliente no lo haga.
- Una respuesta anterior contiene datos personales que la persona escribió: el sistema no la guarda en ningún lado; solo la entrega al modelo en esa consulta (igual que la pregunta actual).
- La respuesta anterior fue una imagen o contenido con formato (listas, negritas): se entrega como texto sin las imágenes.
- Una respuesta anterior es de "sin información" o falló: no forma parte del historial (no ayuda a entender la pregunta y sesga al modelo a negarse).
- El modo con razonamiento no está disponible (tope o falla) y el historial tiene vueltas de ese modo: la consulta en modo literal funciona con ese historial.
- La persona alterna de modo en cada pregunta: cada respuesta mantiene el estilo de su modo y no trata el historial como fuente.
- La reformulación con el modelo devuelve algo vacío, demasiado largo o que cambia el tema: se descarta y se usa la pregunta original.
- Un cliente envía historial a un artefacto con memoria 0: se ignora.
- Dos artefactos distintos con memorias distintas atienden a la misma persona: cada uno aplica la suya.
- La consulta con historial es rechazada (permisos, tope): el rechazo es el de siempre y no revela nada del historial.
- La conversación es muy larga para el contexto del modelo del modo: el recorte por modo evita excederlo; si aun así el proveedor responde error, se trata como cualquier falla del proveedor (la persona puede reintentar).

## Requirements *(mandatory)*

### Functional Requirements

**Parámetro por artefacto y panel**

- **FR-001**: Cada artefacto debe tener un parámetro de memoria de conversación, en vueltas completas (una vuelta es una pregunta y su respuesta), de 0 a 10, con valor por defecto 0 para todos los artefactos existentes y nuevos.
- **FR-002**: El panel de administración debe permitir ver y editar la memoria de conversación de un artefacto (al crearlo y al editarlo), con el mismo alcance (global o por programa) que ya rige para sus demás parámetros, y debe explicar que más memoria significa más texto en cada consulta y más costo, y que 0 es el comportamiento de siempre.
- **FR-003**: Un valor fuera de rango o no numérico debe rechazarse con un mensaje claro, sin cambiar nada. El cambio debe regir desde la consulta siguiente, sin reiniciar nada.
- **FR-004**: Cada cambio de memoria debe dejar una línea en el registro de administración con quién lo hizo, el artefacto, el valor anterior y el nuevo, y cuándo.
- **FR-005**: La configuración que reciben los clientes debe informar cuántas vueltas puede recordar el artefacto, para que cada cliente envíe solo ese número y avise a la persona.

**Historial y modos**

- **FR-006**: Una consulta puede traer un historial de vueltas anteriores (preguntas y respuestas de la conversación). El sistema solo debe usarlo si la memoria del artefacto es mayor que 0; con 0 debe ignorarlo por completo.
- **FR-007**: El sistema debe usar únicamente las últimas vueltas que la memoria del artefacto permite, aunque el cliente envíe más; debe validar el historial (solo roles de persona y asistente, textos de texto, tamaños) y no aceptar nunca un mensaje de sistema como instrucción.
- **FR-008**: El texto de cada respuesta anterior debe recortarse a un máximo, y el total del historial a un máximo por modo (el modo con razonamiento admite más que el literal), de modo que no exceda lo que cada modelo admite.
- **FR-009**: Los intercambios fallidos y las respuestas de "sin información" no deben formar parte del historial que se usa.
- **FR-010**: El historial no debe guardarse en ninguna parte (ni sesión del servidor ni base ni registro de Uso): Uso sigue registrando solo la pregunta actual.
- **FR-011**: Las respuestas de cualquier modo deben conservarse en el historial, aunque la siguiente pregunta use el otro modo. Junto al historial, el modelo debe recibir la regla explícita de que **solo sirve para entender la pregunta, nunca es fuente de datos**, y que toda respuesta sale únicamente de los fragmentos recuperados de los documentos.
- **FR-012**: Cada modo debe conservar su estilo y su instrucción propios al responder, aunque el historial tenga vueltas del otro modo. El historial no puede abrir un modo que el artefacto no permite.

**Reformulación de la búsqueda**

- **FR-013**: Con historial y memoria mayor que 0, el sistema debe usar las vueltas anteriores para reformular la búsqueda de documentos cuando la pregunta lo necesite (un seguimiento corto), de modo que no se corte en "sin información" por falta de contexto.
- **FR-014**: Deben existir dos estrategias de reformulación seleccionables por configuración de la instancia: **por reglas** (sin ningún modelo de lenguaje adicional) y **con el modelo** (una llamada corta que reescribe la pregunta); también debe poder desactivarse la reformulación. El cambio de estrategia debe regir sin reiniciar el artefacto.
- **FR-015**: Una pregunta que se entiende sola no debe cambiar por tener historial: se busca y se responde como si no lo hubiera.
- **FR-016**: Si la reformulación falla o devuelve algo inutilizable, el sistema debe seguir con la pregunta original sin mostrar un error.
- **FR-017**: La estrategia por defecto debe elegirse comparando las dos con casos reales de seguimiento, y esa comparación (aciertos, costo y tiempo por estrategia) debe quedar documentada.

**Costo y topes**

- **FR-018**: El costo adicional del historial y de la reformulación con el modelo debe contar dentro del costo registrado de la consulta y de los topes diarios del artefacto y del modo, que deben seguir aplicando exactamente igual (un artefacto que alcanzó su tope no consulta aunque traiga historial).

**Lo que no cambia**

- **FR-019**: Con la memoria en 0, las consultas, sus resultados, sus fuentes, sus imágenes y su costo deben ser exactamente los de antes. Las pruebas existentes y la batería de aceptación del MVP (19 de 19) deben seguir dando el mismo resultado.
- **FR-020**: Los clientes que no conocen el historial deben seguir funcionando sin cambios.
- **FR-021**: El bot de WhatsApp no debe cambiar su comportamiento: sigue solo en modo literal y no debe entregar historial al modelo; su contexto propio sigue sirviendo solo para la aclaración de programa y el programa recordado.

**Memoria del bot**

- **FR-022**: El módulo Bots del panel debe permitir a la persona administradora de alcance global ver y ajustar la memoria del bot en vueltas (mínimo 1, máximo 10, por defecto el valor actual de 2 vueltas), con un mensaje claro ante valores fuera de rango.
- **FR-023**: El servicio del bot debe usar el valor configurado desde el mensaje siguiente al cambio, sin reiniciar. Si no puede conocerlo, debe usar el valor por defecto y seguir respondiendo.
- **FR-024**: Cada cambio de la memoria del bot debe dejar una línea en el registro de administración (quién, el bot, valor anterior y nuevo, cuándo).

**Consulta administrativa**

- **FR-025**: La Consulta administrativa debe enviar con cada pregunta las últimas vueltas de la conversación (solo las respondidas con éxito y con respuesta, hasta el número que informa la configuración), no debe enviar nada si la memoria es 0, y debe avisar a la persona cuántas preguntas recuerda el artefacto cuando es mayor que 0.

**Medición y documentación**

- **FR-026**: Debe haber casos de prueba nuevos de seguimiento: con un programa o tema anterior, con pronombres, con cambio de modo entre vueltas, y con una respuesta calculada en razonamiento seguida de una pregunta literal que no debe tratarla como dato documental; y la medición de costo con memoria 0 y con memoria 4.
- **FR-027**: La documentación de arquitectura, de operación y del panel debe quedar al día: qué hace la memoria, el límite de 10, los recortes por modo, las estrategias de reformulación y cuál rige por defecto, el costo medido, qué se guarda (nada) y cómo volver atrás (memoria 0).

### Key Entities *(include if feature involves data)*

- **Memoria de conversación del artefacto**: un número de vueltas (0 a 10, por defecto 0) que se agrega a los parámetros del artefacto. Es lo único que se guarda de esta feature.
- **Vuelta de conversación**: una pregunta y su respuesta. Vive en el cliente y se envía con cada consulta; el sistema no la guarda.
- **Historial de la consulta**: las últimas vueltas aceptadas (recortadas y validadas) que acompañan a una consulta; vive solo durante esa consulta.
- **Estrategia de reformulación**: una opción de configuración de la instancia (por reglas, con el modelo o ninguna) que decide cómo se usa el historial para buscar.
- **Memoria del bot**: un número de vueltas (1 a 10, por defecto 2) propio de cada bot, que el servicio del bot usa para dimensionar su contexto de aclaración y programa recordado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el conjunto de casos de seguimiento (con tema anterior y con pronombres), con la memoria encendida y la estrategia elegida, al menos el 80 % de los seguimientos encuentra el documento esperado y responde con su fuente, frente a 0 % o casi 0 % sin memoria.
- **SC-002**: En el 100 % de los casos de prueba con una respuesta calculada en razonamiento seguida de una pregunta literal que pide ese valor, la respuesta literal no presenta el valor como dato de un documento.
- **SC-003**: En el 100 % de los casos de prueba con cambio de modo entre vueltas, cada respuesta mantiene el estilo de su modo y cita fuentes de los fragmentos recuperados (no del historial).
- **SC-004**: Con la memoria en 0, el 100 % de las consultas da el mismo resultado, las mismas fuentes y el mismo costo que antes, aunque el cliente envíe historial; la batería del MVP da 19 de 19 y todas las pruebas existentes siguen pasando.
- **SC-005**: Ningún historial se guarda: en el 100 % de las comprobaciones, la base y el registro de Uso solo contienen la pregunta actual de cada consulta.
- **SC-006**: En el 100 % de las pruebas con historial malicioso o malformado (más vueltas que las permitidas, rol de sistema, textos enormes), el sistema usa solo lo permitido y nunca un mensaje de sistema.
- **SC-007**: El aumento del costo medio por consulta con memoria 4 frente a memoria 0 queda medido con una serie de preguntas de seguimiento y documentado, y los topes diarios siguen deteniendo al artefacto en el 100 % de los casos de prueba.
- **SC-008**: La comparación de las dos estrategias de reformulación (aciertos, costo y tiempo por estrategia y por caso) queda documentada, y la estrategia elegida por defecto es la de mejor resultado según esa medición.
- **SC-009**: Una persona administradora cambia la memoria de un artefacto desde el panel y el cambio rige en la consulta siguiente en el 100 % de los casos, sin reiniciar nada; lo mismo con la memoria del bot.
- **SC-010**: Con el bot de WhatsApp, el 100 % de las respuestas es igual que antes de la feature (sin historial al modelo, solo modo literal) y su contexto de aclaración sigue dando los mismos resultados con el valor por defecto.

## Assumptions

- Las decisiones del 3 de noviembre de 2026 (las seis de la sección "Clarifications") son el punto de partida; el análisis de viabilidad previo es el "por qué" del diseño (historial enviado por el cliente, recortado en la API, sin sesiones en el servidor).
- Los recortes de tamaño por modo tienen valores de partida configurables, que se calibran con los casos de prueba y con la medición de costo: respuestas anteriores de hasta unos 1.500 caracteres y total de historial de hasta unos 6.000 caracteres en el modo literal, y el doble en el modo con razonamiento (que recupera más fragmentos y usa modelos de contexto mayor).
- "Seguimiento corto" y "pregunta que se entiende sola" se distinguen con reglas simples (por ejemplo, longitud y ausencia de palabras con contenido propias) que se ajustan con los casos de prueba; el criterio exacto se decide en el plan.
- La estrategia por defecto se decide con la medición (FR-017); mientras no se mida, el sistema funciona con la reformulación por reglas, que no cuesta nada extra.
- La Consulta administrativa guarda la conversación solo en la memoria de la página (decisión de privacidad anterior): al recargar, empieza de cero; esta feature no cambia eso.
- El valor actual del contexto del bot es de 4 turnos (mensajes de la persona y del bot), es decir, 2 vueltas completas; el nuevo parámetro del bot se expresa en vueltas (mínimo 1, máximo 10, por defecto 2) y reemplaza a la variable del servicio como forma normal de ajustarlo; la variable queda como respaldo cuando la API no informa un valor. Sigue siendo en memoria, por persona (clave con hash), con vencimiento por inactividad y tope de conversaciones.
- Los clientes de la API distintos de la Consulta (otros sitios que consulten con la clave de un artefacto) pueden enviar historial si lo desean; los que no lo hagan siguen funcionando sin cambios.
- Se agrega una columna al artefacto y otra al bot (migraciones aditivas, con vuelta atrás); el historial no se guarda, así que no hay datos nuevos en reposo salvo esos dos números.
- Es un prototipo de vigencia corta: se prefiere lo más simple que cumpla la especificación. Quedan fuera de esta feature la memoria persistente en el servidor, las sesiones, la ventana de documentos por consulta (cuántos fragmentos y cuánto texto de documentos entran al modelo), entregar historial al modelo en el bot de WhatsApp y cualquier cambio en cómo se buscan los documentos fuera de la reformulación con historial.
