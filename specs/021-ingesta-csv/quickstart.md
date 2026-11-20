# Quickstart: validar la ingesta de CSV

Cómo comprobar la feature de punta a punta. Contratos: [contracts/ingesta-csv.md](contracts/ingesta-csv.md). Decisiones: [research.md](research.md).

## Preparación

```bash
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d qdrant                   # solo para el recorrido de extremo a extremo
uvicorn mia.api.main:app --reload             # no hay migración nueva
cd web/admin && npm run dev                   # el panel
```

## 1. Pruebas automáticas (sin datos reales)

```bash
pytest tests/unit/test_csv_loader.py tests/unit/test_tabular.py tests/unit/test_documents_csv.py tests/unit/test_csv_equivalencia.py
pytest tests/unit/test_xlsx_loader.py tests/unit/test_documents_xlsx.py tests/unit/test_loaders_base.py   # Excel sin cambios de resultado
pytest                                        # sin regresiones (SC-008)
ruff check src tests scripts whatsapp
cd web/admin && npm test && npx tsc --noEmit  # tipos aceptados y aviso de datos personales
```

Los CSV de estas pruebas los genera `tests/unit/csv_de_prueba.py` con datos inventados; no hay archivos reales en el repositorio.

## 2. Comprobación con el archivo real, solo en local

El archivo real de la persona dueña del proyecto (un CSV exportado de Excel con datos de personas) **no se copia al repositorio ni se muestra su contenido**. Para comprobar la forma, desde una carpeta fuera del repositorio:

```bash
python -I - <<'PY'
import os
from pathlib import Path
from mia.ingestion.loaders.csv_loader import CsvLoader
cargador = CsvLoader()
texto = cargador.load(Path(os.path.expanduser("~/Downloads/Proceso_2026_final(CANDIDATOS).csv")))
lineas = texto.splitlines()
print("lineas:", len(lineas), "| avisos:", cargador.notes)
print("sin caracteres rotos:", "Ã" not in texto and "�" not in texto)
print("encabezados presentes:", all(h in texto for h in ("Nombre:", "Promedio de cursos de U:")))
PY
```

Esperado (por la forma observada: 45 registros, 29 columnas con la última sin nombre, 3 filas vacías, 11 celdas multilínea): una línea por fila con contenido (unas 41), **ningún aviso**, sin `Ã` ni `�` (la codificación se reconoció) y los encabezados presentes con sus valores.

## 3. Recorrido manual (panel)

1. Elegir un `.csv` (puede ser uno inventado con `python tests/unit/csv_de_prueba.py` o uno propio sin datos personales): aparece el **aviso de datos personales**, que se puede cerrar y no bloquea la subida.
2. Subirlo a un dominio de prueba: queda `pending` y luego `done`; en el inventario aparece con su tipo y sin nota.
3. Subir uno con más filas que `MAX_EXCEL_ROWS` (por ejemplo bajar el ajuste a 100 en local): queda `done` con la nota de recorte visible bajo el documento.
4. Subir un `.csv` en UTF-16 o un `.xlsx` renombrado a `.csv`: queda en `Error` con el motivo y la sugerencia de «CSV UTF-8».
5. Subir un `.tsv`: se rechaza con los tipos aceptados.
6. Preguntar en la Consulta por un dato de una fila (con un dominio que lo contenga): la respuesta trae el valor y cita el archivo.
7. Eliminar el documento: desaparece del inventario y de las búsquedas.

## 4. Carga por carpeta

```bash
python scripts/cargar_carpeta.py <carpeta con un .csv inventado> --dominio <dominio de prueba>
```

Se carga igual que los demás tipos y se imprime el aviso de datos personales una vez.

## 5. Medición (SC-003)

Con un dominio de prueba que tenga un CSV de ejemplo (horarios, cursos o costos inventados), hacer al menos 20 preguntas cuyo dato esté en filas del archivo y verificar que al menos el 90 % se responde con el valor correcto y cita el CSV. Anotar el resultado al final de este archivo.

## Resultado del recorrido

### Recorrido local con datos inventados (T029, 2026-11-19)

Contra una API local con una base SQLite temporal, una colección temporal de Qdrant local (ambas borradas al terminar) y los embeddings locales; `MAX_EXCEL_ROWS=100`. Sin tocar producción. Se subieron por la API CSV generados con `tests/unit/csv_de_prueba.py` (datos inventados): **13 pasos, todos correctos**.

- Un CSV con la estructura del real (Windows-1252, punto y coma, celdas multilínea, filas vacías, columna final sin nombre) queda `done` sin nota; uno con codificaciones mezcladas también; uno UTF-8 con marca de orden de bytes y comas también.
- Subir el mismo contenido otra vez devuelve el documento existente (`already_existed`).
- Un CSV con más filas que el tope queda `done` con la nota `El archivo se recortó en la fila 102 por superar el tope de 100 filas.`; uno con comillas sin cerrar queda `done` con su aviso.
- Un UTF-16, un `.xlsx` renombrado a `.csv` y un CSV vacío quedan en `error` con su mensaje (el de UTF-16 con la sugerencia de «CSV UTF-8»).
- Un `.tsv` y un `.xls` se rechazan con `Tipos aceptados: pdf, docx, txt, xlsx, csv.`.
- Eliminar un CSV lo quita del inventario.
- Verificación automática: `pytest` 2098 pruebas sin fallos, `ruff` limpio, y `npm test` y `npx tsc --noEmit` en `web/admin` (227 pruebas).

**No se midió aquí** (queda para T031): SC-003, las 20 preguntas con el modelo real sobre un CSV en un dominio, y la revisión visual del aviso de datos personales en el panel en el navegador.

### Comprobación con el archivo real, solo en local (T030, 2026-11-19)

Con el fragmento de la sección 2 sobre el archivo de la persona dueña del proyecto, **sin copiarlo ni mostrar su contenido**: se leen **41 líneas** (45 registros, menos el encabezado y 3 filas vacías), **ningún aviso**, los encabezados presentes, la columna final sin nombre como `Columna AC` y sin caracteres rotos.

**Hallazgo**: la primera lectura dejó `Ã­` donde debía haber `í` en 32 lugares. El archivo está en Windows-1252 pero **algunas celdas están en UTF-8** (se pegaron desde otra fuente antes de guardar). Se resolvió leyendo como UTF-8 las secuencias que son una letra o un signo latino válido y el resto como Windows-1252 (tarea T032, caso borde en la spec y `research.md` R2), con una prueba que reproduce el problema con datos inventados.
