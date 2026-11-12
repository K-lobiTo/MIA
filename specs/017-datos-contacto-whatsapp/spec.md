# Feature Specification: Datos de contacto de quienes escriben al bot de WhatsApp

**Feature Branch**: `dev` (feature `017-datos-contacto-whatsapp`, sin rama propia: los specs y la implementación van en `dev`)

**Created**: 2026-11-12

**Status**: Draft

**Input**: User description: "Se debe almacenar cierta información de las personas que interactúan con el bot de WhatsApp, número de teléfono, y solicitar los datos (nombre y correo del interesado) al comenzar la conversación, dejando claro que es opcional. Esta información (en caso de que se entregue) se debe almacenar en una sección dedicada de la base de datos."

Contexto: el bot de WhatsApp (feature 011) existe para atraer estudiantes a los posgrados, pero hoy no sabe quién le escribe: identifica a cada persona solo con una clave con hash que vive en memoria y se pierde al reiniciar, y la API nunca recibe el teléfono (FR-027 y SC-010 de la feature 011: el teléfono solo se usaba para los límites y no se guardaba en ningún lado). Eso deja a la Coordinación sin forma de volver a contactar a una persona interesada. Esta feature agrega un registro de contacto por persona: el teléfono de quien escribe y, si la persona lo quiere entregar, su nombre y su correo, que el bot le pide al comenzar la conversación dejando claro que es opcional. Las personas administradoras (alcance global) pueden ver esos registros en el panel, descargarlos y borrarlos. Es una **excepción explícita y documentada** a la regla de la feature 011 de no guardar el teléfono, acotada a esta sección dedicada: el registro de consultas (Uso) y los registros del servicio siguen sin teléfonos, nombres ni correos, y las preguntas y respuestas siguen sin guardarse.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Una persona nueva recibe la invitación a dejar sus datos y los entrega (Priority: P1)

Una persona escribe por primera vez al bot. El bot responde su mensaje como siempre (con el saludo de siempre) y, **en un mensaje aparte enviado justo después**, le dice que puede dejar su nombre y su correo para que la Coordinación del programa la contacte, y deja claro que es **opcional** y que puede seguir usando el bot sin entregarlos. Le explica también qué se guarda (su número de teléfono, y su nombre y correo si los entrega) y para qué. La persona responde con su nombre y su correo; el bot confirma que los guardó y la conversación sigue con normalidad.

**Why this priority**: es el núcleo de la feature: sin la invitación y el guardado no hay datos de contacto. Con solo esta historia ya se tiene un registro útil de personas interesadas.

**Independent Test**: escribir al bot desde un teléfono que nunca lo ha usado, comprobar que llega la respuesta a su mensaje y, aparte, la invitación con la aclaración de que es opcional, responder con nombre y correo, y comprobar que en la sección dedicada de la base queda un registro con el teléfono, el nombre y el correo, y que la siguiente pregunta se responde normalmente.

**Acceptance Scenarios**:

1. **Given** un teléfono sin registro de contacto, **When** escribe por primera vez al bot, **Then** el bot responde primero su mensaje como siempre y justo después envía, en un mensaje aparte, la invitación a dejar nombre y correo, que dice de forma explícita que es opcional y qué se guarda, y deja un registro con el teléfono y el estado "invitada".
1b. **Given** que el envío de la respuesta a la primera pregunta falló, **When** se revisa el registro, **Then** no queda marcado como invitada y la invitación se envía tras la primera respuesta que sí salga bien.
2. **Given** una persona invitada, **When** responde con su nombre y su correo, **Then** el bot guarda ambos en su registro, le confirma en un mensaje breve qué guardó y no vuelve a pedírselos.
3. **Given** una persona invitada, **When** responde solo con su nombre o solo con su correo, **Then** el bot guarda el dato entregado, confirma qué guardó y no insiste por el que falta.
4. **Given** una persona que entregó sus datos, **When** vuelve a escribir días después, **Then** el bot no repite la invitación (el estado persiste aunque el servicio se haya reiniciado) y responde su pregunta como siempre.
5. **Given** la invitación, **When** el bot la envía, **Then** el texto no contradice el saludo que pide no enviar datos personales: aclara que esos datos son solo el nombre y el correo de este paso, no deben ir dentro de las preguntas.

---

### User Story 2 - Una persona decide no dejar sus datos y el bot sigue siendo útil (Priority: P1)

Una persona que no quiere dejar nombre ni correo lo dice (por ejemplo con "no", "omitir" o simplemente haciendo su pregunta) y el bot sigue con su consulta como siempre. No se le vuelve a pedir. De ella solo queda el registro con su teléfono y el estado "no quiso dejar datos".

**Why this priority**: que sea opcional es un requisito explícito y de privacidad: si no entregar los datos estorba o hace que el bot no responda, la feature falla. Se entrega junto con la historia 1.

**Independent Test**: escribir al bot desde un teléfono nuevo, responder "no" a la invitación (y en otro caso, ignorarla haciendo una pregunta) y comprobar que el bot responde la pregunta, que no vuelve a pedir datos y que el registro tiene el teléfono sin nombre ni correo.

**Acceptance Scenarios**:

1. **Given** una persona invitada, **When** responde "no", "omitir" u otra negativa clara, **Then** el bot lo acepta con un mensaje breve, invita a hacer su pregunta y no vuelve a pedirle los datos; el registro queda con el estado "declinó" y sin nombre ni correo.
2. **Given** una persona invitada, **When** en lugar de contestar la invitación hace una pregunta sobre los programas, **Then** el bot responde la pregunta como siempre (sin una segunda invitación), toma la invitación como no aceptada y no vuelve a pedirle los datos.
3. **Given** una persona que declinó, **When** vuelve a escribir en cualquier momento, **Then** nunca se le pide de nuevo el nombre ni el correo.
4. **Given** una persona que declinó, **When** se revisa la base, **Then** no hay ningún nombre ni correo suyo, y el bot le respondió lo mismo que a quien sí los entregó.

---

### User Story 3 - Los datos se guardan en una sección dedicada, separada de todo lo demás (Priority: P1)

Los teléfonos, nombres y correos viven en una sección propia de la base de datos, aparte de las consultas, el uso, los bots y los documentos. Un registro contiene solo lo necesario: el teléfono, el bot (número de la institución) al que escribió la persona, el nombre y el correo si los entregó, el estado de la invitación y las fechas de creación, de última actividad y de última actualización. No contiene preguntas, respuestas ni textos de conversación. Borrar la sección entera deja el resto del sistema intacto.

**Why this priority**: es la parte de la petición sobre dónde se guarda, y es lo que hace posible controlar, proteger y eliminar estos datos personales sin tocar nada más.

**Independent Test**: después de varias conversaciones (con datos, sin datos, con preguntas y respuestas), revisar la base y comprobar que la sección dedicada tiene un registro por persona y bot con solo los campos descritos, que el registro de Uso y los registros del servicio no contienen teléfonos, nombres ni correos, y que vaciar la sección no afecta a las consultas, los bots ni el uso.

**Acceptance Scenarios**:

1. **Given** cualquier persona que escribe al bot, **When** se revisa la sección dedicada, **Then** hay exactamente un registro para ese teléfono y ese bot, aunque haya escrito muchas veces o en varias conversaciones.
2. **Given** una persona que entregó sus datos, **When** se revisan el registro de consultas (Uso) y los registros del servicio, **Then** no aparece su teléfono, su nombre ni su correo.
3. **Given** el registro de una persona, **When** se revisan sus campos, **Then** no contiene el texto de ninguna pregunta ni respuesta.
4. **Given** la sección dedicada, **When** se vacía por completo, **Then** el bot sigue respondiendo y las consultas, el uso, los bots y la cuota de mensajes no cambian (solo que se vuelve a invitar a quien escriba).
5. **Given** dos números de la institución (dos bots), **When** la misma persona escribe a ambos, **Then** tiene un registro por cada bot y los datos de uno no se leen desde el otro.

---

### User Story 4 - Una persona puede pedir que se borren sus datos (Priority: P2)

La persona puede escribirle al bot una frase clara (por ejemplo "borrar mis datos") y el bot elimina su nombre y su correo y se lo confirma. El bot no vuelve a pedirle datos después. El teléfono queda solo como un registro mínimo de que ya se le preguntó (para no volver a pedirlos), sin nombre ni correo.

**Why this priority**: es la garantía básica de control de la persona sobre sus datos. No bloquea el valor principal, por eso va después, pero debe entregarse junto con él porque se guardan datos personales.

**Independent Test**: con una persona que dejó nombre y correo, escribir "borrar mis datos", comprobar la confirmación, revisar que el registro ya no tiene nombre ni correo y que el bot no vuelve a pedirlos.

**Acceptance Scenarios**:

1. **Given** una persona con nombre y correo guardados, **When** escribe una frase de borrado reconocida, **Then** el bot elimina ambos datos, le confirma que se borraron y su registro queda en el estado "declinó".
2. **Given** una persona sin datos guardados, **When** escribe la misma frase, **Then** el bot le dice que no tenía datos guardados, sin error.
3. **Given** una frase de borrado, **When** el bot la procesa, **Then** no consulta a MIA ni gasta modelo, y el mensaje no se registra como una pregunta.
4. **Given** una persona que borró sus datos, **When** quiere volver a dejarlos, **Then** puede hacerlo escribiendo una frase de actualización reconocida (por ejemplo "quiero dejar mis datos"), y el bot le vuelve a pedir el nombre y el correo.

---

### User Story 5 - La función se puede encender y apagar sin romper el bot (Priority: P2)

Quien opera el sistema activa o desactiva la función con un ajuste. Apagada (por defecto), el bot se comporta exactamente como antes: no guarda teléfonos, no hace la invitación y no escribe nada en la sección dedicada. Los registros ya guardados no se borran al apagarla.

**Why this priority**: permite probar la función en el sandbox con calma y dar marcha atrás sin migraciones peligrosas; sigue el mismo patrón de las demás funciones del bot.

**Independent Test**: con el ajuste apagado, correr el recorrido de la feature 011 y comprobar que da el mismo resultado de antes y no deja nada en la sección dedicada; encenderlo y repetir.

**Acceptance Scenarios**:

1. **Given** la función apagada, **When** una persona escribe al bot, **Then** el bot responde exactamente como antes, sin invitación y sin ningún registro nuevo.
2. **Given** la función encendida y registros guardados, **When** se apaga, **Then** los registros siguen en la base y el bot deja de invitar y de guardar.
3. **Given** un fallo al leer o escribir en la sección dedicada, **When** una persona escribe una pregunta, **Then** el bot la responde igual (la función falla en silencio hacia el comportamiento anterior) y el fallo queda en el registro del servicio sin datos personales.

---

### User Story 6 - Quien administra ve, descarga y borra los contactos desde el panel (Priority: P2)

La persona administradora de alcance global abre en el panel un módulo de contactos de WhatsApp. Ve la lista de contactos con su teléfono, bot, nombre, correo, estado y fechas, con un total y filtros (por bot, por estado y por si dejaron correo). Puede descargar la lista como un archivo CSV compatible con una hoja de cálculo y borrar un contacto o varios. Las demás cuentas (de programa) no ven el módulo ni pueden pedir estos datos por la API. Cada descarga y cada borrado queda en el registro de administración, sin los datos descargados.

**Why this priority**: sin una forma de verlos, los datos guardados no sirven para que la Coordinación contacte a nadie; y sin un borrado desde el panel no se puede atender el pedido de una persona que escribió por otro medio. Depende de la historia 1 (que haya datos) y por eso va después.

**Independent Test**: con contactos de prueba (con datos, sin datos, de dos bots), entrar al panel con una cuenta global y con una de programa, comprobar que solo la global ve el módulo, filtrar, descargar el CSV y abrirlo en una hoja de cálculo, borrar un contacto y comprobar que desaparece de la lista y de la base, y que cada acción deja una línea en el registro de administración.

**Acceptance Scenarios**:

1. **Given** una cuenta de alcance global, **When** abre el módulo, **Then** ve la lista paginada de contactos (más recientes primero) con el total, y puede filtrar por bot, por estado y por "con correo".
2. **Given** una cuenta de alcance de programa, **When** intenta abrir el módulo o pedir los contactos a la API, **Then** el módulo no aparece y la API responde que no tiene permiso.
3. **Given** una lista (con o sin filtros), **When** la persona administradora pide la descarga, **Then** obtiene un CSV con las mismas filas y columnas que ve, con codificación que abre bien los acentos en una hoja de cálculo, y la descarga queda en el registro de administración (quién, cuándo, cuántas filas, filtros), sin los datos.
4. **Given** un nombre o un correo que empieza con `=`, `+`, `-` o `@`, **When** se descarga el CSV, **Then** el valor se entrega neutralizado para que una hoja de cálculo no lo ejecute como fórmula.
5. **Given** un contacto, **When** la persona administradora lo borra tras confirmar en una ventana que advierte que no se puede deshacer, **Then** el registro desaparece de la base y de la lista, y queda una línea en el registro de administración con quién lo hizo y el identificador interno del registro, sin teléfono, nombre ni correo.
6. **Given** una lista con filtros, **When** la persona administradora borra todos los contactos filtrados, **Then** la ventana de confirmación muestra cuántos se borrarán y exige confirmarlo explícitamente; se borran solo los que cumplen el filtro.
7. **Given** una persona que fue borrada desde el panel, **When** vuelve a escribir al bot, **Then** se le trata como persona nueva (se le vuelve a invitar), porque el registro ya no existe.

---

### Edge Cases

- **El aviso de Kapso no trae el teléfono** (solo un identificador de usuario): sin un identificador estable de teléfono no se crea registro ni se hace la invitación, y el bot responde como siempre.
- **Correo con forma inválida** ("juan@", "no tengo"): el bot pide el correo de nuevo una sola vez con un ejemplo; si vuelve a fallar, se guarda solo el nombre (si lo hay) y no se insiste.
- **El mensaje trae el nombre y el correo mezclados con texto** ("soy Ana y mi correo es ana@mail.com"): se reconocen el correo (por su forma) y el nombre (el resto razonable); si no se puede separar con seguridad, se guarda solo el correo y se confirma qué se guardó para que la persona lo corrija.
- **Respuesta que parece una pregunta** ("¿para qué lo piden?"): se trata como una pregunta, el bot responde en una frase para qué se piden y por qué es opcional, y no insiste.
- **Imagen, audio u otro mensaje que no es texto** en respuesta a la invitación: se toma como no aceptada; el bot responde como siempre a estos mensajes.
- **Nombre o correo excesivamente largos** o con contenido que no es un nombre (por ejemplo, una pregunta completa): se recortan al máximo permitido o se descartan; nunca se guarda más del máximo.
- **Dos mensajes simultáneos de una persona nueva** o un reintento de Kapso del mismo aviso: se crea un solo registro y se envía una sola invitación.
- **Se supera el límite de mensajes por persona o el tope mensual**: se aplican igual que hoy; la invitación y su confirmación cuentan en la cuota de mensajes (la invitación es un mensaje más por cada persona nueva) y con el tope mensual alcanzado no se envía ni la invitación.
- **La primera respuesta no es una consulta** (límite por persona, mensaje que no es texto, bot no disponible, error de la API): la invitación solo se envía tras una respuesta a una pregunta que sí salió bien (con información o sin ella) y no se envía junto a avisos de límite o de no disponibilidad, ni justo después de que el bot pida aclarar a qué programa se refiere la persona (feature 013); queda para la primera respuesta posterior que cumpla.
- **La persona escribe varias preguntas seguidas antes de contestar la invitación**: cada una se responde normal; la invitación ya enviada se da por declinada con la primera pregunta que no parezca un dato.
- **El envío de la invitación falla**: el registro no queda marcado como invitada; se vuelve a intentar tras la siguiente respuesta exitosa.
- **Exportar o borrar con mucha cantidad**: la lista se pagina y la descarga entrega todo lo filtrado sin cortar filas; el borrado masivo exige confirmación explícita con el conteo.
- **Reinicio del servicio entre la invitación y la respuesta**: el estado vive en la base, no en la memoria, así que la respuesta se reconoce igual.
- **Pedir borrar o actualizar con el tope mensual alcanzado, con el límite por persona superado o con el bot desactivado**: el bot no responde (o solo avisa del límite una vez), igual que a cualquier otro mensaje; en ese caso el borrado se hace desde el panel o la base. Se declara como límite conocido y se documenta.
- **Pedir "quiero dejar mis datos" sin haber sido invitada todavía, o con la invitación abierta**: se acepta en cualquier estado; el bot envía la invitación (si ya estaba abierta, solo se la repite).
- **Una pregunta que se parece a un nombre** ("Requisitos de Admisión", "Maestría Computación"): se toma como pregunta, no como nombre, y se responde normal; las negativas se reconocen solo con frases exactas ("no", "no gracias", "omitir"), nunca por empezar con "no" ("no encuentro la matrícula" es una pregunta).
- **La respuesta a la pregunta no llegó a enviarse** estando la invitación abierta: la invitación sigue abierta y la persona todavía puede contestarla.
- **Una persona se registra con el teléfono de otra**: el bot solo recibe lo que la persona escribe; no verifica identidad ni correo (no se envía ningún mensaje de confirmación). Se declara como límite conocido.

## Requirements *(mandatory)*

### Functional Requirements

**Registro y sección dedicada**

- **FR-001**: Con la función encendida, el sistema DEBE crear un registro de contacto en una sección dedicada de la base de datos la primera vez que una persona (con teléfono conocido) escribe a un bot, con su teléfono, el bot al que escribió, el estado de la invitación y las fechas.
- **FR-002**: Debe existir como máximo un registro por teléfono y por bot, aunque la persona escriba muchas veces o lleguen mensajes simultáneos.
- **FR-003**: El registro DEBE contener solo: teléfono, bot, nombre (opcional), correo (opcional), estado de la invitación (`pendiente`, `invitada`, `entregó` o `declinó`), si ya se repitió una vez la pregunta del correo y las fechas de creación, última actividad y última actualización. No debe contener el texto de preguntas ni respuestas.
- **FR-004**: La sección dedicada DEBE ser independiente del resto: no se mezcla con el registro de consultas (Uso), los bots, los artefactos ni los documentos, y vaciarla no afecta a nada más.
- **FR-005**: El estado de la invitación DEBE persistir en la base, de modo que reiniciar el servicio no repita invitaciones ni pierda respuestas.

**Invitación y obtención de datos**

- **FR-006**: Tras enviar con éxito la primera respuesta a una persona sin registro, el bot DEBE enviar, **en un mensaje aparte** y justo después, la invitación a dejar su nombre y su correo. La respuesta a su mensaje (con el saludo de siempre) no cambia ni se retrasa por la invitación.
- **FR-007**: La invitación DEBE decir de forma explícita que entregar los datos es **opcional** y que se puede seguir usando el bot sin hacerlo, y DEBE informar qué se guarda (el número de teléfono, y el nombre y el correo si se entregan), para qué se guarda y cómo pedir el borrado.
- **FR-008**: El texto de la invitación NO DEBE contradecir el saludo existente que pide no enviar datos personales: debe aclarar que los datos de este paso son solo el nombre y el correo y que no deben ir dentro de las preguntas.
- **FR-009**: La invitación se hace una sola vez por persona y bot. Si la persona la acepta, la declina o la ignora haciendo una pregunta, no se vuelve a pedir. No se envía junto a avisos de límite, de "no disponible" ni tras un envío fallido.
- **FR-010**: El bot DEBE reconocer por reglas de texto (sin modelo de lenguaje): un correo (por su forma), un nombre (texto corto razonable sin forma de pregunta ni palabras propias de las preguntas sobre programas) y una negativa clara (coincidencia exacta con "no", "omitir", "no gracias" y similares; un mensaje que solo empieza con "no" es una pregunta). En la duda se prefiere tratar el mensaje como pregunta.
- **FR-011**: El nombre y el correo son independientes: entregar solo uno es válido y se guarda ese.
- **FR-012**: Un correo con forma inválida se pide de nuevo una sola vez; si vuelve a fallar no se guarda ni se insiste.
- **FR-013**: Una respuesta a la invitación que es en realidad una pregunta sobre los programas DEBE responderse como una consulta normal y cerrar la invitación como no aceptada.
- **FR-014**: Tras guardar datos, el bot DEBE confirmar en un mensaje breve qué guardó, sin repetir el correo completo si no hace falta (por ejemplo enmascarado parcialmente), y la conversación sigue con normalidad.
- **FR-015**: Declinar o ignorar la invitación NO DEBE cambiar en nada las respuestas posteriores del bot ni sus límites.

**Borrado y control de la persona**

- **FR-016**: La persona DEBE poder pedir el borrado de su nombre y su correo con una frase clara; el bot los elimina, se lo confirma y no vuelve a pedirlos.
- **FR-017**: Una frase de borrado NO DEBE consultar a MIA ni gastar modelo, ni quedar registrada como una pregunta.
- **FR-018**: La persona DEBE poder volver a dejar o actualizar sus datos con una frase clara reconocida, que reinicia la invitación solo para ella, en cualquier estado de su registro.

**Privacidad y protección**

- **FR-019**: El teléfono, el nombre y el correo NO DEBEN aparecer en el registro de consultas (Uso), en los registros del servicio del bot, en los mensajes de error ni en ninguna respuesta pública de la API.
- **FR-020**: Los datos de contacto DEBEN ser accesibles solo con la credencial de servicio del bot (para escribir y leer el estado) y por las personas administradoras de **alcance global**; las cuentas de alcance de programa, las rutas públicas y la Consulta no pueden leerlos ni borrarlos.
- **FR-021**: La clave con hash en memoria que ya usa el servicio para los límites por persona NO DEBE cambiar: los límites siguen funcionando igual, tengan o no registro.
- **FR-022**: El nombre y el correo guardados tienen un máximo de largo; lo que lo excede se recorta o se descarta, y el contenido guardado se trata como texto, nunca como instrucciones.
- **FR-023**: Si el aviso de Kapso no trae un teléfono, la función NO DEBE crear registro ni hacer la invitación, y el bot responde como siempre.

**Control, resiliencia y documentación**

- **FR-024**: La función DEBE poder encenderse y apagarse con un ajuste del servicio, apagada por defecto. Apagada, el comportamiento es exactamente el de antes.
- **FR-025**: Un fallo al leer o escribir en la sección dedicada NO DEBE impedir que el bot responda la pregunta: la función falla hacia el comportamiento anterior.
- **FR-026**: La invitación y su confirmación DEBEN contar en la cuota mensual de mensajes (la invitación es un mensaje más por cada persona nueva) y respetar los límites por persona y el tope mensual como cualquier otro mensaje; con el tope alcanzado no se envía la invitación.
- **FR-027**: Los textos de la invitación, la confirmación, el rechazo y el borrado DEBEN ser configurables y estar en español, como los demás textos del bot, y sin contactos del programa (regla vigente del bot).
- **FR-028**: Los cambios DEBEN ser solo aditivos en la base (una sección nueva), y una API más vieja que la base debe poder revertirse siguiendo el procedimiento de migraciones ya documentado.
- **FR-029**: La documentación de arquitectura, de operación, de privacidad y de la feature 011 DEBE quedar al día: qué se guarda ahora (excepción a FR-027 y SC-010 de la 011), dónde, quién lo puede leer, cómo encender y apagar la función, cómo borrar los datos de una persona o de todas (desde el panel y desde la base), el módulo del panel y cómo volver atrás.

**Panel de administración (alcance global)**

- **FR-030**: El panel DEBE incluir un módulo de contactos de WhatsApp, visible solo para cuentas de alcance global, que liste los contactos (más recientes primero, paginados) con teléfono, bot, nombre, correo, estado y fechas, el total y filtros por bot, por estado y por "con correo".
- **FR-031**: La persona administradora DEBE poder descargar los contactos (todos o los filtrados) como un archivo CSV que abra bien en una hoja de cálculo, con los valores que empiezan con `=`, `+`, `-` o `@` neutralizados contra la ejecución como fórmulas.
- **FR-032**: La persona administradora DEBE poder borrar un contacto o todos los filtrados, tras una confirmación que advierte que no se puede deshacer y, en el borrado masivo, muestra cuántos se borrarán.
- **FR-033**: Cada descarga y cada borrado DEBEN dejar una línea en el registro de administración con quién, cuándo, la acción, el conteo y los filtros, sin teléfonos, nombres ni correos.
- **FR-034**: La descarga y el borrado se hacen con la autenticación de administración ya existente; sin permiso global la API responde que no tiene permiso, sin revelar si existen contactos.

### Key Entities *(include if feature involves data)*

- **Contacto de WhatsApp**: una persona que escribió a un bot de WhatsApp. Atributos: teléfono, bot al que escribió, nombre (opcional), correo (opcional), estado de la invitación (`pendiente`, `invitada`, `entregó`, `declinó`; en la base se guardan sin tilde: `entrego`, `declino`), si ya se repitió la pregunta del correo, fecha de creación, de última actividad y de última actualización. Un contacto por teléfono y por bot. Vive en la sección dedicada y no se relaciona con consultas, conversaciones ni documentos.
- **Invitación a dejar datos**: el mensaje aparte con que el bot pide nombre y correo con la aclaración de que es opcional, enviado tras la primera respuesta. No es una entidad guardada: queda reflejada en el estado del contacto.
- **Descarga de contactos**: el archivo CSV que se genera a pedido de la persona administradora; no se guarda, solo queda una línea de auditoría con el conteo y los filtros.
- **Bot (existente)**: el número de la institución al que escribe la persona; el contacto lo referencia para distinguir los números.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el 100 % de las pruebas, una persona nueva que escribe al bot recibe la invitación una sola vez, el texto contiene de forma explícita que es opcional y qué se guarda, y su registro queda con su teléfono y el estado correcto.
- **SC-002**: En el 100 % de las pruebas, quien declina o ignora la invitación recibe después las mismas respuestas, con las mismas fuentes y el mismo costo, que quien entrega sus datos, y no se le vuelve a pedir nada.
- **SC-003**: Una persona entrega su nombre y su correo y ve la confirmación en una sola respuesta del bot (un mensaje de ida y uno de vuelta), y su registro está completo en la base en menos de 2 segundos tras recibir el mensaje.
- **SC-004**: En el 100 % de las revisiones, la base tiene como máximo un contacto por teléfono y bot, incluso con avisos duplicados y mensajes simultáneos, y la persona recibe una sola invitación.
- **SC-005**: En ninguna revisión del registro de consultas (Uso), de los registros del servicio ni de las respuestas de la API pública aparece un teléfono, un nombre o un correo de contacto; y ningún registro de contacto contiene el texto de una pregunta o respuesta.
- **SC-006**: Tras el pedido de borrado, el 100 % de las revisiones no encuentra el nombre ni el correo de esa persona, y no se le vuelve a invitar.
- **SC-007**: Con la función apagada, el 100 % de las pruebas existentes de la feature 011 (incluido el recorrido de punta a punta) da el mismo resultado que antes y no escribe nada en la sección dedicada; y con un fallo simulado de la sección dedicada, el 100 % de las preguntas se responde igual.
- **SC-008**: Vaciar la sección dedicada deja sin cambios, en el 100 % de las comprobaciones, el registro de consultas, los bots, la cuota de mensajes y los documentos.
- **SC-009**: Tras reiniciar el servicio, el 0 % de las personas que ya habían sido invitadas recibe de nuevo la invitación.
- **SC-010**: La respuesta a la primera pregunta de una persona nueva llega igual y sin demora adicional que antes de la feature (la invitación se envía después, en un mensaje aparte), y la invitación consume exactamente 1 mensaje de la cuota mensual por persona nueva.
- **SC-011**: En el 100 % de las pruebas de permisos, solo las cuentas de alcance global ven, descargan y borran contactos; las de programa y las rutas públicas reciben "sin permiso", y cada descarga o borrado deja su línea de auditoría sin datos personales.
- **SC-012**: Una persona administradora filtra por estado, descarga el CSV y lo abre en una hoja de cálculo con acentos correctos y sin fórmulas ejecutadas en menos de 2 minutos, y el 100 % de las filas descargadas coincide con las filtradas en pantalla.
- **SC-013**: Tras borrar un contacto desde el panel, el 100 % de las revisiones de la base no encuentra su teléfono, nombre ni correo.

## Assumptions

- **Se corrige una regla vigente de forma deliberada**: la feature 011 decidió no guardar el teléfono (FR-027, SC-010) y esta feature lo guarda, pero solo en la sección dedicada y con el aviso a la persona. La regla se mantiene para el registro de consultas (Uso) y para los registros del servicio.
- El entorno de esta entrega sigue siendo el sandbox de Kapso (decisión de la feature 011): se prueba y se acepta con teléfonos de prueba; el diseño admite un número de producción sin cambios de código. Antes de abrir el bot al público hay que revisar la normativa de protección de datos personales aplicable y el texto del aviso con quien corresponda; los datos de prueba se consideran públicos por ahora, pero la feature se diseña como si no lo fueran.
- El teléfono se guarda para todas las personas con las que el bot interactúa (con la función encendida), no solo para quienes entregan nombre y correo; el aviso de la invitación lo declara. Es lo que pidió el usuario y es la condición para saber a quién ya se le preguntó.
- La finalidad declarada es que la Coordinación del programa pueda contactar a la persona interesada; el texto exacto se define con la Coordinación y es configurable.
- La identificación de la persona para este registro es su teléfono y el bot al que escribió; no hay verificación del teléfono ni del correo (límite conocido).
- El reconocimiento de nombre, correo, negativa y frases de borrado es por reglas de texto en español, sin modelo de lenguaje, igual que la aclaración de programa de la feature 013.
- No hay vencimiento automático de los registros en esta entrega: se conservan hasta que la persona pide el borrado o la persona operadora los elimina. Se documenta cómo borrar uno o todos. Una retención automática se puede agregar después.
- La API sigue sin recibir el teléfono en las rutas de consulta; el teléfono viaja solo a las rutas nuevas del servicio de contactos, protegidas con la credencial de servicio del bot, por el mismo canal HTTP que ya usa `mia-whatsapp` (el servicio no importa `mia`).
- **Decisiones del usuario (2026-11-12):** la invitación se envía en un mensaje aparte justo después de responder la primera pregunta (cuesta un mensaje más de la cuota por persona nueva, aceptado), y esta feature incluye un módulo del panel para ver, descargar y borrar los contactos.
- El módulo del panel es de solo alcance global (igual que el módulo Bots), porque los contactos no pertenecen a un programa. Los registros no tienen programa y no se segmentan por unidad.
- Las personas administradoras que acceden a estos datos ya están autenticadas con las cuentas del TEC; se asume que su uso queda cubierto por el registro de administración existente.
- Fuera de alcance: verificación del correo o del teléfono, envío de correos o de mensajes de seguimiento a las personas registradas, campañas, integración con un CRM, segmentación o puntuación de interesados, guardar el historial de preguntas de cada persona, otros datos (programa de interés, edad, ubicación) y datos de contacto en los bots incrustados en páginas web, edición de un contacto desde el panel (solo se ven, descargan y borran), importación de contactos y descargas programadas.
