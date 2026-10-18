# Feature Specification: Respuestas completas, sin cortes

**Feature Branch**: `dev` (feature `007-respuestas-completas`, sin rama propia por decisión del usuario)

**Created**: 2026-10-16

**Status**: Draft

**Input**: User description: "Respuestas completas, sin cortes (feature 007, nuevo requerimiento BUS-8 de docs/Definicion_Requerimientos_V3.md): ninguna respuesta de MIA debe quedar incompleta ni cortada. El usuario lo pidió el 2026-10-16 al ver que la pregunta \"contenidos del curso Diseño de Experimentos\" devolvió el temario solo hasta la sección B, ítem 10, y al ver una respuesta que terminó a media frase. Hay dos causas: (1) contexto incompleto, porque MIA solo entrega un documento completo si es corto y, si no, entrega el fragmento relevante con un vecino a cada lado, así que una lista o sección más larga queda cortada; (2) generación cortada, porque una respuesta puede terminar a media frase y MIA no lo detecta ni lo registra. Se quiere que una lista o sección completa de un documento se devuelva completa, y que si una respuesta se corta por cualquier motivo MIA lo detecte y no la entregue como si estuviera completa. Con costo y latencia acotados, apagable por configuración, sin migraciones y compatible con las citas de la feature 006."

Contexto: la Consulta administrativa se usa para preguntas como "¿cuáles son los contenidos del curso X?", "¿cuáles son las líneas de TFG?" o "¿qué requisitos tiene Y?", cuya respuesta es una lista o una sección completa de un documento. Hoy MIA busca los fragmentos más parecidos a la pregunta y le entrega al modelo cada uno con un fragmento anterior y uno posterior; solo si el documento entero es corto (hasta 12 fragmentos) se lo entrega completo. Medido el 2026-10-16 en producción: 73 de 162 documentos superan ese tamaño, y entre los programas de curso, Deep Learning tiene 21 fragmentos, Procesamiento de Lenguaje Natural 20, Redes Neuronales 17, Introducción a la Investigación 17, y Diseño de Experimentos 15 (su temario se entregó solo hasta la página 4 de 7, y el modelo avisó que "la lista está incompleta"). Además, el 2026-10-16 una respuesta en modo literal terminó a media frase aunque quedaba mucho margen de longitud, y MIA no registra por qué terminó la generación, así que hoy no puede detectar ni medir esos cortes. El límite del contexto ya figura en [PRUEBAS_MVP.md](../../docs/PRUEBAS_MVP.md) y [OPERACION.md](../../docs/OPERACION.md) como problema conocido. Esta feature es el requerimiento BUS-8 de [Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md).

## Clarifications

### Session 2026-10-16

- Q: ¿Cuánto pueden subir el costo medio y la latencia p50 por consulta al entregar más contexto? → A: Opción A: hasta 25 % en el costo medio y hasta 25 % en la latencia p50 (confirmado por el usuario el 2026-10-16). El 2026-10-18 el usuario aceptó mantener 25 % como tope; el margen hasta 50 % solo se usaría si la medición muestra que alguna lista de un documento grande sigue saliendo cortada y subir las variables de alcance la resuelve, y exigiría una decisión explícita del usuario.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recibir la lista o sección completa cuando la respuesta es una lista (Priority: P1)

Una persona de Coordinación pregunta "¿cuáles son los contenidos del curso Diseño de Experimentos?". MIA responde con el temario completo del programa del curso, todas sus secciones (A, B, C y las que siguen) hasta el último ítem, sin la advertencia de que la lista está incompleta. Lo mismo para las líneas de TFG, los requisitos de un reglamento o los acuerdos de un acta cuando la respuesta es una lista o una sección que ocupa varias páginas: la respuesta llega entera.

**Why this priority**: es lo que el usuario pidió y el uso más frecuente de la Consulta (programas de curso, reglamentos, listas de requisitos). Una lista cortada es peor que una lista que no se pidió: parece completa y no lo es.

**Independent Test**: preguntar por los contenidos de los programas de curso más largos (Diseño de Experimentos, Deep Learning, Procesamiento de Lenguaje Natural, Redes Neuronales, Introducción a la Investigación, Sistemas Operativos Avanzados) y comprobar en cada respuesta que aparece el último ítem del temario del documento.

**Acceptance Scenarios**:

1. **Given** un programa de curso de 15 fragmentos como el de Diseño de Experimentos, **When** se pregunta por sus contenidos, **Then** la respuesta incluye todas las secciones del temario hasta la última y no dice que la lista está incompleta.
2. **Given** un programa de curso de más de 20 fragmentos como el de Deep Learning, **When** se pregunta por sus contenidos, **Then** la respuesta incluye el último ítem del temario.
3. **Given** una lista o sección que continúa más allá del fragmento encontrado en un documento largo (un reglamento, un acta), **When** se pregunta por ella, **Then** la respuesta incluye lo que sigue dentro del alcance configurado (los fragmentos posteriores que se entregan) y, si la lista continúa más allá de ese alcance, lo dice (ver escenario 4).
4. **Given** un documento tan largo que la lista o sección no cabe en el contexto máximo permitido por consulta, **When** se pregunta por ella, **Then** la respuesta dice de forma explícita que es parcial y en qué documento continúa, en lugar de presentarse como completa.
5. **Given** una pregunta cuya respuesta cabe en un solo fragmento, **When** se pregunta, **Then** la respuesta no cambia respecto de hoy (misma información, misma forma).

---

### User Story 2 - Detectar una respuesta cortada y no entregarla como completa (Priority: P1)

A veces el modelo termina su respuesta antes de tiempo: a media frase, a mitad de una lista, o por haber agotado el límite de longitud. Hoy MIA la entrega como si estuviera completa. Con esta feature, MIA detecta que la generación no terminó normalmente, lo registra en el módulo Uso y aplica una regla definida: intenta de nuevo una vez y, si el segundo intento también se corta, entrega el texto con un aviso claro al final de que la respuesta pudo quedar incompleta. La persona nunca recibe un texto cortado sin saberlo.

**Why this priority**: es la segunda causa de respuestas incompletas y hoy es invisible (no se registra el motivo del fin). Sin detectarla no se puede medir ni mejorar.

**Independent Test**: simular respuestas del modelo que terminan por límite de longitud o de forma anormal y comprobar que MIA reintenta una vez, que el segundo intento correcto reemplaza al primero, y que si ambos se cortan el texto lleva el aviso y el registro de Uso lo anota.

**Acceptance Scenarios**:

1. **Given** que el modelo informa que terminó por límite de longitud o por otro motivo anormal, **When** MIA procesa la respuesta, **Then** no la entrega como completa.
2. **Given** una respuesta cortada, **When** el segundo intento termina bien, **Then** se entrega el segundo intento y el costo de ambos intentos se registra en el módulo Uso.
3. **Given** una respuesta cortada, **When** el segundo intento también se corta, **Then** se entrega el texto con un aviso al final ("La respuesta pudo quedar incompleta") y el registro de Uso lo anota.
4. **Given** una respuesta que terminó con normalidad, **When** MIA la procesa, **Then** el comportamiento, el costo y la latencia son los de siempre (sin reintento).
5. **Given** una respuesta cortada en la que el reintento haría superar un tope de gasto, **When** MIA decide, **Then** respeta el tope: no reintenta y entrega el texto con el aviso.
6. **Given** una respuesta cortada que además es "sin información", **When** MIA la procesa, **Then** sigue siendo "sin información" y no se reintenta.

---

### User Story 3 - Poder apagarlo y volver al comportamiento anterior (Priority: P2)

Quien opera MIA puede encender o apagar el contexto completo y la detección de cortes con variables de configuración independientes, sin desplegar código ni migrar la base. Mientras no se decida lo contrario, el valor por defecto es el comportamiento actual. Se enciende en producción cuando la medición de la historia 4 demuestra que mejora y no rompe nada.

**Why this priority**: es la salvaguarda (BUS-6) para probar en producción y poder retroceder en minutos, y para separar el efecto del contexto completo del efecto del reintento.

**Independent Test**: con ambas opciones apagadas, repetir la línea base y comprobar que las respuestas y las fuentes son las de antes; encender cada una por separado y comprobar que solo cambia lo suyo.

**Acceptance Scenarios**:

1. **Given** la configuración por defecto, **When** MIA responde, **Then** el contexto entregado, el texto y las fuentes son idénticos a los de antes de la feature.
2. **Given** solo el contexto completo encendido, **When** se pregunta por un temario largo, **Then** la respuesta es completa y no hay reintentos.
3. **Given** solo la detección de cortes encendida, **When** el modelo termina de forma anormal, **Then** se reintenta o se avisa, y el contexto es el de siempre.
4. **Given** un valor inválido en cualquiera de las dos opciones, **When** el servicio arranca o responde, **Then** usa el comportamiento anterior y deja un aviso en el registro en vez de fallar.

---

### User Story 4 - Medir con listas largas que las respuestas salen completas y sin cortes (Priority: P2)

Quien opera MIA agrega al conjunto de casos de la feature 005 casos de listas largas, cada uno con el último ítem esperado en la respuesta, y repite la medición con la herramienta de la 005. El informe cuenta cuántas listas salen completas, cuántas respuestas terminan cortadas, cuántas necesitaron reintento, y compara el costo y la latencia con la línea base y con un control de la opción apagada.

**Why this priority**: es la prueba de que la feature cumple lo pedido y de que no rompe los 19 casos de la batería del MVP ni el filtrado de fuentes de la feature 006.

**Independent Test**: correr `respuestas` con la opción apagada y encendida sobre los casos nuevos y comparar con `comparar`; leer en el informe las listas completas, los cortes y los reintentos.

**Acceptance Scenarios**:

1. **Given** el conjunto de casos con listas largas, **When** se corre la medición con la opción apagada, **Then** el informe muestra qué listas hoy salen cortadas (línea base del problema).
2. **Given** la misma medición con la opción encendida, **When** se compara, **Then** todas las listas esperadas salen completas.
3. **Given** las dos corridas, **When** se comparan, **Then** el informe muestra el costo medio, la latencia p50 y p95, la cantidad de reintentos y la cantidad de respuestas que terminaron con el aviso de posible corte.
4. **Given** los 19 casos de la batería del MVP, **When** se comparan con la línea base, **Then** ninguno empeora.

---

### Edge Cases

- Un documento de más de 100 fragmentos (un acta larga, una tesis): no se puede entregar entero; la lista o sección debe completarse hasta donde la necesite la pregunta y, si aun así no cabe en el tope de contexto, la respuesta lo dice.
- La lista completa está repartida entre dos documentos: por defecto solo el documento de mejor resultado recibe el trato ampliado; el segundo queda como hoy y la variable que fija cuántos documentos principales se amplían (por defecto 1) permite aumentarlo. El tope de contexto por consulta aplica al total.
- El documento mismo está incompleto o truncado: MIA no puede inventar lo que no está; la respuesta puede decir que el documento no continúa.
- Una pregunta amplia ("háblame del programa") que atraería muchos documentos largos: el tope de contexto por consulta evita que el costo se dispare; se prioriza lo más relevante.
- El segundo intento tras un corte tarda más o falla por proveedor: la consulta termina con el texto del primer intento y el aviso, o con el error que ya hoy se devuelve si el proveedor no responde; nunca queda colgada.
- El modelo corta la respuesta justo antes o después de la línea de fuentes de la feature 006: se trata como corte si la generación no terminó con normalidad.
- Un corte detectado en una respuesta "sin información": no se reintenta.
- El reintento se produce con el tope diario del artefacto casi alcanzado: respeta el tope.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cuando la respuesta es una lista o una sección de un documento que continúa más allá del fragmento encontrado, MIA debe entregar al modelo lo que sigue dentro de un alcance configurable; si el documento es de tamaño moderado (FR-002) debe poder entregarse la lista o sección completa, y si no lo es, la respuesta debe decir cuándo la lista puede continuar fuera de lo entregado (FR-004). MIA no promete detectar dónde termina una lista en un documento largo.
- **FR-002**: Los documentos de tamaño moderado (cubriendo al menos los programas de curso conocidos, hasta unos 25 fragmentos) deben poder entregarse completos al modelo.
- **FR-003**: Para documentos más largos, MIA debe ampliar el contexto alrededor de lo encontrado hasta cubrir la lista o sección, dentro de un tope de tamaño de contexto por consulta fijado por configuración.
- **FR-004**: Si, aun con el tope, la lista o sección no cabe completa, la respuesta debe indicar de forma explícita que es parcial y en qué documento continúa; no debe presentarse como completa.
- **FR-005**: El tamaño total del contexto por consulta debe tener un tope, para acotar el costo y respetar los topes de gasto vigentes (por artefacto y de toda la API).
- **FR-006**: MIA debe conocer, para cada respuesta del modelo, el motivo por el que terminó la generación (fin normal, límite de longitud u otro) y dejarlo registrado en el registro informativo del servidor, independientemente de que las opciones estén encendidas, para poder contar cuántas terminan de forma anormal; en el registro de Uso solo se anotan los cortes que se reintentaron o se entregaron con aviso (FR-007 a FR-009).
- **FR-007**: Ante una generación que no terminó con normalidad, MIA no debe entregar el texto como completo: debe reintentar una vez y entregar el segundo intento si termina con normalidad.
- **FR-008**: Si el segundo intento también termina de forma anormal, MIA debe entregar el texto con un aviso al final que diga que la respuesta pudo quedar incompleta, y el registro de Uso debe anotarlo.
- **FR-009**: El costo de ambos intentos debe quedar registrado en el módulo Uso; si reintentar haría superar un tope de gasto, no se reintenta y se entrega el texto con el aviso.
- **FR-010**: No se reintenta una respuesta "sin información" ni una respuesta rechazada por permisos o topes.
- **FR-011**: El contexto ampliado y la detección de cortes deben poder encenderse y apagarse cada uno por separado mediante configuración, sin cambiar código ni base de datos; por defecto el comportamiento es el anterior a la feature.
- **FR-012**: Un valor inválido en cualquiera de las dos opciones de encendido (contexto completo y detección de cortes) debe tratarse como apagado y dejar un aviso en el registro, sin hacer fallar la consulta. Los valores numéricos de configuración (tamaños y topes) fuera de su rango sí impiden el arranque, a propósito, como ya ocurre con las demás variables numéricas de consulta.
- **FR-013**: Con ambas opciones apagadas, el contexto entregado, la respuesta, las fuentes, el costo y el registro deben ser idénticos a los de antes de la feature.
- **FR-014**: La feature no debe cambiar cuándo MIA responde "sin información suficiente".
- **FR-015**: La trazabilidad de la feature 006 debe seguir funcionando con contextos más largos: la numeración de pasajes, la línea de fuentes, su validación y la regla de seguridad siguen aplicando.
- **FR-016**: Debe funcionar con cualquier proveedor de modelo configurado; si un proveedor no informa el motivo de fin de la generación, se trata como fin normal y se deja anotado que no se pudo verificar.
- **FR-017**: La respuesta de la API conserva su estructura; no se requieren migraciones ni reindexar los documentos ya cargados.
- **FR-018**: La herramienta de la feature 005 debe registrar por consulta si la respuesta fue reintentada y si terminó con el aviso de posible corte, resumirlo por modo, y admitir casos con un último ítem esperado en la respuesta.
- **FR-019**: Deben existir pruebas automáticas de la ampliación de contexto, del límite de tamaño, de la detección de cortes y del reintento (sin llamar a proveedores reales), y la documentación debe describir las opciones y cómo medir su efecto.

### Key Entities *(include if feature involves data)*

- **Contexto de la consulta**: los pasajes que se entregan al modelo; puede ser el fragmento y sus vecinos (hoy), el documento completo, o una ampliación que cubre la lista o sección.
- **Tope de contexto**: el tamaño máximo total de lo que se entrega por consulta.
- **Fin de la generación**: el motivo por el que el modelo dejó de escribir (normal, límite de longitud, otro, desconocido).
- **Respuesta con posible corte**: una respuesta cuyo segundo intento también terminó de forma anormal; lleva un aviso y una anotación en el registro de Uso.
- **Caso de lista larga**: un caso de la herramienta de medición con un último ítem esperado en la respuesta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En el conjunto de casos de listas largas (al menos 8: seis programas de curso largos, las líneas de TFG y una lista de un acta), el 100 % de las respuestas incluye el último ítem esperado en los dos modos.
- **SC-002**: En la corrida de verificación (al menos 80 consultas), ninguna respuesta se entrega cortada sin aviso: toda respuesta que terminó de forma anormal fue reintentada o lleva el aviso.
- **SC-003**: Los 19 casos de la batería del MVP siguen respondiendo bien, con su documento esperado, y los que hoy responden "sin información" siguen haciéndolo.
- **SC-004**: El porcentaje de consultas que necesita reintento es de 5 % o menos.
- **SC-005**: El costo medio por consulta de cada modo, medido con el módulo Uso, no sube más de 25 % respecto a la línea base, comparado contra el promedio de la línea base y un control con la opción apagada, y la mediana de la razón por caso lo confirma; los topes de gasto se siguen respetando.
- **SC-006**: La latencia p50 de cada modo no sube más de 25 % respecto a la línea base, con la misma comparación.
- **SC-007**: Con ambas opciones apagadas, la lista de fuentes y el texto de cada caso son los de la línea base (sin diferencias atribuibles a la feature).
- **SC-008**: Con la feature 006 encendida, la regla de seguridad de las citas se aplica en 10 % o menos de las respuestas con contenido, igual que antes.
- **SC-009**: Una persona de Coordinación, ante tres preguntas de temarios largos, confirma que la respuesta es la lista completa del documento.

## Assumptions

- Quien opera MIA es una sola persona (el usuario), y quien consulta es el personal de Coordinación mediante la Consulta administrativa.
- El tope de 25 % es un tope sobre el promedio: una consulta concreta cuyo documento principal se entrega completo (por ejemplo, un programa de curso de 15 a 21 fragmentos) puede subir bastante más que el promedio. Se acepta.
- Se considera "documento de tamaño moderado" el que cabe en unos 25 fragmentos (el mayor programa de curso conocido tiene 21); el valor exacto y el tope de contexto por consulta se fijan en el plan a partir de la medición del costo.
- El motivo de fin de la generación lo informan los proveedores compatibles con el formato de OpenAI (entre ellos OpenRouter); los demás proveedores, si no lo informan, quedan como "desconocido" y no se reintenta.
- El reintento es uno solo y con la misma pregunta y contexto; un segundo corte no se vuelve a reintentar.
- El aviso al final de una respuesta con posible corte es una frase fija en español; su redacción final se decide en el plan.
- El comportamiento por defecto sigue siendo el actual hasta que la medición de la historia 4 respalde encender las opciones; encenderlas en producción es una decisión posterior del usuario, fuera de esta feature.
- La verificación usa la herramienta de la feature 005 contra producción, con un artefacto con acceso a los dos programas, un tope de gasto fijado antes de correr, y una corrida de control con las opciones apagadas.
- Quedan fuera de esta feature: cambiar cómo se fragmentan o indexan los documentos (reindexación), la búsqueda híbrida o el reranker (BUS-1 y BUS-2), la pregunta limpia (opción B), y cualquier cambio visual de la Consulta.
- El comportamiento del modelo no es del todo determinista: un caso que cambie de resultado entre corridas se repite antes de contarse como regresión.
