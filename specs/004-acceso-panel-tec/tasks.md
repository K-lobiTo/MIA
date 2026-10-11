---

description: "Tareas de implementación del acceso al panel con cuentas del TEC y separación por unidad"
---

# Tasks: Acceso al panel con cuentas del TEC y separación por unidad

**Input**: Design documents from `specs/004-acceso-panel-tec/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluidos. FR-028 exige pruebas automáticas para cada ruta cuyo comportamiento cambia y para la lógica pura del panel. Dentro de cada historia, las pruebas van primero y deben fallar antes de implementar.

**Organization**: tareas agrupadas por historia de usuario (US1 a US6 de spec.md), precedidas por la base de la API que todas necesitan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (archivos distintos, sin dependencias pendientes)
- **[Story]**: historia a la que pertenece (US1 a US6)

## Reglas para quien implemente

- Trabajar en la rama `dev`. Nunca hacer merge a `main` ni desplegar (lo pide el usuario).
- Todo texto (código, comentarios, mensajes, documentación, commits) en español y **sin guion largo (em dash)**: usar dos puntos, coma, punto, paréntesis o guion corto. Commits sin atribución de Claude. Ver `CLAUDE.md`.
- Es un prototipo: lo más simple que cumpla la especificación. Sin abstracciones que no se usen.
- Seguir el estilo del código existente: comentarios breves que explican el porqué; en la API la lógica de acceso sin HTTP en `src/mia/access/`; en el panel el mismo patrón de `api/`, `modules/` y variables de color en `styles/tokens.css`.
- Los textos exactos de errores y pantallas están en [contracts/ui-panel.md](contracts/ui-panel.md) y los códigos de error en [contracts/api-acceso.md](contracts/api-acceso.md); no inventar otros.
- Después de cada fase: `pytest` y `ruff check src tests scripts` en verde, y en `web/admin/` `npm run typecheck` y `npm test`.
- Los tests existentes que usan la fixture `admin` (clave `X-Admin-Key`) siguen valiendo: esa clave ahora es la de automatización con alcance global. Solo hay que ajustar los que dependían de que `ADMIN_KEY` vacía respondiera 503 o de que el inventario fuera público.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dependencias y configuración nueva.

- [X] T001 Agregar `"PyJWT[crypto]>=2.9"` a `dependencies` en `pyproject.toml` (junto a `httpx`) y reinstalar con `pip install -e ".[dev]"`
- [X] T002 Agregar a `Settings` en `src/mia/config.py`, junto a `admin_key` y con un comentario breve cada uno: `entra_tenant_id: str = "1119bb90-88ba-4894-b7f1-de26e129d977"` (directorio del TEC), `entra_client_id: str = ""` (vacío: el inicio de sesión responde 503) y `entra_require_mfa: bool = True`. Actualizar también el comentario de `admin_key` ("clave de automatización para scripts, alcance global; vacía la desactiva")
- [X] T003 [P] Documentar `ENTRA_CLIENT_ID=`, `ENTRA_TENANT_ID=1119bb90-88ba-4894-b7f1-de26e129d977` y `ENTRA_REQUIRE_MFA=true` en `.env.example` y en `deploy/railway/variables.example.env` (sección "Versión 2"), y reescribir el comentario de `ADMIN_KEY` en ambos como "clave de automatización para scripts (alcance global); vacía, queda desactivada"
- [X] T004 [P] Instalar `@azure/msal-browser` en `web/admin/` con `npm install @azure/msal-browser` (queda en `package.json` y `package-lock.json`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: esquema, validación de la identidad, `Principal` y fixtures de prueba. Bloquea todas las historias.

**⚠️ CRITICAL**: ninguna historia puede empezar hasta terminar esta fase.

- [X] T005 Agregar a `src/mia/storage/models.py` los modelos `Admin` (tabla `admins`: `id` String PK; `email` String único, "siempre en minúsculas y sin espacios"; `is_global` Boolean por defecto False; `active` Boolean por defecto True; `created_at` y `updated_at` DateTime con `_now`, `updated_at` con `onupdate=_now`) y `AdminUnit` (tabla `admin_units`: `admin_id` FK `admins.id` PK y `unit_id` FK `units.id` PK), con el mismo estilo que `Artifact` y `ArtifactUnit`
- [X] T006 Crear la migración `src/mia/storage/migrations/versions/0003_administradores.py` (revisión `0003`, `down_revision` la de 0002) que crea `admins` y `admin_units` con los nombres de restricciones de `NAMING_CONVENTION`, con `downgrade` que las borra. Extender `tests/unit/test_migrations.py` para que cubra que `alembic upgrade head` crea las dos tablas y que una base en `0002` se actualiza sin perder datos
- [X] T007 [P] Crear `src/mia/access/scope.py` con el dataclass `Principal(email: str | None, is_global: bool, unit_ids: frozenset[str], source: str)` y su propiedad `label` (el correo, o `"automatizacion"` si no hay correo), más las funciones puras de [data-model.md](data-model.md): `unit_in_scope(principal, unit_id)`, `domain_in_scope(session, principal, domain)` (un dominio sin unidad solo para global), `artifact_in_scope(session, principal, artifact)` (global, o: no `all_domains`, con acceso configurado, y todas sus unidades y la unidad de cada dominio puntual en alcance), `can_grant_access(session, principal, access_all_domains, unit_ids, domain_ids)` y `artifact_ids_in_scope(session, principal) -> list[str] | None` (`None` para global, que significa todos; lista vacía significa ninguno)
- [X] T008 [P] Crear `tests/unit/test_scope.py` con pruebas de las reglas de T007: global ve todo; unidad ve su dominio y no el ajeno ni el sin unidad; artefacto de su unidad en alcance; artefacto `all_domains` fuera; artefacto de dos unidades (una ajena) fuera; artefacto con dominio puntual de unidad ajena fuera; `can_grant_access` rechaza `all_domains` y unidades ajenas para alcance de unidad; `artifact_ids_in_scope` devuelve `None` para global y lista vacía cuando no hay artefactos en alcance
- [X] T009 [P] Crear `src/mia/access/admins.py` (único que escribe `admins` y `admin_units`): `normalize_email(text)` (recorta y pasa a minúsculas; lanza `ValueError` si no contiene `@`), `add_admin(session, email, *, is_global, unit_names)` (alcance global **o** al menos una unidad, nunca ninguno; las unidades se buscan por nombre y se rechazan las inexistentes con `ValueError` que las nombra; si el correo existe, reemplaza su alcance y lo reactiva; si es global no guarda filas en `admin_units`), `list_admins(session)` (correo, global, nombres de unidad, activo), `deactivate_admin(session, email)` (no borra; `ValueError` si no existe) y `find_active_admin(session, email) -> Principal | None`. Todo con `session.commit()` dentro de la función
- [X] T010 [P] Crear `tests/unit/test_admins.py` con pruebas de T009: normaliza mayúsculas y espacios; rechaza correo sin `@`; rechaza sin alcance (ni global ni unidades); rechaza unidad inexistente sin guardar nada; agregar de nuevo actualiza el alcance y reactiva; desactivar conserva el registro; `find_active_admin` devuelve `None` para desactivado o desconocido y un `Principal` con los `unit_ids` correctos; global no guarda unidades. Usa la fixture `db` de `tests/conftest.py`
- [X] T011 Crear `src/mia/access/entra.py` según [research.md](research.md) decisiones 3 a 5: clase `AuthError(HTTPException)` con atributo `code`, definida en `src/mia/access/errors.py` (la importan `entra.py`, `security.py` y `main.py`), interfaz `KeySource` (`get_key(kid)`), implementación `MicrosoftKeys` (baja `https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys` con `httpx`; caché en memoria de 1 hora; nueva bajada solo si llega un `kid` desconocido y pasaron al menos 5 minutos desde la última; si la bajada falla usa la caché aunque esté vencida; si no hay ninguna lanza `AuthError` 503 `identity_unavailable`) y `validate_id_token(token, key_source) -> Identity(email, mfa)` que aplica en orden los pasos 1 a 6 de [contracts/api-acceso.md](contracts/api-acceso.md): `ENTRA_CLIENT_ID` configurado (503 `login_not_configured`), solo `RS256` con `kid`, firma, `iss`, `aud`, `tid`, `exp` e `iat` requeridos con margen de 60 s, `amr` con `mfa` si `entra_require_mfa`, correo de `email` o `preferred_username` en minúsculas (sin correo: `invalid_token`). Códigos y estados exactos de la tabla de errores del contrato; los mensajes en español no revelan por qué falló la firma
- [X] T012 En `tests/conftest.py` agregar las fixtures de identidad: `rsa_key` (par RSA generado una vez por sesión), `token_factory` (firma un ID token RS256 con `kid`, `iss`, `aud`, `tid`, `email`, `amr`, `exp` e `iat` por defecto válidos y cada uno sobreescribible; opción para firmar con otra clave y para `alg: none`), `key_source_override` (sustituye la dependencia `get_key_source` con `app.dependency_overrides` por una fuente que conoce solo la clave pública local) y `entra_config` (fija con `monkeypatch` `settings.entra_client_id="cliente-de-prueba"`, el tenant del TEC y `entra_require_mfa=True`). Agregar `as_user(email)` que devuelve los encabezados `Authorization: Bearer` de un token válido de ese correo
- [X] T013 Crear `tests/unit/test_entra.py` con pruebas de `validate_id_token` usando las fixtures de T012: token válido devuelve correo en minúsculas; `preferred_username` cuando falta `email`; sin ninguno `invalid_token`; vencido `token_expired`; `iss` de otro tenant, `aud` ajena y `tid` ajeno `invalid_token`; firmado con otra clave `invalid_token`; `alg: none` y HS256 `invalid_token`; `kid` desconocido; sin `amr` con `mfa` y MFA exigido `mfa_required`, y válido con `entra_require_mfa=False`; sin `entra_client_id` `login_not_configured`; `MicrosoftKeys` con un `httpx` simulado: usa la caché dentro de la hora, no vuelve a bajar antes de 5 minutos ante `kid` desconocido, usa la caché vencida si la bajada falla y responde `identity_unavailable` si nunca hubo claves
- [X] T014 Reescribir `src/mia/api/security.py`: `get_key_source()` (dependencia que devuelve la `MicrosoftKeys` única del proceso); `optional_admin(authorization, x_admin_key, session, key_source) -> Principal | None` (si hay `Authorization: Bearer`, valida con `validate_id_token`, busca con `find_active_admin` y lanza 403 `not_authorized` si no está o está desactivado; si no hay Bearer y llega `X-Admin-Key` válida y `settings.admin_key` no vacía, devuelve `Principal(None, True, frozenset(), "automation")`; con `ADMIN_KEY` vacía ignora `X-Admin-Key`; `None` si no llegó ninguna credencial; clave incorrecta es 401 `unauthenticated`) y `require_admin` (llama a `optional_admin` y lanza 401 `unauthenticated` si es `None`; devuelve el `Principal`). Conservar `optional_artifact` y `require_artifact` sin cambios. Quitar `admin_key_matches` de `access/keys.py` solo si deja de usarse; si se sigue usando, dejarlo
- [X] T015 En `src/mia/api/main.py` registrar el manejador de `AuthError` que devuelve `{"detail": ..., "code": ...}` con su estado, agregar `"Authorization"` a `allow_headers` de CORS, y registrar el router nuevo `me`. Crear `src/mia/api/routes/me.py` con `GET /me` (depende de `require_admin`) que devuelve `email`, `is_global`, `units` (id y nombre) y `source` según [contracts/api-acceso.md](contracts/api-acceso.md)
- [X] T016 Reescribir `tests/unit/test_security.py` para el nuevo `require_admin`/`optional_admin`: sin credencial 401 `unauthenticated`; `X-Admin-Key` correcta da `Principal` global de origen `automation`; con `ADMIN_KEY` vacía cualquier `X-Admin-Key` es 401 (ya no 503); Bearer válido de correo en la lista da su alcance; Bearer válido de correo fuera de la lista o desactivado es 403 `not_authorized`; si llegan ambas credenciales gana el Bearer. Agregar `tests/unit/test_me.py` con `GET /me` para global, unidad, automatización y no autorizada. Ajustar los demás tests que dependan de 503 por `ADMIN_KEY` vacía

**Checkpoint**: la API sabe quién es cada petición; `pytest` y `ruff` en verde.

---

## Phase 3: User Story 1 - Entrar con mi cuenta del TEC y ver solo lo de mi unidad (Priority: P1) 🎯 MVP

**Goal**: iniciar sesión con Microsoft en el panel y ver y operar solo el inventario de la propia unidad.

**Independent Test**: con las cuentas de prueba de Computación y de Administración de Empresas, cada una ve solo su unidad en el inventario y solo puede crear dentro de ella (por el panel y por la API).

### Tests for User Story 1 (API)

- [ ] T017 [P] [US1] Crear `tests/unit/test_scope_inventory.py` con pruebas de las rutas de inventario según la tabla de [contracts/api-acceso.md](contracts/api-acceso.md): `GET /inventory` y `GET /units` sin credencial 401, de unidad solo trae su unidad (con sus dominios, carpetas y documentos) y `unassigned_domains` vacío, global trae todo; `POST /units` de unidad 403 `global_only` y global 201; `POST /domains` en unidad propia 201 (con `visible_to` sin artefactos ajenos) y en ajena 403 `out_of_scope`; `GET /domains` sin ninguna credencial 401, con credencial de unidad solo sus dominios, y con `X-Artifact-Key` igual que hoy; `GET /domains/{id}/documents` ajeno 404 y propio 200; crear, renombrar y borrar carpeta y subir documento en dominio propio funcionan y en ajeno 403 `out_of_scope`

### Implementation for User Story 1 (API)

- [ ] T018 [US1] Aplicar el alcance en `src/mia/api/routes/inventory.py`: `GET /inventory` y `GET /units` con `Depends(require_admin)` que filtran con `unit_in_scope`/`domain_in_scope` (`unassigned_domains` solo para global); `POST /units` exige global (403 `global_only`); crear, renombrar y borrar carpeta validan que el dominio de la carpeta esté en alcance (403 `out_of_scope`); las rutas de escritura pasan a recibir `principal: Principal = Depends(require_admin)` en lugar de `dependencies=[...]`
- [ ] T019 [US1] Aplicar el alcance en `src/mia/api/routes/domains.py`: `POST /domains` valida `unit_in_scope` y calcula `visible_to` solo con artefactos en alcance; `GET /domains` usa `optional_artifact` y `optional_admin` (si hay artefacto, igual que hoy; si no hay artefacto ni credencial, 401; con credencial, filtra por alcance); `POST /domains/{id}/documents` valida el dominio en alcance (403 `out_of_scope`); `GET /domains/{id}/documents` con `require_admin` y dominio ajeno 404

- [ ] T019b [US1] Ajustar las pruebas existentes que leen sin credencial lo que ahora exige sesión (FR-022): `tests/unit/test_inventory.py` (todas las llamadas a `/inventory` y `/units`), `tests/unit/test_units_domains.py` (líneas de `/units` y `/domains`), `tests/unit/test_folders.py` (`/inventory`), `tests/unit/test_upload.py` (`/domains/{id}/documents`) y `tests/unit/test_config.py` (`/domains` sin clave de artefacto), agregándoles la fixture `admin` (clave de automatización) para que sigan verificando lo mismo. `/domains` con `X-Artifact-Key` y `/config` no se tocan. `pytest` completo en verde

### Implementation for User Story 1 (panel)

- [ ] T020 [P] [US1] Crear `web/admin/src/auth/config.ts` con la función pura `buildMsalConfig(env)` que recibe `{clientId, tenantId, authority, origin}` y devuelve la configuración de MSAL: `authority` por defecto `https://login.microsoftonline.com/{tenantId}` (tenant del TEC si falta), `redirectUri` el origen con barra final, `cache: {cacheLocation: "sessionStorage"}`, y cuando hay `authority` alternativa `protocolMode: "OIDC"`, `knownAuthorities` con su host y `authorityMetadata` armado a partir de ella (`authorization_endpoint`, `token_endpoint`, `issuer`, `jwks_uri`, `end_session_endpoint`), más la lista fija de scopes `["openid", "profile", "email"]`; y `isConfigured(env)`. Crear `web/admin/src/auth/config.test.ts` que prueba el valor por defecto de autoridad, la barra final, el modo del IdP alternativo y que sin `clientId` no está configurado
- [ ] T021 [US1] Crear `web/admin/src/auth/session.ts` con el estado observable de acceso (`useSyncExternalStore`) y los estados de [contracts/ui-panel.md](contracts/ui-panel.md) (`cargando`, `sin_sesion`, `no_configurado`, `iniciando`, `activa`, `rechazada`): crea la instancia de `PublicClientApplication` con `buildMsalConfig` desde `import.meta.env` (`VITE_ENTRA_CLIENT_ID`, `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_AUTHORITY`), resuelve `handleRedirectPromise()` al arrancar, expone `signIn()` (`loginRedirect` con `responseMode: "query"`), `getIdToken(forceRefresh?)` (guarda en memoria el ID token vigente y lee su `exp`; solo llama a `acquireTokenSilent` y reemplaza el guardado cuando faltan menos de 5 minutos o con `forceRefresh`, porque con solo los scopes `openid profile email` MSAL no reutiliza una caché de access token y cada llamada iría a Microsoft), `signOut()` (`logoutRedirect` con `onRedirectNavigate: () => false` para borrar solo la caché local y pasar a `sin_sesion`) y `setProfile(me)`. Al arrancar borra la clave `mia-admin-key` de `localStorage` si existe (dentro de `try/catch`). Si MSAL no puede iniciar (almacenamiento bloqueado, modo privado estricto), pasa a `rechazada("navegador")` en vez de dejar la pantalla en blanco
- [ ] T022 [US1] Reescribir `web/admin/src/api/client.ts`: eliminar la clave compartida (`getAdminKey`, `setAdminKey`, `useAdminKey`, `setInvalidKeyHandler`, `X-Admin-Key`); `apiFetch` y `apiDownload` piden el token a `session.getIdToken()` y envían `Authorization: Bearer`; `ApiError` suma el campo `code` leído del cuerpo (`detail` sigue siendo el mensaje). El manejo de 401/403 se completa en T031 (US2)
- [ ] T023 [P] [US1] Agregar a `web/admin/src/api/types.ts` el tipo `Me` (`email`, `is_global`, `units`, `source`) y un hook `useMe` en `web/admin/src/api/me.ts` sobre `GET /me`, que `session.ts` usa para pasar a `activa` guardando el perfil
- [ ] T024 [US1] Crear `web/admin/src/components/LoginScreen.tsx` y sus estilos en `web/admin/src/styles/base.css` (o `login.css`): título "MIA, Panel de administración", botón "Iniciar sesión con Microsoft" que llama a `signIn()`, estado `no_configurado` con el aviso "El inicio de sesión no está configurado" y sin botón. Una columna centrada que cabe en 320 px, con los tokens de color existentes para claro y oscuro. Los mensajes de rechazo se agregan en US2
- [ ] T025 [US1] Reescribir `web/admin/src/components/Layout.tsx` y `web/admin/src/App.tsx`/`main.tsx`: mostrar `LoginScreen` mientras el estado no sea `activa`; en la barra lateral, al pie, el correo, el alcance ("Global" o los nombres de las unidades) y "Cerrar sesión" (`signOut()`); quitar `AdminKeyDialog`, el aviso de "solo lectura", `askForKey` del contexto del `Outlet` y la propiedad `needsAdmin` de `web/admin/src/modules/index.tsx`
- [ ] T026 [US1] Adaptar los tres módulos a la sesión: quitar `useAdminKey`, `askForKey` y las guardas por clave de `InventarioPage.tsx`, `ArtefactosPage.tsx` y `UsoPage.tsx`, y de los componentes que las usen (`grep -rn "AdminKey\|askForKey\|adminKey" web/admin/src`); en Inventario ofrecer "Nueva unidad" solo si `useMe().is_global`. Crear `web/admin/src/auth/capabilities.ts` con `capabilities(me)` (`canCreateUnit`, `canSeeBalance`, `canUseAllDomains`, `showGlobalCaps`) y `web/admin/src/auth/capabilities.test.ts` que prueba cada una para global y para unidad
- [ ] T027 [US1] Verificar que `cd web/admin && npm run typecheck && npm test && npm run build` pasa y que la compilación **no falla** sin `VITE_ENTRA_CLIENT_ID`. En `web/admin/Dockerfile` agregar `ARG VITE_ENTRA_CLIENT_ID`, `ARG VITE_ENTRA_TENANT_ID` y `ARG VITE_ENTRA_AUTHORITY` opcionales (sin `test -n`) junto a `VITE_API_URL`; actualizar `web/admin/src/vite-env.d.ts` con las tres variables

**Checkpoint**: US1 completa del lado API y panel (la validación en navegador va en la fase final, con el servidor de identidad simulado).

---

## Phase 4: User Story 2 - Saber por qué no puedo entrar y qué hacer (Priority: P1)

**Goal**: cada rechazo (cuenta no autorizada, sin segundo factor, sesión vencida, inicio no configurado) muestra su mensaje claro y nunca deja ver datos; la identidad vencida se renueva en silencio.

**Independent Test**: iniciar sesión con una cuenta no listada, una sin segundo factor y una con token vencido: cada una muestra su mensaje y ningún dato.

### Tests for User Story 2

- [ ] T028 [P] [US2] Crear `tests/unit/test_auth_routes.py` con pruebas, sobre rutas reales (`GET /inventory`, `POST /domains`, `GET /artifacts`, `GET /usage`), de cada código del contrato: sin credencial 401 `unauthenticated`; token vencido 401 `token_expired`; tenant ajeno, audiencia ajena y firma de otra clave 401 `invalid_token`; sin MFA 403 `mfa_required` (y con `entra_require_mfa=False` pasa); correo fuera de la lista y correo desactivado 403 `not_authorized`; sin `entra_client_id` 503 `login_not_configured` (y la clave de automatización sigue funcionando); claves de Microsoft no disponibles 503 `identity_unavailable`; el cuerpo trae `detail` en español y `code`; desactivar a un administrador entre dos peticiones con el mismo token hace que la segunda sea 403 (FR-024); cambiar su alcance rige en la segunda petición
- [ ] T029 [P] [US2] Crear `web/admin/src/auth/errors.ts` con la función pura `describeAccessError({status, code}, email?)` que devuelve `{kind, message, action}` con los textos exactos de la tabla de [contracts/ui-panel.md](contracts/ui-panel.md) (`not_authorized`, `mfa_required`, `token_expired`/`invalid_token`, `login_not_configured`, `identity_unavailable`, cancelación o error de Microsoft, sin conexión) y `null` para errores que no son de acceso (`out_of_scope`, `global_only`, 404, 409, 422...), y `web/admin/src/auth/errors.test.ts` que prueba cada fila de la tabla y los `null`

### Implementation for User Story 2

- [ ] T030 [US2] Completar `LoginScreen.tsx` con el estado `rechazada(motivo)`: el mensaje de `describeAccessError` y la acción que corresponde ("Cerrar sesión", "Volver a iniciar sesión" o "Reintentar"), con el correo en el mensaje de cuenta no autorizada; el mismo diseño en claro, oscuro y celular. Incluir el motivo `navegador` con el texto "Tu navegador bloquea el almacenamiento necesario para iniciar sesión. Revisa que no estés en una ventana privada estricta o que las cookies y el almacenamiento del sitio estén permitidos." (agregarlo también a `contracts/ui-panel.md` y a `errors.ts`/`errors.test.ts`). Ajustar `session.ts` para exponer `reject(reason)` y para que un error de Microsoft al volver de la redirección pase a `rechazada` con su motivo
- [ ] T031 [US2] Completar `web/admin/src/api/client.ts`: ante 401 con `code` `token_expired` o `invalid_token`, pedir `getIdToken(true)` y reintentar la petición **una vez**; si la renovación falla o el reintento vuelve a dar 401, `session.reject` con "vencida"; ante 403 `not_authorized`/`mfa_required` y 503 `identity_unavailable`/`login_not_configured`, `session.reject` con su motivo (usando `describeAccessError`); un 403 `out_of_scope`/`global_only` se deja como `ApiError` normal para que el módulo lo muestre. Aplicar lo mismo en `apiDownload`
- [ ] T032 [US2] En `web/admin/src/modules/inventario/useUploads.ts` asegurar que una subida cuya petición reciba 401 por vencimiento se reintenta con el token renovado (mismo mecanismo de T031, sin perder la cola) y que un cuerpo `FormData` se puede reenviar (si ya se consumió, reconstruirlo desde el `File`)

**Checkpoint**: los rechazos de US2 verificados en API (pytest) y en lógica pura (Vitest); la prueba visual va en la fase final.

---

## Phase 5: User Story 3 - Dar y quitar acceso con un script (Priority: P1)

**Goal**: el operador gestiona la lista de administradores desde la terminal.

**Independent Test**: agregar un correo con alcance Computación, listarlo, desactivarlo (la API lo rechaza en la siguiente petición) y volver a agregarlo para reactivarlo.

### Tests for User Story 3

- [ ] T033 [P] [US3] Crear `tests/unit/test_admin_script.py` (patrón de `tests/unit/test_servicios.py`: importar el script como módulo con `importlib` y llamar a `main(argv)` sobre una base temporal) con pruebas de: `agregar --global`, `agregar --unidad "Computación" --unidad "..."`, `listar` (muestra correo, alcance y estado), `desactivar`, reactivar agregando de nuevo, unidad inexistente rechazada sin guardar, correo sin `@` rechazado, `agregar` sin `--global` ni `--unidad` rechazado, `desactivar` de un correo desconocido con mensaje claro, y el aviso cuando tras desactivar ya no queda ningún administrador global activo (la clave de automatización sigue siendo la vía de emergencia)

### Implementation for User Story 3

- [ ] T034 [US3] Crear `scripts/admin.py` con subcomandos `agregar CORREO (--global | --unidad NOMBRE ...)`, `listar` y `desactivar CORREO`, usando `mia.access.admins` y la sesión de `mia.storage.db` (misma base que la API según `DATABASE_URL`; acepta `--env-file` como `scripts/reorganizar_v2.py` para apuntar a producción). Mensajes en español de lo hecho, errores claros sin trazas de Python para `ValueError`, y el aviso del último global. Docstring de uso al inicio, en el estilo de los otros scripts

**Checkpoint**: US3 completa; el operador ya puede cargar a las cuatro personas.

---

## Phase 6: User Story 4 - La separación cubre artefactos y uso (Priority: P2)

**Goal**: artefactos y módulo Uso solo muestran y permiten lo del alcance de la persona.

**Independent Test**: con un artefacto de Computación, uno de Administración de Empresas y uno de "todos los dominios", cada tipo de sesión ve, edita y mide solo lo suyo; el global ve todo y es el único con saldo.

### Tests for User Story 4

- [ ] T035 [P] [US4] Crear `tests/unit/test_scope_artifacts.py` con las pruebas de los escenarios 1 a 8 de US4: `GET /artifacts` de unidad lista solo su artefacto y trae `global: null`; global lista los tres con `global` completo; `POST /artifacts` con acceso de su unidad 201, con `all_domains`, otra unidad o mezcla 403 `out_of_scope`, con dominio puntual propio 201 y ajeno 403, y de alcance con dos unidades puede combinar ambas; `PATCH` y `POST /artifacts/{id}/key` sobre un artefacto fuera de alcance 404 y sobre uno propio con acceso nuevo ajeno 403 `out_of_scope`; el artefacto de dos unidades no lo ve quien tiene solo una
- [ ] T036 [P] [US4] Crear `tests/unit/test_scope_usage.py` con registros de consultas de tres artefactos: `GET /usage` de unidad solo suma los suyos y `by_artifact` solo lista los suyos; un `artifact_id` ajeno en el filtro no devuelve nada ajeno; un alcance de unidad sin ningún artefacto en alcance ve ceros y registro vacío (no todo); `GET /usage/queries` en JSON y en CSV solo con sus artefactos; `GET /usage/queries/{id}` de un artefacto ajeno y de una consulta sin artefacto 404; `GET /usage/balance` de unidad 403 `global_only`; global ve todo sin cambios. Agregar en `tests/unit/test_usage.py` (o en este archivo) una prueba directa de que `artifact_ids=[]` significa "ninguno" y `None` "todos" en `usage/aggregate.py`

### Implementation for User Story 4

- [ ] T037 [US4] En `src/mia/usage/aggregate.py` cambiar el filtro de artefactos a lista exacta: `_statement` usa `if artifact_ids is not None` (lista vacía: sin resultados, p. ej. `where(false())`), y en `compute_usage` el cálculo de `shown` usa `artifact_ids is None or a.id in artifact_ids`. Revisar los demás usos de `artifact_ids` en `src/mia/usage/` y `src/mia/api/routes/usage.py`
- [ ] T038 [US4] Aplicar el alcance en `src/mia/api/routes/usage.py`: reemplazar `dependencies=[Depends(require_admin)]` del router por `principal: Principal = Depends(require_admin)` en cada ruta; `UsageFilters` calcula los ids efectivos intersectando los pedidos con `artifact_ids_in_scope` (`None` para global); `GET /usage/queries/{id}` responde 404 si el artefacto de la consulta no está en alcance o es nulo y el alcance no es global; `GET /usage/balance` exige global (403 `global_only`)
- [ ] T039 [US4] Aplicar el alcance en `src/mia/api/routes/artifacts.py`: quitar la dependencia del router y usar `Depends(require_admin)` por ruta; `GET /artifacts` filtra con `artifact_in_scope` y para alcance de unidad devuelve `global_: None` (cambiar `ArtifactsOut.global_` a `GlobalOut | None`) y calcula los costos medios por modo solo con consultas de sus artefactos; `POST /artifacts` valida con `can_grant_access` (403 `out_of_scope`); `PATCH` y `POST /artifacts/{id}/key` responden 404 si el artefacto no está en alcance y validan el acceso nuevo con `can_grant_access`
- [ ] T040 [P] [US4] Panel: en `web/admin/src/api/types.ts` hacer `global` nulo; en `web/admin/src/modules/artefactos/ArtefactosPage.tsx` ocultar el bloque de topes globales y el aviso de `caps_exceed_global` cuando `global` es nulo; en `ArtifactForm.tsx` no ofrecer "Todos los dominios" sin `canUseAllDomains` (las unidades y dominios del formulario ya llegan recortados por la API); en `web/admin/src/modules/uso/UsoPage.tsx` mostrar `BalanceCard` solo si `canSeeBalance`. Extender `web/admin/src/auth/capabilities.test.ts` si hace falta

**Checkpoint**: US4 completa; la separación cubre inventario, artefactos y uso.

---

## Phase 7: User Story 5 - Los scripts siguen con la clave de automatización (Priority: P2)

**Goal**: `ADMIN_KEY` es solo para scripts, global, desactivable, y el panel no la conoce.

**Independent Test**: con `ADMIN_KEY` configurada los scripts funcionan; vacía, se rechaza; el panel publicado no contiene ni guarda ninguna clave compartida.

### Tests for User Story 5

- [ ] T041 [P] [US5] Crear `tests/unit/test_automation_key.py`: con `ADMIN_KEY` configurada, `X-Admin-Key` da alcance global en una lectura (`GET /inventory`), una escritura (`POST /domains`) y una ruta de Uso/artefactos; con `ADMIN_KEY` vacía la misma clave es 401 `unauthenticated` (no 503) en cada una; `GET /me` con la clave responde `source: "automation"` y `email: null`; una clave incorrecta es 401

### Implementation for User Story 5

- [ ] T042 [US5] Comprobar con `grep -rn "X-Admin-Key\|mia-admin-key\|ADMIN_KEY\|AdminKey" web/admin/src web/admin/index.html` que no queda ninguna referencia en el panel, y borrar `web/admin/src/components/AdminKeyDialog.tsx` si T025 no lo hizo. Revisar con `grep` que `scripts/cargar_carpeta.py` y `scripts/pruebas_mvp.py` solo envían `X-Admin-Key` (siguen valiendo sin cambios) y que `scripts/reorganizar_v2.py` no usa HTTP; actualizar sus docstrings para decir "clave de automatización" donde dicen "clave de administración"
- [ ] T043 [US5] En `src/mia/access/keys.py`, `admin_key_matches` queda como única comprobación de la clave de automatización (compara en tiempo constante y devuelve `False` si `settings.admin_key` está vacía); confirmar que `security.py` la usa y que ningún otro código del panel o la API acepta la clave por otra vía

**Checkpoint**: US5 completa.

---

## Phase 8: User Story 6 - Saber quién hizo cada cambio (Priority: P3)

**Goal**: cada escritura y cada rechazo por alcance deja una línea JSON atribuida.

**Independent Test**: hacer una escritura con una sesión y otra con la clave de automatización; el log del servidor muestra las dos líneas, con correo y `automatizacion`, sin tokens ni claves.

### Tests for User Story 6

- [ ] T044 [P] [US6] Crear `tests/unit/test_audit.py` con `caplog`/captura del logger `mia.admin`: una línea JSON válida con `ts`, `actor`, `action`, `target`, `detail`, `result` por cada escritura (`unit.create`, `domain.create`, `folder.create`, `folder.rename`, `folder.delete`, `document.upload`, `artifact.create`, `artifact.update`, `artifact.key_regenerate`); `actor` es el correo para una sesión y `"automatizacion"` para la clave; un rechazo `out_of_scope` y el rechazo `global_only` de `POST /units` quedan con `result: "rechazado"`; ninguna línea contiene el token, `ADMIN_KEY`, ni la clave de artefacto generada (en `artifact.create` y `artifact.key_regenerate`); las lecturas no registran nada

### Implementation for User Story 6

- [ ] T045 [US6] Crear `src/mia/access/audit.py` con `log_write(principal, action, target, detail="", result="ok")` que escribe una línea JSON (`json.dumps(..., ensure_ascii=False)`) por el logger `mia.admin` y deja configurado ese logger a nivel INFO con su propio `StreamHandler` a la salida estándar y `propagate = False`, de modo que el nivel no se pierda con la configuración de uvicorn
- [ ] T046 [US6] Llamar a `audit.log_write` desde cada ruta de escritura con las acciones de T044: `src/mia/api/routes/inventory.py`, `src/mia/api/routes/domains.py` y `src/mia/api/routes/artifacts.py`; en cada rechazo `out_of_scope` (403) y en el `global_only` de `POST /units` registrar `result="rechazado"` antes de lanzar el error (los 404 por lectura o cambio ajeno no se registran). Solo ids y nombres como `target` y `detail`; nunca la clave de artefacto ni el contenido del archivo

**Checkpoint**: US6 completa.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: servidor de identidad simulado, validación en navegador, documentación y cierre.

- [ ] T047 Crear `scripts/idp_simulado.py` (solo desarrollo, con docstring que lo diga): una aplicación FastAPI mínima en el puerto 9000 con `/{tenant}/v2.0/.well-known/openid-configuration`, `/{tenant}/oauth2/v2.0/authorize` (una página con las cuentas de prueba: global, Computación, Administración de Empresas, no listada y sin segundo factor; redirige con `code` en la query y valida `code_challenge` PKCE `S256`), `/{tenant}/oauth2/v2.0/token` (cambia el código por un ID token RS256 y un refresh token, también con `grant_type=refresh_token`, con CORS abierto para `http://localhost:3001`) y las claves públicas; los tokens llevan `iss`, `aud` (el client ID de prueba), `tid`, `email`, `amr` y una vigencia corta configurable (`--vigencia`, 120 s por defecto). Además arranca la API (uvicorn, puerto 8000, `CORS_ORIGINS=http://localhost:3001`, `ENTRA_CLIENT_ID=cliente-de-prueba`) con `app.dependency_overrides[get_key_source]` apuntando a esas claves y siembra las cuentas en la lista de administradores. Opción `--token CORREO` que imprime un ID token válido para probar con `curl` (quickstart sección 4). No es parte del paquete `mia`
- [ ] T048 Validar en navegador real siguiendo la sección 3 del [quickstart.md](quickstart.md): cuenta de Computación (solo su unidad; sin "Nueva unidad" ni saldo; `sessionStorage` con la sesión y `localStorage` vacío), de Administración de Empresas, global, no listada, sin segundo factor, desactivación con sesión abierta, renovación silenciosa al vencer el token simulado, sesión vencida, cierre de sesión, y la pantalla de inicio de sesión y el panel en modo claro, oscuro y a 360 px; además ejecutar la sección 6 del quickstart (SC-007): `scripts/cargar_carpeta.py` con `ADMIN_KEY` sobre la API local y una consulta de la Consulta administrativa con su clave de artefacto. Comprobar en particular que la respuesta por query (`?code=`) no choca con `HashRouter` y que la URL queda limpia. Tomar capturas en el directorio temporal y corregir lo que falle; anotar en el quickstart lo que no se pudo probar
- [ ] T049 [P] Actualizar `docs/ARQUITECTURA.md`: estructura del código (`access/entra.py`, `admins.py`, `scope.py`, `audit.py`, `routes/me.py`, migración 0003 y modelos nuevos), la sección "Acceso" (ahora con sesión de Microsoft, alcance por unidad, `ADMIN_KEY` solo de automatización, lecturas de inventario con sesión, 404 en lecturas ajenas), el diagrama de despliegue (encabezado `Authorization` en lugar de `X-Admin-Key` para el panel), la sección del panel (MSAL, `sessionStorage`) y la decisión de usar el ID token con su riesgo aceptado
- [ ] T050 [P] Actualizar `docs/OPERACION.md`: variables nuevas (`ENTRA_CLIENT_ID`, `ENTRA_TENANT_ID`, `ENTRA_REQUIRE_MFA`, y `VITE_ENTRA_*` del panel como variables de compilación que exigen volver a desplegar con `railway up`), `scripts/admin.py` con ejemplos, cómo dar y quitar acceso, el orden de despliegue de [research.md](research.md) decisión 12 (y que el panel anterior deja de servir al desplegar la API), qué hacer si TI cambia algo (otro client ID, otra dirección de redirección, cambio de correo de una persona, política sin `amr`) y que `ADMIN_KEY` ahora es solo de automatización
- [ ] T051 [P] Actualizar `docs/REGISTRO_APLICACION_TEC.md` solo si algo cambió respecto del plan (verificar: el flujo, los permisos `openid profile email` y el claim `email` coinciden; agregar una nota de que la dirección de redirección debe terminar en barra y que no se necesita registrar dirección de cierre de sesión), y actualizar `README.md` y `web/admin/README.md` (inicio de sesión, variables, ejecución con el IdP simulado, qué ve cada alcance)
- [ ] T052 Ejecutar el cierre completo y dejarlo en verde: `pytest`, `ruff check src tests scripts` y en `web/admin/` `npm run typecheck`, `npm test` y `npm run build`; revisar con `grep -rnP "\x{2014}" specs/004-acceso-panel-tec docs README.md web/admin/README.md scripts src tests web/admin/src` que no hay guion largo (U+2014); confirmar que ninguna ruta edita los topes globales ni la configuración de la instancia (FR-023: `grep -n "daily_cap_usd\|settings\." src/mia/api/routes/*.py` solo lee); confirmar con `git status` que no hay archivos sin querer (`.env`, capturas, `dist`) y hacer los commits en `dev`, sin atribución de Claude, uno por fase lógica, en español
- [ ] T053 Revisar el [quickstart.md](quickstart.md): que cada paso corresponda a lo implementado (nombres de opciones de `idp_simulado.py` y de `admin.py`) y que la lista "Pendiente: lo que NO se puede probar hasta tener el client ID de TI" siga completa y honesta

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; **bloquea todas las historias**.
- **US1 (Phase 3)**: depende de la fase 2. Es el MVP.
- **US2 (Phase 4)**: depende de la fase 2; las tareas del panel (T030 a T032) dependen de T021 a T025 de US1.
- **US3 (Phase 5)**: depende solo de la fase 2 (`admins.py`); puede hacerse justo después de ella y conviene hacerlo antes de la validación en navegador.
- **US4 (Phase 6)**: depende de la fase 2; T040 depende de T026 (US1).
- **US5 (Phase 7)**: depende de la fase 2; T042 depende de T025 y T026.
- **US6 (Phase 8)**: T046 depende de que existan las rutas modificadas en US1 y US4 (T018, T019, T039).
- **Polish (Phase 9)**: depende de las historias; T048 depende de T034 (US3) y T047.

### User Story Dependencies

- Las historias de API (US1, US4, US5, US6) tocan archivos distintos de ruta salvo `inventory.py`, `domains.py` y `artifacts.py`, que reciben cambios de varias: hacerlas en orden de fase para no mezclar ediciones.
- US2 y US3 son independientes entre sí.

### Within Each User Story

- Pruebas primero (deben fallar), luego implementación.
- Modelos y lógica pura antes de rutas; rutas antes del panel.

### Parallel Opportunities

- Fase 1: T003 y T004 en paralelo.
- Fase 2: T007 a T010 en paralelo entre sí (archivos distintos) después de T005; T012 en paralelo con T007 a T010.
- US1: T017 en paralelo con T020 y T023; el resto del panel en orden.
- US2: T028 y T029 en paralelo.
- US4: T035 y T036 en paralelo.
- Polish: T049, T050 y T051 en paralelo.

## Parallel Example: Phase 2

```text
Tras T005 y T006:
  T007 scope.py          T009 admins.py          T012 fixtures de identidad
  T008 test_scope.py     T010 test_admins.py
Luego T011 entra.py y T013 su prueba; después T014, T015 y T016 en orden.
```

## Implementation Strategy

### MVP (US1 + US3)

1. Fases 1 y 2 (base de la API).
2. US3 (script) para poder cargar correos.
3. US1 (alcance en inventario y panel con inicio de sesión).
4. **Detenerse y validar** con el IdP simulado (T047 y T048 parciales).

### Entrega incremental

1. Base + US3 + US1: se puede entrar y ver solo lo propio.
2. US2: mensajes y renovación.
3. US4: artefactos y uso separados (sin esto una unidad vería las preguntas de la otra en Uso).
4. US5 y US6: automatización explícita y registro.
5. Polish: documentación y cierre.

### Notas

- **No desplegar**: el orden de despliegue está en el quickstart y solo se ejecuta si el usuario lo pide.
- Lo que no se puede probar sin el client ID de TI está listado en el quickstart y debe seguir listado al terminar.
