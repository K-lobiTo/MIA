# Modelo de datos: Ingesta de documentos CSV

**Sin cambios de esquema y sin migración.** La feature agrega un valor a un campo de texto existente y reutiliza otro campo. Decisiones y alternativas en [research.md](research.md) (R7 y R8).

## `documents` (sin cambios de esquema)

| Campo | Cambio |
|---|---|
| `source_type` (texto) | Gana el valor `csv`, junto a `pdf`, `docx`, `txt` y `xlsx`. Se deriva de la extensión del archivo, en minúsculas, igual que hoy. No hay una lista cerrada en la base. |
| `status_note` (texto, nulo, máximo 500 caracteres; migración `0013` de la feature 018) | Se reutiliza: guarda el motivo de un CSV en `error` (por ejemplo, una codificación que no se puede leer) o el aviso de un CSV `done` recortado o leído con una salvedad. Nunca contiene contenido del archivo. |
| `filename`, `file_hash`, `status`, `uploaded_at`, `domain_id`, `folder_id` | Sin cambios: la detección de duplicados por hash, el inventario y la eliminación completa funcionan igual que para los demás tipos. |

## Entidades que no se guardan

- **Archivo CSV**: llega como bytes, se guarda en la carpeta de cargas con el nombre `<id del documento>.csv` mientras se procesa y se lee con el cargador; no tiene tabla propia.
- **Fila de datos**: texto producido por el cargador (`Encabezado: valor | ...`), no una entidad guardada; lo guardado son los fragmentos y sus vectores, como con cualquier documento.

## Constantes del cargador (no son ajustes de configuración)

| Constante | Valor | Dónde | Uso |
|---|---|---|---|
| `MAX_CELDA_CARACTERES` | `20000` | `csv_loader.py` | Largo máximo de una celda; una más larga se recorta con aviso (R5) |
| Muestra para el separador | 64 * 1024 caracteres y 30 registros | `csv_loader.py` | R3 |
| `MAX_COLUMNAS` | `200` | `tabular.py` (antes en `xlsx_loader.py`) | Compartida con Excel (R1, R7) |
| `MAX_FILAS_VACIAS_SEGUIDAS` | `10000` | `tabular.py` | Compartida con Excel |

## Ajustes de configuración existentes que se reutilizan

| Ajuste | Valor inicial | Uso para el CSV |
|---|---|---|
| `MAX_EXCEL_ROWS` | `5000` (de 100 a 50000) | Filas con contenido antes de recortar con aviso; vale también para el CSV |
| `MAX_UPLOAD_MB` | `25` | Tamaño máximo del archivo, para todos los tipos |

## Transiciones de estado relevantes

El documento CSV pasa por los mismos estados que los demás: `pending`, `processing` y `done` o `error` (sin estados nuevos). Un archivo ilegible, vacío o sin contenido termina en `error` con su motivo en `status_note`; uno recortado o leído con una salvedad termina en `done` con el aviso en `status_note` y como línea `[Aviso: ...]` al final del texto.
