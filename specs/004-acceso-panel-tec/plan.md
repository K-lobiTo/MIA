# Implementation Plan: Acceso al panel con cuentas del TEC y separación por unidad

**Branch**: `dev` (feature `004-acceso-panel-tec`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-acceso-panel-tec/spec.md`

## Summary

Reemplazar la clave compartida del panel por inicio de sesión individual con Microsoft (cuentas
@itcr.ac.cr) y separar los datos por unidad. En el panel, `@azure/msal-browser` hace el inicio de sesión
con código de autorización y PKCE, guarda la sesión en `sessionStorage` y renueva el token de identidad
en silencio. En la API, cada petición de administración lleva el token de identidad en
`Authorization: Bearer`; la API lo valida (firma contra las claves del directorio con caché, emisor,
audiencia, tenant, vigencia, segundo factor), busca el correo en una tabla nueva de administradores y
construye un `Principal` (global o por unidades) que las rutas usan para filtrar y autorizar. `ADMIN_KEY`
queda como clave de automatización con alcance global (vacía = desactivada). Un script `scripts/admin.py`
gestiona la lista. Cada escritura deja una línea JSON en el log del servidor con el correo. Todo se prueba
sin el client ID real: tokens firmados con una clave local y un conjunto de claves inyectable, y un
servidor de identidad simulado para probar en el navegador.

## Technical Context

**Language/Version**: Python 3.12 (API y script); TypeScript 5 con React 19 (panel)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic (sin cambios); nueva en la API `PyJWT[crypto]`
(verificación RS256; ya está instalada de forma transitiva, se declara) y `httpx` (ya declarada) para
bajar las claves; en el panel nueva `@azure/msal-browser`

**Storage**: Postgres en Neon / SQLite en desarrollo: 2 tablas nuevas (`admins`, `admin_units`),
migración Alembic `0003`. Qdrant sin cambios. Las claves públicas de Microsoft viven en memoria

**Testing**: pytest con tokens RS256 firmados por una clave local y un origen de claves inyectado con
`app.dependency_overrides`; Vitest para la lógica pura del panel; `tsc` y `vite build`; validación en
navegador real con un servidor de identidad simulado

**Target Platform**: API en Railway y panel como sitio estático en Railway (sin cambios de despliegue;
una variable de compilación nueva en el panel y tres variables nuevas en la API)

**Project Type**: web service (API existente) más aplicación web (panel existente)

**Performance Goals**: validar un token y leer la lista de administradores añade menos de 10 ms por
petición (la verificación RS256 es local; las claves están en caché)

**Constraints**: prototipo, lo más simple posible; sin tabla de auditoría; sin pantalla de gestión de
administradores; el client ID no existe todavía (todo debe construirse y probarse sin él); nada de guion
largo (CLAUDE.md); Consulta y `/query` sin cambios

**Scale/Scope**: 5 personas, 2 unidades; 29 requerimientos funcionales en 6 historias

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación | Estado |
|---|---|---|
| I. Almacenamiento y consulta desacoplados | El control de acceso vive en la API (único punto de contacto); el panel y la Consulta siguen siendo clientes. Las claves de artefacto no cambian. | Cumple |
| II. Pipeline modular e intercambiable | No se toca el pipeline. La fuente de claves de firma es una dependencia sustituible (producción: Microsoft; pruebas: claves locales), en el mismo espíritu. | Cumple |
| III. Independencia de proveedor de LLM | No aplica. | Cumple |
| IV. Extensibilidad de dominios sin fricción | Un dominio nuevo creado por alguien de una unidad queda dentro de su alcance al instante, sin migrar nada. | Cumple |
| V. Trazabilidad de respuestas | No aplica a las respuestas; se agrega trazabilidad de quién administra. | Cumple |
| Restricción: datos sensibles | Es precisamente el "mecanismo de control de acceso" que esa restricción pide antes de exponer actas con datos personales a más de una persona. | Cumple |
| Restricción: stack base | Sin cambios de stack; se actualiza `docs/ARQUITECTURA.md`. | Cumple |
| Alcance incremental | El pipeline base ya está validado en producción; la autenticación es la siguiente capa. | Cumple |

**Re-check post-diseño**: sin cambios. El diseño ([data-model.md](data-model.md),
[contracts/](contracts/)) no introduce violaciones; no hay entradas en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/004-acceso-panel-tec/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones técnicas
├── data-model.md        # Fase 1: tablas, Principal y reglas de alcance
├── quickstart.md        # Fase 1: guía de validación (con lo pendiente de TI)
├── contracts/
│   ├── api-acceso.md    # credenciales, códigos de error, /me y comportamiento por ruta
│   └── ui-panel.md      # pantallas, estados y mensajes del inicio de sesión
├── checklists/
│   └── requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                       # + entra_tenant_id, entra_client_id, entra_require_mfa
├── access/
│   ├── errors.py                   # AuthError (estado, mensaje y code)
│   ├── entra.py                    # validar token de identidad (sin HTTP de FastAPI) + origen de claves
│   ├── admins.py                   # lista de administradores: agregar, listar, desactivar, buscar
│   ├── scope.py                    # Principal y reglas de alcance (dominio, artefacto, unidad)
│   └── audit.py                    # línea JSON por escritura (logger "mia.admin")
├── api/
│   ├── security.py                 # require_admin ahora devuelve Principal; optional_admin; AuthError
│   ├── main.py                     # manejador de AuthError (detail + code); CORS permite Authorization
│   └── routes/
│       ├── me.py                   # GET /me
│       ├── inventory.py            # filtra por alcance; escrituras validan alcance
│       ├── domains.py              # idem; GET /domains y documentos con sesión
│       ├── artifacts.py            # lista y escrituras por alcance; bloque global solo global
│       └── usage.py                # filtros de artefactos por alcance; saldo solo global
├── usage/aggregate.py              # artifact_ids vacío significa "ninguno", None significa "todos"
└── storage/
    ├── models.py                   # + Admin, AdminUnit
    └── migrations/versions/0003_administradores.py

scripts/admin.py                    # agregar, listar, desactivar (sobre mia.access.admins)
scripts/idp_simulado.py             # solo desarrollo: IdP simulado y API con claves inyectadas
tests/unit/                         # test_entra, test_admins, test_scope, test_auth_routes,
                                    # test_admin_script; ajustes a test_security y los que usan `admin`
tests/conftest.py                   # fixtures: clave RSA local, fábrica de tokens, `as_user`

web/admin/
├── package.json                    # + @azure/msal-browser
├── Dockerfile                      # + ARG VITE_ENTRA_CLIENT_ID (opcional)
└── src/
    ├── auth/
    │   ├── config.ts               # configuración de MSAL desde variables (pura)
    │   ├── capabilities.ts         # qué puede hacer una sesión según GET /me (pura)
    │   ├── session.ts              # MSAL: iniciar, renovar, cerrar; estado observable
    │   └── errors.ts               # error de la API -> estado de acceso y mensaje (puro)
    ├── api/client.ts               # Bearer con renovación y un reintento; sin X-Admin-Key
    ├── components/
    │   ├── LoginScreen.tsx         # pantalla de inicio de sesión y de rechazo
    │   └── Layout.tsx              # correo, alcance y cerrar sesión; sin AdminKeyDialog
    └── modules/                    # sin guardas por clave; oculta lo exclusivo de global

docs/                               # ARQUITECTURA, OPERACION, REGISTRO_APLICACION_TEC, README
.env.example, deploy/railway/variables.example.env, web/admin/README.md
```

**Structure Decision**: la lógica de acceso vive en `src/mia/access/` sin dependencias de HTTP, como el
resto de esa carpeta, para probarla sin levantar la API. `security.py` es la única pieza que traduce a
códigos HTTP. En el panel, `auth/` aísla a MSAL detrás de tres funciones para que lo demás no lo conozca.

## Orden de implementación sugerido

1. **Base de la API** (bloquea todo): modelos y migración 0003, `access/entra.py`, `admins.py`,
   `scope.py`, `audit.py`, `security.py` con `Principal`, `GET /me`, fixtures de pruebas.
2. **US3 (script)**: `scripts/admin.py` sobre `admins.py`.
3. **US1 y US2, lado API**: alcance en inventario, dominios, carpetas y documentos; errores con `code`.
4. **US4**: alcance en artefactos y en Uso (incluye `artifact_ids` vacío, CSV, detalle y saldo).
5. **US5 y US6**: `ADMIN_KEY` como automatización (503 a 401 cuando está vacía) y registro de escrituras.
6. **Panel**: `auth/`, cliente de la API, pantalla de inicio de sesión, Layout, adaptación de los tres
   módulos y pruebas de Vitest.
7. **Servidor de identidad simulado** y validación en navegador (quickstart).
8. **Documentación y cierre**: ARQUITECTURA, OPERACION, REGISTRO_APLICACION_TEC, READMEs, ejemplos de
   variables; pytest, ruff, typecheck, test y build en verde.

**Despliegue**: todo en `dev`. Sin merge ni despliegue sin que se pida. Al desplegar, el orden importa
(ver quickstart): primero la API con la migración, el script `admin.py` para cargar correos y
`ENTRA_CLIENT_ID`, y recién entonces el panel con `VITE_ENTRA_CLIENT_ID`; mientras tanto la clave de
automatización sigue sirviendo a los scripts.
