---

description: "Tareas de implementación de la feature 009: reranker local (reordenar los candidatos de la búsqueda)"
---

# Tasks: Reranker local (reordenar los candidatos de la búsqueda)

**Input**: Design documents from `specs/009-reranker-local/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/reranker.md](contracts/reranker.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-018 exige pruebas automáticas con un reranker simulado. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar. Ninguna prueba carga el modelo real ni llama a proveedores externos.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md), precedidas por la base común. La medición y la calibración (que dependen de la herramienta) están al final de US4.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`. No desplegar ni encender servicios de Railway ni gastar sin la autorización del usuario (T042 la pide).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin migraciones ni reindexación**: la nota va en `reject_reason` (data-model.md). **Sin dependencias nuevas**: `onnxruntime`, `sentencepiece`, `numpy` y `huggingface_hub` ya están. Nada de PyTorch ni `transformers`.
- **Sin ninguna llamada nueva a un modelo de lenguaje** (FR-012) y **ninguna API externa de reranking** (FR-002).
- **Con `RERANK_PROVIDER=none` el comportamiento debe ser idéntico al de antes** (FR-011): misma búsqueda (mismo `limit`), contexto, respuesta, fuentes, costo y registro; el módulo del proveedor local ni siquiera se importa.
- **Un fallo del reranker nunca produce un error HTTP** (FR-007): la consulta continúa con coseno y umbral.
- El reranker puntúa siempre contra `payload.question` (research R5) y el modelo de lenguaje recibe siempre `payload.question`.
- La respuesta de `POST /query` conserva su estructura (FR-013) y las features 006, 007 y 008 deben seguir funcionando en todas las combinaciones (FR-014).
- Es un prototipo: lo más simple que cumpla la especificación.
- Para cambiar variables de Railway durante la medición: siempre `railway variable set ... --skip-deploys -s MIA` y luego `python scripts/servicios.py encender MIA --forzar --ref origin/dev`. Sin `--skip-deploys`, Railway redespliega desde `main` y se pierde el código de `dev`.
- Cierre de producción tras medir: variables `off`, servicio apagado, artefacto de prueba desactivado y su clave regenerada y guardada solo en `.env` (T045).

---

## Phase 1: Setup

**Purpose**: archivos nuevos y esqueleto de pruebas.

- [ ] T001 [P] Crear `src/mia/rag/rerank.py` con un docstring que explique su propósito (reordenar y cortar los candidatos de la búsqueda con un modelo que lee juntas la pregunta y cada fragmento; ver [contracts/reranker.md](contracts/reranker.md)) y sin lógica todavía.
- [ ] T002 [P] Crear `src/mia/rag/providers/local_rerank.py` con un docstring que explique su propósito (reranker local con `onnxruntime` y `sentencepiece`, mismo patrón que `local_embeddings.py`; modelo `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, research R1) y sin lógica todavía. Los `import` pesados (`onnxruntime`, `sentencepiece`, `huggingface_hub`) van a nivel de módulo, como en `local_embeddings.py`, porque este módulo solo se importa cuando el proveedor es `local`.
- [ ] T003 [P] Crear `tests/unit/test_rerank.py`, `tests/unit/test_local_rerank.py` y `tests/unit/test_query_rerank.py` con los `import` mínimos; el tercero toma como modelo `tests/unit/test_query_clean_question.py` (fixtures `base`, `db`, `client`, `modes_config`, la clase `_Almacen` que devuelve una lista por búsqueda y registra `limit`, el modelo simulado).

**Checkpoint**: `pytest` sigue pasando.

---

## Phase 2: Foundational (bloquea a todas las historias)

**Purpose**: configuración, interfaz, fábrica y función pura de selección, sin tocar todavía la ruta.

- [ ] T004 Agregar en `src/mia/config.py`, junto a las demás `query_*`, con un comentario que remita a `src/mia/rag/rerank.py` y a la spec, los campos de [data-model.md](data-model.md): `rerank_provider: str = "none"` (**texto libre**, "none" o "local"; un nombre inválido no impide el arranque), `rerank_candidates: int = Field(default=30, ge=5, le=60)`, `rerank_min_score: float = Field(default=0.5, ge=0, le=1)` (provisional, se calibra en T041), `rerank_min_similarity: float = Field(default=0.0, ge=0, le=1)`, `rerank_passage_tokens: int = Field(default=192, ge=32, le=480)`, `rerank_threads: int = Field(default=2, ge=1, le=8)`, `rerank_budget_ms: int = Field(default=2500, ge=0, le=30000)` (0 desactiva el presupuesto).
- [ ] T005 [P] Agregar a `.env.example` las siete variables `RERANK_*` con sus valores por defecto y un comentario por variable (qué hace, rango, que `RERANK_MIN_SCORE` es provisional y que el reranker corre dentro de la API sin servicio externo).
- [ ] T006 En `src/mia/rag/rerank.py`, implementar: la clase abstracta `RerankProvider` con `score(self, query: str, passages: list[str], deadline: float | None = None) -> list[float]` (un logit por pasaje, mismo orden y longitud), la excepción `RerankTimeout(Exception)`, `sigmoid(x: float) -> float` (estable con valores grandes en magnitud, sin desbordar `exp`), y `get_rerank_provider(name: str) -> RerankProvider | None`: `"none"` devuelve `None`; `"local"` importa y construye `LocalRerankProvider` (importación dentro de la función, memoizado por nombre); cualquier otro nombre devuelve `None` con un `logger.warning` **una sola vez** por valor (mismo mecanismo de `_INVALID_VALUES_WARNED` de `mia.rag.completeness`, sin duplicar la lógica de normalización: minúsculas y sin espacios); si la construcción de `local` lanza una excepción, registrarla con `logger.exception` una vez, recordar el fallo (no reintentar hasta reiniciar) y devolver `None`.
- [ ] T007 [P] En `tests/unit/test_rerank.py`, pruebas de `sigmoid` (0 da 0,5; valores de 10,95 y -9,9 de [research.md](research.md) R2 dan cerca de 1 y de 0; -1000 y 1000 no lanzan) y de `get_rerank_provider`: `"none"`, `""`, `"NONE "` devuelven `None`; un valor inválido devuelve `None` y avisa una sola vez (usar `caplog`); `"local"` con la construcción parcheada devuelve el proveedor simulado y lo memoiza; si la construcción lanza una excepción devuelve `None` y no la reintenta; con `"none"` el módulo `mia.rag.providers.local_rerank` no entra en `sys.modules` (**FR-008**).

**Checkpoint**: `pytest` completo pasa; el comportamiento no cambió (aún nada usa el reranker).

---

## Phase 3: User Story 1 - Encontrar documentos que hoy quedan fuera de los primeros resultados (Priority: P1) 🎯 MVP

**Goal**: con `RERANK_PROVIDER=local`, la ruta recupera más candidatos, el reranker los puntúa contra la pregunta original, y los mejores (hasta el límite del modo) llegan al armado del contexto en el orden del reranker.

**Independent Test**: `pytest tests/unit/test_rerank.py tests/unit/test_local_rerank.py tests/unit/test_query_rerank.py`: con un reranker simulado que da puntaje alto a un documento que la búsqueda por coseno dejó en el puesto 12, ese documento llega al modelo de lenguaje aunque el modo traiga 8 resultados.

### Tests de US1 (escribir primero; deben fallar)

- [ ] T008 [P] [US1] En `tests/unit/test_rerank.py`, pruebas de `rerank_candidates(results, logits, min_score, limit)` según [contracts/reranker.md](contracts/reranker.md) sección 3 paso 5: ordena de mayor a menor puntaje; los empates conservan el orden de entrada (orden de coseno, estable); descarta los menores que `min_score`; se queda con los primeros `limit`; a cada resultado devuelto le reemplaza `score` por `sigmoid(logit)` **sin modificar el objeto original** (copia con `dataclasses.replace`); con lista vacía devuelve un resultado vacío; el `RerankOutcome` devuelto tiene `best` (mejor puntaje de todos los puntuados, sea o no sobre el mínimo), `scored` (cuántos se puntuaron), `passed` (cuántos superaron el mínimo) y `fell_back=False`.
- [ ] T009 [P] [US1] En `tests/unit/test_local_rerank.py`, pruebas de `LocalRerankProvider` **sin cargar el modelo real**: el constructor acepta `session` y `tokenizer` opcionales (si son `None` los carga; las pruebas inyectan un tokenizador y una sesión simulados). Comprobar: el par de ids es `[0, *pregunta, 2, 2, *pasaje, 2]` con ids de sentencepiece desplazados en 1 (el id 0 pasa a 3); el pasaje se trunca a `RERANK_PASSAGE_TOKENS` y el total no supera 512; relleno con 1 (PAD) y máscara de atención; la sesión se llama con `input_ids` y `attention_mask` (sin `token_type_ids`, el grafo no lo tiene); se procesa en lotes de 4 y se devuelve un logit por pasaje en el orden de entrada (aunque el último lote sea más corto); una lista vacía devuelve `[]` sin llamar a la sesión; con `deadline` ya vencido lanza `RerankTimeout` antes de puntuar el segundo lote (el primero se permite) y con `deadline=None` no lanza.
- [ ] T010 [P] [US1] En `tests/unit/test_query_rerank.py`, pruebas de la ruta con `RERANK_PROVIDER=local` (proveedor simulado inyectado parchando `get_rerank_provider` en `mia.api.routes.query`): el almacén se llama con `limit == settings.rerank_candidates` (no con `search_limit` del modo); un documento en el puesto 12 por coseno con puntaje alto del reranker llega al modelo de lenguaje aunque el modo literal trae 8; los fragmentos que llegan al armado del contexto no superan `config.search_limit` (8 en literal, 16 en razonamiento); el reranker recibe como pregunta `payload.question` y los textos de los candidatos; el modelo de lenguaje recibe la pregunta original; los fragmentos llegan en el orden del reranker (el primer pasaje es el de mayor puntaje); un documento cuyo coseno está bajo `QUERY_SIMILARITY_THRESHOLD` pero cuyo puntaje del reranker pasa el mínimo **llega al modelo** (caso Cubillo, 0,819 contra 0,82); con `RERANK_MIN_SIMILARITY=0.78` los candidatos con coseno menor no se envían al reranker (el proveedor simulado registra qué recibió).
- [ ] T011 [P] [US1] En `tests/unit/test_query_rerank.py`, pruebas de que en el modo con razonamiento se recuperan `RERANK_CANDIDATES` y se entregan hasta 16, y de que los puntajes del reranker se reutilizan por `chunk_id` dentro de una misma consulta (el proveedor simulado no recibe dos veces el mismo pasaje cuando la segunda búsqueda de la 008 devuelve candidatos repetidos; ver también T020).

### Implementación de US1

- [ ] T012 [US1] En `src/mia/rag/rerank.py`, implementar `RerankOutcome` (dataclass: `results`, `best: float | None`, `scored: int`, `passed: int`, `fell_back: bool`, `min_score: float`) y `rerank_candidates(results, logits, min_score, limit) -> RerankOutcome` como en T008 (función pura, sin acceso a `settings`).
- [ ] T013 [US1] En `src/mia/rag/providers/local_rerank.py`, implementar `download_rerank_files() -> tuple[str, str]` (`hf_hub_download` de `onnx/model_quint8_avx2.onnx` y `sentencepiece.bpe.model` del repositorio `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, constantes de módulo como en `local_embeddings.py`) y `LocalRerankProvider(RerankProvider)` según [contracts/reranker.md](contracts/reranker.md) sección 2: sesión `onnxruntime` con `intra_op_num_threads = settings.rerank_threads`, `enable_cpu_mem_arena = False`, `CPUExecutionProvider`; pares `[0, *pregunta, 2, 2, *pasaje, 2]` con ids desplazados en 1; pasaje truncado a `settings.rerank_passage_tokens` y total máximo 512; lotes de 4; comprobar `deadline` (`time.perf_counter()`) **antes de cada lote salvo el primero**; devolver los logits como `list[float]` (la salida `logits` tiene forma `(lote, 1)`). Reutilizar las constantes de ids especiales (BOS, PAD, EOS, UNK) importándolas de `local_embeddings` en lugar de repetirlas.
- [ ] T014 [US1] En `src/mia/api/routes/query.py`, importar `get_rerank_provider`, `rerank_candidates` y `rerank_note` (este último se crea en T019) y reemplazar la recuperación actual (`results = vector_store.search(...)` y `relevant = [...]`) por una función auxiliar interna `retrieve(vector)` que: si no hay proveedor (`get_rerank_provider(settings.rerank_provider)` es `None`) hace exactamente lo de hoy (misma búsqueda con `limit=config.search_limit` y mismo filtro por `settings.query_similarity_threshold`); si hay proveedor, busca con `limit=settings.rerank_candidates`, descarta los de coseno menor que `settings.rerank_min_similarity` (solo si es mayor que 0), puntúa los pasajes con `payload.question` reutilizando puntajes ya calculados en la consulta (diccionario por `chunk_id`, creado antes de `retrieve`) y llama a `rerank_candidates(..., min_score=settings.rerank_min_score, limit=config.search_limit)`; devuelve la lista `relevant`. Usar `retrieve` en la primera búsqueda y en el segundo intento de la feature 008 (con el embedding de la pregunta limpia). Registrar a nivel INFO `Reranker: <n> candidatos en <ms> ms (modo <modo>)` por cada puntuación. El manejo de errores del reranker es de US3 (T027); aquí se deja el camino feliz.

**Checkpoint**: las pruebas de US1 pasan; con `RERANK_PROVIDER=none` toda la suite anterior pasa sin cambios.

---

## Phase 4: User Story 2 - Seguir diciendo "sin información" cuando los documentos no la tienen (Priority: P1)

**Goal**: cuando ningún candidato supera el mínimo del reranker, la respuesta es "sin información" sin llamar al modelo de lenguaje, con la nota del mejor puntaje; y las notas conviven con las de las features 006 a 008.

**Independent Test**: `pytest tests/unit/test_query_rerank.py -k "sin_info or nota"`: con un reranker simulado que da puntajes bajos a todos, la consulta termina en `no_info`, el modelo de lenguaje no se llama y `reject_reason` lleva la nota.

### Tests de US2 (escribir primero; deben fallar)

- [ ] T015 [P] [US2] En `tests/unit/test_rerank.py`, pruebas de `rerank_note(outcome)` con el texto exacto de [data-model.md](data-model.md): `Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50` cuando `passed > 0`; `Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30` cuando `passed == 0`; `Reranker no disponible: se usó la similitud` cuando `fell_back`; punto decimal y tres decimales (el mínimo con dos); un `best` muy pequeño (por ejemplo 0.0000004) se muestra `0.000` sin notación científica; la nota nunca supera 120 caracteres.
- [ ] T016 [P] [US2] En `tests/unit/test_query_rerank.py`, pruebas de la ruta: si ningún candidato supera el mínimo la respuesta es `no_info` (`no_info=True` en el cuerpo), el modelo de lenguaje no se llama, el costo es cero, `reject_reason` es `Reranker: ninguno sobre el mínimo 0.50, mejor 0.XXX de N`, y `outcome == "no_info"`; si algún candidato lo supera y el modelo responde, `reject_reason` lleva `Reranker: mejor ..., k de N sobre el mínimo 0.50`; con `RERANK_MIN_SCORE` cambiado por `monkeypatch` el corte cambia en consecuencia.
- [ ] T017 [P] [US2] En `tests/unit/test_query_rerank.py`, pruebas de la convivencia con las features 006 a 008: con `QUERY_CLEAN_QUESTION=on`, si el primer intento no deja nada sobre el mínimo del reranker se hace el segundo (búsqueda con el embedding de la pregunta limpia), el reranker puntúa contra la pregunta **original** y no contra la limpia, y la nota queda en el orden `Reranker: ...; Pregunta limpia: «X» (con resultados)`; con `QUERY_COMPLETE_CONTEXT=on`, `QUERY_RETRY_CUT_ANSWERS=on` y `QUERY_CITED_SOURCES=on` las notas salen en el orden reranker, pregunta limpia, corte (007), citas (006) unidas con "; "; con `QUERY_CITED_SOURCES=on` los pasajes numerados siguen el orden del reranker; una respuesta `no_info` tras un segundo intento sin resultados lleva ambas notas.

### Implementación de US2

- [ ] T018 [US2] En `src/mia/rag/rerank.py`, implementar `rerank_note(outcome: RerankOutcome) -> str` con los tres textos de T015 (formato `f"{x:.3f}"` para puntajes y `f"{x:.2f}"` para el mínimo).
- [ ] T019 [US2] En `src/mia/api/routes/query.py`, construir `rerank_note(...)` con el resultado de la **última** búsqueda de la consulta (research R7) y guardarlo en una variable `rerank_note_text`; en `no_info()` escribir `log.reject_reason = combine_notes(rerank_note_text, clean_question_note)`; en el camino de respuesta usar `combine_notes(rerank_note_text, clean_question_note, cut_note, safety_note)` (hoy son tres argumentos: agregar el del reranker **primero**).
- [ ] T020 [US2] En `src/mia/api/routes/query.py`, asegurar que el segundo intento de la feature 008 solo se hace si, tras el reranker, `relevant` quedó vacío (mismo `if not relevant and clean_question_enabled(...)` de hoy), que `retrieve` recibe el embedding de la pregunta limpia pero puntúa siempre con `payload.question`, y que la reutilización de puntajes por `chunk_id` (T014) evita puntuar de nuevo los candidatos repetidos.

**Checkpoint**: las pruebas de US1 y US2 pasan; `no_info` por reranker no llama al modelo y deja nota.

---

## Phase 5: User Story 3 - Poder apagarlo, cambiar de modelo y que un fallo no rompa la consulta (Priority: P1)

**Goal**: con `none` nada cambia y nada se carga; con `local` el modelo se carga al arrancar; si falla o excede el presupuesto de tiempo, la consulta responde por coseno con aviso y nota.

**Independent Test**: `pytest tests/unit/test_query_rerank.py -k "apagado or fallo or presupuesto"`: con `none` el almacén se llama con el `limit` de siempre y `reject_reason` es el de siempre; con un proveedor que lanza una excepción o `RerankTimeout` la consulta responde con el orden y el umbral de coseno, y la nota dice `Reranker no disponible: se usó la similitud`.

### Tests de US3 (escribir primero; deben fallar)

- [ ] T021 [P] [US3] En `tests/unit/test_query_rerank.py`, pruebas con `RERANK_PROVIDER=none` (por defecto), `"NONE"` y un valor inválido (`"xyz"`): el almacén se llama con `limit == config.search_limit` y una sola vez por búsqueda, el filtro es el umbral de coseno, el proveedor no se invoca (`get_rerank_provider` devuelve `None`), `reject_reason` y la respuesta son idénticos a los de antes de la feature (**FR-011, SC-004**).
- [ ] T022 [P] [US3] En `tests/unit/test_query_rerank.py`, pruebas de caída a coseno: un proveedor cuyo `score` lanza `RuntimeError` y otro que lanza `RerankTimeout` hacen que la consulta responda (HTTP 200, nunca 5xx) con los primeros `config.search_limit` resultados por coseno filtrados por `QUERY_SIMILARITY_THRESHOLD`; `reject_reason` empieza con `Reranker no disponible: se usó la similitud`; se registra un aviso; si la caída ocurre en el primer intento, el segundo intento de la 008 se hace **sin** llamar de nuevo al reranker (el proveedor simulado cuenta llamadas); una consulta que cae a coseno y no pasa el umbral termina en `no_info` con la nota; **SC-008**: 20 consultas simuladas con la falla, todas responden y ninguna devuelve error.
- [ ] T023 [P] [US3] En `tests/unit/test_query_rerank.py`, pruebas del presupuesto de tiempo: con `RERANK_BUDGET_MS=50` el `deadline` pasado al proveedor es `inicio + 0.050 s` (el proveedor simulado lo registra); con `RERANK_BUDGET_MS=0` el `deadline` es `None`.
- [ ] T024 [P] [US3] En `tests/unit/test_query_rerank.py`, pruebas del registro: el aviso de fallo se emite como máximo una vez por minuto (parchear el reloj o la marca de tiempo del limitador) aunque haya varias consultas con falla.
- [ ] T025 [P] [US3] En `tests/unit/test_rerank.py`, pruebas del arranque: función `warm_up_rerank_provider()` (T028) con `none` no importa nada y no hace nada; con `local` y un proveedor simulado lo construye una vez y registra a INFO `Reranker cargado: RSS <antes> -> <después> MB`; si la construcción falla, no lanza (la API arranca) y el reranker queda "no disponible".

### Implementación de US3

- [ ] T026 [US3] En `src/mia/rag/rerank.py`, agregar el limitador de avisos (`warn_rerank_failure(exc)`: como máximo un `logger.warning` por minuto, con el texto de la excepción) y `deadline_for(started: float) -> float | None` (`started + settings.rerank_budget_ms / 1000`, o `None` si el presupuesto es 0).
- [ ] T027 [US3] En `src/mia/api/routes/query.py`, dentro de `retrieve` (T014), envolver la puntuación en `try/except Exception`: ante cualquier excepción (incluida `RerankTimeout`) llamar a `warn_rerank_failure`, marcar `rerank_failed = True` para el resto de la consulta, y devolver los primeros `config.search_limit` resultados de la búsqueda con el filtro por `settings.query_similarity_threshold` (lo de hoy); con `rerank_failed` ya marcado, `retrieve` se comporta como sin proveedor (sin reranker y con `limit=config.search_limit`); el `RerankOutcome` de la caída lleva `fell_back=True` para la nota. Pasar `deadline_for(inicio_de_la_puntuacion)` al proveedor.
- [ ] T028 [US3] En `src/mia/rag/rerank.py`, implementar `warm_up_rerank_provider()`: si `settings.rerank_provider` es `local`, registrar el RSS (leer `VmRSS` de `/proc/self/status`; si no existe, omitir la cifra), llamar a `get_rerank_provider("local")` y registrar el RSS de nuevo (`Reranker cargado: RSS <antes> -> <después> MB`); nunca lanzar. En `src/mia/api/main.py`, llamarla en `lifespan` después de crear el proveedor de embeddings y antes de `yield`.
- [ ] T029 [P] [US3] Agregar al `Dockerfile`, tras la descarga del modelo de embeddings y antes de `ENV HF_HUB_OFFLINE=1`, un `RUN python -c "from mia.rag.providers.local_rerank import download_rerank_files; download_rerank_files()"` con un comentario que explique que se descarga siempre (research R11) y que con `RERANK_PROVIDER=none` no se carga en memoria.

**Checkpoint**: las pruebas de US1 a US3 pasan; `pytest` completo y `ruff check src tests scripts` limpios.

---

## Phase 6: User Story 4 - Medir cuánto cuesta y cuánto mejora, y decidir si se conserva (Priority: P1)

**Goal**: la herramienta de la 005 calcula gratis los puntajes del reranker sobre los casos, calibra el mínimo, mide memoria y latencia, lee las notas del reranker en las respuestas y compara corridas; y con eso se mide en local y en Railway y se escribe la recomendación.

**Independent Test**: `pytest tests/unit/test_linea_base.py` (lógica pura de la herramienta con datos sintéticos) y luego los pasos 2 y 3 de [quickstart.md](quickstart.md) (gratis).

### Tests de US4 (escribir primero; deben fallar)

- [ ] T030 [P] [US4] En `tests/unit/test_linea_base.py`, pruebas de `puesto_rerank(candidatos, documentos)` (puesto por coseno y por reranker del mejor fragmento de cada documento esperado, `None` si no aparece) y de `resultado_por_modo_rerank(candidatos, limite, minimo)` (responde si algún candidato de los primeros `limite` por reranker alcanza el mínimo, con `pasan` y `mejor_puntaje`).
- [ ] T031 [P] [US4] En `tests/unit/test_linea_base.py`, pruebas de `barrido_minimos(mediciones, minimos)` (para cada mínimo: cuántos casos con `espera` de respuesta pasan, cuántos casos de "sin información" quedan bloqueados) y de `ventana_rerank(mediciones)` (máximo puntaje de los casos "sin información" frente al mínimo de los casos con respuesta, y `separables`), con datos sintéticos con y sin ventana.
- [ ] T032 [P] [US4] En `tests/unit/test_linea_base.py`, pruebas del patrón de las notas del reranker en `correr_respuestas`: `PATRON_RERANK` reconoce los tres textos de [data-model.md](data-model.md) y extrae mejor puntaje, candidatos y si cayó a coseno; los campos `rerank_mejor`, `rerank_cayo` y `rerank_ninguno_sobre_minimo` se registran por consulta (campos opcionales, igual que los de la 008); el resumen cuenta consultas con reranker y caídas a coseno; `comparar` y `generar_informe` muestran esos conteos sin romper corridas anteriores que no los traen.
- [ ] T033 [P] [US4] En `tests/unit/test_linea_base.py`, pruebas de `resumen_rendimiento(medidas)` (p50 y p95 de una lista de latencias con `percentil`, e indicador de si una combinación cumple los límites de SC-006 recibidos como parámetros) con datos sintéticos.

### Implementación de US4

- [ ] T034 [US4] En `scripts/linea_base.py`, implementar las funciones puras de T030 y T031 (`puesto_rerank`, `resultado_por_modo_rerank`, `barrido_minimos`, `ventana_rerank`), junto a `resultado_por_modo`, `barrido_umbrales` y `ventana_separacion`, y la de T033 (`resumen_rendimiento`).
- [ ] T035 [US4] En `scripts/linea_base.py`, agregar `--rerank` a `puntajes` (`comando_puntajes`): si se pasa, construir el reranker local (`get_rerank_provider("local")` con las variables `RERANK_*` del archivo de entorno), y para cada variante recuperar `settings.rerank_candidates` candidatos **con el texto** del fragmento, puntuarlos con la pregunta de la variante (la variante "limpia" se puntúa con la pregunta completa, como la API, research R5), aplicar `rerank_candidates` con el mismo código de la API, y guardar en cada medición el campo `rerank` descrito en [data-model.md](data-model.md) (candidatos con puesto por coseno y por reranker, logit, puntaje, documento, `por_modo`, `esperados`, `ms`). Imprimir una línea por caso con el puesto del documento esperado por reranker. Los textos de los fragmentos no se guardan en el JSON. Añadir `barrido_minimos` y `ventana_rerank` al resumen e imprimir la ventana como `ventana de separación` de hoy. Sin `--rerank` la salida es idéntica a la actual.
- [ ] T036 [US4] En `scripts/linea_base.py`, agregar el subcomando `rendimiento` (`comando_rendimiento`): leer `--env-file`, abrir Qdrant en solo lectura, tomar los primeros 6 casos con pasajes reales (preguntas del archivo de casos), y para cada combinación de candidatos (10, 20, 30, 40), tokens por pasaje (128, 192, 256) e hilos (1, 2, 4), medir 5 repeticiones de la puntuación (descartar la primera como calentamiento) y calcular p50 y p95 con `resumen_rendimiento`; registrar el RSS (lectura de `/proc/self/status`) antes de cargar el reranker, después de cargarlo y al final; guardar `rendimiento.json` y marcar qué combinaciones cumplen 0,5 s en p50 y 1,5 s en p95. No llama al modelo de lenguaje.
- [ ] T037 [US4] En `scripts/linea_base.py`, agregar `PATRON_RERANK` y, en `correr_respuestas`, registrar por consulta `rerank_mejor`, `rerank_cayo` y `rerank_ninguno_sobre_minimo` (a partir de la nota del reranker en `reject_reason`, igual que se hace con `pregunta_limpia`); extender `CAMPOS_OPCIONALES`, `comparar` y `generar_informe` para mostrar "Consultas con reranker: N; caídas a coseno: K; sin candidatos sobre el mínimo: M" y la latencia mediana por modo contra el control.
- [ ] T038 [P] [US4] En `scripts/datos/casos_busqueda.json`, revisar que los casos "sin información" y de siglas que pide el plan de calibración existan: EN7, EN8, A1 y los 4 de la batería del MVP ya están; agregar los que falten para tener al menos 6 casos de "sin información" y 3 casos de preguntas dudosas (nombres de personas que existen en un dominio distinto al consultado, término real pero de otro dominio), con `espera` y `documentos` como los demás casos y sin tocar los existentes; actualizar el conteo en `tests/unit/test_linea_base.py` si la prueba cuenta los casos.

### Medición y decisión (US4, requiere T034 a T037)

- [ ] T039 [US4] Correr `python scripts/linea_base.py puntajes --etiqueta rerank-previa --env-file .env.produccion --rerank` (solo lectura, gratis) y la herramienta guarda la salida en `tmp/linea_base/<etiqueta>/` (carpeta fuera de git), como en la 008. Leer la ventana de separación, el barrido de mínimos y los casos que cambian de resultado. **Si la ventana dice "NO separables"**: el resultado de la prueba es negativo; anotar los casos que lo impiden y continuar con T040 solo para medir memoria y latencia.
- [ ] T040 [US4] Correr `python scripts/linea_base.py rendimiento --etiqueta rendimiento-local --env-file .env.produccion` (gratis) y leer qué combinaciones cumplen SC-006; elegir el punto de partida (`RERANK_CANDIDATES`, `RERANK_PASSAGE_TOKENS`, `RERANK_THREADS`, y si conviene `RERANK_MIN_SIMILARITY`, usando `puntajes` con ese piso para confirmar que no pierde los documentos esperados). Registrar el RSS del subcomando contra el límite de 512 MB de SC-007.
- [ ] T041 [US4] Con los resultados de T039 y T040, fijar en `src/mia/config.py` y `.env.example` los valores por defecto calibrados de `RERANK_MIN_SCORE` y de los demás parámetros, con un comentario que cite los datos (ventana de separación, casos usados). Si no existe un mínimo que sirva, dejar `RERANK_MIN_SCORE` en un valor conservador, anotarlo y reportarlo en T050. Ajustar las pruebas que dependan del valor por defecto.
- [ ] T042 [US4] Pedir al usuario (AskUserQuestion) la autorización de la medición en Railway con respuestas: casos que cambian (los que T039 muestra que el reranker modifica) más los de "sin información" y una muestra de la batería del MVP, en los dos modos; tope de gasto de la corrida de control y de la corrida con reranker; y confirmar que se enciende el servicio de Railway con `dev` temporalmente. **No gastar ni encender nada sin su respuesta.** Si T039 dice "NO separables" y T040 dice que ninguna combinación cumple, proponer al usuario saltar la medición en Railway y cerrar con el informe local.
- [ ] T043 [US4] Con la autorización de T042: activar el artefacto de prueba `PRUEBA Aceptación ambas unidades` (id `5f0168b0-b86c-4cdd-9ebb-1a9961fa10b7`, tope diario 1 USD) con PATCH `/artifacts/{id}` y `X-Admin-Key`, `railway variable set RERANK_PROVIDER=none ... -s MIA --skip-deploys`, `python scripts/servicios.py encender MIA --forzar --ref origin/dev`, y correr la corrida de control: `python scripts/linea_base.py respuestas --etiqueta control9 ... --tope-usd <tope autorizado> --solo <casos>`.
- [ ] T044 [US4] Cambiar a `RERANK_PROVIDER=local` y los parámetros elegidos (`railway variable set ... --skip-deploys`, reiniciar con `encender ... --forzar --ref origin/dev`), leer del registro de arranque `Reranker cargado: RSS ...` y de la consola de Railway la memoria en reposo y bajo carga, y correr `respuestas --etiqueta rerank ...` con los mismos casos y el tope autorizado. Anotar la memoria y el gasto real.
- [ ] T045 [US4] Cerrar producción: `RERANK_PROVIDER=none` con `--skip-deploys`, desactivar el artefacto de prueba, regenerar su clave (POST `/artifacts/{id}/key`) y guardarla solo en `.env` (`MIA_ARTIFACT_KEY`), `python scripts/servicios.py apagar MIA --forzar`, y comprobar que los cuatro servicios están apagados.
- [ ] T046 [US4] Correr `python scripts/linea_base.py comparar` entre `control9` y `rerank` (y contra la línea base original) y generar el informe de cada corrida. Verificar SC-001 a SC-005 con los datos: casos con documento entre los puestos 9 y 40, los de "sin información", los 19 de la batería, la corrida de control contra la línea base, y el costo medio por consulta.

**Checkpoint**: se tiene la medición completa (puntajes, rendimiento, Railway) y producción quedó apagada con todo en `none`.

---

## Phase 7: Polish & documentación

**Purpose**: documentación viva, resultados y cierre.

- [ ] T047 [P] Actualizar `docs/ARQUITECTURA.md`: la nueva pieza `RerankProvider` en el patrón interfaz más fábrica, el flujo de `POST /query` con el reranker, el orden de las notas de Uso y la descarga del modelo en el `Dockerfile`.
- [ ] T048 [P] Actualizar `docs/OPERACION.md`: las siete variables `RERANK_*` en la tabla de variables, una sección "Reranker local" (qué hace, cómo encenderlo con el procedimiento `--skip-deploys`, el costo en memoria y latencia medido, cómo leer la nota de Uso, cómo apagarlo y qué ocurre si falla).
- [ ] T049 Actualizar `docs/Definicion_Requerimientos_V3.md`: estado de la opción E en 2.6, los resultados de la prueba de 2.7 (marcar "ejecutada" con el enlace al informe), BUS-1/BUS-2/BUS-3/BUS-6 según corresponda, las decisiones 1, 2 y 4 de 2.8 como resueltas con las respuestas del 2026-10-18, y los criterios de 2.9 con la cifra medida.
- [ ] T050 Escribir en `docs/LINEA_BASE_BUSQUEDA.md` la sección "Resultado de la feature 009" con: calidad por caso (tabla), ventana de separación y mínimo elegido, memoria (reposo y bajo carga, local y Railway), latencia p50 y p95 por combinación, costo mensual estimado, gasto de la medición, la evaluación de cada criterio de conservación y la **recomendación explícita** (conservar, dejar apagado, pasar a la búsqueda híbrida; SC-009), dejando claro que la decisión de aceptar más latencia o subir de plan es del usuario. Completar en `spec.md` la tabla "Resultados medidos" con los valores reales de SC-001 a SC-009.
- [ ] T051 [P] Correr `pytest` completo y `ruff check src tests scripts`; corregir lo que falle. Revisar con `grep` que ningún archivo nuevo o modificado de la feature contiene el carácter guion largo (U+2014) y que `.env` no entró al commit.
- [ ] T052 Actualizar la memoria del proyecto (`mia_v3_busqueda_no_directa.md` y el índice `MEMORY.md`) con el estado de la 009, los resultados medidos y lo que sigue (D, G); commit y push a `dev` (sin merge a `main`, sin atribución de Claude).

---

## Dependencies & Execution Order

- **Fases**: Setup (Phase 1) -> Foundational (Phase 2) -> US1 -> US2 -> US3 -> US4 -> Polish. Las historias comparten `src/mia/api/routes/query.py` y `src/mia/rag/rerank.py`, así que se hacen en orden; US2 y US3 extienden lo que US1 deja funcionando.
- **Dentro de cada historia**: pruebas primero (deben fallar), luego la implementación.
- **T012 y T013** son independientes entre sí (archivos distintos) y pueden hacerse en paralelo tras T006; **T014** depende de T012 y T013; **T018** (nota) la usa T019.
- **US4**: T034 a T037 antes que cualquier medición; T038 puede hacerse en paralelo con ellas; la medición es secuencial T039 -> T040 -> T041 -> T042 (autorización) -> T043 -> T044 -> T045 -> T046.
- **Polish**: T047 y T048 en paralelo; T049 y T050 después de T046; T051 y T052 al final.

### Parallel Examples

```text
Setup:     T001, T002, T003 en paralelo.
US1:       T008, T009, T010, T011 en paralelo (pruebas); T012 y T013 en paralelo.
US2:       T015, T016, T017 en paralelo (pruebas).
US3:       T021 a T025 en paralelo (pruebas); T029 en paralelo con T026 a T028.
US4:       T030 a T033 en paralelo (pruebas); T038 en paralelo con T034 a T037.
Polish:    T047 y T048 en paralelo.
```

## Implementation Strategy

- **MVP (US1)**: con T001 a T014 la ruta ya recupera candidatos, los reordena y entrega los mejores al modelo; sin esta parte no hay nada que medir.
- **Seguridad (US2 y US3)**: el corte por mínimo, las notas, la caída a coseno y la carga al arrancar convierten el MVP en algo que se puede probar en producción sin riesgo.
- **Decisión (US4)**: la medición gratuita (T039, T040) decide casi todo; la de Railway (T043, T044) solo confirma en el servidor real y requiere autorización. Si la medición local ya dice que no se cumple el límite, se puede cerrar sin gastar.
- **Incremental**: cada historia termina con `pytest` y `ruff` limpios y un commit en `dev`.

## Notes

- Total: 52 tareas (Setup 3, Foundational 4, US1 7, US2 6, US3 9, US4 17, Polish 6).
- Las tareas de convergencia (`/speckit-converge`) se agregan al final como fases nuevas, sin tocar las anteriores.
