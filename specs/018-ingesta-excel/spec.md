# Feature Specification: Ingesta de documentos Excel

**Feature Branch**: `dev` (feature `018-ingesta-excel`, sin rama propia: los specs y la implementación van en `dev`)

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "MIA acepte documentos Excel (.xlsx) como fuente de ingesta, igual que hoy acepta otros documentos, mediante un nuevo DocumentLoader"

Contexto: hoy MIA ingesta tres tipos de archivo (PDF, DOCX y TXT). Mucha información institucional vive en hojas de cálculo (horarios, listas de cursos, costos, calendarios, matrículas) y hoy hay que copiarla a mano a otro formato para poder consultarla. Esta feature agrega el libro de Excel (.xlsx) como cuarto tipo de fuente: una persona administradora lo sube igual que cualquier otro documento y, una vez procesado, sus datos se pueden consultar por los artefactos (Consulta, chatbot embebible, bot de WhatsApp) con las mismas reglas de dominios, permisos, fuentes y eliminación que ya existen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subir un libro de Excel y consultarlo (Priority: P1)

Una persona administradora sube un archivo .xlsx a un dominio, desde el panel o desde la carga por carpeta, igual que sube un PDF o un DOCX. El documento aparece en el inventario con su tipo, pasa por el mismo proceso de estados que los demás (pendiente, procesando, listo) y, cuando queda listo, una pregunta cuya respuesta está en una celda de la hoja se responde con ese dato y cita el archivo como fuente.

**Why this priority**: es el núcleo de la feature: sin aceptar el archivo y volver sus datos consultables no hay valor. Con solo esta historia ya se pueden consultar hojas de cálculo simples.

**Independent Test**: subir un .xlsx con una hoja de cursos (código, nombre, créditos, profesor), esperar a que el documento quede "listo" y preguntar por los créditos de un curso concreto: la respuesta trae el valor correcto y lista el archivo entre las fuentes.

**Acceptance Scenarios**:

1. **Given** un dominio existente, **When** la persona administradora sube un .xlsx, **Then** el sistema lo acepta, lo muestra en el inventario como documento de tipo Excel y lo procesa por el mismo flujo de estados que los demás tipos.
2. **Given** un documento Excel en estado "listo", **When** alguien pregunta por un dato que está en una celda, **Then** la respuesta contiene ese dato y el archivo aparece entre las fuentes.
3. **Given** un archivo con extensión distinta de las aceptadas (por ejemplo .xls antiguo o .csv), **When** se intenta subir, **Then** el sistema lo rechaza con un mensaje claro que indica los tipos aceptados, igual que hoy.
4. **Given** un .xlsx dañado o protegido con contraseña, **When** se procesa, **Then** el documento queda en estado de error con un mensaje comprensible y no afecta a los demás documentos.

---

### User Story 2 - Las filas conservan el significado de sus columnas (Priority: P1)

Una hoja de cálculo es una tabla: el valor de una celda solo tiene sentido junto al encabezado de su columna y al nombre de su hoja. Al ingestar, cada fila queda expresada de forma que el dato siempre vaya acompañado de lo que significa, de modo que una pregunta como "¿cuántos créditos tiene Redes?" encuentra la fila correcta y no un número suelto sin contexto.

**Why this priority**: sin esto el contenido se vuelve una nube de valores sin etiqueta y las respuestas serían incorrectas o inventadas. Es lo que distingue "aceptar el archivo" de "poder consultarlo bien".

**Independent Test**: subir una hoja con encabezados en la primera fila y verificar que, para una fila cualquiera, el texto ingestado asocia cada valor con el encabezado de su columna y con el nombre de la hoja.

**Acceptance Scenarios**:

1. **Given** una hoja con encabezados en la primera fila, **When** se ingesta, **Then** cada fila de datos queda con cada valor acompañado del encabezado de su columna.
2. **Given** un libro con varias hojas, **When** se ingesta, **Then** el contenido de cada hoja queda identificado con el nombre de su hoja y las hojas no se mezclan.
3. **Given** celdas vacías, filas totalmente vacías o columnas sin encabezado, **When** se ingesta, **Then** las filas y celdas vacías no generan texto de relleno y las columnas sin encabezado se identifican por su posición.
4. **Given** celdas combinadas, **When** se ingesta, **Then** el valor combinado se toma una sola vez, sin repetirse ni perderse.

---

### User Story 3 - Fórmulas, fechas y números se leen como los ve la persona (Priority: P2)

Quien abre el libro en Excel ve resultados, fechas y cantidades con formato (por ejemplo `₡1 250 000`, `15/03/2026`, `85%`). Al ingestar, el sistema toma el valor que se muestra, no la fórmula ni un número interno, para que las respuestas coincidan con lo que la persona ve en su hoja.

**Why this priority**: mejora la exactitud de las respuestas, pero una hoja sin fórmulas ni fechas ya funciona con las historias 1 y 2.

**Independent Test**: subir una hoja con una celda de fórmula (suma de costos), una fecha y un porcentaje, y comprobar que el texto ingestado trae el resultado de la fórmula, la fecha legible y el porcentaje, nunca la expresión de la fórmula ni un número de serie.

**Acceptance Scenarios**:

1. **Given** una celda con fórmula, **When** se ingesta, **Then** se toma el último resultado calculado y guardado en el archivo, no el texto de la fórmula.
2. **Given** una celda de fecha, **When** se ingesta, **Then** aparece como fecha legible y no como número de serie.
3. **Given** una fórmula cuyo resultado no quedó guardado en el archivo, **When** se ingesta, **Then** la celda se omite sin romper el resto de la hoja.

---

### User Story 4 - Libros grandes y hojas que no aportan información (Priority: P3)

Los libros reales traen hojas ocultas, hojas de gráficos, hojas con miles de filas o con filas de totales y notas al pie. El sistema los procesa sin agotar los límites del entorno, ignora lo que no es información consultable y avisa cuando recorta algo.

**Why this priority**: protege la estabilidad y el costo (entorno gratuito, ingesta local), pero los libros pequeños y medianos funcionan sin esta historia.

**Independent Test**: subir un libro con una hoja oculta, una hoja de gráfico y una hoja de miles de filas, y comprobar que el documento queda "listo" sin las hojas ocultas ni los gráficos, y que si se aplicó un recorte por tamaño queda indicado en el documento.

**Acceptance Scenarios**:

1. **Given** un libro con hojas ocultas, **When** se ingesta, **Then** las hojas ocultas no se incluyen.
2. **Given** un libro con gráficos o imágenes incrustadas, **When** se ingesta, **Then** solo se toma el contenido de las celdas, sin falla.
3. **Given** un libro que supera el tamaño máximo de archivo o de filas que MIA admite, **When** se intenta ingestar, **Then** se rechaza o se recorta con un aviso visible a la persona administradora, y nunca queda a medias sin decirlo.

---

### Edge Cases

- Libro sin ninguna hoja visible o con todas las hojas vacías: el documento queda en error con el mensaje "sin contenido", igual que un PDF vacío.
- Hoja con encabezados que no están en la primera fila (título arriba, tabla más abajo): se toma como encabezado la primera fila con al menos dos celdas con contenido, las filas con contenido anteriores (títulos, notas) se conservan como texto simple y las demás filas con contenido son datos.
- Encabezados repetidos en una misma hoja: se conservan ambos y se distinguen por su posición.
- Celdas con saltos de línea, textos muy largos o caracteres especiales (tildes, eñes, símbolos de moneda): se conservan sin alterarse.
- Subir el mismo libro dos veces: se trata igual que los demás tipos (hash del archivo y reglas de duplicados existentes).
- Eliminar un documento Excel: se aplica la eliminación completa existente (vectores, archivo, imágenes y registros) sin pasos especiales.
- Libros con vínculos a otros libros o macros (.xlsm): no se ejecuta nada; las macros no se aceptan como tipo de archivo.
- Hojas con datos sensibles: aplica la misma política de datos que a los demás documentos.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST aceptar archivos .xlsx como fuente de ingesta, por todos los caminos por los que hoy acepta PDF, DOCX y TXT (panel de administración, API y carga por carpeta).
- **FR-002**: El sistema MUST rechazar con un mensaje claro los demás formatos de hoja de cálculo no soportados (.xls antiguo, .xlsm, .csv, .ods), indicando los tipos aceptados.
- **FR-003**: El texto extraído de cada hoja MUST asociar cada valor con el encabezado de su columna y con el nombre de su hoja.
- **FR-004**: El sistema MUST ingestar todas las hojas visibles del libro e ignorar las hojas ocultas.
- **FR-005**: El sistema MUST leer el valor mostrado de cada celda (resultado de fórmulas, fechas legibles, números con su formato) y nunca la expresión de la fórmula.
- **FR-006**: El sistema MUST omitir celdas y filas vacías sin generar texto de relleno, y tratar las celdas combinadas una sola vez.
- **FR-007**: Un libro dañado, protegido con contraseña o sin contenido MUST dejar el documento en estado de error con un mensaje comprensible, sin afectar a los demás documentos ni detener el procesamiento de otros archivos.
- **FR-008**: El sistema MUST aplicar un tope de tamaño del archivo y de cantidad de filas por libro, y MUST informar a la persona administradora cuando rechaza o recorta, nunca recortar en silencio.
- **FR-009**: Los documentos Excel MUST quedar sujetos a las mismas reglas que los demás: dominios, permisos, estados de procesamiento, fuentes citadas en las respuestas, detección de duplicados por hash y eliminación completa.
- **FR-010**: El inventario y el panel MUST mostrar el tipo Excel de forma reconocible y el selector de archivo del panel MUST ofrecer .xlsx.
- **FR-011**: El sistema MUST NOT ejecutar macros ni acceder a vínculos externos del libro.
- **FR-012**: La documentación del proyecto (arquitectura, operación y requerimientos) MUST reflejar el nuevo tipo de fuente y sus límites.

### Key Entities *(include if feature involves data)*

- **Documento (existente)**: gana un cuarto tipo de fuente, Excel, junto a PDF, DOCX y TXT; conserva nombre de archivo, hash, estado y fecha de carga sin campos nuevos.
- **Libro de Excel**: archivo de origen, formado por una o más hojas.
- **Hoja**: tabla con nombre, encabezados de columna y filas de datos; la unidad de contexto que se conserva al ingestar.
- **Fila de datos**: conjunto de valores, cada uno asociado a su encabezado, que representa un registro (un curso, un horario, un costo).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona administradora sube un libro .xlsx y lo ve "listo" para consultar con el mismo número de pasos que un PDF, sin convertirlo antes a otro formato.
- **SC-002**: En un conjunto de al menos 20 preguntas de prueba cuyo dato está en celdas de libros de ejemplo (horarios, cursos, costos), al menos 90% se responden con el valor correcto y citan el libro como fuente.
- **SC-003**: El 100% de los libros dañados, protegidos, vacíos o fuera de tope terminan con un mensaje de error o aviso visible, sin dejar documentos a medias ni afectar a los demás.
- **SC-004**: Un libro típico de hasta 5 000 filas queda listo en un tiempo comparable al de un PDF de tamaño equivalente, sin superar los límites del entorno de despliegue.
- **SC-005**: Los documentos PDF, DOCX y TXT ya cargados se siguen procesando y consultando exactamente igual que antes (sin regresiones en las pruebas existentes).

## Assumptions

- El formato soportado es solo el libro moderno de Excel (.xlsx). El formato antiguo (.xls), los libros con macros (.xlsm), CSV y OpenDocument quedan fuera de alcance; se pueden agregar después con el mismo patrón de cargador.
- Se asume que la mayoría de las hojas tienen forma de tabla con una fila de encabezados (la primera con al menos dos celdas con contenido); las hojas con diseño libre (formularios, tableros) se ingestan de la mejor manera posible sin garantía de precisión.
- Gráficos, imágenes incrustadas, comentarios y formatos de color no se ingestan: solo el contenido de las celdas. Las imágenes por documento (feature 011) no aplican a este tipo.
- Se conserva el valor de las celdas, no su presentación exacta: las fechas se escriben `dd/mm/aaaa` y los porcentajes con `%`, pero no se reproducen los símbolos de moneda ni los separadores de miles (el encabezado de la columna suele indicar la unidad).
- El valor de una fórmula es el guardado por la última vez que el libro se abrió y guardó en Excel; MIA no recalcula fórmulas.
- Los topes concretos de tamaño y de filas se fijan en la planificación según los límites del entorno gratuito documentados en `docs/OPERACION.md`.
- La política de datos (los datos se consideran públicos para pruebas) y los permisos por dominio son los mismos que para los demás documentos.
- El procesamiento posterior al texto (división en fragmentos, vectorización, búsqueda híbrida) es el existente y no cambia; la feature agrega el tipo de fuente, no una forma nueva de consultar.
- Los specs y la implementación van en `dev`; el merge a `main` lo hace la persona dueña del proyecto.
