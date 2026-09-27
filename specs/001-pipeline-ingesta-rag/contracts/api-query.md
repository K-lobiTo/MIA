# Contrato: Consulta RAG

Endpoint: `POST /query` (ya definido en `docs/Definicion_Requerimientos_MVP.md`, sección 6; hoy es un
stub que lanza `NotImplementedError`). Esta feature implementa su comportamiento real.

## Request (sin cambios de forma)

```json
{"domains": ["<domain_id>", "..."], "question": "..."}
```

## Comportamiento

1. Generar el embedding de `question` con el `EmbeddingProvider` configurado.
2. Buscar en Qdrant (`VectorStore.search()`) filtrando por los `domains` recibidos, con un límite de
   resultados (ver `research.md`) y un umbral mínimo de similitud configurable.
3. **Si no hay resultados por encima del umbral**: responder sin llamar al LLM:
   ```json
   {"answer": "No encontré información suficiente en los dominios consultados para responder esta pregunta.", "sources": []}
   ```
4. **Si hay resultados**: armar el contexto con los fragmentos encontrados (texto, documento y
   dominio de origen de cada uno), pasarlo al `LLMProvider` configurado junto con una instrucción de
   sistema que exige basarse únicamente en ese contexto, y devolver:
   ```json
   {
     "answer": "<respuesta generada>",
     "sources": [
       {"domain": "...", "document": "...", "excerpt": "<fragmento citado>"}
     ]
   }
   ```
   `sources` lista únicamente los fragmentos que efectivamente se usaron como contexto (no
   necesariamente todos los que devolvió la búsqueda), para que la cita sea siempre verificable.

## Casos borde (del spec)

- Dominios inexistentes o sin documentos indexados: se trata igual que "sin resultados por encima del
  umbral", respuesta de "no hay información suficiente" (no es un error HTTP).
- `question` vacía o `domains` vacío: error de validación (HTTP 422, generado por FastAPI/Pydantic vía
  `Field(min_length=1)`), no llega a ejecutar la búsqueda.
- Proveedor de LLM no disponible (rate limit, error de red): se propaga como error HTTP 502 con un
  mensaje genérico; no forma parte del alcance de esta feature implementar reintentos avanzados más
  allá de los que ya trae cada SDK (Anthropic o Gemini) por defecto.
