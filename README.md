# MIA: Memoria Institucional Académica

Herramienta de almacenamiento y consulta multi-dominio con RAG, para la memoria institucional de la Unidad.

Ver la definición conceptual completa en [Digital_Transformation_Framework/docs/propuestas/Definicion_Conceptual_Prototipo.md](../Digital_Transformation_Framework/docs/propuestas/Definicion_Conceptual_Prototipo.md), y los requerimientos técnicos y alcance del MVP en [docs/Definicion_Requerimientos_MVP.md](docs/Definicion_Requerimientos_MVP.md).

## Documentación

| Documento | Para qué |
|---|---|
| [docs/Definicion_Requerimientos_MVP.md](docs/Definicion_Requerimientos_MVP.md) | Alcance, requerimientos y decisiones del MVP (el "por qué"). |
| [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) | Cómo está implementado el sistema hoy. |
| [docs/OPERACION.md](docs/OPERACION.md) | Despliegue, ingesta de documentos, variables de entorno, límites conocidos y problemas frecuentes. |
| [docs/ESCALABILIDAD.md](docs/ESCALABILIDAD.md) | Qué cambiar para llevar el prototipo a producción, y qué se probó y descartó. |
| [docs/PRUEBAS_MVP.md](docs/PRUEBAS_MVP.md) | Criterios de aceptación del MVP, datos de prueba y `scripts/pruebas_mvp.py` para verificarlos. |
| [docs/Definicion_Requerimientos_V2.md](docs/Definicion_Requerimientos_V2.md) | Requerimientos de la versión 2: panel de administración, artefactos con su acceso y topes, y las dos instancias de la Consulta administrativa. |
| [specs/001-pipeline-ingesta-rag/](specs/001-pipeline-ingesta-rag/) | Spec, plan, research y tareas de la feature de ingesta + RAG. |
| [specs/002-panel-administracion/](specs/002-panel-administracion/) | Spec, plan, contratos de la API, tareas y guía de validación del panel de administración. |

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d qdrant
uvicorn mia.api.main:app --reload
```

La API queda en `http://localhost:8000/docs` (Swagger UI). También se puede levantar todo el stack con `docker compose up`. Para gestionar la información y los accesos, definir `ADMIN_KEY` en `.env` (sin ella, crear dominios, subir documentos y gestionar artefactos responden 503).

## Panel de administración

`cd web/admin && npm install && npm run dev` abre `http://localhost:3001` contra la API local (`MIA_API_URL=<url> npm run dev` para otra). Gestiona el **inventario** (unidades académicas, dominios, carpetas y documentos), los **artefactos y sus accesos** (clave propia, dominios y modos permitidos, topes de gasto) y el **uso** (gasto, consultas, tokens, registro y saldo). Pide la clave de administración (`ADMIN_KEY`). Detalle en [web/admin/README.md](web/admin/README.md).

## Consultar la API

Desde la versión 2 las consultas exigen la clave de un artefacto, que se registra en el panel y se envía en `X-Artifact-Key`; la API solo muestra y consulta los dominios y modos que ese artefacto tiene permitidos.

- **Consulta administrativa (web):** `cd web/consulta && npm install && npm run dev` abre `http://localhost:3000` (`MIA_API_URL=<url> npm run dev` para elegir la API). Pide la clave del artefacto (la de cada instancia, generada en el panel), muestra solo sus dominios y modos, y permite calificar las respuestas. Detalle en [web/consulta/README.md](web/consulta/README.md).
- **Cliente de terminal:** `python scripts/cliente.py --url <url> --clave mia_...` (o `MIA_ARTIFACT_KEY`). Muestra un menú para elegir uno o varios dominios y luego permite hacer preguntas en un ciclo: `:d` cambia de dominios, `:m` de modo, `:f` muestra los fragmentos citados, `:s` sale. Solo usa la biblioteca estándar de Python.
- **Swagger UI:** `<url>/docs`. En `POST /query` se envían los ids de dominio (que se obtienen con `GET /domains`) y el encabezado `X-Artifact-Key`.

## Tests

```bash
pytest
ruff check src tests scripts

cd web/admin && npm test            # pruebas del panel
cd web/consulta && npm test         # pruebas de la Consulta

# Pruebas de aceptación contra una instancia con los datos reales cargados (clave de un artefacto con acceso a las dos unidades)
python scripts/pruebas_mvp.py --url https://mia-main.up.railway.app --clave mia_...
```

## Despliegue

Prototipo de costo casi cero: API en [Railway](https://railway.com) (plan Hobby, `railway.json`), metadata en Postgres de [Neon](https://neon.tech) (free), vectores en [Qdrant Cloud](https://cloud.qdrant.io) (free) y LLM por [OpenRouter](https://openrouter.ai) (saldo prepagado, con topes de gasto por artefacto). Los documentos se ingieren en el propio servidor, o desde una instancia local apuntando a esas mismas bases. El panel y la Consulta administrativa se publican como sitios estáticos. Pasos completos, y el checklist de puesta en producción de la versión 2, en [docs/OPERACION.md](docs/OPERACION.md).

## Spec-driven development

Este repo usa [Spec Kit](https://github.com/github/spec-kit) para el flujo de especificación con Claude Code (`.specify/`, skills en `.claude/skills/`). Ver `.specify/memory/constitution.md` para los principios del proyecto.
