# Data Model: Datos de contacto de quienes escriben al bot de WhatsApp

Una sola tabla nueva, **dedicada**: no tiene claves foráneas a consultas, conversaciones, artefactos ni documentos. Su única relación es con `bots`, para distinguir el número de la institución al que escribió la persona. Migración `0012` (aditiva).

## Entidad: Contacto de WhatsApp (`whatsapp_contacts`)

| Campo | Tipo | Reglas |
|---|---|---|
| `id` | `String` (uuid), clave primaria | Se genera en la API. Es lo que usa el panel para borrar. |
| `bot_id` | `String`, clave foránea a `bots.id`, no nulo | El bot (número de la institución) al que escribió la persona. |
| `phone` | `String`, no nulo | Normalizado: `+` y de 7 a 15 dígitos. Es el dato que sirve para contactar. |
| `name` | `String`, nulo | De 1 a 80 caracteres, sin saltos de línea. Nulo si no lo entregó o lo borró. |
| `email` | `String`, nulo | Hasta 254 caracteres, forma `usuario@dominio.tld`, en minúsculas. Nulo si no lo entregó o lo borró. |
| `status` | `String`, no nulo | `pendiente`, `invitada`, `entrego` o `declino` (ver transiciones). |
| `email_retried` | `Boolean`, no nulo, falso por defecto | Si ya se repitió una vez la pregunta del correo (R6). |
| `created_at` | `DateTime`, no nulo | UTC. Primera vez que escribió. |
| `last_seen_at` | `DateTime`, no nulo | UTC. Último mensaje de la persona. Se actualiza en cada mensaje, con un máximo de una escritura por hora por contacto para no cargar la base. |
| `updated_at` | `DateTime`, no nulo | UTC. Último cambio del registro (invitación, datos, borrado). |

**Restricciones**: único `(bot_id, phone)`; índice por `status` y por `created_at` (la lista del panel va de la más reciente a la más antigua y filtra por estado). Sin `ondelete` en `bot_id`: los bots no se borran, se desactivan.

**Lo que NO se guarda (FR-003)**: el texto de ninguna pregunta ni respuesta, el contexto de conversación, el identificador de usuario de Kapso, el id de conversación ni costos.

### Estados y transiciones

```text
(no existe) --primer mensaje (BOT_CONTACT=on, con teléfono)--> pendiente
pendiente   --claim_invite (gana la carrera)-----------------> invitada
invitada    --release_invite (el envío falló)---------------> pendiente
invitada    --provided (nombre y/o correo válidos)----------> entrego
invitada    --declined (negativa o pregunta o 2º correo malo)-> declino   (con nombre si ya lo había)*
invitada    --email_retry (correo mal escrito, 1ª vez)-------> invitada   (email_retried = true)
cualquiera  --erase (la persona)----------------------------> declino    (nombre y correo en nulo)
cualquiera  --reopen (la persona)---------------------------> invitada   (se envía la invitación otra vez; desde invitada solo reinicia email_retried)
cualquiera  --borrado desde el panel------------------------> (la fila desaparece)
```

\* Si en un segundo intento de correo inválido ya había un nombre guardado, el estado final es `entrego` (hay un dato), no `declino`.

Reglas de validación en la API (el servicio las aplica antes, pero la API no confía en él):
- `provided` exige al menos un dato válido (nombre o correo). Con ambos nulos se rechaza con 422.
- No hay transiciones desde `pendiente` a `entrego` o `declino` directamente: una persona solo puede contestar una invitación que se le envió. Un evento fuera de orden responde 409 con el estado actual y el servicio lo toma como "no aplicable".
- Un `provided` sobre un contacto que ya tenía nombre o correo **reemplaza** solo el campo recibido (permite corregir con la frase de reapertura).

### Volumen e índices

Se espera de cientos a pocos miles de filas (tope mensual de 1.800 mensajes entre todos los bots). La tabla se lee entera sin problema; los índices son para el orden y el filtro de la lista.

## Entidad derivada: Estado de contacto (respuesta de `POST /bot/messages`)

No se guarda: es lo que la API devuelve al servicio en cada mensaje para decidir el paso siguiente.

| Campo | Significado |
|---|---|
| `status` | El `status` del contacto. |
| `email_retried` | Si ya se repitió la pregunta del correo. |
| `has_name`, `has_email` | Si hay nombre o correo guardados (para que el servicio sepa qué decir en la confirmación del borrado: "no tenías datos guardados"). Nunca los valores. |

## Entidad derivada: Descarga de contactos

El CSV se genera a pedido y no se guarda. Columnas, en este orden: `telefono`, `bot`, `nombre`, `correo`, `estado`, `creado`, `ultimo_mensaje`, `actualizado`. Fechas en UTC con formato ISO 8601. Los valores que empiezan con `=`, `+`, `-` o `@` se neutralizan (se les antepone un apóstrofo). El teléfono empieza con `+`, así que **también** se neutraliza al exportar (queda `'+506...`), como pide la regla general.

## Migración `0012_contactos_de_whatsapp`

- `upgrade`: crea `whatsapp_contacts` con la restricción única y los índices. No toca ninguna tabla ni fila existente y no trae semillas.
- `downgrade`: borra la tabla (**se pierden los contactos**: exportar el CSV antes). Una API anterior a la `0012` no arranca sobre una base que ya la aplicó: antes de volver atrás hay que correr `alembic downgrade 0011` (ver "Cuidado con las migraciones" en `docs/OPERACION.md`).
