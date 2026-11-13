# Contrato: rutas de administración de contactos (panel)

Las usa el módulo **Contactos de WhatsApp** del panel. Todas exigen una cuenta de administración (`require_admin`) con **alcance global** (`principal.is_global`); una cuenta de programa recibe 403 con el mismo error de "solo alcance global" que las rutas de bots, y el intento queda en el registro de administración como `rechazado`. Con `X-Admin-Key` (automatización) valen las mismas reglas que en las demás rutas globales.

## `GET /contacts`

Lista paginada, de la más reciente a la más antigua por `created_at`.

**Parámetros**:

| Parámetro | Reglas |
|---|---|
| `bot_id` | Opcional. Solo contactos de ese bot. |
| `status` | Opcional, repetible: `pendiente`, `invitada`, `entrego`, `declino`. |
| `has_email` | Opcional, booleano. |
| `page` | Entero desde 1 (por defecto 1). |
| `page_size` | De 1 a 200 (por defecto 50). |
| `format` | `json` (por defecto) o `csv`. |

**Respuesta 200 (`json`)**:

```json
{
  "total": 134,
  "page": 1,
  "page_size": 50,
  "items": [
    {
      "id": "c0f1...",
      "phone": "+50688887777",
      "bot": { "id": "b1...", "name": "Posgrados computación" },
      "name": "Ana Pérez",
      "email": "ana@correo.com",
      "status": "entrego",
      "created_at": "2026-11-12T15:04:05Z",
      "last_seen_at": "2026-11-12T15:10:00Z",
      "updated_at": "2026-11-12T15:05:30Z"
    }
  ],
  "summary": { "pendiente": 0, "invitada": 3, "entrego": 40, "declino": 91 }
}
```

`summary` cuenta por estado **sin** el filtro de estado (pero con los demás filtros), para mostrar los totales sin una segunda consulta.

**Respuesta 200 (`csv`)**: `text/csv; charset=utf-8` con `Content-Disposition: attachment; filename="mia-contactos-AAAA-MM-DD.csv"`. Entrega **todas** las filas del filtro, no una página, con un tope de 50.000 (si lo supera, 422 con un mensaje que pide filtrar). Columnas: `telefono`, `bot`, `nombre`, `correo`, `estado`, `creado`, `ultimo_mensaje`, `actualizado`. BOM UTF-8. Los valores que empiezan con `=`, `+`, `-`, `@`, tabulador o retorno se neutralizan con un apóstrofo (también el teléfono, que empieza con `+`). Cada descarga deja la línea de auditoría `contact.export`.

## `DELETE /contacts/{id}`

Borra la fila del contacto. 204. 404 si no existe. Auditoría `contact.delete` con el `id` del contacto (nunca el teléfono, el nombre ni el correo).

## `DELETE /contacts`

Borra todos los contactos que cumplen el filtro (`bot_id`, `status`, `has_email`, con el mismo significado que en la lista).

| Parámetro | Reglas |
|---|---|
| `expected` | **Obligatorio**, entero: el conteo que la persona vio y confirmó. Si no coincide con el conteo actual del filtro, 409 con el conteo actual y **no se borra nada**. |

Sin ningún filtro borra **todos** los contactos (sigue exigiendo `expected`). Respuesta 200 con `{ "deleted": N }`. Auditoría `contact.delete_filtered` con el conteo y los filtros.

## Auditoría (registro de administración)

Una línea JSON por el logger `mia.admin`, con `actor`, `action`, `target`, `detail` y `result`, como las demás escrituras. **Nunca** incluye teléfonos, nombres ni correos:

| Acción | `target` | `detail` |
|---|---|---|
| `contact.export` | (vacío) | `filas=N; filtros=bot:..,estado:..,correo:..` |
| `contact.delete` | id del contacto | (vacío) |
| `contact.delete_filtered` | (vacío) | `borrados=N; filtros=...` |
| (cualquiera, rechazada por alcance) | (vacío) | `result: rechazado` |

La lista (`GET /contacts` en JSON) **no** se audita fila por fila (verla es el uso normal del módulo); sí se audita la descarga y el borrado, que son las salidas de los datos.

## Lo que el panel muestra (interfaz)

- Tarjetas con los totales por estado (`summary`) y la lista paginada.
- Filtros: bot, estado y "con correo".
- Botón **Descargar CSV** (respeta los filtros), con un aviso si falla.
- Acción **Borrar** por fila y **Borrar los N filtrados**, ambas con una ventana de confirmación que dice que no se puede deshacer; la masiva muestra el conteo y exige confirmarlo.
- Una nota visible de que son datos personales y que cada descarga y borrado queda registrado.
- El módulo se oculta a las cuentas de programa (`canManageContacts`, solo alcance global); la API es quien hace cumplir el permiso.
