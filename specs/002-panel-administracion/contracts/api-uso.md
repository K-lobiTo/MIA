# Contrato: Uso

Todas las rutas exigen `X-Admin-Key`. Parámetros comunes de filtro:

| Parámetro | Valores | Por defecto |
|---|---|---|
| `period` | `today`, `7d`, `30d`, `custom` | `7d` |
| `from`, `to` | fechas `AAAA-MM-DD` (solo con `custom`, ambos incluidos) | |
| `artifact_id` | id, repetible | todos |
| `mode` | `literal`, `razonamiento` | todos |

Los días se cortan a medianoche de `CAP_TIMEZONE`, igual que los topes.

## GET /usage

Parámetros extra: `group_by` = `artifact` | `mode` | `model` (por defecto `artifact`).

```json
{
  "period": {"from": "2026-10-03", "to": "2026-10-09", "bucket": "day"},
  "kpis": {
    "spend_usd":        {"value": 3.42, "previous": 3.05, "change_pct": 12.1},
    "queries":          {"value": 248,  "previous": 236,  "change_pct": 5.1},
    "tokens":           {"value": 1900000, "input": 1500000, "output": 300000, "reasoning": 100000, "previous": 1610000, "change_pct": 18.0},
    "avg_cost_usd":     {"value": 0.014, "previous": 0.013, "change_pct": 7.7},
    "latency_ms":       {"p50": 6100, "p95": 21000, "previous_p50": 6300, "change_pct": -3.2},
    "no_info_pct":      {"value": 9.0, "previous": 11.0, "change_pts": -2.0},
    "error_pct":        {"value": 0.8, "previous": 1.2, "change_pts": -0.4},
    "useful_pct":       {"value": 81.0, "rated": 52, "previous": 77.0, "change_pts": 4.0}
  },
  "series": [
    {"bucket": "2026-10-03", "groups": {"Consulta administrativa Postgrados Computación": {"spend_usd": 0.4, "queries": 30, "tokens": 210000}}}
  ],
  "by_artifact": [
    {"id": "a-1", "name": "...", "today_spent_usd": 0.9, "daily_cap_usd": 1.5, "spend_usd": 2.6, "queries": 164, "avg_latency_ms": 7200}
  ],
  "by_model": [
    {"model": "z-ai/glm-5.3", "queries": 120, "tokens": 1200000, "spend_usd": 2.9, "avg_latency_ms": 15000}
  ]
}
```

- `bucket` es `hour` con `period=today` y `day` en los demás (USO-3).
- `previous` es el período anterior de igual duración; `change_pct` es nulo si `previous` es 0.
- Las consultas rechazadas cuentan en `queries` y en el registro, con costo 0, pero no en los
  porcentajes de "sin información" ni en el tiempo de respuesta.

## GET /usage/queries

Parámetros extra: `outcome` (repetible), `page` (desde 1), `page_size` (por defecto 50, máximo 200),
`format=csv`, `include_questions` (solo con CSV; por defecto falso, USO-8).

```json
{
  "total": 248, "page": 1, "page_size": 50,
  "items": [
    {"id": "q-1", "created_at": "2026-10-08T16:42:00Z", "artifact": "...", "mode": "razonamiento",
     "model": "z-ai/glm-5.3", "tokens": 3812, "cost_usd": 0.021, "cost_estimated": false,
     "latency_ms": 18400, "outcome": "answered", "reject_reason": null, "rating": "util"}
  ]
}
```

Con `format=csv` responde `text/csv` con una fila por consulta y las mismas columnas (más `question`
solo si `include_questions=true`).

## GET /usage/queries/{query_id}

Detalle (USO-6): todo lo anterior más `question`, `domains` (nombres), `sources`
(`{domain, document}`) y `rating_comment`.

## GET /usage/balance

```json
{"available": true, "remaining_usd": 11.4, "source": "key_limit", "key_limit_remaining_usd": 11.4,
 "account_remaining_usd": null, "days_left": 23, "avg_daily_spend_usd_7d": 0.49, "warning": false}
```

- `source`: `key_limit` (solo el límite de la clave) o `account` / `key_limit` según cuál sea menor
  cuando también hay clave de gestión; `remaining_usd` es siempre el menor de los disponibles.
- Con `source = key_limit` y sin clave de gestión, el panel aclara que el saldo de la cuenta puede ser
  menor.

Sin fuente de saldo: `{"available": false, "reason": "La clave de OpenRouter no tiene límite de crédito y no hay clave de gestión configurada."}`.
`warning` es verdadero si `days_left < 7` (USO-7). Ver [research.md](../research.md), decisión 7.
