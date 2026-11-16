---

description: "Tareas de implementación de la feature 018: ingesta de documentos Excel (.xlsx) con un cargador nuevo, nota de estado en el documento y tope de filas"
---

# Tasks: Ingesta de documentos Excel

**Input**: Design documents from `specs/018-ingesta-excel/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/interfaces.md](contracts/interfaces.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. La feature agrega un lector de archivos con muchas reglas pequeñas (encabezados, formatos, recortes) que se rompen fácil y la spec fija criterios medibles (SC-002, SC-003, SC-005). Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Los libros de prueba **se arman con `openpyxl` en `tmp_path`** (no se guardan binarios `.xlsx` en el repositorio). Las pruebas de la API usan los fixtures de `tests/conftest.py` y el estilo de `tests/unit/test_upload.py`; las del pipeline, el de `tests/unit/test_ingestion_pipeline.py`. Vitest sin DOM (`renderToString`, funciones puras), como `web/admin/src/modules/inventario/TreeNode.test.tsx`.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md), precedidas por la base común. US1 (aceptar y consultar) y US2 (contexto de columnas) son el núcleo; US3 (valores) y US4 (hojas ocultas y tope de filas) completan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)
- **[USUARIO]**: lo hace el usuario, no quien implementa (despliegue, migración en producción y pruebas con libros reales)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. **No desplegar, no encender servicios de Railway, no cambiar variables de producción ni tocar la base de producción.** Eso lo hace el usuario (T027 a T029).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Una sola dependencia nueva: `openpyxl`** (en `pyproject.toml`). **Una sola migración, la `0013`**, aditiva y con `downgrade`. Sin cambios en `whatsapp/`, `web/consulta/` ni en el fragmentador (`src/mia/ingestion/chunker.py`) ni en el resto del pipeline posterior al texto.
- **Los cargadores de PDF, DOCX y TXT no cambian de comportamiento** (SC-005). Solo se les agrega, vía la clase base, el atributo `notes` vacío.
- **`status_note` nunca contiene contenido del libro** (ni valores de celdas ni nombres de columnas): solo los mensajes fijos de [contracts/interfaces.md](contracts/interfaces.md) con números y el nombre de la hoja.
- Los textos de [data-model.md](data-model.md), [research.md](research.md) y de los contratos mandan: cada restricción citada abajo entre comillas es literal de allí.
- Es un prototipo: lo más simple que cumpla la especificación. **No correr `ruff format` sobre carpetas enteras**, solo sobre los archivos nuevos.
- **Interfaz del panel**: antes de tocar `web/admin/` leer [web/admin/README.md](../../web/admin/README.md#interfaz-mantine) (componentes de Mantine con el tema de `src/theme.ts`, sin colores grises fuera de la paleta).

---

## Phase 1: Setup

**Purpose**: la dependencia y el ajuste de configuración.

- [X] T001 Agregar `"openpyxl>=3.1",` a la lista `dependencies` de `pyproject.toml` (junto a `python-docx>=1.1`) e instalarla en el entorno con `.venv/bin/pip install -e ".[dev]"`; comprobar con `.venv/bin/python -c "import openpyxl"` y que el `Dockerfile` instala desde `pyproject.toml` (no hay lista aparte que actualizar; si la hubiera, agregarla allí)
- [X] T002 [P] Agregar a `src/mia/config.py` el ajuste `max_excel_rows: int = Field(default=5000, ge=100, le=50000)` con un comentario en español de una o dos líneas ("filas con contenido que se leen por libro de Excel, sumando las hojas visibles, antes de recortar"), junto a `max_upload_mb`; documentar `MAX_EXCEL_ROWS` en `.env.example` (después de `MAX_UPLOAD_MB=25`) y en la tabla de ajustes de `docs/OPERACION.md` (junto a la fila de `MAX_UPLOAD_MB`, con el mismo formato: `5000` en las tres columnas de entorno, rango de 100 a 50000); prueba en `tests/unit/test_config.py`: el valor por defecto es 5000, `MAX_EXCEL_ROWS=99` y `MAX_EXCEL_ROWS=50001` impiden crear la configuración

**Checkpoint**: `pytest tests/unit/test_config.py` pasa.

---

## Phase 2: Foundational (bloquea todas las historias)

**Purpose**: la columna `status_note`, la interfaz del cargador con sus mensajes y el pipeline que los guarda. Sin esto ninguna historia puede informar un error o un recorte.

- [X] T003 Agregar a `Document` en `src/mia/storage/models.py` la columna `status_note: Mapped[str | None] = mapped_column(String, nullable=True, default=None)` con un comentario ("motivo de un estado `error` o aviso de un estado `done`; mensaje fijo, nunca contenido del libro; máximo 500 caracteres, se recorta al guardar"); crear `src/mia/storage/migrations/versions/0013_nota_de_estado_de_documento.py` (revisión `0013`, `down_revision = "0012"`, docstring en el estilo de la `0012`) que agrega la columna `status_note` (`String`, nula) a `documents` sin tocar ninguna otra tabla ni fila, y cuyo `downgrade` la quita (con `op.batch_alter_table` para que funcione en SQLite; anotar en la docstring que se pierden las notas y `alembic downgrade 0012`); cambiar `DESTINO = "0012"` a `"0013"` en `scripts/probar_migracion.py` (línea 36) y todas las aserciones `_revision(engine) == "0012"` de `tests/unit/test_migrations.py` a `"0013"` (hay varias: buscar con `grep -n '"0012"' tests/unit/test_migrations.py` y revisar también `grep -rn '"0012"' tests scripts`), salvo las que verifican explícitamente la propia revisión `0012` al subir o bajar; agregar a `tests/unit/test_migrations.py` pruebas de la `0013`: agrega la columna `status_note` nula, los documentos existentes quedan con `status_note` nulo, baja a `0012` y vuelve a subir sin perder datos
- [X] T004 [P] En `src/mia/ingestion/loaders/base.py`: agregar la excepción `class LoaderError(Exception)` con docstring ("falla con un mensaje pensado para la persona administradora") y, en `DocumentLoader`, un `__init__` que fije `self.notes: list[str] = []` ("avisos no fatales de la última lectura, vacío por defecto"); los cargadores existentes no cambian (heredan el `__init__`); prueba en `tests/unit/test_loaders_base.py` (archivo nuevo): `get_loader("pdf").notes == []`, dos cargadores creados por separado no comparten la lista y `get_loader("xyz")` sigue lanzando `ValueError("Tipo de fuente no soportado: xyz")`
- [X] T005 En `src/mia/ingestion/pipeline.py` (`_ingest_document`): al pasar a `processing` poner `document.status_note = None`; guardar el cargador en una variable (`loader = get_loader(document.source_type)`) y, tras `text = loader.load(path)`, juntar `loader.notes` en una sola nota (unidas con un espacio) para guardarla si el documento termina en `done`; capturar `LoaderError` **antes** del `except Exception` genérico, registrando con `logger.warning` (sin el contenido), poniendo `status = "error"` y `document.status_note = <mensaje de la excepción>`; toda nota se recorta a 500 caracteres ("Máximo 500 caracteres (se recorta al guardar)"); el `ValueError` de "sin texto extraíble" y las demás excepciones siguen igual (estado `error`, sin nota); pruebas en `tests/unit/test_ingestion_pipeline.py`, con un cargador falso registrado vía `monkeypatch` sobre `get_loader`: un `LoaderError("mensaje")` deja `status="error"` y `status_note="mensaje"`; un cargador con `notes=["aviso"]` deja `status="done"` y `status_note="aviso"`; reprocesar un documento limpia la nota anterior; una nota de 600 caracteres se guarda con 500
- [X] T006 [P] Exponer `status_note` en la API y el panel: agregar `status_note: str | None = None` a `DocumentOut` en `src/mia/api/routes/domains.py` y a `DocumentNode` en `src/mia/api/routes/inventory.py` (y `status_note=document.status_note` en `_document_node`), y `status_note?: string | null;` a `DocumentItem` en `web/admin/src/api/types.ts`; pruebas en `tests/unit/test_inventory.py` (o el archivo que ya pruebe el inventario: buscar con `grep -ln "image_count" tests/unit/*.py`): un documento con nota la devuelve en el inventario y uno sin nota devuelve `null`

**Checkpoint**: `pytest tests/unit/test_migrations.py tests/unit/test_ingestion_pipeline.py tests/unit/test_loaders_base.py tests/unit/test_probar_migracion.py` pasa y `npx tsc --noEmit` (en `web/admin/`) no da errores.

---

## Phase 3: User Story 1 - Subir un libro de Excel y consultarlo (Priority: P1) 🎯 MVP

**Goal**: un `.xlsx` se acepta por los cuatro caminos de entrada, se procesa con el flujo de estados de siempre y su contenido (hojas visibles, una línea por fila) se puede consultar y se cita como fuente; los formatos no soportados y los libros dañados, protegidos o vacíos fallan con un mensaje claro.

**Independent Test**: subir un `.xlsx` simple a un dominio (quickstart, sección 2), esperar el estado `done` y comprobar que el texto ingestado trae una línea por fila con el nombre de la hoja; subir un `.csv`, un `.xls` y un `.xlsm` (400 con los tipos aceptados) y un libro dañado (`error` con `status_note`).

### Tests for User Story 1 (primero, deben fallar)

- [X] T007 [P] [US1] Crear `tests/unit/test_xlsx_loader.py` con un ayudante `_libro(tmp_path, hojas)` que arma un `.xlsx` con `openpyxl.Workbook` (`hojas`: diccionario nombre de hoja a lista de filas) y lo guarda en `tmp_path`, y las pruebas básicas de `XlsxLoader().load(path)`: (a) cada fila con contenido de una hoja visible produce **una línea** que empieza con `[<hoja>]`, en el orden del libro; (b) las hojas se escriben una tras otra, cada una con una línea de título `## Hoja: <nombre>`; (c) las filas totalmente vacías no producen línea; (d) un archivo que no es un libro (un `.txt` renombrado a `.xlsx`, que da `BadZipFile`) y un libro cuyo XML de hoja se corrompe (armar un `.xlsx` válido y reescribir en el zip `xl/worksheets/sheet1.xml` con texto truncado) lanzan `LoaderError` con el mensaje `No se pudo leer el libro: el archivo está dañado o protegido con contraseña.`; (e) un libro sin celdas con contenido lanza `LoaderError` con `El libro no tiene hojas visibles con contenido.`; (f) con una fila de encabezados y una de datos, el texto contiene los valores de la fila de datos
- [X] T008 [P] [US1] Crear `tests/unit/test_documents_xlsx.py` con el estilo de `tests/unit/test_upload.py` (reusar su fixture `base` o copiar su forma): (a) subir `horarios.xlsx` (bytes de un libro real armado con `openpyxl`) responde 201, `source_type == "xlsx"` y guarda el archivo como `{id}.xlsx`; (b) subir `datos.csv`, `datos.xls` y `datos.xlsm` responde 400 con `Tipo de fuente no soportado: <ext>. Tipos aceptados: pdf, docx, txt, xlsx.`; (c) subir el mismo libro dos veces al mismo dominio responde 200 con `already_existed: true` la segunda vez; (d) con `settings.ingestion_sync` verdadero y un libro dañado el documento queda en `error` con `status_note` "dañado o protegido con contraseña"; (e) con un libro válido queda en `done` con `status_note` nulo; (f) con `monkeypatch.setattr(settings, "max_upload_mb", 1)` y un `.xlsx` mayor de 1 MB (por ejemplo, rellenado con cadenas largas) responde 413 con el mensaje de tamaño máximo y no deja archivo en el directorio de cargas; (g) tras subir un `.xlsx` válido, eliminar el documento con la ruta de eliminación existente borra el archivo `{id}.xlsx` del directorio de cargas (FR-009); (h) la ruta de carga rechaza un `.xlsm` y el cargador nunca lee macros (documentar en un comentario que `read_only=True` no las ejecuta, FR-011)
- [X] T009 [P] [US1] Agregar a `web/admin/src/modules/inventario/inventoryUtils.test.ts` (o el archivo que pruebe `validateFile`: buscar con `grep -ln validateFile web/admin/src/modules/inventario/*.test.*`): `validateFile({ name: "Horarios.XLSX", size: 1000 }, 25)` devuelve `null`; `datos.csv`, `datos.xls` y `datos.xlsm` devuelven el mensaje `Solo se aceptan archivos PDF, DOCX, TXT y XLSX.`; y en `TreeNode.test.tsx`: una fila con `status: "error"` y `status_note: "No se pudo leer el libro: el archivo está dañado o protegido con contraseña."` muestra ese texto en el HTML renderizado, una fila con `status: "done"` y nota de recorte también muestra la nota, una fila sin nota no muestra nada extra

### Implementation for User Story 1

- [X] T010 [US1] Crear `src/mia/ingestion/loaders/xlsx_loader.py` con `class XlsxLoader(DocumentLoader)`: abrir con `openpyxl.load_workbook(path, read_only=True, data_only=True)` y **leer todo el libro dentro del mismo `try`** (abrir e iterar las hojas y las filas; cerrar siempre con `wb.close()` en `finally`); cualquier `Exception` durante esa lectura (`zipfile.BadZipFile`, `openpyxl.utils.exceptions.InvalidFileException`, `KeyError`, `OSError`, un XML de hoja corrupto a mitad de la lectura, etc.), salvo el propio `LoaderError` de "sin contenido" que se lanza fuera del `try`, se convierte en `LoaderError("No se pudo leer el libro: el archivo está dañado o protegido con contraseña.")` con `from None` (para no filtrar detalles); recorrer `wb.worksheets` en orden y, por cada hoja, escribir `## Hoja: <título>` y luego una línea por fila con contenido: `[<título>] ` seguido de los valores de las celdas no vacías unidos con ` | ` (por ahora los textos con `str(valor).strip()`, sin encabezados: eso es US2), ignorando filas sin ninguna celda con contenido; omitir del texto la línea `## Hoja: ...` de las hojas sin filas con contenido; si al final no hay ninguna fila con contenido en todo el libro, lanzar `LoaderError("El libro no tiene hojas visibles con contenido.")`; devolver el texto unido con `\n`. Docstring de módulo en español que cite [research.md](research.md) R1 a R3
- [X] T011 [US1] En `src/mia/ingestion/loaders/base.py`, agregar a `get_loader` la rama `if source_type == "xlsx":` con importación diferida de `XlsxLoader` (mismo patrón que las demás); en `src/mia/api/routes/domains.py` (línea ~192) cambiar el conjunto a `{"pdf", "docx", "txt", "xlsx"}` y el mensaje a `f"Tipo de fuente no soportado: {source_type}. Tipos aceptados: pdf, docx, txt, xlsx."`; revisar con `grep -rn '"docx"' src` que no haya otra lista de tipos por actualizar (la eliminación de la feature 012 usa `source_type` para formar el nombre, no requiere cambios)
- [X] T012 [P] [US1] En `scripts/cargar_carpeta.py` cambiar `TIPOS` a `{".pdf", ".docx", ".txt", ".xlsx"}` y, en la línea del filtro (alrededor de la 117, `and p.suffix.lower() in TIPOS`), agregar `and not p.name.startswith("~$")` (los temporales que Excel crea mientras el libro está abierto; comentario en una línea); en `scripts/reorganizar_v2.py` cambiar `TIPOS` igual (línea 38) y omitir también los nombres que empiecen con `~$` en el filtro de la línea ~63; si alguno de los dos tiene una prueba en `tests/unit/`, ampliarla (buscar con `grep -ln "cargar_carpeta\|reorganizar_v2" tests/unit/*.py`)
- [X] T013 [P] [US1] En el panel: agregar `".xlsx"` a `ALLOWED_EXTENSIONS` de `web/admin/src/modules/inventario/inventoryUtils.ts`, cambiar el mensaje de `validateFile` a `Solo se aceptan archivos PDF, DOCX, TXT y XLSX.` (y los textos de prueba que lo repitan: `grep -rn "PDF, DOCX y TXT" web/admin/src`), y el `accept` de `web/admin/src/modules/inventario/InventarioPage.tsx` (línea ~280) a `".pdf,.docx,.txt,.xlsx"`; en `TreeNode.tsx` (`DocumentRow`), cuando `document.status_note` existe (en `error` **y** en `done`, para que el aviso de recorte sea visible), mostrarla siempre como texto visible en una línea bajo la fila, nunca solo como `title` (un `<span className="doc-note">` con las clases del módulo, sin colores grises fuera de la paleta; leer [web/admin/README.md](../../web/admin/README.md#interfaz-mantine) antes); correr `npm test` y `npx tsc --noEmit` en `web/admin/`

**Checkpoint**: US1 completa: `pytest tests/unit/test_xlsx_loader.py tests/unit/test_documents_xlsx.py` y las pruebas del panel pasan; la sección 2 y la 3 del quickstart (formatos no soportados, libro dañado) funcionan a mano.

---

## Phase 4: User Story 2 - Las filas conservan el significado de sus columnas (Priority: P1)

**Goal**: cada valor queda acompañado del encabezado de su columna y del nombre de su hoja, de modo que una fila sola (o un fragmento que la contenga) sea autosuficiente.

**Independent Test**: un libro con encabezados en la fila 1 produce líneas `[Cursos] Código: MC4001 | Nombre: ...`; uno con un título arriba conserva el título y detecta los encabezados más abajo; las celdas combinadas no repiten el valor (quickstart, sección 2).

### Tests for User Story 2 (primero, deben fallar)

- [X] T014 [P] [US2] Ampliar `tests/unit/test_xlsx_loader.py` con: (a) hoja `Cursos` con encabezados `Código | Nombre | Créditos` y dos filas de datos produce exactamente `[Cursos] Código: MC4001 | Nombre: Redes | Créditos: 3` y la segunda fila análoga, sin línea para la de encabezados; (b) las celdas vacías de una fila de datos no producen par `Encabezado: ` (se omiten); (c) una hoja con una fila de título de una sola celda arriba (`Horarios 2027`) y los encabezados en la fila 3 produce `[Hoja] Horarios 2027` y luego los pares con los encabezados de la fila 3; (d) una hoja de una sola columna (sin fila con dos celdas con contenido) produce `[Hoja] valor` por fila; (e) un encabezado vacío en la columna D produce el nombre `Columna D`; (f) un encabezado repetido (`Nombre` en B y en E) produce `Nombre` y `Nombre (E)`; (g) un libro con dos hojas no mezcla: cada línea lleva el prefijo de su propia hoja y los encabezados de la suya; (h) una celda combinada (`ws.merge_cells`) aporta su valor una sola vez, sin repetirlo en las demás columnas combinadas; (i) tildes, eñes y saltos de línea dentro de una celda se conservan (el salto de línea se reemplaza por un espacio)

### Implementation for User Story 2

- [X] T015 [US2] En `src/mia/ingestion/loaders/xlsx_loader.py` reemplazar la salida simple por la de [research.md](research.md) R2 y R3, con una función por hoja (`_lineas_de_hoja(ws) -> list[str]`) y una pequeña función `_nombres_de_columnas(fila) -> list[str]`: (1) leer las filas con `ws.iter_rows(values_only=True)` llevando el número de fila; (2) las filas con contenido **anteriores** a la fila de encabezados se escriben como `[<hoja>] <valores unidos con " | ">`; (3) la **fila de encabezados** es la primera con "al menos **dos** celdas con contenido"; si ninguna fila cumple, no hay encabezados y cada fila va como `[<hoja>] <valor>`; (4) columnas con encabezado vacío se nombran `Columna <LETRA>` (usar `openpyxl.utils.get_column_letter`); un encabezado repetido conserva el primero y agrega ` (<LETRA>)` a los siguientes; (5) cada fila de datos es `[<hoja>] <Encabezado>: <valor> | ...`, omitiendo las celdas vacías y las filas sin ninguna celda con contenido; las celdas combinadas ya llegan vacías salvo la superior izquierda en modo de solo lectura (anotarlo en un comentario); (6) los saltos de línea dentro de un valor se reemplazan por un espacio. Pasan T007 y T014

**Checkpoint**: US1 y US2 funcionan juntas: el libro de ejemplo de la sección 2 del quickstart produce las líneas con encabezados y la pregunta por los créditos de un curso encuentra la fila correcta.

---

## Phase 5: User Story 3 - Fórmulas, fechas y números se leen como los ve la persona (Priority: P2)

**Goal**: el texto trae el resultado de las fórmulas, las fechas legibles y los porcentajes y enteros limpios, nunca la expresión de la fórmula ni un número de serie.

**Independent Test**: un libro con una fórmula (con resultado guardado), una fecha y un porcentaje produce `85%`, `15/03/2027` y el resultado de la fórmula (quickstart, sección 2, paso 4).

### Tests for User Story 3 (primero, deben fallar)

- [X] T016 [P] [US3] Ampliar `tests/unit/test_xlsx_loader.py` con pruebas de la función de formato (importarla como `from mia.ingestion.loaders.xlsx_loader import _texto_de_celda`) según la tabla de [research.md](research.md) R4: cadena con espacios en los extremos se recorta; `datetime(2027, 3, 15)` produce `15/03/2027`; `datetime(2027, 3, 15, 14, 30)` produce `15/03/2027 14:30`; `date(2027, 3, 15)` produce `15/03/2027`; `0.85` con formato `0%` produce `85%` y `0.125` con formato `0.0%` produce `12.5%`; `3.0` produce `3`; `3.5` produce `3.5`; `1250000` produce `1250000`; `True` produce `Sí` y `False` produce `No`; `None`, `""` y cadenas de error de Excel (`#DIV/0!`, `#N/A`, `#REF!`, `#VALUE!`, `#NAME?`, `#NUM!`, `#NULL!`) devuelven `None` (se omiten); y una prueba de libro completo: una fórmula `=SUM(B2:B3)` guardada **con** resultado cacheado produce el número (`openpyxl` no guarda resultados de fórmulas, así que el método es fijo: escribir el libro con `openpyxl` con la celda `=SUM(B2:B3)`, y con `zipfile` reescribir `xl/worksheets/sheet1.xml` insertando `<v>5</v>` dentro de la celda `<c>` que tiene `<f>`; la lectura con `data_only=True` debe devolver `5`; además, una prueba de la política con una celda de fórmula **sin** `<v>`: queda omitida y el resto de la hoja se lee bien)

### Implementation for User Story 3

- [X] T017 [US3] En `src/mia/ingestion/loaders/xlsx_loader.py` agregar `_texto_de_celda(valor, formato: str) -> str | None` con exactamente las reglas de la tabla de R4 (cadena recortada; `datetime` y `date` como `dd/mm/aaaa` y `dd/mm/aaaa hh:mm` si la hora no es medianoche; número con formato de porcentaje, es decir, un `number_format` que contenga `%`, como `valor * 100` redondeado a 10 decimales y sin ceros finales más el signo `%`; número decimal sin parte fraccionaria como entero; booleano como `Sí` / `No`; `None`, cadena vacía y cadenas de error de Excel devuelven `None`); usarla en `_lineas_de_hoja` leyendo las celdas con `ws.iter_rows()` (no `values_only`) para tener `cell.number_format` (en modo de solo lectura las celdas vacías de relleno son `EmptyCell`: tratarlas como vacías); sustituir en T015 el `str(valor).strip()` por esta función. Pasan T007, T014 y T016

**Checkpoint**: US1 a US3 funcionan; el recorrido manual de la sección 2 del quickstart (paso 4) muestra la fórmula como resultado y la fecha legible.

---

## Phase 6: User Story 4 - Libros grandes y hojas que no aportan información (Priority: P3)

**Goal**: las hojas ocultas y de gráfico no se ingestan, y un libro más grande que el tope de filas se recorta con aviso visible (nunca en silencio) en lugar de agotar los límites del entorno.

**Independent Test**: un libro con una hoja oculta, una de gráfico y otra con más filas que `MAX_EXCEL_ROWS` queda `done` sin las hojas ocultas ni los gráficos, con `status_note` de recorte y una línea de aviso al final del texto (quickstart, sección 3, fila "Recorte").

### Tests for User Story 4 (primero, deben fallar)

- [X] T018 [P] [US4] Ampliar `tests/unit/test_xlsx_loader.py` con: (a) una hoja con `ws.sheet_state = "hidden"` y otra con `"veryHidden"` no aparecen en el texto (ni su título ni sus filas) y los datos de las hojas visibles sí; (b) un libro con una hoja de gráfico se lee sin falla y esa hoja no aparece en el texto (armarla con un gráfico real: `cs = wb.create_chartsheet("G")`, `grafico = BarChart()`, `grafico.add_data(Reference(hoja, min_col=1, min_row=1, max_row=3))`, `cs.add_chart(grafico)`; un chartsheet **vacío** hace fallar a `openpyxl` al leer, comprobado, y no representa un libro real); (c) un libro cuyas hojas visibles están todas vacías y tiene otra hoja oculta con datos lanza `LoaderError` con `El libro no tiene hojas visibles con contenido.`; (d) con `monkeypatch.setattr(settings, "max_excel_rows", 100)` (o el nombre que use el módulo para leer el ajuste) y un libro de 300 filas, el texto tiene 100 líneas de datos, **termina** con la línea `[Aviso: el libro se recortó en la fila N de la hoja "X" por superar el tope de 100 filas]` (con `N` la fila de la hoja donde se cortó) y `loader.notes` contiene `El libro se recortó en la fila N de la hoja "X" por superar el tope de 100 filas.`; (e) el tope cuenta las filas de **todas** las hojas visibles juntas (dos hojas de 80 filas con tope 100: se lee la primera entera y 20 de la segunda); (f) un libro con exactamente el tope de filas **no** se recorta ni deja nota; (g) `loader.notes` queda vacío en un libro que no se recorta
- [X] T019 [P] [US4] Agregar a `tests/unit/test_documents_xlsx.py`: con `settings.ingestion_sync` verdadero, `max_excel_rows = 100` y un libro de 300 filas, el documento queda en `done` con `status_note` que empieza con `El libro se recortó en la fila` y los fragmentos indexados (con el almacén falso de `tests/unit/almacen_falso.py` o el que use `test_ingestion_pipeline.py`) incluyen la línea de aviso

### Implementation for User Story 4

- [X] T020 [US4] En `src/mia/ingestion/loaders/xlsx_loader.py`: (1) omitir las hojas con `ws.sheet_state != "visible"` (cubre `hidden` y `veryHidden`; las hojas de gráfico no están en `wb.worksheets`, comentar por qué); (2) contar las filas con contenido que se escriben (títulos previos y filas de datos, no la fila de encabezados) y, al llegar a `settings.max_excel_rows` ("5000", de 100 a 50000), dejar de leer **todas** las hojas restantes, terminar el texto con la línea `[Aviso: el libro se recortó en la fila <N> de la hoja "<X>" por superar el tope de <M> filas]` y agregar a `self.notes` el texto `El libro se recortó en la fila <N> de la hoja "<X>" por superar el tope de <M> filas.` (`N` es el número de fila de la hoja donde se cortó, `X` el título de la hoja y `M` el tope); solo se recorta si **existe** al menos una fila más con contenido después del tope (un libro con exactamente el tope de filas no se recorta); (3) limpiar `self.notes` al inicio de cada `load`. Pasan T018 y T019

**Checkpoint**: las cuatro historias funcionan; todo el quickstart se puede recorrer.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentación, verificación de regresiones y recorrido final.

- [X] T021 [P] Actualizar `docs/ARQUITECTURA.md`: agregar el cuarto tipo de fuente (`xlsx`) donde se listan los cargadores y los tipos aceptados, describir el formato del texto de un libro (una línea por fila con `[Hoja] Encabezado: valor`, hojas ocultas fuera, tope `MAX_EXCEL_ROWS`), la columna `status_note` de `documents` (migración `0013`) y la interfaz `DocumentLoader` con `notes` y `LoaderError`; actualizar la línea de **Ingesta** (alrededor de la 208) para que mencione `xlsx` y el error con nota
- [X] T022 [P] Actualizar `docs/OPERACION.md`: en la sección de carga de documentos (alrededor de la línea 374) mencionar que se aceptan PDF, DOCX, TXT y XLSX y cómo se comporta un libro (una línea por fila con sus encabezados, hojas ocultas ignoradas, recorte en `MAX_EXCEL_ROWS` con aviso visible en el inventario); agregar la nota del despliegue de la migración `0013` ("Desplegar cambios", regla de no desplegar una versión con menos migraciones que las de la base) y la recomendación de guardar los libros en Excel antes de subirlos para que las fórmulas tengan su resultado calculado
- [X] T023 [P] Actualizar `docs/Definicion_Requerimientos_MVP.md` (la tabla de entidades, `source_type (pdf/docx/txt)` pasa a `pdf/docx/txt/xlsx`, línea ~86; y la línea de procesamiento de documentos, ~124, para mencionar `openpyxl` para XLSX) y `docs/ESCALABILIDAD.md` con una nota breve sobre el riesgo aceptado de archivos `.xlsx` maliciosos (bomba de compresión) de [research.md](research.md) R8, a revisar si se abre la carga a más personas; si `README.md` o `web/admin/README.md` listan los tipos aceptados, actualizarlos (`grep -rn "DOCX" README.md web/admin/README.md docs/*.md`)
- [X] T024 Correr la verificación completa: `pytest` (toda la suite, sin regresiones en los cargadores de PDF, DOCX y TXT ni en el pipeline: SC-005), `ruff check src tests scripts whatsapp`, y en `web/admin/`: `npm test` y `npx tsc --noEmit`; corregir lo que falle; comprobar que no quedó ningún guion largo en lo nuevo (`git diff --name-only` más `grep -c $'\u2014'` sobre cada archivo tocado y sobre `specs/018-ingesta-excel/`)
- [X] T025 Recorrer el [quickstart.md](quickstart.md) de punta a punta en local con Qdrant local (secciones 1 a 5: libro con fórmula y hoja oculta, formatos no soportados, libro dañado, vacío y con contraseña, recorte con `MAX_EXCEL_ROWS=100`, duplicado, panel y carga por carpeta con un `~$temporal.xlsx`); anotar el resultado y cualquier ajuste en `specs/018-ingesta-excel/quickstart.md` (sección "Resultado del recorrido") y marcar las tareas hechas en este archivo
- [X] T026 Medir SC-002 y SC-004: armar un conjunto de al menos 20 preguntas con su valor esperado sobre uno o dos libros de ejemplo (horarios, cursos, costos; pueden ser sintéticos, el dato se considera público para pruebas), ingestarlos con `EMBEDDING_PROVIDER=local` en una colección temporal y comprobar cuántas se responden con el valor correcto y citan el libro; registrar el resultado (porcentaje y las que fallaron con su causa probable) en `specs/018-ingesta-excel/quickstart.md`; si baja de 90%, anotar si el corte de filas largas entre fragmentos (riesgo de [plan.md](plan.md)) es la causa; medir también SC-004: ingestar un libro sintético de 5000 filas y un PDF de tamaño equivalente en texto con el mismo proveedor de embeddings y anotar los dos tiempos (deben ser comparables)

---

## Phase 8: Despliegue y prueba con libros reales (lo hace el usuario)

- [ ] T027 [USUARIO] Revisar el diff de la feature en `dev` y hacer el merge a `main` y `git push origin main`
- [ ] T028 [USUARIO] Desplegar con `scripts/servicios.py encender` (API y panel): la API aplica la migración `0013` al arrancar; confirmar `GET /health`, y que el inventario del panel ofrece `.xlsx`
- [ ] T029 [USUARIO] Subir un libro real de la Coordinación (horarios, costos o lista de cursos) a un dominio de prueba y verificar en producción: estado `done`, una pregunta por un dato de una celda responde bien y cita el libro, y un libro dañado muestra el motivo en el inventario; si se usa la ingesta local, ingestar con `scripts/cargar_carpeta.py` apuntando a la colección de producción (ingesta local, ver `docs/OPERACION.md`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; T001 y T002 en paralelo.
- **Foundational (Phase 2)**: depende de T001 (las pruebas de las historias usan `openpyxl`); T002 solo hace falta desde US4. T003 (modelo y migración) bloquea T005 y T006. T004 y T006 son paralelas entre sí; T005 depende de T003 y T004.
- **User Stories (Phase 3 en adelante)**: dependen de la Phase 2 completa.
  - **US1 (P1)**: independiente; es el MVP. T010 y T011 son secuenciales (el factory importa la clase); T012 y T013 son paralelas a ellas.
  - **US2 (P1)**: depende de T010 (reemplaza la salida simple del mismo archivo).
  - **US3 (P2)**: depende de T015 (el formato se aplica dentro de la función de hoja).
  - **US4 (P3)**: depende de T015 y de T002 (el ajuste); toca el mismo archivo que US2 y US3, así que va después.
- **Polish (Phase 7)**: depende de las historias que se vayan a entregar; T021, T022 y T023 son paralelas.
- **Despliegue (Phase 8)**: lo hace el usuario tras T024 a T026.

### Within Each User Story

- Las pruebas van primero y deben fallar antes de implementar.
- Dentro de `xlsx_loader.py` las tareas T010, T015, T017 y T020 son **secuenciales** (mismo archivo).

### Parallel Opportunities

- T001 y T002 (Setup).
- T004 y T006 (Foundational), después de T003 para lo que dependa del modelo.
- T007, T008 y T009 (pruebas de US1, archivos distintos); T012 y T013 (scripts y panel) en paralelo con T010 y T011.
- T014, T016 y T018 modifican el mismo archivo de pruebas: hacerlas en orden, no en paralelo real, aunque se pueden escribir todas al inicio.
- T021, T022 y T023 (documentación).

### Parallel Example: User Story 1

```text
Tarea: "T007 Pruebas básicas del cargador en tests/unit/test_xlsx_loader.py"
Tarea: "T008 Pruebas de carga por API en tests/unit/test_documents_xlsx.py"
Tarea: "T009 Pruebas del panel en web/admin/src/modules/inventario/"
```

---

## Implementation Strategy

### MVP primero (US1)

1. Setup y Foundational (T001 a T006).
2. US1 (T007 a T013): un `.xlsx` se acepta, se procesa y se cita; los formatos no soportados y los libros dañados dan un mensaje.
3. **Parar y validar** con la sección 2 y 3 del quickstart. Aun sin encabezados, el texto por fila ya permite consultar libros simples, pero la calidad de las respuestas depende de US2: no desplegar el MVP sin US2.

### Entrega incremental

1. Base + US1 + US2: libros con encabezados consultables (entrega recomendada mínima).
2. + US3: fechas, porcentajes y fórmulas como los ve la persona.
3. + US4: hojas ocultas y tope de filas para libros reales grandes.
4. Polish y medición (T024 a T026), y luego el usuario hace T027 a T029.

---

## Notes

- Las dos primeras historias son las dos P1 de la spec porque solo juntas dan respuestas correctas: aceptar el archivo (US1) sin encabezados (US2) produce valores sin etiqueta.
- Las constantes de mensaje (`No se pudo leer el libro: ...`, `El libro no tiene hojas visibles con contenido.`, el aviso de recorte) se definen **una sola vez** como constantes del módulo `xlsx_loader.py` y las pruebas las importan.
- `[USUARIO]` no lo ejecuta quien implementa: ver las reglas arriba.

---

## Phase 9: Convergence

- [X] T030 Acotar en `src/mia/ingestion/loaders/xlsx_loader.py` la lectura de hojas con un área usada enorme (HIGH): hoy una celda con formato en `XFD50000` hace que la lectura tarde 92 s (medido el 2026-11-15) y una en `XFD1048576` mantendría la ingesta ocupada casi una hora; leer como máximo 200 columnas (`hoja.iter_rows(max_col=200)`, constante del módulo `MAX_COLUMNAS`) y dejar de leer una hoja tras 10000 filas vacías seguidas (constante `MAX_FILAS_VACIAS_SEGUIDAS`); pruebas en `tests/unit/test_xlsx_loader.py`: un libro con los datos en `A1:C3` y una celda con formato en `XFD50000` se lee en menos de 5 s con las mismas líneas que sin la celda lejana, y uno con 15000 filas vacías entre un bloque y un segundo bloque lee solo el primero sin falla; documentar el límite en la sección de libros de Excel de `docs/OPERACION.md` y en `research.md` (nueva decisión R9) per FR-008, US4 y SC-004 (partial)
- [X] T031 Resolver la rama que nombra por letra (`F: valor`) las celdas a la derecha del último encabezado en `_lineas_de_hoja` de `src/mia/ingestion/loaders/xlsx_loader.py`: documentarla en [research.md](research.md) R3 con una prueba que la alcance (una fila de datos más ancha que la de encabezados) o quitarla si no es alcanzable tras T030, per research R3 (unrequested)

---

## Phase 10: Convergence

- [X] T032 Avisar cuando el cargador deja contenido sin leer por los límites de T030 (HIGH), en `src/mia/ingestion/loaders/xlsx_loader.py`: hoy una celda con valor en la columna 250 o una fila con datos después de 10000 filas vacías seguidas se descartan sin ninguna nota (comprobado el 2026-11-15: el texto sale sin ellas y `notes == []`), contra FR-008 ("nunca recortar en silencio") y US4 escenario 3; leer una columna de más (`iter_rows(max_col=MAX_COLUMNAS + 1)`) y, si la celda de la columna `MAX_COLUMNAS + 1` de alguna fila tiene contenido, agregar a `self.notes` (una sola vez por hoja) `En la hoja "X" se leyeron solo las primeras 200 columnas.`; al cortar la hoja por `MAX_FILAS_VACIAS_SEGUIDAS` agregar `Se dejó de leer la hoja "X" en la fila N tras 10000 filas vacías seguidas; si había datos después, no se ingestaron.` (se avisa siempre que el corte ocurre, porque no se sabe sin leerlo); en ambos casos añadir también la línea `[Aviso: ...]` al final del texto, como el recorte por `MAX_EXCEL_ROWS`; pruebas en `tests/unit/test_xlsx_loader.py` de las dos notas y de que un libro normal no genera ninguna; corregir `docs/OPERACION.md` y [research.md](research.md) R9, que hoy dicen "ni se avisa", per FR-008 y US4/AC3 (contradicts)

---

## Phase 11: Convergence

- [X] T033 Alinear los contratos con las notas que hoy emite el cargador (LOW): agregar a la tabla "Mensajes fijos" de [contracts/interfaces.md](contracts/interfaces.md) las filas `done` / `En la hoja "X" se leyeron solo las primeras 200 columnas.` y `done` / `Se dejó de leer la hoja "X" en la fila N tras 10000 filas vacías seguidas; si había datos después, no se ingestaron.` (con el aviso `[Aviso: ...]` equivalente al final del texto, como el recorte por `MAX_EXCEL_ROWS`), y a la tabla de "Casos de error y recorte" de [quickstart.md](quickstart.md) los dos casos para probarlas a mano (un libro con contenido en la columna 201 y uno con 10000 filas vacías entre dos bloques), per plan: contratos y R9 (contradicts)
