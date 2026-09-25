# MIA — Memoria Institucional Académica

Herramienta de almacenamiento y consulta multi-dominio con RAG, para la memoria institucional de la Unidad.

Ver la definición conceptual completa en [Digital_Transformation_Framework/docs/propuestas/Definicion_Conceptual_Prototipo.md](../Digital_Transformation_Framework/docs/propuestas/Definicion_Conceptual_Prototipo.md), y los requerimientos técnicos y alcance del MVP en [docs/Definicion_Requerimientos_MVP.md](docs/Definicion_Requerimientos_MVP.md).

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

docker compose up -d qdrant
uvicorn mia.api.main:app --reload
```

La API queda en `http://localhost:8000/docs` (Swagger UI, cliente de prueba del MVP).

## Tests

```bash
pytest
```

## Spec-driven development

Este repo usa [Spec Kit](https://github.com/github/spec-kit) para el flujo de especificación con Claude Code (`.specify/`, skills en `.claude/skills/`). Ver `.specify/memory/constitution.md` para los principios del proyecto.
