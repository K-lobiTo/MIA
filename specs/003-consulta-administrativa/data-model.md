# Data Model: Consulta administrativa de MIA

Esta entrega **no cambia el esquema de la base**: no hay tablas, columnas ni migraciones nuevas. Los
artefactos, permisos, topes, el registro de consultas (`queries`) y la calificación ya existen
(ver [specs/002-panel-administracion/data-model.md](../002-panel-administracion/data-model.md)).

Lo nuevo es configuración de la API por modo y estado del lado de la Consulta.

## Modo de respuesta (configuración, sin tabla)

`ModeConfig` en `src/mia/rag/modes.py` suma dos campos a los que ya tiene (proveedor, modelo,
esfuerzo, precios de respaldo):

| Campo | Literal | Con razonamiento | Origen |
|---|---|---|---|
| `instructions` | `RAG_SYSTEM_PROMPT` (sin cambios) | `REASONING_SYSTEM_PROMPT` (nueva) | código (`src/mia/rag/llm.py`) |
| `search_limit` | `QUERY_SEARCH_LIMIT` (8) | `QUERY_SEARCH_LIMIT_RAZONAMIENTO` (16) | variables de entorno |

Reglas:

- `search_limit` es un entero de 1 a 50; fuera de ese rango la configuración falla al arrancar.
- Los vecinos y los documentos completos cortos (`QUERY_CONTEXT_NEIGHBORS`,
  `QUERY_FULL_DOCUMENT_MAX_CHUNKS`) son los mismos para ambos modos.
- Ambas instrucciones conservan la marca `SIN_INFORMACION`: la API la traduce en la respuesta
  "sin información suficiente" con `no_info: true` y sin fuentes.

## Configuración nueva de la instancia

| Variable | Por defecto | Uso |
|---|---|---|
| `QUERY_SEARCH_LIMIT_RAZONAMIENTO` | `16` | Resultados de la búsqueda en modo con razonamiento |

`CORS_ORIGINS` ya existe; en producción suma las direcciones de las dos instancias publicadas.

## Estado de la Consulta (navegador)

Guardado en `localStorage` de la dirección de cada instancia (cada dirección tiene su propio
almacenamiento, FR-023). Lectura y escritura dentro de `try/catch`; sin almacenamiento, todo vive en
memoria hasta cerrar la pestaña.

| Clave | Contenido | Reglas |
|---|---|---|
| `mia-consulta-key` | Clave del artefacto (`mia_...`) | Se borra cuando la API responde 401 (FR-001) |
| `mia-consulta-dominios` | Lista de ids de dominios seleccionados | La primera vez, todos; al cargar se descartan los ids que ya no están permitidos (FR-006) |
| `mia-consulta-modo` | `literal` o `razonamiento` | Si ya no está permitido o disponible, se usa el primero disponible y se avisa |

**No se guarda** la conversación (FR-020).

## Conversación (memoria de la página)

Cada intercambio vive solo mientras la página está abierta:

| Campo | Descripción |
|---|---|
| `localId` | Identificador local del intercambio |
| `question` | Texto enviado |
| `domainIds` | Dominios seleccionados al enviar |
| `mode` | Modo pedido |
| `status` | `pending` → `answered`, `no_info` o `failed` |
| `response` | Respuesta de la API (`id`, `answer`, `sources`, `mode`, `latency_ms`, `no_info`) |
| `error` | Si falló: estado HTTP, mensaje legible, si se puede reintentar y si se ofrece reintentar en literal |
| `rating` | `util`, `no_util` o nada; con `comment` opcional; solo si hay `response` |

Transiciones:

```text
pending ── 200, no_info=false ──> answered ── calificar ──> answered (con rating)
pending ── 200, no_info=true ───> no_info  ── calificar ──> no_info (con rating)
pending ── error o tiempo agotado ─> failed ── reintentar ──> (nuevo intercambio pending)
                                     failed ── reintentar en literal (si era razonamiento) ──> (nuevo pending, modo literal)
```

Un intercambio `failed` no se puede calificar (Historia 4, escenario 4).
