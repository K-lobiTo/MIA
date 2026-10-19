# Data Model: Búsqueda híbrida

Una tabla nueva en SQL (la lista de equivalencias), un índice nuevo en Qdrant y valores en memoria que viven una consulta. No cambia ninguna tabla ni columna existente.

## SiglaEquivalence (tabla `sigla_equivalences`, migración `0005`)

Un par entre una sigla y una forma desarrollada. Es global: vale para todos los dominios y programas.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto (UUID) | clave primaria, como las demás tablas |
| `sigla` | texto | guardada normalizada: minúsculas, sin tildes, sin puntos ni espacios (`tfg`, `mgti`); de 3 a 20 caracteres de letras y dígitos (una sigla de menos de 3 letras no se busca, ver `HYBRID_MIN_TOKEN_LEN`) |
| `form` | texto | forma desarrollada normalizada: minúsculas, sin tildes, espacios simples (`trabajo final de graduacion`); de 3 a 120 caracteres, al menos una palabra de 3 letras o más |
| `sigla_display` | texto | la sigla como la escribió el operador (`TFG`), solo para mostrar |
| `form_display` | texto | la forma como la escribió el operador (`Trabajo Final de Graduación`), solo para mostrar |
| `created_by` | texto | correo de quien la creó, o `automatizacion` con la clave de los scripts (y para las semillas) |
| `created_at` | fecha y hora | UTC sin zona, como el resto |
| `updated_by` | texto, nulo | quién la editó por última vez |
| `updated_at` | fecha y hora, nulo | cuándo |

**Restricciones**: único (`sigla`, `form`) (el mismo par no se repite aunque cambien mayúsculas, tildes o espacios). Una sigla puede tener varias formas y una forma varias siglas. No hay llaves foráneas. Un par cuya `sigla` coincide con su `form` normalizada se rechaza.

**Semillas** (migración, idempotentes, `created_by = automatizacion`): `tfg` ↔ `trabajo final de graduacion`, `mgti` ↔ `gestion de tecnologias de informacion` y `mgti` ↔ `gestion de tecnologias de la informacion` (la forma se busca como palabras consecutivas, así que se siembran las dos redacciones habituales).

**Validación** (la API, ver [contracts/equivalencias-api.md](contracts/equivalencias-api.md)): textos no vacíos tras normalizar, longitudes acotadas, sin duplicar el par normalizado, y la forma desarrollada no puede ser una sola palabra igual a la sigla.

**Ciclo de vida**: se crea, se edita (la sigla y la forma) y se borra. No hay estados. El borrado es físico: la lista es de configuración, no de historial; el registro de administración (`mia.admin`) conserva quién hizo cada cambio.

## Índice de texto de Qdrant (colección existente)

| Propiedad | Valor |
|---|---|
| Campo | `text` (el texto de cada fragmento, ya guardado en el payload) |
| Tipo | índice de texto |
| Tokenizador | `prefix`, `min_token_len = 3`, `max_token_len = 15` |
| Normalización | `lowercase = true`, `ascii_folding = true` |
| Almacenamiento | `on_disk = true` (se confirma al medir) |
| Quién lo crea | el arranque de la API (`ensure_text_index` en `lifespan`) si `QUERY_HYBRID_SEARCH=on`, o `scripts/palabras.py preparar` |
| Cómo se quita | `scripts/palabras.py quitar` (no toca vectores, payload ni puntos) |

El índice no es una entidad que la API lea: es la capacidad que Qdrant da a los filtros `MatchText`. Los puntos nuevos entran con el `upsert` de siempre.

## Valores en memoria de una consulta (`mia.rag.lexical`)

- **Grupo léxico** (`LexicalGroup`): `terms` (una o más alternativas normalizadas: la palabra, o la sigla y su forma desarrollada), `chunk_ids` (identificadores de los fragmentos que contienen alguna alternativa, como mucho `HYBRID_TERM_CHUNKS`), `documents` (cuántos documentos distintos los contienen), `specific` (verdadero si `documents <= HYBRID_MAX_DOCS`, incluida la ausencia; lo calcula `pick_candidates`).
- **Candidato léxico** (`LexicalCandidate`): `chunk_id`, `matched` (cuántos grupos específicos contiene), `weight` (suma del peso por rareza de esos grupos), y después `result` (`SearchResult` con texto y coseno).
- **Resultado léxico** (`LexicalOutcome`): `groups`, `specific` (cuántos grupos específicos), `candidates` ordenados, `elapsed_ms` (lo que tardó el hilo léxico), `wait_ms` (lo que la consulta esperó de más tras la búsqueda por significado, más la fusión; es el tiempo de SC-007) y `failed` (verdadero si la parte léxica cayó a significado). Sirve para construir la nota de Uso y el registro.
- **Fusión** (`merge_hybrid`): recibe la lista de significado, los candidatos léxicos con su coseno, el límite del modo, las ranuras léxicas y `k`; devuelve la lista fusionada con `score` igual al valor de fusión, o la lista de significado intacta si no hay candidatos léxicos.

## Registro de consultas (`QueryLog.reject_reason`)

Sin columnas nuevas. La nota de la búsqueda híbrida se une con "; " a las demás notas, en este orden estable: reranker (009), búsqueda híbrida (010), pregunta limpia (008), corte (007), regla de seguridad (006). Formas posibles ([contracts/busqueda-hibrida.md](contracts/busqueda-hibrida.md), sección 5):

- `Búsqueda híbrida: N por palabras, M nuevos` (candidatos léxicos y cuántos entraron a la lista final sin estar por significado), con el sufijo `, principal por palabras` si el fragmento principal de la lista final (el primero, que ordena el contexto) llegó solo por palabras (parámetro `main_by_words` de `hybrid_note`)
- `Búsqueda por palabras no disponible: se usó el significado` (la parte léxica falló)
- `Lista de siglas no disponible: se buscó sin equivalencias` (la tabla de siglas no se pudo leer; la parte léxica siguió; puede ir junto a la primera nota)
