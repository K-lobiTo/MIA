# Feature Specification: Pipeline de Ingesta y Consulta RAG

**Feature Branch**: `001-pipeline-ingesta-rag`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Implementar el pipeline real de ingesta y RAG para el dominio Memoria del Consejo del MVP de MIA, reemplazando los stubs actuales por implementaciones funcionales, sin romper la modularidad ya existente (interfaz + factory por proveedor). Alcance: EmbeddingProvider local open-source auto-hospedado; LLMProvider comercial funcional de punta a punta (el local queda como interfaz definida, implementación diferible); búsqueda y guardado reales en la base vectorial con filtro por dominio; pipeline de ingesta conectado de punta a punta al subir un documento, con estado consultable; endpoint de consulta funcional que responde citando documento y dominio de origen. Fuera de alcance: artefactos de chat/UI, autenticación, otros dominios, ingesta de CSV o web scraping."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Un documento subido queda disponible para consulta sin pasos manuales (Priority: P1)

Alguien de Coordinación sube un acta del Consejo de Unidad al dominio "Memoria del Consejo". Sin que nadie tenga que hacer nada más, el contenido del acta queda disponible para responder preguntas relacionadas.

**Why this priority**: es el requisito base de todo el prototipo, si el contenido de un documento subido no llega a estar disponible para consulta, no hay memoria institucional que ofrecer. Sin esto, ninguna otra historia tiene sentido.

**Independent Test**: subir un acta real al dominio "Memoria del Consejo" vía el endpoint ya existente, y verificar que su estado pasa de "pendiente" a "listo" sin intervención manual adicional, y que su contenido aparece reflejado en respuestas a preguntas relacionadas.

**Acceptance Scenarios**:

1. **Given** un documento válido (PDF, DOCX o TXT) con texto extraíble, **When** se sube al dominio "Memoria del Consejo", **Then** su estado pasa de "pendiente" a "listo" en un tiempo razonable, sin pasos manuales adicionales.
2. **Given** un documento cuyo contenido no puede extraerse (por ejemplo, vacío o corrupto), **When** se sube al dominio, **Then** su estado pasa a "error" en vez de quedar indefinidamente "pendiente" o marcarse como "listo" sin contenido real.
3. **Given** un documento ya subido previamente y ya indexado, **When** se vuelve a subir el mismo archivo sin cambios, **Then** no se genera contenido indexado duplicado.

---

### User Story 2 - Una pregunta sobre contenido real recibe una respuesta con su fuente citada (Priority: P1)

Alguien de Coordinación pregunta en lenguaje natural sobre un tema ya cubierto por documentos indexados en uno o más dominios, y recibe una respuesta basada en esos documentos, indicando de cuál(es) documento(s) y dominio(s) proviene la información.

**Why this priority**: es la otra mitad indispensable del prototipo (consulta), y la trazabilidad de la fuente es lo que permite confiar en la respuesta en vez de tratarla como una caja negra.

**Independent Test**: con al menos un documento ya indexado, enviar una pregunta relacionada con su contenido y verificar que la respuesta cita el documento y dominio correctos.

**Acceptance Scenarios**:

1. **Given** un documento indexado con información sobre un tema específico, **When** se pregunta sobre ese tema especificando su dominio, **Then** la respuesta refleja el contenido real del documento y cita el documento y dominio de origen.
2. **Given** documentos indexados en más de un dominio, **When** se pregunta especificando varios dominios a la vez, **Then** la respuesta puede combinar información de documentos de distintos dominios, citando cada fuente por separado.

---

### User Story 3 - El sistema reconoce cuándo no tiene información suficiente (Priority: P2)

Alguien pregunta sobre un tema que no está cubierto por ningún documento indexado en los dominios consultados. El sistema indica que no tiene información suficiente, en vez de generar una respuesta sin respaldo real.

**Why this priority**: sin esto, el sistema puede generar respuestas que parecen confiables pero no lo son, lo cual es peor que no responder, mina la confianza en toda la herramienta.

**Independent Test**: hacer una pregunta sobre un tema que deliberadamente no está en ningún documento indexado, y verificar que la respuesta indica falta de información en vez de inventar contenido.

**Acceptance Scenarios**:

1. **Given** ningún documento indexado contiene información relacionada con la pregunta, **When** se envía esa pregunta, **Then** la respuesta indica explícitamente que no hay información suficiente, sin citar fuentes inexistentes.

---

### Edge Cases

- ¿Qué pasa si se consulta un dominio que no existe o que todavía no tiene ningún documento indexado?
- ¿Qué pasa si el proveedor externo que genera la respuesta (LLM) no está disponible momentáneamente (por ejemplo, límite de uso alcanzado)?
- ¿Qué pasa si un documento subido no tiene texto extraíble en absoluto (por ejemplo, un PDF escaneado sin capa de texto)?
- ¿Qué pasa si se envía una pregunta vacía o sin ningún dominio especificado?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE indexar automáticamente el contenido de un documento subido a un dominio, sin requerir ninguna acción manual adicional después de la subida.
- **FR-002**: El sistema DEBE exponer el progreso de la indexación de cada documento a través de un estado consultable (pendiente, procesando, listo, error).
- **FR-003**: El sistema DEBE marcar un documento como fallido si su contenido no puede procesarse, en vez de dejarlo indefinidamente pendiente o marcarlo como listo sin contenido real.
- **FR-004**: El sistema DEBE evitar indexar contenido duplicado cuando el mismo documento ya fue subido e indexado previamente sin cambios.
- **FR-005**: El sistema DEBE responder preguntas en lenguaje natural usando únicamente el contenido de los dominios que se especifiquen en la consulta.
- **FR-006**: Toda respuesta generada DEBE citar el documento y dominio de origen de la información utilizada.
- **FR-007**: El sistema DEBE indicar explícitamente cuando no encuentra información relevante para responder una consulta, en vez de generar una respuesta sin respaldo en los documentos indexados.
- **FR-008**: El proveedor que genera las respuestas (LLM) DEBE poder configurarse de forma independiente entre una opción local/auto-hospedada y una comercial, sin cambiar el comportamiento observable para quien consulta. El proveedor que genera la representación interna del contenido para búsqueda (embeddings) puede ser exclusivamente local, dado que no tiene costo variable por uso, no expone contenido institucional a un tercero, y su latencia es insignificante frente a la del LLM; no se requiere que exista una implementación comercial de embeddings funcionando en paralelo a la local (ver Constitución, Principio III, v1.1.0).

### Key Entities

- **Dominio**: área de conocimiento (por ejemplo, "Memoria del Consejo") que agrupa documentos relacionados.
- **Documento**: archivo subido a un dominio, con un estado de indexación asociado (pendiente, procesando, listo, error).
- **Fragmento indexado**: porción del contenido de un documento que queda disponible para búsqueda, siempre vinculado a su documento y dominio de origen.
- **Consulta**: pregunta en lenguaje natural asociada a uno o más dominios, que produce una respuesta con sus fuentes citadas.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un documento de tamaño típico (un acta de pocas páginas) queda en estado "listo" en menos de 2 minutos después de subirse, sin intervención manual.
- **SC-002**: Al preguntar sobre un tema efectivamente cubierto por un documento indexado, la respuesta cita correctamente su documento y dominio de origen en al menos 9 de cada 10 intentos.
- **SC-003**: Al preguntar sobre un tema no cubierto por ningún documento indexado, el sistema lo reconoce explícitamente en el 100% de los casos, en vez de responder con información inventada.
- **SC-004**: Subir el mismo documento más de una vez nunca produce contenido indexado duplicado.

## Assumptions

- El proveedor comercial específico de LLM (y el modelo local de embeddings específico) se decide durante la planificación técnica, no en esta especificación, para no atar el "qué" a un proveedor concreto.
- Los embeddings quedan local por diseño permanente (no una limitación temporal): no requieren una implementación comercial paralela, a diferencia del LLM (ver FR-008 y Constitución Principio III, v1.1.0).
- La implementación local del LLM (`LocalLLMProvider`) queda como interfaz definida pero sin cuerpo real por ahora: es un stub intencional, diferido hasta que el proyecto disponga de hardware propio para correr un modelo localmente, no una omisión. FR-008 exige que el LLM pueda configurarse entre local y comercial sin cambios de código (la interfaz y el factory ya lo permiten); no exige que ambas implementaciones estén completas simultáneamente durante el MVP.
- Los documentos de prueba durante esta feature (actas del Consejo de Unidad) tienen texto extraíble de forma directa. Soporte para documentos escaneados sin capa de texto (OCR) queda fuera de alcance.
- El volumen de documentos y consultas durante el MVP es bajo (decenas de documentos, uso esporádico), no se optimiza para alta concurrencia en esta feature.
- El contrato de API ya definido (subir documento a un dominio, consultar uno o más dominios) no cambia de forma; esta feature implementa el comportamiento real detrás de esos puntos de entrada ya existentes.
