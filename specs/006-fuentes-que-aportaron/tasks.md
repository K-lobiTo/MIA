---

description: "Tareas de implementación de la feature 006: mostrar solo las fuentes que aportaron a la respuesta"
---

# Tasks: Mostrar solo las fuentes que aportaron a la respuesta

**Input**: Design documents from `specs/006-fuentes-que-aportaron/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-013 exige pruebas automáticas de la validación y de las reglas. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US4 de spec.md), precedidas por la base común (configuración y formato del contexto).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US4)

## Reglas para quien implemente

- **Terminología:** "pasaje" es el fragmento tal como se entrega al modelo (un fragmento relevante con sus vecinos unidos, o el documento completo si es corto); la spec lo llama "fragmento" y el plan "pasaje".

- Trabajar en la rama `dev` (sin rama por feature). Nunca hacer merge a `main`, y no desplegar ni encender servicios de Railway sin la orden del usuario (la medición de US4 la requiere y se pide en su tarea).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude.
- **Sin migraciones ni cambios de esquema** (plan R7): la regla de seguridad se anota en `reject_reason`. No agregar dependencias.
- **Con la opción apagada el comportamiento debe ser idéntico al de antes** (FR-008): mismo texto de contexto, misma instrucción, misma respuesta, mismas fuentes, mismo registro.
- Ninguna llamada extra a un modelo (FR-002) y nada de lo nuevo en `src/mia/rag/providers/` salvo usar `format_context` (principio III).
- La respuesta de `POST /query` conserva su estructura (FR-011).
- Es un prototipo: lo más simple que cumpla la especificación.

---

## Phase 1: Setup

**Purpose**: archivos nuevos vacíos con sus pruebas, para trabajar con TDD.

- [X] T001 [P] Crear `src/mia/rag/citations.py` con un docstring que explique el propósito (citas del modelo y selección de fuentes, ver [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md)) y sin lógica todavía
- [X] T002 [P] Crear `tests/unit/test_citations.py` y `tests/unit/test_query_citations.py` con los `import` mínimos (y el fixture de base de `tests/unit/test_query_sources.py` como modelo: `base`, `make_artifact`, `client`, `modes_config`)

**Checkpoint**: `pytest` sigue pasando (los archivos nuevos no tienen pruebas aún).

---

## Phase 2: Foundational (bloquea a todas las historias)

**Purpose**: la opción de configuración y el formato del contexto compartido.

- [X] T003 Agregar en `src/mia/config.py`, junto a las demás `query_*`, el campo `query_cited_sources: str = "off"` con un comentario que remita a `src/mia/rag/citations.py`, y la línea `QUERY_CITED_SOURCES=off` con su comentario en `.env.example`. **Es texto y no `bool`** para que un valor inválido no haga fallar el arranque (FR-009, R5)
- [X] T004 En `src/mia/rag/citations.py`, implementar `cited_sources_enabled(value: str) -> bool`: `on`, `true`, `1`, `yes` (sin distinguir mayúsculas ni espacios) devuelven `True`; `off`, `false`, `0`, `no` y la cadena vacía devuelven `False`; **cualquier otro valor devuelve `False` y deja un aviso con `logging.getLogger(__name__).warning`, una sola vez por valor y por proceso** (FR-009; guardar los valores ya avisados en un conjunto del módulo para no llenar el registro en cada consulta). Agregar sus pruebas en `tests/unit/test_citations.py` (todos los valores válidos, mayúsculas, espacios, valor inválido con el aviso comprobado con `caplog`, y que un segundo uso del mismo valor inválido no repite el aviso; limpiar el conjunto de valores avisados entre pruebas)
- [X] T005 En `src/mia/rag/llm.py`, agregar a `RagContext` el campo `reference: int | None = None` ("número del pasaje dentro de la consulta, de 1 a N; nulo con la opción apagada") y una función `format_context(context: list[RagContext]) -> str` que une los pasajes con una línea en blanco y etiqueta cada uno `[Fuente: dominio=..., documento=...]` cuando `reference` es nulo (**idéntico byte por byte al texto actual**) y `[Fuente <n>: dominio=..., documento=...]` cuando no lo es. Agregar pruebas en `tests/unit/test_citations.py`: sin `reference` el resultado es exactamente `"\n\n".join(f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in context)` y con `reference` lleva el número
- [X] T006 Reemplazar en `src/mia/rag/providers/openrouter_llm.py`, `anthropic_llm.py`, `gemini_llm.py` y `glm_llm.py` la construcción local del bloque de contexto por `format_context(context)` (importándolo de `mia.rag.llm`); no cambiar nada más. Comprobar que `tests/unit/test_openrouter_llm.py` y `tests/unit/test_glm_llm.py` siguen pasando sin modificarlos

**Checkpoint**: `pytest` completo pasa; el comportamiento no cambió.

---

## Phase 3: User Story 1 - Ver solo las fuentes que sustentan la respuesta (Priority: P1) 🎯 MVP

**Goal**: con la opción encendida y citas válidas, la lista de fuentes contiene solo los pasajes citados y el texto de la respuesta sale limpio.

**Independent Test**: `pytest tests/unit/test_citations.py tests/unit/test_query_citations.py`: una respuesta simulada con `FUENTES: 1, 3` sobre 4 pasajes devuelve esos dos pasajes como fuentes y un texto sin la línea; lo mismo en modo literal y en razonamiento.

### Pruebas primero

- [X] T007 [US1] En `tests/unit/test_citations.py`, pruebas de `parse_citations(text, total)` para las filas con citas válidas del contrato: `FUENTES: 1, 3` con total 4, números repetidos (`3, 3, 1` da `[1, 3]`), con Markdown (`**FUENTES:** 2`), en minúsculas (`fuentes: 2`), con corchetes (`FUENTES: [1], [3]`), con la palabra "y" (`FUENTES: 1 y 3`), y que el texto devuelto no contiene la línea ni espacios finales sobrantes; y de `select_sources(parsed, total)` con citas válidas (`indexes` en orden creciente, `safety_rule` falso)
- [X] T008 [US1] En `tests/unit/test_query_citations.py`, pruebas de la ruta `POST /query` con `QUERY_CITED_SOURCES=on` (usar `monkeypatch.setattr(settings, "query_cited_sources", "on")`) en el estilo de `tests/unit/test_query_sources.py`: tres documentos entregados, el modelo simulado responde `"Dato.\nFUENTES: 2"` y la respuesta trae solo el documento 2 en `sources`, un `answer` igual a `"Dato."`, y `fake_llm_provider.answer` recibió contextos con `reference` 1, 2 y 3 y unas instrucciones que terminan con el párrafo de citas; y que, **aparte de `reference`**, los contextos que recibe el proveedor (dominio, documento, texto y orden) son exactamente los mismos que recibe con la opción apagada (FR-007); repetirla con `mode: "razonamiento"` y comprobar que las instrucciones del modo con razonamiento también reciben el párrafo

### Implementación

- [X] T009 [US1] En `src/mia/rag/citations.py`, definir `CITATION_INSTRUCTIONS` con el párrafo de [contracts/citas-y-fuentes.md](contracts/citas-y-fuentes.md) (corto, en español, sin guion largo) y las dataclasses `ParsedCitations` (`text`, `cited`, `invalid`, `line_found`) y `SourceSelection` (`indexes`, `safety_rule`) de [data-model.md](data-model.md)
- [X] T010 [US1] En `src/mia/rag/citations.py`, implementar `parse_citations(text: str, total: int) -> ParsedCitations` según la sección 2 del contrato y R3: mirar solo la **última línea no vacía**; reconocerla si, quitando `*`, `_`, `#`, `>` y espacios, empieza por `fuentes:` o `fuente:` sin distinguir mayúsculas ni tildes; quitarla del texto siempre que se reconozca; extraer los enteros con una expresión regular; `cited` = enteros únicos entre 1 y `total`, en orden creciente ("`cited` solo contiene enteros entre 1 y N"); `invalid` = los demás; una línea `FUENTES:` que no esté al final no se interpreta
- [X] T011 [US1] En `src/mia/rag/citations.py`, implementar `select_sources(parsed: ParsedCitations, total: int) -> SourceSelection` para el caso con citas válidas (`indexes = parsed.cited`, `safety_rule = False`); el caso sin citas válidas lo completa T015
- [X] T012 [US1] En `src/mia/api/routes/query.py`, cuando `cited_sources_enabled(settings.query_cited_sources)`: (1) asignar `reference = índice + 1` a cada `RagContext`; (2) pasar `config.instructions + "\n\n" + CITATION_INSTRUCTIONS` como `instructions`; (3) tras recibir la respuesta, aplicar `parse_citations` y usar el **texto limpio** como `answer`; (4) construir `sources` y `log.sources` solo con los pasajes de `select_sources`, sin repetir documentos en el registro (como hoy). Con la opción apagada, no ejecutar nada de esto. Hacer que T008 pase

**Checkpoint**: US1 completa; con la opción encendida y citas válidas, la ruta lista solo lo citado.

---

## Phase 4: User Story 2 - Nunca quedarse sin fuente verificable si el modelo no cita bien (Priority: P1)

**Goal**: sin citas utilizables se muestran todas las fuentes y se anota; con citas mezcladas se muestran las válidas; "sin información" no cambia.

**Independent Test**: respuestas simuladas sin línea, con `FUENTES: ninguna`, con números fuera de rango, mezcladas, repetidas, cortadas y "sin información" con y sin línea: ninguna deja la lista vacía salvo "sin información".

### Pruebas primero

- [X] T013 [US2] En `tests/unit/test_citations.py`, pruebas de las demás filas del contrato: sin línea, `FUENTES: ninguna`, `FUENTES:` sin números, `FUENTES: 9, 12` con total 4 (todo inválido), `FUENTES: 2, 9` con total 4 (`cited == [2]`, `invalid == [9]`), línea `FUENTES:` en medio del texto (no se interpreta y el texto no cambia), respuesta vacía, y `select_sources` sin citas válidas (`indexes` = todos, `safety_rule` verdadero)
- [X] T014 [US2] En `tests/unit/test_query_citations.py`, pruebas de la ruta: (a) el modelo no cita nada: `sources` trae todos los pasajes y en la consulta registrada `reject_reason == "Fuentes: sin citas utilizables, se mostraron todas"` y `outcome == "answered"`; (b) cita mezclada: solo los válidos y `reject_reason` nulo; (c) el modelo responde `"SIN_INFORMACION\nFUENTES: 1"`: la respuesta es "sin información" (`no_info` verdadero, sin fuentes, `outcome == "no_info"`); (d) respuesta solo `SIN_INFORMACION`: igual que hoy; (e) texto cortado sin línea: todas las fuentes; (f) en ningún caso una respuesta con contenido tiene `sources` vacío

### Implementación

- [X] T015 [US2] En `src/mia/rag/citations.py`, completar `select_sources` para el caso sin citas válidas: `indexes` = todos los pasajes (`range(1, total + 1)`) y `safety_rule = True`
- [X] T016 [US2] En `src/mia/api/routes/query.py`, detectar "sin información" sobre el **texto limpio** (después de quitar la línea de citas) para que `is_no_info_answer` siga funcionando aunque el modelo escriba la línea (BUS-3); cuando `safety_rule` sea verdadero, escribir en `log.reject_reason` la nota exacta `Fuentes: sin citas utilizables, se mostraron todas` en esa consulta respondida; y registrar con `logger.info` (sin texto de la respuesta) cuántos números inválidos hubo. Hacer que T014 pase

**Checkpoint**: US1 y US2 completas; el filtrado es seguro ante cualquier salida del modelo.

---

## Phase 5: User Story 3 - Poder apagarlo y volver al comportamiento anterior (Priority: P2)

**Goal**: apagado por defecto, idéntico a antes; encendible y apagable por variable sin tocar código.

**Independent Test**: `pytest tests/unit/test_query_citations.py -k apagada`: con la configuración por defecto o un valor inválido, el contexto, la instrucción, la respuesta y el registro son idénticos a los de antes.

- [X] T017 [US3] En `tests/unit/test_query_citations.py`, pruebas de la opción apagada: (a) con el valor por defecto, los contextos que recibe el proveedor simulado tienen `reference` nulo y la instrucción recibida es exactamente la del modo (`RAG_SYSTEM_PROMPT` o `REASONING_SYSTEM_PROMPT`); (b) si el modelo simulado devuelve un texto que termina con `FUENTES: 1`, la respuesta lo conserva intacto y lista todas las fuentes (sin interpretar); (c) `reject_reason` queda nulo; (d) con un valor inválido (`"quizas"`) se comporta como apagado y deja el aviso en el registro (`caplog`); (e) con `"ON"` y `" true "` se comporta como encendido
- [X] T018 [US3] Verificar y, si falta, ajustar en `src/mia/api/routes/query.py` que la opción se lea en **cada consulta** (`cited_sources_enabled(settings.query_cited_sources)` dentro del endpoint, no al importar el módulo) y que apagada no ejecute ninguna ruta nueva. Hacer que T017 pase
- [X] T019 [P] [US3] Documentar la variable en [docs/OPERACION.md](../../docs/OPERACION.md): una fila `QUERY_CITED_SOURCES` en la tabla de variables de entorno (valores, defecto `off`, qué hace, que se cambia en Railway y se reinicia el servicio, que volver a `off` devuelve el comportamiento anterior sin migraciones) y una frase en "Problemas frecuentes" sobre la nota `Fuentes: sin citas utilizables` del módulo Uso y qué hacer si aparece mucho

**Checkpoint**: US3 completa; la opción es segura de desplegar apagada.

---

## Phase 6: User Story 4 - Comprobar con la línea base que mejora sin romper nada (Priority: P2)

**Goal**: medir con la herramienta de la 005 las fuentes sobrantes, los resultados, el costo, la latencia y la frecuencia de la regla de seguridad.

**Independent Test**: `pytest tests/unit/test_linea_base.py` pasa con las pruebas nuevas, y la corrida `citas` produce un informe comparable con `base`.

### Pruebas primero

- [X] T020 [US4] En `tests/unit/test_linea_base.py`, pruebas de lo nuevo: `leer_costo` devuelve también `reject_reason` del detalle de Uso; `correr_respuestas` agrega `regla_de_seguridad` (verdadero si el `reject_reason` del costo empieza por `Fuentes: sin citas utilizables`, falso si no, nulo si no hubo detalle); `resumen_respuestas` suma `regla_de_seguridad_aplicada` y su `proporcion_regla_de_seguridad` sobre las respuestas con contenido (`respondio`); `comparar` informa diferencias de `regla_de_seguridad` entre corridas y, cuando ambas corridas tienen `respuestas`, la **mediana de la razón de costo y de latencia caso por caso** (corrida B sobre corrida A, solo con los casos que tienen costo en las dos; valores nulos o cero se descartan) y la diferencia de los costos medios; el informe muestra el dato. Con `regla_de_seguridad` ausente en corridas anteriores (como `base`) nada falla

### Implementación

- [X] T021 [US4] En `scripts/linea_base.py`, extender `leer_costo` para devolver `reject_reason`, `correr_respuestas` para registrar `regla_de_seguridad` por consulta (campo opcional, nulo si no hay detalle), `resumen_respuestas` para sumar `regla_de_seguridad_aplicada` y `proporcion_regla_de_seguridad`, `comparar` (diferencias de la regla de seguridad y las medianas de razón de costo y de latencia por modo) y `generar_informe` para mostrarlos (en la línea de cada modo del informe y en las diferencias); no cambiar códigos de salida ni opciones. Actualizar [specs/005-linea-base-busqueda/contracts/linea-base-cli.md](../005-linea-base-busqueda/contracts/linea-base-cli.md) con una nota del campo nuevo. Hacer que T020 pase
- [X] T022 [US4] **Pedir al usuario autorización** para la medición, y esperar su respuesta: (a) cómo desplegar el código nuevo, porque `scripts/servicios.py encender` despliega `origin/main` por defecto y esta feature está en `dev`: `--ref origin/dev` (despliega `dev` en producción solo para medir; no hay migraciones nuevas, así que la base no cambia) o que el usuario haga antes el merge a `main`; (b) el tope de gasto de la corrida (propuesta: 0,40 USD, la corrida `base` costó 0,25); (c) que se active y desactive después el artefacto `PRUEBA Aceptación ambas unidades` como en la 005; (d) que son **dos corridas** (control con la opción apagada y `citas` con la opción encendida), cada una con su tope, así que el gasto total previsto es de hasta 0,80 USD (unos 0,50 en la práctica); y (e) que `dev` lleva también los scripts, pruebas y documentación de la 005 además de esta feature. No avanzar sin su respuesta
- [X] T023 [US4] Con la autorización de T022: `railway variable set QUERY_CITED_SOURCES=on -s MIA --skip-deploys`, `python scripts/servicios.py encender MIA --forzar` con la referencia acordada, activar el artefacto de prueba y correr dos corridas con el código nuevo, en este orden: primero el **control** con `QUERY_CITED_SOURCES=off` (`respuestas --etiqueta control ...`) y luego `QUERY_CITED_SOURCES=on` (`respuestas --etiqueta citas ...`), ambas con `--url https://mia-main.up.railway.app --tope-usd <N> --modo ambos`; entre una y otra cambiar la variable con `railway variable set ... --skip-deploys` y reiniciar el servicio. Luego `comparar base control` (SC-008: cero diferencias de documentos mostrados; y el ruido entre corridas de costo y latencia), `comparar control citas` y `comparar base citas`, y `informe citas --salida tmp/linea_base/informe-citas.md` (**no** sobrescribir `docs/LINEA_BASE_BUSQUEDA.md`, que es el informe de `base`). Si algún caso de la batería del MVP empeora, repetirlo una vez antes de contarlo como regresión (el modelo no es determinista)
- [X] T024 [US4] Evaluar la corrida `citas` contra los criterios de éxito de [spec.md](spec.md) y escribir el resultado a mano: SC-001 (fuentes sobrantes bajan al menos 50 % en cada modo), SC-002 (los 19 casos de la batería siguen bien y citan su documento esperado), SC-003 (mismos "sin información"), SC-004 (costo medio no sube más de 5 % frente al promedio de `base` y `control`, y la mediana de la razón de costo por caso lo confirma) y SC-005 (latencia p50 no sube más de 10 %, con la misma comparación), SC-006 (regla de seguridad en no más del 10 % de las respuestas con contenido) y SC-007 (ninguna respuesta con contenido sin fuentes). Para SC-001, antes de contar, mostrar al usuario los casos que sigan con fuentes sobrantes (ids y nombres de documento) para que valide si alguno de esos documentos sí aportó; los validados se descuentan de los sobrantes y se informan aparte. Agregar a [docs/LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md) una sección "Resultado de la feature 006" (se conserva al regenerar si se escribe después de `## Lectura`, que ya existe) con la tabla de criterios, los números y una recomendación (encender o no). **No encender la opción por defecto**: decide el usuario
- [X] T025 [US4] Dejar todo como estaba: `railway variable set QUERY_CITED_SOURCES=off -s MIA --skip-deploys` (salvo que el usuario pida dejarla encendida), desactivar el artefacto `PRUEBA Aceptación ambas unidades`, apagar la API con `python scripts/servicios.py apagar MIA --forzar`, y confirmar con `python scripts/servicios.py estado`

**Checkpoint**: US4 completa; hay datos para decidir si se enciende.

---

## Phase 7: Polish & Cross-Cutting

- [X] T026 [P] Actualizar [docs/ARQUITECTURA.md](../../docs/ARQUITECTURA.md) (sección "Flujo de una consulta y de una ingesta"): cómo se numeran los pasajes, la línea `FUENTES:`, la validación, la regla de seguridad y la opción `QUERY_CITED_SOURCES`; y el helper `format_context` en la descripción de los proveedores
- [X] T027 [P] Actualizar [docs/Definicion_Requerimientos_V3.md](../../docs/Definicion_Requerimientos_V3.md): estado de BUS-5 y de la opción F (implementada, apagada por defecto, resultado de la medición con enlace a [LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)) y el criterio de aceptación de BUS-5 de la sección 2.9
- [ ] T028 Correr `ruff check src tests scripts` y `pytest` completo y corregir lo que falle; verificar con `git diff --stat main..dev -- src/mia/storage/migrations alembic` que no hay migraciones, con `git diff main..dev -- src/mia/api/routes/query.py` que la estructura de `QueryResponse` no cambió, y con `grep -rnP "\x{2014}"` sobre los archivos tocados que no hay guion largo
- [ ] T029 Pedir al usuario una comprobación manual de SC-009 con tres preguntas reales (por ejemplo con `scripts/cliente.py` contra la API local o de Railway encendida): que confirme si, mirando solo las fuentes mostradas, identifica de qué documento sale la afirmación principal. Esta comprobación también cubre el escenario 5 de la historia 1 (que la información afirmada es la misma con y sin filtrado). Anotar su respuesta en la sección del resultado de [docs/LINEA_BASE_BUSQUEDA.md](../../docs/LINEA_BASE_BUSQUEDA.md)
- [ ] T030 Hacer commit en `dev` por etapa (base común, citas, ruta, herramienta, documentación) con mensajes en español sin atribución y `git push origin dev`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias; T001 y T002 en paralelo.
- **Foundational (Phase 2)**: depende de Setup; bloquea las historias. T003 a T005 pueden hacerse en cualquier orden (archivos distintos salvo T004 y T005 en pruebas del mismo archivo); T006 depende de T005.
- **US1 (Phase 3)**: depende de Foundational. Las pruebas (T007, T008) van antes que la implementación (T009 a T012); T012 depende de T009 a T011.
- **US2 (Phase 4)**: depende de US1 (completa `select_sources` y la ruta).
- **US3 (Phase 5)**: depende de US1 (necesita la ruta); es independiente de US2 salvo por T017 (b) y (c).
- **US4 (Phase 6)**: T020 y T021 (herramienta) solo dependen de la 005 y pueden hacerse en cualquier momento, pero **deben estar terminadas antes de T023**; T022 a T025 dependen de US1 a US3 terminadas y de la autorización del usuario.
- **Polish (Phase 7)**: al final.

### Parallel Opportunities

- T001 y T002; T019 (documentación) en paralelo con T017 y T018; T020 y T021 pueden hacerse en paralelo con US1 a US3 porque tocan `scripts/` y `tests/unit/test_linea_base.py`; T026 y T027.
- Casi todo `src/` pasa por `citations.py` y `query.py`, así que no se paraleliza dentro de una historia.

---

## Implementation Strategy

### MVP (US1 + US2 + US3)

1. Setup y Foundational: configuración, formato del contexto y proveedores sin cambio de comportamiento.
2. US1 y US2: el filtrado con su regla de seguridad. **Parar y validar** con `pytest`: ya hay una función completa y segura, apagada por defecto.
3. US3: confirmar que apagada es idéntica y documentar la variable.

### Entrega incremental

1. MVP desplegable apagado, sin riesgo.
2. US4: medir contra producción (con autorización) y decidir si se enciende.
3. Polish y commits.

### Riesgos a vigilar

- Que apagada algo cambie (el texto de contexto, la instrucción): T005 y T017 lo comprueban byte por byte.
- Que el modelo no escriba la línea (o la escriba distinta) y la regla de seguridad se aplique casi siempre: T024 mide la proporción (meta: 10 % o menos) y, si falla, se ajusta la redacción del párrafo antes de decidir.
- Que una línea `FUENTES:` rompa la detección de "sin información": T014 (c) lo prueba.
- Que se despliegue `dev` a producción sin querer: T022 exige autorización explícita.
