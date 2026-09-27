# Implementation Plan: Pipeline de Ingesta y Consulta RAG

**Branch**: `001-pipeline-ingesta-rag` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-pipeline-ingesta-rag/spec.md`

## Summary

Reemplazar los stubs de `EmbeddingProvider`, `LLMProvider` y `QdrantVectorStore` por implementaciones
funcionales, y conectar el pipeline completo detrás de los endpoints ya definidos
(`POST /domains/{id}/documents`, `POST /query`): al subir un documento se dispara indexación en
segundo plano (loader, chunker, embeddings, guardado vectorial) con estado consultable; al consultar,
se busca en Qdrant filtrando por dominio, se arma contexto y se genera una respuesta citando su
documento y dominio de origen, o se indica explícitamente que no hay información suficiente.

## Technical Context

**Language/Version**: Python 3.12 (ya definido en `pyproject.toml`)

**Primary Dependencies**: FastAPI, SQLAlchemy, `qdrant-client` (ya presentes) más `sentence-transformers`
(embeddings locales, nueva), `anthropic` (SDK oficial, LLM comercial, nueva) y `google-genai` (SDK
oficial de Gemini, LLM comercial alternativo, agregado durante la implementación)

**Storage**: Qdrant (colección única `mia_chunks`, filtro por dominio) más SQLite (metadata de dominios
y documentos), ambos ya definidos

**Testing**: pytest (ya definido); se agregan tests unitarios de chunking/citación y un test de
integración end-to-end contra un Qdrant real (local, vía `docker-compose`)

**Target Platform**: Linux (Docker Compose en desarrollo local; Render más Qdrant Cloud en despliegue
compartido)

**Project Type**: Servicio web (API backend), estructura de proyecto único ya existente

**Performance Goals**: sin objetivos de alto throughput en el MVP; indexar un documento típico en menos
de 2 minutos (SC-001 del spec), latencia de consulta dominada por la llamada al LLM (no es objetivo de
esta feature optimizarla)

**Constraints**: sin GPU disponible, el modelo de embeddings local debe correr aceptablemente en CPU; el
costo del LLM comercial debe quedar acotado por configuración (modelo y límite de tokens de salida
configurables, no hardcodeados)

**Scale/Scope**: un solo dominio en uso ("Memoria del Consejo"), decenas de documentos, uso esporádico
sin concurrencia alta

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | PASS. No se modifica el contrato de la API expuesta a artefactos; se implementa el comportamiento detrás de endpoints ya existentes. |
| II. Pipeline modular e intercambiable | PASS. Las implementaciones nuevas entran dentro de las interfaces `EmbeddingProvider`, `LLMProvider` y `VectorStore` ya definidas, sin tocar el resto del sistema. |
| III. Independencia de proveedor de LLM (v1.1.0) | PASS. LLM comercial vía `AnthropicLLMProvider` y `GeminiLLMProvider`, seleccionables por `LLM_PROVIDER` sin cambiar código. Embeddings local vía `sentence-transformers` (auto-hospedado, CPU); desde la enmienda a v1.1.0 esto es una decisión de arquitectura permanente para embeddings, no una excepción temporal. |
| IV. Extensibilidad de dominios | N/A para esta feature (no se toca el modelo de dominios). |
| V. Trazabilidad de respuestas | Atendido directamente: FR-006 del spec exige citar documento y dominio de origen en toda respuesta. |
| Restricciones técnicas y datos sensibles | N/A ("Memoria del Consejo" no es un dominio de datos sensibles de personas). |
| Alcance incremental y documentación viva | Cumplido: esta feature sigue el flujo spec, ver `/speckit-tasks`, implementar; `docs/ARQUITECTURA.md` se actualiza al terminar. |

Sin violaciones. No se requiere Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/001-pipeline-ingesta-rag/
├── plan.md              # Este archivo
├── research.md           # Fase 0
├── data-model.md         # Fase 1
├── quickstart.md         # Fase 1
├── contracts/            # Fase 1
│   ├── api-ingestion.md
│   └── api-query.md
└── tasks.md              # Fase 2 (/speckit-tasks, no generado por /speckit-plan)
```

### Source Code (repository root)

Proyecto único ya existente (Opción 1), estructura real (no se crean paquetes nuevos de alto nivel,
solo se completan/agregan archivos dentro de los ya existentes):

```text
src/mia/
├── ingestion/
│   ├── loaders/                    # ya implementado (pdf/docx/txt)
│   ├── chunker.py                  # ya implementado
│   └── pipeline.py                 # NUEVO: orquesta loader -> chunker -> embeddings -> upsert
├── rag/
│   ├── embeddings.py                # ya implementado (interfaz + factory)
│   ├── llm.py                       # ya implementado (interfaz + factory)
│   └── providers/
│       ├── local_embeddings.py      # IMPLEMENTAR (sentence-transformers)
│       └── anthropic_llm.py         # IMPLEMENTAR (SDK anthropic)
├── storage/
│   └── vector_store.py              # IMPLEMENTAR upsert()/search()
└── api/routes/
    ├── domains.py                   # MODIFICAR: disparar pipeline.py en segundo plano tras guardar
    └── query.py                     # IMPLEMENTAR endpoint real

tests/
├── unit/                             # chunking, citación, construcción de contexto
└── integration/                      # ingesta + consulta end-to-end contra Qdrant real
```

**Structure Decision**: se mantiene la estructura de proyecto único ya existente en `src/mia/`. Único
archivo nuevo: `src/mia/ingestion/pipeline.py`, para no mezclar la orquestación del pipeline dentro de
las rutas HTTP (mejor testeable de forma aislada).

## Complexity Tracking

*Sin violaciones de la constitución que justificar.*
