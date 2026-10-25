# Implementation Plan: Bot de WhatsApp para atraer estudiantes (con imágenes asociadas a documentos)

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-10-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-bot-whatsapp-kapso/spec.md`

## Summary

Un canal nuevo de consulta a MIA por WhatsApp, construido sobre Kapso, en tres piezas: (1) un **servicio propio pequeño** (`whatsapp/`, Python con FastAPI) que recibe los avisos firmados de Kapso, confirma en milisegundos, consulta a la API, da formato al texto y responde con el texto y, si corresponde, una imagen; (2) **rutas nuevas en la API** para el bot (`/bot/messages` y `/bot/query`, con una credencial de servicio), para administrar los bots (`/bots`) y para gestionar y servir **imágenes asociadas a documentos** (`/domains/.../images` y `GET /media/{id}` pública); y (3) el panel, con un **módulo Bots** y un diálogo de **imágenes** en cada documento del Inventario.

El bot es un artefacto más en lo que importa: consulta con los dominios, el tope diario y el estado de un **artefacto asignado** que se cambia desde el panel en cualquier momento. Como la clave de un artefacto se guarda solo como hash, el servicio no la lleva: se identifica con una credencial de servicio y el número de Kapso del mensaje, y la API resuelve el artefacto (research R2). La consulta del bot ejecuta el **mismo código** que `POST /query` (`run_query`, R3), siempre en modo literal, así que topes, rechazos, citas y registro en Uso valen igual y los demás artefactos no cambian.

La cuota de mensajes, no el costo de modelos, es el límite real (2.000 al mes entre recibidos y enviados): el consumo del mes vive en la base de la API (`bot_message_counts`, R4), el bot se detiene al llegar al tope y el panel lo muestra. El resto de los límites (por persona, ráfagas, tamaño de la pregunta) viven en la memoria del servicio, acotados (R8). Las imágenes se guardan en la base (`document_images`, R5), se validan por su contenido y se envían a Kapso por un enlace público que cambia al reemplazarlas. Se envían las de los documentos que la respuesta cita (R6), por lo que el cierre de V3 (`QUERY_CITED_SOURCES=on`) es un prerrequisito de despliegue.

**Esta entrega funciona solo con el sandbox de Kapso** (decisión del 2026-10-24: por ahora no es posible más). Todo lo funcional se construye, se prueba y se acepta con el número de pruebas; las imágenes se verifican con el simulador si el sandbox no las admite (research R17). El camino a producción (registro en Meta, número propio, plan, campaña) está documentado en la sección 11 de [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md) y no se implementa ni se valida aquí; el diseño no cambia para ese paso, porque registrar un número de producción es registrar un bot nuevo.

El servicio se llama `mia-whatsapp` y atiende todos los números de WhatsApp (un bot nuevo es una fila en el panel); los bots incrustados en páginas web, que habrá más adelante, no pasan por él y son otra feature que llamará a la API directamente (research R16).

No usa LangChain ni LangGraph (decisión del 2026-10-21 en `docs/ARQUITECTURA.md`). El camino para escalar (sección 10 del documento de requerimientos) no es parte de esta feature.

## Technical Context

**Language/Version**: Python 3.12 (la API existente y el servicio nuevo) y TypeScript con React y Mantine (panel)

**Primary Dependencies**: la API no suma dependencias. El servicio nuevo usa `fastapi`, `uvicorn[standard]`, `httpx` y `pydantic-settings` (todas ya en el proyecto, con las mismas versiones mínimas); desarrollo con `pytest`, `pytest-asyncio` y `ruff`. Sin dependencias nuevas de npm. Sin biblioteca de imágenes (R5) ni de pruebas de red (R13: `httpx.MockTransport`).

**Storage**: SQL de la API (SQLite en desarrollo, Postgres en producción): tres tablas nuevas con dos migraciones aditivas (`0006_bots` con `bots` y `bot_message_counts`, `0007_imagenes_de_documentos` con `document_images`), ver [data-model.md](data-model.md). Qdrant no cambia. El servicio del bot no tiene almacenamiento propio: su estado transitorio vive en memoria.

**Testing**: `pytest` en `tests/unit/` para las rutas y las migraciones de la API (con el patrón de `conftest.py`: base SQLite por prueba y `TestClient`); `pytest` en `whatsapp/tests/` para el servicio, con Kapso y la API simulados con `httpx.MockTransport`; Vitest para el panel; un simulador local (`whatsapp/scripts/enviar_webhook.py` y `kapso_falso.py`) para recorrer el flujo sin Kapso; el sandbox de Kapso para la prueba real ([quickstart.md](quickstart.md)).

**Target Platform**: la API en Railway (servicio `MIA`), el servicio nuevo `mia-whatsapp` en Railway (creado por el usuario desde la interfaz con *Root Directory* `whatsapp`), el panel como sitio estático, Kapso en su sandbox (número de pruebas, sin número de producción en esta entrega) como canal y OpenRouter como hoy para el modelo.

**Project Type**: web-service (la API), un servicio nuevo (el bot) y el panel de administración (sitio web).

**Performance Goals**: texto en menos de 5 s en la mitad de los casos y en menos de 10 s en el 95 % (SC-001; línea base del modo literal 1,7 s y 5,0 s); confirmación al webhook siempre en menos de 10 s y en la práctica en milisegundos (SC-002); consultas simultáneas a la API acotadas a 5 (SC-007); costo medio por pregunta bajo 0,001 USD (SC-009).

**Constraints**: el único entorno de aceptación es el sandbox de Kapso (solo escriben los teléfonos registrados como de prueba; texto e interactivos según su documentación); modo literal siempre; sin contacto del programa en ningún texto (FR-017); la API nunca recibe ni guarda el teléfono de la persona (FR-027, SC-010); el consumo mensual persiste y el bot no envía nada al llegar al tope (FR-024, SC-008); los demás artefactos y las pruebas existentes no cambian (FR-039, SC-011, la batería del MVP da 19 de 19); migraciones solo aditivas con procedimiento de vuelta atrás documentado; ningún texto ni límite exige cambiar código (FR-008); sin guiones largos en nada generado; el plan gratuito de Kapso limita a 1 número, 2.000 mensajes al mes, 100 solicitudes por minuto y 1 GB de medios.

**Scale/Scope**: un bot hoy (la estructura admite varios), del orden de 500 a 1.000 preguntas al mes por la cuota; hasta 5 consultas simultáneas y 20 en cola. Toca `src/mia/config.py`, `.env.example`, `deploy/railway/variables.example.env`, `src/mia/storage/models.py`, las migraciones `0006` y `0007`, `src/mia/access/` (credencial de servicio en `keys.py` y `security.py`), `src/mia/bots/` (nuevo: consumo mensual y estado del bot), `src/mia/images/` (nuevo: validación y consulta de imágenes), `src/mia/api/routes/` (`bots.py`, `bot_service.py`, `images.py` y `media.py` nuevos; `query.py`, `inventory.py` y `main.py` modificados), `whatsapp/` (nuevo: el servicio), `scripts/servicios.py`, `scripts/probar_migracion.py`, `web/admin/` (módulo Bots y diálogo de imágenes) y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. El bot es un cliente de la API como cualquier artefacto: no toca Qdrant ni la base, solo llama a rutas de la API. Consulta con la configuración de un artefacto (dominios, modos, tope), no con una vía lateral. |
| II. Pipeline modular e intercambiable | Cumple. No se toca ninguna etapa del pipeline (carga, chunking, embeddings, vectores, LLM). El canal de WhatsApp queda detrás de un cliente propio del servicio (`mia_whatsapp.kapso`), así que cambiar de proveedor de WhatsApp es cambiar ese cliente. |
| III. Independencia de proveedor de LLM | Cumple. El bot no llama a ningún LLM: lo hace la API con la configuración del modo literal, como hoy. |
| IV. Extensibilidad de dominios sin fricción | Cumple. Las imágenes son opcionales y por documento; un dominio o documento nuevo funciona sin imágenes y sin migrar nada. Agregar un dominio al bot es editar los accesos del artefacto asignado desde el panel. |
| V. Trazabilidad de respuestas | Cumple. Cada respuesta del bot incluye los nombres de los documentos que la respaldaron (FR-014); las consultas del bot quedan en el registro de Uso con sus fuentes. Las imágenes salen solo de documentos citados. |
| Datos sensibles | Cumple, con un cuidado operativo. La constitución exige un control de acceso antes de exponer datos de personas por WhatsApp: el control es el acceso por artefacto (el bot solo ve los dominios que se le asignan), y el panel advierte al asignarlo, listando los dominios. No se asignan las actas del Consejo ni dominios con datos de personas. La API no recibe el teléfono de quien escribe. Las imágenes son públicas y se avisa al subirlas. |
| Stack base | Se agrega un servicio de Python con FastAPI, el mismo stack; tres tablas nuevas de SQL. Se actualiza `docs/ARQUITECTURA.md` (servicio nuevo, tablas, rutas, variables). |
| Alcance incremental y documentación viva | El pipeline base ya se validó (MVP, V2 y V3 cerradas). Se actualizan ARQUITECTURA, OPERACION (servicio, variables, despliegue, reversión), ESCALABILIDAD (cuota de mensajes), el documento de requerimientos del bot (pendientes resueltas) y la guía del panel (`web/admin/README.md`). |

Sin violaciones; la tabla de complejidad queda vacía. Un cuarto despliegue (el servicio) es consecuencia directa de la decisión del usuario del 2026-10-21 y de la separación entre canal y motor; las alternativas están en [research.md](research.md) R1.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. Lo que cruza la frontera de la feature es la credencial de servicio (R2), acotada a dos rutas, y las migraciones `0006` y `0007`, aditivas y con `downgrade` (R15). No se agregan dependencias a la API ni llamadas a modelos de lenguaje.

## Project Structure

### Documentation (this feature)

```text
specs/011-bot-whatsapp-kapso/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── bots-api.md           # rutas /bots del panel y el módulo Bots
│   ├── bot-servicio-api.md   # rutas /bot/messages y /bot/query para el servicio y su credencial
│   ├── imagenes-api.md       # rutas de imágenes, GET /media y el campo images de la consulta
│   └── servicio-whatsapp.md       # el servicio: aviso de Kapso, flujo por mensaje, envío, variables y textos
├── checklists/
│   └── requirements.md
└── tasks.md                  # lo genera /speckit-tasks
```

### Source Code (repository root)

```text
src/mia/
├── config.py                          # + bot_service_key, bot_monthly_message_cap, max_image_mb
├── access/
│   └── keys.py                        # + bot_service_key_matches (compare_digest; vacía = apagada)
├── bots/                              # NUEVO
│   ├── usage.py                       # mes en la zona de CAP_TIMEZONE, incremento atómico, consumo y tope
│   └── status.py                      # estado de un bot (ok, disabled, cap_reached, unknown_bot) y su motivo
├── images/                            # NUEVO
│   ├── validate.py                    # firma y final de PNG y JPEG, tamaño (puro)
│   └── lookup.py                      # imágenes de los documentos de las fuentes, en orden, una consulta
├── storage/
│   ├── models.py                      # + Bot, BotMessageCount, DocumentImage
│   └── migrations/versions/
│       ├── 0006_bots.py               # NUEVO: bots y bot_message_counts
│       └── 0007_imagenes_de_documentos.py   # NUEVO: document_images
└── api/
    ├── security.py                    # + require_bot_service
    ├── main.py                        # incluye los routers nuevos; CORS_ALLOW_METHODS suma PUT (rutas de imágenes)
    └── routes/
        ├── query.py                   # run_query(payload, artifact, session) extraída; + images en QueryResponse
        ├── bots.py                    # NUEVO: GET/POST/PATCH /bots (alcance global)
        ├── bot_service.py             # NUEVO: POST /bot/messages y POST /bot/query
        ├── images.py                  # NUEVO: rutas de imágenes por documento
        ├── media.py                   # NUEVO: GET /media/{public_id} pública
        └── inventory.py               # + image_count por documento

whatsapp/                                   # NUEVO: el servicio, paquete aparte
├── pyproject.toml                     # fastapi, uvicorn, httpx, pydantic-settings
├── Dockerfile                         # python:3.12-slim, usuario sin privilegios
├── railway.json                       # healthcheck /health
├── .env.example
├── README.md
├── src/mia_whatsapp/
│   ├── main.py                        # FastAPI: /health y /webhooks/kapso
│   ├── config.py                      # variables, rangos y textos por defecto
│   ├── webhook.py                     # firma, evento, lote, extracción de campos del aviso
│   ├── flow.py                        # el orden de decisiones por mensaje
│   ├── state.py                       # vistos, ventanas por persona, saludo, cola (memoria, acotado)
│   ├── api_client.py                  # /bot/messages y /bot/query con httpx
│   ├── kapso.py                       # envío de texto e imagen, limitador y un reintento
│   ├── format.py                      # Markdown a WhatsApp, fuentes, partición (puro)
│   └── logs.py                        # línea JSON por mensaje sin datos de la persona
├── scripts/
│   ├── enviar_webhook.py              # firma y envía un aviso de ejemplo al bot
│   └── kapso_falso.py                 # imita la API de Kapso e imprime lo recibido
└── tests/                             # firma, flujo, límites, formato, Kapso y API simulados

scripts/
├── servicios.py                       # + servicio mia-whatsapp en SERVICIOS
└── probar_migracion.py                # DESTINO 0007, BAJAR_A 0005

web/admin/src/
├── api/bots.ts                        # NUEVO: consultas y mutaciones de bots
├── api/images.ts                      # NUEVO: consultas y mutaciones de imágenes
├── api/types.ts                       # + tipos de bot e imagen; image_count en DocumentItem
├── auth/capabilities.ts               # + canManageBots
└── modules/
    ├── index.tsx                      # + entrada "Bots" (solo con alcance global)
    ├── bots/                          # NUEVO: BotsPage, BotCard, BotForm, advertencia de acceso público, utilidades y pruebas
    └── inventario/
        ├── TreeNode.tsx               # + botón "Imágenes" con contador en DocumentRow
        └── ImagenesDialog.tsx         # NUEVO: lista, subir, describir, ordenar, reemplazar, quitar y aviso de público

tests/unit/
├── test_bots.py                       # NUEVO
├── test_bot_service.py                # NUEVO
├── test_images.py                     # NUEVO
├── test_query_images.py               # NUEVO
├── test_bots_usage.py                 # NUEVO: mes, incremento atómico, estado y dominios del bot
├── test_image_validate.py             # NUEVO: firma y final de PNG y JPEG
├── test_cors.py                       # NUEVO: todo método de las rutas está permitido por CORS (el PUT de las imágenes)
├── test_migrations.py                 # + cabeza 0007, subida y bajada
├── test_servicios.py                  # + el servicio nuevo
└── test_config.py                     # + variables nuevas

.env.example                           # + BOT_SERVICE_KEY, BOT_MONTHLY_MESSAGE_CAP, MAX_IMAGE_MB
deploy/railway/variables.example.env   # + las mismas, y la sección del bot
docs/                                  # ARQUITECTURA, OPERACION, ESCALABILIDAD, Definicion_Requerimientos_Bot_WhatsApp
web/admin/README.md                    # + el módulo Bots y las imágenes
```

**Structure Decision**: dos paquetes de Python separados en el mismo repositorio, como ya conviven la API y los sitios: `src/mia/` (la API) y `whatsapp/` (el servicio, con su propio `pyproject.toml`, imagen y pruebas), que solo se hablan por HTTP. El servicio no importa `mia`, para que su imagen no arrastre `onnxruntime`, Qdrant ni el modelo de embeddings (R1). En la API, la lógica con reglas propias vive en módulos puros y probables sin HTTP (`mia/bots/`, `mia/images/`), igual que `rerank.py` y `lexical.py`, y las rutas son delgadas. La consulta del bot reutiliza `run_query` extraída de `query.py` sin cambiar su lógica, en el mismo módulo para no romper las pruebas que parchean ese módulo. En el servicio, `format.py` y `webhook.py` son funciones puras, `state.py` aísla la memoria acotada y `flow.py` es la única pieza que decide el orden, de modo que la tabla de [contracts/servicio-whatsapp.md](contracts/servicio-whatsapp.md) se corresponde con un solo archivo. El simulador (`whatsapp/scripts/`) permite recorrer el flujo completo sin Kapso.

Se descartan, con sus razones en [research.md](research.md): la lógica del bot dentro de la API con tareas en segundo plano (R1), pegar la clave del artefacto en una variable del bot (R2), un contador solo en memoria (R4), almacenamiento de objetos para las imágenes (R5) y una cola o un almacén de estado externos (R7, R8). Todo eso queda como camino de escala en la sección 10 del documento de requerimientos.

## Complexity Tracking

Sin violaciones que justificar.
