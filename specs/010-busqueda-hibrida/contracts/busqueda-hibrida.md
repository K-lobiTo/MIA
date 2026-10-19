# Contrato: Búsqueda híbrida

Contrato interno de la feature (no cambia la forma de la respuesta de `POST /query`): las variables, los métodos nuevos del almacén, el módulo `mia.rag.lexical`, el comportamiento de la ruta y las salidas observables. Las rutas del panel están en [equivalencias-api.md](equivalencias-api.md).

## 1. Variables de entorno (`mia.config.Settings`)

| Variable | Campo | Valor por defecto | Significado |
|---|---|---|---|
| `QUERY_HYBRID_SEARCH` | `query_hybrid_search` | `off` | `on` enciende la búsqueda por palabras; cualquier otro valor se trata como `off` (con un aviso una vez) |
| `HYBRID_MAX_DOCS` | `hybrid_max_docs` | 10 (1 a 200) | un grupo es específico si aparece en como máximo este número de documentos de los dominios consultados (se cuentan documentos y no fragmentos: un apellido repetido en cada página de una tesis es un solo documento) |
| `HYBRID_TERM_CHUNKS` | `hybrid_term_chunks` | 200 (20 a 1000) | fragmentos que se piden por palabra y candidatos léxicos que se puntúan por coseno |
| `HYBRID_LEXICAL_LIMIT` | `hybrid_lexical_limit` | 20 (1 a 100) | candidatos léxicos que pasan a la fusión |
| `HYBRID_LEXICAL_SLOTS` | `hybrid_lexical_slots` | 3 (0 a 16) | lugares máximos de la lista final para fragmentos que solo llegaron por palabras |
| `HYBRID_MAX_GROUPS` | `hybrid_max_groups` | 8 (1 a 16) | grupos de la pregunta que se consultan |
| `HYBRID_MIN_TOKEN_LEN` | `hybrid_min_token_len` | 3 (3 a 6) | letras mínimas de una palabra para buscarla (el índice no guarda palabras de menos de 3 letras); no se aplica a la sigla ni a la forma que llegan de una equivalencia |
| `HYBRID_RRF_K` | `hybrid_rrf_k` | 60 (1 a 200) | constante de la fusión |
| `HYBRID_BUDGET_MS` | `hybrid_budget_ms` | 800 (0 a 30000) | tiempo máximo de espera de la parte léxica; 0 la espera sin tope. Es una red de seguridad, no el criterio de aceptación: SC-007 (0,2 s en p50, 0,5 s en p95) se evalúa con la espera y fusión de consultas normales |
| `HYBRID_EQUIVALENCES_TTL_SECONDS` | `hybrid_equivalences_ttl_seconds` | 60 (0 a 3600) | vigencia de la caché de la lista de equivalencias |

| `HYBRID_MIN_MATCH_RATIO` | `hybrid_min_match_ratio` | 0,5 (0,1 a 1,0) | un fragmento que solo llegó por palabras pasa si contiene más de esta fracción de las palabras específicas de la pregunta: con 0,5 la regla de la mayoría acordada (1 de 1, 2 de 2, 2 de 3, 3 de 4); con 1,0 exige todas |

## 2. Métodos nuevos de `VectorStore` (`mia.storage.vector_store`)

No son abstractos: el valor por defecto lanza `NotImplementedError`, que la ruta trata como "parte léxica no disponible".

```text
def ensure_text_index(self) -> None
def text_index_status(self) -> dict   # {"exists": bool, "params": {...}, "indexed": int, "points": int}
def drop_text_index(self) -> None
def match_chunks(self, domains: list[str], text: str, limit: int) -> list[tuple[str, str]]
def score_chunks(self, embedding: list[float], domains: list[str], chunk_ids: list[str]) -> list[SearchResult]
```

- `ensure_text_index`: crea el índice sobre `text` con los parámetros del modelo de datos. Si ya existe con los mismos parámetros no hace nada; si existe con otros lo reporta (no lo reemplaza solo).
- `match_chunks`: pares (id del fragmento, id del documento) de los fragmentos de los dominios dados cuyo `text` contiene todas las palabras de `text` (ya normalizado), como mucho `limit`. Usa `scroll` con `with_payload=["document_id"]`: no trae el texto.
- `score_chunks`: los fragmentos con esos ids y esos dominios, con texto, `document_id`, `domain`, `chunk_index` y `score` igual al coseno con `embedding`. Una consulta `query_points` con filtro de ids y de dominios; un id fuera de los dominios no se devuelve.
- Cualquier error de Qdrant (índice ausente, red, tiempo) sube como excepción; la ruta la convierte en caída a significado.

## 3. Módulo `mia.rag.lexical` (puro, sin Qdrant ni red)

```text
def hybrid_enabled(value: str) -> bool
def normalize(text: str) -> str                                  # minúsculas, sin tildes, "T.F.G." -> "tfg"
def words_of(text: str) -> list[str]                              # palabras (letras y dígitos) del texto normalizado
def query_groups(question: str, equivalences: list[Equivalence], max_groups: int, min_len: int) -> list[LexicalGroup]
def lexical_lookup(store, domains: list[str], groups: list[LexicalGroup], term_chunks: int, executor=None) -> list[LexicalGroup]
def pick_candidates(groups: list[LexicalGroup], max_docs: int, limit: int, elapsed_ms: int = 0, ratio: float = 0.5) -> LexicalOutcome
def order_lexical(candidates: list[LexicalCandidate], scored: list[SearchResult]) -> list[SearchResult]
def merge_hybrid(vector_results, lexical_results, limit: int, slots: int, k: int) -> list[SearchResult]
def hybrid_note(outcome: LexicalOutcome, merged_new: int, main_by_words: bool = False) -> str | None
def failure_note() -> str
def equivalences_failure_note() -> str
def warn_lexical_failure(exc: Exception) -> None                  # a lo sumo un aviso por minuto
```

- `query_groups`: normaliza la pregunta; si una palabra es la sigla de una equivalencia, el grupo lleva la sigla y cada forma desarrollada como alternativas; si la pregunta contiene la forma desarrollada como palabras consecutivas, esas palabras se reemplazan por un grupo con la forma y la sigla. Descarta palabras vacías y de menos de `min_len` letras (las alternativas que vienen de una equivalencia no se filtran), quita duplicados, no encadena equivalencias y devuelve como mucho `max_groups` grupos en el orden de la pregunta.
- `lexical_lookup`: una consulta `store.match_chunks(domains, alternativa, term_chunks)` por alternativa de cada grupo (en paralelo, con un `ThreadPoolExecutor` propio de hasta 8 hilos o el `executor` dado) y devuelve los grupos con `chunk_ids` (unión de las alternativas) y `documents` (documentos distintos de esos fragmentos). Cualquier excepción del almacén sube.
- `order_lexical`: los resultados de los candidatos (con su coseno) en el orden léxico: más grupos coincidentes, más peso y, a igualdad, más coseno; descarta los candidatos que no volvieron del almacén (fuera de los dominios).
- `pick_candidates`: recibe los grupos con `chunk_ids` y `documents` ya consultados y aplica la regla: específico si `documents <= max_docs`; con `n` grupos específicos (los ausentes cuentan) un fragmento pasa si coincide con más de `ratio * n` (`min(n, floor(n * ratio) + 1)`; con 0,5, `n // 2 + 1`); ordena por grupos coincidentes, peso por rareza y a igualdad queda a la espera del desempate por coseno; devuelve los mejores `limit`. Con `n = 0` no hay candidatos.
- `merge_hybrid`: RRF con `k` sobre la lista de significado (en su orden) y la léxica (ya con coseno, ordenada por grupos, peso y coseno). Los fragmentos solo léxicos son como mucho `slots`; el total no supera `limit`; si `lexical_results` está vacía devuelve `vector_results` sin cambios (mismo objeto, mismo orden, mismos `score`). Si actúa, cada resultado se devuelve en una copia con `score` igual a su valor de fusión.

Módulo `mia.rag.equivalences` (lectura de la lista de siglas, con la tabla `sigla_equivalences`):

```text
def get_equivalences(session) -> list[Equivalence]       # normalizada; caché en proceso de HYBRID_EQUIVALENCES_TTL_SECONDS (0 la desactiva)
def invalidate_equivalences() -> None                    # la llaman las rutas /equivalences tras cada escritura y las pruebas
```

## 4. Comportamiento de `POST /query`

Con `QUERY_HYBRID_SEARCH=off` (o un valor inválido): idéntico a hoy. El módulo de equivalencias no se consulta y no se toca la tabla.

Con `on`:

1. Tras la validación de permisos, topes de gasto y modo (sin cambios) y el embedding de la pregunta, se leen las equivalencias (caché de `HYBRID_EQUIVALENCES_TTL_SECONDS`) y se arman los grupos. Si hay al menos un grupo, se lanza la parte léxica en un hilo: una consulta `match_chunks(domains, alternativa, HYBRID_TERM_CHUNKS)` por alternativa de cada grupo, en paralelo (devuelve el id del fragmento y el de su documento, sin el texto).
2. Mientras tanto corre la búsqueda por significado exactamente como hoy (con o sin reranker, 009).
3. Se espera la parte léxica hasta `HYBRID_BUDGET_MS`. Se calculan los candidatos (`pick_candidates`), se obtienen sus textos y cosenos con un `score_chunks` y se fusionan con el resultado de `retrieve` (`merge_hybrid`).
4. La lista fusionada sustituye a la de `retrieve`. Si queda vacía y la pregunta limpia (008) está encendida, se repite la búsqueda por significado con la pregunta limpia y se aplica de nuevo la fusión con los mismos candidatos léxicos; después todo sigue igual (contexto de 007, citas de 006, modelo de lenguaje).
5. Si la parte léxica falla (excepción, índice ausente, tiempo agotado), la consulta sigue con el resultado de `retrieve` sin cambios, con un aviso (a lo sumo uno por minuto) y la nota de caída. Si lo que no se puede leer es la lista de equivalencias, la parte léxica sigue sin relacionar siglas, con el mismo aviso y la nota `Lista de siglas no disponible: se buscó sin equivalencias` (junto a la nota de lo que aportó, si aportó algo). Nunca devuelve un error por esa causa.
6. Si la fusión deja la lista vacía, la respuesta es "sin información suficiente" sin llamar al modelo.

Invariantes: el número de fragmentos que llega al modelo no supera el límite del modo (FR-006); el filtro de dominios es el de la consulta en las dos búsquedas (FR-004); no se agregan llamadas a modelos de lenguaje ni a servicios externos (FR-008); la estructura de `QueryResponse` no cambia (FR-014).

## 5. Salidas observables

- **Uso** (`QueryLog.reject_reason`), notas unidas con "; " en el orden reranker, híbrida, pregunta limpia, corte, regla de seguridad:
  - `Búsqueda híbrida: N por palabras, M nuevos`: `N` candidatos léxicos, `M` de ellos que entraron a la lista final y no estaban por significado; con el sufijo `, principal por palabras` si el fragmento principal de la lista final (el primero, que ordena el contexto) llegó solo por palabras. Solo si la parte léxica aportó al menos un candidato; sin candidatos, ninguna nota.
  - `Lista de siglas no disponible: se buscó sin equivalencias`: cuando la lista de equivalencias no se pudo leer.
  - `Búsqueda por palabras no disponible: se usó el significado`: cuando la parte léxica falló.
- **Registro del servidor** (INFO): `Búsqueda híbrida: %d grupos (%d específicos), %d candidatos, %d nuevos; hilo %d ms, espera y fusión %d ms (modo %s)`, donde el primer tiempo es lo que tardó el hilo léxico y el segundo lo que la consulta esperó de más tras la búsqueda por significado, más la fusión (el que evalúa SC-007); WARNING (a lo sumo uno por minuto): `La búsqueda por palabras falló (%s: %s): la consulta usa el significado`.
- **`scripts/linea_base.py registro`** cuenta las notas anteriores y resume la latencia de la parte léxica del registro INFO.

## 6. `scripts/palabras.py`

```text
python scripts/palabras.py estado   --env-file .env.produccion   # solo lectura: si el índice existe, sus parámetros, puntos indexados
python scripts/palabras.py preparar --env-file .env.produccion   # crea el índice de texto (idempotente) y espera a que se complete
python scripts/palabras.py quitar   --env-file .env.produccion   # quita el índice de texto (no toca vectores ni payload)
```

`preparar` y `quitar` escriben en Qdrant: piden confirmación (`--si` para saltarla) y se niegan si la URL no coincide con la colección esperada. No usan modelos ni red salvo Qdrant.
