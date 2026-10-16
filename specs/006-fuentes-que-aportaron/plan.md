# Implementation Plan: Mostrar solo las fuentes que aportaron a la respuesta

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-fuentes-que-aportaron/spec.md`

## Summary

Hoy `POST /query` devuelve como fuentes todos los pasajes que entregó al modelo. El plan: numerar los pasajes en el contexto (`[Fuente N: ...]`), pedirle al modelo en el mismo mensaje de sistema que cierre la respuesta con una línea `FUENTES: 1, 3`, y en la API **quitar esa línea del texto, validar los números contra los pasajes entregados y listar solo los citados**. Si no hay ninguna cita válida, se listan todos los pasajes, como hoy (regla de seguridad, trazabilidad). Todo ocurre en la capa común (`src/mia/rag/citations.py` y la ruta de consulta), no en cada proveedor, y detrás de una variable `QUERY_CITED_SOURCES` apagada por defecto. No agrega llamadas a ningún modelo, ni migraciones, ni cambia la estructura de la respuesta. La regla de seguridad se anota en el registro de Uso (campo existente) para poder medirla, y la herramienta de la feature 005 se extiende para medirla y comparar contra la línea base.

## Technical Context

**Language/Version**: Python 3.12 (API FastAPI existente)

**Primary Dependencies**: las existentes (FastAPI, SQLAlchemy, pydantic-settings); sin dependencias nuevas

**Storage**: sin cambios de esquema ni migraciones; el registro de consultas (`QueryLog`) usa sus campos actuales (`sources` filtrado y una nota en `reject_reason`)

**Testing**: pytest (`tests/unit/`), con el proveedor de modelos simulado como en `tests/unit/test_query_sources.py`; la verificación real es la corrida de la herramienta de la 005 contra producción (ver [quickstart.md](quickstart.md))

**Target Platform**: API en Railway (se enciende solo para medir) y local para desarrollo

**Project Type**: web-service (API) con una herramienta de diagnóstico ya existente

**Performance Goals**: costo medio por consulta de cada modo sin subir más de 5 % y latencia p50 sin subir más de 10 % respecto a la línea base (SC-004 y SC-005 de la spec)

**Constraints**: cero llamadas extra a modelos; opción apagada por defecto y reversible por variable de entorno sin redespliegue de código; compatibilidad con la Consulta y los scripts; sin migraciones (para que volver al tag `prototipo-v2-estable` siga siendo seguro); funciona con cualquier proveedor de LLM

**Scale/Scope**: toca `src/mia/rag/` (módulo nuevo y formato de contexto compartido por 4 proveedores), `src/mia/api/routes/query.py`, `src/mia/config.py`, la herramienta `scripts/linea_base.py` y la documentación

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. Solo cambia cómo la API arma la respuesta; el almacenamiento no se toca. |
| II. Pipeline modular e intercambiable | Cumple. La lógica de citas es un módulo propio, se activa por configuración y no se mezcla con búsqueda ni con los proveedores. |
| III. Independencia de proveedor de LLM | Cumple por diseño: se descartan las APIs de citas nativas de Claude o Gemini (atarían la función a un proveedor) y se usa una línea de texto que cualquier modelo puede escribir. El formato del contexto se unifica en un helper compartido en vez de repetirse en cada proveedor. |
| IV. Extensibilidad de dominios | No aplica. |
| V. Trazabilidad de respuestas | Es el principio que más pesa: la regla de seguridad garantiza que una respuesta con contenido nunca queda sin fuentes. |
| Datos sensibles | Sin cambios: el contexto que se manda al proveedor es el mismo, con un número de referencia más. |
| Alcance incremental y documentación viva | Se actualizan `docs/ARQUITECTURA.md`, `docs/OPERACION.md`, `docs/Definicion_Requerimientos_V3.md` y se mide con la línea base. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. El diseño no agrega migraciones, ni dependencias, ni llamadas externas.

## Project Structure

### Documentation (this feature)

```text
specs/006-fuentes-que-aportaron/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── citas-y-fuentes.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                       # + query_cited_sources (texto, "off" por defecto)
├── rag/
│   ├── citations.py                # NUEVO: instrucción de citas, interpretación del valor de la opción,
│   │                               #        parseo y validación de la línea FUENTES, selección de fuentes
│   ├── llm.py                      # RagContext gana `reference`; helper compartido format_context()
│   └── providers/
│       ├── anthropic_llm.py        # usan format_context() en lugar de armar el texto cada uno
│       ├── gemini_llm.py
│       ├── glm_llm.py
│       └── openrouter_llm.py
└── api/routes/query.py             # numera pasajes, agrega la instrucción, aplica la selección

scripts/linea_base.py               # extiende `respuestas` para registrar la regla de seguridad
scripts/datos/casos_busqueda.json   # sin cambios

tests/unit/
├── test_citations.py               # NUEVO: parseo, validación y reglas
├── test_query_citations.py         # NUEVO: la ruta con la opción apagada y encendida
└── test_linea_base.py              # + pruebas de lo que se agrega a la herramienta

docs/                               # ARQUITECTURA, OPERACION, V3, LINEA_BASE (resultado de la medición)
```

**Structure Decision**: la lógica nueva va en un módulo propio de `rag/` (como `context.py` y `modes.py`) y la ruta de consulta solo la invoca. Se descarta tocar cada proveedor para pedir citas: se unifica el formato del contexto en `llm.py` y la instrucción se agrega a la que ya trae el modo, así un proveedor nuevo no necesita hacer nada. Se descarta una migración para anotar la regla de seguridad (ver R7).

## Complexity Tracking

Sin violaciones que justificar.
