# Implementation Plan: Historial de chats con usuarios básicos en la Consulta web

**Branch**: `dev` (sin rama propia por decisión del usuario) | **Date**: 2026-11-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/015-historial-chats/spec.md`

## Summary

La Consulta web no guarda nada: la conversación vive en la memoria de la página y la API reconoce solo al artefacto por su clave. Esta feature agrega, **sin dependencias nuevas y sin tocar el pipeline**, usuarios básicos de la Consulta y, sobre ellos, un historial de conversaciones guardado en el servidor.

Cuatro piezas, todas en la API (la Consulta y el panel son clientes, principio I):

1. **Usuarios y sesiones** (`src/mia/chat/`): usuario y contraseña creados por la administración; contraseña con `hashlib.scrypt` y sal propia; sesión con un token aleatorio opaco que se guarda solo como hash SHA-256 en una tabla (así se puede cerrar al instante); límite de intentos fallidos por usuario y por origen en memoria. El token viaja en un encabezado propio, `X-Session-Token`, que se **suma** a `X-Artifact-Key` y nunca la reemplaza ([contracts/auth-api.md](contracts/auth-api.md)).
2. **Administración de usuarios**: rutas `/consulta-users` y un módulo "Usuarios de la Consulta" en el panel, con el alcance por programa que ya existe; la contraseña se muestra una sola vez ([contracts/usuarios-admin-api.md](contracts/usuarios-admin-api.md)).
3. **Conversaciones guardadas por el servidor**: `POST /query` con sesión crea o continúa una conversación, **carga ella misma el historial desde lo guardado** (con el recorte de la memoria de la 014) y agrega la vuelta respondida; así lo que se retoma es siempre lo guardado, no lo que diga el cliente. Rutas `/conversations` para listar, abrir y borrar (una o todas), y limpieza por retención ([contracts/conversaciones-api.md](contracts/conversaciones-api.md), [contracts/query-con-sesion.md](contracts/query-con-sesion.md)).
4. **Consulta web**: inicio y cierre de sesión, lista de conversaciones, retomar, borrar, aviso de retención; con clave fija sigue funcionando y la sesión es opcional, salvo que el artefacto la exija (`artifacts.require_login`).

Una migración aditiva (`0009`): `consulta_users`, `consulta_sessions`, `conversations`, `conversation_turns` y `artifacts.require_login`. `POST /query` sin sesión responde exactamente igual que hoy y no guarda nada. El bot de WhatsApp no cambia. No usa LangChain ni LangGraph.

## Technical Context

**Language/Version**: Python 3.12+ (la API); TypeScript con React 19 y Vite (Consulta y panel)

**Primary Dependencies**: ninguna nueva. Contraseñas con `hashlib.scrypt` y `hmac.compare_digest` (biblioteca estándar); tokens con `secrets`; FastAPI, SQLAlchemy y Alembic como hoy; Mantine en la Consulta y el panel.

**Storage**: SQL de la aplicación (SQLite en desarrollo, Postgres en producción): cuatro tablas nuevas y una columna booleana en `artifacts`, **migración aditiva `0009`** ([data-model.md](data-model.md)). Qdrant y los documentos no cambian.

**Testing**: `pytest` en `tests/unit/` (contraseñas, sesiones, límite de intentos, rutas de usuarios, de autenticación y de conversaciones, `POST /query` con y sin sesión, retención, migración, aislamiento y privacidad) con un archivo por historia; Vitest sin DOM en la Consulta y el panel (funciones puras y `renderToString`), como la 014; la batería del MVP (19 de 19) y la prueba de la migración con `scripts/probar_migracion.py`.

**Target Platform**: los mismos despliegues de hoy (API, Consulta y panel en Railway); variables nuevas opcionales con valores por defecto.

**Project Type**: web-service (la API) más dos sitios estáticos (Consulta y panel).

**Performance Goals**: guardar la vuelta suma una escritura pequeña después de responder (SC-009: menos de 1 s en el 95 %); `scrypt` con n=2^14 tarda unos 70 ms por inicio de sesión, que es aceptable porque solo ocurre al entrar; la validación de la sesión en cada consulta es una lectura por índice (más una escritura de renovación como máximo una vez por minuto).

**Constraints**: `POST /query` anónimo idéntico al de hoy (forma, resultado, costo, sin guardar); ninguna contraseña en claro en ninguna parte; mensajes de inicio de sesión que no revelan si el usuario existe; aislamiento total por usuario y la administración nunca lee el texto; guardar nunca hace fallar una consulta; los topes de gasto y los permisos del artefacto no cambian; sin guiones largos; la batería del MVP 19 de 19.

**Scale/Scope**: decenas de usuarios y cientos de conversaciones (hasta 200 vueltas por conversación y 100 conversaciones por usuario). Toca `src/mia/config.py`, `src/mia/storage/{models.py,migrations/versions/0009_*.py}`, `src/mia/chat/` (nuevo), `src/mia/api/{main.py,security.py}`, `src/mia/api/routes/{auth.py,consulta_users.py,conversations.py,query.py,artifacts.py,config.py}`, `web/consulta/src/`, `web/admin/src/` y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple. Los usuarios, las sesiones y las conversaciones viven en la API; la Consulta y el panel son clientes. El almacenamiento de dominios (Qdrant) no se duplica ni se toca. |
| II. Pipeline modular e intercambiable | Cumple. No se toca ninguna etapa del pipeline ni sus interfaces; el historial guardado alimenta el parámetro `history` que la 014 ya definió. |
| III. Independencia de proveedor de LLM | Cumple. No interviene ningún proveedor ni modelo nuevo. |
| IV. Extensibilidad de dominios | Cumple. Un dominio nuevo no requiere nada de esta feature. |
| V. Trazabilidad de respuestas | Cumple y ayuda: cada vuelta guardada conserva las fuentes citadas (dominio y documento) tal como se mostraron. |
| Datos sensibles | **Se vigila.** Se guardan las preguntas y respuestas de personas con sesión, que pueden tener datos personales. Mitigación: aislamiento total por usuario, administración sin acceso al texto, retención automática (90 días por defecto), borrado por la persona y guardado desactivable (retención 0); la consulta anónima sigue sin guardar nada. |
| Stack base | Mismo Python, FastAPI, SQL y Qdrant; sin dependencias nuevas. |
| Alcance incremental | Cumple: el MVP ya está validado y en producción, que es la condición de la constitución para agregar un mecanismo de autenticación. Se actualizan ARQUITECTURA, OPERACION (variables, usuarios, retención, privacidad), los README de la Consulta y el panel. |

**Desviación a justificar (no es una violación de la constitución):** la feature 014 dejó dicho que el servidor no guarda ninguna conversación (research R10 de esa spec). Esta feature lo cambia **solo para quien inicia sesión**, por decisión del usuario del 2026-11-04. Está en la tabla de complejidad.

**Re-evaluación tras el diseño (Phase 1)**: sin cambios. Los puntos que merecen vigilancia son el aislamiento (se prueba por todos los caminos), que ninguna ruta de administración devuelva texto de conversaciones (se prueba), y el límite de intentos detrás del proxy de Railway (research R6).

## Project Structure

### Documentation (this feature)

```text
specs/015-historial-chats/
├── plan.md              # Este archivo
├── research.md          # Decisiones (R1 a R14)
├── data-model.md        # Tablas, validaciones y ajustes
├── quickstart.md        # Cómo validar la feature
├── contracts/
│   ├── auth-api.md                 # /auth: inicio y cierre de sesión, cambio de contraseña
│   ├── usuarios-admin-api.md       # /consulta-users y el módulo del panel
│   ├── conversaciones-api.md       # /conversations: listar, abrir y borrar
│   └── query-con-sesion.md         # POST /query con sesión, /config y artifacts.require_login
└── tasks.md             # Lo genera /speckit-tasks (no este comando)
```

### Source Code (repository root)

```text
src/mia/
├── config.py                        # + chat_retention_days, chat_max_turns, chat_max_conversations, session_hours, session_max_days, login_*, password_min_chars, trust_forwarded_for
├── chat/                            # NUEVO
│   ├── passwords.py                 # hash_password, verify_password (scrypt), contraseña generada, validación de longitud
│   ├── throttle.py                  # límite de intentos fallidos por usuario y por origen (en memoria, acotado)
│   ├── sessions.py                  # crear, validar (con renovación), cerrar y cerrar todas las sesiones de un usuario
│   ├── service.py                   # conversaciones: crear, cargar historial, agregar vuelta, listar, abrir, borrar; títulos
│   └── retention.py                 # limpieza por retención y de sesiones vencidas (al arrancar y cada hora con las peticiones)
├── storage/
│   ├── models.py                    # + ConsultaUser, ConsultaSession, Conversation, ConversationTurn; Artifact.require_login
│   └── migrations/versions/0009_historial_de_chats.py
└── api/
    ├── main.py                      # + routers, CORS permite X-Session-Token, limpieza al arrancar
    ├── security.py                  # + optional_user / require_user (X-Session-Token)
    └── routes/
        ├── auth.py                  # NUEVO: POST /auth/login, POST /auth/logout, GET /auth/me, POST /auth/password
        ├── consulta_users.py        # NUEVO: administración de usuarios (panel)
        ├── conversations.py         # NUEVO: GET/DELETE /conversations, GET/DELETE /conversations/{id}
        ├── query.py                 # QueryRequest.conversation_id; con sesión carga el historial y guarda la vuelta; run_query(session_missing) y _reject(code) para login_required sin afectar al bot
        ├── artifacts.py             # require_login en crear, editar y listar
        └── config.py                # artifact.require_login y chat (guardado activo y retención)

web/consulta/src/
├── api/{session.ts,auth.ts,conversations.ts}   # NUEVOS: token en el navegador, login y conversaciones; client.ts agrega X-Session-Token
├── components/Header.tsx            # muestra el menú de cuenta o "Iniciar sesión"
├── state/chat.ts                    # NUEVO: de lo guardado a Exchange, qué enviar, errores de sesión y de conversación, qué pantalla mostrar (con pruebas en state/chat.test.ts)
├── components/{LoginPanel.tsx,ConversationList.tsx,AccountMenu.tsx}   # NUEVOS (con sus pruebas .test.tsx)
└── App.tsx                          # sesión, lista, retomar, borrar y aviso de retención

web/admin/src/
├── api/{types.ts,consultaUsers.ts}  # + tipos y llamadas; Artifact.require_login
└── modules/
    ├── usuarios/                    # NUEVO: UsuariosPage, UserForm, UserCard, PasswordReveal, usuariosUtils
    ├── artefactos/{ArtifactForm.tsx,ArtifactCard.tsx}   # + "Exigir inicio de sesión"
    └── index.tsx                    # + módulo "Usuarios de la Consulta"

tests/unit/
├── test_chat_passwords.py · test_chat_throttle.py · test_chat_sessions.py     # piezas puras
├── test_consulta_users_admin.py     # US1
├── test_auth_routes.py              # US2
├── test_query_chat.py · test_conversations_api.py                              # US3
├── test_query_chat_retomar.py       # US4
├── test_chat_retention.py           # US5
├── test_chat_privacidad.py          # US6
├── test_query_chat_compat.py        # US7
└── test_migrations.py               # 0009
docs/ARQUITECTURA.md, docs/OPERACION.md, web/consulta/README.md, web/admin/README.md   # actualizados
```

**Structure Decision**: un paquete nuevo y pequeño, `mia.chat`, para que ninguna regla de usuarios ni de conversaciones se mezcle con el pipeline ni con `query.py`; las rutas son delgadas. `query.py` solo cambia en dos puntos acotados (cargar el historial guardado antes de buscar y guardar la vuelta después de responder), y ambos se saltan por completo sin sesión.

## Complexity Tracking

| Desviación | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| El servidor guarda conversaciones (revierte la decisión de la 014 de no guardar nada) | Es el objetivo de la feature: ver y retomar conversaciones desde cualquier dispositivo | Guardarlas solo en el navegador no viaja entre dispositivos, se pierde al limpiar datos y no necesitaría usuarios, que es lo que se pidió. Se limita a quien inicia sesión, con retención, borrado y aislamiento. |
| Tabla de sesiones en el servidor en vez de un token firmado sin estado | Cerrar la sesión al instante (cerrar sesión, desactivar al usuario, restablecer la contraseña) | Un token firmado sin estado no se puede revocar antes de vencer sin una lista de revocaciones, que sería igual de compleja. |
