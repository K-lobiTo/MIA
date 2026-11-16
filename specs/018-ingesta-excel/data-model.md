# Modelo de datos: Ingesta de documentos Excel

La feature no agrega entidades: agrega un tipo de fuente y una columna opcional al documento.

## Documento (existente, `documents`)

| Campo | Cambio | Descripción |
|---|---|---|
| `source_type` | valor nuevo `xlsx` | Junto a `pdf`, `docx` y `txt`. El archivo se guarda como `{id}.xlsx` en el directorio de cargas. |
| `status_note` | **nuevo**, `String`, nulo por defecto (migración `0013`) | Texto corto en español con el motivo de un estado `error` o un aviso de un estado `done` (por ejemplo, un libro recortado). Nulo cuando no hay nada que decir. |

Reglas:
- `status_note` se limpia al empezar un procesamiento (`pending` o `processing`) y se vuelve a escribir solo si el cargador o el pipeline tienen algo que informar.
- Máximo 500 caracteres (se recorta al guardar).
- No contiene contenido del libro (ni valores de celdas), solo mensajes fijos y números (filas, tope, nombre de la hoja).
- No se indexa ni se envía al modelo; solo la API y el panel lo leen.
- La eliminación completa de un documento (feature 012) ya borra el archivo `{id}.xlsx` porque usa `source_type` para formar el nombre (`removal.py`); no requiere cambios.

## Libro, hoja y fila (conceptuales, no persisten)

Solo existen durante la lectura del cargador; lo que persiste es el texto fragmentado en Qdrant, igual que para los demás tipos.

| Concepto | Qué es | Cómo se representa en el texto |
|---|---|---|
| Libro | Archivo `.xlsx` con una o más hojas | El documento completo |
| Hoja visible | Tabla con nombre, encabezados y filas | Línea `## Hoja: <nombre>` y, en cada fila, el prefijo `[<nombre>]` |
| Fila de encabezados | Primera fila con al menos dos celdas con contenido | No se escribe: sus textos se usan como etiquetas |
| Fila de datos | Valores de una fila, cada uno con su encabezado | `[Hoja] Encabezado: valor \| Encabezado: valor` |
| Filas previas a los encabezados | Títulos o notas arriba de la tabla | `[Hoja] texto` |

## Ajuste de configuración

| Ajuste | Valor por defecto | Rango | Uso |
|---|---|---|---|
| `MAX_EXCEL_ROWS` | `5000` | 100 a 50000 | Filas con contenido que se leen por libro (todas las hojas visibles juntas) antes de recortar |
