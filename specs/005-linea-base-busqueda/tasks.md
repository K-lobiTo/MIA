---

description: "Tareas de implementación de la línea base de la búsqueda"
---

# Tasks: Línea base de la búsqueda de MIA

**Input**: Design documents from `specs/005-linea-base-busqueda/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/linea-base-cli.md](contracts/linea-base-cli.md), [quickstart.md](quickstart.md)

**Tests**: incluidos solo para la lógica pura de la herramienta (carga y validación de casos, barrido de umbrales, ventana de separación, resúmenes, comparación), en `tests/unit/test_linea_base.py`, sin red ni Qdrant. La verificación contra datos reales es la corrida descrita en el quickstart.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md). Casi todo el código vive en un solo archivo, `scripts/linea_base.py`, por eso hay pocas tareas paralelas.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)

## Reglas para quien implemente

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main` ni desplegar: lo pide el usuario.
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **No tocar `src/`, `alembic/` ni la configuración por defecto** (FR-016). La herramienta solo importa de `mia`.
- La medición de puntajes es **de solo lectura** (FR-005): solo SELECT en la base, y en Qdrant solo `query_points`, `count` y `get_collection`.
- **Nunca guardar ni imprimir** el `text` de fragmentos, el texto de la respuesta ni el `excerpt` de las fuentes (FR-006).
- Medir contra producción está permitido (la información se considera pública para pruebas). Lo que gasta es la etapa `respuestas`: no correrla sin `--tope-usd`, y el usuario decide cuándo encender la API de Railway. Las claves ya están en `.env` (ignorado por git): `MIA_ARTIFACT_KEY` (artefacto existente que eligió el usuario) y `MIA_ADMIN_KEY`; la herramienta las lee de ahí. Nunca copiarlas a un archivo versionado ni imprimirlas. Esas corridas usan un artefacto real: comparten su tope diario con el uso normal, así que hay que vigilarlo (ver la tarea de `respuestas`).
- Es un prototipo: lo más simple que cumpla la especificación. Sin abstracciones que no se usen.

---

## Phase 1: Setup

**Purpose**: esqueleto de la herramienta y de sus pruebas.

- [X] T001 Crear `scripts/linea_base.py` con docstring de uso (en el estilo de `scripts/pruebas_mvp.py`), `argparse` con los subcomandos `puntajes`, `respuestas`, `informe` y `comparar` según [contracts/linea-base-cli.md](contracts/linea-base-cli.md), y `main()` que despacha a funciones vacías que lanzan `NotImplementedError`
- [X] T002 [P] Crear `tests/unit/test_linea_base.py` que carga el script con `importlib.util.spec_from_file_location` como en `tests/unit/test_probar_migracion.py`, con un test mínimo que comprueba que el módulo importa y que `main` existe

**Checkpoint**: `python scripts/linea_base.py --help` muestra los cuatro subcomandos y `pytest tests/unit/test_linea_base.py` pasa.

---

## Phase 2: Foundational (bloquea a todas las historias)

**Purpose**: utilidades comunes de carga de casos, contexto de corrida y salida.

- [X] T003 En `scripts/linea_base.py`, implementar `cargar_casos(ruta)` que lee `scripts/datos/casos_busqueda.json` y valida cada campo según [data-model.md](data-model.md): `id` único; `categoria` en `mvp`, `seccion_2_2`, `indirecta`, `sigla`, `sin_respuesta`; `dominios` y `pregunta` obligatorios; `espera` en `respuesta` o `sin_informacion`; `documentos` no vacío si `espera = respuesta`. Errores con el id del caso y en español
- [X] T004 En `scripts/linea_base.py`, implementar `cargar_env(ruta)` que lee un archivo tipo `.env` y exporta sus variables en `os.environ` con prioridad sobre las existentes, **antes** de importar `mia` (igual que `uvicorn --env-file`; las URL con `&` no se parten). Las importaciones de `mia` van dentro de las funciones de `puntajes`. `respuestas` también llama a `cargar_env(".env")` para leer `MIA_ARTIFACT_KEY` y `MIA_ADMIN_KEY`, sin pisar las variables ya exportadas en el shell
- [X] T005 En `scripts/linea_base.py`, implementar `contexto_corrida(etiqueta, destino, ...)` que arma el diccionario de la corrida de [data-model.md](data-model.md): fecha, `git rev-parse HEAD` y si hay cambios sin confirmar, `destino` (`local` si `localhost`/`127.0.0.1`, `produccion` si no; sin guardar la URL ni claves) y la carpeta de salida `tmp/linea_base/<fecha>-<etiqueta>/`. El umbral y los límites que registra son los **declarados en el archivo de entorno**, no necesariamente los de Railway (ver la tarea de verificación en US2)
- [X] T006 En `scripts/linea_base.py`, implementar `guardar_json(carpeta, nombre, datos)` y `leer_corrida(etiqueta)` (busca la carpeta más reciente `tmp/linea_base/*-<etiqueta>/`); crear la carpeta si falta. Confirmar con `git check-ignore tmp/linea_base/x.json` que `tmp/` está ignorado
- [X] T007 Agregar en `tests/unit/test_linea_base.py` pruebas de `cargar_casos` (casos válidos, id repetido, `espera` inválida, `documentos` vacío con `espera = respuesta`, categoría desconocida) y de `cargar_env` (prioridad sobre variables existentes, valor con `&`)

**Checkpoint**: las utilidades pasan sus pruebas; aún no hay casos reales.

---

## Phase 3: User Story 1 - Conjunto de casos de prueba de búsqueda (Priority: P1) 🎯 MVP

**Goal**: un archivo versionado con los casos: la batería del MVP completa, los dos de la sección 2.2, y al menos 3 nuevos en cada categoría indirecta, sigla y sin respuesta.

**Independent Test**: `cargar_casos` valida el archivo; una prueba confirma que todos los ids de `scripts/pruebas_mvp.py` están con la misma pregunta, dominios y resultado esperado, y que las cinco categorías están representadas (SC-001).

- [X] T008 [US1] Generar `scripts/datos/casos_busqueda.json` con un fragmento de Python de un solo uso (no se versiona) que importa `CASOS` de `scripts/pruebas_mvp.py` y escribe, para cada caso, `id`, `categoria: "mvp"`, `grupo` (letras iniciales del id: A, K, CU, U, P, G, N, X, I), `dominios`, `pregunta`, `espera`, `documentos` (a partir de `documento`, como lista de un elemento) y `contiene`. JSON con `ensure_ascii=False` e indentación de 2 espacios
- [X] T009 [US1] Agregar a `scripts/linea_base.py` el subcomando `inventario` (y a [contracts/linea-base-cli.md](contracts/linea-base-cli.md)): con `--env-file`, lista en solo lectura cada `Programa / Dominio` con su cantidad de documentos y fragmentos y los nombres de archivo de sus documentos. Sirve para redactar y validar los casos nuevos
- [X] T010 [US1] Correr `python scripts/linea_base.py inventario --env-file .env.produccion` y, con su salida, proponer al usuario un borrador de los casos nuevos: **3 indirectos** (`IN1` a `IN3`, que no repiten las palabras del documento), **3 con siglas** (`SG1` a `SG3`, una con la sigla y otra con la forma desarrollada) y **3 sin respuesta** (`SR1` a `SR3`, temas que no están en ningún dominio, uno de ellos cercano al tema de los documentos). Mostrar el borrador al usuario para que lo apruebe y marque los `documentos` esperados; **no escribir los casos nuevos sin su aprobación**
- [X] T011 [US1] Pedir al usuario el nombre completo de la persona del caso "¿Quién es *nombre y apellidos*?" (observado el 2026-10-13, ver sección 2.2 de [Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md)) y el dominio y documento donde aparece. Con eso agregar `S22-1` (`categoria: "seccion_2_2"`, `pregunta` con nombre y apellidos, `variante_corta` solo con el nombre) y `S22-2` (`pregunta`: "¿Qué líneas de trabajo final de graduación ofrece la maestría?", `variante_corta`: la misma con "TFG", dominios del currículum del programa donde está el documento de líneas de TFG; comparar con el caso `U4`)
- [X] T012 [US1] Agregar a `scripts/datos/casos_busqueda.json` los casos nuevos aprobados en T010, con `categoria`, `dominios`, `pregunta`, `espera`, `documentos` y `nota` breve
- [X] T013 [US1] Agregar en `tests/unit/test_linea_base.py` pruebas sobre el archivo real: carga sin errores; contiene todos los ids de `pruebas_mvp.CASOS` con la misma pregunta, dominios y `espera` (cargar `scripts/pruebas_mvp.py` con `importlib` como en T002); hay al menos 3 casos en cada categoría `indirecta`, `sigla` y `sin_respuesta`; hay 2 de `seccion_2_2` con `variante_corta`; ids únicos (SC-001)

**Checkpoint**: US1 completa. El conjunto existe y está validado; ya se puede usar para medir.

---

## Phase 4: User Story 2 - Medir puntajes y qué pasa el umbral (Priority: P1)

**Goal**: `puntajes` entrega, sin gastar tokens, los puntajes por caso, el barrido de umbrales y la ventana de separación, solo leyendo.

**Independent Test**: correr `puntajes --solo A1,N1,S22-1 --env-file .env.produccion`; el resultado de cada caso ("responde" o "sin información") coincide con lo que decide la API para ese caso, y la salida no tiene texto de fragmentos.

### Lógica pura (con pruebas primero)

- [X] T014 [US2] En `scripts/linea_base.py`, implementar `resultado_por_modo(candidatos, limite, umbral)` que devuelve `pasan` (cuántos de los primeros `limite` candidatos tienen puntaje >= umbral), `mejor_puntaje` y `resultado` (`responde` si `pasan > 0`, `sin_informacion` si no), idéntico a la regla de `src/mia/api/routes/query.py` (`relevant = [r for r in results if r.score >= threshold]`). Agregar sus pruebas en `tests/unit/test_linea_base.py`, incluido el borde `puntaje == umbral`
- [X] T015 [US2] En `scripts/linea_base.py`, implementar `posicion_esperados(candidatos, documentos)` que para cada fragmento de nombre de `documentos` da `posicion` y `puntaje` del mejor candidato cuyo nombre de archivo lo contiene (comparar normalizando con `unicodedata.normalize("NFC", ...)` como `pruebas_mvp.py`), o `ausente`. Con pruebas
- [X] T016 [US2] En `scripts/linea_base.py`, implementar `barrido_umbrales(mediciones, umbral_actual, desde=0.60, hasta=0.90, paso=0.01)` que, por modo y por umbral, lista los ids de casos cuyo resultado cambia respecto al umbral actual. Usar enteros (centésimas) para evitar errores de coma flotante. Con pruebas que cubran un caso que pasa a responder al bajar el umbral y uno que pasa a "sin información" al subirlo
- [X] T017 [US2] En `scripts/linea_base.py`, implementar `ventana_separacion(mediciones)` según [data-model.md](data-model.md): `max_sin_info` (máximo entre los casos `sin_informacion` del mejor puntaje), `min_respuesta` (mínimo entre los casos `respuesta` del puntaje del mejor documento esperado), `separables` (`min_respuesta > max_sin_info`) y `rango` si lo hay. Incluir en `max_sin_info` también los casos de aislamiento de dominio (`grupo` = `I`) y reportar además `max_sin_info_sin_aislamiento` por separado; excluir de `min_respuesta` los casos donde el esperado está `ausente` (listarlos y contarlos como casos que hoy fallarían por recuperación). Con pruebas, incluidos ambos resultados de `separables`
- [X] T018 [US2] En `scripts/linea_base.py`, implementar `parejas(mediciones, umbral)` para los casos con `variante_corta`: mejor puntaje de la completa y de la corta, y su distancia al umbral. Con una prueba

### Acceso a datos y comando

- [X] T019 [US2] En `scripts/linea_base.py`, implementar el acceso de solo lectura de `puntajes`: abrir la base con `mia.storage.db` (solo `select`) para resolver `Programa / Dominio` a id y los nombres de archivo de `Document` por `document_id`; obtener `get_embedding_provider(settings.embedding_provider)` y `get_vector_store()`; antes de buscar, comparar la dimensión de la colección (`get_collection(...).config.params.vectors.size`) con la del proveedor y salir con error si difieren (R10 de [research.md](research.md)). **No llamar a `init_db()` ni a `ensure_collection()`**: el primero migra la base de producción y el segundo crea índices en Qdrant. Abrir la base en una transacción de solo lectura (`SET TRANSACTION READ ONLY` en Postgres; en SQLite, `PRAGMA query_only = ON`). Incluir un guardia que haga fallar cualquier llamada de escritura a Qdrant (envolver el cliente con una lista de métodos permitidos: `query_points`, `count`, `get_collection`, `collection_exists`) y una prueba que lo demuestre
- [X] T020 [US2] En `scripts/linea_base.py`, implementar `medir_caso(caso, variante)`: embeber con `embed([pregunta], is_query=True)`, buscar con `limit=50` sobre los dominios del caso y devolver `candidatos` con `posicion`, `puntaje`, `documento` (nombre de archivo) y `dominio`. **Descartar `text`** apenas se lee el resultado; no guardarlo en ninguna estructura
- [X] T021 [US2] En `scripts/linea_base.py`, implementar el subcomando `puntajes` completo: cargar `--env-file` (T004), casos (T003) y filtrar con `--solo`; omitir con aviso los casos cuyo dominio no exista; correr `medir_caso` para la pregunta completa y la variante corta; calcular `por_modo` con los límites `settings.query_search_limit` y `settings.query_search_limit_razonamiento` y el umbral `settings.query_similarity_threshold`; calcular T015 a T018; guardar `puntajes.json` con el contexto (T005) incluyendo `fragmentos_por_dominio` (`count` con filtro de dominio); y mostrar un resumen legible por consola (ids, puntajes, cuántos pasan; sin texto de fragmentos)
- [X] T022 [US2] Pedir al usuario que confirme en Railway (servicio `MIA`, *Variables*) que `QUERY_SIMILARITY_THRESHOLD`, `QUERY_SEARCH_LIMIT` y `QUERY_SEARCH_LIMIT_RAZONAMIENTO` coinciden con los del archivo de entorno usado (hoy 0,82 y 8; el de razonamiento vale 16 si no está definido). Si difieren, repetir con los valores de Railway (variables exportadas antes de correr) y anotarlo en el informe
- [X] T023 [US2] Correr `python scripts/linea_base.py puntajes --etiqueta base --env-file .env.produccion` contra producción y verificar: termina en menos de 10 minutos (SC-005), no usa tokens, el resultado de `A1`, `N1` y `S22-1` coincide con el comportamiento observado de la API, y `git status` no muestra cambios fuera de `scripts/`, `tests/` y `specs/` (FR-016). Anotar la duración

**Checkpoint**: US2 completa. Se conocen los puntajes reales y la ventana de separación; ya se pueden responder las decisiones 3 y 5 de la sección 2.8 de V3 en cuanto a puntajes.

---

## Phase 5: User Story 3 - Medir la respuesta completa (Priority: P2)

**Goal**: `respuestas` registra por caso y modo: fuentes mostradas y esperadas, tiempo y costo, con tope de gasto.

**Independent Test**: correr `respuestas --solo S22-1,A1,N1 --modo ambos --tope-usd 0.20`; el informe trae para cada caso resultado, fuentes mostradas, esperadas y sobrantes, tiempo y costo, y el gasto total queda por debajo del tope.

- [X] T024 [US3] En `scripts/linea_base.py`, implementar `evaluar_respuesta(caso, status, body)` (lógica pura, sin red) que devuelve `resultado` (`respondio`, `sin_informacion`, `no_concluyente` si el HTTP no es 200), `correcto` (según `espera`, `documentos` y `contiene`, como `_evaluar` de `scripts/pruebas_mvp.py`), `fuentes_mostradas` (documentos distintos), `fuentes_esperadas_halladas`, `fuentes_sobrantes` (documentos mostrados que no contienen ningún fragmento de `documentos`; en casos `sin_informacion` todos los mostrados cuentan como sobrantes), `documentos_mostrados` y `contiene_ok` (booleano o nulo). **No guardar** la respuesta ni los `excerpt`. Con pruebas que usen cuerpos de respuesta de mentira, incluido un `no_concluyente`
- [X] T025 [US3] En `scripts/linea_base.py`, implementar el cliente HTTP de `respuestas` con la biblioteca estándar (copiar el patrón de `_request` y `_consultar` de `scripts/pruebas_mvp.py`: cabecera `X-Artifact-Key`, tres reintentos ante 502 con espera) y resolver `Programa / Dominio` a id con `GET /domains`. Medir el tiempo de pared por consulta (`latencia_cliente_ms`) y tomar `latency_ms` de la respuesta
- [X] T026 [US3] En `scripts/linea_base.py`, implementar `leer_costo(base_url, clave_admin, consulta_id)` con `GET /usage/queries/{id}` y la cabecera `X-Admin-Key` (la de la clave de automatización, como `scripts/cargar_carpeta.py`); devuelve `costo_usd`, `costo_estimado`, tokens y modelo y descarta pregunta, respuesta y demás campos. Si no hay clave de administración, devuelve `None` y avisa una sola vez
- [X] T027 [US3] En `scripts/linea_base.py`, implementar `resumen_respuestas(resultados)` por modo: casos correctos y fallidos (con ids), no concluyentes, fuentes sobrantes promedio, latencia p50 y p95 (percentiles por rango más cercano, sin dependencias), costo medio por consulta, costo medio de las consultas que terminan en "sin información" y gasto total. Con pruebas, incluido el caso con costos nulos
- [X] T028 [US3] En `scripts/linea_base.py`, implementar el subcomando `respuestas` completo: `--tope-usd` obligatorio (sale con error si falta o es <= 0); imprimir antes de empezar el número de consultas previstas (casos x modos) y, si hay clave de administración, el gasto del día y el tope diario del artefacto (según los contratos de [specs/002-panel-administracion/contracts/](../002-panel-administracion/contracts/)); omitir con aviso, y listar en `casos_omitidos`, los casos cuyos dominios el artefacto no pueda consultar; tratar un HTTP 429 (tope diario) como parada con aviso y no como `no_concluyente`; recorrer casos y modos acumulando el costo tras cada consulta y deteniéndose al alcanzar el tope (guardar lo hecho con `parcial: true`); `--modo literal|razonamiento|ambos`; `--solo`; guardar `respuestas.json` con el contexto y el resumen; salida por consola sin respuesta ni extractos. Con una prueba de la parada por tope usando funciones simuladas de consulta y costo
- [X] T029 [US3] Pedir al usuario que encienda la API de Railway (`python scripts/servicios.py encender MIA`; no hacerlo sin su orden). Las claves salen de `.env`. Correr `respuestas --solo S22-1,A1,N1 --modo ambos --tope-usd 0.20` y verificar el informe y que el gasto quedó bajo el tope
- [X] T030 [US3] Con el tope que el usuario fije para la corrida completa (proponer uno a partir del costo medio de T029 por el número de casos y modos), correr `respuestas --etiqueta base --modo ambos --tope-usd <N>` con todos los casos. No arrancar sin la cifra de T029 ni sin el tope aprobado por el usuario. Verificar que la suma de costos del script coincide con lo que sube el total de Uso del artefacto durante la ventana de la corrida, y pedir al usuario que la contraste con OpenRouter Activity (comprobación independiente, SC-006; es el mismo pendiente 15 de V2). Anotar los `consulta_id` de la corrida en `respuestas.json` para poder excluirlos de los totales de Uso

**Checkpoint**: US3 completa. Se conocen fuentes sobrantes, latencia y costo por consulta, incluidas las que terminan en "sin información".

---

## Phase 6: User Story 4 - Informe de línea base y comparación (Priority: P2)

**Goal**: un informe versionado que resume la línea base y responde las decisiones 3 y 5 de V3, y una forma de comparar corridas futuras.

**Independent Test**: `informe base` produce el Markdown; `comparar base base-2` da cero diferencias; la sección 2.8 de V3 enlaza al informe.

- [X] T031 [US4] En `scripts/linea_base.py`, implementar `comparar(a, b)` (lógica pura sobre dos corridas leídas): por caso, cambios de resultado, de mejor puntaje (diferencia mayor a 0,001) y de fuentes (mostradas y sobrantes); avisar si el `fragmentos_por_dominio` difiere entre corridas. Con pruebas que cubran: sin diferencias, un cambio de resultado, un cambio de puntaje menor al tope (no se reporta) y datos distintos
- [X] T032 [US4] En `scripts/linea_base.py`, implementar el subcomando `comparar` que lee las dos etiquetas (`leer_corrida`), usa `comparar` e imprime el resumen (código de salida 0 si no hay diferencias, 1 si las hay, 2 si no pudo leer)
- [X] T033 [US4] Repetir `puntajes` con `--etiqueta base-2` y comprobar con `comparar` (T032) o a mano con un diff de los JSON que los puntajes difieren menos de 0,001 y los resultados son iguales (SC-007).
- [X] T034 [US4] En `scripts/linea_base.py`, implementar `generar_informe(corrida)` y el subcomando `informe` (`--salida`, por defecto imprime por consola): Markdown en español, sin guion largo, con contexto de la corrida (fecha, commit, destino, umbral, límites, fragmentos por dominio), tabla por caso (categoría, esperado, resultado en cada modo, mejor puntaje, posición del esperado, fuentes mostradas y sobrantes, latencia, costo), barrido de umbrales, ventana de separación, parejas completa y corta, y los resúmenes por modo. Con una prueba que genera el informe de una corrida de mentira y verifica que no contiene guion largo ni claves
- [X] T035 [US4] Generar `docs/LINEA_BASE_BUSQUEDA.md` con `informe base --salida docs/LINEA_BASE_BUSQUEDA.md` y agregarle a mano una sección final "Lectura" con: qué dicen los números sobre cada opción de V3 (A bajar umbral, B pregunta limpia, C umbral por modo, D híbrida, E reranker, F citas), si hay ventana de separación, cuántos candidatos hay que recuperar para que aparezca el documento esperado (dato para el reranker), la línea base de BUS-5 (fuentes sobrantes) y de costo/latencia, y qué casos de la batería del MVP fallan hoy, si alguno. Sin texto de fragmentos ni de respuestas
- [X] T036 [US4] En [docs/Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md), sección 2.8: marcar las decisiones 3 (se permitió medir en producción, información pública para pruebas) y 5 (conjunto de casos definido, con el número final) como resueltas con enlace a `docs/LINEA_BASE_BUSQUEDA.md`, y agregar a las decisiones 1, 2 y 4 los números que ahora se conocen; actualizar la sección 1 (alcance) de V3 para decir que la línea base está medida, y la 2.9 si algún criterio queda más preciso con los datos. No decidir por el usuario: solo registrar los datos y proponer

**Checkpoint**: US4 completa. La línea base está documentada y se puede repetir y comparar.

---

## Phase 7: Polish & Cross-Cutting

- [X] T037 [P] Actualizar [docs/OPERACION.md](../../docs/OPERACION.md) con una sección breve "Medir la búsqueda (línea base)": qué hace la herramienta, comandos, que `puntajes` es de solo lectura, que `respuestas` gasta y exige `--tope-usd`, y enlace a [quickstart.md](quickstart.md) y al informe
- [X] T038 [P] Actualizar [docs/ARQUITECTURA.md](../../docs/ARQUITECTURA.md) con un párrafo sobre `scripts/linea_base.py` como herramienta de diagnóstico fuera del producto (qué lee, que no escribe, dónde deja la salida) y enlace a la feature 005
- [X] T039 [P] Agregar a [docs/PRUEBAS_MVP.md](../../docs/PRUEBAS_MVP.md) una nota que remita al conjunto de `scripts/datos/casos_busqueda.json` y al informe de la línea base para las mediciones de búsqueda posteriores a la versión 2
- [X] T040 Correr `ruff check scripts tests` y `pytest` completo; corregir lo que falle. Verificar con `git diff --stat main..dev -- src alembic` que no hay cambios en `src/` ni en migraciones (FR-016) y con `grep -rnP "\x{2014}" scripts/linea_base.py scripts/datos/casos_busqueda.json docs/LINEA_BASE_BUSQUEDA.md specs/005-linea-base-busqueda` que no hay ningún guion largo
- [X] T041 Revisar por muestreo `tmp/linea_base/*/` y `docs/LINEA_BASE_BUSQUEDA.md` para confirmar que no contienen texto de fragmentos ni de respuestas (SC-004). Marcar los criterios de aceptación de la sección 2.9 de V3 que esta feature deja medibles
- [ ] T042 Hacer commit en `dev` por etapa (herramienta, casos, informe, documentación) con mensajes en español sin atribución y `git push origin dev`. Pedir al usuario si quiere apagar la API de Railway y dejar `main` para después (el merge lo hace él)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; bloquea las historias.
- **US1 (Phase 3)**: depende de Foundational. T010 y T011 requieren al usuario (aprobación de casos y nombre de la persona).
- **US2 (Phase 4)**: depende de Foundational y de US1 (necesita los casos). Las funciones puras T014 a T018 pueden hacerse antes de que los casos estén completos.
- **US3 (Phase 5)**: depende de Foundational y de US1; es independiente de US2 (puede ir antes o después). T029 y T030 requieren la API de Railway encendida (la enciende el usuario); las claves ya están en `.env`.
- **US4 (Phase 6)**: `comparar` (T031, T032) solo necesita Foundational; el informe (T034, T035) necesita datos de US2 y, idealmente, de US3. T033 depende de T032.
- **Polish (Phase 7)**: al final.

### User Story Dependencies

- US1 (P1) es la base de medición. US2 (P1) y US3 (P2) la usan y no dependen entre sí. US4 (P2) consume los resultados de US2 y US3.

### Parallel Opportunities

- T002 junto a T001 (archivos distintos).
- Dentro de US2, T014 a T018 son funciones independientes en el mismo archivo: se pueden escribir en cualquier orden, pero no editar a la vez.
- US2 y US3 pueden desarrollarse en paralelo por distintas personas o sesiones, salvo por el mismo archivo.
- T037 a T039 son archivos de documentación distintos.

---

## Implementation Strategy

### MVP (US1 + US2)

1. Phase 1 y 2: esqueleto y utilidades.
2. US1: casos (con aprobación del usuario).
3. US2: puntajes. **Parar y validar**: con esto ya se sabe si hay ventana de separación, que es el dato central de V3, sin gastar un centavo del proveedor de modelos.

### Entrega incremental

1. MVP.
2. US3: respuestas con tope de gasto (cuando el usuario encienda la API).
3. US4: informe, comparación y actualización de V3.
4. Polish y commits.

### Riesgos a vigilar

- Que `puntajes` quede distinto de lo que hace la API (mismo `is_query=True`, mismo filtro de dominios, mismos límites): T023 lo comprueba con casos conocidos.
- Que se imprima o guarde texto de fragmentos: T020 y T024 lo descartan al leer; T041 lo revisa.
- Que `respuestas` gaste de más: el tope es obligatorio y se verifica contra Uso (T030).
