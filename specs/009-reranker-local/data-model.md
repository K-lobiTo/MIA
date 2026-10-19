# Modelo de datos: Reranker local

Sin tablas ni columnas nuevas: no hay migraciones y los documentos no se reindexan.

## Configuración (`src/mia/config.py`, `.env.example`)

| Variable | Tipo | Por defecto | Validación |
|---|---|---|---|
| `RERANK_PROVIDER` | texto | `none` | `none` o `local`; cualquier otro valor se trata como `none` con un aviso (una vez) |
| `RERANK_CANDIDATES` | entero | `30` | de 5 a 60 |
| `RERANK_MIN_SCORE` | decimal | `0.5` (provisional, se calibra) | de 0 a 1, escala de probabilidad del reranker |
| `RERANK_MIN_SIMILARITY` | decimal | `0` (apagado) | de 0 a 1; coseno mínimo para que un candidato se puntúe |
| `RERANK_PASSAGE_TOKENS` | entero | `192` | de 32 a 480 |
| `RERANK_THREADS` | entero | `2` | de 1 a 8 |
| `RERANK_BUDGET_MS` | entero | `2500` | de 0 a 30000; 0 desactiva el presupuesto |

Los valores numéricos fuera de rango hacen fallar la validación de `Settings` igual que las demás variables numéricas del proyecto (`Field(ge=, le=)`); solo `RERANK_PROVIDER` es texto libre para que un nombre inválido no impida el arranque.

## Registro de consultas (`QueryLog`, tabla existente)

`reject_reason` (texto, hasta 500 caracteres, ya existente) lleva la nota del reranker cuando intervino o cayó, unida con "; " **antes** de las notas de las features 008, 007 y 006.

| Nota | Cuándo |
|---|---|
| `Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50` | Intervino y algún candidato superó el mínimo. |
| `Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30` | Intervino y ninguno lo superó. La consulta termina en `no_info`. |
| `Reranker no disponible: se usó la similitud` | Falló la carga, falló al puntuar o superó el presupuesto de tiempo. |

Los puntajes llevan punto decimal y tres decimales. Las consultas con `RERANK_PROVIDER=none`, o sin ningún candidato, no cambian.

## Entidades del módulo `rerank` (sin persistencia)

| Entidad | Campos | Notas |
|---|---|---|
| `RerankProvider` | `score(query, passages, deadline) -> list[float]` | Interfaz. Devuelve un logit por pasaje, en el mismo orden. Puede lanzar una excepción o `RerankTimeout`. |
| `RerankOutcome` | `results` (candidatos con `score` = puntaje del reranker), `best` (mejor puntaje), `scored` (cuántos se puntuaron), `passed` (cuántos superaron el mínimo), `fell_back` (bool) | Resultado de `rerank_candidates`; construye la nota. |
| Puntaje del reranker | `float` entre 0 y 1 | Sigmoide del logit; reemplaza `SearchResult.score` en la copia que sigue en el flujo. |
| Nota del reranker | `str` | Construida por `rerank_note(outcome, min_score)`. |

## Casos de la herramienta (`scripts/datos/casos_busqueda.json`)

Sin campos nuevos obligatorios. Si la calibración lo pide, se agregan casos de las categorías existentes (`sin_informacion`, `sigla`, `envoltura`) con `espera` y `documentos` como los demás. La herramienta usa `espera` para decidir cuáles son los casos "con respuesta" y cuáles "sin información" al calcular la ventana de separación del reranker.

## Salida de la herramienta (JSON de la corrida)

`puntajes.json` gana, por medición, el campo `rerank` (candidatos puntuados con puesto por coseno y por reranker, logit y puntaje, `por_modo` con qué decidiría la API, `esperados` con el puesto del documento esperado antes y después, y `ms` de la puntuación), y en el resumen `barrido_minimos` y `ventana_rerank`. `rendimiento.json` guarda la memoria y las latencias p50 y p95 por combinación de candidatos, tokens por pasaje e hilos. `respuestas.json` gana, por consulta, `rerank_mejor`, `rerank_cayo` y `rerank_ninguno_sobre_minimo`, y el resumen cuenta cuántas consultas cayeron a coseno.
