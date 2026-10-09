# Contrato: cambios de la API para la Consulta

Cambios sobre el contrato de [specs/002-panel-administracion/contracts/api-consulta.md](../../002-panel-administracion/contracts/api-consulta.md),
que sigue vigente (encabezado `X-Artifact-Key`, orden de validación, `GET /config`, `GET /domains`,
`POST /query/{id}/feedback`). Todos los cambios son compatibles con los clientes actuales.

## POST /query

Request (cambia solo la validación):

```json
{"domains": ["d-1"], "question": "...", "mode": "razonamiento"}
```

- `question`: de 1 a 2000 caracteres; fuera de eso **422** con `detail` en la forma estándar de
  FastAPI (lista de errores). Se valida antes de registrar la consulta, como cualquier 422.

Respuesta (agrega `no_info`):

```json
{
  "id": "q-1",
  "answer": "**Lo que dicen los documentos**\n- Sistemas Operativos Avanzados (MC6004): 4 créditos ...\n\n**Conclusión**\nLos tres cursos suman 12 créditos (4 + 4 + 4).",
  "sources": [{"domain": "Currículum", "document": "MC6004-Sistemas Operativos Avanzados.pdf", "excerpt": "..."}],
  "mode": "razonamiento",
  "latency_ms": 31840,
  "no_info": false
}
```

- `no_info: true` cuando el resultado es "sin información suficiente" (sin fragmentos relevantes o el
  modelo respondió la marca): `answer` es el texto fijo de siempre y `sources` está vacío.

### Comportamiento por modo

| | `literal` | `razonamiento` |
|---|---|---|
| Instrucción al modelo | `RAG_SYSTEM_PROMPT` (la actual) | `REASONING_SYSTEM_PROMPT` |
| Resultados de la búsqueda | `QUERY_SEARCH_LIMIT` (8) | `QUERY_SEARCH_LIMIT_RAZONAMIENTO` (16) |
| Vecinos y documentos completos | `QUERY_CONTEXT_NEIGHBORS`, `QUERY_FULL_DOCUMENT_MAX_CHUNKS` | los mismos |
| Formato de la respuesta con información | libre (negritas y listas) | dos partes fijas: **Lo que dicen los documentos** y **Conclusión** (con la operación o la comparación solo si hizo falta combinar datos) |

Errores sin cambios: 401, 403, 429 (con `Retry-After`) y 502, con `{"detail": "..."}` legible.

## Interfaz interna de LLM (no HTTP)

`LLMProvider.answer(question, context, instructions)`: la instrucción al modelo llega como parámetro
en todos los proveedores (`openrouter`, `anthropic`, `gemini`, `glm`, `openai`, `local`), que dejan
de importar `RAG_SYSTEM_PROMPT` directamente. `local` y `openai` todavía no están implementados (lanzan `NotImplementedError`) y solo cambian su firma.
