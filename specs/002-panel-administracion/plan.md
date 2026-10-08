# Implementation Plan: Panel de administración de MIA

**Branch**: `dev` (feature `002-panel-administracion`) | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-panel-administracion/spec.md`

## Summary

Construir el artefacto 1 de la versión 2: un panel web de administración (React) con tres módulos,
Inventario, Artefactos y accesos, y Uso, y los cambios de API que lo sostienen. La API suma unidades
académicas y carpetas al modelo de datos, un registro de artefactos con clave propia cuyos permisos de
dominios y modos aplica en cada consulta, topes diarios de gasto por artefacto y de toda la API
calculados sobre un registro de consultas con su costo real informado por el proveedor, y un modo de
respuesta por consulta con un modelo configurable por modo. El esquema pasa a migrarse con Alembic, y un
script de una sola vez reorganiza los datos ya cargados en la estructura nueva sin reprocesarlos.

## Technical Context

**Language/Version**: Python 3.12 (API); TypeScript 5 con React 19 (panel)

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic (nueva), `tzdata` (nueva), cliente de
OpenAI (para OpenRouter), `qdrant-client`; en el panel Vite 6, TanStack Query 5, React Router 7
(`HashRouter`) y gráficas en SVG propio

**Storage**: SQLite (desarrollo y tests) y Postgres en Neon (producción) para metadatos, ahora con
migraciones Alembic; Qdrant para vectores, sin cambios de estructura

**Testing**: pytest con `TestClient` y proveedores falsos; Vitest para funciones puras del panel; `tsc`
y `vite build`; `scripts/pruebas_mvp.py` contra una instancia real

**Target Platform**: API en Railway (contenedor Linux, una instancia); panel como sitio estático (Render
Static Sites o Vercel), en desarrollo con el proxy de Vite

**Project Type**: web service (API existente) más aplicación web (panel nuevo)

**Performance Goals**: árbol completo (162 documentos) en menos de 3 s (SC-008); el control de permisos
y topes suma menos de 50 ms a cada consulta

**Constraints**: prototipo de costo cero o casi cero (Railway Hobby, Neon free, Qdrant free); los cambios
de esquema deben aplicarse sobre la base de producción existente sin perder datos; la reorganización no
puede reprocesar documentos; nada de guion largo en textos (CLAUDE.md)

**Scale/Scope**: 2 unidades, 11 dominios, 162 documentos, 2 a 4 artefactos, cientos de consultas por
día; 38 requerimientos funcionales en 5 historias

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Almacenamiento y consulta desacoplados | El panel es un artefacto más que solo usa la API. Registrar artefactos y sus permisos refuerza el principio: un artefacto nuevo se agrega desde el panel, sin tocar el almacenamiento. | Cumple |
| II. Pipeline modular e intercambiable | Se mantiene la fábrica de `LLMProvider`; se le agrega modelo y esfuerzo por parámetro, y el resultado incluye el uso (tokens y costo) como campos opcionales que cada proveedor completa si puede. | Cumple |
| III. Independencia de proveedor de LLM | Cada modo elige proveedor y modelo por configuración, incluido uno local. El costo estimado con precios de respaldo cubre proveedores que no informan costo. | Cumple |
| IV. Extensibilidad de dominios sin fricción | Crear unidades, dominios y carpetas desde el panel no interrumpe la operación ni migra dominios existentes. La reorganización es un ajuste puntual y deliberado de los datos actuales, no un requisito para agregar dominios. | Cumple |
| V. Trazabilidad de respuestas | La consulta sigue citando documento y dominio; además el registro guarda las fuentes de cada respuesta. | Cumple |
| Restricción: datos sensibles en artefactos públicos | Los permisos por artefacto aplicados en la API son el mecanismo de control de acceso que esta restricción exige antes de un artefacto público. El registro de preguntas solo se ve con clave de administración. | Cumple |
| Restricción: stack base | Se agrega Alembic sobre SQLAlchemy; Postgres en producción ya estaba documentado. Requiere actualizar `docs/ARQUITECTURA.md` (tarea de cierre). | Cumple |
| Alcance incremental y documentación viva | El pipeline base ya está validado con datos reales (19 de 19). Las decisiones están en `docs/Definicion_Requerimientos_V2.md`; ARQUITECTURA.md y OPERACION.md se actualizan al implementar. | Cumple |

**Re-check post-diseño**: sin cambios. El diseño ([data-model.md](data-model.md),
[contracts/](contracts/)) no introduce violaciones; no hay entradas en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-panel-administracion/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones técnicas
├── data-model.md        # Fase 1: tablas, reglas y configuración
├── quickstart.md        # Fase 1: guía de validación
├── contracts/           # Fase 1: contratos de la API
│   ├── api-inventario.md
│   ├── api-artefactos.md
│   ├── api-consulta.md
│   └── api-uso.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
alembic.ini                          # nuevo, apunta a src/mia/storage/migrations
src/mia/
├── config.py                        # + ADMIN_KEY, topes, CORS, modos, MAX_UPLOAD_MB
├── api/
│   ├── main.py                      # + CORS, routers nuevos
│   ├── security.py                  # nuevo: dependencias require_admin y require_artifact
│   └── routes/
│       ├── domains.py               # cambia: unidad, carpeta, 409, 413, filtro por artefacto
│       ├── inventory.py             # nuevo: /inventory, /units, /folders
│       ├── artifacts.py             # nuevo: /artifacts
│       ├── config.py                # nuevo: /config
│       ├── query.py                 # cambia: clave, modo, permisos, topes, registro, feedback
│       └── usage.py                 # nuevo: /usage, /usage/queries, /usage/balance
├── access/                          # nuevo: lógica de dominio sin HTTP
│   ├── keys.py                      # generar, hashear y verificar claves
│   ├── permissions.py               # dominios y modos permitidos de un artefacto
│   └── caps.py                      # gasto del día y topes (zona horaria de los topes)
├── usage/                           # nuevo
│   ├── aggregate.py                 # indicadores, percentiles, series y tablas
│   └── balance.py                   # saldo de OpenRouter
├── rag/
│   ├── llm.py                       # cambia: LLMAnswer, fábrica con modelo y esfuerzo
│   ├── modes.py                     # nuevo: configuración y disponibilidad de modos
│   └── providers/*.py               # devuelven LLMAnswer (OpenRouter con usage y cost)
└── storage/
    ├── db.py                        # init_db aplica migraciones (stamp automático)
    ├── models.py                    # + Unit, Folder, Artifact, ArtifactUnit, ArtifactDomain, QueryLog
    ├── vector_store.py              # + set_domain(document_id, domain_id)
    └── migrations/                  # nuevo: env.py y versions/0001, 0002

scripts/
├── reorganizar_v2.py                # nuevo, de una sola vez
├── datos/reorganizacion_v2.json     # nuevo: mapeo de la sección 2.3 y el anexo A
├── pruebas_mvp.py                   # cambia: --clave y dominios nuevos
└── cliente.py                       # cambia: --clave

tests/unit/                          # + test_inventory, test_folders, test_artifacts,
                                     #   test_permissions, test_caps, test_query_access,
                                     #   test_usage, test_balance, test_migrations,
                                     #   test_reorganizacion

web/
├── (cliente actual)                 # cambia: campo para la clave de artefacto
└── admin/                           # nuevo: panel de administración
    ├── package.json, vite.config.ts, tsconfig.json, index.html
    └── src/
        ├── api/                     # cliente tipado de la API y manejo de la clave
        ├── modules/
        │   ├── inventario/          # árbol, búsqueda, crear, subir, sondeo de estado
        │   ├── artefactos/          # lista, formulario, clave de una sola vez, topes
        │   └── uso/                 # filtros, indicadores, gráfica, tablas, registro, saldo
        ├── components/              # menú lateral, diálogo de clave, avisos
        └── styles/                  # variables de color, modo claro y oscuro
```

**Structure Decision**: se mantiene la API en `src/mia` (un solo paquete) agregando dos paquetes de
lógica sin HTTP (`access/`, `usage/`) para poder probar permisos, topes y agregaciones sin levantar la
API. El panel es un proyecto Vite independiente en `web/admin/`, junto al cliente actual en `web/`, que
se reemplazará por `web/consulta/` en la especificación del artefacto 2. No se crea un paquete
compartido de frontend todavía (research, decisión 11).

## Orden de implementación sugerido

Cada paso deja la API funcionando y se puede probar solo, en el orden de prioridad del spec:

1. **Base** (bloquea todo): Alembic con `0001` y `0002`, modelos nuevos, `init_db` con stamp
   automático, configuración nueva, CORS, `require_admin`.
2. **US1**: `/inventory` y `/units`, script de reorganización con `set_domain` en Qdrant; panel con
   menú, diálogo de clave y árbol de solo lectura con búsqueda.
3. **US2**: crear unidades, dominios y carpetas; subida con carpeta, 413 y `already_existed`; panel con
   formularios, arrastrar y soltar y sondeo de estado.
4. **US3**: artefactos y claves, `require_artifact`, permisos en `/domains`, `/config` y `/query`,
   modos con proveedor por modo, `LLMAnswer`; registro de consultas y feedback; adaptar scripts y el
   cliente web actual; panel del módulo Artefactos.
5. **US4**: topes en `/query` y `/config`, datos de gasto en `/artifacts`; panel con barras y avisos.
6. **US5**: `/usage`, `/usage/queries`, `/usage/balance`; panel del módulo Uso.
7. **Cierre**: actualizar `docs/ARQUITECTURA.md`, `docs/OPERACION.md` (variables nuevas, migraciones,
   reorganización, publicación del panel) y `.env.example`; correr la reorganización en producción y
   `scripts/pruebas_mvp.py`.

**Despliegue**: todo se hace en `dev`. Al hacer el merge a `main`, Railway aplica las migraciones al
arrancar. La reorganización se corre después, en local contra producción. Antes del merge hay que
configurar `ADMIN_KEY` en Railway, porque desde ese momento `/query` exige clave de artefacto: conviene
registrar las instancias de consulta y actualizar los clientes en la misma ventana.

## Complexity Tracking

Sin violaciones de la constitución que justificar.
