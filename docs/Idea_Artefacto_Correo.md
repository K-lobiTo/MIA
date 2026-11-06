# Idea a futuro: artefacto de correo electrónico

**Estado:** idea documentada el 2026-11-06. **No está especificada ni implementada**, no tiene feature asignada y no forma parte de ninguna versión. Este documento conserva lo que se conversó para retomarlo sin repetir el análisis. Si se decide hacerla, el siguiente paso es una feature (la 017 o la que corresponda) con su spec en `specs/`.

## Qué sería

Un canal más de consulta a MIA, igual que el bot de WhatsApp ([Definicion_Requerimientos_Bot_WhatsApp.md](Definicion_Requerimientos_Bot_WhatsApp.md)): una persona escribe una pregunta por correo a una dirección de la institución (por ejemplo `consultas@...`) y recibe la respuesta, con los documentos citados, en un correo de vuelta. Sería un servicio pequeño aparte (`mia-correo`, carpeta `correo/`), que traduce entre el correo y la API de MIA y no mezcla el canal con el motor.

## Por qué encaja con la arquitectura actual

- La API es el único punto de contacto con el almacenamiento (principio I). El servicio de correo consultaría igual que `mia-whatsapp`: con una credencial de servicio, y la API aplicaría el artefacto asignado (dominios, modos, tope diario), la memoria y el registro de Uso. Nada de eso se reescribe.
- `POST /bot/query` y `run_query` ya sirven a un canal externo. Hoy el bot se identifica por `kapso_number_id` (tabla `bots`, `kapso_number_id` único). Un canal de correo necesitaría identificar el bot por dirección, ya sea agregando un tipo de canal a la tabla de bots o creando una tabla propia. Es el cambio más pequeño de la API.
- Varios buzones serían varias filas, cada una con su artefacto, como los varios números de WhatsApp.

## Cómo se recibirían los correos (a decidir)

| Opción | Cómo funciona | Cuándo conviene |
|---|---|---|
| Servicio de correo con webhook (Resend, Postmark, SendGrid, Mailgun) | La dirección reenvía cada mensaje por HTTP al servicio. | La más simple y barata. Necesita un dominio donde configurar el correo entrante. |
| Buzón Microsoft 365 del TEC con Graph API | El servicio lee y responde desde un buzón institucional. | Encaja con el inicio de sesión del panel (Entra). Requiere que TI registre la aplicación y dé permisos al buzón. |
| Buzón IMAP o Gmail | El servicio revisa el buzón cada cierto tiempo y responde por SMTP. | No registra nada, pero es más frágil y con retraso. |

## Qué habría que construir

- **El servicio** (`correo/`, FastAPI como `whatsapp/`) con su Dockerfile y servicio de Railway, y su credencial de servicio.
- **Limpieza del mensaje:** quitar firmas, mensajes citados, adjuntos y HTML. Cubrir reenvíos y respuestas.
- **Hilos como conversación:** usar el identificador del hilo (`Message-ID`, `In-Reply-To`, `References`) para dar memoria, como hace la Consulta con sus conversaciones.
- **Reglas de respuesta:** responder solo al remitente, no contestar respuestas automáticas ni listas (evita bucles), filtrar spam y limitar las respuestas por remitente y por hora.
- **Aclaración de programa:** reutilizar la de la feature 013 si el artefacto cubre más de un programa.
- **Una ampliación pequeña de la API:** identificar el canal por dirección (ver arriba).
- **Panel:** una vista para registrar el buzón y su artefacto, como el módulo Bots.

## Decisiones abiertas

1. **Qué dirección y qué buzón.** Es lo primero: define la opción de recepción y quién debe dar permisos.
2. **Público y dominios.** Las actas tienen datos personales y el correo pasa por más sistemas intermedios que WhatsApp. El artefacto asignado debería ver solo información que se pueda decir a cualquiera, como el de WhatsApp (Currículum y Apertura de promoción).
3. **Modo de respuesta.** WhatsApp usa solo el literal por costo. En correo la espera no importa, así que se podría permitir también el modo con razonamiento y respuestas largas (como el resumen de los contenidos de todos los cursos). Se decide con el tope de gasto del artefacto.
4. **Costo.** Los servicios de correo suelen tener un plan gratuito de cientos o miles de mensajes al mes, suficiente para un prototipo. El gasto del modelo se acota con los topes del artefacto.
5. **Privacidad y retención.** Qué se guarda del correo (nada, como la Consulta sin sesión, o el hilo) y por cuánto tiempo. Las preguntas pueden contener datos personales.
6. **Dominio propio.** Quien envía necesita SPF, DKIM y DMARC bien configurados para que las respuestas no caigan en spam.

## Camino sugerido (si se aprueba)

1. Decidir dirección, buzón y público (decisiones 1 y 2).
2. Especificar la feature (`speckit-specify`) con el contrato servicio-API, parecido a `specs/011-bot-whatsapp-kapso/contracts/bot-servicio-api.md`.
3. Primera entrega en un buzón de pruebas, con el modo literal y sin memoria, y medir con preguntas reales.
4. Después: hilos como memoria y modo con razonamiento.
