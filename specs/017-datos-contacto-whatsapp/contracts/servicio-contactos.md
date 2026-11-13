# Contrato: servicio `mia-whatsapp` (flujo de contactos)

Complementa [servicio-whatsapp.md](../../011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md) y [bot-contactos-api.md](bot-contactos-api.md). Todo lo de aquí vale **solo con `BOT_CONTACT=on`**; apagado, el servicio ni envía el teléfono ni evalúa estas reglas y el flujo es exactamente el de antes.

## Variable de entorno

| Variable | Valores | Defecto |
|---|---|---|
| `BOT_CONTACT` | `off`, `on` (cualquier otro valor impide arrancar, con un mensaje que nombra la variable) | `off` |

## Textos (configurables, en español, sin contactos de programas)

Cada texto se puede cambiar con su variable. **Quedan fuera de la advertencia de arranque `contact_warnings`**: piden un correo y llevan un ejemplo con `@`. `{saved}` y `{example}` son marcadores que el servicio reemplaza.

| Variable | Texto por defecto (resumen; el literal exacto queda en `config.py`) |
|---|---|
| `BOT_TEXT_CONTACT_INVITE` | "Si quieres que la Coordinación del programa te contacte, puedes dejarme tu nombre y tu correo. Es totalmente opcional: puedes seguir preguntando sin dejarlos. Guardo tu número de WhatsApp y, si los das, tu nombre y correo, solo para que te contacten sobre los programas; no los uses dentro de tus preguntas. Para dejarlos escribe, por ejemplo: Ana Pérez ana@correo.com. Si no quieres dejarlos, escribe «no». Para borrar tus datos, escribe «borrar mis datos»." |
| `BOT_TEXT_CONTACT_THANKS` | "Listo, guardé {saved}. Para corregirlo escribe «quiero dejar mis datos»; para borrarlo, «borrar mis datos». Sigue con tus preguntas cuando quieras." (`{saved}` es "tu nombre", "tu correo" o "tu nombre y tu correo", con el correo enmascarado: `a**@correo.com`) |
| `BOT_TEXT_CONTACT_DECLINED` | "De acuerdo, no guardé tus datos. Puedes seguir preguntando; si cambias de opinión, escribe «quiero dejar mis datos»." |
| `BOT_TEXT_CONTACT_EMAIL_RETRY` | "No pude leer tu correo. ¿Puedes escribirlo de nuevo? Por ejemplo: {example}. Si no quieres dejarlo, escribe «no»." |
| `BOT_TEXT_CONTACT_WHY` | "Pido el nombre y el correo solo para que la Coordinación del programa pueda contactarte si te interesa. Es opcional, y el bot funciona igual sin ellos. Puedes borrarlos cuando quieras escribiendo «borrar mis datos»." |
| `BOT_TEXT_CONTACT_ERASED` | "Listo, borré tu nombre y tu correo. No te los volveré a pedir." |
| `BOT_TEXT_CONTACT_NO_DATA` | "No tenía tu nombre ni tu correo guardados." |

El correo en la confirmación va **enmascarado** (la primera letra y el dominio) para no repetirlo completo en el chat (FR-014).

## Orden de decisiones por mensaje (cambios respecto a `flow.py`)

Los pasos 1 a 4 de siempre no cambian (duplicado, conteo y estado del bot, límite por persona, bot desactivado). El teléfono se envía en la llamada del paso 2 con `BOT_CONTACT=on` y si el aviso trae un teléfono real (no un identificador de usuario).

**Nuevo paso 4b: contacto** (solo si `count.contact` llegó y no hay una aclaración de programa pendiente, R8):

1. Si el mensaje es de texto, se normaliza y se evalúan **en este orden**:
   1. *Borrado* → `PUT erase` → responde `ERASED` o `NO_DATA` (según `had_data`). Resultado del mensaje: `contacto_borrado`.
   2. *Reapertura* → `PUT reopen` → envía `INVITE`. Resultado: `contacto_reabierto`.
   3. Con el contacto en `invitada`: *negativa* → `PUT declined` → `DECLINED` (`contacto_declinado`); *"para qué"* → `WHY`, sin cambiar el estado (`contacto_explicado`); *correo válido o nombre válido* → `PUT provided` → `THANKS` (`contacto_entregado`); *correo inválido* → primer intento `PUT email_retry` y `EMAIL_RETRY` (`contacto_reintento`), segundo intento `PUT declined` o `provided` si ya había nombre y `DECLINED` (`contacto_declinado`).
2. Todo lo anterior **consume el mensaje**: no se llama a `/bot/query`, no se guarda en el contexto de la 013 y no gasta modelo (FR-017, R5). Cada respuesta es un mensaje enviado que cuenta en la cuota; el mensaje recibido ya se contó en el paso 2.
3. Con el contacto en `invitada` y un mensaje que **no** es dato (una pregunta, o un mensaje que no es texto), `PUT declined` **después** de responder y sin esperar (una falla se ignora, FR-025), y el mensaje sigue su camino normal de los pasos 5 a 9. Solo se declina si la respuesta a ese mensaje **se envió bien**, sea cual sea su resultado (incluidos `aclaracion`, `no_texto` y `muy_largo`); si el envío falló, el contacto sigue `invitada`.
   - La **negativa** es una coincidencia exacta con una lista corta de frases (R4), no un texto que solo empiece con "no": "no encuentro la matrícula" es una pregunta.
   - El **borrado** y la **reapertura** valen en cualquier estado del contacto.
   - **Límite conocido**: estos pasos corren después del tope mensual, del límite por persona y del bot desactivado; con el tope alcanzado ni siquiera se responde "borrar mis datos". La vía de respaldo es el panel.
   - Para decidir si hay una aclaración pendiente, `limit` y `conversations.pending` se calculan **antes** del paso 4b.
4. Si la llamada a la API falla (error, 409, tiempo agotado) el mensaje **no** se consume: sigue el flujo normal como si la función estuviera apagada para esa persona en ese momento.

**Nuevo paso 10: invitación** (después del paso 9 y de las demás respuestas, solo con `contact.status == pendiente`):

- Aplica si el resultado fue `respondido`, `sin_informacion` o `imagen_fallida`. No aplica tras `aclaracion`, `limite`, `no_disponible`, `no_texto`, `muy_largo` ni errores de envío (R8).
- `PUT claim_invite`; si `claimed` es falso, no se envía nada. Si es verdadero, se envía `INVITE` en un mensaje aparte **sin saludo**. Si el envío falla, `PUT release_invite` y el contacto vuelve a `pendiente`.
- El mensaje enviado se suma al `sent` del resultado y a la cuota (`_count_sent`), y el resultado del mensaje queda como el de la respuesta con el campo `contacto=invitada`.

## Registro del servicio (`logs.py`)

Una línea JSON por mensaje, como hoy, con un campo nuevo `contacto` (solo el nombre del evento: `invitada`, `borrado`, `reabierto`, `declinado`, `entregado`, `reintento`, `explicado`, o ausente). **Nunca** el teléfono, el nombre, el correo ni el texto del mensaje (ya era así). Los errores de la API al guardar un contacto se registran con el tipo de excepción y el código HTTP, sin cuerpo.

## Reglas de texto

Las reglas exactas (frases, largos, partículas permitidas en nombres, palabras de relleno) están en [research.md R4](../research.md#r4-reglas-de-texto-para-reconocer-los-datos) y se fijan como casos de tabla en `whatsapp/tests/test_contacts_rules.py`. Todas son deterministas, sin modelo de lenguaje, e ignoran mayúsculas y tildes al comparar frases de control.
