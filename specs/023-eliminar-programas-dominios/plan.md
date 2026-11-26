# Implementation Plan: Eliminación de programas y dominios

**Branch**: `dev` (sin rama propia) | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/023-eliminar-programas-dominios/spec.md`

## Summary

Se pueden crear programas y dominios pero no quitarlos. Se agrega su eliminación desde el panel y la API, solo cuando están vacíos (programa sin dominios ni asociaciones; dominio sin documentos ni carpetas), con una comprobación previa que dice en lenguaje corriente qué lo impide o qué se verá afectado, y la posibilidad de cambiar el programa de un usuario de la Consulta.

Piezas:

1. Un servicio `src/mia/access/structure.py`: calcula impedimentos y afectados, y elimina en una transacción (bloqueo de la fila, comprobación, borrado, limpieza del almacén de vectores y confirmación).
2. Rutas `GET .../deletion` y `DELETE` para `/units/{id}` y `/domains/{id}` en `src/mia/api/routes/structure.py`, y `unit_id` en `PATCH /consulta-users/{id}`.
3. Tabla `deleted_domains` (migración `0016`, aditiva) para que el historial de Uso siga nombrando los dominios eliminados.
4. Panel: botones de eliminar en el Inventario con su ventana, y "Cambiar programa" en Usuarios de la Consulta.

## Technical Context

**Language/Version**: Python 3.12 (API) y TypeScript con React y Mantine (panel)

**Primary Dependencies**: ninguna nueva.

**Storage**: SQL (SQLite en desarrollo, Postgres en producción): tabla nueva `deleted_domains`. Qdrant: un método nuevo de lectura en `VectorStore`. Ver [data-model.md](data-model.md).

**Testing**: `pytest` en `tests/unit/` (con claves foráneas activadas en SQLite en las pruebas de carreras) y Vitest en `web/admin/` con el patrón `renderToString` que ya se usa.

**Target Platform**: los despliegues de hoy; sin servicios ni variables nuevas.

**Project Type**: web-service y panel de administración.

**Performance Goals**: comprobar y eliminar en menos de 2 s con el volumen actual (decenas de dominios).

**Constraints**: sin cascada de contenido ni papelera; mismos alcances que crear; textos sin términos técnicos; sin guiones largos.

**Scale/Scope**: un puñado de programas, decenas de dominios.

## Constitution Check

| Principio / restricción | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | Cumple: es una operación de la API; los artefactos ven el cambio en la consulta siguiente. |
| II. Pipeline modular | Cumple: el método nuevo va en la interfaz `VectorStore`, no abstracto. |
| III. Independencia de LLM | No interviene ningún modelo. |
| IV. Extensibilidad de dominios | Cumple: crear sigue igual y un nombre eliminado queda libre. |
| V. Trazabilidad | Cumple: el historial de Uso conserva el nombre de lo eliminado (research R4). |
| Stack y documentación viva | Mismo stack; se actualizan ARQUITECTURA, OPERACION y `web/admin/README.md`. |

Sin violaciones. Tras el diseño (Phase 1) no cambia: la única novedad de esquema es una tabla aditiva.

## Project Structure

### Documentation (this feature)

```text
specs/023-eliminar-programas-dominios/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/eliminar-estructura-api.md
├── contracts/panel.md
└── tasks.md
```

### Source Code (repository root)

```text
src/mia/
├── access/structure.py                 # NUEVO: impedimentos, afectados y eliminación
├── api/routes/structure.py             # NUEVO: GET deletion y DELETE de programas y dominios
├── api/routes/consulta_users.py        # PATCH acepta unit_id
├── api/routes/domains.py, web_pages.py # carrera: dominio eliminado durante una carga
├── api/main.py                         # registra el router
├── storage/models.py                   # + DeletedDomain
├── storage/migrations/versions/0016_dominios_eliminados.py
├── storage/vector_store.py             # + document_ids_in_domain
└── usage/log.py                        # nombre de un dominio eliminado

tests/unit/test_structure_delete.py, test_consulta_users_unit.py, test_migrations.py (ampliado)

web/admin/src/
├── api/structure.ts, api/consultaUsers.ts
├── modules/inventario/EliminarEstructuraDialog.tsx (+ prueba), InventarioPage.tsx
└── modules/usuarios/CambiarProgramaDialog.tsx (+ prueba), UserCard.tsx, UsuariosPage.tsx
```

**Structure Decision**: la lógica va en `access/` junto a los permisos y relaciones que consulta; las rutas, en un archivo propio.

## Complexity Tracking

Sin violaciones que justificar.
