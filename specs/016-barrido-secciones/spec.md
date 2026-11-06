# Feature 016: barrido de secciones (resumen de los contenidos de todos los cursos)

**Rama:** dev. **Origen:** feedback de Martín Solís (documento `Consultas al chat`, 2026-11-05).

## Problema

"Resuma el contenido de la materia de los 14 cursos" recibía pocos documentos: la búsqueda trae los fragmentos más
parecidos a la pregunta (8 en literal, 16 con razonamiento, unos 3 y 9 documentos). El modelo concluía, sin que fuera
cierto, que solo había programas detallados de 6 cursos. Los 17 programas están cargados y cada uno se recupera bien
cuando se pregunta por él. Subir el límite de fragmentos no garantiza todos los cursos, porque depende de cuáles salgan
más parecidos y los documentos largos ocupan el lugar de otros.

## Qué se pide

Que esa pregunta entregue un resumen real de la sección «Contenidos» de TODOS los programas de curso (no de los
programas enteros).

## Requerimientos

- RF1. Con `QUERY_SECTION_SWEEP=on`, una pregunta que pide resumir o listar los contenidos de los cursos en plural recibe,
  de cada documento de los dominios consultados que tenga la fila `Contenidos`, solo esa sección.
- RF2. La detección es por reglas de texto. No se activa si la pregunta nombra un solo curso ni si pide además créditos,
  requisitos, profesor, horas, costos, evaluación u otro dato.
- RF3. Con menos de dos documentos con la sección, o ante cualquier fallo, la consulta es la de siempre.
- RF4. Los permisos, topes, registro de Uso y fuentes funcionan igual. El registro lleva la nota `Barrido de secciones: N documentos`.
- RF5. Apagado por defecto. Sin migraciones ni reindexación.

## Decisiones

- Se descartaron el resumen precalculado al ingestar (reingestar, una llamada por documento, se desactualiza) y solo subir
  los límites (no garantiza completitud).
- La fila se reconoce por su forma en el texto ingestado (`N. Contenidos | ...` o `Contenidos | ...` al comienzo de línea;
  la fila del cronograma `Semana | Contenidos` no cuenta). Los programas con otra estructura quedan fuera del barrido.
- Los programas de curso del TEC usan la misma plantilla; si cambia, se ajusta `_HEADING` y `_NEXT_ROW` en `rag/sections.py`.

## Medición (2026-11-05, documentos locales de Analítica, 28 documentos)

- 17 programas con su sección: 71 a 2070 caracteres cada una, 21 mil caracteres en total.
- Con `glm-5.3-flash` (literal): 5359 tokens de entrada, 2178 de salida, 0,00075 USD, `finish_reason` `stop`, los 17 cursos resumidos.
- Pendiente: encender en producción (`QUERY_SECTION_SWEEP=on` en Railway, reinicia la API) y repetir las preguntas 2 a 4 de Martín.
- Límite conocido: el modelo no ve más de 17 cursos si el dominio tiene más de `QUERY_SECTION_SWEEP_MAX_DOCUMENTS` documentos con la sección.
