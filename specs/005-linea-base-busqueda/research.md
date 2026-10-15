# Research: Línea base de la búsqueda de MIA

Todas las incógnitas de la spec quedaron resueltas; no hay marcadores `NEEDS CLARIFICATION`. Fecha: 2026-10-15. Revisado el mismo día tras la aclaración de que la información es pública y se mide en producción.

## R1. Cómo medir puntajes sin cambiar el producto

**Decisión**: un script que importa los componentes de `mia` y repite la parte de recuperación de `POST /query` ([query.py](../../src/mia/api/routes/query.py)): `get_embedding_provider(settings.embedding_provider).embed([pregunta], is_query=True)` y `get_vector_store().search(vector, domains=..., limit=N)`. Se pide una sola vez **N = 50** (máximo que acepta `query_search_limit`) y los resultados de cada modo son los primeros 8 (literal) o 16 (razonamiento), que es lo que la API ve, porque Qdrant devuelve los candidatos ordenados.

**Justificación**: la API hoy no expone puntajes, y agregar un modo de diagnóstico contradice "sin cambiar el producto" (FR-016). Reutilizar las fábricas garantiza los mismos vectores y el mismo orden. Pedir 50 de una vez sirve además para saber en qué posición aparece el documento esperado, dato que necesitará el reranker (cuántos candidatos recuperar).

**Alternativas descartadas**: (a) agregar `debug` a `/query`: toca el producto y arriesga exponer puntajes o texto; (b) llamar a Qdrant por HTTP a mano: duplica la lógica y puede divergir; (c) repetir la medición solo con la API: no entrega puntajes.

## R2. Datos de la medición: directamente contra producción

**Decisión** (aclaración del 2026-10-15, que reemplaza la del 2026-10-14): se mide contra producción (Qdrant Cloud y Neon, con las credenciales de `.env.produccion`, que el script carga con `--env-file` igual que `uvicorn --env-file`). No se arma ninguna copia local. El usuario indicó que toda la información cargada se considera pública y se puede usar para pruebas.

**Justificación**: la copia local solo se justificaba por privacidad (las actas tienen datos personales) y esa premisa se retiró para las pruebas. Medir en producción es más fiel (los datos que se miden son los que responden a las consultas reales) y ahorra montar Qdrant y reingestar.

**Lo que se conserva**: la medición de puntajes sigue siendo estrictamente de solo lectura (nunca se escribe en Qdrant ni en la base), porque medir no debe alterar el producto; y la de respuestas sigue con tope de gasto. Producción se identifica como `destino: produccion` en el contexto de la corrida (FR-014).

**Alternativas descartadas**: copia local (esfuerzo y datos que pueden divergir de producción sin ganar nada ahora); medir solo con la API (no entrega puntajes).

## R3. Cómo se resuelven los dominios y los nombres de documento

**Decisión**: en `puntajes`, los nombres `Programa / Dominio` se resuelven leyendo la base de metadatos con SQLAlchemy y **solo SELECT** (tablas de dominios, programas y documentos); en `respuestas` se usa `GET /domains` de la API con la clave del artefacto, como `pruebas_mvp.py`. Los nombres de archivo de los documentos se obtienen de la tabla de documentos. Contra producción, `puntajes` necesita entonces `DATABASE_URL` (Neon) además de Qdrant; ambas viven en `.env.produccion`. Si no se quisiera dar acceso a la base, la alternativa es resolver los dominios con `GET /domains` y limitar los nombres de documento a su id.

**Justificación**: `puntajes` ya necesita las credenciales de Qdrant y la base (las mismas variables que usa la API, cargadas con `--env-file`, igual que `uvicorn --env-file`); `respuestas` no debe necesitar nada más que la clave del artefacto y la URL.

## R4. Qué se guarda y qué no

**Decisión** (con la información considerada pública, 2026-10-15):
1. Se permiten nombres reales en las preguntas, los casos y los nombres de documento, tanto en la salida local como en lo versionado. Se eliminan los marcadores `{{clave}}`, `tmp/nombres_casos.json`, los alias de documentos y la verificación de `informe` contra esos valores.
2. Se conserva una sola regla de higiene, sin costo: ninguna estructura de la herramienta guarda el `text` de fragmentos, el texto de las respuestas ni el `excerpt` de las fuentes. De la respuesta solo quedan su longitud, si es "sin información" y si contiene el texto esperado (`contiene_ok`). No hace falta para medir, evita informes enormes y sigue valiendo si la política de datos cambia.
3. Las preguntas de las corridas de `respuestas` quedan en el registro de Uso de producción y suman a sus totales y a los topes diarios. El usuario decidió (2026-10-15) usar un artefacto existente en lugar de crear uno propio de pruebas, así que la corrida comparte su tope diario con el uso real: `respuestas` muestra el gasto del día y el tope antes de empezar, se detiene ante un 429 y guarda los `consulta_id` para excluirlos de los totales de Uso.
4. Si más adelante se agregan datos que no sean públicos, esta decisión debe revisarse antes de medir.

**Alternativas descartadas**: mantener marcadores y alias (complejidad sin beneficio con datos públicos).

## R5. Qué resultado se calcula con los puntajes

**Decisión**, por caso y por modo (límite 8 o 16):
- Lista de candidatos (posición, puntaje, documento, dominio) y cuántos pasan el umbral configurado.
- Mejor puntaje general, y, si el caso tiene documentos esperados, la posición y el puntaje del mejor fragmento de cada documento esperado.
- Resultado de recuperación: "responde" si algún candidato dentro del límite alcanza el umbral, "sin información" si no. Es exactamente la regla de la API (`relevant = [r for r in results if r.score >= threshold]`, y sin `relevant` responde sin llamar al modelo).
- **Barrido de umbrales** de 0,60 a 0,90 en pasos de 0,01: para cada umbral, qué casos cambian de resultado frente al configurado.
- **Ventana de separación** (BUS-3): el máximo, entre los casos que esperan "sin información", del mejor puntaje, y el mínimo, entre los casos que esperan respuesta, del mejor puntaje de un documento esperado. Si el mínimo supera al máximo hay un rango de umbrales que separa ambos grupos; si no, ningún umbral basta y hace falta un segundo criterio (reranker). Esta cifra es el dato central para decidir entre A, C, B y E.
- Parejas "pregunta completa / variante corta": ambos mejores puntajes y su distancia al umbral.

**Justificación**: son exactamente los números que piden las decisiones 3 y 5 de V3 y no necesitan el modelo de lenguaje.

## R6. Medición de la respuesta completa (costo, tiempo, fuentes)

**Decisión**: reutilizar el patrón de `pruebas_mvp.py` (HTTP con la biblioteca estándar, reintentos ante 502) y agregar: nº de fuentes distintas, esperadas encontradas, sobrantes, tiempo medido por el cliente y `latency_ms` de la API. El costo y los tokens **no vienen en la respuesta de `/query`**; se leen con `GET /usage/queries/{id}` usando la clave de automatización (`MIA_ADMIN_KEY` o `--clave-admin`), que ya existe para los scripts, y se descartan los demás campos (en particular pregunta y respuesta).

El tope de gasto es **obligatorio** (`--tope-usd`): se acumula el costo tras cada consulta y la corrida se detiene al alcanzarlo (el sobregiro máximo es el de una consulta). Antes de empezar se imprime el número de consultas previstas. "Aportó" no se infiere: lo decide el usuario en `documentos` de cada caso (FR-010).

Para SC-006: el costo sale del propio módulo Uso, así que compararlo con su total solo comprueba que no se perdieron consultas (suma del script frente al aumento del total del artefacto en la ventana). La verificación independiente es el detalle de gasto de OpenRouter, que mira el usuario (es el mismo pendiente 15 de V2).

**Alternativas descartadas**: agregar costo a la respuesta de `/query` (toca el producto); leer la base de metadatos para el costo (obliga a tener credenciales de la base de producción en esta etapa).

## R7. Formato y ubicación de los casos y las salidas

**Decisión**: JSON (`scripts/datos/casos_busqueda.json`), porque ya se usa en `scripts/datos/reorganizacion_v2.json` y no requiere dependencias. Salida cruda en `tmp/linea_base/<fecha>-<etiqueta>/{puntajes,respuestas}.json` con un `corrida` (contexto) y una lista de resultados por caso. Esquemas en [data-model.md](data-model.md) y comandos en [contracts/linea-base-cli.md](contracts/linea-base-cli.md).

**Alternativas descartadas**: YAML (dependencia nueva), CSV (no sirve para listas anidadas), SQLite (sobredimensionado).

## R8. Cuántos casos y de qué categorías

**Decisión**: la batería de aceptación completa (19 filas con ids A, U, P, K, CU, G, N, X, I; los "15" de V3 son los 15 que esperan respuesta, incluido `X1`, y los otros 4 esperan "sin información"; se conservan todos con sus ids), los dos casos de la sección 2.2 con su variante corta, y **al menos 3 casos nuevos** en cada una de: indirecta, sigla, sin respuesta (SC-001). Total previsto: unos 30. Los casos nuevos los redacta Claude como borrador a partir de los nombres de documentos y dominios, y el usuario marca los documentos esperados.

**Justificación**: con 3 por categoría se detecta un patrón sin multiplicar el costo del modo con razonamiento; si el informe muestra una categoría ambigua, se amplían después.

## R9. Reproducibilidad y comparación

**Decisión**: cada corrida guarda su contexto (fecha, commit, umbral, límites, proveedor de embeddings, destino, conteo de fragmentos por dominio). `comparar A B` informa por caso los cambios de resultado, de mejor puntaje (diferencia mayor a 0,001, SC-007) y de fuentes, y avisa si el conteo de fragmentos por dominio difiere (datos distintos). La repetibilidad (SC-007) se comprueba corriendo `puntajes` dos veces y comparando.

## R11. Parámetros declarados frente a los de Railway

**Decisión**: el umbral y los límites de búsqueda se toman del entorno cargado (`.env.produccion`, hoy 0,82 y 8; el de razonamiento usa su valor por defecto, 16) y se registran como "declarados". La API no los expone, así que una tarea pide al usuario confirmar en Railway que coinciden antes de dar por buena la línea base.

## R10. Compatibilidad del modelo de vectores

**Decisión**: antes de buscar, `puntajes` compara la dimensión de la colección (`get_collection(...).config.params.vectors.size`) con la del proveedor de embeddings y se niega a seguir si difieren (edge case de la spec), igual que ya hace `ensure_collection` al ingerir. Solo se lee la configuración de la colección.
