# Research: Reranker local

Decisiones de diseño con su razón y las alternativas. Las cifras de la línea base están en [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md). Las mediciones de R2 se hicieron el 2026-10-18 en la laptop de desarrollo (AMD Ryzen 5 7520U, 8 hilos, Python 3.13, `onnxruntime` 1.30) y **no son las de Railway**; sirven para diseñar y para saber qué medir.

## R1. Modelo: `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, variante ONNX int8 oficial

**Decision**: se usa el archivo `onnx/model_quint8_avx2.onnx` del repositorio `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` de HuggingFace, con el tokenizador `sentencepiece.bpe.model` del mismo repositorio.

**Verificado (2026-10-18)**:

| Dato | Valor |
|---|---|
| Licencia | Apache 2.0 (etiqueta `license:apache-2.0` del repositorio) |
| Idiomas | entrenado con mMARCO (MS MARCO traducido a 14 idiomas, entre ellos español); el autor indica que rinde bien en otros idiomas |
| Arquitectura | `XLMRobertaForSequenceClassification`, 12 capas, 384 de ancho, vocabulario de 250 002, una sola salida (logit) |
| ONNX oficial | sí: `onnx/model.onnx` (471 MB, fp32) y variantes cuantizadas `model_quint8_avx2`, `model_qint8_avx512`, `model_qint8_avx512_vnni` y `model_qint8_arm64`, todas de 118,6 MB |
| Entradas del grafo | `input_ids`, `attention_mask` (sin `token_type_ids`); salida `logits` |
| Formato del par | `<s> pregunta </s></s> pasaje </s>`, ids de sentencepiece desplazados en 1 (igual que el modelo de embeddings: BOS 0, PAD 1, EOS 2, UNK 3) |

**Rationale**: ya existe el ONNX cuantizado, sin exportar ni convertir nada; usa la misma pila que los embeddings (`onnxruntime`, `sentencepiece`); la licencia permite su uso; y el modelo de embeddings es de la misma familia (XLM-R pequeño), así que el tamaño en disco es parecido. Se elige la variante `quint8_avx2` porque corre en cualquier procesador x86 con AVX2 (todos los de Railway); las variantes `avx512` y `vnni` aprovechan más instrucciones pero podrían no correr en un procesador sin ellas, y `arm64` no aplica.

**Alternatives considered**: modelos BGE o Jina multilingües (decisión del usuario del 2026-10-18: no entran en esta feature, no cabrían en 512 MB); exportar nosotros el modelo con Optimum (trabajo y dependencias de PyTorch para algo que ya existe); la variante fp32 (471 MB, no cabe).

**Riesgo conocido**: la cuantización a 8 bits puede mover los puntajes respecto de fp32. No se compara con fp32: el mínimo se calibra con el modelo que de verdad se ejecuta (R10).

## R2. Medición previa: calidad, memoria y latencia

Script de prueba (no incluido en el repositorio), con el modelo cuantizado, `intra_op_num_threads` indicado y `enable_cpu_mem_arena=False` como el modelo de embeddings.

**Calidad (muestra mínima, 5 pares)**:

| Pregunta | Pasaje | Logit |
|---|---|---|
| ¿Quién es Natalia Soto Solís? | "Natalia Soto Solís es profesora de la Escuela de Computación y coordina el posgrado." | 10,95 |
| (la misma) | "El clima de Cartago es húmedo en octubre." | -9,90 |
| (la misma) | "Acta de la sesión ordinaria sobre el presupuesto del laboratorio." | -5,99 |
| ¿Quién es Fulano Inventado Pérez? (persona inventada) | el de Natalia | -6,00 |
| (la misma) | el del presupuesto | -5,96 |

Lectura: con pasajes que mencionan a la persona el puntaje es muy alto y con pasajes ajenos o sin la persona queda entre -10 y -6. Es la separación que el coseno no da (0,83 a 0,85 para una persona inventada). Una muestra de 5 pares no calibra nada; la calibración real se hace con los casos de la herramienta (R10).

**Memoria (RSS del proceso)**:

| Etapa | RSS |
|---|---|
| Python con `onnxruntime` y NumPy | 69 MB |
| Más el modelo de embeddings (como la API) | 260 MB |
| Más el reranker cargado | 414 MB (**+154 MB**) |
| Después de puntuar lotes de 8 pasajes | 417 a 451 MB |
| Pico durante la prueba | 560 MB |

Lectura: Railway informa unos 340 MB con la API en reposo; sumarle 154 MB da unos 495 MB, justo bajo el límite de 512 MB de SC-007, sin margen. El pico de 560 MB incluye la carga del archivo y la prueba con muchos pasajes. Hay que medirlo en la API real y en Railway (T-medición) y tener palancas (R9).

**Latencia (30 candidatos, lotes de 8, el mismo pasaje repetido, mediana de 3 corridas)**:

| Tokens máximos por pasaje | 1 hilo | 2 hilos | 4 hilos |
|---|---|---|---|
| 128 | 2,83 s | 1,55 s | 1,04 s |
| 256 | 7,35 s | 4,37 s | 2,92 s |
| 480 | 18,18 s | 10,96 s | 7,52 s |

Con 1 hilo y pasajes de unos 150 tokens: 20 candidatos 2,9 s, 30 candidatos 3,8 s, 40 candidatos 5,0 s; con pasajes de unos 300 tokens, 7,1 s, 10,6 s y 14,1 s. Los fragmentos de MIA miden 1000 caracteres con 200 de solape (`ingestion/chunker.py`), es decir, unos 250 a 300 tokens.

Lectura: la latencia crece casi linealmente con candidatos x tokens y baja con los hilos. **Con fragmentos completos y 30 candidatos no se cumple el límite de 1,5 s en p95 ni con 4 hilos.** Para acercarse hay que combinar: menos tokens por pasaje (los primeros 128 a 192 suelen bastar para decidir si el pasaje trata de lo preguntado), menos candidatos (un piso de coseno que descarte los claramente ajenos), y más hilos (si el plan de Railway los da). La medición en Railway decide qué combinación cumple, o si ninguna.

**Alternatives considered**: puntuar solo los 10 a 15 mejores por coseno (no captura el documento en los puestos 12 a 43, que es la razón de ser de la feature); un reranker más pequeño (no hay uno multilingüe con ONNX oficial de menor tamaño verificado).

## R3. Cómo entra en la ruta

**Decision**: con el reranker activo, la recuperación es una función auxiliar (`_retrieve`) que hace: búsqueda en Qdrant con `RERANK_CANDIDATES` resultados, descarte opcional por piso de coseno, puntaje del reranker, y selección. La selección (función pura `rerank_candidates`) ordena por puntaje de mayor a menor (empates en el orden de coseno, estable), descarta los que no llegan a `RERANK_MIN_SCORE` y se queda con los primeros `config.search_limit` del modo. A cada fragmento seleccionado se le reemplaza el campo `score` por el puntaje del reranker (copia con `dataclasses.replace`; el almacén no se toca).

**Rationale**: `build_passages` (`rag/context.py`) ordena por `score` y elige el documento principal por el mejor `score`; si el campo lleva el puntaje del reranker, el contexto, las citas y las respuestas completas usan el nuevo orden sin tocar `context.py`. El tope del modo (8 o 16) mantiene el costo del modelo de lenguaje (FR-005). Reutilizar la función en el segundo intento de la 008 evita duplicar lógica.

**Alternatives considered**: que el reranker solo reordene y el corte siga siendo por coseno (no resuelve ni a Cubillo, 0,819, ni la separación de nombres inventados); sumar los dos puntajes (calibración doble sin base); modificar `context.py` para recibir un puntaje aparte (más cambios, sin beneficio).

## R4. Escala del puntaje: probabilidad (sigmoide del logit)

**Decision**: el proveedor devuelve el logit crudo; la ruta lo convierte con la función sigmoide (`1 / (1 + e^-x)`) y el mínimo `RERANK_MIN_SCORE` está en esa escala de 0 a 1 (por defecto provisional 0,5, equivalente a logit 0, que se calibra en R10).

**Rationale**: `build_passages` inicializa mejores puntajes en 0,0 (`best.get(..., 0.0)`), y con logits negativos el orden del documento principal se rompería. La escala 0 a 1 se parece a la del umbral actual y es más fácil de documentar. Los logits de 10,9 y -9,9 de R2 dan 0,99998 y 0,00005: sin pérdida práctica de orden (float de 64 bits). Para ver diferencias en los extremos, la herramienta guarda también el logit.

**Alternatives considered**: usar el logit y un mínimo en esa escala (cambia `context.py`); normalizar por lote (hace los puntajes dependientes de los demás candidatos, justo lo que un mínimo no debe ser).

## R5. La pregunta que se puntúa

**Decision**: el reranker puntúa siempre contra `payload.question`, la pregunta original, incluso en el segundo intento de la feature 008 (la pregunta limpia solo cambia qué se busca en Qdrant). Los puntajes de fragmentos ya puntuados en la misma consulta se reutilizan (por `chunk_id`) en el segundo intento.

**Rationale**: el modelo de lenguaje recibe la pregunta original; lo que importa es si el fragmento responde a lo que la persona escribió. Reutilizar puntajes evita pagar dos veces los candidatos que se repiten entre la búsqueda con la pregunta y con el nombre solo.

## R6. Carga, fallos y presupuesto de tiempo

**Decision**:

1. Con `RERANK_PROVIDER=local`, el modelo se carga **al arrancar** (en `lifespan` de `main.py`, junto al modelo de embeddings), se registra la memoria (RSS) antes y después, y una falla de carga se registra una vez y deja el reranker como "no disponible" hasta reiniciar. Con `none` nada se importa ni se carga.
2. En cada consulta, un error del reranker (excepción de `onnxruntime`, archivo ausente) o `RerankTimeout` (el tiempo acumulado supera `RERANK_BUDGET_MS`, comprobado entre lotes de 4 pasajes) hace que esa consulta siga con los primeros `config.search_limit` por coseno y el umbral `QUERY_SIMILARITY_THRESHOLD`, con la nota `Reranker no disponible: se usó la similitud` y un aviso en el registro (limitado a uno por minuto).
3. Un valor inválido de `RERANK_PROVIDER` se trata como `none` con un aviso, una vez.

**Rationale**: cargar al arrancar evita que la primera consulta pague unos segundos de carga y hace visible el consumo de memoria desde el inicio, que es lo que esta prueba mide. El presupuesto de tiempo entre lotes es la única forma de acotar la latencia sin hilos ni procesos extra: una llamada a `onnxruntime` en curso no se puede interrumpir, por eso se comprueba entre lotes pequeños. Una caída nunca debe producir un error porque la feature es una prueba y no puede dejar a MIA sin responder (User Story 3).

**Alternatives considered**: carga diferida en la primera consulta (latencia impredecible y la memoria aparece de golpe en medio del servicio); reintentar la carga en cada consulta tras un fallo (cada intento costaría segundos); un hilo con tiempo límite (complejidad y memoria extra).

## R7. Notas de Uso

**Decision**: nota en `reject_reason`, unida con "; " en este orden: reranker, pregunta limpia (008), corte (007), citas (006).

| Situación | Nota |
|---|---|
| Intervino y algún candidato superó el mínimo | `Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50` |
| Intervino y ninguno superó el mínimo (consulta `no_info`) | `Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30` |
| Cayó a coseno | `Reranker no disponible: se usó la similitud` |

Los puntajes llevan punto decimal y tres decimales para que la herramienta los lea con una expresión regular, como la nota de la 008. El primer número es el mejor de **la última búsqueda** de la consulta (con segundo intento, la del segundo), el segundo es cuántos candidatos pasaron. La respuesta "sin información" también escribe la nota (la 008 ya dejó `no_info` con nota).

**Rationale**: sin migraciones, volver a `prototipo-v2-estable` sigue siendo posible (la columna ya existe y es texto, hasta 500 caracteres; las notas suman menos de 250). El mejor puntaje de las consultas sin respuesta es el dato para calibrar y para detectar "sin información" dudosas (V3, 2.7).

**Alternatives considered**: una columna nueva (migración, rompe el rollback); anotar los puntajes de los 30 candidatos (largo y sin uso).

## R8. Convivencia con las features 006, 007 y 008

- **006 citas**: numera los pasajes que salen de `build_passages`, que ya vienen en el orden del reranker. Sin cambios.
- **007 respuestas completas**: el documento principal se elige por el mejor `score`, ahora el del reranker; sus vecinos y la prolongación hacia adelante no dependen del puntaje. Sin cambios.
- **008 pregunta limpia**: se usa si la búsqueda con reranker no deja ningún candidato sobre el mínimo. El segundo intento recupera `RERANK_CANDIDATES` con el embedding de la pregunta limpia y los puntúa contra la pregunta original (R5). Si el reranker cayó en el primer intento, el segundo se hace sin reranker (con coseno y umbral) para no repetir el fallo.
- **Permisos y topes de gasto**: se evalúan antes de buscar; una consulta rechazada no puntúa nada.

## R9. Palancas para cumplir memoria y latencia

Todas son variables, todas se miden con el subcomando `rendimiento` y `puntajes` (gratis) antes de gastar:

| Variable | Por defecto | Efecto |
|---|---|---|
| `RERANK_CANDIDATES` | 30 | Candidatos recuperados y puntuados (5 a 60). Menos candidatos, menos latencia y menos probabilidad de capturar el documento. |
| `RERANK_MIN_SIMILARITY` | 0 (apagado) | Piso de coseno previo: los candidatos bajo ese coseno no se puntúan. Reduce candidatos sin tocar el documento si su coseno es razonable (en la línea base, los documentos esperados están sobre 0,78). Es opcional; se mide su efecto en la herramienta antes de decidir. |
| `RERANK_PASSAGE_TOKENS` | 192 | Tokens del pasaje que lee el reranker (32 a 480). El modelo de lenguaje sigue recibiendo el fragmento completo. |
| `RERANK_THREADS` | 2 | Hilos de `onnxruntime` para el reranker (1 a 8). Más hilos, menos latencia y más CPU. |
| `RERANK_BUDGET_MS` | 2500 | Presupuesto de tiempo de una consulta; superado, cae a coseno (0 lo desactiva). |
| `RERANK_MIN_SCORE` | 0,5 (provisional) | Mínimo del reranker; se fija con la calibración de R10. |

Lotes de 4 pasajes y el modelo cargado una sola vez acotan el pico de memoria. Si el reranker no cabe en 512 MB aun así, el resultado es "no cumple" y se reporta; la decisión de subir de plan es aparte.

## R10. Medición y calibración

Cuatro pasos, de menor a mayor costo:

1. **`puntajes` con reranker** (solo lectura sobre Qdrant, local, gratis): para cada caso y variante, recupera `RERANK_CANDIDATES`, los puntúa y guarda puesto por coseno y por reranker del documento esperado, el mejor puntaje y qué decidiría la API en cada modo. Un barrido de mínimos (0,01 a 0,99) cuenta cuántos casos "con respuesta" pasan y cuántos "sin información" se bloquean con cada valor; la ventana de separación dice si existe un mínimo que sirva para todos. Los casos sin respuesta incluyen EN7, EN8, A1 y los 4 de la batería; si hacen falta más (siglas, preguntas dudosas), se agregan al archivo de casos.
2. **`rendimiento`** (local, gratis): memoria (RSS en reposo, con el reranker cargado y bajo carga) y latencia p50 y p95 variando candidatos, tokens por pasaje e hilos, con pasajes reales de Qdrant. Elige el punto que cumple los límites, si existe.
3. **Railway, corrida de control y con reranker** (`respuestas`): un servicio con `dev` desplegado (procedimiento ya establecido, `--skip-deploys` y `--ref origin/dev`), `RERANK_PROVIDER` apagado y luego `local`, sobre los casos que cambian y los que no deben cambiar, con tope de gasto autorizado; memoria leída del registro de arranque y de la consola de Railway.
4. **Informe** en `docs/LINEA_BASE_BUSQUEDA.md`: calidad por caso, memoria, latencia, costo mensual estimado y la recomendación (conservar, dejar apagado, pasar a la búsqueda híbrida).

**Rationale**: los pasos 1 y 2 no cuestan nada y deciden casi todo; el paso 3 solo confirma en el servidor real. Es el mismo procedimiento que dio buen resultado en la 008 (medir gratis antes de gastar).

## R11. Descarga del modelo en el build

**Decision**: el `Dockerfile` descarga también los archivos del reranker en el build (`download_rerank_files`), igual que los del modelo de embeddings, y en ejecución se usa `HF_HUB_OFFLINE=1`. Se descargan siempre, aunque `RERANK_PROVIDER=none`.

**Rationale**: una descarga en el arranque en frío tarda y puede fallar; el costo de tener 119 MB más en la imagen es de disco, no de RAM (con `none` no se carga). Si el tamaño de la imagen molesta, se puede condicionar con un argumento de construcción en otra feature.

**Alternatives considered**: descargar en el arranque (frágil); condicionar la descarga con `ARG` (Railway pasa las variables como argumentos solo si se declaran, y complica el procedimiento de medición).

## R12. Límites que no se resuelven aquí

- **Documento más allá del último candidato**: Deep Learning (el programa queda en el puesto 50) y las siglas (TFG, MGTI) no entran entre los 30 candidatos; es recuperación y vocabulario, no reranking (búsqueda híbrida, opción D).
- **Pasajes largos**: el reranker lee los primeros `RERANK_PASSAGE_TOKENS` tokens del fragmento; un dato que esté al final del fragmento no cuenta para el puntaje.
- **Idioma**: el modelo está entrenado con mMARCO; sobre español rinde bien, pero los nombres propios y las actas tienen un estilo (listas, tablas) distinto al de los pasajes de MS MARCO; por eso se calibra con los casos propios y no con el valor por defecto del modelo.
- **Nombres inventados**: el modelo separa bien una persona inventada en la muestra mínima, pero un término inventado que se parece a uno real (o una sigla) puede puntuar alto; la calibración con EN7, EN8 y A1 lo mostrará.
