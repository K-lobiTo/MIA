# Quickstart: validar la ingesta de Excel

Cómo comprobar la feature de punta a punta. Rutas y campos: [contracts/interfaces.md](contracts/interfaces.md). Formato del texto: [research.md](research.md) (R2 a R4).

## Preparación

```bash
source .venv/bin/activate
pip install -e ".[dev]"        # instala openpyxl, nueva dependencia
docker compose up -d qdrant
uvicorn mia.api.main:app --reload   # aplica la migración 0013 al arrancar
```

## 1. Pruebas automáticas

```bash
pytest tests/unit/test_xlsx_loader.py tests/unit/test_documents_xlsx.py   # cargador y carga por API
pytest                                                                    # sin regresiones (SC-005)
ruff check src tests scripts whatsapp
cd web/admin && npm test && npx tsc --noEmit                              # extensiones del panel
```

## 2. Recorrido manual (API)

1. Crear un libro de prueba con una hoja `Cursos` (Código, Nombre, Créditos, Profesor), una hoja oculta y una celda de fórmula (por ejemplo, `=SUM(...)` de los créditos). Guardarlo en Excel o LibreOffice para que las fórmulas queden calculadas.
2. Subirlo a un dominio:

   ```bash
   curl -H "X-Admin-Key: $ADMIN_KEY" -F "file=@cursos.xlsx" http://localhost:8000/domains/<id>/documents
   ```

   Esperado: `201` con `source_type: "xlsx"` y estado `pending`; pasa a `done` en segundos.
3. Preguntar por un dato de una celda (por ejemplo, los créditos de un curso por su nombre) a un artefacto con acceso al dominio. Esperado: la respuesta trae el valor y cita `cursos.xlsx` entre las fuentes.
4. Comprobar que la hoja oculta no aparece en el contenido (preguntar por un dato que solo esté en ella: no debe encontrarse) y que la fórmula se ve como su resultado.

## 3. Casos de error y recorte

| Caso | Cómo probarlo | Esperado |
|---|---|---|
| Formato no soportado | subir `datos.csv`, `datos.xls` y `datos.xlsm` | `400` con la lista de tipos aceptados |
| Libro dañado | renombrar un `.txt` a `.xlsx` y subirlo | documento en `error` con `status_note` "dañado o protegido" |
| Libro con contraseña | proteger un libro con contraseña en Excel y subirlo | documento en `error` con el mismo tipo de mensaje |
| Libro vacío | libro sin celdas con contenido (o solo con hojas ocultas) | documento en `error` con "sin hojas visibles con contenido" |
| Recorte | `MAX_EXCEL_ROWS=100` y un libro de 300 filas | documento `done` con `status_note` de recorte y línea de aviso al final del texto |
| Más de 200 columnas | un libro con un valor en la columna 201 (por ejemplo, `hoja.cell(row=2, column=201, value="x")` con `openpyxl`) | documento `done` con la nota `En la hoja "X" se leyeron solo las primeras 200 columnas.` y la línea `[Aviso: ...]` al final del texto |
| Filas vacías seguidas | un libro con un bloque de datos, 10000 filas vacías y un segundo bloque | documento `done` con la nota `Se dejó de leer la hoja "X" en la fila N tras 10000 filas vacías seguidas; ...`; el segundo bloque no se ingesta |
| Duplicado | subir el mismo libro dos veces al mismo dominio | segunda carga con `200` y `already_existed: true` |

## 4. Panel

1. Abrir el inventario del dominio, elegir el selector de archivos: ofrece `.xlsx`.
2. Subir un libro: la fila muestra `XLSX` y pasa de pendiente a listo.
3. Subir un libro dañado: la fila muestra "Error" y el motivo al pasar el cursor.
4. Eliminar el documento: desaparece del inventario y su archivo del directorio de cargas (eliminación de la feature 012).

## 5. Carga por carpeta

```bash
python scripts/cargar_carpeta.py --help      # ver opciones
python scripts/cargar_carpeta.py <carpeta con un .xlsx y un ~$temporal.xlsx> ...
```

Esperado: el `.xlsx` se sube y el archivo temporal `~$...` se ignora.

## Resultado del recorrido (2026-11-15)

Corrida local con la API real (cliente de pruebas de FastAPI), base SQLite temporal, Qdrant local con una colección temporal (`mia_018_prueba`, ya borrada) y los embeddings locales reales (e5-small). Los datos son sintéticos.

| Prueba | Resultado |
|---|---|
| Libro de 12 cursos con título arriba, dos hojas visibles y una oculta | Documento `done` en 1,6 s, sin nota. La hoja oculta no se indexó (la búsqueda de su contenido no la devuelve). |
| SC-002 (a nivel de recuperación): 30 preguntas (créditos, profesor y horario de cada curso) | **30 de 30 (100 %)**: el fragmento correcto, con el código del curso y el valor esperado en la misma línea, estuvo entre los 8 primeros. |
| `.csv`, `.xls`, `.xlsm` | 400 con `Tipo de fuente no soportado: <ext>. Tipos aceptados: pdf, docx, txt, xlsx.` |
| Archivo que no es un libro | `error` con la nota "dañado o protegido con contraseña" |
| Libro sin celdas con contenido | `error` con la nota "no tiene hojas visibles con contenido" |
| Recorte con `MAX_EXCEL_ROWS=100` y 300 filas | `done` con la nota `El libro se recortó en la fila 102 de la hoja "Matrícula" por superar el tope de 100 filas.`; el inventario la devuelve. |
| SC-004: libro de 5000 filas (578 908 caracteres de texto) frente a un `.txt` de ese mismo texto | 194 s frente a 180 s, ambos `done`: comparables (la lectura del libro agrega unos 14 s sobre el costo de los embeddings, que domina). |

Límites de esta medición, para no sobreestimarla:
- SC-002 se midió como **recuperación** de fragmentos (sin llamar al modelo de lenguaje, para no gastar créditos), no como respuesta final; falta repetirlo con respuestas completas sobre libros reales (T029).
- No se probó un libro protegido con contraseña real (se cubre el mismo camino con un archivo que no es zip), ni el panel en el navegador, ni `cargar_carpeta.py` contra una API en marcha (sí hay pruebas automáticas del filtro de temporales `~$` en `reorganizar_v2.py`).
