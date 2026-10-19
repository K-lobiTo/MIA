# Implementation Plan: Pregunta limpia (segundo intento de búsqueda)

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-pregunta-limpia/spec.md`

## Summary

Un módulo de reglas de texto sin dependencias (`mia.rag.query_rewrite`) que, dada una pregunta de identificación o descripción en español, devuelve la pregunta reducida a lo que se busca ("¿Quién es Natalia Soto Solís?" pasa a "Natalia Soto Solís") o `None` si no corresponde. La ruta `POST /query` lo usa una sola vez, solo si la primera búsqueda no dejó ningún fragmento sobre el umbral y la variable `QUERY_CLEAN_QUESTION` está encendida (apagada por defecto): calcula el embedding local de la versión corta, repite la búsqueda en Qdrant con los mismos dominios, límite y umbral, y sigue el flujo normal con esos fragmentos. El modelo recibe siempre la pregunta original del usuario; la reducción solo cambia qué se busca. No hay llamada nueva a ningún modelo de lenguaje.

La nota de Uso se deja en `reject_reason` (como las de las features 006 y 007), tanto si el segundo intento encontró fragmentos como si no; para eso la respuesta "sin información" también debe poder dejar una nota (hoy no la deja). La herramienta de la 005 gana: las variantes "limpia" en `puntajes` (calculadas con el mismo módulo, sin costo, para anticipar el efecto antes de gastar), casos de envoltura y negativos, y el conteo de segundos intentos en `respuestas`.

## Technical Context

**Language/Version**: Python 3.12 (API FastAPI existente)

**Primary Dependencies**: las existentes; sin dependencias nuevas (solo `re` y `unicodedata` de la biblioteca estándar; no se usan listas de stopwords de NLTK ni spaCy, ver [research.md](research.md) R2)

**Storage**: sin cambios de esquema ni migraciones; `QueryLog.reject_reason` para la nota; Qdrant no se reindexa

**Testing**: pytest (`tests/unit/`), pruebas en tabla del módulo de reglas y pruebas de la ruta con almacén, embeddings y modelo simulados, como `tests/unit/test_query_completeness.py`; la verificación real es la corrida de la herramienta de la 005 contra producción ([quickstart.md](quickstart.md))

**Target Platform**: API en Railway (se enciende solo para medir) y local para desarrollo

**Project Type**: web-service (API) más la herramienta de diagnóstico existente

**Performance Goals**: las consultas sin segundo intento no cambian (FR-011); las que lo tienen suman una búsqueda más (un embedding local y una consulta a Qdrant, menos de 1 s, SC-006); cero llamadas nuevas al modelo

**Constraints**: apagada por defecto y reversible por variable de entorno (BUS-6); sin migraciones ni reindexación; estructura de la respuesta de la API intacta; el valor inválido de la variable no impide el arranque; compatible con las features 006 y 007; los permisos y los topes de gasto se evalúan antes, como hoy

**Scale/Scope**: toca `src/mia/rag/query_rewrite.py` (nuevo), `src/mia/config.py`, `.env.example`, `src/mia/api/routes/query.py`, `scripts/linea_base.py`, los casos de prueba y la documentación

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. Solo cambia qué texto busca la API; el almacenamiento no se toca. |
| II. Pipeline modular e intercambiable | Cumple. La reformulación es una etapa propia (`query_rewrite`), seleccionable por configuración y retirable sin tocar el resto. No introduce un proveedor nuevo: son reglas, no una pieza con implementaciones alternativas, así que no hace falta una interfaz con fábrica. |
| III. Independencia de proveedor de LLM | Cumple. No usa modelo de lenguaje; el embedding es el local ya existente. |
| IV. Extensibilidad de dominios | No aplica. |
| V. Trazabilidad de respuestas | Sin cambios: las fuentes siguen siendo las de los fragmentos que llegan al modelo (y las citas de la 006). La nota de Uso deja constancia de que se usó la pregunta limpia. |
| Datos sensibles | Sin cambios: el texto reducido es parte de la pregunta que ya se registra. |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION, V3 (BUS-1, BUS-7) y LINEA_BASE_BUSQUEDA. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. No hay migraciones, ni dependencias, ni llamadas nuevas a modelos.

## Project Structure

### Documentation (this feature)

```text
specs/008-pregunta-limpia/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── pregunta-limpia.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                     # + query_clean_question (texto on/off)
├── rag/
│   └── query_rewrite.py          # NUEVO: clean_question_enabled, clean_question, nota de Uso
└── api/routes/query.py           # segundo intento tras la primera búsqueda; no_info deja la nota

scripts/linea_base.py             # variante "limpia" en puntajes, conteo de segundos intentos, casos negativos
scripts/datos/casos_busqueda.json # + casos de envoltura (misma persona, otras redacciones) y negativos

tests/unit/
├── test_query_rewrite.py         # NUEVO: tablas de reglas, guardas, negativos, variable
├── test_query_clean_question.py  # NUEVO: la ruta con la opción apagada y encendida
└── test_linea_base.py            # + lo que se agrega a la herramienta

.env.example                      # + QUERY_CLEAN_QUESTION=off
docs/                             # ARQUITECTURA, OPERACION, V3 (BUS-1, BUS-7), LINEA_BASE_BUSQUEDA
```

**Structure Decision**: un módulo nuevo de funciones puras en `rag/` (igual que `citations.py` y `completeness.py`), sin clase ni interfaz con fábrica, porque las reglas son una sola implementación y no un proveedor intercambiable. La ruta gana un bloque corto tras la primera búsqueda. Se descartan: reformular con un modelo de lenguaje (agrega llamada, costo y latencia, y contradice BUS-7); quitar todas las palabras vacías (pierde el sentido de preguntas como "¿Cuántas horas tiene el curso?", ver R2); reconocimiento de entidades con spaCy (dependencia que consume memoria, el recurso escaso en Railway); y bajar el umbral (opciones A y C, descartadas en la 005).

## Complexity Tracking

Sin violaciones que justificar.
