# Implementation Plan: Respuestas completas, sin cortes

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-respuestas-completas/spec.md`

## Summary

Dos causas, dos mecanismos independientes, cada uno detrás de su propia variable y apagado por defecto:

1. **Contexto completo (`QUERY_COMPLETE_CONTEXT`).** Para los documentos principales de la consulta (por defecto, el del mejor resultado) se entrega el documento entero si tiene hasta 25 fragmentos (cubre todos los programas de curso conocidos, el mayor tiene 21) y, si es más largo, se prolongan unos fragmentos hacia adelante desde lo encontrado, donde suelen continuar las listas y secciones. Un tope de caracteres por consulta acota el costo. Cuando un pasaje no llega al final de su documento se marca con `[...el documento continúa]` y una instrucción adicional le pide al modelo decir explícitamente que la lista es parcial y dónde sigue (FR-004).
2. **Corte de la generación (`QUERY_RETRY_CUT_ANSWERS`).** Los proveedores informan el motivo de fin de la generación en un campo nuevo y común de `LLMAnswer` (`finish_reason`). Si es anormal (límite de longitud u otro), la ruta reintenta una vez respetando los topes de gasto; si el segundo intento también se corta, entrega el texto con un aviso fijo al final. Ambas cosas quedan anotadas en el registro de Uso, sin migraciones.

La medición reutiliza la herramienta de la feature 005, con una categoría nueva de casos de listas largas con el último ítem esperado, y mide además reintentos, avisos y respuestas que terminan sin puntuación (señal de corte que el modelo no declara).

## Technical Context

**Language/Version**: Python 3.12 (API FastAPI existente)

**Primary Dependencies**: las existentes; sin dependencias nuevas

**Storage**: sin cambios de esquema ni migraciones; el registro de consultas (`QueryLog`) usa `reject_reason` para las notas, como la feature 006; Qdrant no se reindexa

**Testing**: pytest (`tests/unit/`) con almacén, embeddings y modelo simulados, como `tests/unit/test_query_citations.py`; la verificación real es la corrida de la herramienta de la 005 contra producción ([quickstart.md](quickstart.md))

**Target Platform**: API en Railway (se enciende solo para medir) y local para desarrollo

**Project Type**: web-service (API) más la herramienta de diagnóstico existente

**Performance Goals**: costo medio por consulta y latencia p50 sin subir más de 25 % respecto a la línea base (SC-005 y SC-006); reintentos en 5 % o menos de las consultas (SC-004)

**Constraints**: cada mecanismo apagado por defecto y reversible por variable de entorno; sin migraciones ni reindexación; estructura de la respuesta de la API intacta; compatible con las citas de la feature 006; cualquier proveedor de LLM (el motivo de fin es opcional en la interfaz); los topes de gasto mandan sobre el reintento

**Scale/Scope**: toca `src/mia/rag/` (contexto, interfaz del LLM y 4 proveedores), `src/mia/api/routes/query.py`, `src/mia/config.py`, `scripts/linea_base.py`, los casos de prueba y la documentación

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. Solo cambia cómo la API arma el contexto y procesa la respuesta; no se toca el almacenamiento. |
| II. Pipeline modular e intercambiable | Cumple. La ampliación del contexto vive en `rag/context.py` y el reintento en un módulo propio; ambos por configuración. |
| III. Independencia de proveedor de LLM | Cumple. El motivo de fin se normaliza en un campo común de `LLMAnswer`; cada proveedor lo traduce y, si no lo informa, queda desconocido y no se reintenta. La lógica no depende de ningún proveedor. |
| IV. Extensibilidad de dominios | No aplica. |
| V. Trazabilidad de respuestas | Refuerza el principio: una lista parcial o una respuesta con posible corte lo dicen; las fuentes de la 006 siguen validándose. |
| Datos sensibles | Sin cambios: se entrega más texto del mismo documento al mismo proveedor ya autorizado (OpenRouter con retención cero). |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION, PRUEBAS_MVP (el límite conocido pasa a mitigado), V3 y el informe de la línea base. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. No hay migraciones, ni dependencias, ni llamadas nuevas salvo el reintento acotado por los topes de gasto.

## Project Structure

### Documentation (this feature)

```text
specs/007-respuestas-completas/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── contexto-completo-y-cortes.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                     # + 6 variables query_* (ver data-model.md)
├── rag/
│   ├── context.py                # Passage gana `continues`; build_passages con política de contexto completo y tope
│   ├── completeness.py           # NUEVO: opciones on/off, instrucción de completitud, marca de continuación,
│   │                             #        decisión de reintento y aviso de posible corte
│   ├── llm.py                    # LLMAnswer gana `finish_reason` (opcional)
│   └── providers/
│       ├── openrouter_llm.py     # informan el motivo de fin
│       ├── glm_llm.py
│       ├── anthropic_llm.py
│       └── gemini_llm.py         # sin motivo informado: queda None
└── api/routes/query.py           # pasa la política de contexto, agrega la instrucción y reintenta

scripts/linea_base.py             # categoría `lista_larga`, reintento, aviso de corte, terminación sin puntuación
scripts/datos/casos_busqueda.json # + casos de listas largas con `contiene` (último ítem)

tests/unit/
├── test_completeness.py          # NUEVO: opciones, marca, decisión de reintento y aviso
├── test_context.py               # + ampliación de contexto y tope (archivo existente)
├── test_query_completeness.py    # NUEVO: la ruta con las dos opciones apagadas y encendidas
└── test_linea_base.py            # + lo que se agrega a la herramienta

docs/                             # ARQUITECTURA, OPERACION, PRUEBAS_MVP, V3 (BUS-8), LINEA_BASE
```

**Structure Decision**: dos mecanismos independientes, cada uno con su variable, en lugar de uno solo: el contexto ampliado cuesta tokens en todas las consultas que lo usan y el reintento solo en las que se cortan (muy pocas), y separarlos permite medir y decidir cada uno por su cuenta. Se descarta reindexar con fragmentos más grandes o por secciones (cambia los puntajes de toda la línea base y obliga a recargar los documentos) y se descarta un "modo agente" que pida más contexto al modelo con una segunda llamada (duplica el costo de cada consulta larga).

## Complexity Tracking

Sin violaciones que justificar.
