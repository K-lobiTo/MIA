# Research: Línea base de la búsqueda de MIA

Todas las incógnitas de la spec quedaron resueltas; no hay marcadores `NEEDS CLARIFICATION`. Fecha: 2026-10-15.

## R1. Cómo medir puntajes sin cambiar el producto

**Decisión**: un script que importa los componentes de `mia` y repite la parte de recuperación de `POST /query` ([query.py](../../src/mia/api/routes/query.py)): `get_embedding_provider(settings.embedding_provider).embed([pregunta], is_query=True)` y `get_vector_store().search(vector, domains=..., limit=N)`. Se pide una sola vez **N = 50** (máximo que acepta `query_search_limit`) y los resultados de cada modo son los primeros 8 (literal) o 16 (razonamiento), que es lo que la API ve, porque Qdrant devuelve los candidatos ordenados.

**Justificación**: la API hoy no expone puntajes, y agregar un modo de diagnóstico contradice "sin cambiar el producto" (FR-016). Reutilizar las fábricas garantiza los mismos vectores y el mismo orden. Pedir 50 de una vez sirve además para saber en qué posición aparece el documento esperado, dato que necesitará el reranker (cuántos candidatos recuperar).

**Alternativas descartadas**: (a) agregar `debug` a `/query`: toca el producto y arriesga exponer puntajes o texto; (b) llamar a Qdrant por HTTP a mano: duplica la lógica y puede divergir; (c) repetir la medición solo con la API: no entrega puntajes.

## R2. Datos de la medición: copia local primero, producción solo para confirmar

**Decisión** (aclaración del 2026-10-14, opción C): la medición normal usa una copia local (Qdrant en docker compose y SQLite) ingestada desde `tmp/` con `scripts/cargar_carpeta.py`, el mismo procedimiento de [OPERACION.md](../../docs/OPERACION.md). Contra producción solo se corre cuando se pasa `--confirmo-produccion` y el usuario lo autorizó para esa corrida. El script detecta producción cuando `QDRANT_URL` no apunta a `localhost`/`127.0.0.1` y, sin esa bandera, se niega a continuar.

**Justificación**: la copia local reproduce los mismos vectores (mismo modelo local) y los mismos fragmentos si se usan los mismos archivos. Producción sirve para confirmar que no hay diferencias (documentos cambiados desde entonces). Para comparar ambas, cada corrida registra el conteo de fragmentos por dominio (FR-014).

**Alternativas descartadas**: medir solo en producción (riesgo y credenciales de Neon/Qdrant en cada corrida); medir solo local (no detectaría diferencias con producción).

## R3. Cómo se resuelven los dominios y los nombres de documento

**Decisión**: en `puntajes`, los nombres `Programa / Dominio` se resuelven leyendo la base de metadatos con SQLAlchemy y **solo SELECT** (tablas de dominios, programas y documentos); en `respuestas` se usa `GET /domains` de la API con la clave del artefacto, como `pruebas_mvp.py`. Los nombres de archivo de los documentos se obtienen de la tabla de documentos.

**Justificación**: `puntajes` ya necesita las credenciales de Qdrant y la base (las mismas variables que usa la API, cargadas con `--env-file`, igual que `uvicorn --env-file`); `respuestas` no debe necesitar nada más que la clave del artefacto y la URL.

## R4. Privacidad de las salidas

**Decisión**:
1. Ninguna estructura de la herramienta guarda `text` de fragmentos, el texto de la respuesta ni el `excerpt` de las fuentes: se descartan al leer. La respuesta se reduce a longitud, "sin información" sí/no y si contiene el texto esperado (`contiene_ok`). No existe ninguna opción para imprimir texto.
2. El archivo versionado de casos usa marcadores `{{clave}}` en lugar de nombres reales de personas; sus valores salen de `tmp/nombres_casos.json` (ignorado por git, ya cubierto por `tmp/` en `.gitignore`). Sin ese archivo los casos con marcadores se omiten con aviso (escenario 3 de la historia 1).
3. **Los nombres de archivo de los documentos también pueden contener nombres de personas** (p. ej. los trabajos de graduación llevan el nombre del autor). La spec permite "nombres de documento", pero para lo que se versiona se aplica una regla más estricta: la salida cruda local (en `tmp/linea_base/`) conserva los nombres de archivo; el informe versionado los reemplaza por alias (`D01`, `D02`...) con la etiqueta del dominio, y la tabla de equivalencias queda solo en local. Se ajusta FR-006 en la spec.
4. `informe` verifica antes de escribir que ningún valor de `tmp/nombres_casos.json` ni ningún nombre de archivo aparezca en el texto de salida y, si aparece, aborta.
5. La etapa `respuestas` envía las preguntas a la API, que las guarda en el registro de consultas (módulo Uso, "las preguntas pueden contener datos personales", ver OPERACION.md). Por eso las preguntas con nombres reales se corren de preferencia contra la API local y, contra producción, solo con la misma confirmación.

**Alternativas descartadas**: confiar en que nadie imprima por error (no verificable); cifrar la salida (sobredimensionado para un único usuario).

## R5. Qué resultado se calcula con los puntajes

**Decisión**, por caso y por modo (límite 8 o 16):
- Lista de candidatos (posición, puntaje, alias de documento, dominio) y cuántos pasan el umbral configurado.
- Mejor puntaje general, y, si el caso tiene documentos esperados, la posición y el puntaje del mejor fragmento de cada documento esperado.
- Resultado de recuperación: "responde" si algún candidato dentro del límite alcanza el umbral, "sin información" si no. Es exactamente la regla de la API (`relevant = [r for r in results if r.score >= threshold]`, y sin `relevant` responde sin llamar al modelo).
- **Barrido de umbrales** de 0,60 a 0,90 en pasos de 0,01: para cada umbral, qué casos cambian de resultado frente al configurado.
- **Ventana de separación** (BUS-3): el máximo, entre los casos que esperan "sin información", del mejor puntaje, y el mínimo, entre los casos que esperan respuesta, del mejor puntaje de un documento esperado. Si el mínimo supera al máximo hay un rango de umbrales que separa ambos grupos; si no, ningún umbral basta y hace falta un segundo criterio (reranker). Esta cifra es el dato central para decidir entre A, C, B y E.
- Parejas "pregunta completa / variante corta": ambos mejores puntajes y su distancia al umbral.

**Justificación**: son exactamente los números que piden las decisiones 3 y 5 de V3 y no necesitan el modelo de lenguaje.

## R6. Medición de la respuesta completa (costo, tiempo, fuentes)

**Decisión**: reutilizar el patrón de `pruebas_mvp.py` (HTTP con la biblioteca estándar, reintentos ante 502) y agregar: nº de fuentes distintas, esperadas encontradas, sobrantes, tiempo medido por el cliente y `latency_ms` de la API. El costo y los tokens **no vienen en la respuesta de `/query`**; se leen con `GET /usage/queries/{id}` usando la clave de automatización (`MIA_ADMIN_KEY` o `--clave-admin`), que ya existe para los scripts, y se descartan los demás campos (en particular pregunta y respuesta).

El tope de gasto es **obligatorio** (`--tope-usd`): se acumula el costo tras cada consulta y la corrida se detiene al alcanzarlo (el sobregiro máximo es el de una consulta). Antes de empezar se imprime el número de consultas previstas. "Aportó" no se infiere: lo decide el usuario en `documentos` de cada caso (FR-010).

Para SC-006 (costo del informe coincide con Uso) el costo ya sale del módulo Uso, así que se verifica contra el total del período que muestra `GET /usage` para el artefacto durante la corrida (suma de las consultas del script frente al total del artefacto en esa ventana) y, al menos una vez, contra OpenRouter Activity, como ya está pendiente en el criterio 15 de V2.

**Alternativas descartadas**: agregar costo a la respuesta de `/query` (toca el producto); leer la base de metadatos para el costo (obliga a tener credenciales de la base de producción en esta etapa).

## R7. Formato y ubicación de los casos y las salidas

**Decisión**: JSON (`scripts/datos/casos_busqueda.json`), porque ya se usa en `scripts/datos/reorganizacion_v2.json` y no requiere dependencias. Salida cruda en `tmp/linea_base/<fecha>-<etiqueta>/{puntajes,respuestas}.json` con un `corrida` (contexto) y una lista de resultados por caso. Esquemas en [data-model.md](data-model.md) y comandos en [contracts/linea-base-cli.md](contracts/linea-base-cli.md).

**Alternativas descartadas**: YAML (dependencia nueva), CSV (no sirve para listas anidadas), SQLite (sobredimensionado).

## R8. Cuántos casos y de qué categorías

**Decisión**: la batería de aceptación completa (19 filas con ids A, U, P, K, CU, G, N, X, I; las que en V3 se llaman "los 15" son las de respuesta esperada; se conservan todas con sus ids), los dos casos de la sección 2.2 con su variante corta, y **al menos 3 casos nuevos** en cada una de: indirecta, sigla, sin respuesta (SC-001). Total previsto: unos 30. Los casos nuevos los redacta Claude como borrador a partir del tipo de documentos (sin leer texto de las actas con datos personales) y el usuario marca los documentos esperados.

**Justificación**: con 3 por categoría se detecta un patrón sin multiplicar el costo del modo con razonamiento; si el informe muestra una categoría ambigua, se amplían después.

## R9. Reproducibilidad y comparación

**Decisión**: cada corrida guarda su contexto (fecha, commit, umbral, límites, proveedor de embeddings, `QDRANT_URL` reducido a "local" o "remoto", conteo de fragmentos por dominio). `comparar A B` informa por caso los cambios de resultado, de mejor puntaje (diferencia mayor a 0,001, SC-007) y de fuentes, y avisa si el conteo de fragmentos por dominio difiere (datos distintos). La repetibilidad (SC-007) se comprueba corriendo `puntajes` dos veces y comparando.

## R10. Compatibilidad del modelo de vectores

**Decisión**: antes de buscar, `puntajes` compara la dimensión de la colección (`get_collection(...).config.params.vectors.size`) con la del proveedor de embeddings y se niega a seguir si difieren (edge case de la spec), igual que ya hace `ensure_collection` al ingerir. Solo se lee la configuración de la colección.
