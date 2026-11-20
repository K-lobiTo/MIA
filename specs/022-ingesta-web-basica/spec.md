# Feature Specification: Ingesta básica de una página web

**Feature Branch**: `dev` (feature `022-ingesta-web-basica`, sin rama propia: los specs y la implementación van en `dev`)

**Created**: 2026-11-20

**Status**: Draft

**Input**: User description: "Versión inicial muy básica de ingesta por web scraping. El usuario ingresa una URL y se extrae solamente la información presente en esa página, sin navegar a otras URLs accesibles desde la misma (sin recorrido de enlaces) y sin interpretar archivos enlazados (por ejemplo PDF descargables). Si la página requiere inicio de sesión, o su estructura impide la extracción (contenido no extraíble, protección anti-bot, contenido generado solo con JavaScript, etc.), se debe indicar que no es posible en el momento exacto en que se intenta añadir como fuente de información, antes de crear la fuente. Fuera de alcance: recorrido de enlaces, lectura de archivos enlazados, inicio de sesión, lectura periódica automática (cada X días), reglas por sitio."

Contexto: hoy MIA ingesta cinco tipos de archivo (PDF, DOCX, TXT, XLSX y CSV) y toda la información institucional que viene de una página web hay que normalizarla a mano y subirla como archivo (ver "Preparar documentos que vienen de páginas web" en `docs/OPERACION.md`). El análisis de viabilidad previo está en `docs/Idea_Fuente_Web.md`: concluye que una fuente web completa (rastreo de varias páginas, lectura de archivos enlazados, inicio de sesión, lectura periódica, reglas por sitio) es viable pero grande y con muchos factores, y que las páginas del propio TEC son el caso más seguro, mientras que sitios como la ACM bloquean con protección anti-bot. Esta feature es el **primer paso, deliberadamente mínimo**: una persona administradora escribe la dirección de **una sola página**, el sistema comprueba en ese momento si puede leerla y, solo si puede, la agrega como documento del dominio con el texto de esa página. No sigue ningún enlace, no abre ningún archivo enlazado, no inicia sesión y no se vuelve a leer sola. Si la página no se puede leer, lo dice en el momento, con la razón, y **no crea nada**. El documento resultante se consulta, se cita, se duplica y se elimina con las mismas reglas que cualquier otro documento. No cambia los demás tipos de archivo ni la forma de consultar.

## Clarifications

### Session 2026-11-20

- Q: Al agregar una página, ¿la persona administradora confirma una sola vez o primero ve el texto extraído y luego confirma? → A: Un solo paso: al confirmar se lee, se comprueba y se crea el documento; el texto se revisa después en el inventario (sin vista previa ni segunda lectura).
- Q: Si la dirección ya está agregada en el dominio pero la página cambió (texto distinto), ¿qué debe hacer el sistema? → A: Rechazar con un mensaje que indica que esa dirección ya está agregada (con su fecha de lectura) y que, para actualizarla, hay que eliminar el documento y volver a agregarla; no se crean dos documentos de la misma dirección ni hay reemplazo automático.
- Q: Cuando se rechaza una página, ¿debe quedar un registro de ese intento en la auditoría? → A: Sí: se audita también el rechazo (quién, qué dirección y la razón), sin guardar contenido de la página y sin crear documento ni registro en el inventario.
- Q: ¿Se incluye en esta versión un nombre propio opcional para el documento web? → A: Sí: un campo opcional de nombre; si queda vacío se usa el título de la página o, si no tiene, el sitio.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agregar una página como fuente y consultarla (Priority: P1)

Una persona administradora, en un dominio, elige agregar una página web en lugar de subir un archivo, escribe la dirección y confirma. El sistema lee esa página, y si encuentra contenido útil, la agrega al dominio como un documento más: aparece en el inventario con su origen web, pasa por los mismos estados que los demás (pendiente, procesando, listo) y, cuando queda listo, una pregunta cuya respuesta está en el texto de esa página se responde con ese dato y cita la página como fuente.

**Why this priority**: es el núcleo de la feature: sin leer la página y volver su texto consultable no hay valor.

**Independent Test**: agregar la dirección de una página pública del TEC con un plan de estudios o un calendario, esperar a que quede "listo" y preguntar por un dato que está en ella: la respuesta trae el valor correcto y lista la página entre las fuentes.

**Acceptance Scenarios**:

1. **Given** un dominio existente y una página pública con contenido de texto, **When** la persona administradora escribe su dirección y confirma, **Then** el sistema la agrega como documento del dominio, la muestra en el inventario como fuente de tipo web con su dirección y la procesa por el mismo flujo de estados que los demás tipos.
2. **Given** un documento web en estado "listo", **When** alguien pregunta por un dato que está en esa página, **Then** la respuesta contiene el dato y la página aparece entre las fuentes con un nombre legible: el nombre propio que indicó la persona administradora o, si no indicó ninguno, el título de la página (o el sitio si no tiene título).
3. **Given** el texto extraído, **When** se revisa el documento, **Then** empieza con una línea que indica la dirección de la página y el día en que se leyó, para saber cuándo puede estar vencida.
4. **Given** una dirección que redirige a otra página pública (por ejemplo, de `http` a `https` o a la dirección canónica), **When** se agrega, **Then** se lee la página final, y la dirección que se guarda y se muestra es la final.

---

### User Story 2 - Saber en el momento si la página no se puede leer (Priority: P1)

Muchas páginas no se pueden leer con una lectura simple: piden iniciar sesión, están detrás de una protección anti-bot, cargan todo su contenido con programación del lado del navegador y llegan casi vacías, no existen, tardan demasiado o prohíben su lectura automática. La persona administradora debe enterarse **en el momento exacto en que intenta agregar la fuente**, con una razón comprensible, y el sistema **no debe crear ningún documento, registro ni resto** de ese intento. Nunca debe quedar una fuente "lista" que en realidad está vacía o con el texto de una pantalla de bloqueo.

**Why this priority**: es lo que hace honesta a una versión básica. Sin esto el sistema aceptaría páginas que no sabe leer y las respuestas saldrían vacías o con el texto de un captcha. Es tan importante como leer bien.

**Independent Test**: intentar agregar (a) una página que exige inicio de sesión, (b) una protegida por anti-bot (por ejemplo, el sitio de la ACM, que responde con una página de verificación), (c) una dirección inexistente y (d) una página cuyo contenido llega solo por programación del navegador; en los cuatro casos aparece un mensaje claro con la razón y el inventario del dominio queda exactamente igual que antes.

**Acceptance Scenarios**:

1. **Given** una página que requiere iniciar sesión (respuesta de acceso no autorizado o prohibido, o redirección a un formulario de ingreso), **When** se intenta agregar, **Then** se informa que la página requiere inicio de sesión y que esta versión no puede leerla, y no se crea ningún documento.
2. **Given** una página protegida por anti-bot o que responde con una pantalla de verificación (captcha, "Attention Required"), **When** se intenta agregar, **Then** se informa que el sitio bloquea la lectura automática y no se intenta esquivar la protección, y no se crea ningún documento.
3. **Given** una página que casi no trae texto en su contenido inicial porque lo arma el navegador al abrirla, **When** se intenta agregar, **Then** se informa que su contenido no se puede extraer sin ejecutar la página, y no se crea ningún documento.
4. **Given** una dirección que no existe, un sitio caído, un tiempo de espera agotado o un certificado inválido, **When** se intenta agregar, **Then** se informa cuál fue el problema (no se encontró, no respondió a tiempo, conexión no segura) y no se crea ningún documento.
5. **Given** una dirección cuyo contenido no es una página de texto (un PDF, una imagen, un archivo descargable), **When** se intenta agregar, **Then** se informa que esta versión solo lee páginas web de texto y, si es un archivo, que debe subirse como archivo; no se crea ningún documento.
6. **Given** una página cuyas reglas de acceso para lectores automáticos (`robots.txt`) prohíben leerla, **When** se intenta agregar, **Then** se informa que el sitio no permite la lectura automática de esa página y no se crea ningún documento.
7. **Given** cualquiera de los casos anteriores, **When** se informa el rechazo, **Then** el mensaje se muestra en la misma pantalla y en el mismo momento del intento (sin esperar a que pase un proceso en segundo plano) y la persona puede corregir la dirección o intentar con otra.

---

### User Story 3 - Se lee solo la página indicada (Priority: P1)

Una página típica tiene decenas de enlaces: menús, otros programas, documentos descargables, redes sociales. Esta versión **no los sigue ni los abre**: el documento contiene únicamente la información presente en la página que la persona indicó. Un enlace sale en el texto como texto con su dirección, para que quien lea el documento sepa a dónde apuntaba, pero la dirección no se visita.

**Why this priority**: es el límite de alcance que mantiene la versión simple, segura y predecible (una dirección, una lectura). Sin él, el costo y el riesgo se multiplican.

**Independent Test**: agregar una página con enlaces a otras páginas y a un PDF; comprobar que el sistema hace una sola lectura (la de esa página), que el texto no contiene nada del contenido de las páginas ni del PDF enlazados, y que los enlaces aparecen como texto con su dirección.

**Acceptance Scenarios**:

1. **Given** una página con enlaces a otras páginas del mismo sitio y de otros sitios, **When** se agrega, **Then** el sistema no visita ninguno y el documento no contiene texto que provenga de ellas.
2. **Given** una página con enlaces a archivos descargables (PDF, formularios), **When** se agrega, **Then** esos archivos no se descargan ni se interpretan; el enlace aparece como texto con su dirección.
3. **Given** una página con un enlace cuyo texto dice "Postúlese aquí", **When** se extrae el texto, **Then** la dirección completa del enlace queda escrita junto al texto (por ejemplo `Postúlese aquí (https://sitio/postulacion)`), para que no se pierda el destino.
4. **Given** una página con marcos incrustados, imágenes, videos o formularios, **When** se agrega, **Then** solo se extrae el texto de la propia página; el contenido de lo incrustado no se lee.

---

### User Story 4 - Texto limpio, sin el ruido de la página (Priority: P2)

El texto crudo de una página trae menús, botones, pie de página, avisos de cookies y listas de otros programas, que no responden ninguna pregunta y degradan las búsquedas. El sistema extrae el contenido principal de la página y descarta ese ruido de forma automática, y conserva la estructura básica (títulos, párrafos, listas y tablas simples) en texto regular. No pretende igualar la normalización manual descrita en `docs/OPERACION.md`: la calidad esperada es "buena, no normalizada a mano", y la persona administradora puede verificar el texto antes de confiar en él.

**Why this priority**: mejora la calidad de las respuestas, pero la feature funciona sin ella (aunque con más ruido). Por eso va después de leer, rechazar y acotar.

**Independent Test**: agregar una página de un programa del TEC y revisar el texto resultante: no aparecen menús ni pie de página, los títulos y las listas se reconocen, y una tabla simple queda con cada fila legible.

**Acceptance Scenarios**:

1. **Given** una página con menú de navegación, pie de página, botones y avisos de cookies, **When** se extrae, **Then** el texto del documento no contiene esos bloques.
2. **Given** una página con títulos, párrafos, listas y una tabla simple, **When** se extrae, **Then** el texto conserva los títulos como líneas propias, cada elemento de lista en su línea y cada fila de la tabla en una línea con sus celdas asociadas a su encabezado.
3. **Given** una página con contenido repetido o líneas sueltas, **When** se extrae, **Then** no quedan líneas vacías sobrantes ni viñetas huérfanas.
4. **Given** un documento web ya agregado, **When** la persona administradora quiere revisar el texto, **Then** puede ver el texto que se guardó desde el inventario para contrastarlo con la página; si no es satisfactorio, elimina el documento y lo vuelve a agregar. No hay vista previa antes de confirmar.

---

### User Story 5 - Reglas de siempre: duplicados, tope, permisos y eliminación (Priority: P2)

El documento web se comporta como cualquier otro: se asigna a un dominio y a una carpeta, respeta los permisos por dominio, no se duplica si ya existe con el mismo contenido, se rechaza si el texto supera el tope de tamaño de los demás documentos y se elimina de forma completa con la eliminación existente. Para actualizar una página que cambió, se elimina el documento y se vuelve a agregar la dirección.

**Why this priority**: la consistencia con el resto del sistema evita reglas nuevas, pero cada una se cubre con mecanismos que ya existen.

**Independent Test**: agregar dos veces la misma dirección en el mismo dominio y comprobar que no queda duplicada; eliminar el documento web y comprobar que desaparece de las respuestas y del inventario.

**Acceptance Scenarios**:

1. **Given** un dominio con un documento web ya agregado, **When** se agrega otra vez la misma página (o una con el mismo texto), **Then** se informa que ya existe y no se crea un duplicado (igual que con un archivo repetido).
2. **Given** un dominio con un documento web ya agregado de una dirección, **When** se intenta agregar esa misma dirección (aunque la página haya cambiado y su texto sea distinto), **Then** se rechaza con un mensaje que indica que esa dirección ya está agregada, con su fecha de lectura, y que para actualizarla hay que eliminar el documento y volver a agregarla; no se crea un segundo documento de la misma dirección.
3. **Given** una persona sin permiso sobre el dominio, **When** intenta agregar una página, **Then** se rechaza igual que la subida de un archivo.
4. **Given** una página cuyo texto extraído supera el tamaño máximo permitido para los demás documentos, **When** se intenta agregar, **Then** se rechaza con el mismo mensaje de tope, y no se recorta en silencio.
5. **Given** un documento web, **When** se elimina, **Then** se aplica la eliminación completa existente, sin pasos especiales.
6. **Given** la lista de documentos del dominio, **When** se muestra un documento web, **Then** se distingue de un archivo por su tipo y muestra la dirección de la página y la fecha de lectura.

---

### Edge Cases

- **Dirección mal escrita o sin esquema** (`tec.ac.cr/posgrado`): se normaliza a `https://` cuando es evidente; si no se puede interpretar como dirección web, se rechaza con un mensaje claro antes de hacer ninguna lectura.
- **Esquemas no web** (`ftp://`, `file://`, `javascript:`, `mailto:`): se rechazan; solo se aceptan `http` y `https`.
- **Direcciones internas o privadas** (`localhost`, direcciones de redes privadas, el servicio de metadatos de la nube): se rechazan, también cuando una redirección apunta a ellas. La lectura nunca debe poder alcanzar la red interna del servidor.
- **Cadena de redirecciones larga o circular**: se corta con un mensaje claro ("demasiadas redirecciones").
- **Página enorme** (varios megabytes de HTML): la lectura tiene un tope de bytes y de tiempo; superarlo se informa como "demasiado grande" o "no respondió a tiempo", sin agotar la memoria.
- **Páginas con muy poco texto legítimo** (una portada con una frase): si el texto útil queda por debajo del mínimo, se rechaza como "no se pudo extraer contenido suficiente". El mínimo es una constante ajustable.
- **Pantalla de bloqueo con respuesta 200** (algunos sitios devuelven la verificación con código de éxito): se reconoce por su contenido y se rechaza como bloqueo, no se agrega como fuente.
- **Páginas con pestañas o acordeones**: se extrae lo que el HTML inicial contenga; lo que solo aparece al hacer clic o al ejecutar la página no se obtiene, y esa limitación se documenta (no se avisa por página porque no se puede detectar de forma fiable).
- **Codificación distinta de UTF-8** (páginas antiguas en Latin-1): se reconoce la declarada por la página y se conservan tildes y eñes.
- **Dirección con parámetros de seguimiento** (`?utm_source=...`): se conservan tal cual; el sistema no reescribe la dirección más allá de las redirecciones.
- **Dos direcciones distintas con el mismo texto** (con y sin barra final, con `www` o sin él): la detección de duplicados por contenido las trata como la misma fuente.
- **La página cambia después de agregarla**: el documento conserva lo leído el día indicado en su primera línea; no se actualiza solo. Para actualizarla se elimina y se vuelve a agregar; mientras el documento exista, agregar de nuevo la misma dirección se rechaza (FR-015a).
- **La misma dirección escrita de otra forma o que redirige a una ya agregada** (con o sin barra final, `http` o `https`, o una dirección corta que termina en la página ya agregada): se compara también la dirección final tras las redirecciones, y se rechaza como repetida.
- **Datos personales en la página** (nombres, correos y teléfonos de la coordinación): el sistema no los filtra; se muestra un aviso en el panel (ver FR-016) y la persona decide.
- **Fórmulas, scripts y estilos de la página**: no se ejecutan ni se leen como contenido; el sistema trata la página solo como texto.
- **Ingesta desactivada en la instancia** (producción con la ingesta apagada, ver `docs/OPERACION.md`): se informa igual que al subir un archivo, y no se hace ninguna lectura.

## Requirements *(mandatory)*

### Functional Requirements

**Agregar una página como fuente**

- **FR-001**: El sistema MUST permitir a una persona administradora agregar una página web como fuente de un dominio escribiendo su dirección, por el panel de administración y por la API, en lugar de subir un archivo. La carga por carpeta y la reorganización de datos no cambian.
- **FR-002**: El sistema MUST leer **solamente la página indicada**, con una única petición de contenido a esa dirección (más las redirecciones de la propia dirección y la consulta de las reglas de acceso del sitio). MUST NOT visitar los enlaces que la página contiene, ni descargar ni interpretar los archivos enlazados, ni leer el contenido de marcos, imágenes o videos incrustados.
- **FR-003**: El sistema MUST aceptar solo direcciones `http` y `https`, y MUST rechazar con un mensaje claro cualquier otra, antes de hacer ninguna lectura.
- **FR-004**: El sistema MUST rechazar direcciones que apunten a la red interna o privada del servidor (incluidas las que lleguen ahí por redirección), de modo que la lectura no pueda usarse para alcanzar recursos internos.
- **FR-005**: El sistema MUST seguir las redirecciones de la dirección hasta un máximo razonable, y guardar y mostrar la dirección final.

**Comprobar al intentar agregar (rechazo inmediato)**

- **FR-006**: Agregar una página MUST ser **una sola acción de confirmación**: al confirmar, el sistema lee la página una única vez, comprueba que se puede leer y, si es así, crea el documento. El resultado (agregada o rechazada, con la razón) se muestra a la persona en esa misma acción, sin vista previa intermedia, sin segunda lectura y sin depender de un proceso en segundo plano para saber si la página era legible.
- **FR-007**: Si la página **no se puede leer**, el sistema MUST rechazarla con un mensaje comprensible que indique la razón y MUST NOT crear ningún documento, registro, archivo ni fragmento de ese intento. Las razones distinguibles MUST incluir como mínimo: requiere inicio de sesión; bloqueada por protección anti-bot o pantalla de verificación; contenido que no se puede extraer sin ejecutar la página (texto insuficiente); no encontrada; sitio sin respuesta o tiempo agotado; conexión no segura o certificado inválido; demasiadas redirecciones; contenido que no es una página de texto (por ejemplo, un PDF); lectura prohibida por las reglas de acceso del sitio; página o texto demasiado grande.
- **FR-007a**: El sistema MUST registrar en la auditoría existente cada intento rechazado, con la persona que lo hizo, la dirección indicada y la razón del rechazo, y MUST NOT guardar contenido de la página ni crear documento o registro en el inventario. El intento aceptado se audita como cualquier documento agregado. Un intento rechazado antes de hacer ninguna lectura (dirección inválida, esquema no web, red interna, repetida) también se audita.
- **FR-008**: El sistema MUST reconocer una pantalla de bloqueo, de verificación o de ingreso aunque el sitio la entregue con un código de éxito, y MUST NOT agregarla como si fuera el contenido de la página.
- **FR-009**: El sistema MUST respetar las reglas de acceso para lectores automáticos que publique el sitio (`robots.txt`) y MUST identificarse con un nombre de cliente claro. MUST NOT intentar esquivar protecciones anti-bot, inicios de sesión ni bloqueos, ni reintentar con otras identidades.
- **FR-010**: La lectura MUST tener topes de tiempo y de tamaño que impidan que una página lenta o gigante agote la memoria o deje la acción colgada, y terminar con un resultado o un rechazo claros.

**Texto extraído**

- **FR-011**: El sistema MUST extraer el contenido principal de la página como texto plano, descartando navegación, menús, botones, pie de página, avisos de cookies, scripts y estilos, y conservando títulos, párrafos, listas y tablas simples en un texto regular (una idea por línea, sin líneas vacías sobrantes ni viñetas huérfanas).
- **FR-012**: Los enlaces del contenido MUST quedar escritos como su texto seguido de su dirección completa (`texto (https://...)`), sin visitarlos; los enlaces sin destino utilizable (anclas internas, `javascript:`) se omiten y dejan solo su texto.
- **FR-013**: La primera línea del texto MUST indicar la dirección final de la página y el día en que se leyó, y el documento MUST tener un nombre legible que se muestre como fuente citada. La persona administradora MUST poder indicar un nombre propio opcional al agregar la página; si lo deja vacío (o solo con espacios), el nombre se toma del título de la página o, si no tiene, del sitio. El nombre propio se limita a una longitud razonable y no se puede cambiar después (para cambiarlo se elimina y se vuelve a agregar).
- **FR-014**: Si tras la extracción el texto útil queda por debajo de un mínimo, el sistema MUST tratar la página como no legible (FR-007) y MUST NOT agregarla. Si supera el tamaño máximo de documento (el de los demás tipos), MUST rechazarla con el mensaje de tope y MUST NOT recortarla en silencio.

**Reglas comunes e interfaz**

- **FR-015**: El documento web MUST quedar sujeto a las mismas reglas que los demás: dominios, carpetas, permisos, estados de procesamiento, fuentes citadas en las respuestas, detección de duplicados por contenido y eliminación completa. El texto extraído entra al mismo proceso de división en fragmentos y vectorización, que no cambia. El sistema MUST NOT volver a leer la página por sí solo.
- **FR-015a**: Dentro de un dominio, el sistema MUST permitir **un solo documento web por dirección**: si la dirección indicada, o la dirección final tras las redirecciones, ya está agregada en el dominio, MUST rechazar el intento con un mensaje que indique que ya existe (con su fecha de lectura) y que para actualizarla hay que eliminar el documento y volver a agregarla, aunque el texto de la página haya cambiado. MUST NOT reemplazar el documento anterior de forma automática. Esta comprobación por dirección es adicional a la detección de duplicados por contenido.
- **FR-016**: El panel MUST ofrecer la acción de agregar una página web junto a la de subir un archivo, con el campo de dirección y el nombre opcional, mostrar el rechazo con su razón en la misma pantalla, y mostrar un aviso visible y no bloqueante: que el contenido se podrá consultar con los artefactos del dominio, que el sistema no filtra datos personales (nombres, correos, teléfonos de contactos) y que conviene revisar el texto una vez agregado (y eliminar el documento si no es adecuado).
- **FR-017**: El inventario MUST mostrar el documento web como tipo web, reconocible frente a un archivo, con su dirección y la fecha de lectura. La persona administradora MUST poder ver, desde el inventario, el texto extraído una vez agregado el documento para contrastarlo con la página.
- **FR-018**: Los tipos de archivo existentes (PDF, DOCX, TXT, XLSX y CSV), la forma de consultar y las pruebas existentes MUST NOT cambiar ni dejar de pasar.

**Documentación y pruebas**

- **FR-019**: La documentación del proyecto (arquitectura, operación y requerimientos, y el estado de `docs/Idea_Fuente_Web.md`) MUST reflejar esta primera versión: qué hace, qué no (rastreo, archivos enlazados, inicio de sesión, lectura periódica, reglas por sitio, páginas con pestañas o cargadas por programación del navegador), la lista de razones de rechazo y cómo actualizar una página que cambió.
- **FR-020**: Las pruebas MUST NOT depender de la red ni de sitios reales: usan páginas guardadas como archivos de prueba (una con contenido, una con menús y ruido, una de verificación anti-bot, una vacía por programación del navegador, una de ingreso) y respuestas simuladas para los errores de conexión.

### Key Entities *(include if feature involves data)*

- **Documento (existente)**: gana un sexto tipo de fuente, web, junto a PDF, DOCX, TXT, XLSX y CSV; conserva su nombre, hash, estado, nota de estado y fecha de carga. Para el tipo web necesita además conservar la dirección final de la página y la fecha de lectura (el modelo de datos exacto se decide en la planificación).
- **Página web (fuente)**: una dirección única `http` o `https` de texto, de la que se lee solo su propio contenido, en una única lectura en el momento de agregarla.
- **Resultado de la comprobación**: aceptada (con el texto extraído) o rechazada (con una razón de la lista de FR-007); un rechazo no deja documento ni registro en el inventario, solo una entrada de auditoría (FR-007a).
- **Texto extraído**: texto plano con primera línea de origen (dirección y fecha), contenido principal con estructura básica y enlaces escritos como texto con dirección.
- **Nota de estado (existente, feature 018)**: mensaje corto del documento; aquí se reutiliza solo para avisos del procesamiento posterior, ya que los rechazos de lectura no crean documento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona administradora agrega una página pública con contenido y la ve "lista" para consultar con un solo paso (escribir la dirección y confirmar), sin descargar ni copiar nada a mano.
- **SC-002**: En un conjunto de al menos 10 páginas de prueba que no se pueden leer (inicio de sesión, anti-bot, vacía por programación del navegador, inexistente, sin respuesta, certificado inválido, redirecciones excesivas, PDF, `robots.txt` que la prohíbe, demasiado grande), el 100 % se rechaza con una razón comprensible y distinta según el caso, y el inventario del dominio queda idéntico al de antes del intento (con una entrada de auditoría por intento, sin contenido de la página).
- **SC-003**: La comprobación de la página (leerla, extraer su texto y decidir si se acepta o se rechaza) termina en menos de 20 segundos incluso con un sitio lento, y el resultado se muestra en la misma acción sin dejar la pantalla esperando. Cuando la página se acepta, su procesamiento posterior (vectorización) puede tardar más y se ve por el estado del documento; si la instancia ingiere dentro de la misma petición, la respuesta de una página aceptada llega además cuando ese procesamiento termina, como al subir un archivo.
- **SC-004**: En el 100 % de las páginas de prueba con enlaces, el sistema hace una sola lectura de contenido (la de la dirección indicada, más sus redirecciones) y el texto no contiene nada de las páginas ni de los archivos enlazados.
- **SC-005**: En páginas de ejemplo con menú, pie de página y avisos de cookies, el texto resultante no contiene esos bloques en al menos el 90 % de los casos, y conserva los títulos, las listas y los datos principales (cifras, fechas, requisitos) en el 100 % de los casos.
- **SC-006**: En un conjunto de al menos 10 preguntas con la respuesta en el texto de páginas de prueba, al menos 80 % se responden con el valor correcto y citan la página como fuente (la calidad esperada es "buena, no igual a la normalizada a mano").
- **SC-007**: Una dirección que apunta a la red interna, a un esquema no web o que redirige a ellas se rechaza en el 100 % de los casos, sin que el servidor llegue a leerla.
- **SC-008**: Agregar la misma página dos veces en el mismo dominio (con el mismo texto o con el texto cambiado, y por la dirección directa o por una redirección) no deja más de un documento, y eliminar el documento web lo retira completamente de las respuestas y del inventario.
- **SC-009**: Los documentos PDF, DOCX, TXT, XLSX y CSV ya cargados se siguen procesando y consultando exactamente igual que antes (sin regresiones en las pruebas existentes).

## Assumptions

- **Versión mínima por decisión del dueño del proyecto.** Una dirección, una página, una lectura. Quedan fuera de esta versión: rastreo de enlaces, lectura de archivos enlazados (un PDF enlazado se sube a mano como archivo), inicio de sesión, lectura periódica automática (cada X días), reglas por sitio, navegador automatizado, páginas que cargan su contenido con programación del navegador y contenido que aparece solo al hacer clic (pestañas, acordeones). Son extensiones futuras sobre lo que aquí se construya.
- **Lectura simple, sin navegador.** La comprobación se hace con una petición HTTP simple; una página que necesita ejecutarse en un navegador para mostrar su contenido se rechaza como "no extraíble". No se intenta esquivar ninguna protección (decisión de `docs/Idea_Fuente_Web.md`).
- **Fuente recomendada: páginas del TEC.** El análisis previo mostró que las páginas del propio TEC son el caso más seguro; sitios ajenos como la ACM pueden rechazarse por anti-bot y eso es el comportamiento correcto de esta versión, no un fallo. Para sitios ajenos al TEC, quien agrega la fuente es responsable de revisar los términos de uso y los derechos de autor; el sistema solo respeta `robots.txt`.
- **Calidad "buena", no normalizada a mano.** La extracción automática no reconstruye pestañas, no repite el nombre del programa en cada sección ni da el formato `<PROGRAMA>: <SECCIÓN>` de la primera línea (que `docs/OPERACION.md` usa para la aclaración de programa de la feature 013): eso, si hace falta, se hace subiendo un texto normalizado a mano como hasta ahora. La primera línea de este documento es la de origen (dirección y fecha), con el título de la página como nombre.
- **Un documento por dirección**, no uno por sección de la página. Dividir una página en varios documentos por tema queda para una versión posterior.
- **Sin actualización automática.** Para actualizar una página que cambió, se elimina el documento y se vuelve a agregar la dirección; no hay operación de reemplazo.
- **Los rechazos no dejan rastro en el inventario, pero sí en la auditoría.** Se muestran en la pantalla y se registran en la auditoría existente con quién, la dirección y la razón (FR-007a), sin contenido de la página.
- **Contenido con datos personales.** No se filtra automáticamente (las páginas de coordinación traen contactos que la guía de normalización pide no cargar); el aviso del panel y la documentación cubren el riesgo y la decisión es de la persona administradora. Los permisos por dominio y la constitución (control de acceso antes de exponer datos de personas en un artefacto público) son los mismos que para los demás documentos.
- **Dónde corre la lectura.** Se supone que ocurre en la instancia de la API donde se agrega la fuente, con la misma política de ingesta desactivada en producción y activa en una instancia local (ver `docs/OPERACION.md`); si la planificación concluye que debe correr en otro lugar, se ajusta ahí. La lectura de una sola página es breve y acotada, a diferencia del rastreo que `docs/Idea_Fuente_Web.md` desaconsejaba dentro de la API.
- **Datos de prueba sin red.** Las páginas de prueba son archivos guardados e inventados, no copias de páginas reales con datos de personas; las pruebas no leen la red.
- El procesamiento posterior al texto (división en fragmentos, vectorización, búsqueda híbrida) es el existente y no cambia; la feature agrega un tipo de fuente, no una forma nueva de consultar.
- Los specs y la implementación van en `dev`; el merge a `main` y el despliegue los hace la persona dueña del proyecto.
