# Contratos: ingesta de CSV

Los contratos de la API de carga no cambian en forma; solo el conjunto de tipos aceptados y los mensajes. Decisiones en [research.md](research.md).

## 1. Carga por API y panel

`POST /domains/{domain_id}/documents` (multipart, campo `file`; exige alcance de administración sobre el dominio, igual que hoy).

| Caso | Respuesta |
|---|---|
| Extensión `.csv` (sin importar mayúsculas) | Se acepta como los demás tipos: `201` con el documento (`source_type: "csv"`, `status: "pending"`) y se procesa en segundo plano; con el mismo contenido ya subido al dominio, `200` con `already_existed: true` |
| Extensión no aceptada (`.xls`, `.xlsm`, `.tsv`, `.ods`, otra) | `400` con `Tipo de fuente no soportado: {tipo}. Tipos aceptados: pdf, docx, txt, xlsx, csv.` |
| Archivo mayor que `MAX_UPLOAD_MB` | `413` con `El archivo supera el tamaño máximo de {n} MB.` (sin cambios) |
| Ingesta desactivada en la instancia | `503` (sin cambios) |

El resultado del procesamiento se ve en `GET /domains/{domain_id}/documents` y en el inventario: `status` y `status_note` (feature 018).

## 2. Cargador (interfaz interna)

```python
# mia/ingestion/loaders/base.py
def get_loader(source_type: str) -> DocumentLoader: ...   # "csv" devuelve CsvLoader

# mia/ingestion/loaders/csv_loader.py
class CsvLoader(DocumentLoader):
    def load(self, path: Path) -> str: ...    # texto del archivo; llena self.notes con los avisos; LoaderError ante un error

# mia/ingestion/loaders/tabular.py   (compartido con XlsxLoader)
def lineas_de_tabla(prefijo, objeto, filas, escritas, limite) -> tuple[list[str], int, int | None, list[str]]: ...
# prefijo: "[Hoja] " en Excel y "" en CSV; objeto: 'la hoja "X"' en Excel y 'el archivo' en CSV (para los avisos);
# filas: iterable de (número de fila, lista de textos o None)
```

`LoaderError(mensaje)` lleva un mensaje apto para personas que `pipeline.py` guarda como `status_note`; nunca contiene contenido del archivo ni detalles de la excepción.

## 3. Mensajes (errores y avisos)

| Caso | Tipo | Mensaje |
|---|---|---|
| Archivo vacío, solo líneas en blanco o solo la fila de encabezados | error | `El archivo CSV no tiene contenido.` |
| UTF-16 (marca de orden de bytes), bytes nulos, o bytes sin sentido en UTF-8 y en Windows-1252 | error | `No se pudo leer el archivo: no es un CSV de texto en UTF-8 ni en Windows-1252. Guárdalo de nuevo como «CSV UTF-8» y vuelve a subirlo.` |
| Más filas con contenido que `MAX_EXCEL_ROWS` | aviso (`done`) | `El archivo se recortó en la fila {n} por superar el tope de {max} filas.` |
| Más de 200 columnas con contenido | aviso (`done`) | `En el archivo se leyeron solo las primeras 200 columnas.` |
| Se dejó de leer por `10000` filas vacías seguidas | aviso (`done`) | `Se dejó de leer el archivo en la fila {n} tras 10000 filas vacías seguidas; si había datos después, no se ingestaron.` |
| Ningún separador reconocido (una sola columna) | aviso (`done`) | `No se reconoció un separador de columnas: se leyó como una sola columna.` |
| Comillas sin cerrar o mal puestas | aviso (`done`) | `El archivo tiene comillas sin cerrar: se leyó sin interpretarlas.` |
| Celdas que superan `MAX_CELDA_CARACTERES` | aviso (`done`) | `Se recortó 1 celda que superaba 20000 caracteres.` o `Se recortaron {n} celdas que superaban 20000 caracteres.` |

En los avisos del CSV, la «fila N» cuenta **registros** del archivo, no líneas: una celda con saltos de línea ocupa varias líneas y un solo registro.

Cada aviso también queda como línea `[Aviso: ...]` al final del texto, igual que en Excel, para que una respuesta no presente el archivo como completo.

## 4. Panel

- El selector de archivo ofrece `.pdf,.docx,.txt,.xlsx,.csv`; un archivo de otro tipo se rechaza antes de subirse con `Solo se aceptan archivos PDF, DOCX, TXT, XLSX y CSV.` (sin cambios de forma).
- Con al menos un `.csv` entre los archivos elegidos o soltados se muestra, una vez por tanda y con botón para cerrarlo, un aviso de tono `warn` sobre datos personales (texto en [research.md](research.md) R9). No bloquea la subida.
- El inventario muestra el tipo y la nota de estado como con los demás tipos; no hay pantallas nuevas.

## 5. Scripts

`scripts/cargar_carpeta.py` y `scripts/reorganizar_v2.py` incluyen `.csv` entre los tipos que recorren; `cargar_carpeta.py` imprime el aviso de datos personales una vez si carga algún `.csv`.
