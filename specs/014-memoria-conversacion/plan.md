# Implementation Plan: Memoria de conversación configurable por artefacto

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-11-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-memoria-conversacion/spec.md`

## Summary

Cada consulta a MIA llega sola: el modelo ve la pregunta actual y los fragmentos recuperados, y la Consulta administrativa no envía nada de su chat. Un seguimiento como "¿y cuánto cuesta?" no encuentra fragmentos y se corta en "sin información" antes de llegar al modelo. Esta feature da a cada artefacto una **memoria de conversación** editable desde el panel, en vueltas completas (0 a 10, por defecto 0), sin guardar nada en el servidor.

Cinco piezas:

1. **El parámetro** (`artifacts.context_turns`, `bots.context_turns`, migración aditiva `0008`): en la API de artefactos y de bots, en `GET /config` (para que la Consulta sepa cuántas vueltas enviar) y en el panel (formularios y tarjetas de Artefactos y de Bots) ([contracts/artefactos-memoria-api.md](contracts/artefactos-memoria-api.md), [contracts/bots-memoria-servicio.md](contracts/bots-memoria-servicio.md)).
2. **El historial en la consulta** (`POST /query` con `history` opcional): el cliente lo envía, la API lo valida y lo recorta a las últimas N vueltas y por tamaño según el modo (`rag/history.py`), y con memoria 0 lo ignora. Se entrega al modelo como un **bloque rotulado** dentro del mensaje de usuario ("Conversación anterior, solo para entender la pregunta; no es una fuente de datos"), igual para los cuatro proveedores, con una instrucción de sistema que dice que toda respuesta sale solo de los fragmentos, para que el cambio de modo a mitad del chat no contamine las respuestas ([contracts/query-historial-api.md](contracts/query-historial-api.md)).
3. **La reformulación de la búsqueda** (`rag/followup.py`): un seguimiento corto usa el historial también para buscar, con dos estrategias seleccionables (`HISTORY_REFORMULATION`: `rules` sin modelo, `model` con una llamada corta, u `off`) que se comparan con casos reales para fijar la predeterminada.
4. **La Consulta administrativa** envía las últimas N vueltas respondidas y muestra el aviso de cuántas recuerda.
5. **La memoria del bot**: el servicio la lee en cada mensaje de la respuesta de `/bot/messages` y dimensiona con ella su contexto de aclaración y programa recordado; el bot no recibe historial al modelo y sigue solo en modo literal.

Sin sesiones ni datos nuevos en reposo salvo los dos números; con la memoria en 0 todo es exactamente como hoy. No usa LangChain ni LangGraph.

## Technical Context

**Language/Version**: Python 3.12 (la API y el servicio del bot) y TypeScript con React y Mantine (panel y Consulta administrativa)

**Primary Dependencies**: ninguna nueva. La API usa lo que ya tiene (SQLAlchemy, FastAPI, los SDK de los proveedores); el panel y la Consulta, Mantine y TanStack Query como hoy.

**Storage**: SQL de la API (SQLite en desarrollo, Postgres en producción): **una migración aditiva** (`0008_memoria_de_conversacion`: `artifacts.context_turns` entero no nulo con 0 y `bots.context_turns` entero nulo), con `downgrade`. Qdrant no cambia. El historial no se guarda.

**Testing**: `pytest` en `tests/unit/` (historial, reformulación, consulta con historial, artefactos, bots, migración, regresión de `/query` y del bot), `pytest` en `whatsapp/tests/` (ventana con límite variable), Vitest en el panel y en la Consulta, y un script de medición (`scripts/medir_memoria.py`) con los casos de `scripts/datos/casos_memoria.json` sobre los seis documentos de los posgrados ([quickstart.md](quickstart.md)).

**Target Platform**: los mismos despliegues de hoy (API, panel, Consulta administrativa y servicio del bot en Railway); variables nuevas opcionales.

**Project Type**: web-service (la API), servicio del bot y dos sitios web (panel y Consulta).

**Performance Goals**: con memoria 0, ninguna diferencia de latencia ni de costo; con memoria N, el texto de entrada sube en proporción al historial (en una consulta típica, entre un cuarto y un tercio más con 4 vueltas) y, solo con la estrategia `model`, una llamada corta extra en los seguimientos.

**Constraints**: el historial nunca es fuente de datos (instrucción y rótulo explícitos); ningún mensaje de sistema puede entrar (`extra="forbid"`); nada del historial se guarda; `POST /query` sin historial y `POST /bot/query` no cambian; el bot no entrega historial al modelo; los topes diarios por artefacto y por modo siguen aplicando; sin guiones largos en nada generado; la batería del MVP 19 de 19 con memoria 0; sin dependencias nuevas.

**Scale/Scope**: unos pocos artefactos y un bot; conversaciones de hasta 10 vueltas. Toca `src/mia/storage/models.py` y la migración `0008`, `src/mia/config.py`, `.env.example`, `deploy/railway/variables.example.env`, `src/mia/rag/history.py` y `src/mia/rag/followup.py` (nuevos), `src/mia/rag/llm.py` y los proveedores (`answer(..., history=None)` y `rewrite`), `src/mia/api/routes/{query,artifacts,config,bots,bot_service}.py`, `whatsapp/src/mia_whatsapp/{state,flow,api_client}.py`, `web/admin/src/modules/{artefactos,bots}/` y su API, `web/consulta/src/`, `scripts/medir_memoria.py`, `scripts/datos/casos_memoria.json`, y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. La memoria viaja por la API y no toca el almacenamiento; los artefactos siguen siendo clientes de una única API. |
| II. Pipeline modular e intercambiable | Cumple. `LLMProvider.answer` gana un parámetro **opcional** (compatible hacia atrás) y se agrega un método **no abstracto** `rewrite`; ningún proveedor existente se rompe. El formato del historial es común a todos. |
| III. Independencia de proveedor de LLM | Cumple. El historial es texto plano dentro del mensaje, sin depender de la forma de chat de ningún proveedor; la reescritura cae a reglas si el proveedor no la implementa. |
| IV. Extensibilidad de dominios sin fricción | Cumple. No cambia nada para dominios ni documentos. |
| V. Trazabilidad de respuestas | Cumple y la protege: el historial está rotulado como no-fuente y la instrucción obliga a responder solo con los fragmentos recuperados, de modo que toda respuesta sigue citando documentos; una inferencia de razonamiento no se convierte en dato documental. |
| Datos sensibles | Cumple. El historial no se guarda ni se registra; solo viaja al modelo en esa consulta, igual que la pregunta actual. |
| Stack base | Mismo Python, FastAPI, SQL y Qdrant; una migración aditiva. |
| Alcance incremental y documentación viva | Se actualizan ARQUITECTURA, OPERACION (parámetro, variables, recortes, estrategias, costo, cómo volver atrás), `web/admin/README.md`, `web/consulta/README.md` y la sección del bot. |

Sin violaciones; la tabla de complejidad queda vacía.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. Los dos puntos a vigilar son el comportamiento del modelo ante el historial (no se puede probar con proveedores simulados: se mide con casos reales, research R9) y el costo (se mide con memoria 0 y con 4).

## Project Structure

### Documentation (this feature)

```text
specs/014-memoria-conversacion/
├── plan.md              # Este archivo
├── research.md          # Decisiones (R1 a R10)
├── data-model.md        # Columnas, historial, recortes y variables
├── quickstart.md        # Cómo validar la feature
├── contracts/
│   ├── query-historial-api.md       # POST /query con historial
│   ├── artefactos-memoria-api.md    # Artefactos, /config y el panel
│   └── bots-memoria-servicio.md     # Bots, /bot/messages y el servicio
└── tasks.md             # Lo genera /speckit-tasks (no este comando)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                          # + history_reformulation, history_max_*_chars, history_rewrite_max_tokens
├── storage/
│   ├── models.py                      # + Artifact.context_turns, Bot.context_turns
│   └── migrations/versions/0008_memoria_de_conversacion.py   # NUEVA
├── rag/
│   ├── history.py                     # NUEVO: HistoryTurn, sanitize_history, format_history
│   ├── followup.py                    # NUEVO: is_followup, search_question (rules y model), validación de la reescritura
│   ├── llm.py                         # build_user_message, HISTORY_INSTRUCTIONS, answer(history=None), rewrite (no abstracto)
│   └── providers/{openrouter,gemini,glm,anthropic}_llm.py    # usan build_user_message; OpenRouter implementa rewrite
└── api/routes/
    ├── query.py                       # QueryRequest.history, search_question, bloque en el mensaje, costo de la reescritura
    ├── artifacts.py                   # context_turns en create/update/out y su línea de registro
    ├── config.py                      # context_turns en artifact de /config con clave
    ├── bots.py                        # context_turns en create/update/out y su línea de registro
    └── bot_service.py                 # context_turns en la respuesta de /bot/messages

whatsapp/src/mia_whatsapp/
├── api_client.py                      # CountResult.context_turns
├── state.py                           # ConversationStore con límite por lectura (MAX_CONTEXT_TURNS)
└── flow.py                            # pasa el límite vigente al contexto

web/admin/src/                         # ArtifactForm/Card y BotForm/Card con el campo, y sus tipos y pruebas
web/consulta/src/
├── api/{consulta,types}.ts            # history en useAsk, context_turns en Config
├── state/history.ts                   # NUEVO: buildHistory(exchanges, turns) con sus pruebas
└── components/                        # aviso "Recuerda las últimas N preguntas"

tests/unit/
├── test_history.py, test_followup.py, test_query_history.py       # NUEVOS
├── test_query_history_{modos,memoria_cero,validacion,costo}.py     # NUEVOS (un archivo por historia)
├── historial_de_prueba.py                                         # NUEVO: el mundo simulado compartido
├── test_artifacts_memory.py, test_bots_memory.py                  # NUEVOS
└── test_migrations.py                                             # cabeza en 0008
whatsapp/tests/test_context.py, test_api_client.py, test_flow_clarify.py   # ampliadas
scripts/medir_memoria.py, scripts/datos/casos_memoria.json         # NUEVOS
docs/ARQUITECTURA.md, docs/OPERACION.md, web/admin/README.md, web/consulta/README.md, docs/Definicion_Requerimientos_Bot_WhatsApp.md   # actualizados
```

**Structure Decision**: sin servicios ni paquetes nuevos. Lo que ve el historial (validarlo, recortarlo y formatearlo) y la reformulación son dos módulos pequeños y puros de `rag/`, probables sin HTTP; los proveedores solo cambian su forma de armar el mensaje de usuario, con una función compartida.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
