# Feature Specification: Panel de administración de MIA

**Feature Branch**: `002-panel-administracion`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Artefacto 1: Panel de administración de MIA, según la sección 2 de docs/Definicion_Requerimientos_V2.md (requerimientos ADM-1 a ADM-3, INV-1 a INV-12, ART-1 a ART-10, USO-1 a USO-8), con los cambios de API de la sección 4, los requerimientos no funcionales de la sección 5 que le aplican (clave de administración, claves por artefacto, topes de gasto por artefacto y de toda la API, CORS), los criterios de aceptación de la sección 8 que le corresponden, la reorganización de los datos ya cargados en unidades académicas, dominios y carpetas (sección 2.3 y anexo A) y la incorporación de Alembic. Un solo artefacto de gestión con tres módulos: Inventario de información (unidades académicas > dominios > carpetas > documentos), Artefactos y accesos (registro de artefactos con clave propia, dominios por unidad o uno a uno, modos permitidos, topes diarios en USD) y Uso (métricas y gráficas al estilo de OpenRouter a partir del registro de consultas). No incluye el artefacto 2 (Consulta administrativa), salvo los cambios de API que el panel necesita para configurarlo."

La fuente de verdad de los requerimientos es [docs/Definicion_Requerimientos_V2.md](../../docs/Definicion_Requerimientos_V2.md). Los identificadores entre corchetes (por ejemplo [INV-3]) remiten a ese documento.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver toda la información de MIA organizada por unidad académica (Priority: P1)

Quien mantiene MIA abre el panel y ve, sin usar Swagger, qué información tiene cargada: las unidades académicas (Computación y Administración de Empresas), sus dominios, las carpetas de cada dominio y los documentos con su tipo, fecha de carga y estado. Los cinco dominios cargados hoy aparecen ya reorganizados en esa estructura, sin haber vuelto a procesar ningún documento.

**Why this priority**: es la base de todo el panel y lo primero que se necesita para operar MIA. Incluye la reorganización de los datos existentes, sin la cual el árbol mostraría la estructura vieja y los demás módulos (permisos por unidad) no tendrían sobre qué apoyarse.

**Independent Test**: tras aplicar la reorganización, abrir el panel y comparar el árbol con la tabla de reorganización de la sección 2.3 y el anexo A del documento de requerimientos; verificar que los 162 documentos siguen en estado "listo" y que una consulta sobre un documento movido sigue respondiendo y citándolo.

**Acceptance Scenarios**:

1. **Given** los cinco dominios cargados hoy, **When** se aplica la reorganización, **Then** el inventario muestra dos unidades: Computación con 7 dominios (Memoria del Consejo, Currículum, Apertura de promoción, Docentes, Proyectos de graduación: Tesis, Proyectos de graduación: Informes de IPA y Proyectos de graduación: Artículos) y Administración de Empresas con 4 (Memoria del Consejo, Currículum, Apertura de promoción y Docentes), con los documentos en las carpetas indicadas.
2. **Given** la reorganización aplicada, **When** se revisan los documentos, **Then** los 162 conservan su estado "listo" y ninguno se volvió a procesar.
3. **Given** los 30 proyectos de graduación de Computación clasificados en el anexo A, **When** se consulta solo el dominio "Proyectos de graduación: Tesis", **Then** las fuentes citadas son únicamente tesis.
4. **Given** el panel abierto, **When** se expande una unidad, un dominio o una carpeta, **Then** se ven su descripción (unidad y dominio), su cantidad de documentos y su contenido; al abrir la página las unidades están abiertas y los dominios contraídos [INV-1, INV-2].
5. **Given** el árbol completo, **When** se escribe en el buscador parte del nombre de una unidad, dominio, carpeta o documento, **Then** el árbol muestra solo las coincidencias y las ramas que las contienen [INV-9].
6. **Given** que no se ingresó la clave de administración, **When** se abre el panel, **Then** se puede ver el inventario, pero no crear, subir ni entrar a los módulos Artefactos y accesos y Uso [ADM-1].

---

### User Story 2 - Agregar unidades, dominios, carpetas y documentos desde el panel (Priority: P1)

Quien mantiene MIA crea una unidad, un dominio dentro de ella o carpetas dentro de un dominio, y agrega documentos eligiéndolos o arrastrándolos sobre el dominio o la carpeta. Ve avanzar cada documento (en cola, procesando, listo o error) sin recargar la página, y se le avisa si un archivo ya existía.

**Why this priority**: junto con la historia 1 reemplaza por completo el uso de Swagger y de scripts para cargar información, que es el propósito original del inventario.

**Independent Test**: con la clave de administración, crear un dominio nuevo en una unidad, crear una carpeta dentro, subir dos documentos a la carpeta y verificar que su estado avanza solo hasta "listo" y que una pregunta sobre su contenido se responde citándolos.

**Acceptance Scenarios**:

1. **Given** la clave de administración ingresada, **When** se crea una unidad o un dominio con un nombre que ya existe en ese nivel, **Then** se muestra el error sin perder lo escrito; un mismo nombre de dominio sí puede repetirse en unidades distintas [INV-3].
2. **Given** un dominio, **When** se crea una carpeta dentro de él o dentro de otra carpeta, **Then** aparece en el árbol; una carpeta con el mismo nombre en el mismo nivel se rechaza [INV-10].
3. **Given** una carpeta, **When** se renombra, **Then** el nuevo nombre se ve de inmediato; **When** se intenta borrar con contenido, **Then** se rechaza explicando que debe estar vacía [INV-11].
4. **Given** varios archivos PDF, DOCX y TXT y uno de otro tipo, **When** se arrastran sobre una carpeta, **Then** los de otro tipo se rechazan con un mensaje antes de subirse y los demás quedan en cola [INV-4].
5. **Given** documentos en cola o procesando, **When** se deja el panel abierto, **Then** su estado se actualiza solo hasta "listo" o "error" [INV-5].
6. **Given** un archivo que ya está en el dominio (en cualquiera de sus carpetas), **When** se sube de nuevo, **Then** el panel avisa que ya existía y no se duplica su contenido [INV-6].
7. **Given** una instancia de la API con la carga de documentos desactivada, **When** se abre el panel, **Then** el árbol se ve completo y los botones de agregar aparecen deshabilitados con un aviso que explica por qué [INV-7].
8. **Given** un dominio recién creado, **When** se confirma su creación, **Then** el panel indica qué artefactos lo verán de inmediato y cuáles no hasta habilitarlo [INV-12].
9. **Given** que no se ingresó la clave de administración o es incorrecta, **When** se intenta crear o subir, **Then** la operación se rechaza como no autorizada.

---

### User Story 3 - Registrar artefactos y definir qué información y qué modos puede usar cada uno (Priority: P2)

Quien mantiene MIA registra cada artefacto de consulta (por ejemplo, las dos instancias de la Consulta administrativa) y obtiene su clave, que se muestra una sola vez. Elige qué puede consultar cada artefacto (unidades completas, dominios uno a uno o todo) y qué modos de respuesta puede usar (literal, con razonamiento). La API aplica esa configuración en cada consulta, sin depender del artefacto.

**Why this priority**: es la pieza que permite tener varias puertas de consulta sobre la misma memoria sin que una vea información de otra (por ejemplo, que Administración de Empresas no vea las actas de Computación, que contienen datos personales). Depende del inventario (historias 1 y 2).

**Independent Test**: registrar un artefacto de prueba con un solo dominio y solo el modo literal; con su clave, verificar que la lista de dominios y la configuración que le devuelve la API contienen solo ese dominio y ese modo, y que una consulta a otro dominio o en modo con razonamiento se rechaza como prohibida.

**Acceptance Scenarios**:

1. **Given** el módulo Artefactos y accesos, **When** se registra un artefacto con nombre y descripción, **Then** se muestra su clave completa una sola vez con un botón para copiarla, y después solo su comienzo [ART-2].
2. **Given** un artefacto con acceso a la unidad Computación completa, **When** se crea un dominio nuevo en esa unidad, **Then** el artefacto lo ve en su consulta siguiente sin reiniciar nada; un artefacto con acceso solo a Administración de Empresas no lo ve [ART-3, ART-5].
3. **Given** un artefacto con solo el modo literal permitido, **When** pide una respuesta con razonamiento, **Then** se rechaza como prohibida [ART-4].
4. **Given** la clave de la instancia de Administración de Empresas, **When** se pide directamente a la API una consulta sobre un dominio de Computación, **Then** se rechaza como prohibida, y lo mismo al revés.
5. **Given** un artefacto registrado, **When** se regenera su clave, **Then** la anterior deja de funcionar de inmediato (no autorizada) y la nueva funciona [ART-6].
6. **Given** un artefacto activo, **When** se desactiva, **Then** sus consultas se rechazan como prohibidas con un mensaje que lo explica; **When** se reactiva, **Then** vuelven a funcionar con la misma configuración [ART-7].
7. **Given** un cambio de dominios o modos de un artefacto, **When** el artefacto hace su consulta siguiente, **Then** ya rige la configuración nueva [ART-5].
8. **Given** una consulta sin clave de artefacto, **When** llega a la API, **Then** se rechaza como no autorizada.

---

### User Story 4 - Limitar el gasto diario de cada artefacto y de toda la API (Priority: P2)

Quien mantiene MIA fija un tope diario de gasto en dólares para cada artefacto, y opcionalmente uno menor solo para el modo con razonamiento. Al alcanzarlo, ese artefacto (o ese modo) deja de responder hasta la medianoche sin afectar a los demás. Por encima existe un tope diario de toda la API, que no se puede cambiar desde el panel.

**Why this priority**: el prototipo no admite cobros variables sin límite, y con varias puertas de consulta una sola (por abuso o por error) podría agotar el saldo de todas. Depende del registro de artefactos (historia 3).

**Independent Test**: fijar un tope muy bajo del modo con razonamiento en un artefacto de prueba, hacer consultas hasta alcanzarlo y verificar que ese modo se rechaza por tope mientras el literal y los demás artefactos siguen funcionando; subir el tope desde el panel y verificar que la consulta siguiente funciona.

**Acceptance Scenarios**:

1. **Given** un artefacto nuevo, **When** se registra, **Then** arranca con un tope diario bajo (0.50 USD) y no se puede guardar sin tope [ART-8].
2. **Given** el campo de tope, **When** se edita, **Then** se muestra cuántas consultas alcanza aproximadamente según el costo medio de cada modo en los últimos 7 días [ART-8].
3. **Given** un artefacto que alcanzó su tope del modo con razonamiento, **When** pide ese modo, **Then** se rechaza por tope hasta la medianoche, mientras el modo literal sigue funcionando y otros artefactos no se ven afectados [ART-9].
4. **Given** un artefacto que alcanzó su tope total, **When** se le sube el tope desde el panel, **Then** su consulta siguiente funciona [ART-9].
5. **Given** que el gasto de toda la API alcanzó el tope global, **When** cualquier artefacto consulta, **Then** se rechaza por tope hasta la medianoche, aunque no haya alcanzado su propio tope.
6. **Given** artefactos cuyos topes suman más que el tope global, **When** se abre el módulo, **Then** el panel muestra un aviso que explica el riesgo [ART-10].
7. **Given** la lista de artefactos, **When** se abre el módulo, **Then** cada uno muestra su gasto de hoy frente a su tope, con una barra de avance, y sus consultas de los últimos 7 días [ART-1].

---

### User Story 5 - Ver el uso y el gasto de MIA por artefacto, modo y modelo (Priority: P3)

Quien mantiene MIA abre el módulo Uso y ve, para el período que elija, cuánto se gastó, cuántas consultas hubo, cuántos tokens se usaron y cuánto tardaron las respuestas, con gráficas a lo largo del tiempo desglosadas por artefacto, modo o modelo, el saldo restante del proveedor de modelos y el registro detallado de consultas.

**Why this priority**: da visibilidad y es el insumo de la evaluación con usuarios, pero MIA funciona y se controla (topes) sin él. Depende de que las consultas queden registradas con su artefacto y costo (historias 3 y 4).

**Independent Test**: tras una serie de consultas de prueba desde dos artefactos, abrir el módulo Uso y verificar que muestra el gasto, las consultas y los tokens de cada uno, y que el gasto total coincide con el que informa el proveedor de modelos para el mismo período con menos de 5 % de diferencia.

**Acceptance Scenarios**:

1. **Given** el módulo Uso, **When** se elige un período (hoy, 7 días, 30 días o un rango) y se filtra por artefacto o modo, **Then** todos los indicadores, gráficas y tablas responden a esa selección [USO-1].
2. **Given** un período, **When** se ven los indicadores, **Then** aparecen gasto, consultas, tokens (de entrada, de salida y de razonamiento), costo medio, tiempo de respuesta (mediana y el 95 % más lento), porcentaje sin información, porcentaje de errores y porcentaje de útiles, cada uno comparado con el período anterior de igual duración [USO-2].
3. **Given** la gráfica, **When** se cambia la métrica (gasto, consultas o tokens) o el desglose (artefacto, modo o modelo), **Then** se redibuja como barras apiladas por hora (período "hoy") o por día [USO-3].
4. **Given** el período, **When** se ven las tablas, **Then** hay una por artefacto (con su gasto de hoy frente a su tope) y una por modelo [USO-4, USO-5].
5. **Given** el registro de consultas, **When** se abre una, **Then** se ven su pregunta, los dominios consultados, los documentos citados y el comentario de su calificación; las consultas rechazadas por tope o por permisos aparecen con su motivo [USO-6].
6. **Given** el saldo del proveedor de modelos, **When** se abre el módulo, **Then** se muestra el saldo restante y cuántos días alcanza al ritmo de los últimos 7 días, con un aviso si alcanza para menos de una semana [USO-7].
7. **Given** un período, **When** se descarga el registro en CSV, **Then** el archivo no incluye el texto de las preguntas salvo que se pida explícitamente [USO-8].

---

### Edge Cases

- Una consulta empieza con el artefacto por debajo de su tope y lo supera al terminar: se completa, y el exceso queda acotado por el costo de una sola consulta (el máximo de tokens de respuesta limita ese costo).
- Dos consultas simultáneas del mismo artefacto cuando le queda poco tope: ambas pueden pasar el control, así que el exceso queda acotado por el costo de las consultas en curso.
- El proveedor de modelos no informa el costo de una respuesta: el costo se calcula con los tokens y el precio configurado del modelo, y se marca como estimado.
- El proveedor de modelos no permite consultar el saldo o falla al hacerlo: el módulo Uso muestra el resto de la información y explica que el saldo no está disponible.
- Un artefacto queda sin dominios porque se le quitaron todos: no se permite guardar esa configuración (debe tener al menos uno) [ART-3].
- Un dominio elegido uno a uno por un artefacto pertenece a una unidad a la que el artefacto ya tiene acceso completo: se acepta sin duplicar el acceso.
- Se borra una carpeta que acaba de quedar vacía mientras se sube un archivo a ella: la subida falla con un mensaje claro y el documento no queda huérfano.
- La clave de administración guardada en el navegador deja de ser válida (se cambió en la API): el panel lo detecta en la primera operación, la olvida y la vuelve a pedir.
- Se pierde la conexión mientras se sube un archivo: el archivo queda marcado con error en el panel y se puede volver a intentar.
- La reorganización se ejecuta dos veces: la segunda vez no cambia nada ni duplica unidades, dominios o carpetas.
- El cambio de día para los topes ocurre a medianoche en la zona horaria de Costa Rica, sin depender de la zona del servidor.

## Requirements *(mandatory)*

### Functional Requirements

**Panel en general**

- **FR-001**: El panel DEBE pedir la clave de administración la primera vez, recordarla en el navegador y permitir olvidarla. Sin clave válida solo permite ver el inventario [ADM-1].
- **FR-002**: El panel DEBE organizarse en módulos (Inventario de información, Artefactos y accesos, Uso) con un menú lateral que en pantallas angostas se vuelve desplegable; al abrirlo muestra el Inventario [ADM-2].
- **FR-003**: Agregar un módulo nuevo DEBE requerir solo una sección nueva del menú y un grupo nuevo de operaciones en la API, sin cambiar los módulos existentes [ADM-3].
- **FR-004**: La interfaz DEBE estar en español, funcionar en pantallas de computadora y de celular, y tener modo claro y oscuro.

**Inventario de información**

- **FR-005**: El sistema DEBE organizar la información en unidades académicas, cada una con dominios, cada dominio con carpetas anidables y documentos. El nombre de una unidad es único; el de un dominio, único dentro de su unidad; el de una carpeta, único dentro de su nivel.
- **FR-006**: El panel DEBE mostrar el inventario completo como un árbol con el detalle de [INV-1] y obtenerlo en una sola petición.
- **FR-007**: Con la clave de administración, el panel DEBE permitir crear unidades y dominios [INV-3], crear, renombrar y borrar carpetas vacías [INV-10, INV-11], y subir documentos a un dominio o carpeta eligiéndolos o arrastrándolos [INV-4].
- **FR-008**: El sistema DEBE rechazar antes de subirlos los archivos que no sean PDF, DOCX o TXT, y los mayores a 25 MB.
- **FR-009**: El panel DEBE actualizar solo el estado de los documentos en proceso hasta que queden listos o en error [INV-5], y avisar cuando un archivo ya existía en el dominio [INV-6].
- **FR-010**: Si la instancia tiene la carga de documentos desactivada, el panel DEBE mostrarse en modo solo lectura con la explicación [INV-7].
- **FR-011**: Al crear un dominio, el panel DEBE indicar qué artefactos lo verán de inmediato y cuáles requieren habilitarlo [INV-12].
- **FR-012**: El panel DEBE permitir buscar por nombre de unidad, dominio, carpeta o documento [INV-9].
- **FR-013**: Las carpetas DEBEN ser solo organizativas: la consulta y los permisos siguen siendo por dominio, y crear, renombrar o reorganizar carpetas no obliga a volver a procesar documentos.

**Reorganización de los datos existentes**

- **FR-014**: El sistema DEBE incorporar un mecanismo de migración versionado del esquema de la base de metadatos, que aplique los cambios a tablas existentes en producción sin perder datos.
- **FR-015**: Una reorganización de una sola vez DEBE llevar los cinco dominios actuales a la estructura de la sección 2.3 del documento de requerimientos: asignar unidad, renombrar dominios, crear los dominios vacíos indicados, ubicar cada documento en su carpeta según la ruta de su archivo de origen, y repartir los 30 proyectos de graduación de Computación en tres dominios según el anexo A.
- **FR-016**: La reorganización NO DEBE volver a procesar documentos; mover documentos entre dominios DEBE actualizar solo la referencia de dominio de su contenido ya indexado.
- **FR-017**: La reorganización DEBE poder ejecutarse más de una vez sin efectos adicionales, y DEBE poder probarse antes contra una copia o un entorno local.

**Artefactos y accesos**

- **FR-018**: El panel DEBE listar los artefactos registrados con el detalle de [ART-1].
- **FR-019**: El sistema DEBE registrar artefactos con nombre único y descripción, generar su clave y mostrarla una sola vez; DEBE guardarla de forma que no se pueda recuperar (solo verificar), y mostrar después solo su comienzo [ART-2].
- **FR-020**: Cada artefacto DEBE tener un acceso a dominios que combine unidades completas (incluidos sus dominios futuros), dominios elegidos uno a uno o "todos los dominios" (incluidas unidades futuras), con al menos uno [ART-3].
- **FR-021**: Cada artefacto DEBE tener al menos un modo de respuesta permitido entre literal y con razonamiento, y el panel DEBE mostrar el costo aproximado por consulta de cada modo [ART-4].
- **FR-022**: Los cambios de acceso, modos, topes y estado DEBEN regir desde la consulta siguiente, sin reiniciar la API ni volver a publicar el artefacto [ART-5].
- **FR-023**: El panel DEBE permitir regenerar la clave de un artefacto (invalidando la anterior de inmediato) y desactivarlo o reactivarlo conservando su configuración y su registro de consultas [ART-6, ART-7].
- **FR-024**: Con la clave de un artefacto, la API DEBE devolver solo sus dominios y modos permitidos, el nombre del artefacto y si alcanzó algún tope; y DEBE rechazar como prohibida una consulta a un dominio o modo no permitido, o de un artefacto desactivado.
- **FR-025**: Toda consulta DEBE requerir la clave de un artefacto activo; sin clave o con una inválida se rechaza como no autorizada.
- **FR-026**: La API DEBE aceptar el modo de respuesta en cada consulta (literal por defecto) y responder cada modo con el modelo configurado para él. Las diferencias de instrucción al modelo y de cantidad de fragmentos entre modos quedan para la especificación de la Consulta administrativa.
- **FR-027**: La API DEBE aceptar peticiones desde los sitios donde se publiquen los artefactos, configurados por la instancia.

**Topes de gasto**

- **FR-028**: Cada artefacto DEBE tener un tope diario de gasto en USD para todos sus modos, obligatorio y con 0.50 USD por defecto, y opcionalmente un tope menor para el modo con razonamiento [ART-8].
- **FR-029**: Antes de cada consulta, el sistema DEBE comparar lo gastado hoy por el artefacto, por ese modo del artefacto y por toda la API con sus topes, y rechazar por tope la consulta si alguno se alcanzó, hasta la medianoche (hora de Costa Rica) [ART-9].
- **FR-030**: El tope diario de toda la API DEBE fijarse por configuración de la instancia y NO DEBE poder cambiarse desde el panel.
- **FR-031**: El panel DEBE avisar cuando la suma de los topes de los artefactos supere el tope de toda la API [ART-10] y mostrar junto a cada tope cuántas consultas alcanza aproximadamente [ART-8].

**Registro de consultas y Uso**

- **FR-032**: Cada consulta DEBE quedar registrada con artefacto, pregunta, dominios, modo, modelo, tokens (de entrada, de salida y de razonamiento), costo en USD (marcando si es estimado), tiempo de respuesta, resultado (respondida, sin información, error, rechazada por tope o por permisos) y fuentes citadas. Las rechazadas se registran con costo cero.
- **FR-033**: El costo de cada consulta DEBE tomarse del que informa el proveedor de modelos; si no lo informa, DEBE calcularse con los tokens y el precio configurado del modelo.
- **FR-034**: El sistema DEBE permitir calificar una consulta como útil o no útil con un comentario opcional, y guardarlo junto a ella.
- **FR-035**: El módulo Uso DEBE ofrecer el período, los filtros, indicadores, gráfica, tablas, registro, saldo y descarga descritos en [USO-1] a [USO-8].
- **FR-036**: El registro de consultas y su detalle DEBEN verse solo con la clave de administración, porque las preguntas pueden contener datos personales.

**Pruebas y compatibilidad**

- **FR-037**: Cada operación nueva o modificada de la API DEBE tener pruebas automáticas.
- **FR-038**: El script de pruebas de aceptación existente DEBE adaptarse a los dominios reorganizados y a la clave de artefacto, y seguir dando 19 de 19 en modo literal.

### Key Entities

- **Unidad académica**: agrupa dominios de un área (Computación, Administración de Empresas). Nombre único y descripción. Es el nivel en que normalmente se da acceso a un artefacto.
- **Dominio**: conjunto de documentos que se elige al consultar (Memoria del Consejo, Currículum...). Pertenece a una unidad, con nombre único dentro de ella. Es la unidad de búsqueda y de permisos.
- **Carpeta**: agrupa documentos dentro de un dominio, anidable, solo organizativa. Nombre único en su nivel.
- **Documento**: archivo cargado (PDF, DOCX o TXT) en un dominio y, opcionalmente, una carpeta; con tipo, fecha de carga, estado y huella de contenido para detectar duplicados.
- **Artefacto**: aplicación registrada que consulta a MIA (cada instancia de la Consulta administrativa, un futuro chatbot). Tiene nombre único, descripción, clave (guardada solo para verificar), estado activo o desactivado, acceso a dominios (unidades, dominios o todos), modos permitidos, tope diario total y tope del modo con razonamiento.
- **Consulta registrada**: cada pregunta recibida, con su artefacto, dominios, modo, modelo, tokens, costo, tiempo, resultado, fuentes y calificación.
- **Modo de respuesta**: literal o con razonamiento; cada uno con su modelo configurado en la instancia y su costo aproximado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Quien mantiene MIA crea un dominio, sube a él dos documentos y los ve listos sin usar Swagger, scripts ni la terminal.
- **SC-002**: Tras la reorganización, el inventario coincide con la tabla de la sección 2.3 del documento de requerimientos, los 162 documentos siguen listos sin reprocesarse, y las pruebas de aceptación dan 19 de 19 en modo literal.
- **SC-003**: El 100 % de las consultas de un artefacto a dominios o modos no permitidos se rechazan, aun enviadas directamente a la API sin pasar por el artefacto.
- **SC-004**: Un cambio de acceso, modo o tope hecho en el panel rige en la consulta siguiente del artefacto, sin reinicios ni nuevas publicaciones.
- **SC-005**: El gasto diario de un artefacto no supera su tope en más del costo de las consultas que estaban en curso al alcanzarlo.
- **SC-006**: Al alcanzar el tope de un artefacto, los demás artefactos siguen respondiendo con normalidad.
- **SC-007**: El gasto total que muestra el módulo Uso para un período coincide con el informado por el proveedor de modelos con menos de 5 % de diferencia.
- **SC-008**: El árbol del inventario completo (162 documentos) se muestra en menos de 3 segundos con la API ya activa.
- **SC-009**: Registrar un artefacto nuevo con su acceso, modos y tope toma menos de 2 minutos.

## Assumptions

- La reorganización (FR-015 a FR-017) usa los archivos de origen en `tmp/` y la clasificación del anexo A, y se prueba primero en local antes de aplicarse en producción.
- Una sola clave de administración, compartida por quienes mantienen MIA, configurada en la instancia. Las cuentas individuales quedan fuera (sección 10 del documento de requerimientos).
- La medianoche para reiniciar los topes es la de Costa Rica (UTC-6, sin horario de verano).
- El tope global de la API por defecto es 3 USD diarios, ajustable por configuración de la instancia.
- Las preguntas registradas se conservan durante todo el prototipo, bajo las mismas condiciones que los documentos con datos personales; una política de retención queda para producción.
- Las dos instancias de la Consulta administrativa se registran en el panel como parte de la puesta en marcha (con acceso a su unidad completa y ambos modos), aunque el artefacto 2 se construya en otra especificación.
- El cliente web actual (`web/`) y los scripts que consultan la API se adaptan para enviar la clave de un artefacto registrado mientras exista la Consulta administrativa nueva.
- Fuera de alcance: borrar o renombrar unidades, dominios y documentos; mover documentos o carpetas; reintentar documentos en error; ver el contenido de un documento; topes mensuales; permisos por carpeta (secciones 2.4 y 10 del documento de requerimientos).
- El panel se publica como un sitio estático separado de la Consulta administrativa, siguiendo la decisión de dos aplicaciones del documento de requerimientos.
