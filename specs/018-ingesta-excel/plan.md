# Implementation Plan: Ingesta de documentos Excel

**Branch**: `dev` (feature `018-ingesta-excel`, sin rama propia) | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/018-ingesta-excel/spec.md`

## Summary

Un cargador nuevo, `XlsxLoader`, convierte un libro `.xlsx` en texto plano, una línea por fila, con el nombre de la hoja y el encabezado de cada columna en cada línea (`[Cursos] Código: MC4001 | Créditos: 3`). Se engancha al factory `get_loader` que ya existe, así que el fragmentado, los embeddings, Qdrant, la búsqueda y las fuentes no cambian. Se lee con `openpyxl` en modo de solo lectura y solo valores (resultado de las fórmulas, nunca la expresión), se ignoran las hojas ocultas y se recorta en un tope de filas configurable (`MAX_EXCEL_ROWS`, 5000). Como hoy un documento en `error` no dice por qué, se agrega una columna opcional `status_note` (migración `0013`) con un mensaje fijo en español, que el panel muestra; así los errores (libro dañado, con contraseña o vacío) y los recortes no son silenciosos. Los cuatro caminos de entrada (API, panel, `cargar_carpeta.py`, `reorganizar_v2.py`) agregan `xlsx` a su lista de tipos.

Decisiones principales (detalle y alternativas en [research.md](research.md)):

- **`openpyxl` con `read_only=True, data_only=True`**: Python puro, por flujo (poca memoria), sin ejecutar macros ni vínculos, y entrega el valor calculado de las fórmulas (R1).
- **El contexto va en cada fila, no en un título**: el fragmentador corta cada 1000 caracteres sin mirar líneas, así que cada fila debe llevar su hoja y sus encabezados para ser autosuficiente. No se toca el fragmentador (R2).
- **Encabezados = primera fila con al menos dos celdas con contenido**; lo que está arriba se conserva como texto simple (R3).
- **Formato de valores sin interpretar el código de Excel**: fechas `dd/mm/aaaa`, porcentajes y enteros limpios; no se reproducen símbolos de moneda ni separadores de miles (R4).
- **Recorte con aviso, no rechazo** al llegar a `MAX_EXCEL_ROWS`, con nota en el documento y línea de aviso en el texto (R5, R6).
- **`status_note` en el documento** y `LoaderError` para mensajes aptos para personas; también mejora el PDF vacío o el DOCX dañado (R6).

## Technical Context

**Language/Version**: Python 3.12+ (API `mia`), TypeScript con React 19 (panel `web/admin/`)

**Primary Dependencies**: FastAPI, SQLAlchemy y Alembic (ya existen). **Una dependencia nueva**: `openpyxl>=3.1` (con `et-xmlfile`, Python puro). Panel: Mantine, TanStack Query y Vite, sin cambios.

**Storage**: columna nueva `documents.status_note` (migración aditiva `0013`, nula por defecto) en la base SQL (SQLite en desarrollo, Postgres en producción). El archivo se guarda como `{id}.xlsx` en el directorio de cargas existente. Qdrant sin cambios (los mismos fragmentos de texto).

**Testing**: `pytest` en la raíz (nuevos `tests/unit/test_xlsx_loader.py` y `tests/unit/test_documents_xlsx.py`; los libros de prueba se arman con `openpyxl` en `tmp_path`, sin archivos binarios en el repositorio) y Vitest en `web/admin/`.

**Target Platform**: Railway (API), Neon (Postgres), sitio estático del panel; la ingesta pesada se sigue haciendo en la laptop (memoria `mia_ingesta_local`).

**Project Type**: web-service (API) + panel web. Sin proyectos nuevos.

**Performance Goals**: un libro de hasta 5000 filas queda listo en un tiempo comparable al de un PDF equivalente (SC-004); lectura por flujo, sin cargar el libro entero en memoria.

**Constraints**: entorno gratuito (unos 340 MB de RAM en reposo en Railway); `MAX_UPLOAD_MB=25` ya limita el archivo; sin ejecutar macros ni vínculos externos (FR-011); mensajes y documentación en español, sin guion largo.

**Scale/Scope**: un cargador nuevo (~150 líneas), una rama en el factory, una columna y una migración, dos pequeños cambios de API (`DocumentOut`, validación del tipo), tres lugares del panel, dos scripts y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | **Cumple.** Los artefactos siguen consultando solo por la API; no se toca ninguno. |
| II. Pipeline modular | **Cumple y es el caso de uso previsto**: "agregar un tipo de fuente nuevo" por interfaz y factory (`DocumentLoader`), sin tocar fragmentado, embeddings ni almacén. La columna `status_note` y `notes` son extensiones opcionales de la interfaz, sin romper los cargadores existentes. |
| III. Independencia del proveedor de LLM | **No aplica.** La lectura del libro es determinista, sin modelo. |
| IV. Extensibilidad de dominios | **Cumple.** Se puede subir un libro a cualquier dominio sin tocar los demás; la migración es solo aditiva. |
| V. Trazabilidad de respuestas | **Cumple.** El libro es un documento normal del dominio: se cita por su nombre de archivo. La línea de aviso de recorte evita que una respuesta presente como completo un libro recortado. |
| Datos sensibles de personas | **Sin cambios.** Aplican los mismos permisos por dominio y la misma política de datos que a los demás documentos. `status_note` no guarda contenido del libro. |
| Estilo (sin guion largo, español) | **Cumple.** |

Sin violaciones: no hace falta la tabla de complejidad. **Re-evaluación tras el diseño (Phase 1): sin cambios.**

## Project Structure

### Documentation (this feature)

```text
specs/018-ingesta-excel/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R1 a R8
├── data-model.md        # Phase 1: columna status_note y modelo conceptual
├── quickstart.md        # Phase 1: guía de validación
├── contracts/
│   └── interfaces.md    # Phase 1: carga, DocumentOut, DocumentLoader, formato de texto
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
pyproject.toml                                      # + openpyxl>=3.1
src/mia/
├── config.py                                       # + max_excel_rows (MAX_EXCEL_ROWS)
├── ingestion/
│   ├── loaders/
│   │   ├── base.py                                 # + LoaderError, notes, rama "xlsx" en get_loader
│   │   └── xlsx_loader.py                          # NUEVO: XlsxLoader
│   └── pipeline.py                                 # guarda status_note (LoaderError y notes) y la limpia al empezar
├── api/routes/
│   ├── domains.py                                  # tipo "xlsx" y mensaje con los tipos aceptados; DocumentOut.status_note
│   └── inventory.py                                # status_note en el objeto del inventario
└── storage/
    ├── models.py                                   # Document.status_note
    └── migrations/versions/0013_nota_de_estado_de_documento.py   # NUEVO

scripts/
├── cargar_carpeta.py                               # + .xlsx y omite los temporales "~$"
└── reorganizar_v2.py                               # + .xlsx

web/admin/src/
├── modules/inventario/
│   ├── inventoryUtils.ts                           # ALLOWED_EXTENSIONS + ".xlsx"
│   ├── InventarioPage.tsx                          # accept + ".xlsx"
│   └── TreeNode.tsx                                # muestra status_note junto al estado
└── api/types.ts                                    # status_note?: string | null

tests/unit/
├── test_loaders_base.py                            # NUEVO: LoaderError, notes y get_loader
├── test_xlsx_loader.py                             # NUEVO: formato, hojas ocultas, fórmulas, fechas, combinadas, recorte, errores
└── test_documents_xlsx.py                          # NUEVO: carga por API, rechazo de .xls/.csv, status_note en el pipeline
web/admin/src/modules/inventario/*.test.ts(x)       # extensiones y nota de estado

docs/
├── ARQUITECTURA.md                                 # cuarto tipo de fuente, status_note, MAX_EXCEL_ROWS
├── OPERACION.md                                    # tabla de ajustes (MAX_EXCEL_ROWS) y tipos aceptados
├── Definicion_Requerimientos_MVP.md                # source_type (pdf/docx/txt/xlsx)
└── ESCALABILIDAD.md                                # riesgo aceptado de archivos maliciosos (R8)
```

**Structure Decision**: se sigue la estructura existente (cargadores en `src/mia/ingestion/loaders/`, una migración por cambio de esquema, módulo de inventario del panel). No hay proyectos ni servicios nuevos; el servicio `mia-whatsapp` no cambia.

## Riesgos

- **Filas largas cortadas entre dos fragmentos**: el fragmentador no respeta saltos de línea; una fila de más de unos 200 caracteres puede quedar partida sin traslape completo. Como cada fila lleva su hoja y encabezados, la mitad que queda sigue siendo informativa. Se mide en el quickstart con libros reales; si hace falta, una feature aparte cambia el fragmentador para respetar líneas.
- **Libros sin calcular**: una fórmula que nunca se guardó en Excel (por ejemplo, generada por otro programa) llega sin valor y se omite. Documentado en la spec.
- **Libros de diseño libre** (formularios, tableros): se ingestan con la mejor lectura posible sin garantía de precisión (spec, Assumptions).
- **Despliegue**: la migración `0013` debe estar en el código desplegado antes de que la base la tenga (regla de `CLAUDE.md`); como es aditiva y la columna es nula, desplegar primero el código es seguro.
