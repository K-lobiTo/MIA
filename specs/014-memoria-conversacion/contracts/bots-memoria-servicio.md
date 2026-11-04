# Contrato: la memoria del bot (módulo Bots, `/bot/messages` y servicio)

Cambios de las rutas de bots, de `POST /bot/messages` y del servicio `mia-whatsapp`. Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R5 y R6. El bot **no** recibe historial al modelo y sigue solo en modo literal: lo único que cambia es cuánto recuerda para la aclaración de programa y el programa recordado (feature 013).

## Rutas de administración (`/bots`)

- `BotCreate` y `BotUpdate` aceptan `context_turns`: entero de **1 a 10** o `null` (el valor por defecto, 2 vueltas). Fuera de rango (0, mayor que 10) o no numérico responde **422**. Solo alcance global, como el resto del módulo (`global_only`).
- `BotOut` devuelve `context_turns` (el valor del bot, o `null`) y `context_turns_effective` (el que rige: el del bot o 2).
- Un cambio deja una línea `bot.context_turns` en `mia.admin` con `actor`, `target` = id del bot y `detail` = `"<nombre>: <anterior> -> <nuevo>"` (los nulos se escriben `por defecto`), además de la línea `bot.update` de siempre.

## `POST /bot/messages` (el servicio lo llama al recibir cada mensaje)

La respuesta agrega `context_turns`: las vueltas efectivas del bot (entero de 1 a 10), o `null` si el número no tiene bot. El resto de la respuesta (`status`, `month`, `month_messages`, `month_cap`) no cambia.

## Servicio `mia-whatsapp`

| Pieza | Comportamiento |
|---|---|
| `CountResult.context_turns` | Lee el campo de la respuesta; vacío si la API no lo informa. |
| Límite de la ventana | `2 * context_turns` turnos; si no hay valor, `BOT_CONTEXT_MESSAGES` (4). Se calcula en cada mensaje: un cambio desde el panel rige desde el mensaje siguiente y también para conversaciones en curso. |
| `ConversationStore` | Guarda hasta 20 turnos por persona; `turns`, `pending` y `remembered_program` reciben el límite vigente y miran solo los últimos. El vencimiento, el tope de conversaciones y lo que guarda cada turno no cambian. |
| Error al contar | Con el estado `error` el servicio ya no procesa el mensaje (como hoy); el límite por defecto solo aplica cuando la API responde sin el campo. |

## Panel (módulo Bots)

El formulario del bot (`BotForm.tsx`) agrega **Memoria (vueltas)**: entero de 1 a 10, vacío significa el valor por defecto (2), con este texto: "Cuántas vueltas recuerda el bot de cada conversación para pedir aclaraciones de programa y recordar el programa. Mínimo 1. El bot no entrega la conversación al modelo." La tarjeta (`BotCard.tsx`) muestra el valor efectivo.
