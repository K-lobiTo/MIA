# Quickstart: validar el pipeline de ingesta y consulta

## Prerrequisitos

```bash
cp .env.example .env
# Completar en .env (elegir un LLM_PROVIDER, ambos son intercambiables):
#   EMBEDDING_PROVIDER=local
#   LLM_PROVIDER=gemini
#   GEMINI_API_KEY=<tu key de Google AI Studio>
# o, si tienes crédito de Anthropic disponible:
#   LLM_PROVIDER=anthropic
#   ANTHROPIC_API_KEY=<tu key>
#   ANTHROPIC_EFFORT=medium          # opcional, "high" para respuestas más elaboradas (mayor costo)

docker compose up -d qdrant
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn mia.api.main:app --reload
```

## Escenario 1: ingesta (User Story 1)

```bash
curl -X POST http://localhost:8000/domains \
  -H "Content-Type: application/json" \
  -d '{"name": "Memoria del Consejo", "description": "Actas del Consejo de Unidad"}'
# Guardar el "id" devuelto como DOMAIN_ID

curl -X POST http://localhost:8000/domains/$DOMAIN_ID/documents \
  -F "file=@ruta/a/un/acta.pdf"
# Guardar el "id" devuelto como DOC_ID

# Esperar unos segundos y verificar el estado:
curl http://localhost:8000/domains/$DOMAIN_ID/documents
```

**Resultado esperado**: el documento pasa de `"pending"` a `"done"` en menos de 2 minutos (SC-001),
sin ninguna otra acción manual.

## Escenario 2: consulta con fuente citada (User Story 2)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"domains\": [\"$DOMAIN_ID\"], \"question\": \"<pregunta sobre algo que sí está en el acta subida>\"}"
```

**Resultado esperado**: `answer` refleja el contenido real del acta, y `sources` incluye el documento y
dominio subidos en el escenario 1 (SC-002).

## Escenario 3: reconocer falta de información (User Story 3)

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d "{\"domains\": [\"$DOMAIN_ID\"], \"question\": \"¿Cuál es la capital de Mongolia?\"}"
```

**Resultado esperado**: `answer` indica explícitamente falta de información, `sources` es una lista
vacía (SC-003).

## Escenario 4: deduplicación

Repetir la subida del mismo archivo del escenario 1 y confirmar que se devuelve el mismo `id` de
documento (no uno nuevo), y que no aumenta el conteo de puntos en la colección `mia_chunks` de Qdrant
(verificable en `http://localhost:6333/dashboard`, o vía `GET /collections/mia_chunks` de la API de
Qdrant).
