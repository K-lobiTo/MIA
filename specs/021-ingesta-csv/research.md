# Research: Ingesta de documentos CSV

Cada decisión con su razón y lo descartado. Los datos de partida salen del código actual (`src/mia/ingestion/loaders/xlsx_loader.py`, `base.py`, `pipeline.py`, `api/routes/domains.py`, scripts y panel), de la feature 018 y de pruebas hechas con la biblioteca estándar de Python y con la **forma** del archivo real de la persona dueña del proyecto (sin copiar ni mostrar sus datos).

## R1. Lógica de filas compartida con el cargador de Excel

**Decisión**: se extrae de `xlsx_loader.py` a un módulo nuevo, `src/mia/ingestion/loaders/tabular.py`, la parte que no depende del formato: la **fila de encabezados** (la primera con al menos dos celdas con contenido), los **nombres de columna** (`Columna <LETRA>` si está vacía y, si se repite, con la letra entre paréntesis), el tope de filas, el tope de columnas (`MAX_COLUMNAS = 200`), el corte por filas vacías seguidas (`MAX_FILAS_VACIAS_SEGUIDAS = 10000`), el formato de cada línea (`Encabezado: valor | ...`) y la generación de los avisos. La función recibe filas ya convertidas a texto, `(número de fila, lista de textos o None)`, un prefijo (`[Hoja] ` en Excel, vacío en CSV) y un `objeto` para redactar los avisos (`la hoja "X"` en Excel, `el archivo` en CSV); devuelve lo mismo que hoy devuelve `_lineas_de_hoja`. `XlsxLoader` pasa a llamarla con su prefijo `[Hoja] ` y `CsvLoader` con prefijo vacío.

**Razón**: el requisito FR-006 pide que el CSV y el Excel produzcan el mismo texto de fila (SC-006). Con dos copias de la regla se desviarían al primer cambio. La extracción es mecánica y el cargador de Excel ya tiene pruebas detalladas (`test_xlsx_loader.py`, `test_documents_xlsx.py`) que detectan cualquier cambio de resultado.

**Alternativas**: (a) copiar la lógica al cargador nuevo (más rápido, pero duplica unas 80 líneas y garantiza deriva); (b) que el CSV simule una hoja de `openpyxl` con `iter_rows` y celdas con `value` (acopla un cargador al otro y es frágil); (c) convertir el CSV a un `.xlsx` temporal y leerlo con `XlsxLoader` (más lento, gasta memoria y depende de `openpyxl` para escribir).

## R2. Reconocer la codificación

**Decisión**, en este orden, sobre los bytes del archivo (ya acotados por `MAX_UPLOAD_MB`):

1. **Marca de orden de bytes** de UTF-16 (`FF FE` o `FE FF`): error con la sugerencia de guardarlo como «CSV UTF-8» (es lo que produce Excel con «Texto Unicode»). Se rechaza de entrada porque UTF-16 no tiene separadores legibles como bytes.
2. **Bytes nulos** (`00`) en el archivo: no es texto (un `.xlsx` o un PDF renombrado a `.csv` los trae): error de lectura.
3. **UTF-8 estricto** (`utf-8-sig`, que descarta la marca de orden de bytes si existe): si decodifica, se usa. El texto en español que no es UTF-8 casi siempre falla esta prueba porque `é` en Windows-1252 es el byte suelto `E9`, que no es una secuencia UTF-8 válida.
4. **Windows-1252 estricto**, con una salvedad descubierta con el archivo real: casi todo el texto está en Windows-1252 pero **algunas celdas están en UTF-8** (se pegaron desde una página web antes de guardar), y leerlo todo como Windows-1252 deja `Ã­` en lugar de `í` en 32 lugares. Por eso, antes de decodificar, las secuencias de bytes que son una **letra o un signo latino válido en UTF-8** (letras con tilde, `¿`, comillas, guiones, euro) se leen como UTF-8 y el resto como Windows-1252. Un archivo solo en Windows-1252 no cambia, y ningún byte se inventa. Limitación conocida: un par de símbolos de Windows-1252 que, juntos, sean una letra válida de UTF-8 (por ejemplo `Ã` seguido de `±`) se lee como esa letra (`ñ`); en español esos pares no aparecen a propósito.
5. Si ninguna decodifica (hay bytes sin sentido, como `81`, `8D`, `8F`, `90` o `9D`, que Windows-1252 no define): **error** con el mensaje de lectura y la sugerencia. No se usa latin-1 de respaldo porque aceptaría cualquier cosa y produciría caracteres inventados (US2 escenario 3: "no se inventan caracteres").

**Razón**: cubre exactamente las dos codificaciones de la spec con una regla verificable. El orden UTF-8 primero es el estándar práctico de detección sin dependencias.

**Alternativas**: `charset-normalizer` o `chardet` (dependencia nueva que adivina por estadística y puede equivocarse con textos cortos; descartado por el costo cero y por la previsibilidad); probar latin-1 de respaldo (nunca falla, y por eso oculta archivos ilegibles); pedir la codificación a la persona (contradice US2: "sin pedirle nada").

## R3. Reconocer el separador

**Decisión**: sobre una **muestra** (los primeros 64 * 1024 caracteres, cortados en el último salto de línea, o todo el archivo si es menor), para cada candidato (`;`, `,`, tabulador, `|`) se leen los registros con el módulo `csv` (que respeta las comillas) y se calcula su **puntaje**: de los primeros 30 registros no vacíos, cuántos tienen **la misma cantidad de campos**, tomando la cantidad (de al menos 2) que más registros comparte; así una línea de título con menos campos no hace perder al separador correcto. Gana el candidato con mayor puntaje; los empates se resuelven por el orden `;`, `,`, tabulador, `|` (el punto y coma primero porque es lo que exporta Excel en español). Si ningún candidato llega a 2 campos, el archivo se lee como **una sola columna** y se deja un aviso (US2 escenario 4).

**Razón**: contar caracteres falla con comas dentro de textos en un archivo separado por punto y coma (muy común: direcciones, nombres), y `csv.Sniffer` se equivoca con celdas multilínea y con archivos de muchas columnas. La **consistencia del número de campos** es la señal que realmente distingue una tabla. Comprobado con el archivo real: con `;` los 45 registros tienen 29 campos; con `,` la lectura estricta ni siquiera termina.

**Alternativas**: `csv.Sniffer` (no robusto, ver arriba); fijar `;` (rompe los exportados por otros sistemas); contar apariciones del carácter en la primera línea (se confunde con comas dentro de textos).

## R4. Leer con el módulo `csv` y comillas sin cerrar

**Decisión**: se lee con `csv.reader` alimentado con `io.StringIO(texto, newline="")` (verificado: sin `newline=""` un archivo con fin de línea `\r` falla con `csv.Error` aunque esté bien formado; con él se leen igual `\r\n`, `\n` y `\r`), con el separador elegido y las comillas dobles (`"`), así que una celda entre comillas puede contener el separador y saltos de línea sin partir la fila (FR-004). Los fines de línea de Windows, Unix y Mac antiguo se leen igual. La lectura es **estricta** (`strict=True`): si el archivo tiene comillas sin cerrar o comillas mal puestas, el módulo lanza `csv.Error` (con `newline=""` esa es la única causa, así que el aviso no se confunde con otro problema); entonces se **reintenta sin interpretar comillas** (`quoting=csv.QUOTE_NONE`) y se agrega el aviso "el archivo tiene comillas sin cerrar; se leyó sin interpretarlas". Verificado: sin la lectura estricta una comilla sin cerrar se traga **todo el resto del archivo en una sola celda** sin avisar.

El límite de tamaño de campo del módulo (131 072 caracteres por defecto) se sube a un valor mayor solo mientras dura la lectura y se restaura después; el tope de memoria sigue siendo el tamaño del archivo (25 MB). Los campos mayores que el tope por celda de R5 se recortan con aviso.

**Razón**: cumple "se lee lo que se pueda y se avisa" (US4 escenario 4) sin quedar esperando ni agotar la memoria.

**Alternativas**: leer siempre sin comillas (parte mal las celdas multilínea, que el archivo real tiene 11); `pandas` o `polars` (dependencia nueva muy pesada para esto).

## R5. Tope de largo por celda

**Decisión**: una constante `MAX_CELDA_CARACTERES = 20000` en `csv_loader.py`. Una celda más larga se **recorta** a ese largo y se agrega el aviso "se recortaron N celdas que superaban 20000 caracteres" (una sola vez, con la cantidad). No es un ajuste de configuración: es una protección técnica sin razón para cambiarla.

**Razón**: FR-012 pide proteger la memoria y el tiempo ante una celda gigantesca. Aunque el archivo ya está acotado a 25 MB, una sola celda de ese tamaño produciría una línea enorme que el fragmentado y la vectorización procesarían como un bloque. 20 000 caracteres es mucho más que cualquier texto real de una celda (la carta motivacional de un candidato mide unos cientos) y no recorta nada en la práctica.

**Alternativas**: sin tope (la protección de memoria sería solo el tamaño del archivo); un ajuste de configuración (más superficie sin necesidad).

## R6. Mismo texto de fila que Excel, sin marca de hoja

**Decisión**: cada fila queda como `Encabezado: valor | Encabezado: valor | ...` con las mismas reglas que Excel (valores vacíos omitidos, columnas sin encabezado como `Columna <LETRA>`, encabezado repetido con la letra entre paréntesis, filas anteriores al encabezado como texto simple unido con ` | `). Se **omiten** el prefijo `[Hoja] ` de la línea y la línea `## Hoja: ...`, porque un CSV no tiene nombre de hoja y el cargador no conoce el nombre del archivo (la API lo guarda con el identificador del documento como nombre, `<uuid>.csv`). Los valores se conservan **como están escritos**: no se interpretan fechas ni números. Los saltos de línea dentro de una celda y los espacios repetidos se unen en un solo espacio (`" ".join(texto.split())`), igual que en Excel, para que una fila siga siendo una línea.

**Razón**: FR-006 y SC-006 piden el mismo formato; la única diferencia legítima es la marca de hoja. Los fragmentos siguen siendo autosuficientes porque cada valor lleva su encabezado y la respuesta cita el documento por su nombre de archivo.

**Alternativas**: usar el nombre del archivo como nombre de hoja (el cargador no lo conoce sin cambiar la interfaz `load(path)` para los cinco tipos); conservar los saltos de línea dentro de la celda (partiría la fila en varias líneas y el fragmentado las separaría).

## R7. Límites y avisos compartidos con Excel

**Decisión**: el CSV usa `settings.max_excel_rows` (filas con contenido, 5000 por defecto), `MAX_COLUMNAS` (200) y `MAX_FILAS_VACIAS_SEGUIDAS` (10000) tal cual, y el mismo mecanismo: el aviso va a `loader.notes` (que `pipeline.py` guarda en `documents.status_note`, máximo 500 caracteres) y como línea `[Aviso: ...]` al final del texto. Los textos de los avisos se adaptan al CSV: "el archivo se recortó en la fila N por superar el tope de X filas", "se leyeron solo las primeras 200 columnas". El ajuste conserva su nombre `MAX_EXCEL_ROWS`; la documentación aclara que también vale para CSV. No se crea un ajuste nuevo.

**Razón**: el comportamiento debe ser idéntico (FR-011); un solo tope es más fácil de operar. Renombrar la variable rompería los `.env` existentes.

**Alternativas**: `MAX_CSV_ROWS` aparte (dos números que mantener sin motivo); renombrar a `MAX_TABLE_ROWS` (rompe configuración existente sin beneficio).

## R8. Dónde se acepta el tipo

**Decisión**: se agrega `csv` en los lugares donde hoy se listan los tipos, sin crear una constante común nueva (son cuatro listas independientes, tres en Python y una en TypeScript):

| Lugar | Cambio |
|---|---|
| `base.py` `get_loader` | rama `"csv"` que devuelve `CsvLoader` |
| `api/routes/domains.py` | `{"pdf", "docx", "txt", "xlsx", "csv"}` y el mensaje "Tipos aceptados: pdf, docx, txt, xlsx, csv." |
| `scripts/cargar_carpeta.py` y `scripts/reorganizar_v2.py` | `TIPOS` con `.csv` |
| `web/admin/.../inventoryUtils.ts` | `ALLOWED_EXTENSIONS` y el mensaje "Solo se aceptan archivos PDF, DOCX, TXT, XLSX y CSV." |
| `InventarioPage.tsx` | `accept=".pdf,.docx,.txt,.xlsx,.csv"` |

El tipo del documento (`source_type`) ya es texto libre, y el inventario y los demás caminos (duplicados por hash, eliminación, fuentes) no distinguen tipos (FR-014). No hay migración.

**Razón**: es el mismo patrón que siguió la 018, sin abstracciones nuevas.

## R9. Aviso de datos personales

**Decisión**: en el panel, cuando entre los archivos elegidos o soltados haya al menos un `.csv`, se muestra un aviso **no bloqueante** (`Notice` de tono `warn`) encima de la lista de subidas, que se puede cerrar: "Los archivos CSV suelen traer datos de personas (cédulas, correos, teléfonos, direcciones). Lo que subas se podrá consultar con los artefactos que tengan acceso a este dominio: quita o anonimiza esas columnas antes de subirlo si no hacen falta." La lógica de si hay un CSV es una función pura (`hasCsv(files)`) en `inventoryUtils.ts`, con prueba. La misma advertencia y la forma de prepararlo van en `docs/OPERACION.md`. No hay detección automática de columnas con datos personales.

**Razón**: el riesgo es real y propio de este formato, pero detectar "qué es un dato personal" en columnas libres es poco fiable y puede dar una falsa tranquilidad; una advertencia clara y la decisión de la persona administradora es lo proporcionado. La constitución exige control de acceso antes de exponer datos sensibles en un artefacto público: ese control es el de los artefactos y no cambia.

**Alternativas**: bloquear la subida si hay una columna llamada `Cédula` o `Correo` (frágil y paternalista); pedir una confirmación (fricción en cada subida); no avisar (incumple FR-016).

## R10. Pruebas sin datos reales

**Decisión**: un generador de pruebas, `tests/unit/csv_de_prueba.py`, construye en memoria CSV **inventados** con parámetros: codificación (UTF-8 con y sin BOM, Windows-1252), separador, fin de línea, celdas con comillas y saltos de línea, líneas en blanco, columna sin encabezado, filas con más y menos celdas que el encabezado, una comilla sin cerrar y una celda gigantesca. Reproduce la estructura y los problemas del archivo real (29 columnas con la última sin nombre, 45 filas, 11 celdas multilínea, 3 filas vacías) con nombres y valores falsos (`Persona 01`, `correo01@ejemplo.test`). El archivo real queda **solo en la máquina de quien lo tiene**: se usa para una comprobación manual local (ver [quickstart.md](quickstart.md)) y nunca se copia al repositorio, a las pruebas ni a los registros.

**Razón**: FR-017 y SC-007. Un generador además cubre todas las combinaciones, que un archivo único no cubre.

## R11. Qué no cambia

- El fragmentado, los embeddings, el almacén vectorial, la búsqueda (híbrida, completa, barrido de secciones) y la respuesta: reciben texto como siempre.
- La interfaz `DocumentLoader` (`load(path)` y `notes`) y `LoaderError`.
- La API de carga, el estado de los documentos y `documents.status_note`.
- Los tipos PDF, DOCX, TXT y XLSX: el texto de un libro de Excel debe salir **idéntico** antes y después de extraer `tabular.py` (SC-008).
- No hay migración, ni dependencia nueva, ni variable de entorno nueva.
