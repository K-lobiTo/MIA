# Contrato: rutas de administración de bots (`/bots`)

Rutas que usa el módulo **Bots** del panel. Requieren administración (`require_admin`: cuenta del TEC o `ADMIN_KEY`) y **alcance global** en las cuatro (el número y la cuota son de toda la institución): una persona con alcance de programa recibe 403 `global_only`. Las escrituras dejan una línea en el registro de administración (`mia.admin`) con `bot.create` o `bot.update`; un rechazo por alcance también (`result: rechazado`). Detalle de los datos en [data-model.md](../data-model.md).

## GET /bots

Lista los bots, ordenados por nombre, con el consumo del mes en curso.

**200**:

```json
{
  "monthly_cap": 1800,
  "service_configured": true,
  "month": "2026-10",
  "bots": [
    {
      "id": "…",
      "name": "Atracción de estudiantes",
      "kapso_number_id": "123456789012345",
      "active": true,
      "artifact": { "id": "…", "name": "Bot de WhatsApp", "active": true },
      "domains": ["Unidad de Postgrados de Computación / Admisión", "Unidad de Postgrados de Computación / Plan de estudios"],
      "available": true,
      "unavailable_reason": null,
      "usage": { "received": 412, "sent": 530, "total": 942, "cap_reached": false },
      "created_at": "2026-10-24T15:30:00Z"
    }
  ]
}
```

- `monthly_cap`: `BOT_MONTHLY_MESSAGE_CAP` (igual para todos los bots).
- `service_configured`: `BOT_SERVICE_KEY` no está vacía. Con `false` el panel avisa que el servicio del bot no podrá consultar.
- `artifact`: `null` si el bot no tiene artefacto.
- `domains`: etiquetas `Programa / Dominio` de los dominios que el artefacto cubre **hoy** (`configured_domain_ids`), ordenadas; vacía sin artefacto. Con acceso a todos los dominios, son todos.
- `available` y `unavailable_reason`: `true` si el bot responde hoy; si no, el motivo en una frase (`"El bot está desactivado."`, `"No tiene artefacto asignado."`, `"El artefacto asignado está desactivado."`, `"Se alcanzó el tope mensual de mensajes."`).
- `usage`: el consumo del mes en curso (`received + sent = total`); `cap_reached` es `total >= monthly_cap`. Sin fila del mes, ceros.

## POST /bots

Registra un bot.

**Cuerpo**: `{ "name": "…", "kapso_number_id": "…", "artifact_id": "…" }`. `name` y `kapso_number_id` se recortan y no pueden quedar vacíos; `kapso_number_id` es de 1 a 64 caracteres sin espacios.

**201**: el bot, con la misma forma de un elemento de la lista.

**Errores**: 404 `Artefacto no encontrado.`; 409 `Ya existe un bot llamado '…'.` o `Ya hay un bot registrado para ese número de Kapso.`; 403 `global_only`; 422 por un cuerpo inválido.

## PATCH /bots/{bot_id}

Cambia lo enviado y deja lo demás. Rige desde el mensaje siguiente, sin reiniciar nada (BOT-3).

**Cuerpo** (todo opcional): `{ "name": "…", "kapso_number_id": "…", "artifact_id": "…", "active": true }`.

**200**: el bot actualizado. **Errores**: 404 `Bot no encontrado.` o `Artefacto no encontrado.`; 409 por nombre o número repetido; 403 `global_only`.

**Registro**: `bot.update` con el detalle del cambio (por ejemplo `artefacto: A -> B`, `activo: false`); nunca incluye claves.

## Qué no hay

No hay `DELETE`: un bot se desactiva (BOT-5). Tampoco hay rutas para editar los textos ni los límites: son variables del servicio y de la API (BOT-8).

## Panel (módulo Bots)

- Lista con una tarjeta por bot: nombre, número, estado (activo o desactivado, y si no responde hoy, el motivo), artefacto asignado, dominios que ve y la barra de mensajes del mes frente al tope (mensajes recibidos, enviados y total).
- Registrar y editar: nombre, número de Kapso y selector de artefacto (los artefactos de `GET /artifacts`).
- **Advertencia al asignar o cambiar el artefacto** (BOT-7, FR-007): "Este bot responde a cualquiera que escriba al número. Los dominios del artefacto deben ser información que se pueda decir a cualquiera." y, debajo, los dominios que verá. Se confirma antes de guardar.
- Interruptor de activo.
- Si `service_configured` es falso, un aviso al principio de la página.
- La entrada del módulo solo se muestra con alcance global (`canManageBots`).
