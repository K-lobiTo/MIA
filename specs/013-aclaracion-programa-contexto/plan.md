# Implementation Plan: Aclaración de programa y contexto de conversación en el bot de WhatsApp

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-aclaracion-programa-contexto/spec.md`

## Summary

El bot responde "sin información" a las preguntas que no nombran el programa aunque varios programas tengan la respuesta, y no recuerda nada de la conversación. Esta feature agrega, **solo con reglas y sin modelo de lenguaje**, la opción 1 (aclaración) y la opción 3 (ventana de conversación) de la propuesta 10.1 del documento de requerimientos del bot.

Dos piezas:

1. **En la API** (`POST /bot/query`): cuando la búsqueda no deja nada sobre el umbral, una búsqueda vectorial adicional con el mismo embedding, más candidatos (`BOT_CLARIFY_CANDIDATES`) y un piso de similitud bajo agrupa por **programa** los fragmentos que además comparten una palabra con contenido con la pregunta (evidencia léxica: el puntaje solo no distingue "ambigua" de "sin relación", research R9) (el título de cada documento, "<PROGRAMA>: <SECCIÓN>", sin migración ni campo nuevo). Si salen dos o más programas, la respuesta lleva la lista de candidatos (`clarify`); si no, sigue siendo "sin información". La respuesta del bot también informa los programas de las fuentes (`programs`). Es un `BotQueryResponse` propio: `POST /query` no cambia ([contracts/bot-query-aclaracion.md](contracts/bot-query-aclaracion.md)).
2. **En el servicio del bot** (`mia-whatsapp`): un contexto de conversación en memoria, por persona (hash), con los **últimos 4 turnos**, vencimiento por inactividad y tope de personas. Con él se **resuelve la aclaración** (la persona contesta "Ciberseguridad" y el bot repite la pregunta original con ese programa) y se **recuerda el programa** (una pregunta siguiente sin programa que recibiría "sin información" o aclaración se reintenta una vez con el programa de la conversación) ([contracts/servicio-whatsapp-contexto.md](contracts/servicio-whatsapp-contexto.md)).

No hay migraciones ni cambios en el panel; `BOT_CLARIFY` (apagado por defecto) enciende la aclaración en la API. Antes de encenderlo, el umbral bajo se calibra con los seis documentos reales (research R9). No usa LangChain ni LangGraph.

## Technical Context

**Language/Version**: Python 3.12 (la API y el servicio del bot); sin cambios en TypeScript

**Primary Dependencies**: ninguna nueva. La API usa lo que ya tiene (`VectorStore.search` y `get_chunks`, SQLAlchemy, FastAPI); el servicio, `fastapi`, `httpx` y `pydantic-settings` como hoy.

**Storage**: **sin cambios**: ni tablas ni migraciones (la cabeza sigue en la `0007`). El contexto vive en la memoria del servicio y el programa de cada documento se calcula del primer fragmento (con caché por proceso).

**Testing**: `pytest` en `tests/unit/` (unidades de programa, búsqueda de decisión, `/bot/query`, regresión de `/query`) y en `whatsapp/tests/` (contexto, resolución, reintento, flujo, registro sin datos); el recorrido de punta a punta ampliando `tests/unit/test_bot_end_to_end.py`; casos de calibración en `scripts/datos/casos_aclaracion.json` con `scripts/calibrar_aclaracion.py` y la medición con los seis documentos reales en un Qdrant local ([quickstart.md](quickstart.md)).

**Target Platform**: los mismos despliegues de hoy (API en Railway, `mia-whatsapp` en Railway); variables nuevas opcionales.

**Project Type**: web-service (la API) y servicio del bot.

**Performance Goals**: las preguntas que hoy se responden no cambian de latencia ni de costo (la búsqueda adicional y el reintento ocurren solo en el camino de "sin información"); la búsqueda de decisión añade una consulta vectorial y, la primera vez por documento, la lectura de su primer fragmento (milisegundos).

**Constraints**: ninguna llamada nueva a modelos de lenguaje (SC-007); `POST /query` y los demás artefactos sin cambios de forma ni de comportamiento (FR-019); sin teléfono ni texto de mensajes en la base, en Uso ni en los registros (FR-010); memoria acotada (4 turnos por persona, tope de conversaciones, vencimiento); máximo una aclaración por pregunta; el texto por defecto sin contacto; sin guiones largos en nada generado; la batería del MVP 19 de 19 y las pruebas existentes sin cambios.

**Scale/Scope**: un bot hoy (la estructura admite varios); decenas a pocos miles de conversaciones activas. Toca `src/mia/config.py`, `.env.example`, `deploy/railway/variables.example.env`, `src/mia/rag/programs.py` (nuevo), `src/mia/api/routes/query.py` (`run_query` con un parámetro opcional), `src/mia/api/routes/bot_service.py`, `whatsapp/src/mia_whatsapp/{config,state,flow,api_client}.py`, `whatsapp/README.md`, `scripts/datos/casos_aclaracion.json`, `scripts/calibrar_aclaracion.py` y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. El bot sigue siendo un cliente de la API; la decisión de ambigüedad vive en la API, que es quien ve los documentos. Ningún artefacto nuevo duplica ni modifica el almacenamiento. |
| II. Pipeline modular e intercambiable | Cumple. Se usan los métodos existentes de `VectorStore` (`search`, `get_chunks`); no se agregan métodos a la interfaz ni se toca ninguna etapa del pipeline. |
| III. Independencia de proveedor de LLM | Cumple. No interviene ningún modelo de lenguaje. |
| IV. Extensibilidad de dominios sin fricción | Cumple y ayuda: un programa nuevo aparece entre los candidatos con solo cargar sus documentos con el título normalizado, sin configurar nada. |
| V. Trazabilidad de respuestas | Cumple. Las respuestas siguen citando sus documentos; la aclaración no responde con datos de ninguno, así que no hay respuesta sin fuente. |
| Datos sensibles | Cumple. El contexto no guarda teléfonos ni va a ninguna base; el texto por defecto de la aclaración no tiene contacto. |
| Stack base | Mismo Python, FastAPI, SQL y Qdrant; sin migraciones. |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION (variables, guía de normalización con la convención del título), el documento de requerimientos del bot (la 10.1 pasa de propuesta a implementada) y el README del servicio. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. El único punto que merece vigilancia es el umbral bajo, que se calibra con datos reales antes de encender `BOT_CLARIFY` (research R9), y la convención del título, que se documenta (R3).

## Project Structure

### Documentation (this feature)

```text
specs/013-aclaracion-programa-contexto/
├── plan.md              # Este archivo
├── research.md          # Decisiones (R1 a R11)
├── data-model.md        # Programa, respuesta del bot, contexto y variables
├── quickstart.md        # Cómo validar la feature
├── contracts/
│   ├── bot-query-aclaracion.md          # POST /bot/query con aclaración
│   └── servicio-whatsapp-contexto.md    # Orden de decisiones del servicio y configuración
└── tasks.md             # Lo genera /speckit-tasks (no este comando)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                     # + bot_clarify, bot_clarify_min_similarity, bot_clarify_max_programs
├── rag/programs.py               # NUEVO: título -> programa (nombre natural y clave), caché y agrupación por programa
└── api/routes/
    ├── query.py                  # run_query(..., clarify=None, extras=None): búsqueda de decisión en el camino sin información
    └── bot_service.py            # BotQueryResponse (clarify, programs); pasa la política de aclaración

whatsapp/src/mia_whatsapp/
├── config.py                     # + bot_context_*, bot_text_clarify (y su aviso de contacto)
├── state.py                      # + ConversationStore (turnos, vencimiento, tope)
├── api_client.py                 # QueryResult con clarify y programs
└── flow.py                       # resolución de la aclaración, reintento con programa recordado, respuesta de aclaración

tests/unit/
├── test_programs.py                 # título -> programa, nombre natural, clave, caché
├── test_bot_clarify.py              # búsqueda de decisión y BotQueryResponse (y regresión de /query)
└── test_bot_end_to_end.py           # + recorrido con aclaración, resolución y programa recordado
whatsapp/tests/
├── test_context.py                  # ConversationStore: 4 turnos, vencimiento, tope, sin datos
└── test_flow_clarify.py             # el orden de decisiones del contrato

scripts/datos/casos_aclaracion.json  # NUEVO: casos de calibración (ambiguas, de un solo programa y sin relación)
scripts/calibrar_aclaracion.py       # NUEVO: repite la medición con documentos reales en un Qdrant local
docs/ARQUITECTURA.md, docs/OPERACION.md, docs/Definicion_Requerimientos_Bot_WhatsApp.md, whatsapp/README.md   # actualizados
```

**Structure Decision**: sin servicios ni paquetes nuevos. Lo que ve la API (documentos y vectores) se queda en la API, en un módulo pequeño y puro (`rag/programs.py`); lo que sabe la conversación se queda en el estado del servicio, junto al resto del estado transitorio por persona.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
