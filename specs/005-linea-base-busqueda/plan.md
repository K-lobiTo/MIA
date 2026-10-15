# Implementation Plan: Línea base de la búsqueda de MIA

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-linea-base-busqueda/spec.md`

## Summary

Armar un conjunto de casos de prueba de búsqueda y una herramienta de línea de comandos (`scripts/linea_base.py`) que mide cómo se comporta MIA hoy, **sin tocar nada de `src/`**: (1) la etapa `puntajes` consulta Qdrant de producción en solo lectura con los mismos componentes que la API (embedding local e5-small y `VectorStore`), registra posición, puntaje y documento de hasta 50 candidatos por caso y calcula, sin gastar tokens, qué casos cambiarían de resultado con otros umbrales; (2) la etapa `respuestas` corre los casos contra `POST /query` en los dos modos, con un tope de gasto obligatorio, y registra fuentes mostradas frente a esperadas, latencia y costo (leído del módulo Uso); (3) `informe` genera un resumen en Markdown sin datos personales y `comparar` contrasta dos corridas caso por caso. El resultado es `docs/LINEA_BASE_BUSQUEDA.md`, que responde las decisiones 3 y 5 de la sección 2.8 de V3 y sirve de vara para F, B y E.

## Technical Context

**Language/Version**: Python 3.12 (el del proyecto)

**Primary Dependencies**: las que ya instala `pip install -e .` (`qdrant-client`, `onnxruntime`, `sqlalchemy`, `mia.rag.embeddings`, `mia.storage`); la etapa `respuestas` usa solo la biblioteca estándar, como `scripts/pruebas_mvp.py`. Sin dependencias nuevas.

**Storage**: lee Qdrant y la base de metadatos (SQLite local o Postgres) solo con consultas de lectura; escribe únicamente archivos JSON/Markdown en `tmp/linea_base/` (ignorado por git) y el informe versionado en `docs/`.

**Testing**: pytest (`tests/unit/test_linea_base.py`) para la lógica pura (carga y validación de casos, barrido de umbrales, ventana de separación, resumen, comparación); sin red ni Qdrant. La verificación contra datos reales va en [quickstart.md](quickstart.md).

**Target Platform**: la laptop del usuario (Linux), contra producción: Qdrant Cloud y Neon (para `puntajes`, con `.env.produccion`) y la API de Railway (para `respuestas`).

**Project Type**: herramienta de línea de comandos y documentación (no es un servicio nuevo).

**Performance Goals**: corrida completa de puntajes en menos de 10 minutos (SC-005) sin tokens de LLM; las corridas de respuestas son lentas por naturaleza (3 a 5 s por consulta, 19+ casos por 2 modos).

**Constraints**: solo lectura (FR-005); ninguna salida con texto de fragmentos ni de respuestas (FR-006); tope de gasto obligatorio por corrida (FR-011); la información se considera pública y se mide en producción (aclaración del 2026-10-15); no se modifica `src/`, ni migraciones, ni configuración por defecto (FR-016).

**Scale/Scope**: unos 30 casos, dos modos, hasta 50 candidatos por caso; 4 dominios grandes de actas, currículum y proyectos de graduación ya cargados.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. La herramienta es un cliente más: puntajes lee el mismo almacenamiento que la API; respuestas usa solo HTTP. No agrega ningún camino nuevo a los datos dentro del producto. |
| II. Pipeline modular e intercambiable | Cumple. Se reutilizan las fábricas (`get_embedding_provider`, `get_vector_store`) en vez de instanciar clases concretas, así la medición sigue la configuración del entorno. |
| III. Independencia de proveedor de LLM | No aplica a puntajes (no llama al LLM). respuestas pasa por la API, que ya es agnóstica. |
| IV. Extensibilidad de dominios | No aplica; no crea ni cambia dominios. |
| V. Trazabilidad de respuestas | Apoya el principio: mide qué fuentes se muestran y cuáles sobran, línea base de BUS-5. |
| Datos sensibles | El usuario declaró públicos los datos para pruebas (2026-10-15). Aun así: solo lectura y salidas sin texto de fragmentos ni de respuestas. Ver R4 en [research.md](research.md). |
| Alcance incremental y documentación viva | Cumple: se documenta en `docs/ARQUITECTURA.md`, `docs/OPERACION.md`, el informe y la sección 2.8 de V3. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. El diseño no agrega código a `src/`, no agrega dependencias y no escribe en ningún almacén de MIA.

## Project Structure

### Documentation (this feature)

```text
specs/005-linea-base-busqueda/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── linea-base-cli.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
scripts/
├── linea_base.py                  # CLI: puntajes, respuestas, informe, comparar (nuevo)
├── datos/
│   └── casos_busqueda.json        # conjunto de casos versionado (nuevo)
└── pruebas_mvp.py                 # batería existente: no se modifica

tests/unit/
└── test_linea_base.py             # lógica pura (nuevo)

tmp/linea_base/<fecha>-<etiqueta>/ # salida cruda de cada corrida (ignorada por git)

docs/
└── LINEA_BASE_BUSQUEDA.md         # informe versionado (nuevo, al final)
```

**Structure Decision**: un solo script con subcomandos, como `scripts/admin.py` y `scripts/cargar_carpeta.py`, más un archivo de datos en `scripts/datos/` (donde ya vive `reorganizacion_v2.json`). Se descarta ponerlo en `src/mia/` porque la herramienta no forma parte del producto y no debe desplegarse con la API; y se descarta ampliar `pruebas_mvp.py` porque esa batería es de aceptación (pasa o falla) y esta medición es de diagnóstico (números).

## Complexity Tracking

Sin violaciones que justificar.
