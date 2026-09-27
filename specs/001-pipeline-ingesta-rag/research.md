# Research: Pipeline de Ingesta y Consulta RAG

## Modelo de embeddings local

**Decision**: `intfloat/multilingual-e5-small` vía `sentence-transformers`.

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

**Alternatives considered**: confiar solo en que el LLM diga "no lo sé" vía prompting: rechazado como
único mecanismo, es menos verificable y más caro (siempre llama al LLM aunque no haya contexto real).
