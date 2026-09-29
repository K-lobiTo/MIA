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
| [specs/001-pipeline-ingesta-rag/](specs/001-pipeline-ingesta-rag/) | Spec, plan, research y tareas de la feature de ingesta + RAG. |

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d qdrant
uvicorn mia.api.main:app --reload
```

La API queda en `http://localhost:8000/docs` (Swagger UI, cliente de prueba del MVP). También se puede levantar todo el stack con `docker compose up`.

## Consultar la API

- **Cliente web tipo chat:** `cd web && npm install && npm run dev` abre `http://localhost:3000` (contra la API de Render; `MIA_API_URL=http://localhost:8000 npm run dev` para una local). Detalle en [web/README.md](web/README.md).
- **Cliente de terminal:** `python scripts/cliente.py` (usa la API de Render; `--url http://localhost:8000` para otra instancia). Muestra un menú para elegir uno o varios dominios y luego permite hacer preguntas en un ciclo: `:d` cambia de dominios, `:f` muestra los fragmentos citados, `:s` sale. Solo usa la biblioteca estándar de Python.
- **Swagger UI:** `https://mia-api-5qgh.onrender.com/docs` (o `/docs` en la instancia local). En `POST /query` se envían los ids de dominio, que se obtienen con `GET /domains`.

## Tests

```bash
pytest
ruff check src tests scripts

# Pruebas de aceptación contra una instancia con los datos de prueba cargados
python scripts/pruebas_mvp.py --url https://mia-api-5qgh.onrender.com
```

## Despliegue

Prototipo de costo cero: API en [Render](https://render.com) (plan free, `render.yaml`), metadata en Postgres de [Neon](https://neon.tech) (free), vectores en [Qdrant Cloud](https://cloud.qdrant.io) (free) y LLM Gemini (tier gratuito). Los documentos grandes se ingieren desde una instancia local apuntando a esas mismas bases. Pasos completos en [docs/OPERACION.md](docs/OPERACION.md).

## Spec-driven development

Este repo usa [Spec Kit](https://github.com/github/spec-kit) para el flujo de especificación con Claude Code (`.specify/`, skills en `.claude/skills/`). Ver `.specify/memory/constitution.md` para los principios del proyecto.
