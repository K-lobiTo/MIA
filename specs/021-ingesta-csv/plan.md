# Implementation Plan: Ingesta de documentos CSV

**Branch**: `dev` (feature `021-ingesta-csv`, sin rama propia) | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/021-ingesta-csv/spec.md`

## Summary

Se agrega **`csv`** como quinto tipo de fuente con un cargador nuevo, `CsvLoader`, que sigue el patrón de interfaz y factory (`DocumentLoader` y `get_loader`). El CSV se trata como **una hoja de Excel sin nombre**: para que el texto sea idéntico y no haya dos implementaciones que se desvíen, la lógica de filas de `XlsxLoader` (detección del encabezado, nombres de columna, límites, avisos) se **extrae a un módulo compartido** (`tabular.py`) que usan los dos cargadores. El cargador nuevo se ocupa solo de lo propio del CSV: **reconocer la codificación** (UTF-8 con o sin marca de orden de bytes, o Windows-1252), **reconocer el separador** (`;`, `,`, tabulador o `|`), leer con el módulo `csv` de la biblioteca estándar (respeta comillas y celdas con saltos de línea), proteger memoria y tiempo ante archivos mal formados y devolver mensajes claros. Se agrega el tipo a la API, el panel, los dos scripts de carga y la documentación, con un **aviso de datos personales** al elegir un `.csv` en el panel. Sin migración, sin dependencias nuevas, sin ajustes de configuración nuevos (se reutiliza `MAX_EXCEL_ROWS`).

Decisiones principales (detalle y alternativas en [research.md](research.md)):

- **Lógica de filas compartida** con el cargador de Excel, extraída a `tabular.py` sin cambiar su resultado (R1).
- **Codificación**: marca de orden de bytes, luego UTF-8 estricto, luego Windows-1252 estricto; UTF-16, bytes nulos o bytes sin sentido son un error con la sugerencia de guardarlo como «CSV UTF-8» (R2).
- **Separador** por puntaje de consistencia de columnas en una muestra, no por conteo de caracteres (R3).
- **Comillas sin cerrar**: una lectura estricta falla y se reintenta sin interpretar comillas, con aviso (R4).
- **Tope de largo por celda** con aviso, además de los topes de filas y columnas de Excel (R5).
- **Mismo formato de fila que Excel, sin marca de hoja** porque el CSV no tiene nombre de hoja (R6).
- **Aviso de datos personales** no bloqueante en el panel y en la documentación, sin detección automática (R9).

## Technical Context

**Language/Version**: Python 3.12+ (API `mia` y scripts), TypeScript con React 19 (panel `web/admin/`)

**Primary Dependencies**: módulo `csv` y `codecs` de la biblioteca estándar; `openpyxl` (ya existe, para el cargador de Excel y la letra de columna). **Ninguna dependencia nueva.**

**Storage**: sin cambios de esquema. `documents.source_type` ya es texto libre (gana el valor `csv`) y `documents.status_note` (migración `0013`) guarda el motivo de un error o un aviso de recorte.

**Testing**: `pytest` en la raíz (cargador, API de carga, canal de ingesta, scripts, equivalencia con Excel) y Vitest en `web/admin/`. Los archivos de prueba se **generan** en las pruebas con datos inventados; no hay binarios ni datos reales en el repositorio (FR-017).

**Target Platform**: Railway (API y panel), ingesta local (`scripts/cargar_carpeta.py`).

**Project Type**: web-service (API) + aplicación web (panel). Sin servicios nuevos.

**Performance Goals**: un CSV de hasta 5 000 filas queda listo en un tiempo comparable al de un TXT equivalente (SC-005); un archivo con una celda de millones de caracteres no agota la memoria.

**Constraints**: entorno de costo cero (sin dependencias ni servicios nuevos); la memoria máxima de un archivo es la de `MAX_UPLOAD_MB` (25 MB); el cargador nunca ejecuta ni evalúa contenido; mensajes y documentación en español, sin guion largo; **ningún dato real de personas en el repositorio**.

**Scale/Scope**: un cargador nuevo, un módulo compartido extraído de un cargador existente, cambios de una línea en cuatro listas de tipos, un aviso en el panel y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | **Cumple.** Solo cambia la ingesta; ningún artefacto toca la base ni el almacén. |
| II. Pipeline modular e intercambiable | **Cumple.** Un tipo de fuente nuevo (el ejemplo que da el principio, "CSV") se agrega como implementación de `DocumentLoader` seleccionada por nombre en el factory, sin modificar el fragmentado, los embeddings ni el almacén vectorial. |
| III. Independencia del proveedor de LLM | **No aplica** (no toca el modelo). |
| IV. Extensibilidad de dominios | **Cumple.** Se pueden agregar CSV a un dominio existente en cualquier momento sin migrar nada. |
| V. Trazabilidad de respuestas | **Cumple.** El CSV es un documento más: se cita por su nombre de archivo y su dominio, como los demás tipos. |
| Datos sensibles de personas | **Cumple con cuidado.** Un CSV suele traer datos de personas (cédulas, correos). Se agrega un aviso en el panel y en la documentación y se prohíben datos reales en el repositorio; los permisos por dominio y artefacto son los de siempre, y la constitución sigue exigiendo control de acceso antes de exponer esos datos en un artefacto público. |
| Estilo (sin guion largo, español) | **Cumple.** |

Sin violaciones: no hace falta la tabla de complejidad. **Re-evaluación tras el diseño (Phase 1): sin cambios.** El único riesgo es de regresión del cargador de Excel al extraer su lógica; se cubre con sus pruebas existentes y con la prueba de equivalencia (SC-006).

## Project Structure

### Documentation (this feature)

```text
specs/021-ingesta-csv/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R1 a R11
├── data-model.md        # Phase 1: sin cambios de esquema; el tipo csv y la nota de estado
├── quickstart.md        # Phase 1: guía de validación, con el archivo real solo en local
├── contracts/
│   └── ingesta-csv.md   # Phase 1: cargador, mensajes, carga por API y panel
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
src/mia/
├── ingestion/loaders/
│   ├── base.py                        # get_loader: rama "csv"
│   ├── tabular.py                     # NUEVO: lógica de filas compartida (encabezado, columnas, límites, avisos)
│   ├── xlsx_loader.py                 # usa tabular.py, sin cambiar su resultado
│   └── csv_loader.py                  # NUEVO: CsvLoader (codificación, separador, comillas, tope de celda)
└── api/routes/domains.py              # tipos aceptados: pdf, docx, txt, xlsx, csv

scripts/
├── cargar_carpeta.py                  # TIPOS incluye .csv
└── reorganizar_v2.py                  # TIPOS incluye .csv

web/admin/src/modules/inventario/
├── inventoryUtils.ts                  # ALLOWED_EXTENSIONS y mensaje de rechazo con .csv; helper del aviso
└── InventarioPage.tsx                 # accept con .csv y aviso de datos personales al elegir o soltar un .csv

tests/unit/
├── csv_de_prueba.py                   # NUEVO: genera CSV inventados con las variantes y los problemas reales
├── test_csv_loader.py                 # NUEVO: codificación, separador, comillas, celdas, límites, errores
├── test_tabular.py                    # NUEVO: la lógica compartida (encabezado, columnas, tope, avisos)
├── test_documents_csv.py              # NUEVO: carga por API, estados, nota, duplicado y eliminación
├── test_csv_equivalencia.py           # NUEVO: la misma tabla en CSV y en Excel da las mismas filas (SC-006)
└── test_xlsx_loader.py, test_loaders_base.py, test_documents_xlsx.py    # sin cambios de resultado; se amplía el rechazo de tipos

docs/
├── ARQUITECTURA.md                    # el quinto tipo y el módulo compartido
├── OPERACION.md                       # cómo subir un CSV, límites y aviso de datos personales
└── Definicion_Requerimientos_MVP.md / _V2.md    # donde listen los tipos aceptados
```

**Structure Decision**: se sigue la estructura existente (un cargador por tipo en `ingestion/loaders/`, registrado en el factory). El módulo compartido `tabular.py` es nuevo porque dos cargadores necesitan exactamente la misma regla de filas, y duplicarla haría que el CSV y el Excel se desviaran con el tiempo.

## Riesgos

- **Regresión en el cargador de Excel** al extraer la lógica compartida: se mantiene su texto idéntico y se corren sus pruebas existentes (`test_xlsx_loader.py`, `test_documents_xlsx.py`, la medición de 30 preguntas de la 018) antes y después.
- **Codificación mal elegida**: un archivo en Windows-1252 cuyos bytes casualmente sean UTF-8 válido, o al revés, se leería con tildes rotas; es poco probable con texto en español y se reduce con la prueba estricta de UTF-8 primero (R2).
- **Separador mal elegido** en archivos de una sola columna o con muy pocas filas: se lee como una columna con aviso, nunca falla (R3).
- **Datos personales en un dominio consultable**: no se puede resolver con código; el aviso y la documentación lo advierten y el control de acceso es el de los artefactos (R9).
- **Nombre del ajuste `MAX_EXCEL_ROWS`**: se reutiliza para el CSV aunque se llame "Excel"; se documenta (R7).
