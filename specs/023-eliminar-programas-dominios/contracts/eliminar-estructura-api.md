# Contrato: eliminar programas y dominios

Todas requieren administración (cuenta del panel o `X-Admin-Key`). Una clave de artefacto no sirve (401).

## `GET /units/{unit_id}/deletion` y `GET /domains/{domain_id}/deletion`

Qué pasaría al eliminar. No cambia nada.

```json
{
  "name": "Dominio de prueba",
  "can_delete": false,
  "blockers": [{ "kind": "documents", "count": 3, "names": [], "hint": "Elimina primero sus documentos (puedes usar Seleccionar)." }],
  "affects": [{ "kind": "artifacts", "count": 1, "names": ["Consulta de Computación"], "hint": "Dejarán de consultar este dominio." }]
}
```

- `blockers[].kind`: dominio `documents`, `folders`; programa `domains`, `consulta_users`, `admins`, `artifacts`.
- `affects[].kind` (solo dominios): `artifacts` (con acceso puntual), `empty_artifacts` (se quedan sin ningún dominio), `bots`.
- `names` lista como máximo 10; `count` es el total. Los artefactos fuera del alcance cuentan pero no se nombran.

## `DELETE /units/{unit_id}` (solo alcance global) y `DELETE /domains/{domain_id}` (global o su programa)

| Respuesta | Cuándo |
|---|---|
| 204 | Eliminado |
| 403 | Fuera de alcance (queda en el registro de administración) |
| 404 | No existe (también al repetir) |
| 409 | Hay impedimentos, o algo cambió mientras se eliminaba. `detail`: frase con qué lo impide y cómo resolverlo |
| 503 | Solo dominios: no se pudo revisar el almacén de búsqueda; nada cambió |

Registro de administración: `unit.delete` / `domain.delete` con el id y el nombre.

## `PATCH /consulta-users/{user_id}`

Cuerpo: `{"active"?: bool, "unit_id"?: string | null}`. `unit_id` ausente no cambia; `null` deja sin programa (solo global). 404 si el usuario está fuera del alcance o el programa no existe; 403 si el destino está fuera del alcance.
