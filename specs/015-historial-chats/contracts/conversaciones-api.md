# Contrato: conversaciones guardadas (`/conversations`)

Rutas que usa la Consulta con la sesión iniciada. Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R5, R8 y R9. Todas exigen `X-Session-Token` (sin él o con uno inválido: **401** `session_invalid`); no exigen la clave del artefacto. Cada ruta filtra por el usuario de la sesión: **una conversación ajena o inexistente responde 404** idéntico en ambos casos (`{"detail": "Conversación no encontrada."}`).

## `GET /conversations`

**200**: `{ "retention_days": 90, "conversations": [ { "id": "uuid", "title": "¿Cuándo empieza la maestría?", "created_at": "...", "updated_at": "...", "turn_count": 4 } ] }`, de la más reciente a la más antigua (por `updated_at`). Hasta `CHAT_MAX_CONVERSATIONS` elementos, así que no se pagina. Con el guardado apagado (`CHAT_RETENTION_DAYS=0`): lista vacía y `retention_days: 0`.

## `PATCH /conversations/{id}`

Cambia el título (agregada el 2026-11-06, menú de cada conversación en la Consulta). Cuerpo: `{ "title": "Costos de la maestría" }`. Los espacios se normalizan y el título se recorta a 80 caracteres; vacío o de más de 200 caracteres es **422**. **200**: el resumen de la conversación (`id`, `title`, `created_at`, `updated_at`, `turn_count`). No cambia `updated_at`: ni el orden de la lista ni la retención se alteran. Ajena o inexistente: 404.

## `GET /conversations/{id}`

**200**:

```json
{
  "id": "uuid",
  "title": "...",
  "created_at": "...",
  "updated_at": "...",
  "turns": [
    {
      "position": 1,
      "question": "¿Cuándo empieza la maestría?",
      "answer": "Inicia el I trimestre de 2027.",
      "sources": [ { "domain": "Admisión", "document": "Ciber_Admision.txt" } ],
      "mode": "literal",
      "no_info": false,
      "created_at": "..."
    }
  ]
}
```

Las vueltas van en orden. Las fuentes traen dominio y documento, **sin extracto**.

## `DELETE /conversations/{id}`

**204**: borra la conversación y todas sus vueltas por completo. **404** si no es del usuario o no existe.

## `DELETE /conversations`

**204**: borra todas las conversaciones del usuario y sus vueltas; no toca las de nadie más. Idempotente (sin conversaciones también responde 204).

## Reglas comunes

- **Retención**: una conversación sin actividad por más de `CHAT_RETENTION_DAYS` desaparece sola (limpieza al arrancar y perezosa cada hora, research R8). Con `0` no se guarda ni se conserva nada.
- **Sin rutas de administración que lean texto**: el único dato de conversaciones que sale por `/consulta-users` son la cantidad y la fecha de la última actividad.
- **Registro del servidor**: las operaciones de conversaciones registran solo el resultado y cantidades (`borradas=3`), nunca títulos ni textos.
