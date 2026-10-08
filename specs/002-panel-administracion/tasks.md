---

description: "Tareas de implementación del Panel de administración de MIA"
---

# Tasks: Panel de administración de MIA

**Input**: Design documents from `specs/002-panel-administracion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-037 exige pruebas automáticas para cada operación nueva o modificada de la API. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US5 de spec.md), en orden de prioridad.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US5)

## Reglas para quien implemente

- Trabajar en la rama `dev`. Nunca hacer merge a `main` (lo hace el usuario).
- Todo texto (código, comentarios, mensajes de error, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Ver `CLAUDE.md`.
- Mensajes de error de la API en español, con la forma `{"detail": "..."}`.
- Seguir el estilo del código existente (comentarios breves que explican el porqué, nombres en inglés en el código y conceptos de dominio en español en textos).
- Después de cada fase: `pytest` y `ruff check src tests scripts` en verde.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencias, configuración y esqueletos.

- [X] T001 Agregar `alembic>=1.13` y `tzdata>=2024.1` a `dependencies` en `pyproject.toml` y reinstalar (`pip install -e ".[dev]"`)
- [X] T002 Agregar a `Settings` en `src/mia/config.py`: `admin_key: str = ""`, `daily_cap_usd: float = 3.0`, `cap_timezone: str = "America/Costa_Rica"`, `cors_origins: str = ""` (lista separada por comas), `max_upload_mb: int = 25`, `openrouter_management_key: str = ""`, y por cada modo (`literal`, `razonamiento`) `llm_provider_<modo>: str = ""`, `llm_model_<modo>: str = ""`, `llm_reasoning_effort_<modo>: str = ""`, `llm_price_in_<modo>: float = 0.0`, `llm_price_out_<modo>: float = 0.0` (USD por millón de tokens), con comentarios breves como los existentes (ver data-model.md, "Configuración nueva de la instancia")
- [X] T003 [P] Documentar las variables nuevas de T002 en `.env.example`, agrupadas y comentadas como las existentes (incluir que `OPENROUTER_MANAGEMENT_KEY` es opcional y no recomendada en producción, research decisión 7)
- [X] T004 [P] Crear el proyecto Vite del panel en `web/admin/`: `package.json` (nombre `mia-admin`, scripts `dev`, `build` = `tsc && vite build`, `typecheck`, `test` = `vitest run`, `preview`), dependencias `react@^19`, `react-dom@^19`, `react-router-dom@^7`, `@tanstack/react-query@^5`, `recharts`, y de desarrollo `typescript@^5.6`, `vite@^6`, `@vitejs/plugin-react`, `@types/react`, `@types/react-dom`, `vitest`; `tsconfig.json` estricto; `index.html` con `<title>MIA: Panel de administración</title>` y `lang="es"`
- [X] T005 [P] Crear `web/admin/vite.config.ts` con el plugin de React, puerto 3001 (`strictPort`) y proxy `/api` hacia `process.env.MIA_API_URL ?? "http://localhost:8000"` reescribiendo el prefijo, con timeout de 200 s, igual que `web/vite.config.ts`
- [X] T006 [P] Crear `web/admin/README.md` con uso (`npm install`, `npm run dev`, `MIA_API_URL`), estructura de carpetas y cómo se publica como sitio estático (requiere `CORS_ORIGINS` en la API)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: esquema, migraciones, seguridad y base del panel que necesitan todas las historias.

**⚠️ CRITICAL**: ninguna historia puede empezar hasta terminar esta fase.

### Modelos y migraciones

- [X] T007 Agregar a `src/mia/storage/models.py` los modelos nuevos según data-model.md: `Unit` (`units`: id, name "obligatorio, único", description por defecto "", created_at), `Folder` (`folders`: id, domain_id FK obligatorio, parent_id FK a `folders.id` "nulo si está en la raíz del dominio", name, created_at), `Artifact` (`artifacts`: id, name único, description, key_hash "único e indexado", key_prefix, active por defecto verdadero, all_domains por defecto falso, modes texto "lista separada por comas de literal y razonamiento", daily_cap_usd `Numeric(10,4)` por defecto 0.50, reasoning_daily_cap_usd opcional, created_at, updated_at), `ArtifactUnit` (`artifact_units`, PK compuesta artifact_id + unit_id), `ArtifactDomain` (`artifact_domains`, PK compuesta artifact_id + domain_id) y `QueryLog` (`queries`: todos los campos de data-model.md, con `domain_ids` y `sources` como texto JSON, índice compuesto `(artifact_id, created_at)`); y en los existentes: `Domain.unit_id` FK nullable a `units.id`, `Domain.name` sin `unique=True` y con `UniqueConstraint("unit_id", "name")`, `Document.folder_id` FK nullable a `folders.id`. Agregar una `naming_convention` a `Base.metadata` (ix, uq, ck, fk, pk) para que las migraciones tengan nombres estables
- [X] T008 Crear `alembic.ini` en la raíz (con `script_location = src/mia/storage/migrations`) y `src/mia/storage/migrations/env.py` que tome la URL de `mia.config.settings.database_url` normalizada con `_normalize_url` de `src/mia/storage/db.py`, use `target_metadata = Base.metadata` y `render_as_batch=True` (necesario para SQLite)
- [X] T009 Crear `src/mia/storage/migrations/versions/0001_esquema_inicial.py` con el esquema actual exacto que genera hoy `create_all` (tablas `domains` con `name` único y `documents`, ver `git show main:src/mia/storage/models.py`), para poder marcar con `stamp` las bases existentes
- [X] T010 Crear `src/mia/storage/migrations/versions/0002_panel_administracion.py`: crea `units`, `folders`, `artifacts`, `artifact_units`, `artifact_domains`, `queries`; agrega `domains.unit_id` (nullable) y `documents.folder_id` (nullable); reemplaza la unicidad de `domains.name` por `(unit_id, name)` usando `batch_alter_table`. En Postgres la restricción existente se llama `domains_name_key` (nombre por defecto de `create_all`); en SQLite el modo batch recrea la tabla. Incluir `downgrade` simétrico
- [X] T011 Reescribir `init_db()` en `src/mia/storage/db.py`: si la base tiene la tabla `domains` pero no `alembic_version`, ejecutar `alembic stamp 0001`; después `alembic upgrade head` (vía `alembic.command` con un `Config` armado en código que apunte a `alembic.ini` del paquete o a `script_location` absoluto, para que funcione también dentro del contenedor). Mantener un comentario que explique el stamp automático (research decisión 1). Verificar que `Dockerfile` copie lo necesario (si `alembic.ini` está en la raíz, copiarlo o definir el `Config` sin archivo)
- [X] T012 Actualizar `tests/conftest.py` y los tests que crean bases con `Base.metadata.create_all` (`tests/unit/test_query_sources.py`, `tests/unit/test_query_no_info.py` y los que correspondan) para que sigan funcionando con los modelos nuevos
- [X] T013 [P] Crear `tests/unit/test_migrations.py`: (a) una base SQLite creada con el esquema de `0001` y datos (un dominio y un documento) se migra con `init_db()` sin perder datos y queda en la última revisión; (b) una base vacía queda en la última revisión; (c) correr `init_db()` dos veces no falla

### Seguridad y API común

- [X] T014 Crear `src/mia/access/__init__.py` y `src/mia/access/keys.py` con `generate_key() -> str` (`"mia_" + secrets.token_urlsafe(32)`), `hash_key(key) -> str` (SHA-256 hex), `key_prefix(key) -> str` (primeros 8 caracteres) y `admin_key_matches(given) -> bool` con `hmac.compare_digest` contra `settings.admin_key` (research decisión 3)
- [X] T015 Crear `src/mia/api/security.py` con la dependencia `require_admin` (lee `X-Admin-Key`; 503 `"La instancia no tiene configurada la clave de administración (ADMIN_KEY)."` si `settings.admin_key` está vacía; 401 `"Clave de administración inválida."` si no coincide) y `optional_artifact` / `require_artifact` (leen `X-Artifact-Key`, buscan el `Artifact` por `hash_key`; `require_artifact` responde 401 `"Clave de artefacto inválida."` si falta o no existe; no verifican `active`, eso lo hace cada ruta para poder registrar el rechazo)
- [X] T016 Agregar `CORSMiddleware` en `src/mia/api/main.py` con los orígenes de `settings.cors_origins` (separados por comas, ignorando vacíos), métodos GET, POST, PATCH, DELETE y encabezados `content-type`, `X-Admin-Key`, `X-Artifact-Key`; exponer el encabezado `Retry-After`
- [X] T017 [P] Crear `tests/unit/test_security.py`: 503 sin `ADMIN_KEY`, 401 con clave incorrecta, acceso con la correcta (usar una ruta de prueba o `POST /units` cuando exista); `require_artifact` con clave inexistente da 401; `generate_key` empieza con `mia_` y su hash es estable

### Base del panel

- [X] T018 [P] Crear `web/admin/src/styles/tokens.css` y `web/admin/src/styles/base.css`: variables de color en `:root` con modo oscuro bajo `@media (prefers-color-scheme: dark)`, incluido un color propio de administración (violeta, como `--admin` en `docs/MIA_conceptual.html`), tipografía del sistema, diseño utilizable en celular (sin desplazamiento horizontal)
- [X] T019 Crear `web/admin/src/api/client.ts`: función `apiFetch<T>(path, init)` sobre `/api`, que agrega `X-Admin-Key` si hay clave guardada, parsea JSON, y lanza un `ApiError` con `status` y `detail`; ante 401 en una operación de administración, borra la clave guardada (caso borde del spec) y notifica para volver a pedirla. Guardado de la clave en `localStorage` con lectura y escritura dentro de `try/catch`
- [X] T020 Crear `web/admin/src/api/types.ts` con los tipos de los contratos (`Inventory`, `Unit`, `DomainNode`, `FolderNode`, `DocumentItem`, `Artifact`, `ArtifactsResponse`, `ConfigResponse`, `UsageResponse`, `QueryLogItem`, `QueryLogDetail`, `BalanceResponse`) según `contracts/*.md`
- [X] T021 Crear `web/admin/src/main.tsx` y `web/admin/src/App.tsx`: `QueryClientProvider`, `HashRouter` con rutas `#/inventario` (por defecto), `#/artefactos` y `#/uso`; `web/admin/src/components/Layout.tsx` con menú lateral (desplegable en pantallas angostas, ADM-2) donde Artefactos y Uso aparecen deshabilitados sin clave (ADM-1); `web/admin/src/components/AdminKeyDialog.tsx` para ingresar y olvidar la clave; cada módulo registrado en un arreglo `MODULES` para que agregar uno sea sumar una entrada (ADM-3)

**Checkpoint**: migraciones aplicadas, seguridad lista, panel con menú vacío. `pytest` en verde.

---

## Phase 3: User Story 1 - Ver la información organizada por unidad académica (Priority: P1) 🎯 MVP

**Goal**: el inventario completo en un árbol unidades > dominios > carpetas > documentos, con los datos actuales ya reorganizados sin reprocesar.

**Independent Test**: tras la reorganización, el árbol coincide con la tabla de la sección 2.3 de `docs/Definicion_Requerimientos_V2.md`, los 162 documentos siguen en `done`, y "Proyectos de graduación: Tesis" cita solo tesis.

### Tests for User Story 1

- [X] T022 [P] [US1] Crear `tests/unit/test_inventory.py`: `GET /inventory` sin clave devuelve unidades con dominios, carpetas anidadas y documentos según `contracts/api-inventario.md`; `document_count` acumula lo de carpetas internas; dominios sin unidad salen en `unassigned_domains`; `ingestion_enabled` refleja la configuración; `GET /units` lista unidades
- [X] T023 [P] [US1] Crear `tests/unit/test_reorganizacion.py` con una base SQLite y un `VectorStore` falso: aplicar el mapeo a cinco dominios con los nombres actuales deja la estructura esperada, llama a `set_domain` solo para los documentos que cambian de dominio, no cambia `status` de ningún documento, y una segunda corrida no produce cambios; `--simular` no escribe nada

### Implementation for User Story 1

- [X] T024 [US1] Agregar `set_domain(document_id: str, domain_id: str) -> None` a la interfaz `VectorStore` y a `QdrantVectorStore` en `src/mia/storage/vector_store.py`, usando `client.set_payload(collection, payload={"domain": domain_id}, points=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]))`
- [X] T025 [US1] Crear `src/mia/api/routes/inventory.py` con `GET /inventory` (una sola lectura de unidades, dominios, carpetas y documentos, armando el árbol en memoria; `document_count` acumulado; orden alfabético) y `GET /units`; registrar el router en `src/mia/api/main.py`
- [X] T026 [P] [US1] Crear `scripts/datos/reorganizacion_v2.json` con el mapeo de la sección 2.3 y el anexo A de `docs/Definicion_Requerimientos_V2.md`: unidades (`Computación`, `Administración de Empresas`) con descripción; por cada dominio actual (`Computación: Consejo de Unidad`, `Computación: Planes de estudio`, `Computación: Proyectos de graduación`, `Analítica de Negocios: Consejo de Área`, `Analítica de Negocios: Currículum`) su unidad, nombre nuevo, carpeta de origen en `tmp/` y regla de carpetas (replicar la estructura de subcarpetas del origen, con los nombres de carpeta legibles de la tabla 2.3: `Actas`, `Programas de curso`, `Documento constitutivo del programa`, `Líneas de trabajos finales de graduación`, `Reglamentos`); la clasificación de los 30 proyectos del anexo A en los tres dominios nuevos; y los dominios vacíos a crear (`Apertura de promoción`, `Docentes` en ambas unidades)
- [X] T027 [US1] Crear `scripts/reorganizar_v2.py` (con `argparse`, `--simular`, `--env-file`) que use `SessionLocal` y `get_vector_store()` de la API: crea unidades, dominios y carpetas que falten (buscando por nombre, idempotente); renombra y asigna unidad a los dominios actuales; ubica cada documento en su carpeta buscando su `filename` en la carpeta de origen; mueve los proyectos de graduación a su dominio nuevo (`document.domain_id` y `set_domain` en Qdrant); no toca `status` ni reprocesa; imprime un resumen por unidad, dominio y carpeta con cantidades y lista los documentos que no pudo ubicar. Docstring de uso como en `scripts/cargar_carpeta.py`
- [X] T028 [P] [US1] Crear `web/admin/src/api/inventory.ts` con hooks de TanStack Query `useInventory()` y `useUnits()`
- [X] T029 [P] [US1] Crear `web/admin/src/modules/inventario/filterTree.ts` (función pura que filtra el árbol por texto sin distinguir mayúsculas ni tildes, conservando las ramas que contienen coincidencias, INV-9) y `web/admin/src/modules/inventario/filterTree.test.ts` (Vitest)
- [X] T030 [US1] Crear `web/admin/src/modules/inventario/InventarioPage.tsx` y `web/admin/src/modules/inventario/TreeNode.tsx`: árbol con unidades abiertas y dominios contraídos al abrir (INV-2), expandir y contraer, descripción y cantidad de documentos por unidad, dominio y carpeta, y por documento su tipo, fecha de carga y estado con etiqueta en español (en cola, procesando, listo, error) (INV-1); buscador (INV-9); sección "Sin unidad" si hay `unassigned_domains`
- [X] T031 [US1] Probar la reorganización en local antes de producción: con SQLite y Qdrant locales, cargar con `scripts/cargar_carpeta.py` una muestra (2 o 3 archivos de cada carpeta de origen, incluidos al menos un proyecto de cada tipo del anexo A) en dominios con los nombres actuales; correr `python scripts/reorganizar_v2.py --simular`, luego sin `--simular`, luego otra vez (debe informar sin cambios); verificar en `GET /inventory` la estructura y que los proyectos movidos aparecen al consultar su dominio nuevo. Anotar el resultado en el mensaje del commit

**Checkpoint**: US1 funcional: árbol completo en el panel y reorganización probada en local.

---

## Phase 4: User Story 2 - Agregar unidades, dominios, carpetas y documentos (Priority: P1)

**Goal**: reemplazar Swagger y los scripts para cargar información.

**Independent Test**: con la clave de administración, crear un dominio, una carpeta, subir dos documentos a la carpeta y verlos llegar a "listo"; una pregunta sobre ellos los cita.

### Tests for User Story 2

- [ ] T032 [P] [US2] Crear `tests/unit/test_units_domains.py`: `POST /units` (201, 409 nombre repetido, 422 vacío, 401 sin clave); `POST /domains` exige `unit_id` (404 unidad inexistente, 409 nombre repetido en la unidad, 201 con el mismo nombre en otra unidad) y devuelve `visible_to` con `now` y `needs_enabling` según los artefactos (crear artefactos directamente en la base)
- [ ] T033 [P] [US2] Crear `tests/unit/test_folders.py`: crear en la raíz y anidada (201), 409 nombre repetido en el mismo nivel (incluida la raíz, donde `parent_id` es nulo), 422 carpeta padre de otro dominio, `PATCH` renombra (409 si choca), `DELETE` 204 vacía y 409 con documentos o subcarpetas
- [ ] T034 [P] [US2] Ampliar `tests/unit/test_ingestion_disabled.py` o crear `tests/unit/test_upload.py`: la subida exige clave (401), acepta `folder_id` (404 inexistente, 422 de otro dominio), rechaza tipos no soportados (400) y archivos mayores a `MAX_UPLOAD_MB` (413), devuelve `already_existed: true` y 200 si el contenido ya estaba en el dominio en otra carpeta, 201 si es nuevo

### Implementation for User Story 2

- [ ] T035 [US2] Agregar a `src/mia/api/routes/inventory.py`: `POST /units`, `POST /domains/{domain_id}/folders`, `PATCH /folders/{folder_id}` y `DELETE /folders/{folder_id}` con `require_admin`, validaciones y mensajes de `contracts/api-inventario.md` (verificar la unicidad de carpetas en la API, porque `NULL` en `parent_id` no participa de la restricción única)
- [ ] T036 [US2] Modificar `src/mia/api/routes/domains.py`: `POST /domains` con `require_admin`, `unit_id` obligatorio, 409 por nombre repetido en la unidad y respuesta con `visible_to` (activos con `all_domains` o con la unidad en `now`; activos con dominios puntuales en `needs_enabling`); `GET /domains` incluye `unit_id` y `unit_name`; `POST /domains/{id}/documents` con `require_admin`, `folder_id` opcional en el formulario, 413 si supera `settings.max_upload_mb`, `already_existed` en la respuesta y código 200 o 201; `GET /domains/{id}/documents` incluye `folder_id`
- [ ] T037 [US2] Actualizar `scripts/cargar_carpeta.py`: argumentos `--clave` (o variable `MIA_ADMIN_KEY`) enviada en `X-Admin-Key`, y `--unidad` (nombre; la crea si no existe) para crear el dominio dentro de esa unidad; actualizar el docstring y los ejemplos
- [ ] T038 [P] [US2] Crear `web/admin/src/api/inventoryMutations.ts` con mutaciones `useCreateUnit`, `useCreateDomain`, `useCreateFolder`, `useRenameFolder`, `useDeleteFolder` y `useUploadDocument` (multipart con `folder_id`), que invalidan `inventory` al terminar
- [ ] T039 [US2] Crear `web/admin/src/modules/inventario/forms/` con formularios en diálogo para nueva unidad, nuevo dominio (muestra después el aviso de `visible_to`, INV-12) y nueva carpeta, y acciones de renombrar y borrar carpeta; los errores 409 se muestran sin perder lo escrito (INV-3)
- [ ] T040 [US2] Crear `web/admin/src/modules/inventario/UploadZone.tsx`: elegir archivos o arrastrarlos sobre un dominio o carpeta; rechaza antes de subir lo que no sea `.pdf`, `.docx` o `.txt` y lo que supere `max_upload_mb` de `GET /config`; sube uno a la vez; muestra "ya existía" para `already_existed` (INV-6) y error con opción de reintentar si falla la conexión
- [ ] T041 [US2] Sondear el estado de documentos en proceso: en `InventarioPage.tsx`, mientras haya documentos `pending` o `processing`, refrescar `inventory` cada 5 s (`refetchInterval` condicionado) y detenerse cuando no quede ninguno (INV-5)
- [ ] T042 [US2] Modo solo lectura: si `ingestion_enabled` es falso, deshabilitar subir con el aviso "Esta instancia tiene la carga de documentos desactivada..." (INV-7); sin clave de administración, los botones de crear y subir abren el diálogo de clave (ADM-1)

**Checkpoint**: US1 y US2 funcionan: se puede administrar el inventario sin Swagger.

---

## Phase 5: User Story 3 - Registrar artefactos y definir su acceso (Priority: P2)

**Goal**: varias puertas de consulta con permisos aplicados en la API.

**Independent Test**: un artefacto con un solo dominio y solo modo literal: `GET /domains` y `GET /config` con su clave muestran solo eso, y `/query` a otro dominio o en razonamiento da 403.

### Tests for User Story 3

- [ ] T043 [P] [US3] Crear `tests/unit/test_artifacts.py`: `POST /artifacts` devuelve la clave una sola vez (no aparece en `GET /artifacts`), 409 nombre repetido, 422 sin acceso, sin modos, modo desconocido, tope de razonamiento mayor que el total; `PATCH` cambia acceso, modos, estado; `POST /artifacts/{id}/key` invalida la anterior; todo exige `X-Admin-Key`
- [ ] T044 [P] [US3] Crear `tests/unit/test_permissions.py` (lógica pura de `src/mia/access/permissions.py`): dominios permitidos con `all_domains`, con unidades (incluye un dominio creado después), con dominios puntuales y combinados sin duplicados; artefacto desactivado no tiene acceso
- [ ] T045 [P] [US3] Crear `tests/unit/test_query_access.py` con proveedores falsos: `/query` sin clave 401; clave inválida 401; desactivado 403; dominio no permitido 403; modo no permitido 403; consulta válida registra una fila en `queries` con artefacto, modo, modelo, tokens, costo, `outcome` y `sources`; los 403 se registran como `rejected_permission`; un fallo del proveedor se registra como `error` y responde 502; `POST /query/{id}/feedback` guarda la calificación y da 404 para consultas de otro artefacto
- [ ] T046 [P] [US3] Crear `tests/unit/test_config.py`: `GET /config` sin clave lista ambos modos con `available` y `reason`; con clave de artefacto solo los permitidos y `artifact.name`; un modo sin proveedor configurado figura `available: false`

### Implementation for User Story 3

- [ ] T047 [US3] Cambiar la interfaz de LLM en `src/mia/rag/llm.py`: dataclass `LLMAnswer(text, model, prompt_tokens=None, completion_tokens=None, reasoning_tokens=None, cost_usd=None)`; `LLMProvider.answer()` devuelve `LLMAnswer`; `get_llm_provider(name, model="", reasoning_effort="")` con `lru_cache` por combinación
- [ ] T048 [US3] Actualizar `src/mia/rag/providers/openrouter_llm.py` para recibir `model` y `reasoning_effort` en el constructor (con los valores actuales de `settings` como respaldo) y devolver `LLMAnswer` con `completion.usage.prompt_tokens`, `completion_tokens`, `completion_tokens_details.reasoning_tokens` y `cost` (OpenRouter lo incluye siempre en `usage`; leerlo con `getattr` o `model_extra` porque no es un campo estándar del SDK de OpenAI; research decisión 6)
- [ ] T049 [P] [US3] Actualizar los demás proveedores (`anthropic_llm.py`, `gemini_llm.py`, `glm_llm.py`, `openai_llm.py`, `local_llm.py` en `src/mia/rag/providers/`) para devolver `LLMAnswer` con el modelo y los tokens que su SDK informe (sin costo); actualizar `tests/unit/test_openrouter_llm.py` y `tests/unit/test_glm_llm.py` a la nueva forma
- [ ] T050 [US3] Crear `src/mia/rag/modes.py`: definición de los modos (`literal`: "Literal", descripción "Lo que dice exactamente un documento."; `razonamiento`: "Con razonamiento", "Combina, compara y calcula datos de varios documentos."), resolución de proveedor, modelo, esfuerzo y precios por modo desde `settings` (el literal cae en `llm_provider` y `openrouter_*` si no tiene los suyos; research decisión 5), `mode_available(mode) -> (bool, reason)` y `estimate_cost(mode, prompt_tokens, completion_tokens)` con los precios de respaldo
- [ ] T051 [US3] Crear `src/mia/access/permissions.py`: `allowed_domain_ids(session, artifact) -> set[str]` según data-model.md ("todos los dominios si `all_domains`; si no, los dominios de sus unidades más sus dominios puntuales") y `allowed_modes(artifact) -> list[str]`
- [ ] T052 [US3] Crear `src/mia/api/routes/artifacts.py` según `contracts/api-artefactos.md`: `GET /artifacts` (sin `global` ni `today` todavía si US4 no está, o con valores calculados si ya está), `POST /artifacts` (genera clave con `access/keys.py`, guarda hash y prefijo, tope por defecto 0.50), `PATCH /artifacts/{id}`, `POST /artifacts/{id}/key`; validaciones: "al menos uno" de acceso y de modos, `daily_cap_usd` "mayor que 0", `reasoning_daily_cap_usd` "menor o igual que `daily_cap_usd`", unidades y dominios existentes; registrar el router
- [ ] T053 [US3] Crear `src/mia/api/routes/config.py` con `GET /config` según `contracts/api-consulta.md` (usa `optional_artifact`); registrar el router
- [ ] T054 [US3] Modificar `GET /domains` en `src/mia/api/routes/domains.py`: con `X-Artifact-Key` válida, solo los dominios de `allowed_domain_ids`
- [ ] T055 [US3] Reescribir `src/mia/api/routes/query.py`: `require_artifact`; `QueryRequest.mode` (`literal` por defecto); validación en el orden de `contracts/api-consulta.md` (desactivado, modo, dominios; los topes los agrega US4); proveedor del modo vía `modes.py`; medir `latency_ms`; registrar cada consulta en `QueryLog` (incluidas las rechazadas por permisos con costo 0, y los errores 502), calculando `cost_usd` con el de `LLMAnswer` o con `estimate_cost` y `cost_estimated`; respuesta con `id`, `mode` y `latency_ms`; nueva ruta `POST /query/{query_id}/feedback`
- [ ] T056 [US3] Actualizar `tests/unit/test_query_sources.py` y `tests/unit/test_query_no_info.py` para crear un artefacto con acceso al dominio de prueba y enviar su clave, y para que el proveedor falso devuelva `LLMAnswer`
- [ ] T057 [P] [US3] Actualizar `scripts/pruebas_mvp.py`: `--clave` (o `MIA_ARTIFACT_KEY`) enviada en `X-Artifact-Key`, `--modo` (por defecto `literal`), y las constantes de dominio con los nombres nuevos (`Memoria del Consejo`, `Currículum`, `Proyectos de graduación: Tesis`, etc.), resolviendo cada dominio por unidad y nombre a partir de `GET /domains` (que ahora trae `unit_name`); revisar que los casos de proyectos de graduación apunten al dominio correcto según el anexo A
- [ ] T058 [P] [US3] Actualizar `scripts/cliente.py` (`--clave`) y el cliente web actual (`web/src/api.ts` y `web/src/main.ts`: campo para la clave de artefacto guardada en `localStorage`, enviada en `X-Artifact-Key`; mensaje claro ante 401, 403 y 429); actualizar `web/README.md`
- [ ] T059 [P] [US3] Crear `web/admin/src/api/artifacts.ts` con `useArtifacts`, `useCreateArtifact`, `useUpdateArtifact`, `useRegenerateKey`
- [ ] T060 [US3] Crear `web/admin/src/modules/artefactos/ArtefactosPage.tsx` y `ArtifactCard.tsx`: lista con nombre, descripción, estado, prefijo de la clave, dominios (unidades completas, puntuales o todos) y modos, y consultas de 7 días (ART-1); acciones Editar, Regenerar clave (con confirmación) y Desactivar o Reactivar (ART-6, ART-7)
- [ ] T061 [US3] Crear `web/admin/src/modules/artefactos/ArtifactForm.tsx`: nombre, descripción, selector de acceso (todos los dominios, unidades completas, dominios puntuales agrupados por unidad; ART-3), modos con su costo aproximado (`avg_cost_usd_7d` de `GET /artifacts`, "sin datos" si es nulo; ART-4); validación de al menos un acceso y un modo
- [ ] T062 [US3] Crear `web/admin/src/modules/artefactos/KeyReveal.tsx`: muestra la clave completa una sola vez tras crear o regenerar, con botón para copiar y aviso de que no se volverá a mostrar (ART-2)

**Checkpoint**: US3 funcional. Las consultas exigen clave y respetan los permisos; los scripts y el cliente actual siguen funcionando con una clave.

---

## Phase 6: User Story 4 - Topes de gasto diarios (Priority: P2)

**Goal**: ningún artefacto agota el presupuesto de los demás.

**Independent Test**: con un tope bajo de razonamiento, ese modo da 429 al alcanzarlo y el literal y otros artefactos siguen; al subir el tope en el panel, la consulta siguiente funciona.

### Tests for User Story 4

- [ ] T063 [P] [US4] Crear `tests/unit/test_caps.py` (lógica de `src/mia/access/caps.py`): el inicio del día se calcula en `America/Costa_Rica` (una consulta a las 23:30 del día anterior en Costa Rica no cuenta, aunque en UTC sea el mismo día); sumas de gasto por artefacto, por modo con razonamiento y global; `resets_at` es la medianoche siguiente
- [ ] T064 [P] [US4] Ampliar `tests/unit/test_query_access.py`: con gasto previo registrado, se responde 429 con `Retry-After` en el orden global, total del artefacto, razonamiento del artefacto; el rechazo se registra como `rejected_cap` con `reject_reason`; otro artefacto no se ve afectado; subir el tope con `PATCH` permite la consulta siguiente; `GET /config` refleja `cap_reached`

### Implementation for User Story 4

- [ ] T065 [US4] Crear `src/mia/access/caps.py`: `day_start_utc(now)` y `next_reset_utc(now)` con `zoneinfo.ZoneInfo(settings.cap_timezone)`; `spent_today(session, artifact_id=None, mode=None) -> Decimal` con una consulta SQL de suma sobre `queries` desde el inicio del día; `check_caps(session, artifact, mode) -> CapStatus | None` que devuelve cuál tope se alcanzó (research decisión 8)
- [ ] T066 [US4] Integrar los topes en `src/mia/api/routes/query.py` como paso 5 de la validación (429 con `{"detail": ...}` legible, la hora de reinicio y el encabezado `Retry-After` en segundos) y en `src/mia/api/routes/config.py` (`caps` y modos con `available: false` y `reason` si su tope se alcanzó)
- [ ] T067 [US4] Completar `GET /artifacts` en `src/mia/api/routes/artifacts.py`: `today` por artefacto (gastado total y de razonamiento, topes alcanzados), `queries_last_7_days`, bloque `global` (tope de la API, gastado hoy, suma de topes de artefactos y `caps_exceed_global`) y `avg_cost_usd_7d` por modo (promedio de `cost_usd` de consultas `answered` y `no_info` de los últimos 7 días)
- [ ] T068 [P] [US4] Crear `web/admin/src/modules/artefactos/capMath.ts` (funciones puras: porcentaje del tope usado, consultas aproximadas que alcanza un tope según el costo medio, texto de "se reinicia a medianoche") y `capMath.test.ts`
- [ ] T069 [US4] Agregar topes al panel: en `ArtifactForm.tsx`, campos de tope diario total (obligatorio, 0.50 por defecto) y tope de razonamiento opcional, con "alcanza para unas N consultas" al lado (ART-8); en `ArtifactCard.tsx`, barra de gasto de hoy frente al tope y estado "tope alcanzado" (ART-1, ART-9); en `ArtefactosPage.tsx`, aviso cuando `caps_exceed_global` (ART-10) y el tope de toda la API como dato informativo no editable

**Checkpoint**: US3 y US4 funcionan juntas: accesos y topes por artefacto, aplicados en la API.

---

## Phase 7: User Story 5 - Módulo Uso (Priority: P3)

**Goal**: ver gasto, consultas, tokens y tiempos por artefacto, modo y modelo.

**Independent Test**: tras consultas de dos artefactos, el módulo muestra el gasto y las consultas de cada uno, y el total coincide con OpenRouter con menos de 5 % de diferencia.

### Tests for User Story 5

- [ ] T070 [P] [US5] Crear `tests/unit/test_usage.py` con consultas sembradas en la base: `GET /usage` calcula indicadores, `previous` y `change_pct` (nulo con anterior 0), percentiles 50 y 95 de latencia excluyendo rechazadas, series por hora con `period=today` y por día en los demás, agrupadas por artefacto, modo o modelo; filtros por artefacto y modo; `by_artifact` y `by_model`; todo exige clave de administración
- [ ] T071 [P] [US5] Ampliar `tests/unit/test_usage.py` con `GET /usage/queries` (paginación, filtro `outcome`, CSV sin columna `question` salvo `include_questions=true`) y `GET /usage/queries/{id}` (detalle con pregunta, nombres de dominios, fuentes y comentario)
- [ ] T072 [P] [US5] Crear `tests/unit/test_balance.py` con respuestas de OpenRouter simuladas: solo `limit_remaining` da `source: key_limit`; con clave de gestión toma el menor de los dos e indica cuál limita; sin límite ni clave de gestión da `available: false` con motivo; error de red da `available: false`; `days_left` y `warning` según el gasto de 7 días

### Implementation for User Story 5

- [ ] T073 [US5] Crear `src/mia/usage/__init__.py` y `src/mia/usage/aggregate.py`: resolución del período (`today`, `7d`, `30d`, `custom`) y del período anterior en la zona de los topes; lectura filtrada de `QueryLog`; indicadores, percentiles, series por cubeta y grupo, y tablas por artefacto y por modelo según `contracts/api-uso.md` (research decisión 10)
- [ ] T074 [US5] Crear `src/mia/usage/balance.py`: `GET https://openrouter.ai/api/v1/key` con `settings.openrouter_api_key` (`data.limit_remaining`) y, si hay `settings.openrouter_management_key`, `GET /api/v1/credits` (`total_credits - total_usage`); devuelve la forma de `contracts/api-uso.md` con timeout corto y sin propagar errores (research decisión 7)
- [ ] T075 [US5] Crear `src/mia/api/routes/usage.py` con `GET /usage`, `GET /usage/queries` (JSON y CSV), `GET /usage/queries/{query_id}` y `GET /usage/balance`, todas con `require_admin`; registrar el router
- [ ] T076 [P] [US5] Crear `web/admin/src/api/usage.ts` con `useUsage(filters)`, `useQueryLog(filters, page)`, `useQueryDetail(id)`, `useBalance()` y una función para descargar el CSV
- [ ] T077 [US5] Crear `web/admin/src/modules/uso/UsoPage.tsx` y `Filters.tsx`: selector de período (hoy, 7 días, 30 días, rango) y filtros por artefacto y modo que controlan todo el módulo (USO-1)
- [ ] T078 [P] [US5] Crear `web/admin/src/modules/uso/KpiRow.tsx`: tarjetas de gasto, consultas, tokens (con desglose de entrada, salida y razonamiento), costo medio, tiempo (mediana y 95 %), sin información, errores y útiles, cada una con su variación frente al período anterior (USO-2)
- [ ] T079 [P] [US5] Crear `web/admin/src/modules/uso/UsageChart.tsx` con Recharts: barras apiladas por hora o por día, selector de métrica (gasto, consultas, tokens) y de desglose (artefacto, modo, modelo), colores consistentes por grupo, legibles en modo claro y oscuro (USO-3)
- [ ] T080 [P] [US5] Crear `web/admin/src/modules/uso/Tables.tsx`: tabla por artefacto con barra del gasto de hoy frente al tope y enlace a su configuración, y tabla por modelo (USO-4, USO-5)
- [ ] T081 [US5] Crear `web/admin/src/modules/uso/QueryLog.tsx` y `QueryDetail.tsx`: registro paginado con fecha, artefacto, modo, modelo, tokens, costo (marcar si es estimado), tiempo, resultado en español (respondida, sin información, error, rechazada por tope o por permisos, con su motivo) y calificación; detalle con pregunta, dominios, documentos citados y comentario (USO-6); botón de descarga CSV con casilla "incluir preguntas" desmarcada por defecto (USO-8)
- [ ] T082 [US5] Crear `web/admin/src/modules/uso/BalanceCard.tsx`: "Límite restante de la clave de MIA" o el saldo menor con cuál limita, días que alcanza, aviso si son menos de 7, nota de que el saldo de la cuenta puede ser menor cuando la fuente es solo el límite de la clave, y el motivo si no está disponible (USO-7)

**Checkpoint**: las cinco historias funcionan.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: documentación viva, puesta en marcha y validación final.

- [ ] T083 [P] Actualizar `docs/ARQUITECTURA.md`: unidades, carpetas, artefactos y registro de consultas en el modelo de datos; Alembic y el arranque con stamp automático; claves y permisos; modos por proveedor; topes; módulo Uso; panel en `web/admin/`
- [ ] T084 [P] Actualizar `docs/OPERACION.md`: variables nuevas (tabla de variables por entorno), cómo correr la reorganización en local contra producción, cómo registrar las dos instancias de la Consulta administrativa, cómo publicar el panel como sitio estático y configurar `CORS_ORIGINS`, y la recomendación de ajustar el límite de la clave de OpenRouter al saldo cargado
- [ ] T085 [P] Actualizar `docs/PRUEBAS_MVP.md` con los dominios nuevos y el uso de `--clave` en `scripts/pruebas_mvp.py`
- [ ] T086 Revisar el rendimiento de `GET /inventory` con los 162 documentos (menos de 3 s con la API activa, SC-008) y del control de permisos y topes (menos de 50 ms por consulta); si hace falta, agregar índices en una migración nueva
- [ ] T087 Correr la validación completa de [quickstart.md](quickstart.md) en local (pasos 1 a 7) y anotar los resultados
- [ ] T088 Verificar que no haya guion largo en ningún archivo nuevo o modificado (`grep -rnP "\x{2014}" src tests scripts web/admin docs specs/002-panel-administracion`)
- [ ] T089 Preparar la puesta en producción en un checklist dentro de `docs/OPERACION.md` (sin ejecutarlo; lo hace el usuario): configurar `ADMIN_KEY`, `DAILY_CAP_USD` y los modelos por modo en Railway; hacer el merge de `dev` a `main` (migraciones al arrancar); correr `scripts/reorganizar_v2.py --simular` y luego sin simular en local contra producción; registrar las dos instancias de la Consulta administrativa desde el panel; actualizar las claves de los clientes; correr `scripts/pruebas_mvp.py` (19 de 19 en literal)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias.
- **US1 (Phase 3)**: depende de Foundational.
- **US2 (Phase 4)**: depende de Foundational; usa el árbol de US1 en el panel (T030) para ubicar formularios y subida.
- **US3 (Phase 5)**: depende de Foundational y de las unidades de US1 (acceso por unidad). Es independiente de US2.
- **US4 (Phase 6)**: depende de US3 (artefactos y registro de consultas).
- **US5 (Phase 7)**: depende de US3 (registro de consultas); usa los topes de US4 en la tabla por artefacto.
- **Polish (Phase 8)**: depende de las historias que se entreguen.

### User Story Dependencies

```text
Setup → Foundational → US1 → US2
                        └──→ US3 → US4 → US5
```

### Within Each User Story

- Pruebas primero (deben fallar), después lógica sin HTTP (`access/`, `usage/`), después rutas, después panel.
- Commit al terminar cada tarea o grupo lógico, en `dev`.

### Parallel Opportunities

- Setup: T003 a T006 en paralelo tras T001 y T002.
- Foundational: T013, T017 y T018 en paralelo con el resto una vez hechos los modelos (T007).
- En cada historia, las pruebas marcadas [P] en paralelo, y las tareas del panel [P] en paralelo con las de la API.
- US2 y US3 pueden avanzar en paralelo una vez terminada US1.

---

## Parallel Example: User Story 3

```bash
# Pruebas de US3 en paralelo:
Task: "tests/unit/test_artifacts.py"
Task: "tests/unit/test_permissions.py"
Task: "tests/unit/test_query_access.py"
Task: "tests/unit/test_config.py"

# Proveedores y scripts en paralelo con las rutas:
Task: "T049 actualizar los demás proveedores a LLMAnswer"
Task: "T057 scripts/pruebas_mvp.py con --clave"
Task: "T058 scripts/cliente.py y web/ con clave de artefacto"
Task: "T059 web/admin/src/api/artifacts.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 y Phase 2.
2. Phase 3 (US1): árbol en el panel y reorganización probada en local.
3. **Parar y validar**: el árbol coincide con la tabla 2.3 y los documentos siguen listos.

### Incremental Delivery

1. Setup + Foundational.
2. US1, después US2: el panel ya reemplaza Swagger para el inventario.
3. US3 y US4: accesos y topes. **A partir de aquí `/query` exige clave de artefacto**, así que el merge a `main` debe ir acompañado del registro de las instancias y la actualización de los clientes (T089).
4. US5: módulo Uso.

Como Railway despliega desde `main` y todo se trabaja en `dev`, cada historia se puede validar en local sin desplegar; el usuario decide cuándo hacer el merge.

---

## Notes

- [P] = archivos distintos, sin dependencias pendientes.
- Cada historia se puede completar y probar sola en su checkpoint.
- No borrar ni reprocesar documentos en ninguna tarea; la reorganización solo mueve referencias.
- La reorganización contra producción y el merge a `main` los ejecuta el usuario (T089).
