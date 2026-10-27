# Contrato: el servicio del bot con contexto y aclaración

Cambio del flujo de cada mensaje de `mia-whatsapp` ([servicio-whatsapp.md](../../011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md), "Qué hace con cada mensaje"). Datos en [data-model.md](../data-model.md); decisiones en [research.md](../research.md) R5 a R8.

## Orden de decisiones (después de validar que es una pregunta de texto razonable)

| # | Paso | Resultado en el registro (`resultado`) |
|---|---|---|
| a | Si el último turno del bot fue una aclaración: comparar el mensaje con los candidatos (palabras de su clave o su número). **Exactamente uno**: la pregunta a enviar es `"{pregunta original} ({programa})"` y `ya_aclarado` = verdadero. Ninguno o varios: descartar la aclaración y seguir con el mensaje tal cual. | |
| b | Entrar **una vez** a la cola de consultas y llamar a `POST /bot/query` con la pregunta a enviar. | |
| c | Respuesta: entregarla (texto, fuentes, imagen). Programa recordado = el único programa de `programs` o el elegido. | `respondido` |
| d | Sin información o aclaración, **y** hay programa recordado, **y** la pregunta no iba ya con un programa (`ya_aclarado` falso y la pregunta no es un reintento): reintentar **una vez** con `"{pregunta} ({programa recordado})"` dentro del mismo lugar de la cola. Si responde, entregarla y recordar ese programa. Si no, seguir. | `respondido` |
| e | Aclaración (y `ya_aclarado` falso): enviar `BOT_TEXT_CLARIFY` con los candidatos numerados (con el saludo si toca), un solo mensaje. | `aclaracion` |
| f | Aclaración con `ya_aclarado` verdadero: tratarla como sin información (nunca dos aclaraciones por pregunta). | `sin_informacion` |
| g | Sin información: el texto de siempre. | `sin_informacion` |
| h | Después de un envío con éxito (no `error_envio`): guardar en el contexto el turno de la persona y el del bot. | |

El mensaje duplicado se descarta antes (paso 1 del flujo actual) y no entra al contexto. El bot desactivado, el tope mensual, el límite por persona, los mensajes que no son texto y los demasiado largos se resuelven antes de este orden y **no** tocan el contexto.

## Cuota de mensajes

Cada aclaración es un envío más y se cuenta como cualquier otro (`count_messages`). El reintento no envía nada. Una pregunta con aclaración y su respuesta suman 4 mensajes (2 recibidos y 2 enviados; 3 enviados si la respuesta lleva imagen).

## Configuración

Variables del servicio (todas opcionales, con rangos en [data-model.md](../data-model.md)): `BOT_CONTEXT_MESSAGES` (4), `BOT_CONTEXT_MINUTES` (30), `BOT_CONTEXT_MAX_PEOPLE` (5000) y `BOT_TEXT_CLARIFY`. El texto no debe contener contacto: al arrancar se avisa si la variable lo trae (`contact_warnings`), igual que los demás textos.

## Registro del servicio

Cada mensaje sigue terminando en una línea con su `resultado` (ahora también `aclaracion`) y su duración, **sin** texto de la persona, sin teléfono, sin el texto del contexto ni los nombres de los programas.
