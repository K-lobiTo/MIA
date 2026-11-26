---
description: "Tareas para la eliminación de programas y dominios"
---

# Tasks: Eliminación de programas y dominios

**Input**: Design documents from `/specs/023-eliminar-programas-dominios/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: sí, como en las features anteriores del proyecto (están en plan.md).

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

No hay: sin dependencias, variables ni servicios nuevos.

## Phase 2: Foundational

- [X] T001 Agregar el modelo `DeletedDomain` (`id` texto clave primaria, `label` texto, `deleted_at` UTC; sin claves foráneas) en src/mia/storage/models.py
- [X] T002 Crear la migración aditiva y reversible src/mia/storage/migrations/versions/0016_dominios_eliminados.py (revises 0015)
- [X] T003 Actualizar la revisión final esperada (0016) y probar subida y bajada de la 0016 en tests/unit/test_migrations.py
- [X] T004 [P] Agregar `VectorStore.document_ids_in_domain(domain_id) -> set[str]` (no abstracto) y su implementación en Qdrant, recorriendo todas las páginas, en src/mia/storage/vector_store.py, con prueba en tests/unit/test_vector_store.py

**Checkpoint**: esquema y almacén listos.

## Phase 3: User Story 1 - Quitar un dominio creado por error (P1) 🎯 MVP

**Goal**: eliminar un dominio vacío desde el panel y la API.

**Independent Test**: crear un dominio, eliminarlo y crear otro con el mismo nombre.

- [X] T005 [US1] Pruebas de comprobación y eliminación de dominios (vacío, con documentos en cualquier estado, con carpetas, alcance, clave de artefacto, repetir da 404, accesos puntuales borrados, fragmentos huérfanos borrados y fragmentos de otro dominio reetiquetados, almacén caído da 503 sin cambios) en tests/unit/test_structure_delete.py
- [X] T006 [US1] Crear el servicio de dominios (impedimentos, afectados `artifacts`/`empty_artifacts`/`bots` con máximo 10 nombres y sin nombrar artefactos fuera del alcance; eliminación con bloqueo de fila y relectura tras bloquear (quien llega segundo recibe 404), `DeletedDomain`, limpieza del almacén y 409 ante `IntegrityError`) en src/mia/access/structure.py
- [X] T007 [US1] Rutas `GET /domains/{domain_id}/deletion` y `DELETE /domains/{domain_id}` con registro `domain.delete` en src/mia/api/routes/structure.py, y registrarlas en src/mia/api/main.py
- [X] T008 [US1] Que una carga de archivo o de página web, o la creación de una carpeta, cuyo dominio se eliminó mientras tanto responda 404 "El dominio ya no existe." sin dejar el archivo, en src/mia/api/routes/domains.py, web_pages.py e inventory.py, con prueba en tests/unit/test_structure_delete.py
- [X] T009 [P] [US1] Hooks de comprobación y eliminación (invalidan inventario, artefactos y usuarios) en web/admin/src/api/structure.ts
- [X] T010 [US1] Ventana de eliminación con su contenido puro (impedimentos, o afectados y "No se puede deshacer.") en web/admin/src/modules/inventario/EliminarEstructuraDialog.tsx, con prueba EliminarEstructuraDialog.test.tsx
- [X] T011 [US1] Botón "Eliminar" por dominio (sin programa: solo alcance global) en web/admin/src/modules/inventario/InventarioPage.tsx

## Phase 4: User Story 2 - Quitar un programa creado por error (P1)

**Goal**: eliminar un programa vacío y sin asociaciones.

**Independent Test**: crear un programa, eliminarlo y crear otro con el mismo nombre.

- [X] T012 [US2] Pruebas de programas (vacío, con dominios, usuarios de la Consulta activos o desactivados, cuentas de administración, artefactos; solo alcance global y rechazo registrado) en tests/unit/test_structure_delete.py
- [X] T013 [US2] Impedimentos `domains`, `consulta_users`, `admins`, `artifacts` y eliminación de programas en src/mia/access/structure.py
- [X] T014 [US2] Rutas `GET /units/{unit_id}/deletion` y `DELETE /units/{unit_id}` con registro `unit.delete` en src/mia/api/routes/structure.py
- [X] T015 [US2] Botón "Eliminar programa" (solo alcance global) en web/admin/src/modules/inventario/InventarioPage.tsx

## Phase 5: User Story 3 - Reasignar a las personas de un programa (P1)

**Goal**: cambiar o quitar el programa de un usuario de la Consulta.

**Independent Test**: moverlo y eliminar el programa anterior.

- [X] T016 [P] [US3] Pruebas (mover, dejar sin programa, `unit_id` ausente no cambia, programa inexistente, alcance de programa; contraseña, estado y sesiones intactos) en tests/unit/test_consulta_users_unit.py
- [X] T017 [US3] `PATCH /consulta-users/{user_id}` acepta `unit_id` (ausente no cambia; `null` solo alcance global) en src/mia/api/routes/consulta_users.py
- [X] T018 [US3] Hook para cambiar el programa en web/admin/src/api/consultaUsers.ts
- [X] T019 [US3] Ventana "Cambiar programa" en web/admin/src/modules/usuarios/CambiarProgramaDialog.tsx y botón en UserCard.tsx y UsuariosPage.tsx, con prueba en UsuariosPage.test.tsx

## Phase 6: User Story 4 - Entender por qué no se puede y qué hacer (P2)

**Goal**: cada impedimento dice cuántos, cuáles y cómo resolverlo.

- [X] T020 [US4] Pruebas de los textos: cada `kind` trae un `hint` accionable, el 409 de `DELETE` lo repite en una frase, el programa que es el único acceso de un artefacto indica darle otro o eliminarlo, y las cuentas de administración remiten a soporte técnico, en tests/unit/test_structure_delete.py
- [X] T021 [US4] Ajustar los textos de impedimentos en src/mia/access/structure.py hasta que las pruebas de T020 pasen

## Phase 7: User Story 5 - El historial y lo demás no cambian (P1)

**Goal**: el registro de Uso sigue legible y nada más cambia.

- [X] T022 [US5] Pruebas (detalle de una consulta pasada muestra "Programa / Dominio (eliminado)"; otros dominios, artefactos, claves, modos y topes intactos; artefacto sin dominios responde sin error al listar) en tests/unit/test_structure_delete.py
- [X] T023 [US5] Usar `DeletedDomain` al nombrar dominios en src/mia/usage/log.py

## Phase 8: Polish

- [X] T024 [P] Documentar rutas, servicio, tabla y método del almacén en docs/ARQUITECTURA.md
- [X] T025 [P] Documentar cómo eliminar, la migración 0016 y la vuelta atrás en docs/OPERACION.md
- [X] T026 [P] Documentar los botones y ventanas en web/admin/README.md
- [X] T027 Validar: `ruff`, `pytest`, `npm test` y `npm run build` del panel, y el recorrido de specs/023-eliminar-programas-dominios/quickstart.md contra la API local

## Dependencies & Execution Order

- Fase 2 antes que todo. US1 antes que US2 (comparten servicio, rutas y ventana).
- US3 es independiente de US1 y US2.
- US4 y US5 después de US1 y US2.
- Polish al final.

**Paralelo**: T004, T009 y T016 tocan archivos distintos; T024 a T026 también.

## Implementation Strategy

MVP: Fase 2 y US1. Después US2 y US3, que juntas permiten eliminar cualquier programa; luego US4, US5 y documentación.

## Phase 9: Convergence

- [X] T028 Responder 404 con un mensaje claro (en vez de 500) cuando el programa o un dominio se elimina mientras se crea un dominio o se crea o edita un artefacto, en src/mia/api/routes/domains.py y src/mia/api/routes/artifacts.py, con prueba per spec: Edge Cases y FR-009 (partial)
