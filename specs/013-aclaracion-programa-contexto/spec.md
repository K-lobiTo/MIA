# Feature Specification: Aclaración de programa y contexto de conversación en el bot de WhatsApp

**Feature Branch**: `dev` (feature `013-aclaracion-programa-contexto`, sin rama propia por decisión del usuario)

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Aclaración de programa y contexto de conversación en el bot de WhatsApp (propuesta 10.1, opciones 1 y 3 de docs/Definicion_Requerimientos_Bot_WhatsApp.md). Hoy el bot responde 'sin información' a una pregunta que no nombra el programa cuando varios programas tienen la respuesta, y cada mensaje es independiente. Se quiere que el bot pida aclaración ('¿A qué programa te refieres?' listando los programas candidatos) y que recuerde un contexto mínimo de la conversación (los últimos 4 mensajes) para completar la pregunta. Solo reglas, sin modelo de lenguaje; solo el bot de WhatsApp; sin migraciones ni cambios en el panel."

Contexto: el bot de WhatsApp atiende a personas interesadas en los posgrados del TEC con documentos de varios programas (hoy la Maestría en Ciberseguridad y la Maestría en Analítica de Negocio), y responde cada mensaje por separado, sin recordar nada de la conversación. Una persona que escribe "¿Cuándo empiezan las lecciones?" no nombra el programa; la respuesta existe en los documentos de los dos programas, pero ningún fragmento se parece lo bastante a una pregunta tan general, así que el bot responde "sin información" y la persona se queda sin salida (observado el 27 de octubre de 2026). Elegir uno de los programas al azar sería peor: daría la fecha del programa equivocado. Lo que se quiere es que el bot pregunte "¿A qué programa te refieres?" y que, cuando la persona conteste, siga con su pregunta original. Tres hechos condicionan el diseño:

1. **Ambigüedad no es ausencia.** "Sin información" y "la pregunta es ambigua entre programas" son situaciones distintas y deben distinguirse sin gastar un modelo de lenguaje: el bot solo pregunta cuando hay evidencia de que dos o más programas tienen algo relacionado.
2. **La aclaración solo sirve si el bot recuerda la pregunta.** Hoy cada mensaje es independiente, así que la respuesta "Ciberseguridad" sola no lleva la pregunta original. Hace falta un contexto mínimo y acotado de la conversación.
3. **El prototipo debe seguir siendo barato y eficiente.** Memoria acotada y transitoria, sin guardar datos personales, sin llamadas extra a modelos y sin tocar lo que hoy ya se responde bien ni a los demás artefactos.

## Clarifications

### Session 2026-10-27

- Q: ¿De dónde sale el nombre del programa de cada documento? → A: Del título del documento, que es su primera línea con la forma "<PROGRAMA>: <SECCIÓN>" (por ejemplo "MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN" da "Maestría en Ciberseguridad"). No se agrega ningún campo a los documentos ni cambios al panel; la convención se documenta en la guía de normalización de documentos de páginas web.
- Q: ¿Qué hace el bot con el contexto además de resolver la aclaración? → A: También recuerda el programa: si la persona ya hablaba de un programa (lo eligió o la última respuesta lo citó), una pregunta siguiente sin programa que recibiría "sin información" o una aclaración se reintenta una vez con ese programa.
- Q: ¿Cuánto contexto se guarda? → A: Los últimos 4 mensajes de cada conversación (mensajes de la persona y respuestas del bot), para que el sistema sea eficiente.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - El bot pide aclaración cuando la pregunta es ambigua entre programas (Priority: P1)

Una persona escribe al bot una pregunta general que no nombra el programa ("¿Cuándo empiezan las lecciones?", "¿Cuánto cuesta?", "¿Cuáles son los requisitos?") y que varios programas pueden responder. En lugar de "sin información", el bot le contesta con una pregunta corta que lista los programas sobre los que tiene información y le pide elegir uno.

**Why this priority**: es el problema que origina la feature. Sin esto la persona se queda sin respuesta y sin saber qué hacer.

**Independent Test**: con los documentos de Ciberseguridad y de Analítica cargados, enviar "¿Cuándo empiezan las lecciones?" y comprobar que la respuesta pide elegir entre la Maestría en Ciberseguridad y la Maestría en Analítica de Negocio, sin dar ninguna fecha.

**Acceptance Scenarios**:

1. **Given** documentos de dos programas que tratan el mismo tema, **When** la persona hace una pregunta general sobre ese tema sin nombrar el programa, **Then** el bot responde con el texto de aclaración que lista los dos programas, sin dar datos de ninguno.
2. **Given** una pregunta que no nombra el programa y de la que solo un programa tiene información relacionada, **When** el bot la procesa, **Then** responde "sin información" como hoy (no pregunta, porque no hay nada entre qué elegir).
3. **Given** una pregunta sin relación con ningún documento ("¿Cuánto cuesta la luna?"), **When** el bot la procesa, **Then** responde "sin información" como hoy y no pregunta nada.
4. **Given** una pregunta que ya se respondía bien porque nombra el programa ("¿Cuándo empiezan las lecciones de la Maestría en Analítica de Negocio?"), **When** el bot la procesa, **Then** responde igual que hoy, con las mismas fuentes e imágenes, sin pedir aclaración.
5. **Given** que el bot pidió aclaración, **When** se revisa el consumo mensual, **Then** la aclaración cuenta como un mensaje enviado más, igual que cualquier otra respuesta.

---

### User Story 2 - La persona contesta la aclaración y el bot sigue con su pregunta original (Priority: P1)

Después de que el bot pregunta a qué programa se refiere, la persona contesta con el nombre del programa ("Ciberseguridad", "la de analítica", "Maestría en Analítica de Negocio"). El bot entiende que es la respuesta a su pregunta, retoma la pregunta original con ese programa y la responde, sin que la persona tenga que repetirla.

**Why this priority**: la aclaración sin esto no cierra el ciclo: cada mensaje es independiente y "Ciberseguridad" solo no es una pregunta.

**Independent Test**: enviar "¿Cuándo empiezan las lecciones?", recibir la aclaración y contestar "Ciberseguridad": la respuesta da la fecha de inicio del programa de Ciberseguridad y cita su documento de admisión.

**Acceptance Scenarios**:

1. **Given** una aclaración pendiente con dos programas candidatos, **When** la persona responde nombrando uno de ellos (con o sin la palabra "maestría", en mayúsculas o minúsculas, con o sin tildes), **Then** el bot responde la pregunta original para ese programa, con sus fuentes e imágenes como cualquier otra respuesta.
2. **Given** una aclaración pendiente, **When** la persona responde con algo que no nombra ninguno de los candidatos ("no sé", otra pregunta), **Then** el bot lo trata como una pregunta nueva y no vuelve a pedir aclaración sobre la anterior.
3. **Given** una aclaración pendiente, **When** la persona nombra más de un candidato ("las dos"), **Then** el bot no puede decidir: responde "sin información" y trata el mensaje como pregunta nueva (máximo una aclaración por pregunta).
4. **Given** una aclaración pendiente que venció por inactividad, **When** la persona responde "Ciberseguridad", **Then** el bot lo trata como un mensaje nuevo, como hoy.
5. **Given** que nadie pidió aclaración, **When** la persona escribe solo "Ciberseguridad", **Then** el bot lo trata como una pregunta nueva, como hoy.

---

### User Story 3 - El bot recuerda el programa de la conversación (Priority: P2)

Una persona que ya está hablando de un programa (porque lo eligió en una aclaración o porque la última respuesta del bot citó sus documentos) hace una pregunta siguiente sin nombrarlo ("¿Y cuánto cuesta?"). Si esa pregunta recibiría "sin información" o una aclaración, el bot la reintenta una vez con el programa de la conversación y responde, sin volver a preguntar lo que ya se sabe.

**Why this priority**: mejora la conversación natural (las personas no repiten el nombre en cada mensaje), pero la feature funciona sin esto.

**Independent Test**: preguntar "¿Cuándo empiezan las lecciones de la maestría en ciberseguridad?", recibir la respuesta y luego escribir "¿Y cuánto cuesta?": el bot responde con el costo de Ciberseguridad (o dice que no tiene el dato de ese programa), sin pedir aclaración ni responder "sin información" de forma genérica.

**Acceptance Scenarios**:

1. **Given** que la última respuesta del bot citó documentos de un programa, **When** la persona hace una pregunta siguiente sin programa que de otro modo recibiría "sin información", **Then** el bot reintenta una vez con ese programa y, si hay respuesta, la entrega.
2. **Given** que la última respuesta del bot citó documentos de un programa, **When** la persona hace una pregunta sin programa que de otro modo recibiría una aclaración, **Then** el bot reintenta con ese programa en lugar de preguntar.
3. **Given** el reintento con el programa recordado, **When** tampoco hay respuesta, **Then** el bot hace lo que habría hecho sin contexto (aclaración o "sin información"), una sola vez: nunca encadena reintentos.
4. **Given** una pregunta que ya se responde sin ayuda del contexto, **When** hay un programa recordado distinto, **Then** el bot responde sobre lo que la pregunta dice, sin forzar el programa recordado (el contexto solo interviene cuando de otro modo no habría respuesta).
5. **Given** que la persona nombra otro programa en una pregunta ("¿y en Analítica?"), **When** el bot responde, **Then** el programa recordado pasa a ser ese.

---

### User Story 4 - Lo demás no cambia (Priority: P1)

La Consulta administrativa y los demás artefactos responden exactamente igual que antes; las preguntas que el bot ya respondía bien se responden igual; y "sin información" sigue siendo la respuesta cuando de verdad no hay nada. La batería de aceptación del MVP y las pruebas existentes dan el mismo resultado.

**Why this priority**: es un cambio en el camino de respuesta compartido por todo el sistema; no debe degradar nada fuera de la aclaración.

**Independent Test**: correr las pruebas existentes y la batería del MVP, y preguntar al bot una pregunta con programa nombrado y una sin relación: ambas responden como antes.

**Acceptance Scenarios**:

1. **Given** una consulta de la Consulta administrativa o de cualquier otro artefacto, **When** no hay resultados sobre el umbral, **Then** responde "sin información" exactamente como antes, sin aclaración ni búsqueda extra.
2. **Given** la batería de aceptación del MVP y las pruebas existentes, **When** se ejecutan, **Then** dan el mismo resultado que antes (19 de 19).
3. **Given** una persona que escribe al bot sin contexto previo y con una pregunta que se responde bien, **When** el bot la procesa, **Then** la respuesta, las fuentes, las imágenes y el consumo de mensajes son los mismos que antes de esta feature.
4. **Given** que el bot está desactivado o con el tope mensual alcanzado, **When** llega un mensaje, **Then** se comporta como hoy (nada de aclaración ni contexto cambia eso).

---

### User Story 5 - El contexto es mínimo, transitorio y privado (Priority: P2)

El bot guarda solo los últimos 4 mensajes de cada conversación (de la persona y del bot), los olvida por inactividad, no los guarda en ninguna base ni en el registro de Uso, no los asocia al teléfono y no crece sin límite. No se hace ninguna llamada extra a modelos de lenguaje por esta feature.

**Why this priority**: es la condición para que la feature sea eficiente y respete la decisión de que la API nunca recibe ni guarda el teléfono; sin eso, no es aceptable aunque funcione.

**Independent Test**: enviar más de 4 mensajes y comprobar que el contexto solo conserva los últimos 4; esperar el vencimiento y comprobar que se olvida; revisar que el teléfono y los mensajes no aparecen en la base, en el registro de Uso ni en los registros del servicio.

**Acceptance Scenarios**:

1. **Given** una conversación con más de 4 mensajes, **When** se consulta el contexto, **Then** solo están los 4 más recientes (de la persona y del bot, en orden).
2. **Given** una conversación inactiva por más del tiempo de vencimiento, **When** llega un mensaje nuevo, **Then** el contexto anterior ya no existe.
3. **Given** muchas conversaciones distintas, **When** el servicio supera su tope de conversaciones en memoria, **Then** salen primero las más viejas y la memoria no crece sin límite.
4. **Given** el contexto de una persona, **When** se revisa la base de datos, el registro de Uso y los registros del servicio, **Then** no aparece el teléfono ni el texto de los mensajes.
5. **Given** una pregunta con o sin contexto, **When** se mide el gasto, **Then** esta feature no agrega llamadas a modelos de lenguaje: el costo de una pregunta es el de una consulta normal, y solo el camino de "sin información" puede hacer una segunda búsqueda (y, si recuerda el programa, un reintento).

---

### User Story 6 - El texto de aclaración es configurable y el nombre del programa se toma del título (Priority: P3)

Quien opera el bot puede cambiar el texto de la aclaración sin tocar código, igual que los demás textos del bot. El nombre que el bot muestra de cada programa sale del título del documento, y la forma de escribir ese título queda documentada para quien prepare documentos nuevos.

**Why this priority**: es la parte de operación; la feature funciona con valores por defecto, pero necesita poder ajustarse y que quien carga documentos sepa cómo nombrar los programas.

**Independent Test**: cambiar el texto de aclaración por una variable de configuración y comprobar que el bot lo usa; cargar un documento con un título nuevo "<PROGRAMA>: <SECCIÓN>" y comprobar que el programa nuevo aparece entre los candidatos.

**Acceptance Scenarios**:

1. **Given** el texto de aclaración por defecto, **When** el bot pregunta, **Then** el texto no contiene contacto del programa, correos, teléfonos ni enlaces.
2. **Given** un texto de aclaración configurado, **When** el bot pregunta, **Then** usa ese texto con la lista de programas candidatos.
3. **Given** documentos cuyo primer renglón tiene la forma "<PROGRAMA>: <SECCIÓN>", **When** se calculan los programas candidatos, **Then** cada programa aparece una sola vez, con el nombre del título escrito de forma natural (mayúscula inicial, sin "<SECCIÓN>").
4. **Given** un documento sin título con esa forma (sin dos puntos en la primera línea), **When** se calculan los candidatos, **Then** ese documento no cuenta como programa: no se muestra ni dispara la aclaración.
5. **Given** la guía de normalización de documentos de páginas web, **When** una persona prepara documentos nuevos, **Then** encuentra la convención del título "<PROGRAMA>: <SECCIÓN>" y por qué importa.

---

### Edge Cases

- La pregunta es ambigua entre dos programas, pero uno de ellos solo tiene un fragmento de poca relación: se pide aclaración solo si dos o más programas tienen un fragmento que supera el umbral bajo (la búsqueda extra) y que comparte una palabra con contenido con la pregunta (evidencia léxica), para no preguntar de más ante preguntas sin sentido.
- Hay tres o más programas candidatos: se listan todos (hasta un máximo razonable, para no llenar el mensaje).
- La persona responde la aclaración con el número de la opción ("1", "2"): se acepta si el texto de la aclaración numera las opciones; si no, no se interpreta (se trata como pregunta nueva).
- La persona responde la aclaración con un programa que no es candidato pero sí existe ("Computación"): se trata como pregunta nueva.
- La persona cambia de tema a mitad de una aclaración pendiente: se trata como pregunta nueva y la aclaración pendiente se descarta.
- El servicio se reinicia: se pierde el contexto (se acepta); un mensaje posterior se trata como nuevo.
- Dos personas distintas conversan a la vez: cada una tiene su propio contexto, sin mezclarse.
- Mensaje duplicado (reintento de Kapso): no cuenta dos veces en el contexto ni genera dos aclaraciones.
- La aclaración o su resolución fallan al enviarse: el contexto no debe quedar en un estado que bloquee la conversación (la siguiente pregunta se trata como nueva).
- El bot con un solo programa cargado: nunca pide aclaración, porque nunca hay dos candidatos.
- Un documento nuevo del mismo programa con otra sección: el programa no se duplica entre los candidatos.
- Se elimina el único documento de un programa (feature 012): el programa deja de ser candidato desde la consulta siguiente.
- La pregunta de la persona nombra el programa de forma distinta a como lo titula el documento ("ciberseguridad" a secas): se debe reconocer igual al contestar una aclaración (comparación sin mayúsculas, sin tildes y sin la palabra "maestría").

## Requirements *(mandatory)*

### Functional Requirements

**Aclaración (opción 1)**

- **FR-001**: Cuando una pregunta del bot no deja ningún fragmento sobre el umbral de similitud, el sistema debe repetir la búsqueda con un umbral más bajo y más candidatos **solo para decidir** si hay ambigüedad, nunca para responder con ese resultado. Como el puntaje de similitud solo no distingue una pregunta ambigua de una sin relación (research R9), un fragmento cuenta únicamente si además comparte con la pregunta alguna palabra con contenido (evidencia léxica).
- **FR-002**: Si los fragmentos de esa búsqueda que cuentan (umbral bajo y evidencia léxica) vienen de documentos de **dos o más programas distintos**, el bot debe responder con el texto de aclaración, que lista los programas candidatos, y no dar datos de ninguno.
- **FR-003**: Si esos fragmentos vienen de **un solo programa o de ninguno**, el bot debe responder "sin información" exactamente como hoy.
- **FR-004**: El programa de cada documento debe tomarse de su título (primera línea con la forma "<PROGRAMA>: <SECCIÓN>"), mostrarse con el nombre natural del programa (mayúscula inicial, sin la sección) y contarse una sola vez aunque tenga varios documentos. Un documento sin título con esa forma no cuenta como programa.
- **FR-005**: El texto de aclaración debe ser un texto fijo y configurable sin tocar código, igual que los demás textos del bot, y por defecto no debe contener contacto del programa, correos, teléfonos ni enlaces.
- **FR-006**: La aclaración debe contar en el consumo mensual de mensajes como cualquier otro envío y no debe llevar imágenes.
- **FR-007**: La búsqueda con umbral bajo y la aclaración solo deben ocurrir en el camino que hoy termina en "sin información": ninguna pregunta que hoy se responde cambia de resultado ni de costo.

**Contexto de conversación (opción 3)**

- **FR-008**: El servicio del bot debe guardar, por persona, solo los **últimos 4 mensajes** de la conversación (los de la persona y las respuestas del bot), en orden.
- **FR-009**: El contexto debe vencer por inactividad y debe tener un tope de tamaño total (salen primero las conversaciones más viejas), de modo que la memoria no crezca sin límite. Se pierde al reiniciar el servicio y eso se acepta.
- **FR-010**: El contexto no debe guardarse en la base, ni en el registro de Uso, ni en los registros del servicio, ni asociarse al teléfono: la persona se identifica con la misma clave con hash que ya usa el servicio.
- **FR-011**: El contexto debe aplicarse solo con reglas: ninguna llamada a un modelo de lenguaje por esta feature.
- **FR-012**: Cada persona debe tener su propio contexto, sin mezclarse con el de otras, y un mensaje duplicado no debe contarse dos veces en él.

**Resolver la aclaración**

- **FR-013**: Si el bot preguntó a qué programa se refiere y la persona responde nombrando **exactamente uno** de los candidatos (sin importar mayúsculas, tildes ni la palabra "maestría"), el bot debe repetir la pregunta original con ese programa y responderla como cualquier otra pregunta.
- **FR-014**: Si la respuesta de la persona no nombra ningún candidato, o nombra más de uno, el bot no debe volver a preguntar: debe tratar el mensaje como una pregunta nueva (y, si es el caso, responder "sin información"). **Máximo una aclaración por pregunta.**
- **FR-015**: Una aclaración pendiente vence con el contexto (por inactividad) y una respuesta posterior se trata como mensaje nuevo.

**Recordar el programa**

- **FR-016**: El contexto debe recordar el programa de la conversación cuando la persona lo eligió al contestar una aclaración o cuando la última respuesta del bot citó documentos de un programa.
- **FR-017**: Si una pregunta sin programa recibiría "sin información" o una aclaración y hay un programa recordado, el bot debe **reintentar una vez** con ese programa; si hay respuesta, la entrega; si no, hace lo que habría hecho sin contexto. Nunca encadena reintentos.
- **FR-018**: El programa recordado solo debe intervenir cuando de otro modo no habría respuesta: una pregunta que se responde sin contexto, o que nombra otro programa, se responde sobre lo que dice, y nombrar otro programa cambia el programa recordado.

**Alcance y lo que no cambia**

- **FR-019**: La aclaración y el contexto solo deben aplicar al bot de WhatsApp (modo literal): la Consulta administrativa y los demás artefactos deben responder exactamente igual que antes, sin búsqueda extra.
- **FR-020**: No debe haber migraciones de base ni cambios en el panel de administración. El bot, los topes, los accesos de los artefactos y el registro de Uso siguen funcionando igual.
- **FR-021**: Las consultas que terminen en aclaración deben quedar en el registro de Uso como hoy queda una consulta "sin información" (sin un resultado nuevo), de modo que el módulo Uso no cambie; el resultado `aclaracion` se registra en el registro del servicio, que no lleva datos de la persona.
- **FR-022**: Las pruebas existentes y la batería de aceptación del MVP (19 de 19) deben seguir dando el mismo resultado.

**Medición y documentación**

- **FR-023**: Debe haber casos de prueba nuevos: una pregunta ambigua entre programas (pide aclaración), la misma con un solo programa cargado (responde "sin información" o responde), con el programa nombrado (responde igual que hoy), la respuesta a la aclaración, la respuesta que no decide, el programa recordado y el vencimiento del contexto.
- **FR-024**: La guía de normalización de documentos de páginas web debe documentar la convención del título "<PROGRAMA>: <SECCIÓN>" y por qué importa; la documentación de arquitectura, de operación y de requerimientos del bot debe quedar al día (cómo funciona, textos y variables nuevas, qué se guarda y por cuánto tiempo).

### Key Entities *(include if feature involves data)*

- **Programa (para la aclaración)**: no es una entidad nueva de la base. Es el nombre que se obtiene del título de un documento ("<PROGRAMA>: <SECCIÓN>"), único entre los documentos que el bot puede ver.
- **Contexto de conversación**: los últimos 4 mensajes de una persona (suyos y del bot), más, si existen, la aclaración pendiente (la pregunta original y los programas candidatos) y el programa recordado. Vive solo en la memoria del servicio del bot, con vencimiento y tope de tamaño; se identifica por la clave con hash de la persona.
- **Aclaración pendiente**: la pregunta original que el bot no pudo responder por ambigua y la lista de programas candidatos; se resuelve con la siguiente respuesta de la persona o se descarta.
- **Texto de aclaración**: texto configurable del bot, junto a los demás textos (no disponible, sin información, límite, etc.).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de los casos de prueba de preguntas ambiguas entre programas (que no nombran el programa y que dos o más programas pueden responder), el bot pide aclaración con la lista de programas candidatos y no da datos de ninguno.
- **SC-002**: En el 100 % de los casos de prueba en que la persona contesta la aclaración nombrando uno de los candidatos, el bot responde la pregunta original para ese programa, con su fuente, sin que la persona repita la pregunta.
- **SC-003**: En el 100 % de los casos de prueba con la pregunta que ya nombra el programa, o de un solo programa con información, o sin relación con ningún documento, el resultado es el mismo que antes de esta feature (misma respuesta y mismas fuentes, o "sin información").
- **SC-004**: Nunca se pide más de una aclaración por pregunta: en el 100 % de los casos de prueba en que la respuesta a la aclaración no permite decidir, el bot responde "sin información" y trata el mensaje como pregunta nueva.
- **SC-005**: Con un programa recordado, en el 100 % de los casos de prueba de preguntas siguientes sin programa que antes recibían "sin información" o aclaración, el bot responde con ese programa cuando hay respuesta, y nunca hace más de un reintento.
- **SC-006**: El contexto nunca guarda más de 4 mensajes por persona, se olvida tras el tiempo de inactividad y no supera el tope de conversaciones en memoria; en la base, en el registro de Uso y en los registros del servicio hay 0 teléfonos y 0 textos de mensajes (comprobado por pruebas).
- **SC-007**: Esta feature no agrega llamadas a modelos de lenguaje: el costo medio por pregunta del bot sigue siendo el de una consulta normal (línea base de 0,0004 USD por consulta), y las consultas que hoy se responden no hacen búsquedas extra.
- **SC-008**: Una pregunta que termina en aclaración y su respuesta gastan 4 mensajes de la cuota mensual en total (2 recibidos y 2 enviados), documentado, y el contador mensual los cuenta exactamente.
- **SC-009**: La batería del MVP da 19 de 19 como antes, todas las pruebas existentes siguen pasando y la Consulta administrativa y los demás artefactos responden igual (0 diferencias en sus pruebas).
- **SC-010**: En una prueba con el bot real tras el despliegue, "¿Cuándo empiezan las lecciones?" recibe la aclaración con ambos programas y, al contestar "Ciberseguridad" o "Analítica", el bot responde con la fecha de inicio del programa elegido.

## Assumptions

- Las decisiones del 27 de octubre de 2026 (las dos de la sesión de aclaraciones y la ventana de 4 mensajes) son las de la sección "Clarifications"; esta spec es la implementación de las opciones 1 y 3 de la sección 10.1 de [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md), que sigue siendo la explicación del "por qué".
- Los documentos de los programas se preparan con la convención de normalización: la primera línea es el título "<PROGRAMA>: <SECCIÓN>" (los seis documentos de Ciberseguridad y de Analítica ya la cumplen). Los documentos cargados antes que no la cumplen no cuentan como programa (no rompen nada: solo no ayudan a la aclaración).
- El nombre natural del programa se obtiene del texto antes de los dos puntos, convertido a mayúscula inicial con el resto en minúsculas, salvo que el título lo escriba de otra forma; cualquier ajuste fino (siglas, nombres propios) se decide en el plan y se prueba con los dos programas actuales.
- Los valores concretos (umbral bajo de la búsqueda de decisión, número máximo de programas que se listan, tiempo de vencimiento del contexto, tope de conversaciones) tienen valores por defecto razonables y son configurables, y se calibran con los casos de prueba. Valores de partida (calibrados con los seis documentos reales el 2026-11-03): piso de similitud de 0,70, 30 fragmentos en la búsqueda de decisión, vencimiento de 30 minutos de inactividad, ventana de 4 mensajes, hasta 5 programas listados. La API solo informa los programas de las fuentes (`programs`) cuando la aclaración está encendida (`BOT_CLARIFY=on`); apagada, la respuesta es exactamente la de antes.
- "Mensaje" cuenta los de la persona y las respuestas del bot (una respuesta partida en varios envíos por su largo cuenta como una sola respuesta del bot), de modo que 4 mensajes equivalen a las dos últimas vueltas de la conversación.
- El contexto de conversación se guarda en la memoria del servicio del bot (donde ya viven los mensajes vistos, el saludo y los límites por persona), no en la API ni en la base. El nombre del programa y los candidatos los decide la API (que es quien ve los documentos); el servicio del bot guarda el contexto y reintenta la consulta. Esto se detalla en el plan.
- Una pregunta que termina en aclaración queda en el registro de Uso como una consulta "sin información" y no se agrega un resultado nuevo al módulo Uso; el resultado `aclaracion` se ve en el registro del servicio, que no lleva datos de la persona.
- El consumo de mensajes se cuenta como hoy: cada mensaje recibido y cada mensaje enviado cuenta uno; una aclaración y su respuesta suman 4 en total.
- Es un prototipo de vigencia corta: se prefiere lo más simple que cumpla la especificación. Quedan fuera de esta feature el razonamiento con modelo (opción 2 de la propuesta), la memoria persistente o con más de 4 mensajes, otros canales distintos de WhatsApp, cualquier cambio en el panel y las preguntas de seguimiento generales que no sean de programa (por ejemplo, "¿y el segundo?").
- La feature no resuelve preguntas ambiguas por motivos distintos al programa (por ejemplo, entre dos secciones del mismo programa): solo la ambigüedad entre programas.
