# Implementation Plan: Reranker local (reordenar los candidatos de la búsqueda)

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-reranker-local/spec.md`

## Summary

Una pieza nueva e intercambiable, `RerankProvider` (módulo `mia.rag.rerank`, con fábrica por nombre y la variable `RERANK_PROVIDER`: `none` por defecto, `local`), que puntúa cuánto responde cada fragmento a la pregunta. La implementación `local` corre dentro de la API con `onnxruntime` y `sentencepiece`, igual que los embeddings, usando `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` en su variante ONNX int8 oficial (119 MB, Apache 2.0, ver [research.md](research.md) R1).

Con `RERANK_PROVIDER=local`, `POST /query` cambia solo la etapa de recuperación: pide a Qdrant `RERANK_CANDIDATES` fragmentos (30 por defecto) en vez de los 8 o 16 del modo, el reranker los puntúa contra la pregunta original, y el corte de "sin información" pasa a ser el puntaje del reranker contra `RERANK_MIN_SCORE`, quedándose con los mejores hasta el límite del modo. El resto del flujo (contexto, citas, respuestas completas, pregunta limpia) recibe los fragmentos ya reordenados y no cambia. Con `none` la ruta es idéntica a la actual. Si el reranker falla o excede su presupuesto de tiempo, la consulta sigue con el orden y el umbral por coseno y deja una nota de Uso. No hay migraciones ni llamadas nuevas a ningún modelo de lenguaje.

La herramienta de la 005 gana: variante con reranker en `puntajes` (gratis, calcula el puntaje del reranker en local sobre Qdrant de producción en solo lectura), barrido del mínimo y ventana de separación, un subcomando `rendimiento` (memoria y latencia por número de candidatos, tokens por pasaje e hilos), y el conteo de notas del reranker en `respuestas`.

Hallazgo previo que condiciona el diseño (medición en esta máquina, R2): el modelo separa muy bien (pertinente 10,9 en logit, irrelevante entre -10 y -6, persona inventada -6,0), pero **la latencia con 30 candidatos y fragmentos completos es de 7 a 10 s**, muy por encima del límite de 0,5 s en p50 y 1,5 s en p95 de SC-006, y la memoria sube unos 154 MB (cerca del límite de 512 MB de SC-007 con los 340 MB actuales). Por eso el plan incluye palancas medibles (candidatos, tokens por pasaje, hilos, piso de coseno, presupuesto de tiempo) y asume que la prueba puede terminar en "no cumple los límites".

## Technical Context

**Language/Version**: Python 3.12 (API FastAPI existente)

**Primary Dependencies**: las existentes (`onnxruntime`, `sentencepiece`, `numpy`, `huggingface_hub`); sin dependencias nuevas. No se usan PyTorch, `transformers` ni `sentence-transformers`.

**Storage**: sin cambios de esquema ni migraciones; `QueryLog.reject_reason` para la nota; Qdrant no se reindexa

**Testing**: pytest (`tests/unit/`) con un reranker simulado (no se carga el modelo real), como `tests/unit/test_query_clean_question.py`; la verificación real es la corrida de la herramienta de la 005 y el subcomando `rendimiento` ([quickstart.md](quickstart.md))

**Target Platform**: API en Railway (se enciende solo para medir) y local para desarrollo y calibración

**Project Type**: web-service (API) más la herramienta de diagnóstico existente

**Performance Goals**: latencia añadida p50 <= 0,5 s y p95 <= 1,5 s con unos 30 candidatos y RAM de la API bajo 512 MB en reposo (SC-006 y SC-007, confirmados el 2026-10-18); cero llamadas nuevas a un modelo de lenguaje. Probablemente exige reducir tokens por pasaje o candidatos (R2)

**Constraints**: apagado por defecto y reversible por variable (BUS-6); sin migraciones ni reindexación; estructura de la respuesta intacta; un valor inválido de la variable no impide el arranque; un fallo del reranker nunca produce un error; ningún texto de la consulta sale a un servicio externo de reranking; compatible con las features 006 a 008; los permisos y topes de gasto se evalúan antes, como hoy

**Scale/Scope**: toca `src/mia/rag/rerank.py` (nuevo), `src/mia/rag/providers/local_rerank.py` (nuevo), `src/mia/config.py`, `.env.example`, `src/mia/api/main.py` (carga al arrancar), `src/mia/api/routes/query.py`, `Dockerfile`, `scripts/linea_base.py`, los casos de prueba y la documentación

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. Solo cambia cuántos candidatos se piden y cómo se ordenan en la API; el almacenamiento y los artefactos no se tocan. |
| II. Pipeline modular e intercambiable | Cumple y es la primera feature de V3 con una pieza nueva de verdad: `RerankProvider` es una interfaz con fábrica por nombre y variable de entorno, con la implementación `none` (no hace nada) y `local`. Cambiar de modelo o de proveedor no toca la ruta. |
| III. Independencia de proveedor de LLM | Cumple. No usa modelo de lenguaje. Como los embeddings, un reranker local no tiene costo variable por uso ni envía contenido a un tercero; puede ser una decisión permanente (R6). |
| IV. Extensibilidad de dominios | No aplica; el reranker puntúa fragmentos de cualquier dominio sin reindexar. |
| V. Trazabilidad de respuestas | Sin cambios: las fuentes siguen siendo las de los fragmentos que llegan al modelo (y las citas de la 006). La nota de Uso deja el mejor puntaje. |
| Datos sensibles | Cumple: el reranker corre dentro del servidor de la API; la pregunta y los fragmentos no salen a ningún reranking externo (FR-002). |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION (variables, memoria, medición), V3 (E, 2.7, 2.9) y LINEA_BASE_BUSQUEDA. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. No hay migraciones, ni dependencias nuevas, ni llamadas nuevas a modelos de lenguaje.

## Project Structure

### Documentation (this feature)

```text
specs/009-reranker-local/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── reranker.md
└── tasks.md             # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                       # + rerank_* (proveedor, candidatos, mínimos, tokens, hilos, presupuesto)
├── rag/
│   ├── rerank.py                   # NUEVO: RerankProvider, get_rerank_provider, rerank_candidates (puro), notas
│   └── providers/
│       └── local_rerank.py         # NUEVO: LocalRerankProvider (ONNX int8) y download_rerank_files
└── api/
    ├── main.py                     # carga el reranker al arrancar (si RERANK_PROVIDER=local) y registra la memoria
    └── routes/query.py             # recuperación con candidatos, rerank, corte por puntaje, caída a coseno, notas

scripts/linea_base.py               # variante con reranker en puntajes, barrido del mínimo, subcomando rendimiento
scripts/datos/casos_busqueda.json   # + casos de calibración que falten (sin respuesta y siglas)

tests/unit/
├── test_rerank.py                  # NUEVO: fábrica, selección por puntaje, empates, deadline, notas
├── test_query_rerank.py            # NUEVO: la ruta con el reranker apagado, encendido, caído y combinado con 006 a 008
├── test_local_rerank.py            # NUEVO: tokenización de pares y truncado, sin cargar el modelo real
└── test_linea_base.py              # + lo que se agrega a la herramienta

Dockerfile                          # + descarga del modelo del reranker en el build
.env.example                        # + variables RERANK_*
docs/                               # ARQUITECTURA, OPERACION, V3 (E, 2.7, 2.9), LINEA_BASE_BUSQUEDA
```

**Structure Decision**: módulo `rag/rerank.py` con la interfaz y la lógica pura (selección, empates, notas) más un proveedor en `rag/providers/`, el mismo reparto que los embeddings. La ruta gana una función auxiliar de recuperación que encapsula "buscar, reordenar, cortar" para que la segunda búsqueda de la feature 008 la reutilice. Se descartan: una API externa de reranking (privacidad, FR-002), PyTorch o `sentence-transformers` (memoria), un modelo más grande como BGE o Jina (no cabe, decisión del usuario), reordenar por heurísticas de texto (no resuelve la separación), y cambiar el umbral de coseno (opciones A y C, descartadas en la 005).

## Complexity Tracking

Sin violaciones que justificar.
