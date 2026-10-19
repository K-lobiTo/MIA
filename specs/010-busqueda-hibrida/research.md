# Research: Búsqueda híbrida

Decisiones de diseño con su razón y las alternativas. Las cifras de la línea base están en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md). Las mediciones de R2 a R6 se hicieron el 2026-10-19 con un **análisis de factibilidad**: se leyó en solo lectura la colección de producción (6.239 fragmentos, 6,1 millones de caracteres), se copió a un Qdrant 1.19.1 local en Docker (contenedor desechable, ya retirado) con vectores de relleno, se creó el índice de texto y se simuló solo la parte léxica con los 57 casos de `scripts/datos/casos_busqueda.json` (dominios reales). No incluye la parte de vectores ni la fusión, y no se escribió nada en producción. Los scripts de esa simulación no se versionan; la medición oficial es la tarea de calibración con la herramienta de la 005.

## R1. Técnica: índice de texto de Qdrant (no vectores dispersos, no índice en memoria, no SQL)

**Decision**: crear en la colección existente un índice de texto (`TextIndexParams`) sobre el campo `text`, y consultarlo con filtros `MatchText` por palabra. La clasificación, la regla de la mayoría y la fusión las hace la API sobre los identificadores que devuelve Qdrant.

**Verificado (2026-10-19)**: el Qdrant de producción responde versión 1.19.1 (`GET /`), igual que el cliente instalado (`qdrant-client` 1.19.1). El cliente expone `TextIndexParams` con `tokenizer` (`word`, `whitespace`, `prefix`, `multilingual`), `lowercase`, `ascii_folding`, `min_token_len`, `max_token_len`, `phrase_matching`, `stopwords`, `stemmer` y `on_disk`, y las condiciones `MatchText`, `MatchTextAny` y `MatchPhrase`. La colección de producción tiene hoy solo los índices de `domain`, `document_id` y `chunk_index`.

**Rationale**:
- **El índice se mantiene solo.** La ingesta de documentos corre en la laptop del usuario contra el Qdrant y la base de producción (memoria `mia_ingesta_local`); cualquier cosa que viva en la memoria de la API quedaría desactualizada. Un índice de la colección se actualiza con cada `upsert`, venga de donde venga, y `set_domain` solo cambia el payload `domain` (el filtro de dominio de la búsqueda léxica lo ve al instante).
- **No gasta la RAM de la API**, que ya está al límite (366 MB en reposo y 512 MB de tope; el reranker no cupo por 10 MB). El índice cuesta RAM en Qdrant: en la medición local, +67 MB con el tokenizador por prefijo (R2), que se puede pasar a disco con `on_disk`.
- **Preparar lo ya ingerido es una operación de Qdrant** (`create_payload_index`): 1,5 s con el tokenizador por prefijo y 0,5 s con `word` sobre los 6.239 fragmentos, sin tocar vectores. Es idempotente y reversible (`delete_payload_index`). La versión anterior de la API ignora el índice.
- **Da lo que la regla pide**: una consulta por palabra con `limit = K + 1` devuelve a la vez cuántos fragmentos la contienen (si pasa de K es una palabra común) y cuáles son, sin leer el texto (`with_payload` solo con `document_id` y `chunk_index`, o sin payload). Mediana de 2,3 ms por consulta en la medición local.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Vectores dispersos con modificador IDF (BM25 hecho por la API) | Hay que calcular y guardar un vector disperso por fragmento (reindexar los 6.239 puntos con `update_vectors`), mantener el vocabulario y la longitud media en la API, y no devuelve qué palabras coincidieron, que es lo que necesita la regla de la mayoría. Es más complejo y no cubre mejor los casos medidos. Queda como evolución si el índice de texto no bastara. |
| Índice invertido en la memoria de la API (por ejemplo `rank_bm25`) | Se desactualiza con la ingesta local y consume la RAM que está al límite (decisión del usuario del 2026-10-18 de no pasar de 512 MB). |
| Búsqueda de texto completo en SQL (FTS5 en SQLite, `tsvector` en Postgres) | Dos motores distintos entre desarrollo y producción, el texto duplicado en Neon (límite gratuito) y una sincronización con Qdrant en la ingesta. |
| Servicio externo de búsqueda | Privacidad (FR-002 de la 009 vale igual: los textos solo salen hacia el proveedor de modelos de lenguaje) y costo. |

## R2. Tokenizador: por prefijo, minúsculas y sin tildes

**Decision**: índice de texto con `tokenizer = prefix`, `lowercase = true`, `ascii_folding = true`, `min_token_len = 3`, `max_token_len = 15`, `on_disk = true` (el último se confirma al medir latencia y memoria, tarea de medición).

**Hallazgo que lo decide**: el documento de Joseph Obando Sandí (`IPA Joseph Obando Sandi.pdf`) escribe en su carátula "Joseph Obando2023800202": el nombre pegado al carné. Con el tokenizador por palabras la palabra es `obando2023800202` y la búsqueda de `obando` no lo encuentra (solo trae a Kenneth Obando de dos actas). Con el tokenizador por prefijo, `obando` coincide con el inicio de esa palabra.

| Consulta | `word` | `prefix` |
|---|---:|---:|
| `obando` | 2 fragmentos (ambos de otra persona, Kenneth Obando) | 3 (incluye el de Joseph) |
| `joseph obando` (las dos palabras en el mismo fragmento) | 0 | 1 (el documento correcto) |
| `líneas` / `linea` | 31 / 83 | 31 / 307 (`linea` es prefijo de `lineas` y `lineamientos`) |
| `tfg`, `mgti`, `solis` | 19, 42, 29 | 19, 42, 29 |
| `OBANDÍ`, `sandí` (ausentes en el corpus) | 0 | 0 |
| Tiempo de construcción sobre 6.239 fragmentos | 0,46 s | 1,47 s |
| RAM extra de Qdrant (contenedor local) | referencia 133 MB | +67 MB (200,8 MB) |

El mismo corpus muestra el patrón en otros PDF ("Natalia María Soto Solís - 2023800205", "Luis Diego Cubillo Guevara 2023800196"): los nombres de carátula suelen venir pegados a números. Los PDF de carátula son justo donde están los casos que la feature debe resolver.

**Consecuencias del prefijo**: coincide por inicio de palabra, así que `curso` también trae `cursos` y `cursor`, y una palabra más corta que el mínimo (menos de 3 letras) no se indexa. Eso afecta por igual la medición de frecuencia (R4) y la búsqueda, así que el criterio de "palabra común" es coherente. No resuelve plurales hacia atrás (`líneas` no encuentra `línea`); el `stemmer` en español que ofrece el índice queda fuera de esta feature (solo coincidencia exacta de inicio de palabra, ver la spec).

**Alternatives considered**: `word` más `stemmer` español (no resuelve el nombre pegado al carné, que es el caso `S22-3`); `multilingual` (pensado para idiomas sin espacios); `whitespace` (no separa la puntuación pegada, por ejemplo "Solís," o "(*)"); `MatchPhrase` con `phrase_matching` (más tamaño de índice; la forma desarrollada de una sigla se busca con `MatchText`, que exige todas las palabras en el mismo fragmento, ver R7).

## R3. Cómo se consulta: una consulta por palabra, en paralelo, solo identificadores

**Decision**: para cada grupo de la pregunta (R4), un `scroll` con el filtro de dominios más `MatchText`, `limit = HYBRID_MAX_DOC_FREQ + 1` y sin payload de texto; los grupos se consultan en paralelo con un `ThreadPoolExecutor` pequeño. Después, una sola consulta `query_points` con el vector de la pregunta y un filtro `HasIdCondition` sobre los candidatos finales trae su texto y su coseno (desempate y fusión).

**Rationale**: dos rondas de red como máximo, y la primera se lanza **antes** de la búsqueda por significado y se espera después de ella, de modo que su latencia se solapa con la del vector (y con la del reranker si está encendido). El texto solo se pide de los candidatos finales (tope `HYBRID_LEXICAL_LIMIT`, 20).

**Medido**: `scroll` con `limit = 61` y sin texto, 30 repeticiones en el contenedor local: mediana 2,3 ms, máximo 5,6 ms. La latencia real de Railway a Qdrant Cloud es parte de la medición de SC-007.

**Alternatives considered**: `MatchTextAny` con todas las palabras en una sola consulta (una ronda menos, pero no dice qué palabra coincidió ni cuántos fragmentos tiene cada una, que son la regla y el criterio de palabra común); `count` por palabra más `scroll` (dos rondas en serie por palabra).

## R4. Palabra específica y grupos de la pregunta

**Decision**: la pregunta se normaliza (minúsculas, sin tildes, sigla con puntos "T.F.G." pasa a "tfg"), se parte en palabras de letras y dígitos, y se descartan las de menos de `HYBRID_MIN_TOKEN_LEN` (3) letras y las palabras vacías (lista fija en español que incluye interrogativos y verbos genéricos de pregunta). Cada palabra restante, o cada par sigla y forma desarrollada de la lista de equivalencias (R7), es un **grupo**; se conservan hasta `HYBRID_MAX_GROUPS` (8). Un grupo es **específico** si el número de fragmentos que lo contienen en los dominios consultados es como máximo `HYBRID_MAX_DOC_FREQ` (60). Un grupo que no aparece en ningún fragmento **cuenta como específico** (con cero coincidencias).

**Por qué cuenta lo ausente**: es lo que sostiene BUS-3. "¿Quién es Zacarías Fernández Pizarro?" tiene tres grupos: `zacarias` (0 fragmentos), `fernandez` (13) y `pizarro` (0); la regla pide 2 de 3 y ningún fragmento las cumple. Si lo ausente no contara, quedaría solo `fernandez` (1 de 1) y 13 fragmentos ajenos llegarían al modelo. Con el nombre real "Joseph Obando Sandí", `sandí` está ausente del corpus (el documento dice "Joseph Obando") y aun así 2 de 3 alcanza.

**Barrido de la frecuencia máxima K** (57 casos, con la regla de R5, 11 casos objetivo):

| K | Objetivos con su documento entre los candidatos | Casos "sin información" que reciben candidatos |
|---:|---:|---|
| 20 | 11 de 11 | `I3` (1 candidato) |
| 40 | 11 de 11 | `I1` (17), `SR1` (25) |
| 60 | 11 de 11 | `I1` (17) |
| 100 | 11 de 11 | `I1` (17) |
| 200 | 11 de 11 | `I1` (17) |

Un K bajo deja pasar casos raros porque palabras de uso corriente pasan a ser específicas por azar (por ejemplo, `SR1` a K = 40); el barrido no es monótono. Se fija 60 como valor de partida y la calibración real (FR-005, FR-017) lo ajusta con los casos nuevos.

**Limitación**: la frecuencia se mide sobre los dominios consultados, así que la misma palabra puede ser común para un artefacto con muchos dominios y específica para otro. Es un efecto buscado (lo específico depende de dónde se busca) y queda como riesgo anotado en R14.

## R5. Regla de la mayoría

**Decision** (acordada el 2026-10-19): un fragmento que solo llegó por palabras pasa si contiene **más de la mitad** de los grupos específicos de la pregunta (1 de 1, 2 de 2, 2 de 3, 3 de 4, 3 de 5...). Se ordena por grupos coincidentes y, a igualdad, por la suma del peso de cada grupo (`ln(1 + (K + 1) / fragmentos_del_grupo)`, más peso cuanto más raro) y luego por el coseno con la pregunta.

**Resultados del análisis** (57 casos; K = 60; con los dominios reales de cada caso):

| Caso | Grupos específicos | Candidatos léxicos | Documento esperado entre ellos |
|---|---|---:|---|
| `S22-1` Natalia Soto Solís (y variante corta) | natalia (1), soto (48), solis (29) | 1 | sí |
| `S22-3` Joseph Obando Sandí | joseph (9), obando (3), sandi (0) | 1 | sí (el fragmento de la carátula) |
| `S22-4` Luis Diego Cubillo Guevara | diego (3), cubillo (1), guevara (3); `luis` (154) es común | 1 | sí |
| `S22-2` líneas de trabajo final de graduación | `{trabajo final de graduación, tfg}`, líneas | 1 | sí ("Líneas de TFG") |
| `EN1` a `EN6`, `EN10` | los de las personas | 1 | sí |
| `LL2` Deep Learning | deep, learning... | 25 (13 del programa MC8840) | sí |
| `SG3` MGTI | mgti (42) | 39 | no (ver abajo) |
| `EN7` Zacarías Fernández Pizarro; `EN8`; `EN9`; `SR4` a `SR7`; `N1`; `I2`; `I3`; `SR1` a `SR3` | incluyen palabras ausentes | 0 | no aplica (correcto) |
| `I1` (Cibercrimen horas, aislamiento de dominio) | horas, extraclase, semana, curso, cibercrimen (ausente en ese dominio) | 17 | no aplica |

`I1` no es una regresión: con la búsqueda actual ya supera el umbral de coseno (0,846) y llega al modelo, que responde "sin información" (costo 0,0008 a 0,02 USD). `SG3` muestra el límite de la técnica: "MGTI" aparece en 42 fragmentos, sobre todo códigos de curso ("Código: MGTI-####") de un solo documento de reforma curricular, y los 39 candidatos son de un documento de reforma curricular y el documento esperado ("Plan 473", que escribe "MAESTRIA EN GE..." sin la sigla) no está entre ellos; la simulación solo incluyó la equivalencia de TFG, así que falta medir qué aporta la forma desarrollada de MGTI. La parte léxica no basta sola: el desempate por coseno y la fusión con los vectores deciden. Es un caso a medir con cuidado, no a prometer.

**Alternatives considered**: todas las palabras (más seguro pero deja fuera "Joseph Obando" para "Joseph Obando Sandí"); al menos una (sube el costo de las preguntas sin respuesta y deja pasar apellidos sueltos); mayoría con peso por rareza (más compleja; se vuelve a evaluar con los casos nuevos si la regla simple falla).

## R6. Fusión de las dos listas

**Decision**: *Reciprocal Rank Fusion* con `k = HYBRID_RRF_K` (60) sobre la lista de significado (la que hoy llega a `retrieve`: los `search_limit` mejores sobre el umbral, o la salida del reranker) y la lista léxica (ordenada como en R5). Un fragmento en las dos listas suma ambos aportes. Los que solo vinieron por palabras ocupan como máximo `HYBRID_LEXICAL_SLOTS` (3) lugares, y el total nunca supera el límite del modo (8 en literal, 16 con razonamiento, o el que resulte de la 007). Si la parte léxica no aporta ningún candidato, la lista se devuelve sin tocar, idéntica a hoy. Cuando la fusión actúa, el `score` de cada resultado pasa a ser su valor de fusión: la construcción del contexto ordena los pasajes y elige el documento principal por `score` (`context.py`), y la fusión es lo que debe decidir ese orden.

**Rationale**: RRF no necesita comparar escalas (coseno, puntaje del reranker, conteo de palabras), es el método estándar de los proyectos híbridos de Qdrant y de Elastic, y el tope de ranuras deja intacta la mayor parte de lo que hoy responde bien (SC-004). El desempate por coseno usa un `query_points` con filtro de ids (R3).

**Alternatives considered**: sumar o mezclar puntajes normalizados (escalas distintas, sensible a la distribución); poner los léxicos siempre primero (arriesga la batería del MVP); ampliar el límite del modo cuando hay candidatos léxicos (sube el costo del modelo de lenguaje, contra FR-006).

## R7. Lista de equivalencias de siglas

**Decision**: tabla `sigla_equivalences (id, sigla, form, created_by, created_at, updated_by, updated_at)` con unicidad en (`sigla`, `form`), editable solo por el alcance global desde el panel, leída por la API con una caché en proceso de `HYBRID_EQUIVALENCES_TTL_SECONDS` (60) que cada escritura invalida en su propio proceso. Una sigla puede tener varias formas y una forma varias siglas; no se encadenan (la expansión se aplica una vez, sobre las palabras originales de la pregunta). Las semillas de la migración son `TFG` ↔ "trabajo final de graduación" y `MGTI` ↔ "gestión de tecnologías de información" (la forma aparece como "Maestría en Gestión de Tecnologías de Información" en el documento de reforma curricular y en mayúsculas en el Plan 473). La forma desarrollada se busca con `MatchText`, que exige todas sus palabras en el mismo fragmento (no la frase exacta); la precisión extra de `MatchPhrase` cuesta tamaño de índice y se evalúa en la medición.

**Rationale**: el sistema de archivos de Railway es efímero, así que no puede ser un archivo; una variable de entorno obligaría a redesplegar y no se puede editar desde el panel. Un minuto de retraso es el máximo que acordó la spec (FR-007). El punto de partida de la forma desarrollada es el de los documentos reales, no una lista inventada.

**Alternatives considered**: archivo o variable de entorno (descartado por el usuario el 2026-10-19 al elegir el panel); ampliar el embedding de la pregunta con la forma desarrollada (cambiaría la búsqueda por significado, fuera de alcance); sinónimos automáticos desde los documentos (fuera de alcance).

## R8. Persistencia y vuelta atrás de la migración

**Decision**: migración Alembic `0005` que crea `sigla_equivalences` e inserta las dos semillas de forma idempotente; `downgrade` borra la tabla. La API aplica las migraciones al arrancar, así que **una API más vieja que la base no arranca** (advertencia en [OPERACION.md](../../docs/OPERACION.md), "Cuidado con las migraciones"): para volver a `prototipo-v2-estable` hay que devolver la base con `alembic downgrade 0004` (con `DATABASE_URL` de producción) antes de desplegar. Antes de eso conviene guardar la lista (`GET /equivalences`), porque el `downgrade` la borra. `scripts/probar_migracion.py` se corre sobre una copia de la base de producción. La migración no toca ninguna fila existente.

**Rationale**: es el mismo mecanismo que ya usaron las migraciones `0002` a `0004`; la diferencia es que ahora el procedimiento queda escrito y probado en la medición (SC-012). La parte de Qdrant no necesita migración: el índice de texto no afecta a la API anterior.

**Alternatives considered**: guardar la lista en Qdrant (otro almacén para datos de gestión, sin auditoría ni permisos); en un archivo del repositorio con un script de carga (no cumple "editable desde el panel"); crear la tabla fuera de Alembic (rompe el mecanismo de migraciones existente).

## R9. Permisos y registro de cambios

**Decision**: `GET /equivalences` lo ve cualquier persona que administra (alcance global o de unidad); `POST`, `PATCH` y `DELETE` exigen alcance global con `ensure_global`, que deja el intento rechazado en el registro de administración (`mia.admin`) como las demás escrituras. Cada cambio registra `audit.log_write(principal, "equivalence.create|update|delete", id, "sigla")` y las columnas `created_by`, `created_at`, `updated_by` y `updated_at` guardan quién y cuándo (el correo, o "automatizacion" con la clave de los scripts).

**Rationale**: el patrón de `ensure_global` y de `audit` es el de las demás rutas de administración (`guards.py`, `audit.py`); la tabla guarda lo mínimo que pide la spec (FR-020). La lista es global porque las siglas del posgrado valen en todos los dominios.

## R10. Orden de las etapas y combinación con 006 a 009

**Decision**: la ruta calcula la embedding de la pregunta; lanza la parte léxica en un hilo; ejecuta `retrieve` (significado, con o sin reranker); espera la parte léxica con un tope de `HYBRID_BUDGET_MS` (800 ms) y fusiona. El mismo `with_lexical(results)` se aplica al resultado de cada `retrieve`, así que el segundo intento con la pregunta limpia (008) usa el mismo conjunto léxico de la pregunta original (la parte léxica ya ignora las palabras de relleno) y solo ocurre si la lista fusionada de la primera búsqueda quedó vacía. Con el reranker encendido, los candidatos léxicos **no pasan por el mínimo del reranker**: el documento de Joseph Obando puntúa 0,000 en el reranker (research R14 de la 009), así que filtrarlo anularía la mejora; el reranker solo reordena los de significado. Las citas por fragmento (006) y el contexto completo (007) reciben la lista final, con el `score` de fusión (R6).

**Rationale**: la fusión después de cada `retrieve` mantiene el cambio local a la ruta (una sola función nueva) y no obliga a reescribir el reranker ni la pregunta limpia; los candidatos léxicos ya pasaron su propia regla de la mayoría.

**Alternatives considered**: fusionar antes del reranker (el mínimo los descartaría); hacer la búsqueda léxica con la pregunta limpia (la parte léxica ya descarta las palabras vacías).

## R11. Interfaz del almacén y activación

**Decision**: la interfaz `VectorStore` gana métodos no abstractos (que lanzan `NotImplementedError` por defecto, para no romper otros almacenes ni las pruebas existentes): `ensure_text_index()`, `text_index_status()`, `drop_text_index()`, `match_chunks(domains, text, limit)` y `score_chunks(embedding, domains, chunk_ids)`. `QdrantVectorStore` los implementa. `ensure_collection` crea el índice de texto solo si `QUERY_HYBRID_SEARCH=on` (igual que asegura los índices de `domain` y `document_id`); con `off` no se crea nada y producción queda como hoy. `scripts/palabras.py` (`estado`, `preparar`, `quitar`, con `--env-file`) permite prepararlo, comprobarlo y revertirlo sin encender la API.

**Rationale**: una consulta con filtro sobre un campo sin índice se rechaza en Qdrant Cloud (comentario existente en `vector_store.py`), así que sin índice la parte léxica falla de forma limpia y la ruta cae a significado con aviso (FR-009): un despliegue con la opción `on` antes de preparar el índice no rompe nada. Con índice parcial (mientras Qdrant construye), el índice responde con lo que ya tiene indexado.

## R12. Parte visual: módulo nuevo del panel

**Decision**: un módulo nuevo "Siglas y equivalencias" en `web/admin/src/modules/equivalencias/` con una tabla (sigla, forma desarrollada, quién y cuándo), un diálogo de alta y edición con validación, y confirmación para borrar, todo con componentes de Mantine y el tema de `src/theme.ts`, siguiendo las reglas de `web/admin/README.md` (sección Interfaz Mantine) y la paleta vigente. La sesión sin alcance global ve la tabla sin botones de escritura (`capabilities.canEditEquivalences`); la API es la que hace cumplir el permiso. Pruebas de las utilidades de validación y normalización con Vitest, como las demás utilidades del panel.

**Alternatives considered**: sumarlo como una sección del módulo Inventario (mezcla datos de gestión con el inventario de documentos); un módulo propio es lo que pide ADM-3 ("agregar un módulo es sumar una entrada aquí").

## R13. Medición y casos nuevos

**Decision**: la herramienta de la 005 gana, en `puntajes` (gratis, solo lectura): el cálculo de los candidatos léxicos de cada caso y variante contra Qdrant (de producción solo si ya tiene el índice, o de una copia local con el índice), con el puesto del documento esperado antes y después de la fusión, qué parte trajo cada candidato y los grupos específicos y ausentes; `comparar` entre la corrida de control y la híbrida; y el conteo de notas de la búsqueda híbrida en `respuestas`. Se agregan al menos 12 casos al archivo de casos (FR-017): personas (nombre completo y con un solo apellido, con la carátula pegada a un número), siglas y su forma desarrollada, términos específicos inventados y preguntas con palabras comunes sin respuesta (por ejemplo "¿Cuál es el procedimiento de matrícula de honor del instituto?"), seis de ellos sin respuesta. El mínimo de medición en Railway sigue el flujo de las lecciones del flujo de la 005 a 009: puntajes gratis, tope de gasto autorizado antes de cada corrida y cierre de producción al terminar.

## R14. Riesgos conocidos

- **Frecuencia relativa a los dominios**: la misma palabra puede ser común o específica según los dominios del artefacto (R4); se mide con casos de dominios distintos y es el motivo de que `HYBRID_MAX_DOC_FREQ` sea configurable.
- **Prefijos que sobran**: `curso` trae `cursos` y `cursor`; `linea` trae `lineamientos`. Es parte del recorte de "común" (se mide con la misma semántica) y se vigila en las pruebas con casos negativos.
- **Palabras con menos de 3 letras** (por ejemplo la sigla "TI") no se indexan ni se buscan.
- **Variantes de una sigla escritas con puntos o con guiones** ("T.F.G.", "TFG-I"): la pregunta se normaliza, el texto del documento lo normaliza el tokenizador (la primera queda como `t`, `f`, `g` y no coincide); se anota como límite y se resuelve con una equivalencia si hace falta.
- **Empates masivos** (`SG3`): la ordenación por coseno de los candidatos léxicos y la fusión con los vectores deciden; se mide en la calibración y puede quedar como caso reportado aparte.
- **Una sola instancia de la API**: la caché de equivalencias es por proceso; con varias instancias el cambio tardaría hasta un minuto en cada una (sigue dentro de lo acordado).
- **Qdrant Cloud gratuito**: el índice por prefijo con `on_disk` debe caber en el plan; se comprueba con el estado de la colección antes de encender.
- **Borrar y reingerir**: hoy la API no borra fragmentos del almacén y reingerir un documento crea ids nuevos sin borrar los anteriores (comportamiento previo, fuera de esta feature); por eso FR-010 se verifica con la ingesta nueva y con mover de dominio (`set_domain`), que solo cambia el payload `domain` y el filtro léxico lo ve al instante.
- **Coherencia con la ingesta**: un documento ingerido durante la construcción del índice puede tardar en aparecer; no afecta a la búsqueda por significado.

## R15. Versión mínima de `qdrant-client`

**Decision**: la primera tarea comprueba qué versión del cliente introdujo `ascii_folding`, `MatchTextAny` y `on_disk` en `TextIndexParams` y sube el piso de `pyproject.toml` (hoy `>=1.10`) a esa versión; `docker-compose.yml` usa `qdrant/qdrant:latest` en desarrollo y Qdrant Cloud responde 1.19.1. Si algún entorno tuviera un Qdrant anterior sin `ascii_folding`, la creación del índice falla de forma limpia y la ruta cae a significado (R11).
