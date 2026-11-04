# Feature Specification: Historial de chats con usuarios básicos en la Consulta web

**Feature Branch**: `dev` (feature `015-historial-chats`, sin rama propia por decisión del usuario)

**Created**: 2026-11-04

**Status**: Draft

**Input**: User description: "Historial de chats con usuarios básicos en la Consulta web: hoy la Consulta administrativa muestra un chat pero la conversación vive solo en la memoria de la página y se pierde al recargar; POST /query es anónimo (se identifica solo el artefacto por su clave) y la feature 014 dejó dicho que el servidor no guarda ninguna conversación. Se quiere que las personas puedan volver a ver y retomar sus conversaciones anteriores, para lo cual se necesita un sistema muy básico de usuarios, porque por ahora se imposibilita la conexión con el sistema de identidad del TEC y el uso del dominio itcr.ac.cr. Decisiones del usuario (2026-11-04): alcance solo la Consulta web; los usuarios los crea la persona administradora desde el panel (usuario y contraseña), sin registro público ni correo; las conversaciones se guardan en el servidor, por usuario, con retención configurable y borrado por parte de cada persona (excepción explícita a la regla de la feature 014 de no guardar nada); al reabrir una conversación se retoma con la memoria de la feature 014."

Contexto: la Consulta administrativa muestra una conversación, pero esa conversación vive solo en la memoria de la página: al recargar, cerrar o cambiar de dispositivo se pierde, y la persona no puede volver a ver lo que preguntó ni retomarlo. Hoy nadie se identifica en la Consulta: la API reconoce únicamente al artefacto por su clave. La feature 014 le dio memoria al chat (el historial viaja en cada pregunta y el servidor no lo guarda) y dejó escrito que el servidor no conserva ninguna conversación. Para guardar conversaciones por persona hace falta saber quién es cada una, y el sistema de identidad del TEC (cuentas del dominio itcr.ac.cr, con el que inicia sesión el panel de administración) no se puede usar con la Consulta por ahora. Esta feature agrega un sistema de usuarios muy básico (usuario y contraseña que entrega la persona administradora) y, sobre él, el historial de chats guardado en el servidor, con retención y borrado claros porque las preguntas pueden contener datos personales. Es una **excepción explícita y documentada** a la regla de la feature 014: lo que se guarda es la conversación de quien inició sesión, no lo que llega a la consulta anónima. El bot de WhatsApp no cambia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Quien administra crea y gestiona usuarios desde el panel (Priority: P1)

La persona administradora abre en el panel un módulo de usuarios de la Consulta. Crea un usuario con un nombre de usuario y una contraseña inicial que el panel muestra una sola vez para entregarla a la persona. Puede desactivar un usuario (deja de poder iniciar sesión sin perder sus conversaciones), reactivarlo y restablecer su contraseña (el panel muestra la nueva una sola vez). Una cuenta de programa gestiona solo a los usuarios de su programa; el alcance global gestiona a todos.

**Why this priority**: sin usuarios no hay a quién asociar conversaciones. Es lo primero que debe existir y no tiene valor por sí sola sin las historias de inicio de sesión y de historial, pero cada una de ellas depende de esta.

**Independent Test**: crear, desactivar, reactivar y restablecer la contraseña de un usuario desde el panel con cuentas de distinto alcance, y comprobar con la API que el usuario existe, que su contraseña no queda guardada en claro y que cada cambio deja huella en el registro de administración.

**Acceptance Scenarios**:

1. **Given** una persona administradora de alcance global, **When** crea el usuario "ana" con un programa y una contraseña generada, **Then** el panel muestra la contraseña una sola vez, el usuario aparece activo en la lista y nadie puede volver a ver esa contraseña después.
2. **Given** un nombre de usuario que ya existe (sin distinguir mayúsculas), **When** se intenta crear otro igual, **Then** el panel lo rechaza con un mensaje claro y no cambia nada.
3. **Given** un usuario activo, **When** la persona administradora lo desactiva, **Then** no puede iniciar sesión y su sesión abierta deja de valer, y sus conversaciones se conservan; al reactivarlo todo vuelve como estaba.
4. **Given** un usuario, **When** se restablece su contraseña, **Then** la anterior deja de funcionar, las sesiones abiertas se cierran y el panel muestra la nueva una sola vez.
5. **Given** una persona administradora de un programa, **When** abre el módulo, **Then** ve y gestiona solo a los usuarios de su programa; un usuario ajeno responde como no encontrado.
6. **Given** cualquier cambio de usuarios, **When** termina, **Then** queda una línea en el registro de administración con quién lo hizo, qué usuario, qué cambió y cuándo, sin contraseñas.

---

### User Story 2 - Una persona inicia y cierra sesión en la Consulta con usuario y contraseña (Priority: P1)

Al abrir la Consulta, la persona puede iniciar sesión con su usuario y contraseña. Una vez dentro ve su nombre y un botón para cerrar sesión. La sesión dura un tiempo limitado y se renueva con el uso. Si falla muchas veces seguidas, el sistema frena los intentos. Los mensajes de error no dicen si el usuario existe.

**Why this priority**: es la puerta de todo el historial, y su seguridad es crítica porque protege conversaciones que pueden tener datos personales.

**Independent Test**: iniciar sesión con credenciales correctas e incorrectas, cerrar sesión, esperar el vencimiento y repetir fallos para comprobar el límite de intentos, siempre con los mismos mensajes para "usuario inexistente" y "contraseña incorrecta".

**Acceptance Scenarios**:

1. **Given** un usuario activo con su contraseña, **When** inicia sesión, **Then** la Consulta muestra su nombre y sus conversaciones, y la sesión sigue abierta al recargar la página mientras no venza.
2. **Given** un usuario inexistente o una contraseña incorrecta, **When** intenta iniciar sesión, **Then** recibe el mismo mensaje genérico en ambos casos y no se revela si el usuario existe.
3. **Given** varios intentos fallidos seguidos contra un usuario o desde un mismo origen, **When** supera el límite, **Then** los intentos siguientes se rechazan por un tiempo con un aviso de que espere, incluso si la contraseña fuera correcta, y pasado el plazo se puede volver a intentar.
4. **Given** una sesión abierta, **When** la persona cierra sesión, **Then** la sesión deja de valer de inmediato en cualquier dispositivo donde se use esa misma sesión, y la conversación en pantalla se limpia.
5. **Given** una sesión vencida o de un usuario desactivado, **When** la persona intenta preguntar o ver el historial, **Then** se le pide iniciar sesión de nuevo sin perder lo que escribió.
6. **Given** un usuario con contraseña dada por la persona administradora, **When** inicia sesión, **Then** puede cambiar su propia contraseña desde la Consulta, y las demás sesiones se cierran.

---

### User Story 3 - Las conversaciones se guardan y se ven al volver (Priority: P1)

Con la sesión iniciada, cada pregunta y su respuesta se guardan en una conversación del usuario. La Consulta muestra una lista de conversaciones anteriores (la más reciente primero, con un título tomado de la primera pregunta y la fecha). La persona abre una de ellas y ve las preguntas, las respuestas con sus fuentes y el modo en que se respondió. Puede empezar una conversación nueva en cualquier momento. Recargar la página, cerrar el navegador o entrar desde otro dispositivo no hace perder nada.

**Why this priority**: es el objetivo de la feature. Sin esto, los usuarios no sirven de nada.

**Independent Test**: iniciar sesión, hacer tres preguntas, recargar, y ver la conversación en la lista con su título y sus tres vueltas completas (respuesta, fuentes y modo), y repetirlo desde otro navegador con el mismo usuario.

**Acceptance Scenarios**:

1. **Given** un usuario con sesión y sin conversaciones, **When** hace su primera pregunta, **Then** se crea una conversación con un título automático tomado de esa pregunta (recortado) y la respuesta queda guardada en ella.
2. **Given** una conversación abierta, **When** hace otra pregunta, **Then** la vuelta se agrega a la misma conversación y la fecha de la conversación se actualiza.
3. **Given** conversaciones guardadas, **When** el usuario abre la lista, **Then** las ve ordenadas de la más reciente a la más antigua, con título y fecha, y puede abrir cualquiera para ver sus vueltas con fuentes y modo.
4. **Given** una conversación guardada, **When** el usuario entra desde otro dispositivo con su usuario, **Then** la ve igual.
5. **Given** una pregunta que falla (error, tope de gasto, sin permiso), **When** ocurre, **Then** no se guarda como vuelta respondida y el usuario puede reintentar; las respuestas de "sin información" sí se guardan, porque son parte de lo que la persona vio.
6. **Given** el usuario pulsa "Nueva conversación", **When** pregunta, **Then** se crea otra conversación y la anterior queda intacta.

---

### User Story 4 - Retomar una conversación guardada con la memoria de la 014 (Priority: P1)

Al abrir una conversación guardada y hacer una pregunta nueva, la conversación se retoma: la consulta lleva como memoria las últimas vueltas de esa conversación, con el límite del artefacto (feature 014), de modo que las preguntas de seguimiento ("¿y cuánto cuesta?") se entienden aunque la conversación sea de ayer. Si la memoria del artefacto es 0, la conversación se ve completa pero cada pregunta nueva sale sin historial, como hoy.

**Why this priority**: da sentido al historial: ver lo anterior sirve, pero poder seguir donde se dejó es lo que lo vuelve una conversación.

**Independent Test**: con un artefacto de memoria 3, abrir una conversación guardada de 5 vueltas, preguntar un seguimiento corto y comprobar que se responde bien y que la consulta llevó solo las últimas 3 vueltas; repetir con memoria 0 y comprobar que no lleva ninguna.

**Acceptance Scenarios**:

1. **Given** una conversación guardada y un artefacto con memoria N mayor que 0, **When** el usuario pregunta de nuevo en ella, **Then** la consulta lleva las últimas N vueltas respondidas de esa conversación, igual que lo hace hoy la Consulta con la conversación de la página.
2. **Given** un artefacto con memoria 0, **When** el usuario pregunta en una conversación guardada, **Then** la consulta no lleva historial, y la conversación se sigue viendo y creciendo.
3. **Given** una conversación hecha con un artefacto y retomada con otro de distinta memoria, **When** pregunta, **Then** rige la memoria del artefacto actual y todas las vueltas guardadas siguen visibles.
4. **Given** una conversación con vueltas de ambos modos, **When** se retoma en cualquiera de los dos, **Then** valen las reglas de la feature 014 (el historial solo sirve para entender la pregunta y nunca es fuente de datos).

---

### User Story 5 - Borrar conversaciones y retención automática (Priority: P2)

La persona puede borrar una conversación (con confirmación) o todas las suyas a la vez, y lo borrado desaparece por completo, no solo de la pantalla. Además, el sistema borra solo las conversaciones que llevan más de un número configurable de días sin actividad. La Consulta le dice a la persona cuánto tiempo se guardan sus conversaciones.

**Why this priority**: las preguntas pueden contener datos personales; sin borrado claro la feature no es aceptable. No bloquea el valor principal, por eso va después, pero debe entregarse junto con él.

**Independent Test**: borrar una conversación y todas, comprobar que no quedan en la base ni en las respuestas de la API, y simular el paso del tiempo para comprobar que se borran solas las que superan la retención.

**Acceptance Scenarios**:

1. **Given** una conversación, **When** el usuario la borra y confirma, **Then** desaparece de la lista y no queda ninguna vuelta suya guardada.
2. **Given** varias conversaciones, **When** el usuario elige "Borrar todas" y confirma, **Then** no queda ninguna conversación suya, y las de otros usuarios no se tocan.
3. **Given** una conversación sin actividad por más de la retención configurada, **When** el sistema hace su limpieza, **Then** se borra por completo; una conversación con actividad reciente se conserva.
4. **Given** la retención configurada, **When** el usuario abre su historial, **Then** la Consulta le informa cuántos días se guardan las conversaciones.
5. **Given** la retención en 0 (guardado desactivado), **When** el usuario pregunta, **Then** la conversación vive solo en la página como hoy y no se guarda nada; y las conversaciones que ya estaban guardadas se borran en la siguiente limpieza, sin posibilidad de recuperarlas desde la aplicación.
6. **Given** un usuario desactivado durante mucho tiempo, **When** pasa la retención, **Then** sus conversaciones también se borran solas.

---

### User Story 6 - Cada usuario solo ve lo suyo y se sabe qué se guarda (Priority: P2)

Cada usuario ve únicamente sus propias conversaciones; ningún otro usuario ni persona administradora puede leer el texto de las conversaciones desde el panel ni desde la API. Lo que se guarda es: título, preguntas, respuestas con sus fuentes, modo y fechas. No se guarda la clave del artefacto, ni teléfonos, ni contraseñas en claro. El registro de Uso sigue guardando solo la pregunta actual de cada consulta, sin duplicar las conversaciones.

**Why this priority**: es la garantía de privacidad que hace aceptable guardar conversaciones; se verifica con pruebas de aislamiento.

**Independent Test**: con dos usuarios, comprobar que cada uno ve solo las suyas por todos los caminos de la API (listar, abrir, borrar), que una persona administradora no obtiene texto de conversaciones, y revisar la base para confirmar qué se guardó.

**Acceptance Scenarios**:

1. **Given** dos usuarios con conversaciones, **When** uno intenta abrir o borrar una conversación del otro (por ejemplo con su identificador), **Then** la API responde como no encontrada y no revela que existe.
2. **Given** una persona administradora, **When** usa el panel o la API de administración, **Then** puede ver cuántas conversaciones tiene un usuario (cantidad y fecha de la última actividad) pero nunca su texto.
3. **Given** una conversación guardada, **When** se revisa la base, **Then** no contiene la clave del artefacto ni teléfonos ni contraseñas en claro.
4. **Given** una pregunta hecha con sesión, **When** se revisa el registro de Uso, **Then** guarda solo la pregunta actual como siempre y no contiene el historial de la conversación ni las respuestas.
5. **Given** la consulta anónima (`POST /query` sin sesión), **When** se responde, **Then** el servidor sigue sin guardar historial ni conversación alguna.

---

### User Story 7 - Compatibilidad: sin sesión todo sigue como hoy (Priority: P2)

Un artefacto, un cliente o una Consulta sin inicio de sesión siguen funcionando exactamente como hoy: consultar con la clave del artefacto, sin guardar nada. La Consulta con clave fija sigue funcionando y ofrece iniciar sesión como opción. Quien administra puede, por artefacto, exigir inicio de sesión para consultar (desactivado por defecto): con ese ajuste una Consulta sin sesión pide iniciar sesión antes de preguntar.

**Why this priority**: protege a todos los clientes y despliegues actuales y deja la decisión de exigir o no sesión en manos de quien administra.

**Independent Test**: probar la batería de pruebas existente y una consulta con clave sin sesión (idéntica a hoy), y probar un artefacto con "exigir sesión" encendido con y sin sesión.

**Acceptance Scenarios**:

1. **Given** una consulta con la clave del artefacto y sin sesión, **When** el artefacto no exige sesión, **Then** responde exactamente igual que antes de la feature, sin guardar nada.
2. **Given** una Consulta publicada con clave fija, **When** se abre, **Then** funciona sin pedir la clave y ofrece "Iniciar sesión" para guardar el historial.
3. **Given** un artefacto con "exigir inicio de sesión" encendido, **When** llega una consulta sin sesión válida, **Then** se rechaza con un mensaje claro que pide iniciar sesión, y con sesión válida responde y guarda como siempre.
4. **Given** la clave del artefacto, **When** el usuario inicia sesión, **Then** la clave sigue siendo la que autoriza consultar (los permisos, modos, dominios y topes son los del artefacto) y el usuario no amplía ni reduce lo que el artefacto permite.
5. **Given** una consulta con sesión, **When** supera el tope de gasto del artefacto, **Then** se rechaza como siempre y no se guarda como vuelta respondida.
6. **Given** el bot de WhatsApp, **When** atiende mensajes, **Then** no cambia nada: no guarda conversaciones en el servidor ni usa usuarios.

---

### Edge Cases

- ¿Qué pasa si la sesión vence en medio de una respuesta en curso? Si la sesión valía cuando se envió la pregunta, la respuesta se entrega y se guarda; la siguiente acción pide iniciar sesión de nuevo, sin perder el texto de la conversación en pantalla.
- ¿Qué pasa si el usuario tiene la misma conversación abierta en dos dispositivos y pregunta en ambos a la vez? Cada vuelta se agrega en el orden en que llega; ninguna se pierde ni se duplica.
- ¿Qué pasa si el usuario borra una conversación mientras otra pestaña la tiene abierta? La pestaña ve que ya no existe al preguntar de nuevo y ofrece empezar una conversación nueva.
- ¿Qué pasa con una conversación muy larga? Se guarda completa hasta un máximo de vueltas por conversación (configurable); pasado el máximo se pide empezar una nueva, sin perder lo guardado.
- ¿Qué pasa si una respuesta o una pregunta es muy larga? Se guarda recortada al máximo ya vigente para preguntas (2.000 caracteres) y para respuestas.
- ¿Qué pasa si falla la escritura en la base al guardar? La respuesta se entrega igual a la persona y se le avisa que esa vuelta no se pudo guardar; la consulta nunca falla por el guardado.
- ¿Qué pasa si se desactiva un usuario con una sesión abierta? La sesión deja de valer en la siguiente petición.
- ¿Qué pasa si dos usuarios eligen nombres casi iguales ("Ana" y "ana")? Se tratan como el mismo nombre y se rechaza el segundo.
- ¿Qué pasa si el artefacto cambia de memoria o de modos con conversaciones ya guardadas? Las conversaciones se conservan y se ven; rige la configuración actual al retomarlas.
- ¿Qué pasa con el tope de usuarios o de conversaciones? Hay un máximo de conversaciones por usuario (configurable); al superarlo se avisa y se sugiere borrar alguna, sin borrar automáticamente nada antes de la retención.
- ¿Qué pasa cuando se elimina un documento citado en una conversación guardada? La conversación se conserva tal como se vio, con el nombre del documento citado.
- ¿Qué pasa si la persona olvida su contraseña? Debe pedir a quien administra que la restablezca (no hay recuperación por correo).

## Requirements *(mandatory)*

### Functional Requirements

**Usuarios y administración**

- **FR-001**: El sistema debe tener usuarios de la Consulta, cada uno con un nombre de usuario único (sin distinguir mayúsculas, sin espacios, de 3 a 40 caracteres), un estado (activo o desactivado) y un programa de pertenencia (o ninguno, para alcance global), creados únicamente por una persona administradora; no debe haber registro público.
- **FR-002**: El panel de administración debe tener un módulo para listar, crear, desactivar, reactivar y restablecer la contraseña de usuarios, con el mismo alcance (global o por programa) que ya rige para las demás cuentas del panel: el alcance global gestiona a todos y una cuenta de programa gestiona solo a los de su programa.
- **FR-003**: Al crear un usuario o restablecer su contraseña, el panel debe mostrar la contraseña una sola vez y ofrecer generar una; el sistema nunca debe poder mostrarla de nuevo.
- **FR-004**: Las contraseñas deben guardarse únicamente protegidas con un método de resguardo lento y no reversible, con sal propia; nunca en claro, ni en registros, ni en Uso, ni en las respuestas de la API. Debe exigirse una longitud mínima.
- **FR-005**: Cada alta, desactivación, reactivación y restablecimiento debe dejar una línea en el registro de administración con quién lo hizo, el usuario, qué cambió y cuándo, sin contraseñas.
- **FR-006**: Desactivar un usuario o restablecer su contraseña debe cerrar sus sesiones abiertas; las conversaciones de un usuario desactivado se conservan hasta la retención.

**Inicio y cierre de sesión**

- **FR-007**: La Consulta debe permitir iniciar y cerrar sesión con usuario y contraseña, mostrar quién tiene la sesión abierta y mantenerla al recargar mientras no venza.
- **FR-008**: La sesión debe tener duración limitada (configurable) y renovarse con el uso; cerrar sesión la invalida de inmediato (desactivar al usuario o restablecer su contraseña la invalida según FR-006).
- **FR-009**: El sistema debe limitar los intentos fallidos de inicio de sesión por usuario y por origen, con bloqueo temporal y aviso de espera, para frenar el adivinar contraseñas; el bloqueo aplica aunque la contraseña intentada fuera correcta.
- **FR-010**: Los mensajes de un inicio de sesión fallido no deben revelar si el usuario existe, está desactivado o la contraseña es incorrecta (mismo mensaje y la misma verificación de contraseña en todos los casos, para que el tiempo de respuesta no delate al usuario).
- **FR-011**: Un usuario debe poder cambiar su propia contraseña estando con sesión (pidiendo la actual), lo que cierra sus demás sesiones.
- **FR-012**: No debe haber recuperación de contraseña por correo ni conexión con el sistema de identidad del TEC; quien olvida su contraseña pide a quien administra que la restablezca.

**Historial de conversaciones**

- **FR-013**: Con sesión iniciada, cada consulta respondida debe guardarse como una vuelta (pregunta, respuesta, fuentes, modo y fecha) de una conversación del usuario; la primera pregunta crea la conversación con un título automático tomado de ella, recortado.
- **FR-014**: La Consulta debe listar las conversaciones del usuario de la más reciente a la más antigua (título y fecha), abrir una para ver todas sus vueltas con sus fuentes y modo, y permitir empezar una conversación nueva en cualquier momento.
- **FR-015**: Las conversaciones deben ser las mismas desde cualquier dispositivo con el mismo usuario y sobrevivir a recargar, cerrar el navegador o cambiar de equipo.
- **FR-016**: Una consulta que falla (error, tope, permiso) no debe guardarse como vuelta respondida; una respuesta de "sin información" sí se guarda. Un fallo al guardar no debe hacer fallar la consulta: la respuesta se entrega y se avisa que no se guardó.
- **FR-017**: Debe haber un máximo configurable de vueltas por conversación y de conversaciones por usuario; al alcanzarlos se avisa con un mensaje claro, sin borrar nada.

**Retomar con la memoria de la 014**

- **FR-018**: Al preguntar en una conversación guardada, la consulta debe llevar como historial las últimas vueltas respondidas de esa conversación, hasta el número que permite la memoria del artefacto (feature 014); con memoria 0 no debe llevar historial, aunque la conversación se siga viendo y guardando. El historial de una conversación guardada debe salir de lo guardado, no de lo que diga el cliente.
- **FR-019**: Las reglas de la feature 014 siguen vigentes sin cambios: el historial se recorta y se valida en la API, solo sirve para entender la pregunta y nunca es fuente de datos, y los modos y topes del artefacto aplican igual.

**Borrado y retención**

- **FR-020**: Cada usuario debe poder borrar una conversación (con confirmación) o todas las suyas (con confirmación); lo borrado debe desaparecer por completo del almacenamiento, no solo de la vista.
- **FR-021**: El sistema debe borrar solo, por completo, las conversaciones sin actividad por más de un número de días configurable (por defecto 90), y debe poder desactivarse el guardado con un valor de retención en 0, caso en que no se guarda nada, la Consulta funciona como hoy y **se borran las conversaciones que ya estaban guardadas**. Ese borrado no se puede deshacer desde la aplicación: para poder recuperar conversaciones hay que mantener una retención mayor a 0 y restaurar una copia de la base dentro de ese lapso.
- **FR-022**: La Consulta debe informar a la persona cuántos días se guardan sus conversaciones y cómo borrarlas.

**Privacidad y aislamiento**

- **FR-023**: Cada usuario debe ver, abrir y borrar únicamente sus propias conversaciones por todos los caminos de la API; acceder a una ajena debe responder como no encontrada sin revelar que existe.
- **FR-024**: Ni otra persona usuaria ni una persona administradora deben poder leer el texto de las conversaciones desde el panel o la API; la administración solo puede ver, por usuario, la cantidad de conversaciones y la fecha de la última actividad.
- **FR-025**: No debe guardarse la clave del artefacto, ningún teléfono ni contraseña en claro junto a las conversaciones; de cada conversación solo se guardan el título, las vueltas (pregunta, respuesta, fuentes, modo) y las fechas.
- **FR-026**: El registro de Uso debe seguir guardando solo la pregunta actual de cada consulta, sin duplicar el historial ni las respuestas; si la consulta se hizo con sesión, puede enlazarse con la conversación solo por un identificador, sin copiar textos.
- **FR-027**: `POST /query` anónimo debe seguir sin guardar historial ni conversación alguna: lo único que se guarda es lo de las personas con sesión, y solo mientras la retención lo permita.

**Compatibilidad**

- **FR-028**: Un cliente o artefacto sin inicio de sesión debe funcionar exactamente como antes de la feature (resultado, fuentes, imágenes y costo idénticos), y las pruebas existentes y la batería del MVP (19 de 19) deben seguir dando el mismo resultado.
- **FR-029**: La clave del artefacto sigue siendo la que autoriza consultar: el usuario se suma a la clave y no amplía ni reduce permisos, modos, dominios ni topes del artefacto. La Consulta con clave fija debe seguir funcionando sin pedir la clave y ofrecer iniciar sesión.
- **FR-030**: Cada artefacto debe tener un ajuste "exigir inicio de sesión para consultar", editable en el panel con el mismo alcance que sus demás parámetros y desactivado por defecto; encendido, una consulta sin sesión válida se rechaza con un mensaje claro que pide iniciar sesión. El cambio debe regir desde la consulta siguiente y dejar línea en el registro de administración.
- **FR-031**: El bot de WhatsApp no debe cambiar su comportamiento: no usa usuarios ni guarda conversaciones en el servidor.
- **FR-032**: Los cambios a la base deben ser aditivos (usuarios, sesiones o su equivalente y conversaciones), sin perder ni cambiar nada existente, y poder revertirse.

**Documentación**

- **FR-033**: La documentación de arquitectura, de operación, de privacidad (la sección de datos), el panel y la Consulta debe quedar al día: que existe el historial por usuario como excepción a la regla de la feature 014, qué se guarda y qué no, la retención y cómo cambiarla, cómo crear y restablecer usuarios, los límites de intentos y de sesiones, y cómo volver atrás (retención 0 y desactivar el ajuste de sesión).

### Key Entities *(include if feature involves data)*

- **Usuario de la Consulta**: persona que inicia sesión en la Consulta. Tiene nombre de usuario único, estado (activo o desactivado), programa de pertenencia (o ninguno), contraseña protegida (nunca legible) y fechas de creación y de último acceso. No tiene permisos propios sobre los documentos: eso lo decide el artefacto.
- **Sesión**: periodo en que un usuario está identificado. Tiene vigencia limitada, se renueva con el uso y se cierra al cerrar sesión, al desactivar al usuario o al restablecer su contraseña.
- **Conversación**: serie de vueltas de un usuario, con título automático, fecha de creación y de última actividad. Pertenece a un solo usuario y solo él la ve.
- **Vuelta guardada**: una pregunta, su respuesta, las fuentes citadas (nombres de documento y dominio), el modo con que se respondió y la fecha. Es lo que se retoma como historial con la memoria del artefacto.
- **Ajuste de exigir sesión (por artefacto)**: indica si ese artefacto solo responde a consultas con sesión. Desactivado por defecto.
- **Ajustes de la instancia**: retención de conversaciones (días), máximo de vueltas por conversación y de conversaciones por usuario, duración de la sesión y límites de intentos fallidos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las pruebas, una persona con sesión que hizo preguntas ve sus conversaciones completas (preguntas, respuestas, fuentes y modo) tras recargar la página o entrar desde otro dispositivo.
- **SC-002**: Retomar una conversación guardada con un artefacto con memoria funciona como hoy lo hace la conversación de la página: el 100 % de las pruebas de seguimiento de la feature 014 da el mismo resultado partiendo de una conversación guardada, y con memoria 0 la consulta no lleva historial.
- **SC-003**: En el 100 % de las comprobaciones, un usuario no puede listar, abrir ni borrar conversaciones de otro (todas las respuestas son "no encontrada"), y una persona administradora no obtiene el texto de ninguna conversación por ninguna ruta.
- **SC-004**: Tras borrar una conversación (o todas), el 100 % de las revisiones de la base no encuentra ninguna de sus vueltas; y tras la limpieza por retención no queda ninguna conversación con más días sin actividad que el límite configurado.
- **SC-005**: En ninguna revisión de la base, de los registros del servidor ni de Uso aparece una contraseña en claro, la clave del artefacto junto a una conversación ni un teléfono; y el registro de Uso contiene solo la pregunta actual de cada consulta.
- **SC-006**: Un inicio de sesión fallido da un mensaje idéntico y ejecuta la misma verificación de contraseña para un usuario inexistente que para una contraseña equivocada en el 100 % de las pruebas, y tras el máximo de intentos fallidos seguidos el 100 % de los intentos siguientes dentro del plazo se rechaza.
- **SC-007**: Con el inicio de sesión sin usar, el 100 % de las consultas da el mismo resultado, las mismas fuentes y el mismo costo que antes de la feature, y la batería del MVP da 19 de 19 y todas las pruebas existentes siguen pasando.
- **SC-008**: Una persona administradora crea un usuario, desactiva a otro y restablece una contraseña desde el panel en menos de 2 minutos en total, y cada cambio rige en el siguiente intento de inicio de sesión del usuario.
- **SC-009**: Guardar la conversación no suma una demora perceptible a la respuesta: guardar es una sola escritura pequeña que no llama a ningún modelo ni al almacén de documentos y suma menos de 1 segundo en el 95 % de las preguntas, y un fallo al guardar no hace fallar la consulta en ningún caso de prueba.
- **SC-010**: El bot de WhatsApp da el 100 % de sus respuestas igual que antes de la feature y no guarda conversaciones en el servidor.

## Assumptions

- Los usuarios son de uso interno de las personas que ya usan la Consulta administrativa (coordinación y consejo); el volumen esperado es de decenas de usuarios y cientos de conversaciones, así que no hay requisitos de escala especiales.
- El nombre de usuario es una cadena sencilla elegida por quien administra (por ejemplo "ana.perez"); no hay correo ni verificación. Los usuarios pertenecen a un programa o ninguno solo para decidir qué cuentas de administración los gestionan; no cambia lo que pueden consultar.
- Retención por defecto: 90 días sin actividad, configurable por la instancia; máximo de 200 vueltas por conversación y de 100 conversaciones por usuario; sesión de 8 horas de vigencia que se renueva con el uso; bloqueo tras 5 intentos fallidos seguidos por 15 minutos. Son valores de partida ajustables. Poner la retención en 0 es una decisión deliberada de apagar el guardado y borra lo guardado; quien quiera conservar la posibilidad de recuperar conversaciones mantiene una retención mayor a 0.
- Se exige una contraseña de al menos 10 caracteres; el panel ofrece generar una aleatoria que cumple ese mínimo.
- La Consulta sigue siendo un sitio estático que habla con la API; el inicio de sesión y el historial son una capacidad de la API que la Consulta usa, no una base propia (principio de almacenamiento y consulta desacoplados).
- El panel de administración sigue iniciando sesión con las cuentas del TEC; el módulo de usuarios de la Consulta es una pantalla más del panel, visible según el alcance de la persona administradora, y no cambia el acceso al panel.
- Que el servidor guarde conversaciones es una excepción deliberada a la regla de la feature 014 y requiere declararla en la documentación de privacidad; la consulta anónima mantiene la regla original.
- El texto de las preguntas puede contener datos personales; por eso hay retención automática, borrado por la persona y aislamiento total, y se advierte a la persona en la Consulta. Se asume que, por ahora, los datos de prueba se consideran públicos, pero la feature se diseña como si no lo fueran.
- Fuera de alcance: conexión con el sistema de identidad del TEC o el dominio itcr.ac.cr, registro público, recuperación de contraseña por correo, inicio de sesión social, historial del bot de WhatsApp, compartir conversaciones entre usuarios, búsqueda dentro de las conversaciones, exportar conversaciones y que la administración lea conversaciones.
