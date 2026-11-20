# Feature Specification: Ingesta de documentos CSV

**Feature Branch**: `dev` (feature `021-ingesta-csv`, sin rama propia: los specs y la implementación van en `dev`)

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "MIA acepte documentos CSV (.csv) en la ingesta, como ya acepta PDF, DOCX, TXT y XLSX (feature 018), con el mismo patrón de carga. Casos reales de un archivo de prueba exportado de Excel en español: codificación Windows-1252, separador punto y coma, celdas con saltos de línea, líneas en blanco, 29 columnas con la última sin nombre y unas 45 filas. Se trata como una hoja de Excel (una línea por fila con el nombre de cada encabezado), con los mismos límites y avisos visibles, y con mensajes claros para un archivo vacío, ilegible o con una codificación que no se pueda leer. Aviso de privacidad: un CSV puede traer datos personales."

Contexto: hoy MIA ingesta cuatro tipos de archivo (PDF, DOCX, TXT y XLSX). La feature 018 agregó el libro de Excel y **excluyó el CSV de forma explícita** (su FR-002 lo rechaza), dejándolo para después "con el mismo patrón de cargador". Mucha información institucional sale de otros sistemas o de Excel como CSV (listas de personas admitidas, matrículas, calendarios, resultados de evaluaciones) y hoy hay que abrirla en Excel y guardarla como libro antes de poder consultarla. Esta feature agrega el **CSV** como quinto tipo de fuente: una persona administradora lo sube igual que cualquier otro documento y, una vez procesado, sus datos se pueden consultar por los artefactos con las mismas reglas de dominios, permisos, fuentes y eliminación que ya existen. Los CSV reales no son tan uniformes como un libro de Excel: hay que adivinar su codificación y su separador, y pueden traer celdas con saltos de línea o líneas en blanco. Esta feature resuelve esos casos sin pedirle nada a la persona que sube el archivo. No cambia los demás tipos de archivo ni la forma de consultar.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Subir un CSV y consultarlo (Priority: P1)

Una persona administradora sube un archivo .csv a un dominio, desde el panel o desde la carga por carpeta, igual que sube un PDF o un libro de Excel. El documento aparece en el inventario con su tipo, pasa por el mismo proceso de estados que los demás (pendiente, procesando, listo) y, cuando queda listo, una pregunta cuya respuesta está en una fila del archivo se responde con ese dato y cita el archivo como fuente.

**Why this priority**: es el núcleo de la feature: sin aceptar el archivo y volver sus datos consultables no hay valor.

**Independent Test**: subir un .csv con una lista de cursos (código, nombre, créditos, profesor), esperar a que quede "listo" y preguntar por los créditos de un curso concreto: la respuesta trae el valor correcto y lista el archivo entre las fuentes.

**Acceptance Scenarios**:

1. **Given** un dominio existente, **When** la persona administradora sube un .csv, **Then** el sistema lo acepta, lo muestra en el inventario como documento de tipo CSV y lo procesa por el mismo flujo de estados que los demás tipos.
2. **Given** un documento CSV en estado "listo", **When** alguien pregunta por un dato que está en una fila, **Then** la respuesta contiene ese dato y el archivo aparece entre las fuentes.
3. **Given** un archivo con una extensión distinta de las aceptadas (por ejemplo .xls, .tsv u .ods), **When** se intenta subir, **Then** el sistema lo rechaza con un mensaje claro que indica los tipos aceptados, que ahora incluyen .csv.
4. **Given** un .csv vacío, o cuya primera parte no se puede leer como texto, **When** se procesa, **Then** el documento queda en estado de error con un mensaje comprensible y no afecta a los demás documentos.

---

### User Story 2 - El CSV se lee sin que la persona tenga que prepararlo (Priority: P1)

Un CSV exportado de Excel en español no es UTF-8 con comas: suele venir en Windows-1252 y separado por punto y coma, porque la coma es el separador decimal. Otros sistemas exportan con comas, con tabuladores o con barras verticales y en UTF-8, con o sin marca de orden de bytes. La persona sube el archivo tal como lo tiene y el sistema reconoce solo la codificación y el separador, de modo que las tildes, las eñes y las columnas salen bien.

**Why this priority**: sin esto el archivo de la vida real saldría con letras rotas (`Ã©` por `é`) o con todo el contenido en una sola columna, y las respuestas serían incorrectas. Es lo que distingue "aceptar el archivo" de "poder consultarlo bien".

**Independent Test**: subir un .csv en Windows-1252 con punto y coma y tildes, y otro en UTF-8 con comas; comprobar que en los dos casos el texto ingestado tiene las tildes correctas y una columna por encabezado.

**Acceptance Scenarios**:

1. **Given** un CSV en Windows-1252 con punto y coma, **When** se ingesta, **Then** las tildes, las eñes y los símbolos se conservan y cada columna queda separada.
2. **Given** un CSV en UTF-8, con o sin marca de orden de bytes, y con comas, tabuladores o barras verticales como separador, **When** se ingesta, **Then** se lee correctamente sin ninguna indicación de la persona.
3. **Given** un archivo cuya codificación no se puede determinar con seguridad, **When** se ingesta, **Then** no se inventan caracteres: se usa la codificación más común para archivos de Excel en español y, si hay bytes que no tienen sentido en ella, el documento queda en error con un mensaje que explica el problema y sugiere guardarlo de nuevo como "CSV UTF-8".
4. **Given** un archivo en el que no se reconoce ningún separador (una sola columna), **When** se ingesta, **Then** se lee como una tabla de una columna y se deja un aviso visible, en lugar de fallar.

---

### User Story 3 - Las filas conservan el significado de sus columnas (Priority: P1)

Igual que en una hoja de Excel, el valor de una celda solo tiene sentido junto al encabezado de su columna. Al ingestar, cada fila queda expresada de forma que el dato siempre vaya acompañado de su encabezado, de modo que una pregunta como "¿qué promedio tiene el candidato número 12?" encuentra la fila correcta y no un número suelto.

**Why this priority**: es el mismo requisito que hizo útil al Excel y define si las respuestas son correctas.

**Independent Test**: subir un CSV con encabezados en la primera fila y verificar que, para una fila cualquiera, el texto ingestado asocia cada valor con el encabezado de su columna.

**Acceptance Scenarios**:

1. **Given** un CSV con encabezados en la primera fila, **When** se ingesta, **Then** cada fila de datos queda con cada valor acompañado del encabezado de su columna, con el mismo formato de texto que usa el libro de Excel.
2. **Given** celdas vacías, líneas totalmente en blanco o columnas sin encabezado (como una última columna sin nombre), **When** se ingesta, **Then** las celdas y las líneas vacías no generan texto de relleno y las columnas sin encabezado se identifican por su posición.
3. **Given** celdas con saltos de línea dentro (un texto de varios renglones entre comillas), **When** se ingesta, **Then** la celda se conserva como un solo valor, sin partir la fila en dos.
4. **Given** una fila con más o menos celdas que el encabezado, **When** se ingesta, **Then** no se pierde ni se desplaza ningún dato: las celdas de más se identifican por su posición y las que faltan se omiten.
5. **Given** un CSV cuyos encabezados no están en la primera línea (un título arriba y la tabla más abajo), **When** se ingesta, **Then** se aplica la misma regla que en Excel: el encabezado es la primera fila con al menos dos celdas con contenido y las filas con contenido anteriores se conservan como texto simple.

---

### User Story 4 - Archivos grandes: límites y avisos como en Excel (Priority: P2)

Un CSV puede tener decenas de miles de filas (una exportación de una base de datos). El sistema lo procesa sin agotar los límites del entorno, aplica los mismos topes que a un libro de Excel y avisa cuando recorta algo; nunca recorta en silencio.

**Why this priority**: protege la estabilidad y el costo (entorno gratuito, ingesta local); los archivos pequeños y medianos funcionan sin esta historia.

**Independent Test**: subir un CSV con más filas que el tope y comprobar que el documento queda "listo" con el recorte indicado en el inventario y en una línea de aviso al final del texto; y uno con una línea gigantesca (una celda de millones de caracteres) y comprobar que no agota la memoria.

**Acceptance Scenarios**:

1. **Given** un CSV con más filas con contenido que el máximo de filas de la ingesta de Excel, **When** se ingesta, **Then** se recorta a ese máximo, el documento queda "listo" y el recorte queda indicado en una nota visible del inventario y en una línea de aviso en el texto (el mismo mecanismo que el libro de Excel).
2. **Given** un CSV con más columnas que el máximo de columnas de Excel, **When** se ingesta, **Then** se leen solo las columnas hasta ese máximo y el recorte queda avisado.
3. **Given** un CSV que supera el tamaño máximo de archivo, **When** se intenta subir, **Then** se rechaza con el mensaje de siempre.
4. **Given** una celda o un archivo con comillas sin cerrar, **When** se ingesta, **Then** no se queda esperando ni agota la memoria: se lee lo que se pueda y se avisa, o queda en error con un mensaje claro.

---

### User Story 5 - Aviso de privacidad por datos personales (Priority: P1)

Un CSV es el formato típico de las listas de personas: candidatos, estudiantes, matrículas, con cédulas, correos y teléfonos. Antes de que una persona administradora lo agregue a un dominio debe saber que esos datos se podrán consultar a través de los artefactos, y la propia feature no debe llevar datos personales reales en su código, sus pruebas ni su repositorio.

**Why this priority**: es el riesgo propio de este formato y la constitución exige control de acceso antes de exponer datos sensibles de personas por un artefacto público.

**Independent Test**: en el panel, elegir un .csv para subir y comprobar que se muestra un aviso que dice que no debe contener datos personales sin necesidad y que se recuerda quitar o anonimizar las columnas antes de subirlo; y revisar que ningún archivo del repositorio contiene datos reales de personas.

**Acceptance Scenarios**:

1. **Given** el panel, **When** la persona elige un archivo .csv para subir, **Then** se muestra un aviso visible, no bloqueante, que explica que el contenido se podrá consultar con los artefactos del dominio y que conviene quitar o anonimizar las columnas con datos personales (cédulas, correos, teléfonos, direcciones) antes de subirlo.
2. **Given** la documentación de operación, **When** se consulta cómo subir un CSV, **Then** incluye el mismo aviso y cómo preparar el archivo.
3. **Given** el repositorio de MIA, **When** se revisan los archivos de prueba de esta feature, **Then** todos los datos son inventados y ningún archivo real de personas se incluye ni se versiona.

---

### Edge Cases

- **Archivo vacío o solo con líneas en blanco**: el documento queda en error con el mensaje "sin contenido", igual que un libro vacío.
- **Solo la fila de encabezados, sin datos**: el documento queda en error con el mensaje "sin contenido".
- **Encabezados repetidos**: se conservan y se distinguen por su posición (como en Excel).
- **Valores que parecen números o fechas**: se conservan tal como están escritos en el archivo; el sistema no los interpreta ni los reformatea (un CSV exportado de Excel ya trae los valores mostrados).
- **Texto con caracteres especiales** (tildes, eñes, comillas, símbolos de moneda): se conservan sin alterarse.
- **Codificaciones mezcladas** (un archivo en Windows-1252 con algunas celdas pegadas en UTF-8, que pasa al copiar y pegar desde una página web antes de guardar; lo mostró el archivo real de prueba): las letras y los signos latinos que están en UTF-8 se leen como tales y el resto como Windows-1252, sin dejar `Ã­` en lugar de `í` ni inventar caracteres.
- **Marca de orden de bytes (BOM) al inicio**: no aparece como un carácter raro pegado al primer encabezado.
- **Fin de línea de Windows, de Mac antiguo o de Unix**: se leen igual.
- **Separador distinto dentro de las celdas** (una coma dentro de un texto en un archivo separado por punto y coma): no parte la celda.
- **Archivo con extensión .csv que en realidad es otra cosa** (un libro de Excel o un PDF renombrado): se rechaza o queda en error con el mensaje de lectura, sin afectar a los demás.
- **Subir el mismo CSV dos veces**: se trata igual que los demás tipos (hash del archivo y reglas de duplicados existentes).
- **Eliminar un documento CSV**: se aplica la eliminación completa existente, sin pasos especiales.
- **Fórmulas** (un CSV que se exportó con celdas que empiezan con `=`): no se ejecuta ni se evalúa nada; el texto se trata como cualquier otro valor.
- **Archivos .tsv y de texto con otra extensión**: quedan fuera; se rechazan por la extensión como hoy.

## Requirements *(mandatory)*

### Functional Requirements

**Aceptar y leer el archivo**

- **FR-001**: El sistema MUST aceptar archivos .csv como fuente de ingesta, por todos los caminos por los que hoy acepta PDF, DOCX, TXT y XLSX (panel de administración, API, carga por carpeta y reorganización de datos).
- **FR-002**: El sistema MUST seguir rechazando con un mensaje claro los demás tipos no soportados (.xls antiguo, .xlsm, .tsv, .ods y cualquier otro), indicando los tipos aceptados, que ahora incluyen .csv. Esto reemplaza lo que decía el FR-002 de la feature 018 solo en lo que toca al CSV.
- **FR-003**: El sistema MUST reconocer por sí solo la codificación del archivo entre UTF-8 (con o sin marca de orden de bytes) y la codificación de Windows para Europa occidental (Windows-1252), sin que la persona la indique, y conservar las tildes, las eñes y los demás caracteres.
- **FR-004**: El sistema MUST reconocer por sí solo el separador entre punto y coma, coma, tabulador y barra vertical, sin que la persona lo indique, y respetar las comillas que encierran celdas (un separador o un salto de línea dentro de comillas no parte la celda ni la fila).
- **FR-005**: Un archivo que no se pueda leer (codificación con bytes sin sentido, contenido no textual, vacío, solo encabezados o sin contenido) MUST dejar el documento en estado de error con un mensaje comprensible que explique el problema y, si aplica, sugiera guardarlo como «CSV UTF-8», sin afectar a los demás documentos ni detener el procesamiento de otros archivos.

**Estructura del texto**

- **FR-006**: El texto extraído de cada fila MUST asociar cada valor con el encabezado de su columna, con el **mismo formato de texto** que el cargador de libros de Excel produce para una fila, de modo que las preguntas y las respuestas no distingan el origen del archivo. La única diferencia es la marca de hoja de Excel (la línea `## Hoja: ...` y el prefijo `[Hoja] ` de cada fila), que el CSV no tiene porque no tiene hojas.
- **FR-007**: Las celdas vacías y las líneas totalmente vacías MUST NOT generar texto de relleno; las columnas sin encabezado y las celdas de más se identifican por su posición; las filas con menos celdas que el encabezado no pierden ni desplazan datos.
- **FR-008**: El encabezado MUST ser la primera fila con al menos dos celdas con contenido, y las filas con contenido anteriores se conservan como texto simple, igual que en Excel. Los encabezados repetidos se distinguen por su posición.
- **FR-009**: Los valores MUST conservarse como están escritos en el archivo, sin interpretarlos ni reformatearlos (números, fechas, porcentajes, texto).
- **FR-010**: El sistema MUST NOT ejecutar ni evaluar el contenido de ninguna celda (por ejemplo, las que empiezan con `=`), ni acceder a recursos externos.

**Límites y avisos**

- **FR-011**: El sistema MUST aplicar al CSV los **mismos topes** que a un libro de Excel (cantidad máxima de filas con contenido, cantidad máxima de columnas y filas vacías seguidas) y el mismo mecanismo de aviso: el recorte queda en una nota visible del documento en el inventario y en una línea de aviso en el texto. Nunca MUST recortar en silencio.
- **FR-012**: El sistema MUST proteger la memoria y el tiempo de proceso ante archivos grandes o mal formados (una celda gigantesca, comillas sin cerrar, millones de columnas): no agotarlos y terminar con un resultado o un error claros.
- **FR-013**: El tamaño máximo de archivo es el mismo que para los demás tipos (`MAX_UPLOAD_MB`).

**Reglas comunes e interfaz**

- **FR-014**: Los documentos CSV MUST quedar sujetos a las mismas reglas que los demás: dominios, permisos, estados de procesamiento, fuentes citadas en las respuestas, detección de duplicados por hash y eliminación completa.
- **FR-015**: El inventario y el panel MUST mostrar el tipo CSV de forma reconocible, y el selector de archivo del panel MUST ofrecer .csv.
- **FR-016**: Al elegir un .csv para subir, el panel MUST mostrar un aviso visible y no bloqueante sobre los datos personales: que el contenido se podrá consultar con los artefactos del dominio y que conviene quitar o anonimizar cédulas, correos, teléfonos y direcciones antes de subirlo.

**Privacidad y documentación**

- **FR-017**: Ningún archivo del repositorio (código, pruebas, especificaciones, documentación) MUST contener datos reales de personas: los archivos de prueba son inventados, con la estructura y los problemas de los reales (codificación, separador, celdas multilínea, líneas en blanco, columna sin nombre).
- **FR-018**: La documentación del proyecto (arquitectura, operación y requerimientos) MUST reflejar el nuevo tipo de fuente, sus límites, cómo prepararlo y el aviso de datos personales.
- **FR-019**: Los demás tipos de archivo (PDF, DOCX, TXT y XLSX) y la forma de consultar MUST NOT cambiar; las pruebas existentes deben seguir pasando.

### Key Entities *(include if feature involves data)*

- **Documento (existente)**: gana un quinto tipo de fuente, CSV, junto a PDF, DOCX, TXT y XLSX; conserva nombre de archivo, hash, estado, nota de estado y fecha de carga sin campos nuevos.
- **Archivo CSV**: texto con filas separadas por saltos de línea y celdas separadas por un carácter, con codificación y separador que se reconocen al leerlo.
- **Fila de datos**: conjunto de valores, cada uno asociado a su encabezado, que representa un registro; tiene el mismo texto que una fila de un libro de Excel.
- **Nota de estado (existente, feature 018)**: mensaje corto del documento con el motivo de un error o un aviso de recorte; se reutiliza para el CSV.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Una persona administradora sube un CSV y lo ve "listo" para consultar con el mismo número de pasos que un PDF, sin abrirlo en Excel ni indicar la codificación o el separador.
- **SC-002**: El 100 % de los archivos de prueba de las variantes reales (Windows-1252 con punto y coma, UTF-8 con y sin marca de orden de bytes con coma, con tabulador y con barra vertical, fin de línea de Windows y de Unix) se leen con las tildes correctas y una columna por encabezado.
- **SC-003**: En un conjunto de al menos 20 preguntas de prueba cuyo dato está en filas de CSV de ejemplo (listas, horarios, costos), al menos 90 % se responden con el valor correcto y citan el CSV como fuente.
- **SC-004**: El 100 % de los archivos vacíos, ilegibles, sin contenido o fuera de tope terminan con un mensaje de error o un aviso visible, sin dejar documentos a medias ni afectar a los demás.
- **SC-005**: Un CSV de hasta 5 000 filas queda listo en un tiempo comparable al de un TXT de tamaño equivalente, y un archivo con una celda de millones de caracteres no agota la memoria del proceso.
- **SC-006**: La misma tabla guardada como CSV y como libro de Excel produce el mismo texto de filas, salvo la marca de hoja de Excel, y las mismas preguntas reciben la misma respuesta.
- **SC-007**: El aviso de datos personales se muestra en el 100 % de las veces que se elige un .csv en el panel, y una revisión de los archivos nuevos del repositorio no encuentra ningún dato real de personas.
- **SC-008**: Los documentos PDF, DOCX, TXT y XLSX ya cargados se siguen procesando y consultando exactamente igual que antes (sin regresiones en las pruebas existentes).

## Assumptions

- **Solo .csv.** Los archivos con otras extensiones de texto delimitado (.tsv, .txt con comas) quedan fuera: un .txt sigue leyéndose como texto, y las tablas en otros formatos se guardan como .csv o .xlsx.
- **Codificaciones soportadas**: UTF-8 y Windows-1252, que cubren los archivos exportados de Excel en español y de la mayoría de los sistemas. Otras codificaciones (UTF-16, por ejemplo, que Excel usa al guardar como «Unicode») quedan fuera y producen un error con la sugerencia de guardarlo como «CSV UTF-8».
- **Separadores soportados**: punto y coma, coma, tabulador y barra vertical, el más frecuente en las primeras líneas del archivo, fuera de las comillas.
- **Mismo texto que Excel.** El CSV se trata como una hoja de Excel de una sola hoja sin nombre: la fila se escribe igual que en la feature 018, sin línea de nombre de hoja. Los límites de filas, de columnas y de filas vacías seguidas son los de esa feature (`MAX_EXCEL_ROWS` y sus constantes), compartidos para que el comportamiento sea idéntico; si más adelante conviene separarlos, se hace en la planificación.
- **Sin interpretar valores.** El CSV ya trae el texto mostrado; las fechas, los números y los porcentajes se conservan como están escritos.
- **Aviso, no bloqueo, por datos personales.** Detectar automáticamente columnas con datos personales queda fuera: el aviso del panel y de la documentación cubre el riesgo, y la decisión de qué subir es de la persona administradora. La política de datos del proyecto y los permisos por dominio son los mismos que para los demás documentos; antes de exponer un dominio con datos personales por un artefacto público debe existir control de acceso (constitución).
- **Datos de prueba inventados.** El archivo real con el que se descubrieron los casos tiene datos de personas y no se versiona ni se copia: las pruebas usan archivos generados que reproducen su estructura y sus problemas.
- El procesamiento posterior al texto (división en fragmentos, vectorización, búsqueda híbrida) es el existente y no cambia; la feature agrega el tipo de fuente, no una forma nueva de consultar.
- Los specs y la implementación van en `dev`; el merge a `main` y el despliegue los hace la persona dueña del proyecto.
