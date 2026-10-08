# Contrato: Artefactos y accesos

Todas las rutas exigen `X-Admin-Key` (401 / 503 como en [api-inventario.md](api-inventario.md)).
La clave completa de un artefacto solo aparece en la respuesta de crear y de regenerar; nunca en
listados.

## Forma de un artefacto

```json
{
  "id": "a-1",
  "name": "Consulta administrativa Postgrados Computación",
  "description": "",
  "key_prefix": "mia_k3f9",
  "active": true,
  "access": {"all_domains": false, "unit_ids": ["u-1"], "domain_ids": []},
  "allowed_domain_count": 7,
  "modes": ["literal", "razonamiento"],
  "daily_cap_usd": 1.5,
  "reasoning_daily_cap_usd": 1.0,
  "today": {"spent_usd": 0.9, "reasoning_spent_usd": 0.7, "cap_reached": false, "reasoning_cap_reached": false},
  "queries_last_7_days": 164,
  "created_at": "2026-10-09T15:00:00Z"
}
```

## GET /artifacts

```json
{
  "artifacts": [ "<artefacto>" ],
  "global": {"daily_cap_usd": 3.0, "spent_today_usd": 1.2, "sum_of_artifact_caps_usd": 2.5, "caps_exceed_global": false},
  "modes": [
    {"id": "literal", "name": "Literal", "available": true, "avg_cost_usd_7d": 0.0021},
    {"id": "razonamiento", "name": "Con razonamiento", "available": true, "avg_cost_usd_7d": 0.019}
  ]
}
```

- `caps_exceed_global` alimenta el aviso de ART-10.
- `avg_cost_usd_7d` (nulo sin datos) permite mostrar el costo aproximado de cada modo (ART-4) y cuántas
  consultas alcanza un tope (ART-8): `tope / costo medio`.

## POST /artifacts

Request:

```json
{
  "name": "Consulta administrativa Postgrados Computación",
  "description": "",
  "access": {"all_domains": false, "unit_ids": ["u-1"], "domain_ids": []},
  "modes": ["literal", "razonamiento"],
  "daily_cap_usd": 0.5,
  "reasoning_daily_cap_usd": null
}
```

`daily_cap_usd` es opcional al crear (por defecto 0.50). **201** con el artefacto más `"key": "mia_..."`
(única vez). **409** nombre repetido. **422**: sin acceso a ningún dominio, sin modos, modo
desconocido, tope menor o igual a 0, tope de razonamiento mayor que el total, o unidades o dominios
inexistentes.

## PATCH /artifacts/{artifact_id}

Cualquier subconjunto de `description`, `access`, `modes`, `daily_cap_usd`,
`reasoning_daily_cap_usd` y `active`. Mismas validaciones que al crear. **200** con el artefacto.
Rige desde la consulta siguiente (ART-5). **404** si no existe.

## POST /artifacts/{artifact_id}/key

Regenera la clave: la anterior deja de funcionar de inmediato. **200** `{"key": "mia_...", "key_prefix": "mia_p81c"}`.

## No hay DELETE

Un artefacto se desactiva (`PATCH {"active": false}`), así su registro de consultas se conserva
(ART-7).
