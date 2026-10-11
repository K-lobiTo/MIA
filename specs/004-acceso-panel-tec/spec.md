# Feature Specification: Acceso al panel con cuentas del TEC y separación por unidad

**Feature Branch**: `dev` (feature `004-acceso-panel-tec`)

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Reemplazar la clave compartida del panel de administración (ADMIN_KEY, guardada en el navegador) por inicio de sesión individual con cuentas institucionales del TEC (Microsoft, correos @itcr.ac.cr), con separación de datos por unidad. Quienes usarán el panel: el coordinador de Postgrados de Computación y su ayudante (unidad Computación), el coordinador de Analítica de Negocios y su ayudante (unidad Administración de Empresas) y el operador de MIA con alcance global. Cada persona ve y gestiona solo lo de su unidad; el alcance global ve y hace todo. ADMIN_KEY se conserva solo como clave de automatización para scripts. Las claves de artefacto y la consulta no cambian. El client ID de la aplicación registrada en el TEC todavía no existe: todo debe poder construirse y probarse sin él."

Contexto: el panel y la API ya existen (specs/002-panel-administracion) y hoy se protegen con una sola clave compartida, `ADMIN_KEY`, que cualquiera que la conozca usa con todos los permisos y que no deja saber quién hizo qué. La solicitud a TI para registrar la aplicación en el directorio del TEC está en [docs/REGISTRO_APLICACION_TEC.md](../../docs/REGISTRO_APLICACION_TEC.md). Esta especificación no cambia la Consulta administrativa ni la ruta de consulta.

## Clarifications

### Session 2026-10-10

- Q: ¿Las lecturas de inventario que hoy son públicas (árbol, unidades, dominios sin clave de artefacto y lista de documentos de un dominio) deben exigir inicio de sesión y devolver solo lo del alcance de quien pregunta? → A: Sí. Sin sesión ni clave de automatización responden no autorizado; con sesión, solo lo del alcance. `/health` sigue público y la Consulta (que usa su clave de artefacto) no cambia.
- Q: La identidad que entrega Microsoft dura cerca de una hora: ¿qué debe hacer el panel cuando vence mientras alguien trabaja? → A: Renovarla en silencio y reintentar la operación; solo si no es posible (la sesión de Microsoft venció o fue revocada) mostrar "sesión vencida" y ofrecer iniciar sesión de nuevo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entrar al panel con mi cuenta del TEC y ver solo lo de mi unidad (Priority: P1)

La coordinadora de Postgrados de Computación abre el panel, pulsa "Iniciar sesión con Microsoft", se identifica con su cuenta @itcr.ac.cr (con su segundo factor) y entra. Ve su correo en el encabezado y, en el inventario, solo la unidad Computación con sus dominios, carpetas y documentos. En Artefactos y accesos ve únicamente las consultas que dan acceso a su unidad, y en Uso solo el gasto y las consultas de esos artefactos. Puede crear dominios y carpetas y subir documentos dentro de su unidad.

**Why this priority**: es el propósito de la entrega: que cada persona entre con su identidad y no vea los datos de la otra unidad (las actas de Computación contienen datos personales). Sin esta historia no hay separación.

**Independent Test**: con dos cuentas de prueba, una de alcance Computación y otra de Administración de Empresas, iniciar sesión con cada una y comprobar que el inventario, los artefactos y el uso de cada una no muestran nada de la otra unidad, y que intentar acceder directamente a algo de la otra unidad (por la API) es rechazado.

**Acceptance Scenarios**:

1. **Given** el panel sin sesión, **When** se abre, **Then** se muestra solo una pantalla de inicio de sesión con Microsoft, sin datos de MIA.
2. **Given** una persona de la lista de administradores con segundo factor, **When** completa el inicio de sesión de Microsoft, **Then** entra al panel y su correo se ve en el encabezado, con una acción para cerrar sesión.
3. **Given** una sesión de alcance Computación, **When** se abre el inventario, **Then** solo aparece la unidad Computación con sus dominios, carpetas y documentos; la unidad Administración de Empresas no aparece ni en el árbol, ni en el buscador, ni en los selectores de unidad.
4. **Given** una sesión de alcance Computación, **When** se crea un dominio, una carpeta o se sube un documento dentro de Computación, **Then** la operación funciona como hoy; **When** se intenta lo mismo en una unidad ajena (por ejemplo directamente contra la API), **Then** se rechaza como prohibido.
5. **Given** una sesión de alcance Computación, **When** intenta crear una unidad, **Then** no se ofrece la acción y, si se intenta directamente contra la API, se rechaza.
6. **Given** una sesión de alcance global (el operador), **When** entra, **Then** ve y puede hacer todo lo que hoy permite la clave compartida, salvo lo que esta especificación declara no editable (FR-023).
7. **Given** una sesión iniciada, **When** se cierra la sesión, **Then** se vuelve a la pantalla de inicio de sesión y no queda ninguna credencial guardada en el navegador.

---

### User Story 2 - Saber por qué no puedo entrar y qué hacer (Priority: P1)

Una persona intenta entrar y no puede: su cuenta no está autorizada en MIA, su inicio de sesión no incluyó segundo factor, o su sesión venció mientras trabajaba. En cada caso ve un mensaje claro en español que dice qué pasó y qué hacer (pedir acceso a quien administra MIA, completar el segundo factor, o volver a iniciar sesión), y nunca ve datos.

**Why this priority**: con cuentas institucionales y listas de acceso los rechazos serán frecuentes al principio (primeros inicios de sesión, cuentas faltantes); sin mensajes claros, cada rechazo sería una consulta al operador.

**Independent Test**: iniciar sesión con (a) una cuenta válida del TEC que no está en la lista, (b) una cuenta en la lista cuyo token no declara segundo factor y (c) una sesión con token vencido; verificar que cada caso muestra su mensaje propio y no deja ver datos.

**Acceptance Scenarios**:

1. **Given** una cuenta del TEC que no está en la lista de administradores (o está desactivada), **When** inicia sesión, **Then** se muestra "cuenta no autorizada", con el correo con que intentó y a quién pedir acceso, y no se muestran datos.
2. **Given** un inicio de sesión sin segundo factor, **When** llega a la API, **Then** se rechaza y el panel explica que se necesita la verificación en dos pasos.
3. **Given** una identidad que venció mientras la persona trabaja (dura cerca de una hora), **When** se hace cualquier operación, **Then** el panel la renueva en silencio y completa la operación sin interrumpir, y solo si la renovación no es posible (la sesión de Microsoft venció o fue revocada) avisa que la sesión venció y ofrece iniciar sesión de nuevo, sin perder lo que la persona estaba escribiendo cuando sea posible.
4. **Given** un correo de otro directorio (por ejemplo una cuenta personal), **When** intenta entrar, **Then** se rechaza y no hay forma de que un token de otro directorio sea aceptado.
5. **Given** una persona a la que se le desactiva el acceso mientras tiene una sesión abierta, **When** hace su siguiente operación, **Then** se rechaza como no autorizada sin esperar a que venza su sesión.

---

### User Story 3 - Dar y quitar acceso a las personas con un script (Priority: P1)

El operador de MIA agrega a la lista de administradores el correo de cada persona con su alcance (global o una o más unidades), consulta la lista y desactiva a quien deja de necesitar acceso, usando un script de línea de comandos. No hay pantalla de gestión en el panel.

**Why this priority**: sin lista no entra nadie; es lo que permite cargar a las cuatro personas y quitar el acceso cuando cambie el equipo.

**Independent Test**: agregar un correo con alcance Computación, verificar con el listado que aparece activo con ese alcance, desactivarlo y verificar que su siguiente petición se rechaza; volver a agregarlo lo reactiva.

**Acceptance Scenarios**:

1. **Given** un correo nuevo, **When** se agrega con alcance de una o más unidades (por nombre) o global, **Then** queda registrado y activo; agregar uno ya existente actualiza su alcance en vez de duplicarlo.
2. **Given** la lista, **When** se consulta, **Then** muestra por cada correo su alcance y si está activo.
3. **Given** un correo activo, **When** se desactiva, **Then** conserva su registro pero deja de poder usar el panel de inmediato.
4. **Given** un nombre de unidad que no existe o un correo que no es de la forma de un correo, **When** se intenta agregar, **Then** el script lo rechaza con un mensaje claro y no guarda nada.
5. **Given** que el correo se escribe con mayúsculas distintas, **When** la persona inicia sesión, **Then** se reconoce igual (los correos no distinguen mayúsculas).

---

### User Story 4 - Que la separación también cubra artefactos y uso (Priority: P2)

Una persona de alcance de unidad solo ve y gestiona los artefactos de consulta que dan acceso exclusivamente a dominios de sus unidades, solo puede crear artefactos con acceso dentro de sus unidades, y el módulo Uso (indicadores, series, tablas, registro de consultas con su detalle, descarga CSV) cubre únicamente esos artefactos. El saldo de OpenRouter y los artefactos que abarcan todo o varias unidades son del alcance global.

**Why this priority**: sin esto una persona de Computación vería las preguntas (con datos personales) hechas en la Consulta de Administración de Empresas. Se separa de la historia 1 porque esa deja funcionando el inventario y el acceso, y esta extiende la separación al resto del panel.

**Independent Test**: con el artefacto de Computación, el de Administración de Empresas y uno que da acceso a todos los dominios, listar artefactos y uso con cada tipo de sesión y comprobar qué ve cada una; luego intentar por la API leer el detalle de una consulta, descargar el CSV o editar un artefacto ajeno y verificar el rechazo.

**Acceptance Scenarios**:

1. **Given** artefactos de Computación, de Administración de Empresas y uno de "todos los dominios", **When** una sesión de alcance Computación lista artefactos, **Then** ve solo el de Computación.
2. **Given** una sesión de alcance Computación, **When** crea un artefacto con acceso a dominios o a la unidad Computación, **Then** se crea; **When** intenta uno con "todos los dominios", con otra unidad o con una mezcla de unidades, **Then** se rechaza.
3. **Given** una sesión de alcance Computación, **When** intenta modificar, desactivar o regenerar la clave de un artefacto ajeno, **Then** se rechaza como no encontrado o prohibido, sin revelar si existe.
4. **Given** una sesión de alcance Computación, **When** abre el módulo Uso, **Then** los indicadores, series, tablas, el registro, el detalle de cada consulta y el CSV incluyen solo consultas de artefactos de Computación.
5. **Given** una sesión de alcance Computación, **When** pide el detalle de una consulta de otro artefacto (por su identificador), **Then** se rechaza como no encontrada.
6. **Given** una sesión de alcance Computación, **When** abre Uso, **Then** el saldo de OpenRouter no se muestra ni se puede pedir; solo el alcance global lo ve.
7. **Given** una sesión de alcance global, **When** usa Artefactos y Uso, **Then** ve todos los artefactos y todo el registro, como hoy.
8. **Given** una persona con varias unidades en su alcance, **When** crea un artefacto con acceso a dominios de esas unidades, **Then** se permite, pues todas están dentro de su alcance, salvo "todos los dominios", que es solo global.

---

### User Story 5 - Los scripts de carga siguen funcionando con la clave de automatización (Priority: P2)

Quien carga documentos o reorganiza datos desde la terminal (scripts/cargar_carpeta.py, scripts/reorganizar_v2.py) sigue usando `ADMIN_KEY`, que pasa a ser una clave de automatización de alcance global y que ya no se usa desde el navegador. Si se deja vacía, queda desactivada y nada puede usarla.

**Why this priority**: sin ella, las cargas masivas desde la laptop dejarían de funcionar (no pueden iniciar sesión con Microsoft). Es P2 porque ya funciona hoy y el cambio es de alcance, no de comportamiento.

**Independent Test**: con `ADMIN_KEY` configurada, hacer con ella una operación de escritura y una lectura globales y comprobar que funcionan; vaciarla, reiniciar y comprobar que la misma clave se rechaza.

**Acceptance Scenarios**:

1. **Given** `ADMIN_KEY` configurada, **When** un script la envía, **Then** tiene alcance global en las rutas de administración, como hoy.
2. **Given** `ADMIN_KEY` vacía, **When** alguien envía cualquier valor como clave de administración, **Then** se rechaza (sin errores que sugieran que existe).
3. **Given** el panel ya en producción, **When** se revisa su código y su almacenamiento, **Then** ya no pide, envía ni guarda `ADMIN_KEY`.
4. **Given** una operación hecha con la clave de automatización, **When** se revisa el registro del servidor, **Then** queda atribuida a "clave de automatización" y no a una persona.

---

### User Story 6 - Saber quién hizo cada cambio (Priority: P3)

Cada operación de escritura de administración (crear unidad, dominio, carpeta, renombrar o borrar carpeta, subir documento, crear o modificar artefacto, regenerar clave) deja una línea en el registro del servidor con quién la hizo (su correo, o la clave de automatización), qué hizo y sobre qué, sin guardar secretos.

**Why this priority**: es lo que la clave compartida no permitía, pero no cambia lo que las personas pueden hacer; es la parte más simple y la que se puede entregar al final.

**Independent Test**: hacer una operación de escritura con una sesión y revisar que el registro del servidor incluye el correo, la operación y el objeto afectado, y que no incluye tokens ni claves de artefacto.

**Acceptance Scenarios**:

1. **Given** una operación de escritura hecha con una sesión, **When** se revisa el registro del servidor, **Then** hay una línea estructurada con fecha, correo, operación y objeto afectado.
2. **Given** un rechazo por falta de permiso en una unidad ajena, **When** se revisa el registro, **Then** también queda anotado con el correo y lo que intentó.
3. **Given** cualquier línea del registro, **When** se inspecciona, **Then** no contiene tokens de Microsoft, `ADMIN_KEY` ni claves de artefacto.

---

### Edge Cases

- La instancia de la API no tiene configurado el identificador de la aplicación registrada (aún no hay client ID): las rutas de administración no aceptan inicio de sesión (responden que no está configurado) y siguen aceptando la clave de automatización si está activa; el panel muestra que el inicio de sesión no está configurado en vez de fallar sin explicación.
- El segundo factor no lo emite la política de TI en el token: existe un ajuste de la instancia para dejar de exigirlo; por defecto se exige. Desactivarlo es una decisión consciente del operador y queda documentada.
- Las claves públicas del directorio de Microsoft no se pueden obtener en un momento dado: si ya hay claves guardadas recientes, se siguen usando; si no hay ninguna, la API rechaza con un error de servicio no disponible, no con "no autorizado".
- Microsoft rota sus claves de firma: una clave desconocida provoca una nueva consulta de claves antes de rechazar, con un límite de frecuencia para que tokens falsos no puedan forzar consultas sin fin.
- La persona de alcance de unidad tiene una unidad que luego se renombra: el alcance sigue a la unidad, no al nombre.
- Una persona sin ninguna unidad ni alcance global (alcance vacío): es una cuenta sin acceso a nada; el script no debe permitir crearla así.
- Se desactiva el último administrador global: la clave de automatización sigue siendo la vía de emergencia, siempre que esté activa; el script avisa si no queda ningún alcance global activo.
- El token de una persona viaja en cada petición: solo se envía por conexión cifrada hacia la API publicada y nunca se escribe en el registro.
- Un artefacto con acceso a dominios de dos unidades, visto por alguien con solo una de ellas: no lo ve (solo ve los exclusivamente dentro de su alcance).
- Una unidad sin ningún dominio todavía: la persona con alcance sobre ella la ve vacía y puede crear su primer dominio.
- Dos pestañas abiertas del panel: cada una guarda su propia sesión (solo vive en su pestaña), así que cada una inicia sesión por separado, lo que con Microsoft suele ser un clic; cerrar sesión en una no afecta a la otra, y cada una sigue sin dejar credencial alguna al cerrarse.
- El navegador bloquea las ventanas o el almacenamiento necesario para iniciar sesión: el panel lo explica en vez de quedarse en blanco.

## Requirements *(mandatory)*

### Functional Requirements

**Inicio de sesión en el panel**

- **FR-001**: El panel DEBE iniciar sesión con la cuenta institucional del TEC mediante el flujo de código de autorización con PKCE de Microsoft, sin secreto de cliente y sin flujo implícito.
- **FR-002**: Sin sesión, el panel DEBE mostrar solo la pantalla de inicio de sesión, sin ningún dato de MIA.
- **FR-003**: Con sesión, el panel DEBE mostrar el correo de quien está dentro y permitir cerrar la sesión; al cerrarla no DEBE quedar credencial alguna en el navegador.
- **FR-004**: El panel DEBE guardar la sesión solo para la pestaña abierta (no persistente entre sesiones del navegador) y NO DEBE usar el almacenamiento persistente del navegador para credenciales.
- **FR-005**: Cuando la identidad esté por vencer o haya vencido, el panel DEBE renovarla en silencio y reintentar la operación pendiente, sin que la persona vuelva a escribir sus datos; una subida de varios documentos no DEBE interrumpirse por el vencimiento.
- **FR-006**: El panel DEBE mostrar mensajes distintos y claros, en español, para: cuenta no autorizada, inicio de sesión sin segundo factor, sesión vencida, inicio de sesión no configurado, y fallo o cancelación del inicio de sesión en Microsoft.
- **FR-007**: El panel DEBE ser utilizable en pantallas de computadora y de celular, y en modo claro y oscuro, incluyendo la pantalla de inicio de sesión y los mensajes de rechazo.
- **FR-008**: El identificador de la aplicación registrada (client ID) DEBE ser una configuración de la instalación (de la API y de la compilación del panel), nunca estar fijo en el código; el identificador del directorio del TEC es fijo.

**Validación en la API**

- **FR-009**: La API DEBE validar la identidad en cada petición de administración, sin confiar en nada que el navegador declare: firma contra las claves públicas del directorio del TEC (guardadas en memoria con renovación), emisor, audiencia igual al identificador de la aplicación, directorio igual al del TEC, y vigencia.
- **FR-010**: La API DEBE exigir que el inicio de sesión incluya segundo factor, con un ajuste de la instancia que permita no exigirlo; por defecto se exige.
- **FR-011**: La API DEBE tomar el correo de la identidad validada y aceptar la petición solo si está en la lista de administradores activos, sin distinguir mayúsculas.
- **FR-012**: Una petición sin credenciales o con credenciales inválidas, vencidas, de otro directorio o de otra aplicación DEBE rechazarse como no autorizada; una identidad válida cuyo correo no está activo en la lista, o sin segundo factor, o sin permiso sobre lo pedido, DEBE rechazarse como prohibida, con un motivo distinguible para que el panel muestre su mensaje.
- **FR-013**: La verificación de la identidad DEBE poder probarse sin conexión a Microsoft y sin el identificador real de la aplicación, con identidades de prueba firmadas localmente y un conjunto de claves de prueba inyectable.

**Lista de administradores**

- **FR-014**: La lista de administradores DEBE guardarse en la base de datos: correo (único, sin distinguir mayúsculas), alcance (global, o una o más unidades) y si está activo.
- **FR-015**: Un script de línea de comandos DEBE permitir agregar un administrador (con alcance global o con unidades indicadas por nombre), listarlos y desactivarlos (y reactivarlos al volver a agregar), y rechazar entradas inválidas sin guardar nada.
- **FR-016**: El panel NO DEBE incluir pantalla de gestión de administradores.

**Separación por unidad**

- **FR-017**: Con alcance global, la persona DEBE poder ver y hacer todo lo que hoy permite la clave compartida, salvo FR-023.
- **FR-018**: Con alcance de unidad, el inventario (unidades, dominios, carpetas y documentos) DEBE mostrar solo lo de sus unidades, y crear dominios, carpetas, renombrar o borrar carpetas y subir documentos DEBE permitirse solo dentro de ellas. Crear unidades DEBE ser exclusivo del alcance global.
- **FR-019**: Con alcance de unidad, los listados de artefactos DEBEN incluir solo los que dan acceso exclusivamente a dominios (o unidades completas) dentro de su alcance; modificar, desactivar o regenerar la clave de un artefacto fuera de su alcance DEBE rechazarse. Crear un artefacto DEBE permitirse solo con acceso dentro de su alcance; los de "todos los dominios" o con acceso a unidades fuera del alcance son exclusivos del alcance global.
- **FR-020**: Con alcance de unidad, el módulo Uso (indicadores, series, tablas, registro, detalle de una consulta y descarga CSV) DEBE cubrir solo consultas de los artefactos visibles según FR-019; pedir una consulta o artefacto fuera del alcance DEBE responder como no encontrado.
- **FR-021**: El saldo de OpenRouter DEBE ser exclusivo del alcance global.
- **FR-022**: Las lecturas del inventario (unidades, dominios sin clave de artefacto, documentos de un dominio y el árbol completo) que hoy son públicas DEBEN exigir sesión (o la clave de automatización) y devolver solo lo del alcance de quien pregunta; sin credencial responden no autorizado. `/health` sigue público. Esto no DEBE afectar a la lista de dominios ni a la configuración que consultan los artefactos con su propia clave.
- **FR-023**: Los topes globales de gasto y la configuración de la instancia NO DEBEN ser editables por nadie desde el panel (como hoy), ni con alcance global.
- **FR-024**: Cuando el alcance de una persona cambia o se desactiva, el cambio DEBE regir desde su siguiente petición, sin cerrar su sesión de Microsoft.

**Clave de automatización**

- **FR-025**: `ADMIN_KEY` DEBE conservarse únicamente como clave de automatización con alcance global para scripts, y DEBE desactivarse dejándola vacía (ninguna clave se acepta entonces). El panel NO DEBE pedirla, enviarla ni guardarla.
- **FR-026**: Las rutas de consulta (`/query`, calificación, configuración y dominios con la clave de un artefacto) y las claves de artefacto NO DEBEN cambiar.

**Registro**

- **FR-027**: Cada operación de escritura de administración (y cada rechazo por falta de permiso sobre lo pedido) DEBE dejar una línea estructurada en el registro del servidor con fecha, quién (correo o "clave de automatización"), operación y objeto afectado, sin guardar tokens ni claves.

**Pruebas y documentación**

- **FR-028**: Cada ruta cuyo comportamiento cambia DEBE tener pruebas automáticas para: alcance global, alcance de unidad, cuenta no autorizada, sin segundo factor, identidad vencida o de otro directorio, y clave de automatización (activa e inactiva). La lógica del panel que no depende de la red (interpretación de errores de acceso, cómo se decide qué mostrar según el alcance) DEBE tener pruebas automáticas.
- **FR-029**: La documentación (arquitectura, operación, solicitud a TI, instrucciones del panel y del script) y los ejemplos de configuración DEBEN actualizarse, incluyendo cómo dar y quitar acceso y qué hacer si TI cambia algo.

### Key Entities

- **Administrador**: una persona autorizada a usar el panel. Tiene un correo institucional (único, sin distinguir mayúsculas), un alcance (global, o un conjunto de una o más unidades) y un estado activo o inactivo. Lo gestiona el operador con el script.
- **Alcance**: el conjunto de unidades sobre las que una sesión puede ver y operar; "global" equivale a todas, incluidas las futuras, y además a lo que no pertenece a ninguna unidad (artefactos de todos los dominios, saldo, dominios sin unidad).
- **Sesión del panel**: la identidad firmada por Microsoft que el panel presenta en cada petición; vive solo en la pestaña abierta y se valida completa en cada petición.
- **Clave de automatización**: `ADMIN_KEY`, alcance global, solo para scripts.
- **Registro de administración**: líneas del servidor (no tabla) que atribuyen cada escritura a una persona o a la clave de automatización.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de los intentos de una persona de alcance de unidad de ver, crear, modificar o descargar algo de una unidad ajena (inventario, artefactos, uso, registro, CSV) se rechazan o devuelven vacío, incluidos los hechos directamente contra la API sin pasar por el panel.
- **SC-002**: Una persona autorizada, con su cuenta del TEC, llega del enlace del panel a ver su inventario en menos de 1 minuto y sin recibir ni conocer ninguna clave.
- **SC-003**: El 100 % de los intentos de entrar con cuenta no listada, desactivada, sin segundo factor, vencida o de otro directorio se rechazan, y cada uno muestra en el panel el mensaje que le corresponde.
- **SC-004**: Desactivar a una persona con el script impide su siguiente operación en menos de 1 minuto, sin tocar nada más.
- **SC-005**: Tras esta entrega, el panel publicado no contiene ni guarda ninguna clave compartida: revisando su código y el almacenamiento del navegador no aparece `ADMIN_KEY`.
- **SC-006**: El 100 % de las escrituras de administración quedan atribuidas en el registro del servidor a una persona o a la clave de automatización, y el 0 % de las líneas contiene un token o una clave.
- **SC-007**: Los scripts de carga existentes siguen funcionando sin cambios con `ADMIN_KEY`, y la Consulta administrativa sigue funcionando sin cambios con la clave de su artefacto.
- **SC-008**: Todo lo anterior queda verificado con pruebas automáticas y en un navegador real contra un servidor de identidad simulado, sin necesidad del identificador real de la aplicación.

## Assumptions

- La aplicación se registrará en el directorio del TEC según [docs/REGISTRO_APLICACION_TEC.md](../../docs/REGISTRO_APLICACION_TEC.md) (aplicación de una sola página, código con PKCE, sin secreto) y TI devolverá el client ID. Hasta entonces no se puede probar el inicio de sesión real; queda como pendiente en el quickstart del feature.
- La lista de personas es pequeña (unas cuatro más el operador): un script de línea de comandos basta; no se necesita pantalla de gestión.
- El directorio del TEC es el único aceptado; no hay cuentas de Google ni cuentas personales de Microsoft.
- Coordinador y ayudante de una misma unidad tienen exactamente los mismos permisos: no hay roles dentro de una unidad.
- "Alcance global" es el de quien opera MIA y es el único que ve el saldo de OpenRouter y gestiona los artefactos de todos los dominios o de varias unidades.
- Que las lecturas de inventario exijan sesión (FR-022) está confirmado: leer sin sesión mostraría datos de todas las unidades.
- Las dos Consultas administrativas publicadas y sus claves de artefacto no cambian; el registro de consultas, los topes y los permisos de artefactos ya existen (specs/002 y 003).
- La atribución de operaciones es solo en el registro del servidor (se pierde con los logs de la plataforma); una auditoría en base de datos queda fuera de alcance.
- Fuera de alcance: roles dentro de una unidad, gestión de administradores desde el panel, cuentas de Google, cambios en las Consultas administrativas y auditoría en base de datos.
