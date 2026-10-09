# Implementation Plan: Consulta administrativa de MIA

**Branch**: `dev` (feature `003-consulta-administrativa`) | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-consulta-administrativa/spec.md`

## Summary

Construir el artefacto 2 de la versión 2: la Consulta administrativa, un sitio web de consulta (React)
que se abre con la clave de un artefacto y muestra su nombre, sus dominios y sus modos según la API,
publicado dos veces (Computación y Administración de Empresas) a partir de la misma compilación.
Reemplaza al cliente de `web/`, que se elimina. En la API, cada modo de respuesta pasa a tener su
propia instrucción al modelo y su cantidad de fragmentos (literal: la actual y 8; con razonamiento:
una instrucción que permite calcular, con dos partes fijas, y 16), y `POST /query` agrega `no_info` y
un largo máximo de pregunta. Los artefactos, permisos, topes, registro y calificación ya existen.

## Technical Context

**Language/Version**: Python 3.12 (API); TypeScript 5 con React 19 (Consulta)

**Primary Dependencies**: FastAPI, cliente de OpenAI para OpenRouter (sin cambios); en la Consulta
Vite 6 y TanStack Query 5, sin router ni biblioteca de Markdown

**Storage**: sin cambios de esquema (Postgres en Neon, Qdrant); la Consulta guarda en `localStorage`
solo la clave, los dominios y el modo

**Testing**: pytest con proveedores falsos para la API; Vitest para las funciones puras de la
Consulta; `tsc` y `vite build`; `scripts/pruebas_mvp.py` contra una instancia real (19 de 19 en
literal)

**Target Platform**: API en Railway (sin cambios de despliegue); Consulta como dos sitios estáticos en
Render Static Sites; en desarrollo con el proxy de Vite en el puerto 3000

**Project Type**: web service (API existente) más aplicación web (Consulta nueva)

**Performance Goals**: respuesta en menos de 15 s en literal y menos de 90 s con razonamiento, en 9
de cada 10 preguntas (SC-008); primera pregunta en menos de 2 minutos desde que se recibe el enlace
(SC-001)

**Constraints**: costo cero o casi cero (sitios estáticos gratuitos); la Consulta no guarda la
conversación (aclaración del 2026-10-08); una consulta a la vez por pestaña y 200 s de espera; nada
de guion largo en textos (CLAUDE.md)

**Scale/Scope**: 2 instancias, unas pocas personas por unidad, decenas a cientos de consultas por día;
27 requerimientos funcionales en 5 historias

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Almacenamiento y consulta desacoplados | La Consulta es un artefacto más que solo usa la API con su clave; publicar una instancia nueva no toca el almacenamiento. | Cumple |
| II. Pipeline modular e intercambiable | La instrucción al modelo pasa por la interfaz `LLMProvider` como parámetro; cada proveedor sigue siendo intercambiable. La cantidad de fragmentos por modo es configuración. | Cumple |
| III. Independencia de proveedor de LLM | Cada modo sigue eligiendo proveedor y modelo por configuración; las instrucciones no dependen de un proveedor. | Cumple |
| IV. Extensibilidad de dominios sin fricción | Un dominio nuevo aparece en la Consulta al recargarla, sin publicar de nuevo (SC-005). | Cumple |
| V. Trazabilidad de respuestas | Ambos modos citan documentos y dominios; el razonamiento además nombra el documento de cada dato usado. "Sin información" no muestra fuentes porque no responde nada. | Cumple |
| Restricción: datos sensibles en artefactos públicos | La Consulta es pública en internet, pero sin clave válida no ve nada, y los permisos por artefacto (aplicados en la API) impiden que una unidad vea dominios de otra (SC-004). La conversación no se guarda en el navegador. | Cumple |
| Restricción: stack base | Sin cambios en la API ni en el almacenamiento más allá de configuración. `docs/ARQUITECTURA.md` se actualiza por la Consulta y el retiro del cliente anterior. | Cumple |

**Re-check post-diseño**: sin cambios. El diseño ([data-model.md](data-model.md),
[contracts/](contracts/)) no introduce violaciones; no hay entradas en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/003-consulta-administrativa/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones técnicas
├── data-model.md        # Fase 1: configuración por modo y estado de la Consulta
├── quickstart.md        # Fase 1: guía de validación
├── contracts/
│   ├── api-consulta-modos.md   # cambios de /query y de la interfaz LLMProvider
│   └── ui-consulta.md          # llamadas, pantallas, estados y mensajes de la Consulta
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                        # + QUERY_SEARCH_LIMIT_RAZONAMIENTO
├── api/routes/query.py              # instrucción y fragmentos del modo, no_info, largo máximo
└── rag/
    ├── llm.py                       # + REASONING_SYSTEM_PROMPT; answer(..., instructions)
    ├── modes.py                     # ModeConfig + instructions y search_limit
    └── providers/*.py               # reciben la instrucción como parámetro

tests/unit/                          # + test_modes_config (instrucción y límite por modo),
                                     #   cambios en test_query_access, test_openrouter_llm,
                                     #   test_glm_llm y proveedores falsos

web/
├── README.md                        # nuevo y breve: presenta admin/ y consulta/
├── (cliente anterior)               # se elimina: index.html, src/, package*.json, tsconfig, vite.config
├── admin/                           # sin cambios
└── consulta/                        # nuevo
    ├── package.json, vite.config.ts, tsconfig.json, index.html, README.md
    └── src/
        ├── api/                     # client.ts (clave, 200 s, ApiError), consulta.ts (hooks), types.ts
        ├── state/                   # selección de dominios y modo guardados; disponibilidad (puras)
        ├── format/                  # formateador de respuestas a bloques (puro) y su componente
        ├── components/              # KeyScreen, Header, DomainPicker, ModePicker, Conversation,
        │                            # Exchange (respuesta, fuentes, error, calificación), Composer
        └── styles/                  # tokens con modo claro y oscuro, base

scripts/pruebas_mvp.py               # sin cambios de interfaz (ya acepta --modo)
docs/                                # OPERACION (publicación de las instancias, variable nueva),
                                     # ARQUITECTURA, PRUEBAS_MVP, README.md, ESCALABILIDAD
```

**Structure Decision**: la API sigue en `src/mia` con cambios acotados a `rag/` y a la ruta de
consulta. La Consulta es un proyecto Vite independiente en `web/consulta/`, junto al panel, sin
paquete compartido (research, decisión 7). El cliente anterior de `web/` se elimina en esta entrega.

## Orden de implementación sugerido

1. **API por modo** (bloquea la historia 2): `instructions` en la interfaz y los proveedores,
   `REASONING_SYSTEM_PROMPT`, `search_limit` por modo, `no_info` y largo máximo en `/query`, con sus
   pruebas. Compatible con los clientes actuales.
2. **Base de la Consulta**: proyecto Vite, cliente de la API con clave y tiempo de espera, estilos,
   pantalla de clave y encabezado con el nombre.
3. **US1**: dominios agrupados y recordados, envío, conversación, formateador, fuentes, "sin
   información".
4. **US2**: selector de modo, aviso de espera, pie con modo y tiempo; validar el criterio 7.
5. **US3**: disponibilidad de modos y envío según `/config`, mensajes de error y reintentos, refresco
   tras 403 y 429.
6. **US4**: calificación con comentario.
7. **US5 y cierre**: eliminar el cliente anterior, documentación (publicación, `CORS_ORIGINS`,
   variable nueva), validación del quickstart y `pruebas_mvp.py`.

**Despliegue**: todo en `dev`. El merge a `main` despliega la API en Railway (cambios compatibles; la
variable nueva tiene valor por defecto). Publicar los dos sitios en Render y agregar sus direcciones
a `CORS_ORIGINS` lo hace quien administra MIA, siguiendo `docs/OPERACION.md`.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
