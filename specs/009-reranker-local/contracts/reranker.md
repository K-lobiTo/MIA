# Contrato: Reranker local

Contrato interno (no cambia la API HTTP): la interfaz de la pieza, el comportamiento de `POST /query` con el reranker y las salidas observables.

## 1. Interfaz `RerankProvider` (`mia.rag.rerank`)

```text
class RerankProvider(ABC):
    @abstractmethod
    def score(self, query: str, passages: list[str], deadline: float | None = None) -> list[float]: ...
```

- Devuelve un logit por pasaje, en el mismo orden y con la misma longitud. Una lista vacía devuelve una lista vacía sin invocar el modelo.
- `deadline` es un instante de `time.perf_counter()` (o `None`): se comprueba entre lotes y, si ya pasó, lanza `RerankTimeout`.
- Cualquier excepción del proveedor es un fallo recuperable para la ruta (cae a coseno).
- Fábrica: `get_rerank_provider(name) -> RerankProvider | None`; `"none"` (y cualquier valor desconocido, con un aviso una vez) devuelve `None`, `"local"` devuelve `LocalRerankProvider` (memoizado por nombre). Una falla de carga se recuerda y no se reintenta hasta reiniciar.

## 2. `LocalRerankProvider` (`mia.rag.providers.local_rerank`)

- Modelo `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, archivo `onnx/model_quint8_avx2.onnx`, tokenizador `sentencepiece.bpe.model`; `download_rerank_files()` los descarga (o toma de la caché) y la llama el `Dockerfile`.
- Sesión de `onnxruntime` con `intra_op_num_threads = RERANK_THREADS`, `enable_cpu_mem_arena = False`, proveedor `CPUExecutionProvider`.
- Par de entrada: `[0, *pregunta, 2, 2, *pasaje, 2]` con ids de sentencepiece desplazados en 1 (0 pasa a 3, UNK); el pasaje se trunca a `RERANK_PASSAGE_TOKENS` tokens y el total no supera 512. Relleno con 1 (PAD) y máscara de atención.
- Lotes de 4 pasajes; entre lotes se comprueba `deadline`.

## 3. Comportamiento de `POST /query`

Con `RERANK_PROVIDER=none` (o inválido): idéntico a hoy.

Con `local`:

1. Permisos, modo, dominios y topes de gasto: como hoy, antes de buscar.
2. Embedding local de la pregunta; búsqueda con `limit = RERANK_CANDIDATES`.
3. Se descartan los candidatos con coseno menor que `RERANK_MIN_SIMILARITY` (si es mayor que 0).
4. El reranker puntúa los candidatos contra `payload.question` (se reutilizan los puntajes ya calculados en la consulta).
5. `rerank_candidates`: puntaje = sigmoide del logit; orden descendente (empates por orden de coseno); se descartan los menores que `RERANK_MIN_SCORE`; se queda con los primeros `config.search_limit` del modo. A cada uno se le reemplaza `score` por su puntaje del reranker.
6. Si no queda ninguno y `QUERY_CLEAN_QUESTION` está encendida, el segundo intento de la 008 repite los pasos 2 a 5 con el embedding de la pregunta limpia (el reranker puntúa contra la pregunta original).
7. Sin fragmentos: `no_info` sin llamar al modelo de lenguaje, con la nota. Con fragmentos: el flujo sigue (`build_passages`, citas, respuesta, fuentes) con los fragmentos en el orden del reranker.
8. Falla del reranker o `RerankTimeout` en cualquier punto del 4: esa consulta continúa con los primeros `config.search_limit` por coseno y el umbral `QUERY_SIMILARITY_THRESHOLD` (comportamiento de hoy), con la nota `Reranker no disponible: se usó la similitud`; no se reintenta el reranker en el segundo intento de la misma consulta.

Garantías: ninguna llamada nueva a un modelo de lenguaje; a lo sumo `config.search_limit` fragmentos entran al armado del contexto; la estructura de la respuesta HTTP no cambia; ningún error del reranker llega al cliente.

## 4. Notas de Uso

Ver [data-model.md](../data-model.md). Orden: reranker, pregunta limpia, corte (007), citas (006), unidas con "; ".

## 5. Registro del servidor (nivel INFO)

- Al arrancar con `local`: `Reranker cargado: RSS <antes> -> <después> MB`.
- Por consulta con reranker: `Reranker: <n> candidatos en <ms> ms (modo <m>)`.
- Aviso de fallo: como máximo uno por minuto.

## 6. Herramienta (`scripts/linea_base.py`)

- `puntajes --rerank`: variantes con reranker (mismo código que la API, `rerank_candidates`), `barrido_minimos`, `ventana_rerank`.
- `rendimiento`: memoria y latencia por combinación; sin llamar al modelo de lenguaje.
- `respuestas`: lee las notas del reranker; `comparar` y `informe` resumen consultas con reranker, caídas a coseno y el cambio contra el control.
