# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Instrucción general de estilo

**Nunca usar guión largo (—, em dash) en ningún documento o producto generado para este proyecto.** Usar en su lugar, según el caso: dos puntos, coma, punto y aparte, paréntesis, o guion corto/medio (-). Esto aplica a código, comentarios, documentación, mensajes de commit y cualquier texto generado.

## Comandos

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d qdrant        # Qdrant local para desarrollo

# Correr la API
uvicorn mia.api.main:app --reload  # http://localhost:8000/docs (Swagger)

# Tests
pytest
pytest tests/unit/test_health.py::test_health   # un solo test

# Lint
ruff check src tests scripts
```

## Arquitectura

Documentación completa y viva en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md): mantenerla actualizada cuando cambie algo relevante de cómo está implementado el sistema. El "por qué" de las decisiones de alcance y requerimientos está en [docs/Definicion_Requerimientos_MVP.md](docs/Definicion_Requerimientos_MVP.md). Despliegue, ingesta y límites del entorno gratuito en [docs/OPERACION.md](docs/OPERACION.md); camino a producción y alternativas descartadas en [docs/ESCALABILIDAD.md](docs/ESCALABILIDAD.md).

Resumen: una API FastAPI intermedia entre el almacenamiento (Qdrant + SQL: SQLite en desarrollo, Postgres en producción) y los futuros "artefactos" de consulta (chatbots, interfaces internas). El patrón central es interfaz + factory por nombre (`DocumentLoader`, `EmbeddingProvider`, `LLMProvider`, `VectorStore`), seleccionable por variable de entorno, para poder cambiar cualquier pieza del pipeline sin tocar el resto.

## Idioma y convenciones

- Documentación, nombres de dominio/conceptos en español.
- Frontend del panel (`web/admin/`): componentes de Mantine con el tema de `src/theme.ts`; las gráficas siguen siendo SVG propio. Reglas en [web/admin/README.md](web/admin/README.md#interfaz-mantine): leerlas antes de tocar la interfaz. Paletas de color candidatas (la #03 es la vigente) en [docs/PALETAS.md](docs/PALETAS.md).
- Despliegue: `scripts/servicios.py encender` despliega `origin/main` de GitHub (no la carpeta local; `--local` y `--ref` son la excepción). Flujo: trabajar en `dev`, merge a `main`, `git push origin main`, y recién entonces encender. La API migra la base al arrancar: no desplegar una versión con menos migraciones que las de la base (ver "Desplegar cambios" en `docs/OPERACION.md`).
- Sin atribución de Claude en commits ni PRs (`includeCoAuthoredBy: false` en `.claude/settings.json`).
- Spec Kit está instalado (`.specify/`, skills `speckit-*`) para uso opcional en flujos de especificación futuros.
