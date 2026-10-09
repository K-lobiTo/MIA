---

description: "Tareas de implementación de la Consulta administrativa de MIA"
---

# Tasks: Consulta administrativa de MIA

**Input**: Design documents from `specs/003-consulta-administrativa/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-026 exige pruebas automáticas para los cambios de la API y para las funciones de la Consulta que no dependen de la red. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US5 de spec.md), en orden de prioridad.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US5)

## Reglas para quien implemente

- Trabajar en la rama `dev`. Nunca hacer merge a `main` (lo hace el usuario).
- Todo texto (código, comentarios, mensajes de la interfaz, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Ver `CLAUDE.md`.
- Seguir el estilo del código existente: comentarios breves que explican el porqué; en `web/consulta/` el mismo patrón que `web/admin/` (cliente de la API, `localStorage` dentro de `try/catch`, variables de color en `styles/tokens.css`).
- Los textos exactos de pantallas, estados y errores están en [contracts/ui-consulta.md](contracts/ui-consulta.md); no inventar otros.
- Después de cada fase: `pytest` y `ruff check src tests scripts` en verde, y en `web/consulta/` `npm run typecheck` y `npm test`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: proyecto de la Consulta y configuración nueva de la API.

- [X] T001 Agregar a `Settings` en `src/mia/config.py` `query_search_limit_razonamiento: int = 16` junto a `query_search_limit`, con un comentario breve ("resultados de la búsqueda en modo con razonamiento; más que en literal para que entren datos de más documentos") y validación de rango "entero de 1 a 50" (con `Field(ge=1, le=50)` en ambos límites, `query_search_limit` incluido)
- [X] T002 [P] Documentar `QUERY_SEARCH_LIMIT_RAZONAMIENTO=16` en `.env.example` (junto a `QUERY_SEARCH_LIMIT`) y en `deploy/railway/variables.example.env` (sección "Versión 2"), con su comentario
- [X] T003 [P] Crear el proyecto Vite en `web/consulta/`: `package.json` (nombre `mia-consulta`, scripts `dev`, `build` = `tsc && vite build`, `typecheck` = `tsc`, `test` = `vitest run`, `preview`), dependencias `react@^19`, `react-dom@^19`, `@tanstack/react-query@^5`, y de desarrollo `typescript@^5.6`, `vite@^6`, `@vitejs/plugin-react`, `@types/react`, `@types/react-dom`, `@types/node`, `vitest` (mismas versiones que `web/admin/package.json`); `tsconfig.json` estricto como el del panel; `index.html` con `lang="es"` y `<title>MIA: Consulta</title>`; `src/vite-env.d.ts` con `VITE_API_URL`
- [X] T004 [P] Crear `web/consulta/vite.config.ts` como `web/admin/vite.config.ts` pero con puerto 3000 (`strictPort`) en `server` y `preview`; proxy `/api` hacia `process.env.MIA_API_URL ?? "http://localhost:8000"` reescribiendo el prefijo, con `timeout` y `proxyTimeout` de 200 000 ms
- [X] T005 [P] Crear `web/consulta/src/styles/tokens.css` y `web/consulta/src/styles/base.css`: variables de color en `:root`, redefinidas en `@media (prefers-color-scheme: dark)`, con un color de acento propio de la Consulta distinto del violeta del panel; tipografía del sistema; utilizable desde 360 px sin desplazamiento horizontal; estilos para burbuja de pregunta, respuesta, respuesta "sin información" (fondo neutro) y error

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: instrucción y fragmentos por modo en la API, y la base de la Consulta (cliente, clave, nombre). Ninguna historia puede empezar antes.

### Pruebas

- [X] T006 [P] Crear `tests/unit/test_modes_config.py`: `mode_config("literal")` tiene `instructions == RAG_SYSTEM_PROMPT` y `search_limit == settings.query_search_limit`; `mode_config("razonamiento")` tiene `instructions == REASONING_SYSTEM_PROMPT` y `search_limit == settings.query_search_limit_razonamiento`; `REASONING_SYSTEM_PROMPT` contiene `SIN_INFORMACION`, "Lo que dicen los documentos" y "Cálculo o conclusión", y prohíbe el conocimiento externo; un `query_search_limit_razonamiento` de 0 o 51 falla al crear `Settings`
- [X] T007 [P] Ampliar `tests/unit/test_query_access.py` (con los proveedores falsos que ya usa): en modo literal el `VectorStore` falso recibe `limit=8` y el LLM falso recibe `instructions=RAG_SYSTEM_PROMPT`; en modo con razonamiento `limit=16` y `REASONING_SYSTEM_PROMPT`; la respuesta trae `no_info: false` cuando responde y `no_info: true` (con `sources` vacío) cuando no hay fragmentos relevantes y cuando el modelo responde la marca; una pregunta de 2001 caracteres da 422 y una de 2000 se acepta
- [X] T008 [P] Actualizar `tests/unit/test_openrouter_llm.py` y `tests/unit/test_glm_llm.py`: el mensaje de sistema enviado es la instrucción recibida por parámetro (probar con un texto propio, no la constante)

### API

- [X] T009 Agregar `REASONING_SYSTEM_PROMPT` en `src/mia/rag/llm.py` según research decisión 2: misma base que `RAG_SYSTEM_PROMPT` (solo los fragmentos, sin conocimiento externo, español, Markdown simple sin LaTeX, `SIN_INFORMACION` si ningún fragmento trata el tema), más: puede combinar, comparar, contar y calcular con datos de varios fragmentos; toda respuesta con información tiene dos partes en este orden con títulos en negrita (no `#`): "**Lo que dicen los documentos**" (cada dato usado, con el nombre del documento de donde sale) y "**Cálculo o conclusión**" (la operación con sus números, p. ej. `4 + 4 + 4 = 12`, y el resultado, o lo que se deduce y por qué); si falta un dato para el cálculo, lo dice en vez de suponerlo
- [X] T010 Cambiar la interfaz en `src/mia/rag/llm.py`: `LLMProvider.answer(self, question, context, instructions: str = RAG_SYSTEM_PROMPT) -> LLMAnswer`; actualizar todos los proveedores en `src/mia/rag/providers/` (`openrouter_llm.py`, `anthropic_llm.py`, `gemini_llm.py`, `glm_llm.py` usan `instructions` como mensaje de sistema en lugar de importar `RAG_SYSTEM_PROMPT`; `openai_llm.py` y `local_llm.py` solo cambian la firma)
- [X] T011 Agregar a `ModeConfig` en `src/mia/rag/modes.py` los campos `instructions: str` y `search_limit: int` (literal: `RAG_SYSTEM_PROMPT` y `settings.query_search_limit`; razonamiento: `REASONING_SYSTEM_PROMPT` y `settings.query_search_limit_razonamiento`), actualizando el docstring del módulo
- [X] T012 Modificar `src/mia/api/routes/query.py`: obtener `config = mode_config(payload.mode)` antes de la búsqueda y usar `config.search_limit` en `vector_store.search(...)` y `config.instructions` en `llm_provider.answer(payload.question, context, instructions=config.instructions)` (por nombre, como lo comprueba T007); `QueryRequest.question` con `Field(min_length=1, max_length=2000)`; `QueryResponse` con `no_info: bool = False`, en `True` en la función `no_info()`. Actualizar los proveedores falsos de `tests/unit/test_query_sources.py` y `tests/unit/test_query_no_info.py` si su firma lo exige
- [X] T013 [P] Documentar en `docs/ARQUITECTURA.md` (sección de modos de respuesta) la instrucción y la cantidad de fragmentos por modo, `no_info` y el largo máximo de la pregunta, enlazando a `specs/003-consulta-administrativa/contracts/api-consulta-modos.md`

### Base de la Consulta

- [X] T014 [P] Crear `web/consulta/src/api/types.ts` con los tipos de los contratos: `Config` (con `artifact` y `caps`), `Mode`, `Domain` (`id`, `unit_id`, `unit_name`, `name`, `description`), `QueryRequest`, `QueryResponse` (con `no_info`), `Source`, `Rating` (`"util" | "no_util"`)
- [X] T015 Crear `web/consulta/src/api/client.ts` con el patrón de `web/admin/src/api/client.ts`: base `import.meta.env.VITE_API_URL ?? "/api"`; clave en `localStorage` bajo `mia-consulta-key` (lectura y escritura en `try/catch`) con `getKey`, `setKey`, `useKey` (`useSyncExternalStore`); `apiFetch<T>(path, init, timeoutMs = 30_000)` que agrega `X-Artifact-Key`, usa `AbortController` con el tiempo indicado, parsea JSON y lanza `ApiError` con `status` (0 sin conexión, -1 tiempo agotado) y `detail` (texto de `detail`, o el primer mensaje si es una lista de 422); ante 401 borra la clave y llama al manejador registrado con `setInvalidKeyHandler`
- [X] T016 Crear `web/consulta/src/api/consulta.ts` con hooks de TanStack Query: `useConfig()` (clave `["config"]`, `refetchOnWindowFocus: true`), `useDomains()` (clave `["domains"]`), `useAsk()` (mutación de `POST /query` con `timeoutMs = 200_000`) y `useFeedback()` (mutación de `POST /query/{id}/feedback`); los hooks de lectura solo corren si hay clave
- [X] T017 Crear `web/consulta/src/main.tsx`, `web/consulta/src/App.tsx`, `web/consulta/src/components/KeyScreen.tsx` y `web/consulta/src/components/Header.tsx`: sin clave, `KeyScreen` (campo, botón "Entrar", explicación de dónde se obtiene, y el aviso de clave inválida si se llegó por un 401, con los textos de `contracts/ui-consulta.md`); con clave, `Header` con `config.artifact.name` y `document.title` igual a ese nombre (FR-002), con una acción para cambiar la clave (FR-001); mientras carga `/config`, un estado de carga

**Checkpoint**: la API responde distinto por modo y es compatible con los clientes actuales; la Consulta abre con clave y muestra el nombre de la instancia. `pytest` en verde.

---

## Phase 3: User Story 1 - Preguntar sobre los dominios de mi unidad y ver de dónde sale la respuesta (Priority: P1) 🎯 MVP

**Goal**: preguntar en modo literal sobre los dominios permitidos y ver la respuesta con formato, fuentes y fragmentos.

**Independent Test**: con la clave de una instancia de Computación, preguntar por un acuerdo de un acta y ver la respuesta citando el acta y su dominio, con fragmentos desplegables; con la clave de Administración de Empresas, ese dominio no aparece.

### Tests for User Story 1

- [X] T018 [P] [US1] Crear `web/consulta/src/format/formatAnswer.ts` vacío con su firma y `web/consulta/src/format/formatAnswer.test.ts` (Vitest): convierte texto en bloques `paragraph`, `bullets` (líneas con `*` o `-`) y `numbered` (líneas con `1.` o `1)`), con segmentos `{text, bold}` para `**negritas**`; una línea que empieza con `#` se vuelve un párrafo en negrita sin los `#`; un texto con `<script>` queda como texto literal en un segmento; líneas vacías separan bloques
- [X] T019 [P] [US1] Crear `web/consulta/src/state/domains.ts` vacío con su firma y `web/consulta/src/state/domains.test.ts`: `groupByUnit(domains)` agrupa por `unit_name` en orden alfabético y devuelve un solo grupo sin título si hay una sola unidad; `restoreSelection(saved, domains)` devuelve todos los ids si no hay nada guardado o ninguno guardado sigue permitido, y si no, solo los guardados que siguen permitidos; `loadSelection`/`saveSelection` usan `localStorage` bajo `mia-consulta-dominios` dentro de `try/catch`
- [X] T020 [P] [US1] Crear `web/consulta/src/state/sources.test.ts` y `web/consulta/src/state/sources.ts`: `uniqueDocuments(sources)` devuelve los pares documento y dominio sin repetir, en el orden en que aparecen

### Implementation for User Story 1

- [X] T021 [US1] Implementar `web/consulta/src/format/formatAnswer.ts` hasta pasar T018, y crear `web/consulta/src/format/Answer.tsx` que dibuja los bloques con elementos React (`<p>`, `<ul>`, `<ol>`, `<strong>`), sin `dangerouslySetInnerHTML` (FR-021)
- [X] T022 [US1] Implementar `web/consulta/src/state/domains.ts` hasta pasar T019
- [X] T023 [US1] Crear `web/consulta/src/components/DomainPicker.tsx`: casillas por dominio agrupadas por unidad (con título de unidad solo si hay más de una), acciones "Todos" y "Ninguno", selección guardada al cambiar; sin dominios, "Esta Consulta todavía no tiene dominios para consultar."; lateral en pantallas anchas y desplegable en celular (FR-004, FR-006, FR-025)
- [X] T024 [US1] Crear `web/consulta/src/components/Composer.tsx`: área de texto con `maxLength={2000}` y contador visible desde 1800 caracteres, Enter envía y Mayúsculas+Enter agrega una línea; botón deshabilitado sin texto, sin dominios ("Elige al menos un dominio.") o con una consulta en curso; tras un 422 conserva lo escrito y muestra el mensaje de `contracts/ui-consulta.md` (FR-005, FR-019)
- [X] T025 [US1] Crear `web/consulta/src/state/conversation.ts` (lista de intercambios en memoria según data-model.md, "Conversación": `localId`, `question`, `domainIds`, `mode`, `status` `pending` → `answered` | `no_info` | `failed`, `response`, `error`, `rating`; sin persistencia, FR-020) y `web/consulta/src/components/Conversation.tsx` con `Exchange.tsx`: burbuja de pregunta; mientras espera "Buscando en N dominios..."; respuesta con `Answer`, "Fuentes" (`uniqueDocuments`) y desplegable "Ver fragmentos (N)" con el texto de cada fragmento; respuesta con `no_info` con su estilo propio y sin fuentes (FR-014, FR-016); en la conversación vacía, ejemplos de preguntas en texto fijo
- [X] T026 [US1] Integrar en `web/consulta/src/App.tsx`: panel de dominios, conversación y composer; al enviar, crear el intercambio `pending`, llamar a `useAsk` con los dominios seleccionados y el modo `literal` (el selector llega en US2), y pasar el intercambio a `answered`, `no_info` o `failed` (con el mensaje de error de `contracts/ui-consulta.md` y "Reintentar", que crea un intercambio nuevo con la misma pregunta)

**Checkpoint**: US1 funcional en modo literal contra la API local o de producción.

---

## Phase 4: User Story 2 - Elegir una respuesta con razonamiento (Priority: P1)

**Goal**: elegir el modo antes de preguntar y recibir respuestas con razonamiento con las dos partes fijas.

**Independent Test**: en Computación, modo con razonamiento, la pregunta de créditos de Sistemas Operativos Avanzados, Análisis de Algoritmos y Diseño de Experimentos responde 12 con el dato de cada curso y los tres programas citados.

### Tests for User Story 2

- [X] T027 [P] [US2] Crear `web/consulta/src/state/modes.ts` vacío con su firma y `web/consulta/src/state/modes.test.ts`: `resolveAvailability(config, savedMode)` devuelve los modos visibles (los de `config.modes`, que ya son los permitidos), si se muestra el selector (más de uno visible), el modo efectivo (el guardado si está disponible; si no, el primero disponible, con `changed: true` para avisar) y `null` si ninguno está disponible; `loadMode`/`saveMode` con `localStorage` bajo `mia-consulta-modo` dentro de `try/catch`

### Implementation for User Story 2

- [X] T028 [US2] Implementar `web/consulta/src/state/modes.ts` hasta pasar T027
- [X] T029 [US2] Crear `web/consulta/src/components/ModePicker.tsx`: solo si hay más de un modo visible; cada opción con `name` y `description`; un modo no disponible deshabilitado con su `reason`; el elegido se guarda; si el modo guardado cambió por no estar disponible, un aviso breve (FR-007, FR-008)
- [X] T030 [US2] Usar el modo efectivo en `web/consulta/src/App.tsx` al enviar; en `Exchange.tsx`, en modo con razonamiento el aviso de espera "El modo con razonamiento puede tardar más de un minuto." y, en cada respuesta, el pie con el nombre del modo y el tiempo (`latency_ms` en segundos con una cifra decimal bajo 10 s y sin decimales desde 10 s, p. ej. "Literal · 3,2 s", "Con razonamiento · 41 s") (FR-015)
- [X] T031 [US2] Validar el criterio 7 contra una API con el modo con razonamiento configurado (local con OpenRouter o producción): la pregunta de créditos responde 12 con las dos partes y cita los tres programas; si no, ajustar `REASONING_SYSTEM_PROMPT` o `QUERY_SEARCH_LIMIT_RAZONAMIENTO` y anotar el resultado y los ajustes en el mensaje del commit

**Checkpoint**: US1 y US2 funcionan: la Consulta pregunta en ambos modos.

---

## Phase 5: User Story 3 - Saber por qué no puedo preguntar y recuperarme de un error (Priority: P2)

**Goal**: motivos claros cuando un modo o el envío no están disponibles, y salidas ante errores.

**Independent Test**: con un tope de razonamiento bajo en un artefacto de prueba, al alcanzarlo la opción queda deshabilitada con su motivo y el literal sigue; al subir el tope, la siguiente funciona.

### Tests for User Story 3

- [X] T032 [P] [US3] Ampliar `web/consulta/src/state/modes.test.ts`: `resolveAvailability` marca `sendBlocked` con el motivo cuando `caps.cap_reached` o `caps.global_cap_reached`; y crear `web/consulta/src/state/errors.test.ts` con `describeError(error, mode)`: devuelve mensaje, si se puede reintentar y si se ofrece "Reintentar en modo literal", para sin conexión (status 0), tiempo agotado (-1), 502, 429, 403 por desactivado (detail "Este artefacto está desactivado.") y 403 por permisos, según la tabla de errores de `contracts/ui-consulta.md`; la opción de literal solo en modo `razonamiento`

### Implementation for User Story 3

- [X] T033 [US3] Completar `sendBlocked` en `web/consulta/src/state/modes.ts` y crear `web/consulta/src/state/errors.ts` hasta pasar T032
- [X] T034 [US3] En `web/consulta/src/components/Composer.tsx` y `App.tsx`: si `sendBlocked`, deshabilitar el envío mostrando solo el `reason` que da `/config` (ya incluye "Se reinicia a la medianoche."; no agregarlo otra vez) (FR-009); si el modo efectivo es `null`, el `reason` del modo
- [X] T035 [US3] En `web/consulta/src/components/Exchange.tsx`, usar `describeError` para el mensaje y las acciones "Reintentar" y "Reintentar en modo literal" (que crea un intercambio nuevo con la misma pregunta en modo `literal`) (FR-017)
- [X] T036 [US3] En `web/consulta/src/App.tsx`, tras un 403 o 429 de `/query`, invalidar las consultas `["config"]` y `["domains"]` de TanStack Query para refrescar modos, topes y dominios sin recargar (FR-018); tras refrescar, volver a aplicar `restoreSelection` para descartar dominios ya no permitidos

**Checkpoint**: US3 funcional: topes, modos sin configurar, desactivación y errores del proveedor se explican y tienen salida.

---

## Phase 6: User Story 4 - Calificar cada respuesta (Priority: P2)

**Goal**: calificar respuestas como útil o no útil con comentario opcional.

**Independent Test**: calificar una respuesta "No útil" con comentario y verlo en el registro de consultas del panel.

### Implementation for User Story 4

- [X] T037 [US4] Crear `web/consulta/src/components/Rating.tsx` y usarlo en `Exchange.tsx` para intercambios `answered` y `no_info` (no en `failed`): botones "Útil" y "No útil" que envían `{"rating": "util" | "no_util"}` con `useFeedback`; al elegir, aparece un campo de comentario opcional con "Enviar comentario" que reenvía la calificación con el comentario; la elegida queda marcada y se puede cambiar (reemplaza a la anterior); ante error, un mensaje breve y la posibilidad de reintentar (FR-022)

**Checkpoint**: US4 funcional: la calificación llega al registro del panel.

---

## Phase 7: User Story 5 - Dos instancias publicadas de la misma Consulta (Priority: P3)

**Goal**: publicar la misma compilación en dos direcciones y retirar el cliente anterior.

**Independent Test**: cada dirección abre con su clave, muestra su nombre y solo sus dominios; un dominio nuevo en Computación aparece al recargar la instancia de Computación y no en la de Administración de Empresas.

### Implementation for User Story 5

- [X] T038 [US5] Eliminar el cliente anterior: `web/index.html`, `web/src/`, `web/package.json`, `web/package-lock.json`, `web/tsconfig.json`, `web/vite.config.ts` y `web/dist/` si existe; reemplazar `web/README.md` por uno breve que presenta `admin/` (panel de administración) y `consulta/` (Consulta administrativa) con enlaces a sus README (FR-024)
- [X] T039 [P] [US5] Crear `web/consulta/README.md`: uso (`npm install`, `npm run dev` en el puerto 3000, `MIA_API_URL`), estructura de carpetas, qué se guarda en el navegador (clave, dominios y modo; nunca la conversación), y cómo se publica (compilación con `VITE_API_URL`, una dirección por instancia, `CORS_ORIGINS` en la API)
- [X] T040 [US5] Agregar a `docs/OPERACION.md` una sección "Consulta administrativa": publicar dos sitios estáticos en Render desde `web/consulta` (`rootDir: web/consulta`, build `npm ci && npm run build`, publish `dist`, variable `VITE_API_URL` con la URL de Railway, nombres sugeridos `mia-computacion` y `mia-administracion`), agregar ambas direcciones a `CORS_ORIGINS` en Railway (separadas por coma, sin barra final), registrar o reutilizar los dos artefactos en el panel y entregar a cada equipo su enlace y su clave; agregar `QUERY_SEARCH_LIMIT_RAZONAMIENTO` a la tabla de variables; reemplazar las menciones del cliente anterior por la Consulta

**Checkpoint**: las cinco historias funcionan; el cliente anterior ya no existe.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: documentación viva y validación final.

- [X] T041 [P] Actualizar `README.md`: reemplazar el punto "Cliente web tipo chat (transitorio)" por la Consulta administrativa (`cd web/consulta && npm install && npm run dev`, puerto 3000, clave de artefacto) y agregar `cd web/consulta && npm test` a la lista de pruebas
- [X] T042 [P] Actualizar `docs/ARQUITECTURA.md`, además de lo que ya agregó T013 sobre los modos (artefactos de consulta: la Consulta en `web/consulta/`, una compilación y dos publicaciones, qué guarda en el navegador; retirar el cliente anterior) y `docs/PRUEBAS_MVP.md` y `docs/ESCALABILIDAD.md` donde describen el cliente actual como vigente (no tocar los registros históricos)
- [X] T043 Correr la validación de [quickstart.md](quickstart.md) (pasos 1 a 9 y 11 en local o contra producción con artefactos de prueba; el paso 10 de publicación queda para quien administra MIA) más una prueba de SC-001 (una persona que no conoce la Consulta recibe el enlace y la clave y hace su primera pregunta; cronometrar, meta menos de 2 minutos, y anotar el tiempo o marcarlo pendiente para la evaluación con usuarios), y anotar los resultados en una sección "Resultados de la validación" al final de `quickstart.md`, marcando lo que quede pendiente
- [X] T044 Correr `python scripts/pruebas_mvp.py --url <api> --clave mia_...` (19 de 19 en literal) y con `--modo razonamiento` (informativo); anotar ambos resultados en `docs/PRUEBAS_MVP.md`
- [X] T045 Verificar que no haya guion largo en ningún archivo nuevo o modificado (`grep -rnP "\x{2014}" src tests scripts web/consulta/src web/README.md web/consulta/README.md docs README.md specs/003-consulta-administrativa`)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias. La parte de API (T006 a T013) y la base de la Consulta (T014 a T017) pueden avanzar en paralelo.
- **US1 (Phase 3)**: depende de Foundational.
- **US2 (Phase 4)**: depende de US1 (usa la conversación y el envío) y de la parte de API de Foundational.
- **US3 (Phase 5)**: depende de US2 (usa la disponibilidad de modos).
- **US4 (Phase 6)**: depende de US1 (usa `Exchange`); independiente de US2 y US3.
- **US5 (Phase 7)**: depende de US1 como mínimo; conviene al final.
- **Polish (Phase 8)**: depende de las historias que se entreguen.

### User Story Dependencies

```text
Setup → Foundational → US1 → US2 → US3
                          └──→ US4
                          └──→ US5 (al final)
```

### Within Each User Story

- Pruebas primero (deben fallar), después funciones puras (`format/`, `state/`), después componentes, después integración en `App.tsx`.
- Commit al terminar cada tarea o grupo lógico, en `dev`.

### Parallel Opportunities

- Setup: T002 a T005 en paralelo tras T001.
- Foundational: pruebas T006 a T008 en paralelo; T014 en paralelo con la parte de API.
- US1: T018 a T020 en paralelo.
- US4 puede avanzar en paralelo con US2 y US3 una vez terminada US1.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo:
Task: "web/consulta/src/format/formatAnswer.test.ts"
Task: "web/consulta/src/state/domains.test.ts"
Task: "web/consulta/src/state/sources.test.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 y Phase 2.
2. Phase 3 (US1): la Consulta en modo literal.
3. **Parar y validar**: preguntar en Computación y en Administración de Empresas con sus claves.

### Incremental Delivery

1. Setup + Foundational: la API ya responde por modo (desplegable sin romper nada).
2. US1 y US2: la Consulta pregunta en ambos modos; validar el criterio 7.
3. US3 y US4: errores, topes y calificación; ya sirve para la evaluación con usuarios.
4. US5 y Polish: retirar el cliente anterior, documentar la publicación.

Como Railway despliega desde `main` y todo se trabaja en `dev`, cada historia se valida en local; el usuario decide cuándo hacer el merge y cuándo publicar los dos sitios.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- Cada historia se puede completar y probar sola en su checkpoint.
- No se cambia el esquema de la base ni el pipeline de ingesta.
- Publicar los sitios en Render y cambiar `CORS_ORIGINS` en Railway lo hace el usuario.

---

## Phase 9: Convergence

**Purpose**: cerrar los vacíos que /speckit-converge encontró entre el código y la especificación.

- [X] T046 Deshabilitar "Reintentar" y "Reintentar en modo literal" de `web/consulta/src/components/Exchange.tsx` (propiedad nueva `busy` pasada desde `App.tsx` por `Conversation.tsx`) mientras haya una consulta en curso, para que no se pueda enviar una segunda pregunta en paralelo desde un intercambio fallido anterior, per FR-019 (partial)
- [X] T047 Conservar lo escrito cuando la API rechaza la pregunta con 422: `web/consulta/src/components/Composer.tsx` debe vaciar el campo solo cuando el envío no es rechazado (por ejemplo, `onSend` devuelve una promesa o `App.tsx` devuelve el texto al campo tras el 422) y agregar una prueba de la regla en `web/consulta/src/state/`, per Edge Cases del spec y contracts/ui-consulta.md, fila 422 (partial)
- [X] T048 Distinguir "nunca se guardó una selección" de "se eligió ninguno" en `web/consulta/src/state/domains.ts`: `loadSelection` devuelve `null` si no hay nada guardado y `restoreSelection` solo selecciona todos en ese caso (con una lista guardada vacía queda en ninguno; con una lista cuyos dominios ya no están permitidos, sigue seleccionando todos); actualizar `domains.test.ts` y el uso en `App.tsx`, per FR-006 (partial)
- [X] T049 Mostrar en `web/consulta/src/components/Conversation.tsx` ejemplos de preguntas distintos para cada modo (uno literal sobre un dato exacto y uno con razonamiento sobre una suma o comparación), según el modo elegido, con texto fijo que no se envía, per contracts/ui-consulta.md, "Área de conversación vacía" (partial)
