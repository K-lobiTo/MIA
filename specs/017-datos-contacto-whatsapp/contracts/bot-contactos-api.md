# Contrato: rutas de la API para el servicio del bot (contactos)

Las llama `mia-whatsapp` con la credencial de servicio (`X-Bot-Service-Key`), igual que el resto de `/bot/...` (ver [contrato de la 011](../../011-bot-whatsapp-kapso/contracts/bot-servicio-api.md)). Una credencial ausente o incorrecta responde 401, como hoy. Estas son **las únicas rutas por donde el teléfono entra a la API**: `POST /bot/query` no lo recibe ni lo recibirá.

## `POST /bot/messages` (ampliada)

Cuenta mensajes del mes y dice el estado del bot, como hasta ahora. Se agrega, **opcional**, el teléfono de la persona.

**Petición** (los campos existentes no cambian):

```json
{ "number_id": "647015955153740", "received": 1, "sent": 0, "phone": "50688887777" }
```

| Campo nuevo | Reglas |
|---|---|
| `phone` | Opcional. Texto de hasta 32 caracteres con el teléfono tal como llegó (se normaliza en la API). Sin él, o con `BOT_CONTACT=off`, la ruta se comporta exactamente como antes y `contact` es `null`. |

**Respuesta 200** (los campos existentes no cambian):

```json
{
  "status": "ok",
  "month": "2026-11",
  "month_messages": 12,
  "month_cap": 1800,
  "context_turns": 2,
  "contact": { "status": "pendiente", "email_retried": false, "has_name": false, "has_email": false }
}
```

- `contact` **no aparece** (equivale a `null`: así la respuesta sin `phone` es idéntica a la de antes) si no llegó `phone`, si el teléfono es inválido, si el bot no existe (`unknown_bot`) o si la parte de contactos falló. Una falla de contactos **nunca** cambia `status` ni hace fallar la ruta (FR-025): se registra sin datos personales.
- Con `phone` válido, la API obtiene o crea el contacto (`pendiente` si es nuevo) y actualiza `last_seen_at` (como máximo una escritura por hora por contacto).
- `has_name` y `has_email` son booleanos: la API no devuelve el nombre ni el correo.
- Se cuenta el mensaje **antes** de tocar contactos, así que un error de contactos no deja el conteo a medias.

## `PUT /bot/contacts`

Aplica un evento al contacto de una persona. Un solo endpoint, un solo contrato de errores.

**Petición**:

```json
{
  "number_id": "647015955153740",
  "phone": "50688887777",
  "event": "provided",
  "name": "Ana Pérez",
  "email": "ana@correo.com"
}
```

| Campo | Reglas |
|---|---|
| `number_id` | Como en las demás rutas: de 1 a 64 caracteres. |
| `phone` | Obligatorio. Se normaliza: solo dígitos, de 7 a 15, se guarda con `+`. Inválido: 422. |
| `event` | Obligatorio, uno de los de la tabla siguiente. |
| `name` | Solo con `provided`. De 1 a 80 caracteres después de quitar espacios; sin saltos de línea. |
| `email` | Solo con `provided`. Hasta 254 caracteres; forma `usuario@dominio.tld`; se guarda en minúsculas. |

**Eventos**:

| Evento | Estado previo permitido | Efecto | Resultado |
|---|---|---|---|
| `claim_invite` | `pendiente` | `status = invitada` de forma atómica (`UPDATE ... WHERE status='pendiente'`) | `claimed: true` si ganó; `false` si otro ya la reclamó o el estado no era `pendiente` |
| `release_invite` | `invitada` (sin nombre ni correo) | vuelve a `pendiente` | el estado nuevo |
| `provided` | `invitada` | guarda `name` y/o `email` recibidos (reemplaza solo los recibidos), `status = entrego`, `email_retried = false` | el estado nuevo |
| `email_retry` | `invitada` con `email_retried = false` | guarda `name` si viene, `email_retried = true`, sigue `invitada` | el estado nuevo |
| `declined` | `invitada` | `status = declino` (o `entrego` si ya había nombre o correo guardado) | el estado nuevo |
| `erase` | cualquiera | `name = null`, `email = null`, `status = declino`, `email_retried = false` | el estado nuevo y `had_data` (si había algo que borrar) |
| `reopen` | cualquiera (`pendiente`, `invitada`, `entrego` o `declino`) | `status = invitada`, `email_retried = false` (nombre y correo se conservan hasta que la persona los reemplace); desde `invitada` solo reinicia `email_retried` | `claimed: true` (el servicio envía la invitación) |

**Respuesta 200**:

```json
{ "claimed": true, "had_data": false, "contact": { "status": "invitada", "email_retried": false, "has_name": false, "has_email": false } }
```

**Errores**:

| Código | Cuándo |
|---|---|
| 401 | Credencial de servicio ausente o incorrecta. |
| 404 | El número no tiene bot (`unknown_bot`) o el contacto no existe (solo los eventos que lo exigen; `claim_invite`, `erase` y `reopen` **crean** el contacto si falta, para no fallar por una carrera con el primer mensaje). |
| 409 | El evento no aplica al estado actual (por ejemplo `provided` sobre `pendiente`). El cuerpo trae el estado actual; el servicio lo trata como "no aplicable" y no insiste. |
| 422 | Teléfono, correo, nombre o evento inválidos. El mensaje de error **no repite** el valor recibido. |

## Garantías (verificadas por pruebas)

- Los cuerpos de error, los registros de la API y la línea de auditoría **no** incluyen el teléfono, el nombre ni el correo.
- `PUT /bot/contacts` es idempotente por evento: repetir `claim_invite` devuelve `claimed: false`; repetir `declined` o `erase` no falla.
- Ninguna de estas rutas lee ni escribe `queries`, `conversations` ni ninguna tabla que no sea `whatsapp_contacts` (y `bot_message_counts` en `/bot/messages`, como antes).
