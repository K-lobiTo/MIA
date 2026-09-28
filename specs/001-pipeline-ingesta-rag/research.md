# Research: Pipeline de Ingesta y Consulta RAG

## Modelo de embeddings local

**Decision**: `intfloat/multilingual-e5-small` vía `sentence-transformers`.

**Actualización (2026-09-27)**: se mantiene el modelo, pero se ejecuta exportado a ONNX y cuantizado a
int8 con `onnxruntime` + `sentencepiece`, porque con `sentence-transformers` (PyTorch) la API ocupaba
~1.2 GB y no cabía en Render free (512 MB). Detalle y mediciones en `docs/ESCALABILIDAD.md`.

**Rationale**: soporta español de forma nativa (multilingüe), es pequeño (~118M parámetros, corre
aceptablemente en CPU sin GPU, requisito de la restricción técnica de esta feature) y tiene buen
desempeño de recuperación semántica en benchmarks públicos (MTEB) para su tamaño. Es la opción que
mejor equilibra calidad de búsqueda y viabilidad sin hardware dedicado.

**Alternatives considered**:
- `paraphrase-multilingual-MiniLM-L12-v2`: más liviano, pero desempeño de recuperación inferior en
  benchmarks recientes frente a la familia E5.
- Embeddings comerciales (OpenAI `text-embedding-3-small`, etc.): rechazado para el arranque porque el
  proveedor local ya cubre la necesidad sin costo ni dependencia externa. Nota (2026-09-26): esto ya
  no se justifica por una exigencia de simetría del Principio III, tras la enmienda a v1.1.0 los
  embeddings quedan exceptuados de esa simetría y el local puede ser una decisión permanente, no solo
  la opción de arranque.

## Proveedor de LLM comercial

**Decision**: Anthropic (SDK oficial `anthropic`), modelo fijo `claude-sonnet-5`. Nivel de esfuerzo
(`output_config.effort`) configurable por variable de entorno `ANTHROPIC_EFFORT`, con `medium` como
valor por defecto y `high` como opción disponible sin cambiar código.

**Rationale**: el benchmark de LLMs ya realizado por el proyecto (`LLMs-profiling`, objetivo específico
3) solo comparó modelos locales entre sí (deepseek-r1, llama3.1, qwen2.5), no proveedores comerciales;
no hay evidencia previa que decida entre proveedores comerciales. Se elige Anthropic por tener el SDK y
los patrones de integración mejor documentados y verificados en este mismo flujo de trabajo. Por
instrucción explícita del usuario, `claude-opus-5` queda descartado por completo (ni como default ni
como opción ofrecida); `claude-sonnet-5` en esfuerzo `medium` da un costo acotado y predecible para el
volumen del MVP, con `high` disponible por configuración para preguntas que requieran más profundidad
sin necesitar cambiar de modelo.

**Alternatives considered**:
- `claude-opus-5`: descartado explícitamente por decisión del usuario, no se ofrece ni como default ni
  como opción configurable.
- OpenAI: descartado sin razón técnica en contra, solo se prioriza Anthropic por mejor soporte de
  implementación verificada en esta sesión; la interfaz `LLMProvider` ya deja espacio para agregarlo
  después sin cambiar el resto del sistema (`openai_llm.py` queda como stub).
- LLM local (Ollama u otro): explícitamente diferido por el spec y la conversación previa, no hay
  hardware disponible todavía.

**Actualización (2026-09-26)**: el usuario no logró reclamar el crédito de prueba de Anthropic. Se
agregó `GeminiLLMProvider` (`gemini-3.5-flash-lite`, tier gratuito de Google AI Studio sin tarjeta)
como segunda opción comercial, sin quitar `AnthropicLLMProvider`. Se eligió Flash-Lite sobre Flash
porque en el benchmark FACTS Grounding (fidelidad al contexto dado, justo lo que exige el Principio V
de la constitución) Flash-Lite puntúa mejor que Flash, además de un límite gratuito más generoso
(~1,500 solicitudes/día). `LLM_PROVIDER=gemini` queda como valor activo en `.env.example` mientras se
resuelve el acceso a Anthropic; ambos proveedores son intercambiables sin cambiar código (Principio
III).

## Disparo de la indexación (síncrono vs. background)

**Decision**: `BackgroundTasks` de FastAPI, disparada desde `POST /domains/{id}/documents` después de
guardar el archivo y crear el registro con estado `pending`.

**Rationale**: indexar puede tardar hasta 2 minutos (SC-001 del spec); bloquear la respuesta HTTP ese
tiempo sería mala experiencia y podría exceder timeouts de proxy en Render. El volumen esperado del MVP
(decenas de documentos, uso esporádico) no justifica una cola de mensajes dedicada.

**Alternatives considered**:
- Procesamiento síncrono en el request: rechazado, viola UX y límites de timeout.
- Cola dedicada (Celery, RQ, etc.): rechazado por ahora, es complejidad que el volumen del MVP no
  justifica (alineado con el principio de alcance incremental de la constitución); queda como
  extensión futura documentada si el volumen crece.

## Chunking

**Decision**: reutilizar `chunk_text()` ya existente (1000 caracteres, 200 de overlap), sin cambios.

**Rationale**: ya implementado y es un tamaño razonable para actas de Consejo (texto corrido en
español); no hay evidencia todavía de que necesite ajuste, se puede afinar después con casos reales.

## Manejo de "no hay información suficiente"

**Decision**: si la búsqueda en Qdrant no devuelve resultados con un puntaje de similitud por encima de
un umbral configurable, se responde directamente sin llamar al LLM, con un mensaje fijo indicando falta
de información. Si hay resultados por encima del umbral, se pasan como contexto al LLM con una
instrucción de sistema explícita de no inventar información fuera de ese contexto.

**Rationale**: cumple FR-007 y SC-003 del spec de forma verificable (una decisión de umbral, no
depende únicamente del criterio del LLM para "admitir" que no sabe, que es menos confiable).

**Calibración empírica (durante implementación)**: con `intfloat/multilingual-e5-small`, una pregunta
sin relación alguna con el documento indexado obtuvo 0.72 de similitud coseno contra un fragmento
relevante real que obtuvo 0.91; es decir, este modelo comprime las similitudes hacia arriba (0.5 como
umbral resultaba demasiado permisivo). El valor por defecto quedó en `0.8`. Es un valor de partida, no
definitivo: debe recalibrarse con preguntas y documentos reales una vez haya más contenido indexado.

**Recalibración con actas reales (2026-09-28)**: con las actas 3436, 3437 y 3438 del Consejo
Institucional del TEC indexadas (1189 fragmentos, modelo e5-small en ONNX int8), se midió la
similitud del mejor fragmento (top-1) para dos grupos de preguntas:

| Grupo | Preguntas | Top-1 |
|---|---|---|
| Con respuesta en las actas (programa de inglés, conformación del Consejo, Premio Nacional de Tecnología, dietas estudiantiles, Plan Táctico, nombre del CONARE, Comisión de Evaluación Profesional, creación de plazas, evaluación del PAO) | 9 | 0.872 a 0.924 |
| Sin respuesta pero del mismo ámbito (casos de uso 1 a 6 del documento conceptual) | 5 | 0.838 a 0.868 |
| Totalmente ajenas (receta, fútbol) | 2 | 0.78 a 0.79 |

Con el umbral anterior (0.8) toda pregunta del ámbito institucional pasaba el filtro: el LLM
respondía "no hay información" pero la API igual listaba 5 fuentes, lo que confunde la
trazabilidad. Un primer intento fue subir el umbral a 0.87, que separaba ambos grupos en esa
muestra, pero al probar formulaciones más naturales los grupos se solapan por completo:

| Pregunta | Tiene respuesta | Top-1 |
|---|---|---|
| ¿Cuándo abre la matrícula de la maestría en Computación? | No | 0.873 |
| programa de inglés | Sí | 0.870 |
| ¿Qué informó la Rectoría? | Sí | 0.868 |
| ¿Qué se acordó sobre el programa de inglés? | Sí | 0.853 |
| ¿Quién es el coordinador de la Unidad? | No | 0.849 |
| ¿Se aprobó el acta 3435? | Sí | 0.847 |

Conclusión: con este modelo, la similitud sirve para descartar preguntas totalmente ajenas, pero
no para decidir si las actas responden una pregunta del mismo ámbito.

**Decisión actual (2026-09-28), dos capas:**

1. Umbral bajo, **0.82** (`render.yaml`, `.env.example`): solo descarta lo claramente ajeno, sin
   llamar al LLM.
2. El LLM decide si hay respuesta: la instrucción de sistema (`RAG_SYSTEM_PROMPT` en
   `src/mia/rag/llm.py`) le pide responder exactamente `SIN_INFORMACION` si ningún fragmento trata el
   tema. La API convierte esa marca en la respuesta fija "sin información suficiente" y **sin
   fuentes**. Una primera redacción ("si los fragmentos no contienen información suficiente")
   hacía que Gemini se negara incluso con fragmentos relevantes; la redacción actual le pide
   responder con la información parcial disponible y usar la marca solo si ningún fragmento trata el
   tema.

Pendiente: recalibrar con actas del Consejo de Unidad (el dominio real del MVP) y cada vez que
cambie el modelo de embeddings o el LLM. Para medir: embeber todos los fragmentos, embeber las
preguntas con `is_query=True` y comparar el producto punto máximo de cada una; y revisar a mano las
respuestas de `/query` para un conjunto de preguntas con y sin respuesta.

**Alternatives considered**: confiar solo en que el LLM diga "no lo sé" vía prompting, sin umbral:
rechazado como único mecanismo, es más caro (siempre llama al LLM aunque la pregunta sea ajena). Subir
el umbral hasta separar los grupos: rechazado por el solapamiento descrito arriba.
