---

description: "Tareas de implementación de la feature 021: ingesta de documentos CSV (quinto tipo de fuente, mismo texto de fila que Excel, codificación y separador reconocidos solos, aviso de datos personales)"
---

# Tasks: Ingesta de documentos CSV

**Input**: Design documents from `specs/021-ingesta-csv/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/ingesta-csv.md](contracts/ingesta-csv.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. El cargador recibe texto de terceros con codificaciones y formatos impredecibles, extrae lógica de un cargador que ya está en producción y toca datos que pueden ser de personas; la spec fija criterios medibles (SC-001 a SC-008). Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Las pruebas de la API usan los fixtures de `tests/conftest.py` (`client`, `db`, `admin`) y el fixture `mundo` de `tests/unit/test_documents_xlsx.py` como modelo (dominio, carpeta de cargas temporal, `ingestion_sync`); las de Excel se arman con `tests/unit/libros_de_prueba.py` (`hacer_libro`). Vitest sin DOM (`renderToString` y funciones puras), como las pruebas existentes de `web/admin/`.

**Organization**: tareas agrupadas por historia de usuario (US1 a US5 de spec.md), precedidas por la base común (el generador de archivos de prueba y la lógica de filas compartida con Excel). **MVP usable**: US1 + US2 + US3 + US5 (con solo US1 un CSV real de Excel en español saldría con letras rotas y en una sola columna; US5 es el aviso de datos personales, que no debe faltar en lo que se despliegue); US4 (límites y robustez) sigue de inmediato.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US5)
- **[USUARIO]**: lo hace el usuario, no quien implementa (merge, despliegue y prueba en producción)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. **No desplegar, no encender servicios de Railway, no cambiar variables de producción ni tocar la base de producción.** Eso lo hace el usuario (T031).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Ningún dato real de personas en el repositorio** (FR-017): ni en el código, las pruebas, las especificaciones ni la documentación. El archivo real de la persona dueña del proyecto (`~/Downloads/Proceso_2026_final(CANDIDATOS).csv`) **no se copia ni se versiona**; solo se usa en T030, desde su ubicación y sin imprimir su contenido. Los datos de prueba son inventados (`Persona 01`, `correo01@ejemplo.test`).
- **Sin dependencias nuevas** (`pyproject.toml`, `web/admin/package.json`), **sin migración** y **sin ajustes de configuración nuevos**: se reutilizan `MAX_EXCEL_ROWS` y `MAX_UPLOAD_MB`. Sin cambios en `whatsapp/`, el fragmentado, los embeddings, el almacén vectorial ni la búsqueda.
- **El texto de un libro de Excel debe salir idéntico antes y después** de extraer `tabular.py` (SC-008): las pruebas de Excel existentes no cambian de resultado. Los nombres `MAX_COLUMNAS`, `MAX_FILAS_VACIAS_SEGUIDAS`, `ERROR_ILEGIBLE`, `ERROR_SIN_CONTENIDO` y `_texto_de_celda` siguen importables desde `mia.ingestion.loaders.xlsx_loader` (las pruebas los importan de ahí).
- Las decisiones y los textos de [research.md](research.md) y [contracts/ingesta-csv.md](contracts/ingesta-csv.md) mandan: cada constante, mensaje y límite citado abajo entre comillas es literal de allí. El texto de los avisos del CSV se arma con la misma lógica que el de Excel.
- Es un prototipo: lo más simple que cumpla la especificación. **No correr `ruff format` sobre carpetas enteras**, solo sobre los archivos nuevos. Antes de tocar `web/admin/` leer [web/admin/README.md](../../web/admin/README.md#interfaz-mantine).

---

## Phase 1: Setup

**Purpose**: los archivos de prueba inventados que usan todas las historias.

- [x] T001 Crear `tests/unit/csv_de_prueba.py` con el generador de CSV inventados (R10), sin datos reales: `csv_bytes(filas=..., separador=";", codificacion="cp1252", bom=False, fin_de_linea="\r\n", ...)` que devuelve los bytes de un CSV con encabezados y filas inventados (`Persona 01`, `correo01@ejemplo.test`, cédulas del estilo `0-0000-0000`, nunca una real), con parámetros para: la codificación (`utf-8`, `utf-8-sig`, `cp1252`, `utf-16`), el separador (`;`, `,`, tabulador, `|`), el fin de línea (`\r\n`, `\n`, `\r`), celdas entre comillas con el separador y con saltos de línea dentro, filas totalmente vacías, una columna final sin encabezado, filas con más y con menos celdas que el encabezado, filas de título antes del encabezado, una comilla sin cerrar y una celda de tamaño dado; y `csv_como_el_real()` que reproduce la **estructura** del archivo real (29 columnas con la última sin nombre, 45 registros, 11 celdas multilínea, 3 filas vacías, Windows-1252 con `;`) con valores falsos, y **con un valor en la columna final sin encabezado en varias filas** (si no, esa columna nunca aparecería en el texto, porque las celdas vacías se omiten y las pruebas de `Columna AC` no tendrían qué comprobar); agregar `if __name__ == "__main__":` que escribe `csv_como_el_real()` en la ruta pasada como argumento (lo usa el quickstart); la prueba de su estructura (45 registros de 29 campos) está en T006(d)

**Checkpoint**: `python tests/unit/csv_de_prueba.py /tmp/ejemplo.csv` escribe un archivo; ningún valor del generador parece un dato real.

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: la lógica de filas compartida (R1), sin cambiar el resultado de Excel.

- [x] T002 [P] Crear `tests/unit/test_tabular.py` con las pruebas de la lógica compartida y una prueba "dorada" de Excel: (a) con filas `(número, textos)` la función devuelve una línea `prefijo + "Encabezado: valor | ..."` por fila con contenido, el encabezado es la primera fila con al menos dos celdas con contenido y no cuenta para el tope; (b) las filas anteriores al encabezado van como texto simple unido con ` | `; (c) las columnas vacías se nombran `Columna <LETRA>` y un encabezado repetido lleva la letra entre paréntesis; (d) **una fila con más celdas que el encabezado** nombra las de más `Columna <LETRA>` en lugar de perderlas ni desplazarlas, y una con menos omite las que faltan; (e) con `limite` filas escritas y una más con contenido, devuelve el número de fila del corte; (f) un texto con más de `MAX_COLUMNAS` (200) columnas con contenido en la columna 201 se corta y produce el aviso `en {objeto} se leyeron solo las primeras 200 columnas`; (g) tras `MAX_FILAS_VACIAS_SEGUIDAS` (10000) filas vacías seguidas deja de leer y avisa `se dejó de leer {objeto} en la fila {n} tras 10000 filas vacías seguidas; si había datos después, no se ingestaron`; y (h) una prueba que arma con `hacer_libro` un libro con dos hojas, filas de título, encabezados repetidos y vacíos, fechas y porcentajes, lo lee con `XlsxLoader` y compara el texto **exacto** con el esperado (escrito a mano a partir de lo que produce hoy el cargador, **ejecutando la prueba antes de T003 para fijar el valor**), para detectar cualquier cambio de resultado
- [x] T003 Crear `src/mia/ingestion/loaders/tabular.py` y extraer a él, desde `src/mia/ingestion/loaders/xlsx_loader.py`, la parte que no depende del formato, según [research.md](research.md) R1: las constantes `MAX_COLUMNAS = 200` y `MAX_FILAS_VACIAS_SEGUIDAS = 10000`, `nombres_de_columnas` (con `get_column_letter` de `openpyxl.utils`; hoy `_nombres_de_columnas`) y `lineas_de_tabla(prefijo, objeto, filas, escritas, limite)` (hoy `_lineas_de_hoja` menos la lectura de `openpyxl`): recibe `filas` como iterable de `(número de fila, lista de textos o None)` ya convertidos, aplica el corte de columnas y de filas vacías y el tope de filas, y devuelve `(líneas, filas escritas en total, número de fila del corte o None, avisos)`, con los avisos redactados con `objeto` (`la hoja "X"` en Excel, `el archivo` en CSV) y **las filas más anchas que el encabezado nombran sus celdas de más `Columna <LETRA>`**; reescribir `XlsxLoader` para que su generador de filas convierta cada celda con `_texto_de_celda` y llame a `lineas_de_tabla` con `prefijo=f"[{hoja.title}] "` y `objeto=f'la hoja "{hoja.title}"'`; conservar en `xlsx_loader.py` los nombres `MAX_COLUMNAS`, `MAX_FILAS_VACIAS_SEGUIDAS`, `ERROR_ILEGIBLE`, `ERROR_SIN_CONTENIDO`, `_texto_de_celda` y `XlsxLoader` importables y su texto idéntico; pasan las pruebas de T002 y **todas** las de Excel sin modificarlas: `pytest tests/unit/test_xlsx_loader.py tests/unit/test_documents_xlsx.py tests/unit/test_loaders_base.py tests/unit/test_reorganizacion.py`

**Checkpoint**: `pytest tests/unit/test_tabular.py tests/unit/test_xlsx_loader.py tests/unit/test_documents_xlsx.py` pasa con el texto de Excel idéntico, y `ruff check src tests` está limpio.

---

## Phase 3: User Story 1 - Subir un CSV y consultarlo (Priority: P1) 🎯 MVP

**Goal**: un `.csv` se acepta por la API, el panel y los scripts, pasa por los estados de siempre y sus filas se consultan citando el archivo; los demás tipos se rechazan con los tipos aceptados.

**Independent Test**: subir por la API un `.csv` de cursos (en esta historia, con coma y UTF-8), ver `done` y preguntar por un dato de una fila; un `.tsv` responde `400` con los tipos aceptados, que incluyen `csv`.

### Tests for User Story 1 (primero, deben fallar)

- [x] T004 [P] [US1] Crear `tests/unit/test_documents_csv.py` (con un `mundo` como el de `tests/unit/test_documents_xlsx.py`): (a) subir un `.csv` (UTF-8, coma) responde `201` con `source_type == "csv"`, queda `done` con `status_note` nulo, el archivo se guarda como `<id>.csv` y tiene fragmentos; (b) la extensión en mayúsculas (`DATOS.CSV`) también se acepta; (c) los fragmentos indexados llevan el identificador del documento (así una respuesta cita el archivo, FR-014) y el texto de la fila con sus encabezados: para eso ampliar `AlmacenFalso` de `tests/unit/almacen_falso.py` con un diccionario `textos` (`{documento: [texto de cada fragmento]}`, que `upsert` llena sin cambiar lo demás) y comprobar que contiene, por ejemplo, `Créditos: 4` junto al nombre del curso; (d) subir el mismo contenido dos veces devuelve el existente con `already_existed: true`; (e) eliminar el documento borra su archivo y sus fragmentos (como en `test_eliminar_un_xlsx_borra_su_archivo_y_sus_fragmentos`); (f) un CSV mayor que `MAX_UPLOAD_MB` responde `413` y no deja archivo; (g) un `.csv` vacío queda en `error` con la nota `El archivo CSV no tiene contenido.` y no afecta a un segundo documento subido después; (h) con la ingesta apagada responde `503` como siempre
- [x] T005 [P] [US1] Actualizar `tests/unit/test_documents_xlsx.py` (aquí queda la **única** prueba del rechazo de otros tipos): el caso parametrizado `test_los_demas_formatos_de_hoja_se_rechazan_con_los_tipos_aceptados` deja de incluir `datos.csv` (el CSV ahora se acepta) y espera el mensaje `Tipo de fuente no soportado: {extension}. Tipos aceptados: pdf, docx, txt, xlsx, csv.`; agregar `datos.tsv` y `datos.ods` al caso; y en `tests/unit/test_loaders_base.py` agregar que `get_loader("csv")` devuelve un `CsvLoader` y que un tipo desconocido sigue lanzando `ValueError`
- [x] T006 [P] [US1] Crear `tests/unit/test_csv_loader.py` con las pruebas del caso básico (se amplía en las historias siguientes): (a) un CSV UTF-8 con coma y encabezados produce una línea por fila `Encabezado: valor | Encabezado: valor` **sin** prefijo de hoja ni línea `## Hoja:`; (b) `CsvLoader().notes` queda vacío sin avisos; (c) un archivo vacío, uno solo con líneas en blanco y uno solo con la fila de encabezados lanzan `LoaderError("El archivo CSV no tiene contenido.")`; (d) `csv_como_el_real()` (T001) tiene 45 registros de 29 campos; (e) el cargador no se llama para un `.xlsx` (usa su propio cargador, la factory decide por tipo)

### Implementation for User Story 1

- [x] T007 [US1] Crear `src/mia/ingestion/loaders/csv_loader.py` con `CsvLoader(DocumentLoader)` en su versión inicial: leer los bytes, decodificar con `utf-8-sig` y separar con la coma por ahora (las historias US2 reemplazan esas dos decisiones), leer los registros con `csv.reader` **alimentado con `io.StringIO(texto, newline="")`** (sin `newline=""` un archivo con fin de línea `\r` falla con `csv.Error` aunque esté bien formado, comprobado; con él se leen igual los fines de línea `\r\n`, `\n` y `\r`, y una celda entre comillas puede traer saltos de línea), convertir cada celda con una función `_texto_de_celda(valor)` propia (valor vacío o solo espacios es `None`; si no, `" ".join(valor.split())`), llamar a `lineas_de_tabla(prefijo="", objeto="el archivo", ...)` de `tabular.py` con `settings.max_excel_rows` como límite, y lanzar `LoaderError("El archivo CSV no tiene contenido.")` si no hay líneas; vaciar `self.notes` al empezar y, por cada aviso, agregarlo a `self.notes` (con la primera letra en mayúscula y punto final) y como línea `[Aviso: ...]` al final del texto, como `XlsxLoader`; agregar a `src/mia/ingestion/loaders/base.py` la rama `if source_type == "csv"` de `get_loader` (importación diferida, como las demás). Pasan las pruebas de T006 y T005 (parte del factory)
- [x] T008 [US1] En `src/mia/api/routes/domains.py` (función `upload_document`, línea del conjunto de tipos) cambiar `{"pdf", "docx", "txt", "xlsx"}` por `{"pdf", "docx", "txt", "xlsx", "csv"}` y el mensaje por `Tipo de fuente no soportado: {source_type}. Tipos aceptados: pdf, docx, txt, xlsx, csv.`; revisar con `grep -rn '"xlsx"' src` que no quede otro lugar con la lista de tipos. Pasan las pruebas de T004 y T005
- [x] T009 [P] [US1] En `scripts/cargar_carpeta.py` y `scripts/reorganizar_v2.py` agregar `.csv` al conjunto `TIPOS` (junto a `.xlsx`) y, si alguno tiene un texto de ayuda o un mensaje que enumere los tipos, incluir CSV; ampliar `tests/unit/test_reorganizacion.py` con una prueba como `test_ubicaciones_acepta_xlsx_e_ignora_los_temporales_de_excel` que verifique que un `.csv` se recorre
- [x] T010 [P] [US1] En el panel: `web/admin/src/modules/inventario/inventoryUtils.ts` agrega `".csv"` a `ALLOWED_EXTENSIONS` y el mensaje de `validateFile` pasa a `Solo se aceptan archivos PDF, DOCX, TXT, XLSX y CSV.`; `web/admin/src/modules/inventario/InventarioPage.tsx` agrega `.csv` al `accept` del `<input type="file">` (`.pdf,.docx,.txt,.xlsx,.csv`); ampliar `web/admin/src/modules/inventario/inventoryUtils.test.ts` (`validateFile` acepta `datos.csv` y `DATOS.CSV`, rechaza `datos.tsv` con el mensaje nuevo); correr `npm test` y `npx tsc --noEmit` en `web/admin/`

**Checkpoint**: US1 completa: `pytest tests/unit/test_documents_csv.py tests/unit/test_csv_loader.py tests/unit/test_documents_xlsx.py tests/unit/test_loaders_base.py` y las pruebas de `web/admin/` pasan; un CSV UTF-8 con coma se sube y se consulta. Todavía no lee bien un CSV de Excel en español (US2).

---

## Phase 4: User Story 2 - El CSV se lee sin que la persona tenga que prepararlo (Priority: P1)

**Goal**: la codificación (UTF-8 con o sin BOM, o Windows-1252) y el separador (`;`, `,`, tabulador o `|`) se reconocen solos; lo ilegible da un error claro.

**Independent Test**: subir el CSV de Windows-1252 con `;` y tildes y uno UTF-8 con comas: en los dos las tildes están bien y hay una columna por encabezado; un UTF-16 queda en error con la sugerencia de «CSV UTF-8».

### Tests for User Story 2 (primero, deben fallar)

- [x] T011 [P] [US2] Ampliar `tests/unit/test_csv_loader.py` con las pruebas de codificación y separador (SC-002): (a) una matriz de variantes con `csv_bytes` (UTF-8 con y sin BOM, Windows-1252) por separador (`;`, `,`, tabulador, `|`) por fin de línea (`\r\n`, `\n`, `\r`): el texto tiene las tildes y eñes correctas (`Ñandú`, `Académico`), una columna por encabezado y ningún `Ã` ni `�`; (b) el BOM de UTF-8 no queda pegado al primer encabezado; (c) una coma dentro de un texto en un archivo separado por `;` no parte la celda, y un `;` dentro de un archivo con comas tampoco; (d) UTF-16 (con su marca de orden de bytes), un archivo con bytes nulos (un `.xlsx` renombrado) y uno con los bytes `81 8D 8F 90 9D` sueltos lanzan `LoaderError` con `No se pudo leer el archivo: no es un CSV de texto en UTF-8 ni en Windows-1252. Guárdalo de nuevo como «CSV UTF-8» y vuelve a subirlo.`; (e) un archivo de una sola columna (sin ningún separador reconocido) se lee como una columna y deja el aviso `No se reconoció un separador de columnas: se leyó como una sola columna.` en `notes` y como línea `[Aviso: ...]`; (f) dos registros no bastan para decidir mal: un archivo de 2 filas con `;` y una coma en un texto elige `;`; (g) `csv_como_el_real()` produce 41 líneas de datos (45 registros menos 3 vacíos menos el encabezado) con todos los encabezados, incluida `Columna AC` para la última sin nombre, y **ningún aviso**
- [x] T012 [P] [US2] Ampliar `tests/unit/test_documents_csv.py` con la carga por API de las variantes reales: un CSV Windows-1252 con `;` (`csv_como_el_real()`) queda `done` y una pregunta por un valor con tilde lo encuentra en el almacén simulado; un UTF-16 y un `.xlsx` renombrado a `.csv` quedan en `error` con la nota de lectura (mensaje de T011 d) y sin afectar a otro documento subido después

### Implementation for User Story 2

- [x] T013 [US2] En `src/mia/ingestion/loaders/csv_loader.py` reemplazar la decodificación fija por `_decodificar(contenido: bytes) -> str` según [research.md](research.md) R2, en este orden: (1) si empieza con `FF FE` o `FE FF` (UTF-16), error; (2) si contiene un byte `00`, error; (3) `contenido.decode("utf-8-sig")` estricto; (4) `contenido.decode("cp1252")` estricto; (5) si ninguna decodifica, error; el error es `LoaderError("No se pudo leer el archivo: no es un CSV de texto en UTF-8 ni en Windows-1252. Guárdalo de nuevo como «CSV UTF-8» y vuelve a subirlo.")`, **sin latin-1 de respaldo** y sin detalles de la excepción; definir la constante del mensaje (`ERROR_ILEGIBLE`) junto a `ERROR_SIN_CONTENIDO`. Pasan las pruebas de codificación de T011
- [x] T014 [US2] En `src/mia/ingestion/loaders/csv_loader.py` agregar `_separador(texto: str) -> str | None` según R3: tomar una muestra (`MUESTRA_BYTES = 64 * 1024` caracteres, cortada en el último salto de línea) y, para cada candidato en el orden `;`, `,`, tabulador, `|`, leer los registros con `csv.reader` (no estricto) y calcular el puntaje: de los primeros `MUESTRA_REGISTROS = 30` registros no vacíos, cuántos tienen la misma cantidad de campos que el registro más común, siempre que esa cantidad sea **de al menos 2**; gana el mayor puntaje y los empates los resuelve el orden de la lista; si ningún candidato llega a 2 campos devuelve `None`, y `load` lee entonces el archivo como una sola columna (delimitador que no aparezca, por ejemplo `\x1f`) y agrega el aviso `no se reconoció un separador de columnas: se leyó como una sola columna`; reemplazar la coma fija de T007. Pasan las pruebas de separador de T011
- [x] T015 [US2] Revisar el cargador completo contra las decisiones R2 y R3 (el CSV real con `;` y Windows-1252, 29 campos en los 45 registros, el `,` no gana por puntaje) y dejar los comentarios de `csv_loader.py` explicando en español por qué cada paso va en ese orden; pasan las pruebas de T011 y T012

**Checkpoint**: US2 completa: `pytest tests/unit/test_csv_loader.py tests/unit/test_documents_csv.py` pasa; un CSV de Excel en español (Windows-1252 con `;`) y uno UTF-8 con comas se leen bien sin indicarle nada a la persona.

---

## Phase 5: User Story 3 - Las filas conservan el significado de sus columnas (Priority: P1)

**Goal**: cada valor va con su encabezado y la estructura de la tabla se respeta: celdas multilínea, líneas en blanco, columna sin nombre, filas irregulares y encabezado que no está en la primera línea.

**Independent Test**: con un CSV con celdas multilínea, 3 filas vacías, una última columna sin nombre y una fila con una celda de más, comprobar que cada fila trae sus encabezados, que ninguna celda parte una fila y que no se pierde ni se desplaza ningún dato.

### Tests for User Story 3 (primero, deben fallar)

- [x] T016 [P] [US3] Ampliar `tests/unit/test_csv_loader.py` (SC-006 y US3): (a) una celda entre comillas con saltos de línea (`"línea 1\nlínea 2"`) queda como **una** celda de una sola línea (`línea 1 línea 2`) y no parte la fila en dos; (b) las líneas en blanco y las filas con solo separadores (`;;;;`) no generan líneas ni texto de relleno; (c) una celda vacía no produce `Encabezado:` en la línea; (d) la columna final sin encabezado se llama `Columna <LETRA>` según su posición (la 29 es `Columna AC`); (e) un encabezado repetido lleva la letra de su columna entre paréntesis; (f) una fila con una celda de más la nombra `Columna <LETRA>` y una con menos omite las que faltan, sin desplazar los valores a otras columnas; (g) una hoja con título y notas arriba (`Proceso 2026` en la primera línea y la tabla más abajo) toma como encabezado la primera fila con al menos dos celdas con contenido y las anteriores van como texto simple; (h) los valores se conservan **como están escritos** (`15/03/2026`, `85%`, `₡1 250 000`, `007`, `=SUMA(A1:A2)`): no se interpretan, no se reformatean y una celda que empieza con `=` no se evalúa ni se altera; (i) los espacios repetidos y los saltos de línea dentro de una celda se unen en un espacio; (j) el texto con `Ñ`, `ü`, `«»` y `€` se conserva sin alterarse
- [x] T017 [P] [US3] Crear `tests/unit/test_csv_equivalencia.py` (SC-006): con una tabla inventada (encabezados con tildes, una celda vacía, una columna sin encabezado, números y fechas ya como texto) armada una vez como `.xlsx` con `hacer_libro` (una hoja de nombre `Hoja1`) y otra como `.csv` (`csv_bytes`), leer cada una con su cargador, **quitar de las líneas del Excel la línea `## Hoja: Hoja1` y el prefijo `[Hoja1] `** y comprobar que las líneas de las filas de los dos son idénticas, y que la misma pregunta de coincidencia de palabras (comparar los conjuntos de pares `Encabezado: valor`) encuentra las mismas filas

### Implementation for User Story 3

- [x] T018 [US3] En `src/mia/ingestion/loaders/csv_loader.py` completar la conversión de las filas leídas a lo que espera `lineas_de_tabla`: `_texto_de_celda(valor)` devuelve `None` si el valor está vacío o solo tiene espacios y, si no, `" ".join(valor.split())` (une saltos de línea y espacios repetidos; no interpreta números, fechas ni fórmulas, R6 y FR-009/FR-010); numerar los registros (`(número, textos)`) con el número de **registro** del CSV (no de línea física, porque una celda multilínea ocupa varias); omitir sin texto de relleno los registros vacíos o con todas las celdas vacías (los cuenta la lógica compartida como filas vacías); y verificar que la fila más ancha que el encabezado nombra sus celdas de más (lo hace `tabular.py`, T003). Pasan las pruebas de T016 y T017

**Checkpoint**: US3 completa: `pytest tests/unit/test_csv_loader.py tests/unit/test_csv_equivalencia.py` pasa; el CSV de ejemplo con la estructura del real produce una línea por fila con sus encabezados.

---

## Phase 6: User Story 5 - Aviso de privacidad por datos personales (Priority: P1)

**Goal**: quien elige un `.csv` en el panel o lo carga por carpeta ve el aviso de datos personales, y el repositorio no contiene datos reales.

**Independent Test**: en el panel, elegir o soltar un `.csv` muestra el aviso (que se puede cerrar y no bloquea); `cargar_carpeta.py` lo imprime una vez; una revisión de archivos versionados no encuentra ningún `.csv` ni correo que no sea de ejemplo.

### Tests for User Story 5 (primero, deben fallar)

- [x] T019 [P] [US5] Ampliar `web/admin/src/modules/inventario/inventoryUtils.test.ts` y crear `web/admin/src/modules/inventario/CsvNotice.test.tsx`: `hasCsv(files)` devuelve verdadero si algún archivo termina en `.csv` (sin importar mayúsculas), falso con otros tipos y con una lista vacía; el componente `CsvNotice` muestra el texto `Los archivos CSV suelen traer datos de personas (cédulas, correos, teléfonos, direcciones). Lo que subas se podrá consultar con los artefactos que tengan acceso a este dominio: quita o anonimiza esas columnas antes de subirlo si no hacen falta.` con tono de advertencia y un botón **Cerrar** que llama a `onClose`
- [x] T020 [P] [US5] Crear `tests/unit/test_csv_sin_datos_reales.py` (FR-017 y SC-007): (a) `git ls-files '*.csv'` (saltar la prueba si no hay repositorio de git) no devuelve ningún archivo; (b) todo correo que genera `csv_bytes` y `csv_como_el_real()` termina en `@ejemplo.test` y ninguna cédula tiene un formato de las de verdad (solo ceros: `0-0000-0000`); (c) `scripts/cargar_carpeta.py` con una carpeta que tiene un `.csv` imprime el aviso de datos personales **una sola vez** aunque haya varios `.csv` (usar `capsys` y la función de recorrido del script; ver cómo prueba `tests/unit/test_reorganizacion.py` las funciones de los scripts)

### Implementation for User Story 5

- [x] T021 [US5] En `web/admin/src/modules/inventario/inventoryUtils.ts` agregar `hasCsv(files: { name: string }[]): boolean` y la constante `CSV_NOTICE` con el texto de T019; crear `web/admin/src/modules/inventario/CsvNotice.tsx` (`Notice` de `components/Notice.tsx` con tono `warn`, el texto y un botón `Cerrar`, accesible con teclado); en `web/admin/src/modules/inventario/InventarioPage.tsx` mantener un estado `csvNotice` que pasa a verdadero cuando entre los archivos elegidos (`onChange` del `<input type="file">`) o soltados (`dropFiles`) hay un `.csv` según `hasCsv`, mostrar `CsvNotice` encima de la lista de subidas y cerrarlo con su botón; **no bloquea la subida**; pasan las pruebas de T019; correr `npm test` y `npx tsc --noEmit` en `web/admin/`
- [x] T022 [US5] En `scripts/cargar_carpeta.py` imprimir, una sola vez y antes de cargar, el aviso `Aviso: hay archivos CSV en la carpeta. Los CSV suelen traer datos de personas (cédulas, correos, teléfonos): quita o anonimiza esas columnas antes de cargarlos si no hacen falta.` cuando entre los archivos a cargar haya al menos un `.csv`; pasan las pruebas de T020

**Checkpoint**: US5 completa: las pruebas de `web/admin/` y `pytest tests/unit/test_csv_sin_datos_reales.py` pasan; con T021 y T022 el aviso aparece en el panel y en la carga por carpeta.

---

## Phase 7: User Story 4 - Archivos grandes: límites y avisos como en Excel (Priority: P2)

**Goal**: los mismos topes y avisos visibles que Excel, y protección ante archivos mal formados (celda gigante, comillas sin cerrar, muchas columnas).

**Independent Test**: un CSV con más filas que el tope queda `done` con la nota de recorte y la línea de aviso; uno con una celda de millones de caracteres no agota la memoria; uno con una comilla sin cerrar se lee con aviso.

### Tests for User Story 4 (primero, deben fallar)

- [x] T023 [P] [US4] Ampliar `tests/unit/test_csv_loader.py` con las pruebas de límites y robustez: (a) con `max_excel_rows = 100` (monkeypatch de `settings`) y 150 filas con contenido, el texto trae 100 líneas, `notes` tiene `El archivo se recortó en la fila 102 por superar el tope de 100 filas.` (el registro 1 es el encabezado, los registros 2 a 101 se escriben y el 102 es el primero que no cabe) y la última línea es `[Aviso: el archivo se recortó en la fila ... por superar el tope de 100 filas]`; con exactamente 100 filas no hay aviso; (b) con 201 columnas y contenido en la columna 201 se leen 200 y el aviso es `En el archivo se leyeron solo las primeras 200 columnas.`; (c) con `MAX_FILAS_VACIAS_SEGUIDAS` filas vacías seguidas y datos después, deja de leer y avisa `Se dejó de leer el archivo en la fila {n} tras 10000 filas vacías seguidas; si había datos después, no se ingestaron.`; (d) una celda de 50 000 caracteres se recorta a `MAX_CELDA_CARACTERES = 20000` y el aviso es `Se recortó 1 celda que superaba 20000 caracteres.`, y con 3 celdas largas `Se recortaron 3 celdas que superaban 20000 caracteres.`; una celda de 2 millones de caracteres (menor que `MAX_UPLOAD_MB`) no lanza `csv.Error` por el límite de campo del módulo y no deja ese límite cambiado después de leer (comprobar `csv.field_size_limit()` antes y después); (e) una comilla sin cerrar a mitad del archivo **no se traga el resto** en una celda: se lee sin interpretar comillas y el aviso es `El archivo tiene comillas sin cerrar: se leyó sin interpretarlas.`; (f) un archivo bien formado no produce ese aviso; (g) la lectura de un CSV de 5 000 filas termina en un tiempo comparable a la de un TXT de tamaño equivalente (comparar la mediana de 3 lecturas de cada uno con un margen holgado de 10 veces, para no depender de la máquina) (SC-005)
- [x] T024 [P] [US4] Ampliar `tests/unit/test_documents_csv.py`: un CSV con más filas que `max_excel_rows` queda `done` con `status_note` igual al aviso de recorte (máximo 500 caracteres) y la línea `[Aviso: ...]` indexada (como `test_un_libro_recortado_queda_listo_con_la_nota_y_el_aviso_indexado` de Excel); un CSV con comillas sin cerrar queda `done` con su nota; y la respuesta de `GET /domains/{id}/documents` trae la nota

### Implementation for User Story 4

- [x] T025 [US4] En `src/mia/ingestion/loaders/csv_loader.py` agregar la protección y los avisos de los límites: (1) la constante `MAX_CELDA_CARACTERES = 20000` y el recorte de cada celda más larga con un contador, y un aviso al final `se recortaron {n} celdas que superaban 20000 caracteres` (en singular `se recortó 1 celda que superaba 20000 caracteres` si es una); (2) subir `csv.field_size_limit` a `len(texto) + 1` solo mientras dura la lectura y **restaurarlo siempre** (`try/finally`), para que una celda grande no lance `csv.Error`; (3) la lectura **estricta** (`csv.reader(io.StringIO(texto, newline=""), ..., strict=True)`, como en T007): si lanza `csv.Error` (con `newline=""` solo ocurre por comillas sin cerrar o mal puestas, nunca por el fin de línea), repetir la lectura completa con `quoting=csv.QUOTE_NONE` y agregar el aviso `el archivo tiene comillas sin cerrar: se leyó sin interpretarlas`; (4) el aviso del tope de filas `el archivo se recortó en la fila {n} por superar el tope de {settings.max_excel_rows} filas` cuando `lineas_de_tabla` devuelve el corte, y pasar `objeto="el archivo"` para los avisos de columnas y de filas vacías; todos los avisos van a `self.notes` y al final del texto como `[Aviso: ...]` (R4, R5, R7). Pasan las pruebas de T023 y T024

**Checkpoint**: US4 completa: `pytest tests/unit/test_csv_loader.py tests/unit/test_documents_csv.py` pasa con los límites, los avisos y la protección.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: documentación, verificación y despliegue.

- [x] T026 [P] Actualizar `docs/ARQUITECTURA.md`: en la estructura del código, `tabular.py` (lógica de filas compartida por Excel y CSV) y `csv_loader.py` junto a `xlsx_loader.py`, y `DocumentLoader` con los cinco tipos (PDF, DOCX, TXT, XLSX y CSV); una sección corta de la ingesta de CSV con las decisiones de [research.md](research.md): codificación (BOM, UTF-8, Windows-1252, UTF-16 y bytes nulos son error, sin respaldo permisivo), separador por consistencia de columnas, comillas sin cerrar, tope de 20000 caracteres por celda, mismo texto de fila que Excel sin marca de hoja y los topes compartidos con `MAX_EXCEL_ROWS`
- [x] T027 [P] Actualizar `docs/OPERACION.md`: en "Cargar documentos (ingesta)" la lista de tipos aceptados (PDF, DOCX, TXT, XLSX y CSV) y **corregir la frase que dice que no se aceptan `.xls`, `.xlsm` ni `.csv`** (el CSV ahora sí); una viñeta "CSV" con cómo prepararlo (guardar desde Excel como «CSV (delimitado por comas)» o «CSV UTF-8»; la codificación y el separador se reconocen solos; las celdas multilínea se unen en una línea; la primera fila con al menos dos celdas es el encabezado), los límites compartidos con Excel (`MAX_EXCEL_ROWS` también vale para CSV, 200 columnas, 20000 caracteres por celda), los errores y avisos que se ven en el inventario y que **la «fila N» de un aviso cuenta registros del CSV, no líneas del archivo** (una celda con saltos de línea ocupa varias líneas y un solo registro); y el **aviso de datos personales** (un CSV suele traer cédulas, correos y teléfonos: quitar o anonimizar esas columnas antes de subirlo; lo que se suba se podrá consultar con los artefactos con acceso al dominio; la constitución exige control de acceso antes de exponer datos de personas en un artefacto público); anotar el despliegue (`./scripts/servicios.py encender MIA mia-panel`, sin migración); actualizar donde `docs/Definicion_Requerimientos_MVP.md` y `docs/Definicion_Requerimientos_V2.md` listen los tipos o digan que el CSV es una fuente futura (`grep -n -i "csv" docs/Definicion_Requerimientos_*.md`), dejando constancia de que la feature 021 lo resolvió
- [x] T028 Correr la verificación completa: `pytest` (toda la suite, sin regresiones: SC-008), `ruff check src tests scripts whatsapp`, y en `web/admin/`: `npm test` y `npx tsc --noEmit`; corregir lo que falle; comprobar que no quedó ningún guion largo en lo nuevo (`git diff --name-only` más `grep -c` con el carácter de guion largo (U+2014) sobre cada archivo tocado y sobre `specs/021-ingesta-csv/`) y que `git ls-files '*.csv'` no devuelve nada
- [x] T029 Recorrer el [quickstart.md](quickstart.md) en local: las secciones 1, 3 y 4 con la API y el panel (con el CSV que escribe `python tests/unit/csv_de_prueba.py <ruta>`, nunca con datos reales) y, si hay Qdrant y un modelo configurado, hacer las 20 preguntas de la sección 5 sobre un CSV inventado (SC-003; si no hay modelo o Qdrant en la máquina, anotarlo y dejarlo para T031); anotar el resultado y cualquier ajuste en `specs/021-ingesta-csv/quickstart.md` (sección "Resultado del recorrido") y marcar las tareas hechas en este archivo
- [x] T030 Comprobar con el archivo real, **solo en local y sin copiarlo**: ejecutar el fragmento de la sección 2 del quickstart sobre `~/Downloads/Proceso_2026_final(CANDIDATOS).csv` (imprime únicamente cantidades y banderas, nunca datos); esperado: unas 41 líneas, ningún aviso, sin `Ã` ni `�` y los encabezados presentes; anotar solo esos resultados (sin valores) en `specs/021-ingesta-csv/quickstart.md`; si algo difiere (otra cantidad de líneas, un aviso inesperado), corregir el cargador y sus pruebas con un caso **inventado** que reproduzca el problema

---

## Phase 9: Despliegue (lo hace el usuario)

- [ ] T031 [USUARIO] Revisar el diff de la feature en `dev`, hacer el merge a `main` y `git push origin main`; desplegar con `./scripts/servicios.py encender MIA mia-panel` (la API lee los CSV y el panel ofrece el tipo y el aviso; no hay migración ni cambios en las Consultas); comprobar `GET /health` y subir en un dominio de prueba un `.csv` **sin datos personales** (o el real, anonimizado), ver que queda `done` y hacer al menos 20 preguntas cuyo dato esté en filas del archivo (SC-003: al menos 90 % con el valor correcto y citando el archivo, si T029 no lo pudo medir); decidir si el archivo real, ya anonimizado, se agrega a un dominio

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 sin dependencias.
- **Foundational (Phase 2)**: T002 (pruebas) en paralelo con T001 (archivos distintos); T003 depende de T002 (la prueba dorada de Excel se fija **antes** de extraer) y bloquea todas las historias.
- **User Stories (Phase 3 en adelante)**: dependen de la Phase 2 completa.
  - **US1 (P1, MVP)**: T004, T005 y T006 en paralelo (archivos distintos); T007 depende de T003 y T001; T008 depende de T007; T009 y T010 en paralelo con T007 y T008.
  - **US2 (P1)**: depende de US1 (T007 crea `csv_loader.py`). T011 y T012 en paralelo; T013 depende de T011; T014 depende de T013 (mismo archivo); T015 al final.
  - **US3 (P1)**: depende de US1 y de T003; T016 y T017 en paralelo; T018 depende de T014 (mismo archivo) y de T016 y T017.
  - **US5 (P1)**: independiente del cargador (solo panel y script): T019 y T020 en paralelo; T021 depende de T010 (mismo archivo `InventarioPage.tsx` y `inventoryUtils.ts`); T022 depende de T009 (mismo script).
  - **US4 (P2)**: depende de US1 a US3 (mismo archivo `csv_loader.py`); T023 y T024 en paralelo; T025 depende de T018.
- **Polish (Phase 8)**: T026 y T027 en paralelo; T028 depende de todo lo anterior; T029 y T030 después de T028.
- **Despliegue (Phase 9)**: lo hace el usuario tras T028 a T030.

### Within Each User Story

- Las pruebas van primero y deben fallar antes de implementar.
- Las tareas que tocan el mismo archivo son **secuenciales**: `csv_loader.py` (T007, T013, T014, T015, T018, T025), `test_csv_loader.py` (T006, T011, T016, T023), `test_documents_csv.py` (T004, T012, T024), `inventoryUtils.ts` e `InventarioPage.tsx` (T010, T021), `cargar_carpeta.py` (T009, T022) y `tabular.py` (T003 solamente).

### Parallel Opportunities

- T001 y T002 (Setup y pruebas de la base).
- T004, T005 y T006 (pruebas de US1); T009 y T010 en paralelo con T007 y T008.
- T011 y T012 (pruebas de US2); T016 y T017 (pruebas de US3); T019 y T020 (pruebas de US5); T023 y T024 (pruebas de US4).
- T026 y T027 (documentación).

### Parallel Example: User Story 1

```text
Tarea: "T004 Pruebas de carga por la API en tests/unit/test_documents_csv.py"
Tarea: "T005 Actualizar el rechazo de tipos en tests/unit/test_documents_xlsx.py y tests/unit/test_loaders_base.py"
Tarea: "T006 Pruebas del cargador en tests/unit/test_csv_loader.py"
```

---

## Implementation Strategy

### MVP primero (US1 + US2 + US3 + US5)

1. Setup y Foundational (T001 a T003): el generador de archivos inventados y la lógica de filas compartida, con Excel sin cambios.
2. US1 (T004 a T010): el tipo se acepta por la API, el panel y los scripts.
3. US2 (T011 a T015): codificación y separador reconocidos solos; sin esto un CSV de Excel en español sale con letras rotas.
4. US3 (T016 a T018): la estructura de la tabla (celdas multilínea, columnas sin nombre, filas irregulares) y la equivalencia con Excel.
5. US5 (T019 a T022): el aviso de datos personales y la garantía de que el repositorio no lleva datos reales; no debe faltar en lo que se despliegue.
6. **Parar y validar** con las secciones 1 a 3 del quickstart y con T030 (el archivo real, solo en local).

### Entrega incremental

1. MVP: un CSV real de Excel en español se sube, se lee bien, se consulta y avisa de los datos personales.
2. + US4 (T023 a T025): límites, avisos y protección ante archivos mal formados; **recomendado antes del despliegue**, porque un archivo grande o con comillas sin cerrar es el riesgo operativo real.
3. Pulido y verificación (T026 a T030) y luego el usuario hace T031.

---

## Notes

- US1, US2, US3 y US5 son P1 en la spec; US4 es P2. El orden de las fases sigue la spec con US5 antes que US4 porque el aviso de datos personales es parte de lo que debe salir en la primera entrega.
- El **cargador de Excel no cambia de resultado**: la extracción de `tabular.py` (T003) se hace con una prueba dorada fijada antes (T002) y con todas las pruebas de Excel intactas.
- Los textos de los avisos del CSV usan `objeto="el archivo"`, así que quedan como `En el archivo se leyeron solo las primeras 200 columnas.`; el contrato de [contracts/ingesta-csv.md](contracts/ingesta-csv.md) ya lo refleja.
- `[USUARIO]` no lo ejecuta quien implementa: ver las reglas arriba.

---

## Phase 10: Hallazgo con el archivo real (T030)

- [x] T032 Leer bien un archivo en Windows-1252 con algunas celdas en UTF-8, que mostró el archivo real en T030 (32 `Ã­` donde debía haber `í`): en `src/mia/ingestion/loaders/csv_loader.py`, `_decodificar` lee las secuencias que son una letra o un signo latino válido en UTF-8 como UTF-8 y el resto como Windows-1252 (`_windows1252_con_celdas_en_utf8`); `tests/unit/csv_de_prueba.py` gana `csv_con_codificaciones_mezcladas()` y `tests/unit/test_csv_loader.py` sus pruebas (un archivo mezclado se lee bien, uno solo en Windows-1252 con muchos símbolos no cambia); se anotó en la spec (caso borde) y en `research.md` R2 per US2 y SC-002 (partial)
