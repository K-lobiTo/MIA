# MIA Constitution

## Core Principles

### I. Almacenamiento y Consulta Desacoplados (Multi-Artefacto)

El almacenamiento de dominios de conocimiento (base vectorial + metadata) y los artefactos que lo
consultan (chatbot de WhatsApp, chatbot web, consulta interna de Coordinación, o cualquier
integración futura) DEBEN permanecer desacoplados a través de una única API intermediaria. Ningún
artefacto nuevo puede requerir duplicar o modificar la infraestructura de almacenamiento existente;
la API es el único punto de contacto entre ambos mundos.

Rationale: es el requisito fundacional del proyecto desde su definición conceptual original,
permitir múltiples artefactos sobre la misma memoria institucional sin construir un sistema
separado por cada uno.

### II. Pipeline Modular e Intercambiable

Cada etapa del pipeline (carga de documentos por tipo de fuente, chunking, generación de
embeddings, almacenamiento vectorial, generación de respuesta por LLM) DEBE implementarse como una
interfaz con implementaciones intercambiables seleccionables por configuración, nunca
hardcodeadas. Agregar un tipo de fuente nuevo (CSV, web scraping) o cambiar el motor de RAG NO DEBE
requerir modificar el resto del sistema.

Rationale: requisito técnico explícito desde la definición conceptual original ("cambiar partes del
pipeline sin que interfiera con el resto del producto"), ya materializado en el patrón interfaz más
factory de `DocumentLoader`, `EmbeddingProvider`, `LLMProvider` y `VectorStore`.

### III. Independencia de Proveedor de LLM

El sistema DEBE poder operar tanto con un LLM local o auto-hospedado como con uno comercial por API
key, seleccionable por configuración y sin cambios de código. Ninguna decisión de arquitectura puede
asumir de forma permanente que el LLM correrá en un proveedor específico.

Los embeddings quedan exceptuados de esta exigencia de simetría: a diferencia del LLM, no tienen
costo variable por uso, no envían contenido institucional a un tercero, y su latencia es
insignificante frente a la del LLM incluso cuando corren en cada consulta (para embeber la
pregunta, no solo al ingerir documentos). Un proveedor de embeddings local puede ser, por lo tanto,
una decisión de arquitectura permanente y no solo una limitación temporal. La interfaz intercambiable
de embeddings (Principio II) se mantiene por si el criterio cambia, pero no se exige que exista una
implementación comercial de embeddings funcionando en paralelo a la local.

Rationale: mientras no se disponga de hardware propio para correr modelos localmente, el proyecto
depende de un proveedor comercial de LLM por suscripción. La meta declarada es migrar el LLM a un
modelo local cuando sea viable, para reducir costo y dependencia externa; bloquear la arquitectura a
un solo proveedor de LLM comprometería esa meta. Los embeddings no comparten ese riesgo de costo o
dependencia, exigirles la misma simetría sería una restricción sin beneficio real.

### IV. Extensibilidad de Dominios Sin Fricción Operativa

DEBE ser posible crear un dominio nuevo o agregar documentos a un dominio existente en cualquier
momento, sin interrumpir la operación del resto del sistema ni requerir migración de los dominios
existentes. El mecanismo concreto para crear o gestionar dominios (API, script, interfaz de
administración) es una decisión de implementación, no una restricción de esta ley.

Rationale: requisito explícito desde la primera definición conceptual del prototipo, poder crear
dominios nuevos e ingresar documentos a los existentes sin que eso interfiera en el funcionamiento
general del producto.

### V. Trazabilidad de Respuestas

Toda respuesta generada por el motor RAG DEBE poder citar el o los documentos y dominios de origen
de la información utilizada. Una respuesta sin fuente verificable se considera un defecto, no una
limitación aceptable.

Rationale: MIA reemplaza el conocimiento tácito de una persona por una memoria consultable. Sin
trazabilidad, Coordinación y el Consejo no tienen forma de confiar en ni verificar lo que el
sistema responde.

## Restricciones Técnicas y de Datos Sensibles

- Stack base: Python más FastAPI para la API, Qdrant para vectores, SQLite para metadata
  (migrable a Postgres sin cambiar la capa de acceso a datos). Cambiar cualquiera de estos
  componentes requiere actualizar `docs/ARQUITECTURA.md`.
- Los dominios que contengan datos sensibles de personas (por ejemplo, evaluaciones de desempeño
  docente) NO DEBEN exponerse a través de un artefacto de acceso público (chatbot web o WhatsApp)
  sin un mecanismo de control de acceso implementado antes.
- La documentación técnica, los nombres de dominios y conceptos, y los mensajes de commit se
  escriben en español. Nunca se usa guión largo (em dash) en ningún texto generado para el
  proyecto (ver `CLAUDE.md`).

## Alcance Incremental y Documentación Viva

- El sistema se construye en orden de validación: no se agrega un artefacto de consulta, un
  mecanismo de autenticación, o un dominio nuevo antes de que exista evidencia de que el pipeline
  base (ingesta más RAG) funciona sobre el primer dominio y caso de uso reales.
- Toda decisión de alcance, arquitectura o despliegue se documenta en
  `docs/Definicion_Requerimientos_MVP.md` (el qué y el por qué) o `docs/ARQUITECTURA.md` (el cómo
  está implementado). Ninguna decisión relevante queda solo en el historial de conversación.

## Governance

Esta constitución tiene precedencia sobre cualquier práctica ad hoc. Cualquier plan
(`/speckit-plan`) o especificación (`/speckit-specify`) que entre en conflicto con un principio
debe justificar explícitamente la excepción o modificar primero esta constitución. Las enmiendas se
hacen exclusivamente mediante `/speckit-constitution`, versionando según semver: MAJOR para
eliminación o redefinición incompatible de un principio, MINOR para un principio o sección nueva,
PATCH para aclaraciones de redacción. Usar `CLAUDE.md` para guía operativa de desarrollo del día a
día que no altere estos principios.

**Version**: 1.1.0 | **Ratified**: 2026-09-26 | **Last Amended**: 2026-09-26
