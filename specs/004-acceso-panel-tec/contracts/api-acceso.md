# Contrato de la API: acceso de administración

Lo que cambia respecto de [specs/002-panel-administracion/contracts](../../002-panel-administracion/contracts/).
`/query`, `/query/{id}/feedback`, `GET /config` y `GET /domains` con `X-Artifact-Key` **no cambian**.

## Credenciales de administración

Una petición de administración lleva una de estas dos:

| Credencial | Encabezado | Quién la usa | Alcance |
|---|---|---|---|
| Token de identidad de Microsoft | `Authorization: Bearer <id_token>` | el panel | el del administrador en la lista |
| Clave de automatización | `X-Admin-Key: <ADMIN_KEY>` | los scripts | global |

Si llegan ambas, vale `Authorization`. Con `ADMIN_KEY` vacía, `X-Admin-Key` se ignora.

### Validación del token (en este orden)

1. `ENTRA_CLIENT_ID` configurado; si no, 503 `login_not_configured`.
2. Cabecera: algoritmo `RS256` (cualquier otro, incluido `none`, es `invalid_token`) y un `kid`.
3. Firma contra la clave del directorio con ese `kid` (503 `identity_unavailable` si no hay claves).
4. `iss == https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0`, `aud == ENTRA_CLIENT_ID`,
   `tid == ENTRA_TENANT_ID`, y `exp` e `iat` presentes. Margen de reloj de 60 segundos.
5. Si `ENTRA_REQUIRE_MFA`: `amr` contiene `"mfa"`; si no, 403 `mfa_required`.
6. Correo: `email` o, si falta, `preferred_username`, en minúsculas. Sin correo: `invalid_token`.
7. El correo está en `admins` con `active = true`; si no, 403 `not_authorized`.

### Errores de acceso

Cuerpo: `{"detail": "<mensaje en español>", "code": "<código>"}`.

| Estado | `code` | Cuándo |
|---|---|---|
| 401 | `unauthenticated` | sin credenciales, o `X-Admin-Key` incorrecta o `ADMIN_KEY` vacía |
| 401 | `invalid_token` | firma, emisor, audiencia, tenant, algoritmo o formato inválidos |
| 401 | `token_expired` | `exp` vencido |
| 403 | `mfa_required` | el token no declara segundo factor |
| 403 | `not_authorized` | identidad válida pero correo fuera de la lista o desactivado |
| 403 | `out_of_scope` | escritura sobre una unidad, dominio o acceso fuera del alcance |
| 403 | `global_only` | operación exclusiva del alcance global (crear unidad, saldo) |
| 503 | `login_not_configured` | token recibido y la instancia no tiene `ENTRA_CLIENT_ID` |
| 503 | `identity_unavailable` | no hay claves del directorio y no se pudieron obtener |

Los demás errores de las rutas (409, 422, 404 de objetos inexistentes...) no cambian.

## Ruta nueva

### `GET /me`

Requiere credencial de administración. Lo usa el panel después de iniciar sesión.

```json
{
  "email": "coordinadora@itcr.ac.cr",
  "is_global": false,
  "units": [{"id": "…", "name": "Computación"}],
  "source": "entra"
}
```

Con la clave de automatización: `email: null`, `is_global: true`, `units: []`, `source: "automation"`.
Un correo fuera de la lista responde 403 `not_authorized` (el panel muestra su mensaje).

## Comportamiento por ruta

"Sin credencial" siempre es 401 `unauthenticated`. "Ajeno" es fuera del alcance de la persona.

| Ruta | Cambio |
|---|---|
| `GET /inventory` | **Ahora exige credencial.** Devuelve solo las unidades en alcance y, con ellas, sus dominios, carpetas y documentos. `unassigned_domains` vacío salvo global. |
| `GET /units` | **Ahora exige credencial.** Solo las unidades en alcance. |
| `POST /units` | Solo global (403 `global_only`). |
| `GET /domains` | Con `X-Artifact-Key`: igual que hoy. Sin ella: **exige credencial de administración** y devuelve los dominios en alcance. |
| `POST /domains` | La unidad debe estar en alcance (403 `out_of_scope`). `visible_to` solo menciona artefactos en alcance. |
| `GET /domains/{id}/documents` | **Ahora exige credencial.** Dominio ajeno: 404. |
| `POST /domains/{id}/folders` | Dominio ajeno: 403 `out_of_scope`. |
| `PATCH` y `DELETE /folders/{id}` | Carpeta de dominio ajeno: 403 `out_of_scope`. |
| `POST /domains/{id}/documents` | Dominio ajeno: 403 `out_of_scope`. |
| `GET /artifacts` | Solo los artefactos en alcance. `global` es `null` y los costos medios por modo salen de sus artefactos, salvo global. |
| `POST /artifacts` | El acceso debe poder darse dentro del alcance (403 `out_of_scope`): `all_domains` y unidades ajenas son solo global. |
| `PATCH /artifacts/{id}` | Artefacto fuera de alcance: 404. El acceso nuevo, si viene, debe poder darse (403 `out_of_scope`). |
| `POST /artifacts/{id}/key` | Artefacto fuera de alcance: 404. |
| `GET /usage` | Filtra por los artefactos en alcance; los `artifact_id` pedidos se intersectan. |
| `GET /usage/queries` (JSON y CSV) | Idem. |
| `GET /usage/queries/{id}` | Consulta de un artefacto fuera de alcance, o sin artefacto: 404. |
| `GET /usage/balance` | Solo global (403 `global_only`). |
| `GET /health`, `GET /config` | Públicos, sin cambios. |

`ArtifactsOut.global` pasa a ser `GlobalOut | null`. Es el único cambio de forma de una respuesta
existente.

## Registro de escrituras

Línea JSON por el logger `mia.admin`, una por escritura exitosa y por rechazo `out_of_scope`:

```json
{"ts":"2026-10-10T15:04:05Z","actor":"coordinadora@itcr.ac.cr","action":"domain.create","target":"<id>","detail":"Currículum","result":"ok"}
```

`actor` es el correo o `"automatizacion"`. Acciones: `unit.create`, `domain.create`, `folder.create`,
`folder.rename`, `folder.delete`, `document.upload`, `artifact.create`, `artifact.update`,
`artifact.key_regenerate`. Con `result` `"ok"` o `"rechazado"`. Nunca contiene tokens, `ADMIN_KEY` ni
claves de artefacto.

## CORS

`allow_headers` suma `Authorization`. Los códigos de error y `detail` ya son legibles desde el sitio.
