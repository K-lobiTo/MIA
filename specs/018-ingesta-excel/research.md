# Research: Ingesta de documentos Excel

Cada decisión con su razón y lo descartado. Los datos de partida salen del código actual (`src/mia/ingestion/`, `src/mia/api/routes/domains.py`, `web/admin/src/modules/inventario/`) y de la spec.

## R1. Biblioteca: `openpyxl` en modo de solo lectura

**Decisión**: agregar `openpyxl>=3.1` a las dependencias de `pyproject.toml` y abrir el libro con `read_only=True, data_only=True`. Es Python puro (la única dependencia propia es `et-xmlfile`), sin extensiones compiladas, así que no cambia la imagen de Railway más que unos cientos de KB.

**Razón**:
- `data_only=True` entrega el último resultado guardado de las fórmulas, no la expresión (FR-005). Si el archivo nunca se calculó en Excel, la celda llega como `None` y se omite (US3, escenario 3).
- `read_only=True` recorre las hojas por flujo, sin cargar todo el libro en memoria (el servidor tiene unos 340 MB de RAM en reposo, ver `docs/OPERACION.md`), y no ejecuta nada del libro: las macros y los vínculos externos no se tocan (FR-011).
- En ese modo las celdas combinadas solo traen el valor en la celda superior izquierda y las demás vienen vacías, que es justo lo que pide FR-006 (el valor una sola vez).
- `wb.worksheets` no incluye las hojas de gráfico (están en `wb.chartsheets`) y cada hoja informa `sheet_state` (`visible`, `hidden`, `veryHidden`), lo que resuelve FR-004.

**Alternativas**:
- `pandas`: arrastra `numpy` (ya está) pero también `python-dateutil`, `pytz`, y obliga a materializar tablas enteras; añade peso para un uso que `openpyxl` resuelve solo.
- `xlrd`: ya no lee `.xlsx` desde la versión 2.
- `python-calamine`: más rápido, pero es una extensión en Rust y no entrega el formato de número (necesario para fechas y porcentajes).

## R2. Cómo se escribe el texto: una línea por fila, con la hoja y los encabezados en cada línea

**Decisión**: el cargador devuelve texto plano, una línea por fila de datos, con esta forma:

```text
[Cursos] Código: MC4001 | Nombre: Blockchain y Libros Distribuidos | Créditos: 3 | Profesor: Ana Mora
```

- El nombre de la hoja va **al inicio de cada línea**, no en un título aparte.
- Cada valor va como `Encabezado: valor`; las celdas vacías se omiten.
- Las hojas se escriben una tras otra, cada una con una línea de título (`## Hoja: Cursos`) que no depende del resto.

**Razón**: el fragmentador actual corta cada 1000 caracteres con 200 de traslape, sin mirar saltos de línea (`chunker.py`). Si el contexto (hoja y encabezado) estuviera solo en una línea de título, los fragmentos que no la contengan quedarían como "valores sin etiqueta" (US2). Con el contexto en cada fila, cualquier fragmento que contenga una fila entera es autosuficiente, y la búsqueda híbrida y la de significado encuentran el nombre de la columna y de la hoja en el mismo texto que el valor. El costo es repetir el encabezado en cada fila (más caracteres y más fragmentos), que con el tope de filas (R5) es aceptable.

**Alternativas**:
- Una tabla con las celdas separadas por ` | ` y los encabezados una sola vez (como el cargador de DOCX): ahorra caracteres pero pierde el significado fuera del primer fragmento. Descartada por US2.
- Cambiar el fragmentador para respetar filas: afecta a los otros tipos y a la regresión de SC-005; la spec pide no cambiar el procesamiento posterior al texto. Si una fila supera el traslape de 200 caracteres puede cortarse entre dos fragmentos; es un riesgo aceptado, ver "Riesgos" en `plan.md`.
- JSON por fila: más ruido para el modelo y para la búsqueda por palabras.

## R3. Encabezados: primera fila con al menos dos celdas con contenido

**Decisión** (por hoja):
1. Se lee la hoja en orden. Las filas previas a la fila de encabezados que tengan contenido (títulos, notas) se escriben como líneas de texto simple con el prefijo de la hoja, sin pares `encabezado: valor`.
2. La **fila de encabezados** es la primera con al menos **dos** celdas con contenido. Si ninguna fila lo cumple (hoja de una sola columna), no hay encabezados: cada fila se escribe como `[Hoja] valor`.
3. Las columnas con celda de encabezado vacía se nombran por su letra (`Columna D`). Un encabezado repetido conserva el primero tal cual y agrega la letra de columna a los siguientes (`Nombre`, `Nombre (E)`).
4. Las filas totalmente vacías no producen línea.

**Razón**: resuelve de forma determinista el borde de la spec ("título arriba, tabla más abajo") sin perder el título y sin un modelo. Una fila de título suele tener una sola celda con contenido; la de encabezados, varias.

**Alternativa descartada**: exigir que los encabezados estén en la fila 1. Rompe con libros reales de la Coordinación (la mayoría trae un título arriba).

## R4. Formato de los valores

**Decisión**: función única `_texto_de_celda(valor, formato_de_numero)` con estas reglas:

| Valor de la celda | Texto |
|---|---|
| Cadena | la cadena sin espacios en los extremos (se conservan los saltos de línea internos, reemplazados por un espacio) |
| Fecha u hora (`datetime`, `date`) | `dd/mm/aaaa`, y `dd/mm/aaaa hh:mm` si tiene hora distinta de cero |
| Número entero o decimal con formato de porcentaje | `85%` (se multiplica por 100 y se quita el ruido de coma flotante) |
| Número decimal sin parte fraccionaria (`3.0`) | `3` |
| Otro número | el número tal cual (`3.5`, `1250000`) |
| Booleano | `Sí` / `No` |
| Vacío (`None`) o cadena vacía | se omite |
| Error de Excel (`#DIV/0!`, `#N/A`) | se omite |

**Razón**: coincide con lo que se ve en la hoja en los casos que importan para consultas (fechas, porcentajes, enteros). Se descarta reproducir el símbolo de moneda y los separadores de miles: el formato de Excel es un mini lenguaje, y el encabezado de la columna ya suele llevar la unidad (`Costo (CRC)`). Es un matiz respecto al ejemplo de la spec (`₡1 250 000`): el valor se conserva exacto, solo no se reproduce la presentación. Queda en "Assumptions".

**Alternativa descartada**: interpretar el código de formato completo de Excel. Mucho código para un beneficio marginal en respuestas de texto.

## R5. Tope de filas y aviso

**Decisión**: nuevo ajuste `MAX_EXCEL_ROWS` (por defecto `5000`, mínimo 100 y máximo 50000), contado sobre las filas con contenido de todas las hojas visibles. Al llegar al tope el cargador **deja de leer**, el documento se ingesta con lo leído y queda una **nota** en el documento. El texto termina con una línea de aviso (`[Aviso: el libro se recortó en la fila N de la hoja X por superar el tope de 5000 filas]`) para que el modelo no presente el libro como completo.

El tamaño del archivo ya está acotado por `MAX_UPLOAD_MB` (25 MB, igual para todos los tipos). No se agrega un tope de tamaño propio del Excel.

**Razón**: 5000 filas es el volumen que fija SC-004; con unas 150 caracteres por fila son unos 750 mil caracteres, unos 940 fragmentos: cabe en la ingesta local. Recortar en vez de rechazar permite usar libros largos (listas de estudiantes) sin que el administrador tenga que partirlos, y el aviso (en la nota y en el texto) evita el recorte silencioso (FR-008).

**Alternativas**: rechazar el libro entero (más estricto, obliga a partir el archivo a mano); sin tope (arriesga el tiempo de ingesta y los 25 MB de un libro con muchas filas diminutas).

## R6. Cómo se informa un error o un recorte: nota en el documento

**Decisión**: columna nueva y opcional `documents.status_note` (migración aditiva `0013`) que guarda un texto corto en español. El panel la muestra junto al estado del documento (ayuda al pasar el cursor y en el detalle) y la API la expone en los mismos objetos de documento que ya devuelve. Para llenarla:
- `mia.ingestion.loaders.base` define una excepción `LoaderError(message)` para fallas con mensaje apto para personas (libro dañado, protegido o sin contenido). El pipeline la captura, marca el documento en `error` y guarda el mensaje.
- El `DocumentLoader` gana un atributo `notes: list[str]` (vacío por defecto); un cargador agrega avisos no fatales (como el recorte) y el pipeline los guarda como nota de un documento en estado `done`.
- Cualquier otra excepción sigue como hoy (estado `error`, detalle solo en el registro del servidor).

**Razón**: hoy un documento en `error` no dice por qué (`pipeline.py` solo registra la excepción). Sin ese texto, FR-007 y FR-008 ("mensaje comprensible", "avisar cuando recorta") no se pueden cumplir. Beneficia también a los demás tipos (PDF vacío, DOCX dañado) sin cambiar su comportamiento.

**Alternativas**:
- Solo el registro del servidor: la persona administradora no lo ve (incumple la spec).
- Bloquear el libro en la carga con un 4xx: obliga a abrir el libro dentro de la petición HTTP (lento para libros grandes y duplica la lectura). Se mantiene el 4xx solo para el tipo de archivo y el tamaño, que ya existen.
- Una tabla de eventos por documento: sobredimensionado para un texto corto.

**Despliegue**: la migración es aditiva (columna nula). Regla de `CLAUDE.md`: no desplegar una versión con menos migraciones que las de la base; esta es la `0013`.

## R7. Tipos aceptados: una sola lista y los cuatro caminos de entrada

**Decisión**: `domains.py` (carga por API y panel), `scripts/cargar_carpeta.py` y `scripts/reorganizar_v2.py` agregan `xlsx` a su lista. El factory `get_loader` agrega la rama `"xlsx"`. El panel agrega `.xlsx` a `ALLOWED_EXTENSIONS` y al atributo `accept`. `cargar_carpeta.py` además ignora los archivos temporales de Excel (`~$libro.xlsx`), que Excel crea mientras el libro está abierto y no son libros válidos. El rechazo de `.xls`, `.xlsm` y `.csv` ya ocurre por la lista (FR-002); se mejora el mensaje para listar los tipos aceptados.

**Razón**: los scripts son independientes de `mia` (usan solo `urllib`), por eso no comparten la constante; es el mismo trato que reciben hoy `pdf`, `docx` y `txt`.

## R8. Seguridad del archivo

**Decisión**: sin medidas nuevas más allá de R1. Solo la persona administradora (alcance global o del dominio) sube archivos, el tamaño ya está acotado, `openpyxl` en modo de lectura no ejecuta macros ni resuelve vínculos externos y el archivo se guarda con el id del documento, no con el nombre original.

**Riesgo aceptado**: un `.xlsx` malicioso (una bomba de compresión) podría consumir tiempo o memoria. No se trata aquí porque el actor es una persona administradora autenticada y el entorno es un prototipo de costo cero; `openpyxl` usa `defusedxml` si está instalado, y se deja anotado en `docs/ESCALABILIDAD.md` como punto a revisar si se abre la carga a más personas.
