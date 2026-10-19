# MIA: Definición de Requerimientos de la Versión 3

**Qué es este documento:** punto de partida de los requerimientos de la tercera versión de MIA. **Es un borrador abierto: de momento solo recoge un tema, las consultas no directas, y su implementación se deja para después** (decisión del 2026-10-13). El 2026-10-14 se agregó la investigación de técnicas y proyectos similares (sección 2.4) y se acordó la recomendación provisional con una prueba de un reranker local (sección 2.6 y 2.7). El 2026-10-15 se midió la línea base de la búsqueda en producción (feature [005](../specs/005-linea-base-busqueda/spec.md), informe en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md)). Parte del estado descrito en [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md) y [ARQUITECTURA.md](ARQUITECTURA.md). Los otros candidatos para esta versión ya están listados en la sección 10 del documento de la versión 2 y se incorporarán aquí cuando se decida su alcance.

## 1. Alcance acordado hasta ahora

| Id | Tema | Estado |
|---|---|---|
| BUS-1 a BUS-7 | Responder consultas que no coinciden de forma directa con el texto de los documentos y mostrar solo las fuentes que sirvieron (sección 2) | Requerimientos definidos, **implementación pendiente**; línea base medida el 2026-10-15 ([informe](LINEA_BASE_BUSQUEDA.md)); la prueba del reranker local (2.7) está planificada, no ejecutada |

## 2. Consultas no directas

### 2.1 Qué se quiere

Que la Consulta administrativa (y cualquier artefacto que use `POST /query`) responda bien preguntas formuladas con las palabras de una persona y no con las del documento, como lo hace una herramienta del tipo NotebookLM. Hoy una pregunta correcta puede terminar en "No encontré información suficiente" solo porque se parece poco al texto.

### 2.2 Casos que hoy fallan

| Caso | Pregunta que falla | Variante que sí responde | Qué pasa |
|---|---|---|---|
| Pregunta sobre una persona | "¿Quién es *nombre y apellidos*?" (observado el 2026-10-13 en modo con razonamiento) | Escribir solo "*nombre y apellidos*" | La respuesta "sin información" llegó en 0,1 s, o sea sin consultar al modelo: ningún fragmento superó el umbral de similitud. Con solo el nombre sí lo superó y el documento se encontró. |
| Siglas | "¿Qué líneas de trabajo final de graduación ofrece la maestría?" (prueba del 2026-10-06, ver [PRUEBAS_MVP.md](PRUEBAS_MVP.md)) | Preguntar con "TFG" | La forma desarrollada no alcanza el umbral contra un documento que usa la sigla. |

Los dos casos tienen la misma causa: el sistema descarta los fragmentos cuya similitud con la pregunta queda bajo `QUERY_SIMILARITY_THRESHOLD` y, si no queda ninguno, responde "sin información" sin llamar al modelo (`src/mia/api/routes/query.py`). Una pregunta completa ("¿Quién es X?") se parece menos a un fragmento que el nombre solo. Es un diagnóstico por lectura del código y de las pruebas anteriores: no se han medido los puntajes reales.

### 2.3 Requerimientos

| Id | Requerimiento |
|---|---|
| BUS-1 | Una pregunta sobre un nombre propio, una sigla o un término que aparece en los documentos debe encontrar esos documentos aunque la pregunta tenga palabras de más ("¿Quién es X?", "¿Qué es el TFG?", "háblame de X"). **Avance del 2026-10-18** (feature [008](../specs/008-pregunta-limpia/spec.md), `QUERY_CLEAN_QUESTION`, apagada por defecto): el segundo intento con la pregunta limpia resuelve una de las tres personas de la línea base y solo con razonamiento; el resto queda pendiente de la recuperación (el documento aparece en los puestos 12 a 43 o puntúa justo bajo el umbral) y de las siglas (reranker E y búsqueda híbrida D). Ver [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md). **Avance del 2026-10-18** (feature [009](../specs/009-reranker-local/spec.md), `RERANK_PROVIDER`, apagado por defecto): el reranker local resuelve a las personas cuyo documento estaba en los puestos 14 a 25 (5 de 5 casos medidos, en los dos modos); Joseph Obando, las líneas de TFG y las siglas siguen pendientes de la búsqueda híbrida (D). |
| BUS-2 | Una pregunta con la forma desarrollada de una sigla, o con la sigla cuando el documento usa la forma desarrollada, debe encontrar el mismo documento. |
| BUS-3 | Ningún cambio debe aumentar de forma notable las respuestas inventadas: cuando los documentos de verdad no tienen la información, la respuesta sigue siendo "sin información suficiente". |
| BUS-4 | Los topes de gasto (por artefacto y de toda la API) se siguen respetando, y el costo adicional por consulta, si lo hay, queda visible en el módulo Uso. |
| BUS-5 | Las fuentes que muestra una respuesta son solo las que aportaron a ella, no todos los fragmentos que se le pasaron al modelo (hoy una respuesta puede listar documentos que no sirvieron, ver [PRUEBAS_MVP.md](PRUEBAS_MVP.md)). **Implementado y medido el 2026-10-16** (feature [006](../specs/006-fuentes-que-aportaron/spec.md), variable `QUERY_CITED_SOURCES`, apagada por defecto): las fuentes que no aportaron bajan alrededor de 80 % sin cambiar respuestas, costo ni latencia de forma medible. Resultado en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md). |
| BUS-6 | Cualquier etapa nueva de búsqueda (reranker, búsqueda híbrida, reformulación) se puede apagar por configuración, igual que las demás piezas del pipeline (interfaz y fábrica por nombre), de modo que se pueda volver al comportamiento anterior sin desplegar código. |
| BUS-8 | Ninguna respuesta debe quedar incompleta ni cortada: una lista o sección completa de un documento (contenidos de un curso, líneas de TFG, requisitos) debe devolverse completa y, si no cabe en lo que se entrega al modelo o la generación se corta por cualquier motivo, la respuesta lo dice en vez de presentarse como completa. **Implementado y medido el 2026-10-18** (feature [007](../specs/007-respuestas-completas/spec.md), variables `QUERY_COMPLETE_CONTEXT` y `QUERY_RETRY_CUT_ANSWERS`, apagadas por defecto). Resultado en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md). |
| BUS-7 | El segundo intento con la pregunta "limpia" (opción B) se hace por reglas de texto, sin llamar a un modelo de lenguaje: no consume tokens de OpenRouter. Solo suma un embedding local y una búsqueda en Qdrant. **Implementado y medido el 2026-10-18** (feature [008](../specs/008-pregunta-limpia/spec.md), variable `QUERY_CLEAN_QUESTION`, apagada por defecto): ayuda menos de lo esperado (de tres personas, una, y solo con razonamiento), no inventa respuestas y cuesta cerca de 0,001 USD por consulta de identificación que antes era "sin información". Resultado en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md). |

### 2.4 Investigación (2026-10-14)

Se buscó cómo logran NotebookLM y proyectos parecidos encontrar coincidencias con preguntas poco literales y mostrar solo las fuentes relevantes. **Límite:** Google no publica el interior de NotebookLM; lo que hay son blogs y guías de terceros. Los proyectos abiertos revisados (README en GitHub) describen qué hacen, no cómo. Las cifras de terceros no se verificaron de forma independiente.

#### Qué se sabe de NotebookLM

- Responde solo con lo que hay en las fuentes del cuaderno y cita las fuentes (cada cita enlaza al pasaje).
- Se asocia con Gemini y su ventana de contexto muy larga. Un blog dice que con pocas fuentes puede meter documentos completos sin trocear; otro describe un índice que busca fragmentos relevantes y se los pasa al modelo. Ambas descripciones se contradicen y ninguna está confirmada.
- Deducción (sin confirmar): la diferencia principal con MIA es que no hay una puerta de similitud antes del modelo. Se le pasan los fragmentos más cercanos, o documentos enteros, y el modelo decide si hay respuesta y qué citar.
- Google ofrece a desarrolladores la herramienta File Search de la API de Gemini (RAG administrado, con citas por página desde mayo de 2026). No está confirmado que NotebookLM la use.

#### Son dos problemas distintos

| Problema | Hoy en MIA | Técnicas |
|---|---|---|
| **A. Encontrar** el documento aunque la pregunta se parezca poco al texto | Solo vectores (modelo local e5-small) y un umbral de similitud duro: si ningún fragmento lo supera, no se llama al modelo. | Búsqueda híbrida, reranker, reformulación de la pregunta, contexto por fragmento, evaluador de relevancia |
| **B. Mostrar solo las fuentes relevantes** | Se listan todos los fragmentos pasados al modelo. | Que el modelo cite lo que usó, puntaje de relevancia visible, filtrado por un evaluador |

#### Técnicas para encontrar (problema A)

| Técnica | Qué hace | Evidencia |
|---|---|---|
| Búsqueda híbrida | Combina BM25 (coincidencia de términos) con vectores y fusiona los rankings, normalmente con RRF. | Varias guías la llaman la mejora de mayor impacto sobre una búsqueda solo vectorial; BM25 es el mejor señal para nombres propios y siglas. |
| Reranker | Un modelo que lee pregunta y fragmento juntos reordena un grupo grande de candidatos (ver más abajo). | Ejemplo de Anthropic: de 150 candidatos pasan 20; los fallos bajan de 2,9 % a 1,9 %. |
| Reformular la pregunta | Reescritura por modelo, varias versiones o HyDE (se busca con una respuesta hipotética). | Cada una suma una llamada al modelo; se sugiere usarla solo si el mejor puntaje es bajo. |
| Contexto por fragmento (Contextual Retrieval) | Al indexar, un modelo antepone a cada fragmento una frase que lo sitúa en su documento (sirve para vectores y BM25). | Fallos entre los 20 mejores: 5,7 % con vectores solos, 3,7 % con contexto, 2,9 % con contexto y BM25, 1,9 % con reranking. Costo: unos 1,02 USD por millón de tokens de documentos, una sola vez. |
| Evaluador de relevancia (CRAG) | Un modelo pequeño clasifica lo recuperado como correcto, ambiguo o incorrecto y filtra. | Investigación publicada; poco usado en la práctica. |

#### Técnicas para mostrar solo lo relevante (problema B)

- **Que el modelo cite lo que usó.** Es lo que hacen la API de Citations de Claude (cada afirmación lleva su cita, con página en los PDF) y Gemini File Search (citas por página). Solo se muestra lo citado, no todo lo recuperado. Mi lectura, sin confirmar, es que NotebookLM funciona así.
- **Puntaje de relevancia visible y aviso.** Kotaemon muestra el puntaje en cada cita y avisa cuando la búsqueda trae fragmentos poco relevantes.
- **Advertencia.** El benchmark ALCE (EMNLP 2023) halló que incluso los mejores modelos dejaban la mitad de las respuestas de uno de sus conjuntos sin respaldo completo en sus citas. Las citas del modelo pueden estar mal: se deben validar, no tratarse como garantía.

#### Proyectos similares

| Proyecto | Lo que su README documenta |
|---|---|
| Kotaemon | Recuperación híbrida (texto completo y vectores), reranking, citas con visor de PDF y resaltado, puntaje de relevancia, GraphRAG opcional. |
| RAGFlow | Comprensión profunda del documento, fragmentación por plantillas visible y editable, "múltiples recuperaciones con reranking fusionado" y citas rastreables. |
| Open Notebook, SurfSense, AnythingLLM, NotebookLlama | Citan fuentes y hacen búsqueda de texto y vectorial; su README no explica el reranking ni cómo se generan las citas (habría que leer el código). |

#### El reranker en detalle

Un reranker es una segunda pasada de ordenamiento. Lo que hace MIA hoy es un **bi-encoder**: el modelo de embeddings convierte la pregunta y cada fragmento en vectores por separado (los de los fragmentos, de antemano) y solo compara los vectores. Es muy rápido, pero cada texto se comprime en un vector y se pierden los detalles de cómo se relacionan una pregunta y un fragmento concretos. Un **cross-encoder** lee pregunta y fragmento juntos, en una sola pasada, y devuelve un número de relevancia. Es mucho más preciso, pero no se puede precalcular: corre por cada par en cada consulta, así que solo se usa sobre un grupo reducido.

```
pregunta
  |
  v  1. Recuperación amplia y barata (vectores, o híbrida): los N mejores (N de 50 a 150)
  v  2. Reranker: puntúa cada par (pregunta, candidato)
  v  3. Se ordena por ese puntaje y se corta: los K mejores (5 a 20) y/o los que superan un mínimo
  v  4. Esos fragmentos van al modelo de lenguaje (y de ahí salen las fuentes)
```

| Tipo | Cómo funciona | Contra |
|---|---|---|
| Cross-encoder local | Modelo pequeño (familia MiniLM o BGE) que corre en el propio servidor. | Ocupa memoria y CPU; hay que elegir uno multilingüe para español. |
| API de reranking (Cohere, Voyage, Jina) | Se envían la pregunta y los candidatos; devuelve los puntajes. | Cuesta por búsqueda y sale información a un tercero. |
| Un LLM como reranker | Se le pide que puntúe o reordene los candidatos. | Más lento y caro. |
| ColBERT (interacción tardía) | Compara a nivel de palabras. | Exige otro índice. |

Límites: solo reordena lo que ya se recuperó (si el documento no entra entre los N candidatos, nunca aparece); lee unos 512 tokens por fragmento; su puntaje no es el coseno (un umbral sobre él es más fiable, pero hay que calibrarlo); y suma latencia, del orden de cientos de milisegundos a pocos segundos en CPU según el modelo (no medido en MIA).

### 2.5 Opciones de solución (sin decidir)

| Opción | Problema | Qué cambia | Costo y riesgo |
|---|---|---|---|
| A. Bajar el umbral de similitud | A | Variable de entorno en Railway, sin código. | Más fragmentos poco relacionados llegan al modelo y más consultas sin respuesta lo llaman (cuestan). Hay que recalibrar. |
| B. Segundo intento con la pregunta "limpia" | A | Si ningún fragmento pasa el umbral, repetir la búsqueda sin la envoltura ("¿Quién es X?" pasa a "X"). Por reglas, sin modelo. | Bajo costo y riesgo. Cubre nombres y "qué es X", no las siglas. |
| C. Umbral distinto por modo | A | Con razonamiento aceptar un umbral más bajo y más fragmentos. | La consulta cuesta más cuando entra ruido. |
| D. Búsqueda híbrida (BM25 y vectores) | A | Esquema de Qdrant con vectores dispersos y reindexación completa. | El cambio más grande. Solución de fondo para nombres propios y siglas. |
| E. Reranker (cross-encoder) | A y B | Etapa nueva entre la búsqueda y el armado del contexto; el corte pasa a ser por su puntaje. | Memoria y latencia en el servidor (local) o un tercero (API). Se prueba en 2.7. |
| F. Citas por fragmento | B | Numerar los fragmentos en la instrucción, pedir que el modelo cite sus números y mostrar solo los citados. | Sin reindexar ni llamadas extra. Hay que validar que las citas sean correctas (ALCE). |
| G. Contexto por fragmento al indexar | A | Una pasada de modelo sobre todos los documentos al ingerir. | Costo único por reindexar; lo más potente de la lista según la fuente. |

#### Opción B en detalle: el segundo intento con la pregunta "limpia"

**Costo:** no usa ningún modelo de lenguaje (BUS-7). La búsqueda normal se hace como hoy; solo si ningún fragmento supera el umbral, un código de reglas le quita a la pregunta su envoltura, se calcula el embedding de la versión corta con el modelo local y se repite la búsqueda en Qdrant. Si aparecen fragmentos, el modelo de lenguaje responde con ellos (la única llamada a OpenRouter de la consulta). Si tampoco hay resultados, sigue sin llamar al modelo, como hoy. No existe un estándar para esto en español: en recuperación de información se llama *query reformulation* o *query reduction* y cada proyecto escribe sus reglas. Sí hay piezas estándar reutilizables, como las listas de palabras vacías (*stopwords*) en español de NLTK, spaCy o Snowball.

**Principio:** solo reglas para preguntas de **identificación o descripción** ("¿Quién es X?", "¿Qué es X?", "háblame de X"), donde la respuesta es todo lo que dicen los documentos sobre X y por eso conviene buscar solo X. En una pregunta como "¿Cuántos créditos tiene X?" el resto de la pregunta importa y quitarlo la dañaría, así que esas no se tocan.

**Normalización previa:** quitar `¿ ? ¡ !`, espacios sobrantes, y comparar sin distinguir mayúsculas ni tildes (devolviendo el texto original).

**Reglas propuestas (al inicio de la pregunta):**

| Grupo | Patrón (resumido) | Entrada | Resultado |
|---|---|---|---|
| Cortesía y rodeos | `(por favor,?)? (me )?(puedes\|podrías) (decir\|explicar\|indicar)(me)?`, `dime`, `quiero saber`, `necesito saber`, `quisiera saber` | "¿Me puedes decir quién es X?" | "quién es X" (pasa al grupo siguiente) |
| Interrogativo y verbo ser | `(quién(es)?\|qué\|cuál(es)?) (es\|son\|era\|fue\|significa) (el\|la\|los\|las\|un\|una)?` | "¿Quién es *nombre y apellidos*?" | "*nombre y apellidos*" |
| | | "¿Qué es el TFG?" | "TFG" |
| Pedir información | `(háblame\|cuéntame\|dame\|quiero) (información\|datos\|detalles) (sobre\|acerca de\|de)` | "Dame información sobre la maestría" | "la maestría" |
| Pedir que hable de algo | `(háblame\|cuéntame) (de\|sobre\|acerca de)`, `qué (sabes\|se sabe\|hay) (de\|sobre\|acerca de)` | "¿Qué se sabe de Cibercrimen?" | "Cibercrimen" |

Además se recorta lo que sobre al final ("por favor", signos).

**Guardas para no estropear nada:**
- Si el resultado queda con menos de 3 caracteres, o es igual a la pregunta original, no se hace el segundo intento.
- Un solo intento por consulta, y solo si la primera búsqueda no pasó el umbral.
- Si ningún patrón aplica, no hay segundo intento (por ejemplo, "¿Cuántos créditos tiene X?").
- El registro de consultas anota que se usó la reformulación, para medir cuántas veces ayuda.

**Pruebas:** pruebas unitarias en tabla con los ejemplos de arriba, casos negativos (la pregunta de créditos debe quedar sin reformular) y variantes con y sin tildes ni signos de interrogación. Lo más importante para ajustar la lista son las preguntas reales del personal: con ellas se descubre qué formas se usan de verdad.

**Alternativas descartadas por ahora:**
- *Quitar todas las palabras vacías* (listas de NLTK o spaCy): es más general, pero "¿Cuántas horas tiene el curso?" quedaría en "horas curso", pierde el sentido y no está claro que ayude a un modelo de embeddings. Podría probarse como un tercer intento y medirse con los casos de prueba.
- *Reconocimiento de nombres propios* (spaCy `es_core_news`): detectaría un nombre sin depender de la forma de la pregunta, pero añade una dependencia que consume memoria, el recurso escaso en Railway.
- *Detectar secuencias de palabras con mayúscula inicial* como heurística de nombres propios: es barato, pero falla con nombres escritos en minúscula y con siglas.

**Límites:** cubre bien nombres propios y "qué es X"; no resuelve las siglas ("trabajo final de graduación" frente a "TFG"), porque ahí el problema es el vocabulario y no la envoltura de la pregunta (eso lo cubren D, E o G). Las reglas son para español y hay que mantenerlas.

### 2.6 Recomendación provisional (confirmada el 2026-10-14)

Se acordó seguir esta recomendación como punto de partida y **probar un cross-encoder que corra en el servidor para medir cuánto cuesta y decidir después si se conserva**:

1. **F. Citas por fragmento.** Resuelve el problema B sin reindexar ni costo extra. **Hecha (2026-10-16, feature 006), apagada por defecto**: el modelo cierra la respuesta con una línea `FUENTES: 1, 3`, la API la valida y lista solo esos pasajes; sin citas válidas se listan todos (regla de seguridad, 2 % de las respuestas en la medición).
2. **B. Segundo intento con la pregunta limpia** (solo si nada pasa el umbral). Cubre "¿Quién es X?" a bajo costo. **Hecha (2026-10-18, feature 008), apagada por defecto**: no inventa y cuesta poco, pero resuelve una de las tres personas de la línea base (solo con razonamiento): el documento de una persona queda en el puesto 12 a 43 aun con el nombre solo, o puntúa 0,819 contra el umbral de 0,82. Se excluyó "cuál es" de las formas (pide datos). Lo que queda pasa por E (reranker) y D (híbrida).
3. **E. Reranker local, como prueba de costo** (plan en 2.7). Si se conserva, el corte de "sin información" pasa a su puntaje y se puede retirar el umbral de coseno. **Hecha (2026-10-18, feature 009), apagada por defecto (`RERANK_PROVIDER=none`)**: separa las preguntas sin respuesta (con el mínimo 0,06 ninguno de 14 casos pasa; el coseno no podía) y rescata a las personas cuyo documento estaba en los puestos 14 a 25 (Natalia Soto Solís, Cubillo y tres variantes, en los dos modos). Corre en Railway dentro de la latencia (0,30 s en p50) pero ocupa unos 158 MB más (queda unos 10 MB sobre el límite de 512 MB) y cuesta, por estimación, 1 a 1,6 USD al mes; una regresión conocida (`IN3`). Queda a la espera de que el usuario acepte ese costo. Ver [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md).
4. **D. Búsqueda híbrida** para nombres y siglas, cuando haya evidencia de que B y E no bastan.
5. **G. Contexto por fragmento**, opcional y al final.

Antes de implementar cualquiera: armar el conjunto de casos de prueba (ver 2.9) y medir la línea base, para saber cuánto mejora cada paso.

### 2.7 Prueba del cross-encoder local (ejecutada el 2026-10-18, feature 009)

**Resultado (2026-10-18):** se probó `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (ONNX int8, 119 MB, Apache 2.0) en local y en Railway. Calidad: mejora los casos de personas (5 de 5 con el documento entre los 30 primeros candidatos), bloquea los 14 casos sin respuesta con el mínimo 0,06 (margen estrecho: 0,057 el mayor caso sin respuesta) y pierde 1 caso que hoy funciona (`IN3`). Latencia añadida en Railway: 0,30 s en p50 y 0,34 s en p95 con 4 hilos y 128 tokens por pasaje. Memoria: +158 MB (522 a 524 MB en reposo, picos de 600 MB). No resuelve siglas ni Obando (recuperación). Recomendación: conservar apagado y encender si se acepta el costo. El texto siguiente es el plan original. Resultados completos en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md).


**Pregunta que responde:** ¿un cross-encoder corriendo en el propio servidor mejora lo suficiente la búsqueda y las fuentes como para justificar su costo en memoria y tiempo?

**Punto de partida técnico:** la API usa `onnxruntime` y `sentencepiece` con el modelo de embeddings e5-small cuantizado a int8 (`src/mia/rag/providers/local_embeddings.py`), precisamente para evitar PyTorch y caber en poca memoria. Un cross-encoder exportado a ONNX e int8 seguiría el mismo patrón. Con el servicio en reposo la API usa unos 340 MB de RAM en Railway Hobby ([OPERACION.md](OPERACION.md)).

**Candidatos (por verificar: tamaño, licencia y disponibilidad en ONNX):** un cross-encoder multilingüe pequeño de la familia MiniLM (por ejemplo `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`), y uno más grande de la familia BGE o Jina multilingüe como referencia de calidad. Requisitos: soporte de español, ONNX o exportable, licencia permisiva, y un tamaño que quepa.

**Diseño:**
- Una interfaz `RerankProvider` con fábrica por nombre (`RERANK_PROVIDER`: `none` por defecto, `local`), igual que las demás piezas (BUS-6). Con `none` el comportamiento es el actual.
- En `POST /query`: recuperar más candidatos (por ejemplo 30 a 50 en lugar de 8 o 16), puntuarlos con el reranker y quedarse con los mejores. El umbral de similitud pasa a ser el puntaje del reranker (a calibrar), con un mínimo configurable.
- Guardar en el registro de consultas el mejor puntaje, para calibrar y para detectar "sin información" dudosas.

**Qué se mide (línea base con `RERANK_PROVIDER=none`, luego con el reranker):**

| Medida | Cómo | Para qué |
|---|---|---|
| Memoria | RAM de la API en reposo y con carga, con y sin el modelo cargado (en local y en Railway) | Si cabe en el plan actual |
| Latencia añadida | p50 y p95 por consulta con N candidatos (variando N) | Si es aceptable frente a los 3 s (literal) y 5 s (razonamiento) actuales |
| Calidad | Los 15 casos de [PRUEBAS_MVP.md](PRUEBAS_MVP.md) más los dos casos de 2.2 y los que se agreguen: respuestas correctas, "sin información" correctos, y qué fuentes se muestran | Si BUS-1, BUS-2, BUS-3 y BUS-5 mejoran sin romper nada |
| Costo mensual | Cambio de uso de Railway (hoy unos 4 a 4,5 USD de los 5 incluidos) | Si exige subir de plan |

**Dónde se prueba:** primero en local con los datos de producción (como en la validación de la versión 2); después, si el resultado es prometedor, en Railway con la variable activada, comprobando el uso de memoria del servicio. Se apaga cambiando la variable.

**Criterios para decidir (propuesta, a confirmar antes de medir):** se conserva si mejora los casos que hoy fallan, no empeora ninguno de los 15, la latencia añadida del p95 queda dentro de lo que se acepte, y la memoria cabe sin subir de plan (o con un aumento de costo que se acepte de forma explícita). Si no, se deja apagado y se pasa a D.

**Riesgos:**
1. **Memoria.** Un cross-encoder multilingüe puede no caber junto al modelo de embeddings en el plan actual; por eso es una prueba y no una decisión.
2. **Privacidad.** Se descarta por ahora una API externa de reranking: recibiría la pregunta y los fragmentos, que incluyen actas con datos personales, y hoy esos datos solo salen hacia OpenRouter con retención cero. Un tercero nuevo exigiría revisar sus condiciones.
3. **Calibración.** El puntaje del reranker no es el coseno: el umbral hay que calibrarlo con casos reales, incluidas preguntas sin respuesta en los documentos.

### 2.8 Decisiones pendientes

Datos de la línea base medida el 2026-10-15 en [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md) (sección "Lectura").

1. **Cuánto gasto extra por consulta sin respuesta se acepta** (decide entre A y C, y entre B y E). *Datos:* hoy una consulta sin respuesta cuesta 0 si la corta el umbral y entre 0,0008 y 0,02 USD si llega al modelo (0,0008 a 0,001 en modo literal). El segundo intento (B) y el reranker local no agregan costo de modelos; las opciones A y C quedan descartadas por los datos (punto siguiente). **Resuelta (2026-10-18):** el reranker local no suma costo de modelos de lenguaje, así que el gasto extra aceptable por consulta es cero; sí suma costo de servidor (ver la decisión 2).
2. **Límites aceptables de memoria y de latencia** para conservar el reranker (propuesta en 2.7). *Datos:* latencia actual del cliente, p50 / p95: 1,7 s / 5,0 s en literal y 3,4 s / 11,2 s en razonamiento; la memoria no se midió. **Resuelta (2026-10-18):** la API completa bajo 512 MB de RAM en reposo y dentro de los 5 USD del plan, y el reranker con p50 de hasta 0,5 s y p95 de hasta 1,5 s con unos 30 candidatos. Medido: latencia 0,30 s y 0,34 s (cumple); memoria 522 a 524 MB (no cumple por unos 10 MB) y costo mensual estimado sobre los 5 USD (decisión explícita del usuario pendiente).
3. ~~Si se permite consultar a Qdrant de producción para medir los puntajes.~~ **Resuelta (2026-10-15):** el usuario declaró públicos los datos para pruebas; se midió directamente contra producción en solo lectura. Ver [LINEA_BASE_BUSQUEDA.md](LINEA_BASE_BUSQUEDA.md).
4. **Qué modelo probar primero** (candidatos en 2.7, por verificar). *Dato:* para capturar el documento esperado bastan 20 a 40 candidatos antes del reranker. **Resuelta (2026-10-18):** `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`; los modelos más grandes (BGE, Jina) no entran en la prueba.
5. ~~Cuántos casos de prueba hacen falta.~~ **Resuelta (2026-10-15):** el conjunto es `scripts/datos/casos_busqueda.json` con 32 casos (los 19 de la batería de [PRUEBAS_MVP.md](PRUEBAS_MVP.md), 4 de la sección 2.2 con su variante corta, 3 indirectos, 3 con siglas y 3 sin respuesta). Alcanza para ver el patrón; para calibrar un corte por puntaje del reranker convendrá sumar más casos de siglas y de preguntas dudosas.

### 2.9 Criterios de aceptación (borrador)

- Los casos de la sección 2.2 (`S22-1` a `S22-4`, nombres y apellidos y sigla) responden con la pregunta completa igual que con la variante corta (BUS-1 y BUS-2). Hoy fallan 7 de las 8 preguntas de esos casos en literal y 6 en razonamiento. Con `QUERY_CLEAN_QUESTION=on` (feature 008) la pregunta completa de `S22-1` responde con su documento en razonamiento (no en literal); `S22-3` y `S22-4` siguen en "sin información" (medido el 2026-10-18).
- Los 19 casos de [PRUEBAS_MVP.md](PRUEBAS_MVP.md) (los 15 que esperan respuesta y los 4 de "sin información") siguen respondiendo bien, como hoy en los dos modos.
- Una pregunta sobre un tema que no está en ningún documento sigue respondiendo "sin información suficiente" (BUS-3).
- Ninguna respuesta se entrega cortada sin aviso y las listas de documentos de hasta 25 fragmentos salen completas (BUS-8). Línea base de la feature 007: de las 6 listas de programas de curso medidas solo la de Diseño de Experimentos salía cortada; con `QUERY_COMPLETE_CONTEXT=on` sale completa. El reintento no se necesitó en la medición (ningún fin anormal en unas 230 llamadas al modelo).
- Las fuentes mostradas son las que aportaron a la respuesta; en los casos de prueba no se lista ningún documento que no sirvió (BUS-5). Línea base: 1,39 fuentes sobrantes por consulta en literal y 2,69 en razonamiento. **Con `QUERY_CITED_SOURCES=on` (feature 006): 0,28 y 0,47** (-80 %); los documentos que siguen apareciendo no se validaron uno por uno (criterio del usuario: mejor que sobren a que falten). El 2026-10-16 el usuario aprobó encenderla; falta su merge a `main` y se dejó `QUERY_CITED_SOURCES=on` en las variables de Railway (con la API apagada).
- El costo medio por consulta de los modos literal y con razonamiento, medido en el módulo Uso, no sube más de lo que se decida en la decisión pendiente 1 (BUS-4).
- Con `RERANK_PROVIDER=none` el comportamiento es el anterior (BUS-6). Cumplido en la feature 009 (pruebas automáticas; con `none` el módulo del modelo ni se importa).
- El segundo intento no hace ninguna llamada a un modelo de lenguaje: una consulta sin respuesta en ninguna de las dos búsquedas sigue sin gastar tokens (BUS-7).
- Las reglas de reformulación pasan sus pruebas en tabla, incluidos los casos negativos como "¿Cuántos créditos tiene X?", que no se reformula. Cumplido en la feature 008 (83 filas en `tests/unit/test_query_rewrite.py`).

## Anexo A. Fuentes de la investigación (2026-10-14)

- [Contextual Retrieval (Anthropic)](https://www.anthropic.com/news/contextual-retrieval)
- [Citations (Claude API docs)](https://platform.claude.com/docs/build-with-claude/citations)
- [Enabling LLMs to Generate Text with Citations (ALCE)](https://arxiv.org/pdf/2305.14627)
- [Corrective Retrieval Augmented Generation (CRAG)](https://arxiv.org/pdf/2401.15884)
- [ARAGOG: Advanced RAG Output Grading](https://arxiv.org/pdf/2404.01037)
- [Gemini API File Search: multimodal, filtros de metadatos y citas por página](https://www.techwyse.com/news/ai-search/google-gemini-api-file-search-multimodal-rag-update)
- [Kotaemon (README)](https://raw.githubusercontent.com/Cinnamon/kotaemon/main/README.md)
- [RAGFlow (README)](https://raw.githubusercontent.com/infiniflow/ragflow/main/README.md)
- [Open Notebook (README)](https://raw.githubusercontent.com/lfnovo/open-notebook/main/README.md)
- [SurfSense (README)](https://raw.githubusercontent.com/MODSetter/SurfSense/main/README.md)
- [Hybrid Search for RAG (Denser)](https://denser.ai/blog/hybrid-search-for-rag/)
- [Hybrid search and reranking for RAG (WZ-IT)](https://wz-it.com/en/knowledge/ki/hybrid-search-reranking/)
- [Hybrid Search for RAG: BM25, SPLADE and Vector Search (PremAI)](https://blog.premai.io/hybrid-search-for-rag-bm25-splade-and-vector-search-combined)
- [Query Rewriting (ZeroEntropy)](https://www.zeroentropy.dev/concepts/query-rewriting/)
- [NotebookLM: guía de terceros sobre fuentes y citas (KZSoftworks)](https://www.kzsoftworks.com/blog/notebooklm-this-ai-is-grounded-in-your-documents-not-the-whole-internet)
- [Mejores alternativas de código abierto a NotebookLM (Peekaboo Labs)](https://peekaboolabs.ai/blog/best-open-source-notebooklm-alternatives)
