# Quickstart: Reranker local

Cómo comprobar la feature, de menor a mayor costo. Variables y notas: [data-model.md](data-model.md). Contrato: [contracts/reranker.md](contracts/reranker.md).

## 1. Pruebas automáticas (gratis)

```bash
pytest tests/unit/test_rerank.py tests/unit/test_query_rerank.py tests/unit/test_local_rerank.py tests/unit/test_linea_base.py
pytest && ruff check src tests scripts
```

Esperado: todo en verde. Con `RERANK_PROVIDER=none` ninguna prueba de las features anteriores cambia.

## 2. Puntajes con reranker (gratis, solo lectura sobre producción)

```bash
python scripts/linea_base.py puntajes --etiqueta rerank-previa --env-file .env.produccion --rerank
```

Esperado: por caso y variante, el puesto del documento esperado por coseno y por reranker, qué decidiría la API en literal y en razonamiento, el barrido de mínimos y la ventana de separación. Casos esperados de la 008: Natalia Soto Solís (S22-1) debería llegar al contexto en literal; EN7 y EN8 (inventados) deberían quedar bajo el mínimo. Si la ventana dice "NO separables", la prueba termina en negativo y se reporta.

## 3. Memoria y latencia en local (gratis)

```bash
python scripts/linea_base.py rendimiento --etiqueta rendimiento-local --env-file .env.produccion
```

Esperado: RSS en reposo, con el reranker cargado y bajo carga; p50 y p95 por combinación de candidatos (10, 20, 30, 40), tokens por pasaje (128, 192, 256) e hilos (1, 2, 4). El informe marca qué combinaciones cumplen 0,5 s en p50 y 1,5 s en p95.

## 4. Medición en Railway (con autorización y tope de gasto)

Procedimiento ya establecido en las features 007 y 008 (resumido en la memoria del proyecto):

1. `railway variable set RERANK_PROVIDER=local RERANK_CANDIDATES=... -s MIA --skip-deploys` (sin `--skip-deploys` redespliega desde `main` y pierde `dev`).
2. `python scripts/servicios.py encender MIA --forzar --ref origin/dev`.
3. Leer en el registro de arranque `Reranker cargado: RSS ...` y comparar con la consola de Railway (memoria en reposo y bajo carga).
4. Corrida de control (`RERANK_PROVIDER=none`) y corrida con reranker con `respuestas --tope-usd ... --solo ...`; `comparar` contra el control.
5. Cierre: `RERANK_PROVIDER=none`, desactivar el artefacto de prueba, regenerar su clave, `python scripts/servicios.py apagar MIA --forzar`.

## 5. Informe

Resultados y recomendación (conservar, dejar apagado, pasar a la búsqueda híbrida) en `docs/LINEA_BASE_BUSQUEDA.md`, sección "Resultado de la feature 009", y en la spec (tabla "Resultados medidos").
