# Data Model: Línea base de la búsqueda de MIA

No hay tablas ni migraciones: son estructuras JSON en archivos. Nada de esto se guarda en las bases de MIA.

## Caso de prueba de búsqueda (`scripts/datos/casos_busqueda.json`, versionado)

Lista de objetos con:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `id` | texto | sí | Único. Los de la batería de aceptación conservan su id (`A1`, `U4`, `I2`...). Los nuevos usan prefijos `IN` (indirecta), `SG` (sigla), `SR` (sin respuesta) y `S22` (sección 2.2). |
| `categoria` | `mvp` \| `seccion_2_2` \| `indirecta` \| `sigla` \| `sin_respuesta` | sí | Los casos de aislamiento `I1` a `I3` y el caso `N1` quedan en `mvp`; el subtipo va en `grupo`. |
| `grupo` | texto | no | Letra de grupo de PRUEBAS_MVP (A, K, CU, U, P, G, N, X, I), solo informativo. |
| `dominios` | lista de texto | sí | Nombres `Programa / Dominio`. |
| `pregunta` | texto | sí | Puede llevar marcadores `{{clave}}`. |
| `variante_corta` | texto | no | La misma pregunta en su forma corta (solo nombre, o la sigla), también con marcadores. |
| `espera` | `respuesta` \| `sin_informacion` | sí | Resultado esperado. |
| `documentos` | lista de texto | solo si `espera = respuesta` | Fragmentos de nombre de archivo que deben aparecer entre las fuentes y que **aportan**; los marca el usuario. Pueden llevar marcadores. |
| `contiene` | texto | no | Texto que debe aparecer en la respuesta (puede llevar marcador). |
| `nota` | texto | no | Por qué existe el caso. Sin datos personales. |

**Reglas de validación**: ids únicos; `documentos` no vacío si `espera = respuesta`; todo marcador usado debe estar definido en `tmp/nombres_casos.json` o el caso se omite con aviso; ningún valor de ese archivo puede aparecer literal en `casos_busqueda.json`.

## Valores locales (`tmp/nombres_casos.json`, no versionado)

Objeto simple `{ "clave": "valor real" }`. Resuelve los marcadores `{{clave}}`. Si falta el archivo, los casos con marcadores se omiten.

## Corrida (contexto de una medición)

| Campo | Descripción |
|---|---|
| `etiqueta` | Nombre elegido por quien opera (p. ej. `base-local`). |
| `fecha` | Fecha y hora de inicio. |
| `commit` | Commit del código (`git rev-parse HEAD`) y si había cambios sin confirmar. |
| `destino` | `local` o `remoto` (por `QDRANT_URL`/`--url`); nunca la URL completa. |
| `umbral` | `QUERY_SIMILARITY_THRESHOLD` vigente. |
| `limite_literal`, `limite_razonamiento` | `QUERY_SEARCH_LIMIT` y `QUERY_SEARCH_LIMIT_RAZONAMIENTO`. |
| `candidatos_pedidos` | 50. |
| `proveedor_embeddings` | `EMBEDDING_PROVIDER` y dimensión del vector. |
| `fragmentos_por_dominio` | Conteo por `Programa / Dominio`. |
| `casos_omitidos` | Ids omitidos y motivo (falta de marcador, dominio ausente). |

## Medición de puntajes de un caso (`puntajes.json`)

| Campo | Descripción |
|---|---|
| `caso_id` | Id del caso. |
| `variante` | `completa` o `corta`. |
| `candidatos` | Lista de hasta 50: `posicion` (1...), `puntaje`, `documento` (nombre de archivo, solo en la salida cruda), `dominio`. Nunca `text`. |
| `por_modo` | Para `literal` y `razonamiento`: `pasan` (cuántos superan el umbral), `mejor_puntaje`, `resultado` (`responde`/`sin_informacion`). |
| `esperados` | Por cada fragmento de `documentos`: `posicion` y `puntaje` del mejor candidato cuyo archivo lo contiene, o `ausente`. |

## Resumen de puntajes de una corrida

| Campo | Descripción |
|---|---|
| `barrido_umbrales` | Por umbral (0,60 a 0,90): ids de casos que cambian de resultado frente al configurado, por modo. |
| `ventana_separacion` | `max_sin_info` (mayor mejor puntaje entre los casos `sin_informacion`), `min_respuesta` (menor puntaje del documento esperado entre los casos `respuesta`), `separables` (`min_respuesta > max_sin_info`), `rango` si lo hay. |
| `parejas` | Por caso con variante corta: puntajes y distancia al umbral. |

## Medición de respuesta de un caso (`respuestas.json`)

| Campo | Descripción |
|---|---|
| `caso_id`, `modo` | Identificación. |
| `resultado` | `respondio`, `sin_informacion` o `no_concluyente` (error persistente del proveedor, HTTP distinto de 200). |
| `correcto` | Si coincide con `espera` (y con `documentos` y `contiene`, si aplica). |
| `fuentes_mostradas` | Nº de documentos distintos listados. |
| `fuentes_esperadas_halladas`, `fuentes_sobrantes` | Cruce con `documentos` del caso. |
| `documentos_mostrados` | Nombres de archivo (solo salida cruda). |
| `contiene_ok` | Booleano o nulo; nunca el texto de la respuesta. |
| `latencia_cliente_ms`, `latencia_api_ms` | Tiempos. |
| `costo_usd`, `costo_estimado`, `tokens` | De `GET /usage/queries/{id}`. |
| `consulta_id` | Id del registro de Uso. |

## Resumen de respuestas de una corrida

Por modo: casos correctos y fallidos (con ids), no concluyentes, fuentes sobrantes promedio, latencia p50 y p95, costo medio por consulta, costo medio de las consultas que terminan en "sin información" y gasto total frente al tope.

## Informe de línea base (`docs/LINEA_BASE_BUSQUEDA.md`, versionado)

Generado por `informe` con alias de documentos (`D01`...) y sin nombres reales; contiene el contexto de la corrida, la tabla por caso, los resúmenes anteriores y la ventana de separación, y se completa a mano con la lectura de las decisiones 3 y 5 de V3.
