# Contratos: Ingesta de documentos Excel

Los cambios son pequeños y compatibles hacia atrás: ninguna ruta nueva. Se listan las rutas y las interfaces internas que se tocan.

## 1. Carga de documentos (`POST /domains/{domain_id}/documents`)

Sin cambios en la forma de la petición. Cambia la validación del tipo:

| Caso | Respuesta |
|---|---|
| Extensión `pdf`, `docx`, `txt` o **`xlsx`** | Como hoy: se guarda y se procesa |
| Otra extensión (`xls`, `xlsm`, `csv`, ...) | `400` con `Tipo de fuente no soportado: <ext>. Tipos aceptados: pdf, docx, txt, xlsx.` |
| Archivo mayor que `MAX_UPLOAD_MB` | `413`, como hoy |

El libro no se abre durante la petición: la lectura, la validación del contenido y los recortes ocurren en el procesamiento en segundo plano, como con los demás tipos.

## 2. Objetos de documento (respuestas de la API)

Los objetos `DocumentOut` (carga, listado de un dominio) y el del inventario ganan un campo opcional:

```json
{
  "id": "…",
  "filename": "horarios-2027.xlsx",
  "source_type": "xlsx",
  "status": "done",
  "status_note": "El libro se recortó en la fila 5000 de la hoja \"Matrícula\" por superar el tope de 5000 filas."
}
```

`status_note` es `null` cuando no hay nada que informar. Los clientes que ignoran el campo siguen funcionando.

Mensajes fijos (todos en español, sin datos del libro):

| Situación | Estado | `status_note` |
|---|---|---|
| El archivo no se puede leer como libro (dañado o con contraseña) | `error` | `No se pudo leer el libro: el archivo está dañado o protegido con contraseña.` |
| Sin hojas visibles o sin celdas con contenido | `error` | `El libro no tiene hojas visibles con contenido.` |
| Se llegó a `MAX_EXCEL_ROWS` | `done` | `El libro se recortó en la fila N de la hoja "X" por superar el tope de M filas.` |
| Hay contenido más allá de la columna 200 de una hoja (una nota por hoja) | `done` | `En la hoja "X" se leyeron solo las primeras 200 columnas.` |
| Se dejó de leer una hoja tras 10000 filas vacías seguidas (se avisa siempre que ocurre) | `done` | `Se dejó de leer la hoja "X" en la fila N tras 10000 filas vacías seguidas; si había datos después, no se ingestaron.` |

Cada aviso de recorte o de lectura limitada también queda como línea `[Aviso: ...]` (con la misma frase, sin la mayúscula inicial ni el punto final) al final del texto, para que una respuesta no presente el libro como completo. Ver [research.md](research.md) R5 y R9.

## 3. Interfaz `DocumentLoader` (interna)

```python
class DocumentLoader(ABC):
    notes: list[str]  # avisos no fatales de la última lectura (vacío por defecto)

    @abstractmethod
    def load(self, path: Path) -> str: ...

class LoaderError(Exception):
    """Falla con un mensaje pensado para la persona administradora."""

def get_loader(source_type: str) -> DocumentLoader:  # agrega "xlsx" -> XlsxLoader
```

- `load` sigue devolviendo texto plano: el resto del pipeline (fragmentado, embeddings, Qdrant) no cambia.
- `get_loader` crea un cargador nuevo por documento, así `notes` no se comparte entre documentos.
- Los cargadores de PDF, DOCX y TXT no cambian.

## 4. Salida del cargador de Excel (formato de texto)

Ver R2 y R3 de [research.md](research.md). Ejemplo:

```text
## Hoja: Cursos
[Cursos] Código: MC4001 | Nombre: Blockchain y Libros Distribuidos | Créditos: 3 | Profesor: Ana Mora
[Cursos] Código: MC4002 | Nombre: Redes seguras | Créditos: 4 | Profesor: Luis Rojas
## Hoja: Calendario
[Calendario] Actividad: Matrícula | Inicio: 15/03/2027 | Cierre: 19/03/2027 | Avance: 85%
```

## 5. Panel (`web/admin/`)

- El selector de archivos y la validación aceptan `.xlsx`.
- La columna de tipo muestra `XLSX` (ya se calcula con `source_type.toUpperCase()`).
- El estado del documento muestra `status_note` como ayuda y, para los documentos en `error` o con aviso, en el detalle del inventario.
