# Implementation Plan: Modo "plantilla" en la Consulta

**Branch**: `dev` (feature `020-modo-plantilla`, sin rama propia) | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/020-modo-plantilla/spec.md`

## Summary

Se agrega un **tercer modo de respuesta, `plantilla`**, que reutiliza la configuración del modo con razonamiento (mismo proveedor, modelo, esfuerzo, precios y cantidad de resultados) con una **instrucción propia** (`TEMPLATE_SYSTEM_PROMPT`). La persona elige una plantilla guardada y la respuesta sigue su estructura con contenido solo de los documentos. Las plantillas viven en una **tabla nueva `response_templates`** (migración `0014`), de dos tipos: **del artefacto** (las gestiona la administración desde el panel) y **personales** (con sesión de la feature 015, para un artefacto o para todos). Se pueden escribir, pegar o **cargar desde un `.docx` o `.txt`** con los cargadores de la ingesta. La conversación guardada recuerda la plantilla usada (id y nombre en `conversation_turns`, nunca el contenido). El modo se habilita **por artefacto** (`artifacts.modes`, sin migración), cuenta en el tope diario y en el tope del razonamiento, y aparece en Uso como "plantilla".

Decisiones principales (detalle y alternativas en [research.md](research.md)):

- **Un modo más sobre el razonamiento**, sin variables de modelo nuevas, y una función `is_reasoning_class(mode)` que unifica los lugares donde el razonamiento tiene trato propio (topes, historial, configuración, Uso) (R1, R2).
- **La plantilla va en el mensaje del usuario, delimitada y declarada como dato**, no en la instrucción de sistema ni como parámetro nuevo de los proveedores: protege las reglas ante plantillas hostiles y evita tocar seis proveedores (R3).
- **Una tabla con clave de dueño** (`owner_key` + nombre normalizado) deja la unicidad por alcance en la base (R4).
- **Sin clave foránea en la vuelta guardada**: eliminar una plantilla no toca las conversaciones (R5).
- **Se pide por `template_id`, nunca por contenido**: la API resuelve la plantilla y aplica la visibilidad (R6).
- **Tres grupos de rutas** (Consulta, panel, conversaciones) con la autenticación existente (R7).
- **Archivos con los cargadores existentes**, mensajes fijos y sin guardar el archivo (R8).

## Technical Context

**Language/Version**: Python 3.12+ (API `mia`), TypeScript con React 19 (Consulta `web/consulta/` y panel `web/admin/`)

**Primary Dependencies**: FastAPI, SQLAlchemy y Alembic (ya existen); `python-docx` (ya existe, por el cargador de DOCX). Mantine, TanStack Query y Vite en los dos frontends. **Ninguna dependencia nueva.**

**Storage**: tabla nueva `response_templates` y dos columnas nulas en `conversation_turns` (migración aditiva `0014`) en la base SQL (SQLite en desarrollo, Postgres en producción). Qdrant no interviene (las plantillas no se indexan).

**Testing**: `pytest` en la raíz (modos, API de plantillas, panel, consulta, conversaciones, migración) y Vitest en `web/consulta/` y `web/admin/`. Las pruebas del modelo de lenguaje usan un proveedor falso (como `tests/unit/chat_de_prueba.py` y los de modos existentes), sin red.

**Target Platform**: Railway (API y sitios estáticos de la Consulta y el panel), Neon (Postgres).

**Project Type**: web-service (API) + dos aplicaciones web (Consulta y panel). Sin servicios nuevos.

**Performance Goals**: el modo plantilla no agrega llamadas: una consulta cuesta lo mismo que una de razonamiento (misma búsqueda, mismo modelo); la mediana del tiempo no pasa de un 25 % más que el razonamiento (SC-011).

**Constraints**: entorno de costo cero (sin servicios ni dependencias nuevas); el gasto del modo cuenta contra los topes del artefacto y del razonamiento; la plantilla es texto no confiable (puede traer instrucciones hostiles); el contenido de la plantilla no se guarda en Uso ni en los registros; mensajes y documentación en español, sin guion largo.

**Scale/Scope**: una tabla y una migración, un modo, 10 rutas nuevas (5 de la Consulta y 5 del panel) y una ampliada (conversaciones), un servicio de plantillas, un selector y un gestor en la Consulta, un diálogo y un modo en el panel, y la documentación. Cantidades pensadas para decenas de plantillas, no miles.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | **Cumple.** La Consulta y el panel hablan solo con la API; las plantillas viven del lado del almacenamiento de metadata y la API aplica la visibilidad en cada petición. Ningún artefacto toca la base. |
| II. Pipeline modular | **Cumple.** El modo se agrega al registro de modos por configuración, sin tocar el fragmentado, los embeddings ni el almacén vectorial; los cargadores de ingesta se reutilizan sin cambios. |
| III. Independencia del proveedor de LLM | **Cumple.** El modo hereda la configuración del razonamiento (proveedor y modelo por variable de entorno); no asume ningún proveedor y no agrega parámetros a las implementaciones. |
| IV. Extensibilidad de dominios | **No aplica.** Ningún dominio cambia; la migración es solo aditiva. |
| V. Trazabilidad de respuestas | **Cumple.** La respuesta en modo plantilla incluye las fuentes como los demás modos; la plantilla no es una fuente ni se cita. Una sección sin datos lo dice en lugar de inventar (FR-004 y FR-007). |
| Datos sensibles de personas | **Cumple con cuidado.** Las plantillas son texto de personas (se advierte que no deben llevar datos personales) y solo las ve su dueño o, las del artefacto, quienes consultan con él; su contenido no va a Uso ni a los registros. No expone dominios nuevos. |
| Estilo (sin guion largo, español) | **Cumple**: aplica a todos los artefactos y al código. |

Sin violaciones: no hace falta la tabla de complejidad. **Re-evaluación tras el diseño (Phase 1): sin cambios.** El único punto a vigilar es la fidelidad del modelo a la forma y su resistencia a plantillas hostiles (R3), que se mide con el quickstart (sección 5) y tiene una salida definida (parámetro dedicado en los proveedores).

## Project Structure

### Documentation (this feature)

```text
specs/020-modo-plantilla/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R1 a R13
├── data-model.md        # Phase 1: response_templates, conversation_turns, ajustes
├── quickstart.md        # Phase 1: guía de validación y medición
├── contracts/
│   └── plantillas-api.md  # Phase 1: rutas de la Consulta, del panel y cambios en /query
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                                       # + template_max_chars, template_max_per_user, template_max_per_artifact, template_file_max_mb
├── rag/
│   ├── modes.py                                    # PLANTILLA, MODE_IDS, is_reasoning_class, mode_config/mode_available del modo
│   ├── llm.py                                      # TEMPLATE_SYSTEM_PROMPT, build_template_block
│   └── history.py                                  # el trato del razonamiento (doble de historial, advertencia) vale para plantilla
├── access/caps.py                                  # el tope del razonamiento suma razonamiento y plantilla
├── templates/                                      # NUEVO paquete
│   ├── __init__.py
│   └── service.py                                  # visible_templates, resolve_template, validaciones, extract_text
├── api/routes/
│   ├── query.py                                    # mode "plantilla", template_id, bloque de plantilla, turno con plantilla
│   ├── config.py                                   # el modo en /config, tope del razonamiento
│   ├── usage.py                                    # ModeName incluye "plantilla"
│   ├── artifacts.py                                # ModeId incluye "plantilla"; template_count
│   ├── conversations.py                            # template_id y template_name en las vueltas
│   ├── templates.py                                # NUEVO: rutas de la Consulta (/templates...)
│   └── artifact_templates.py                       # NUEVO: rutas del panel (/artifacts/{id}/templates...)
├── api/main.py                                     # registra los dos routers
├── chat/service.py                                 # append_turn y lectura con la plantilla de la vuelta
└── storage/
    ├── models.py                                   # ResponseTemplate; ConversationTurn.template_id y template_name
    └── migrations/versions/0014_plantillas_de_respuesta.py   # NUEVO

web/consulta/src/
├── api/types.ts, api/consulta.ts, api/templates.ts # modo "plantilla", template_id, rutas de plantillas
├── state/modes.ts, state/templates.ts, state/conversation.ts   # selección y recuerdo de la plantilla, retomar conversación
├── components/
│   ├── ModePicker.tsx                              # ya ofrece los modos; sin cambios de estructura
│   ├── TemplatePicker.tsx                          # NUEVO: dos grupos, Del artefacto y Mías
│   ├── TemplatesDialog.tsx                         # NUEVO: crear, editar, cargar archivo y eliminar (personales)
│   └── Composer.tsx                                # muestra el selector de plantilla con el modo elegido
└── (pruebas junto a cada archivo)

web/admin/src/
├── api/types.ts, api/artifacts.ts, api/templates.ts   # ModeId, template_count, rutas del panel
├── modules/artefactos/
│   ├── ArtifactForm.tsx                            # tercer modo con advertencia de costo
│   ├── ArtifactCard.tsx                            # botón "Plantillas"
│   └── ArtifactTemplatesDialog.tsx                 # NUEVO: gestión del catálogo
└── modules/uso/ (Filters.tsx, QueryLog.tsx, KpiRow.tsx)  # modo "plantilla"

tests/unit/
├── test_template_modes.py                          # NUEVO: registro del modo, config heredada, topes y historial
├── test_templates_api.py                           # NUEVO: rutas de la Consulta, visibilidad, alcance, límites, archivos
├── test_templates_admin.py                         # NUEVO: rutas del panel, alcance, auditoría sin contenido
├── test_templates_query.py                         # NUEVO: consulta en modo plantilla, bloque, no_info, plantilla hostil, Uso
├── test_templates_conversations.py                 # NUEVO: la vuelta guarda id y nombre, retomar, plantilla eliminada
└── test_migrations.py                              # la 0014 (columnas, unicidad, CHECK, CASCADE) y la revisión esperada 0014

docs/
├── ARQUITECTURA.md                                 # modo plantilla, tabla, rutas, límites
├── OPERACION.md                                    # ajustes TEMPLATE_*, cómo habilitar el modo, migración 0014
└── Definicion_Requerimientos_V3.md / README de la Consulta  # si listan modos, actualizarlos
```

**Structure Decision**: se sigue la estructura existente (rutas en `api/routes/`, un paquete pequeño de dominio como `contacts/`, componentes de cada frontend, una migración por cambio de esquema). No hay servicios nuevos; los servicios `mia-whatsapp` y el futuro de correo no cambian.

## Riesgos

- **Fidelidad de forma y plantillas hostiles**: depende del modelo. Se mide (quickstart, sección 5); si no se alcanza SC-001 o SC-004, la salida es el parámetro dedicado en `LLMProvider.answer` o mover el bloque de la plantilla (research R3).
- **Una función por modo**: olvidar un sitio donde el razonamiento tiene trato propio (topes, historial, configuración, Uso) dejaría el modo "gratis" o sin tope. `is_reasoning_class` y una prueba que recorre los lugares (`test_template_modes.py`) lo cubren.
- **`formatAnswer` limitado** (negritas, listas, encabezados como negrita): una plantilla con subniveles o tablas se ve plana; aceptado en esta versión (R10 y Q3).
- **Retomar una conversación con la plantilla de otro alcance** (por ejemplo, una "para este artefacto" abierta desde otro artefacto): `resolve_template` la rechaza y el cliente pide elegir otra; se cubre con una prueba.
- **Despliegue**: la migración `0014` es aditiva; respetar la regla de `CLAUDE.md` (no desplegar una versión con menos migraciones que las de la base) y recordar que Railway no redespliega solo: `scripts/servicios.py encender MIA mia-panel` y el sitio de la Consulta correspondiente (`mia-computacion` y `mia-administracion`).
