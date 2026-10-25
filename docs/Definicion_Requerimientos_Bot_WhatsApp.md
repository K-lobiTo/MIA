# MIA: Definición de Requerimientos del Bot de WhatsApp

**Qué es este documento:** requerimientos del primer bot de WhatsApp de MIA, un canal nuevo para la **atracción de estudiantes** (personas interesadas en los posgrados que preguntan por horarios de matrícula, requisitos, planes de estudio, etc.), construido sobre [Kapso](https://docs.kapso.ai). Es **independiente de la versión 3** ([Definicion_Requerimientos_V3.md](Definicion_Requerimientos_V3.md), cerrada el 2026-10-21): parte del estado de [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md) (artefactos, accesos y topes) y de [ARQUITECTURA.md](ARQUITECTURA.md). Estado: **borrador de requerimientos (2026-10-21)**, con la especificación en `specs/011-bot-whatsapp-kapso/`. **Primera entrega: solo el sandbox de Kapso** (decisión del 2026-10-24, por ahora no es posible más que eso): todo lo funcional se construye y se acepta con el número de pruebas, y el camino a producción está en la sección 11 sin implementarse.

## 1. Alcance acordado

| Decisión | Elegido | Por qué |
|---|---|---|
| Naturaleza | El bot consulta a MIA como un artefacto más: usa los dominios, modos y topes de un **artefacto asignado**, que se puede cambiar en cualquier momento desde el panel (sección 3.1) | Es el principio I de la constitución: la API es el único punto de contacto entre el almacenamiento y los artefactos. Editar los dominios del artefacto asignado, o asignarle otro artefacto, cambia a qué información accede el bot, sin tocar el servicio. |
| Varios bots | Hoy **uno solo** (el plan gratuito de Kapso incluye 1 número), pero la estructura admite varios: cada bot tiene su número de Kapso y su artefacto | Agregar un bot en el futuro es registrar una fila en el panel y apuntar el webhook del número nuevo al mismo servicio, sin escribir código. |
| Modo de respuesta | El bot pide siempre el modo **literal** | Uso masivo y el modo literal es el más barato: `z-ai/glm-5.3-flash` con razonamiento bajo, 0,0004 USD por consulta de costo medio en la V3. Aunque el artefacto asignado permita razonamiento, el bot no lo usa. |
| Dónde corre la lógica | **Servicio propio pequeño**, aparte de la API de MIA, creado desde la interfaz de Railway como los demás servicios. Se llama `mia-whatsapp` (carpeta `whatsapp/`) porque atiende solo el canal de WhatsApp, y un único servicio atiende todos los números (sección 10) | Recibe los webhooks de Kapso, llama a la API y responde. Confirma en menos de 10 s, responde después, evita duplicados por reintento y limita mensajes (sección 3.2). No mezcla el canal con el motor. |
| Imágenes | Se **asocian a documentos** desde el panel y el bot las envía cuando el documento aporta a la respuesta | El RAG ya sabe qué documentos usó una respuesta (fuentes citadas, BUS-5): la asociación documento a imagen hace el resto de forma automática. |
| Dónde viven las imágenes | En la **base SQL** (Neon) y la API las sirve en una ruta pública con identificador no adivinable | El disco de Railway no es persistente y Kapso envía una imagen a partir de un enlace público. Sin servicio ni cuenta nuevos. |
| Contacto del programa | **El bot no lo da** | Se quiere que las personas prueben el bot antes de pasar con la asistente del programa. Quien quiera el contacto lo busca por su cuenta. |
| Memoria de conversación | **No** en esta versión: cada mensaje es independiente | Menos tokens y menos piezas. |
| Público | Personas externas y anónimas | Todo lo que el bot pueda consultar debe ser información que se le puede decir a cualquiera. |
| Tipos de mensaje | Solo texto | Ante audio, imagen, sticker u otro tipo, el bot pide que se escriba la pregunta. |

## 2. Cómo funciona

```
Persona (WhatsApp) -> Kapso -> webhook -> Bot (servicio propio) -> API de MIA (consulta como el artefacto asignado)
                                                |                        |
                                                |<--- respuesta, fuentes e imágenes
                                                v
                              Kapso API: envía texto, luego cada imagen (por enlace público a la API de MIA)
```

1. Kapso entrega el mensaje al bot por webhook. El bot verifica la firma, guarda el id del mensaje (para no responder dos veces un reintento) y devuelve `200` de inmediato.
2. En segundo plano, el bot pide a la API la consulta en modo literal, indicando de qué número de Kapso viene el mensaje. La API busca el bot de ese número y consulta con la configuración de su artefacto asignado (dominios, tope, estado).
3. La API responde con el texto, las fuentes y, nuevo, las **imágenes** asociadas a los documentos citados por la respuesta.
4. El bot envía el texto por Kapso y a continuación las imágenes (con su descripción como pie de foto).

## 3. Requerimientos

### 3.1 Bots y artefacto asignado (BOT)

La clave de un artefacto se guarda solo como hash y se muestra una vez (ART-2), así que el servicio del bot no puede leerla de la API. Por eso la asignación no se hace pegando la clave en una variable del servicio (que exigiría reiniciarlo para cambiarla): el bot se identifica ante la API con una credencial de servicio y el número de Kapso del mensaje, y la API resuelve a qué artefacto corresponde. El mecanismo exacto se confirma en el plan.

| Id | Requerimiento |
|---|---|
| BOT-1 | Un módulo nuevo del panel, **Bots**, lista los bots registrados con su nombre, el número de Kapso al que responden, su artefacto asignado, su estado (activo o desactivado) y los mensajes del mes frente a su tope (WAP-12). |
| BOT-2 | Registrar un bot con nombre (único), el identificador de su número de Kapso (único entre bots) y el artefacto asignado, elegido entre los artefactos registrados. Hoy se registra uno. |
| BOT-3 | **Cambiar el artefacto asignado a un bot en cualquier momento** desde el panel. Rige desde el mensaje siguiente, sin reiniciar ni volver a desplegar el servicio del bot. Los dominios y el tope que usa el bot son siempre los del artefacto asignado. |
| BOT-4 | Cambiar los dominios del artefacto asignado (ART-3) también cambia, desde el mensaje siguiente (ART-5), a qué información accede el bot. El panel muestra en el bot los dominios que hoy ve, para no tener que abrir el artefacto. |
| BOT-5 | Desactivar y reactivar un bot sin tocar el artefacto, que puede estar usándose en otros lugares. Un bot desactivado, sin artefacto asignado o con el artefacto desactivado responde el aviso de no disponible (WAP-7). |
| BOT-6 | Un mismo servicio atiende a todos los bots. Cada número de Kapso nuevo se atiende registrando un bot y apuntando el webhook de ese número al servicio. Un mensaje de un número que no corresponde a ningún bot se ignora y queda en el registro. |
| BOT-7 | Al asignar un artefacto, el panel advierte que el bot responde a **cualquiera** que escriba al número, y que los dominios del artefacto deben ser información que se pueda decir a cualquiera. |
| BOT-8 | En esta versión los textos fijos y los límites son los mismos para todos los bots (variables del servicio); configurarlos por bot queda para cuando haya más de uno. |

### 3.2 Comportamiento del bot (WAP)

| Id | Requerimiento |
|---|---|
| WAP-1 | Recibe los mensajes por el webhook de Kapso del número de WhatsApp del programa. Verifica la firma del webhook (HMAC-SHA256, ver [seguridad de webhooks](https://docs.kapso.ai/docs/platform/webhooks/security.md)) y rechaza lo que no la tenga válida. |
| WAP-2 | Responde `200` a Kapso en menos de 10 s, siempre, y procesa la consulta después. Un mismo mensaje entregado más de una vez (Kapso reintenta hasta 3 veces) se responde una sola vez, por el id del mensaje. |
| WAP-3 | Responde con el texto de la consulta en modo literal e incluye los nombres de los documentos que la respaldaron (principio V de la constitución), en forma breve y dentro del mismo mensaje. |
| WAP-4 | Adapta la respuesta al chat: usa el formato de WhatsApp (no encabezados Markdown), y si supera el límite de un mensaje (4096 caracteres) la divide en varios. |
| WAP-5 | Si la API responde "sin información suficiente", el bot lo dice con el texto de la sección 3.3, **sin dar el contacto del programa** y sin enviar imágenes. |
| WAP-6 | Si la consulta no se puede hacer porque el artefacto alcanzó su tope diario (la API responde 429), está desactivado (403) o falla, el bot responde un aviso breve de que no puede atender ahora, sin contacto y sin reintentar. Nunca deja la conversación en silencio, salvo lo dicho en WAP-12. |
| WAP-7 | Un mensaje que no es texto recibe el pedido de escribir la pregunta y no llama a la API. Un texto de más de 500 caracteres recibe el pedido de resumirlo. |
| WAP-8 | Limita los mensajes por número: 10 por hora y 30 por día (configurables). Al superarlo, responde una sola vez que espere y no procesa más hasta que pase la ventana. El número se usa solo para esto, en memoria, y no se guarda en el registro de consultas. |
| WAP-9 | Limita las consultas simultáneas a la API (5 a la vez, con una cola corta). Lo que exceda la cola se descarta sin respuesta, para que una ráfaga de muchos números no sature a MIA ni agote el tope en segundos. |
| WAP-10 | El saludo, que aclara que es un asistente automático que responde con documentos oficiales y pide no enviar datos personales, se antepone a la **primera respuesta** de cada conversación (la primera de un número en 24 h), dentro del mismo mensaje y no en uno aparte. Las preguntas pasan por WhatsApp (Meta), Kapso y el proveedor del modelo (OpenRouter, con retención cero): el aviso debe decirlo. |
| WAP-11 | Responde en español, a la conversación que originó el mensaje. No asume que el número de teléfono llega en el webhook (la documentación de Kapso indica que `phone_number`, `wa_id`, `from` y `to` pueden faltar por la migración a identificadores de usuario, BSUID). |
| WAP-12 | Cuenta de forma **persistente** (no en memoria) los mensajes del mes, los recibidos y los enviados, porque el plan gratuito de Kapso y los mensajes gratuitos de Meta se agotan antes que el presupuesto de modelos (sección 6). Al llegar a un tope mensual configurable (por defecto 1.800 de los 2.000 del plan gratuito), el bot deja de responder para no gastar ni un mensaje más, y el panel lo muestra en el bot (BOT-1). |
| WAP-13 | Se puede probar sin usar el número de producción, con el [sandbox de Kapso](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md). |

### 3.3 Límites y textos propuestos

Valores por defecto, configurables por variable del servicio. Se proponen para que el consumo de mensajes, no el de tokens, sea el límite real (sección 6).

| Parámetro | Valor propuesto | Motivo |
|---|---|---|
| Mensajes por número | 10 por hora y 30 por día | Una conversación típica de interés son pocas preguntas; frena a una persona o programa que repite, no a un grupo de números distintos. |
| Tamaño de la pregunta | 500 caracteres | Una pregunta de chat es corta, y limita los tokens por consulta. |
| Consultas simultáneas | 5, cola de 20 | Protege a la API de una ráfaga. |
| Imágenes por respuesta | 1 | Cada imagen es un mensaje más del plan; se sube si hace falta. |
| Tamaño máximo de una imagen | 2 MB, PNG o JPG | Livianas, por el espacio de la base gratuita (4.3). |
| Tope diario del artefacto | 1 USD (unas 2.400 consultas) | Casi nunca será el límite que se alcance primero. |
| Tope mensual de mensajes | 1.800 | 90 % del plan gratuito de Kapso, con reserva. |

| Texto | Propuesta |
|---|---|
| Saludo (WAP-10) | "Hola, soy un asistente automático de los posgrados. Respondo con base en documentos oficiales. Por favor no envíes datos personales." |
| Sin información (WAP-5) | "No encontré esa información en los documentos. Prueba con otras palabras o pregunta por otro tema, por ejemplo matrícula, requisitos o plan de estudios." |
| No disponible (WAP-6) | "Ahora mismo no puedo responder. Intenta de nuevo más tarde." |
| Límite por número (WAP-8) | "Enviaste muchos mensajes seguidos. Intenta de nuevo en un rato." |
| No es texto (WAP-7) | "Por ahora solo entiendo mensajes de texto. Escribe tu pregunta, por favor." |
| Pregunta larga (WAP-7) | "Tu mensaje es muy largo. Resúmelo en una o dos frases, por favor." |

## 4. Imágenes asociadas a documentos (IMG)

### 4.1 Qué se quiere

Que quien administra el inventario asocie una o varias imágenes a un documento, y que cuando una respuesta se apoya en ese documento, el bot envíe además esas imágenes. Ejemplo: la pregunta "¿cuándo es la matrícula?" recupera `horario_matricula.pdf`; el documento tiene asociada `horario_matricula.png`; el bot responde el texto y envía la imagen del horario. Un administrador no tiene que tocar nada más: el RAG ya decide qué documento corresponde.

### 4.2 Requerimientos

| Id | Requerimiento |
|---|---|
| IMG-1 | En el módulo Inventario, cada documento permite **agregar, ver, ordenar y quitar imágenes asociadas**. Cada imagen tiene una descripción opcional, que el bot usa de pie de foto. |
| IMG-2 | Solo se aceptan PNG y JPG (los formatos que admite WhatsApp para imágenes), con un tamaño máximo por imagen configurable (por defecto 2 MB). Lo demás se rechaza con un mensaje antes de subirlo. |
| IMG-3 | Las imágenes se guardan en la base de datos de la API y no en el disco (que no es persistente). Reemplazar una imagen genera un enlace nuevo; el anterior deja de servir. |
| IMG-4 | La API sirve cada imagen en una ruta pública (`GET /media/{id}`) sin clave, con un identificador aleatorio no adivinable, porque Kapso la envía por enlace. El panel avisa al subirla que **la imagen será pública**: nada que no pueda ver cualquiera. |
| IMG-5 | La consulta devuelve, junto a las fuentes, la lista de **imágenes de los documentos citados por la respuesta**, en el orden de las fuentes. Una respuesta "sin información" no devuelve imágenes. No se devuelven imágenes de documentos que solo se le pasaron al modelo y no aportaron: por eso depende de `QUERY_CITED_SOURCES=on` (decidida en la V3). |
| IMG-6 | El bot envía como máximo un número configurable de imágenes por respuesta (por defecto 1), en el orden recibido. Si una imagen falla al enviarse, el texto ya enviado no se pierde y el fallo queda en el registro del bot. |
| IMG-7 | Los administradores gestionan imágenes con el mismo alcance que ya tienen sobre los documentos (global o por programa); no se puede asociar una imagen a un documento de otro programa. |
| IMG-8 | Eliminar una imagen rige en la consulta siguiente, sin reiniciar nada. |
| IMG-9 | Sin imágenes asociadas, la consulta responde exactamente como hoy (la lista de imágenes va vacía): ningún otro artefacto cambia. |

### 4.3 Limitaciones conocidas

- La asociación es por documento, no por contenido: si el documento se cita, se envían sus imágenes (hasta el máximo del bot), aunque la pregunta use solo una parte.
- Un documento nuevo (otra versión del mismo PDF) es otro documento: no hereda las imágenes del anterior y se deben asociar de nuevo.
- La base gratuita tiene un espacio acotado (Neon free, 0,5 GB): conviene imágenes livianas. A 2 MB, cien imágenes ocupan unos 200 MB.

## 5. Cambios en la API y en el panel

| Dónde | Cambio | Para |
|---|---|---|
| Tabla nueva `bots` | Nombre, identificador del número de Kapso, artefacto asignado, estado y contador de mensajes del mes | BOT-1 a BOT-6 y WAP-12 |
| Tabla nueva `document_images` | Imagen (tipo, contenido, descripción, orden, identificador público) asociada a un documento | IMG-1 a IMG-4 |
| Migraciones nuevas (tras la `0005`) | Una por tabla | La API migra la base al arrancar: no se debe desplegar una versión con menos migraciones que las de la base (ver "Desplegar cambios" en [OPERACION.md](OPERACION.md)). |
| Rutas de administración de bots (`/bots`) | Crear, listar, cambiar el artefacto asignado, activar y desactivar; requieren administración | BOT-1 a BOT-5 |
| Ruta de consulta para el servicio del bot | Consulta con la credencial de servicio y el número de Kapso, aplicando el artefacto del bot (permisos, topes y registro en Uso como si lo consultara el artefacto) | Sección 2 |
| `POST /domains/{id}/documents/{doc}/images`, `PATCH` y `DELETE` | Agregar, reordenar, describir y quitar imágenes; requieren administración con el alcance del documento | IMG-1, IMG-7 y IMG-8 |
| `GET /media/{id}` | Sirve la imagen, pública, con caché | IMG-4 |
| `POST /query` y la ruta del bot | Agregan el campo `images` (lista de `{url, caption, document}`), vacío si no hay | IMG-5 y IMG-9 |
| Panel, módulo nuevo **Bots** | Lista, registro, cambio de artefacto, estado y dominios que ve cada bot | BOT-1 a BOT-7 |
| Panel, módulo Inventario | Acción "Imágenes" por documento con subida, orden, descripción y aviso de que son públicas | IMG-1 y IMG-4 |
| Servicio nuevo `mia-whatsapp` (carpeta `whatsapp/`) | Receptor de webhooks de Kapso que llama a la API y responde por Kapso; se despliega con `scripts/servicios.py` desde `origin/main`, que hay que extender | WAP-1 a WAP-13 |

## 6. Requerimientos no funcionales

- **Cuota de mensajes, el límite real.** Con el plan gratuito de Kapso (verificado el 2026-10-21 en su [página de precios](https://docs.kapso.ai/docs/whatsapp/pricing-faq.md)): 1 número, **2.000 mensajes al mes entre recibidos y enviados**, API sin límite de llamadas (100 por minuto) y 1 GB de almacenamiento de medios. Además, desde el 1 de octubre de 2026 los mensajes de servicio de Meta son facturables salvo **1.000 entregados gratis al mes por número**; las tarifas dependen del país y no están en la página. Una pregunta con respuesta de texto cuesta 2 mensajes (1 recibido y 1 enviado) y con una imagen, 3. Eso da **entre 660 y 1.000 preguntas al mes** antes de agotar el plan gratuito de Kapso, y **entre 500 y 1.000** antes de pagar a Meta. El presupuesto de modelos (2.400 consultas por día con 1 USD) no es el límite: lo es el número de mensajes. Una campaña con buena respuesta, o alguien que escriba desde muchos números, agotaría la cuota en días. De ahí WAP-9, WAP-10 (el saludo no es un mensaje aparte) y WAP-12.
- **Costo de modelos:** el tope diario del artefacto limita el gasto de OpenRouter. El servicio del bot suma costo de Railway aparte, que hay que medir: Railway Hobby ya ronda 4 a 4,5 USD de los 5 incluidos (V3, sección 2.7).
- **Latencia:** objetivo de que la respuesta de texto llegue en pocos segundos (el modo literal tarda 1,7 s en p50 y 5,0 s en p95 en la línea base de la V3); la confirmación al webhook no depende de ella.
- **Seguridad:** el webhook solo acepta peticiones firmadas; la credencial de servicio y la clave de Kapso viven solo en el servicio del bot y en la API; las imágenes públicas no deben contener nada que no pueda ver cualquiera; el bot no guarda números de teléfono.
- **Apagado:** se desactiva desde el panel (BOT-5 o ART-7) sin tocar el servicio, y el bot responde el aviso de WAP-6.
- **Pruebas:** pruebas automáticas del receptor (firma inválida, duplicado, no texto, 429, límite por número, tope mensual) con Kapso simulado, y pruebas de la API para cada ruta nueva, incluido el cambio de artefacto asignado. Los 19 casos de la batería del MVP siguen respondiendo igual.
- **Documentación:** al implementarse, actualizar ARQUITECTURA.md y OPERACION.md (nuevo servicio, variables y despliegue).

## 7. Criterios de aceptación (borrador)

En la primera entrega se verifican con el número de pruebas (sandbox) de Kapso, desde un teléfono registrado como de prueba; lo que el sandbox no admita (posiblemente las imágenes) se verifica con el proveedor simulado.

- Una pregunta al número de pruebas recibe respuesta de texto con los documentos que la respaldan, en modo literal, en pocos segundos.
- Con el documento `horario_matricula.pdf` y la imagen `horario_matricula.png` asociada desde el panel, la pregunta por el horario de matrícula devuelve el texto y la imagen, sin otra configuración.
- Cambiar desde el panel el artefacto asignado al bot, o los dominios de ese artefacto, cambia lo que el bot responde en el mensaje siguiente, sin reiniciar nada.
- Una pregunta sin respuesta en los documentos recibe el aviso sin contacto y ninguna imagen.
- Un reintento del webhook de Kapso no genera una segunda respuesta.
- Un audio recibe el pedido de escribir la pregunta, sin gasto de modelo.
- Al alcanzar el tope diario, desactivar el bot o su artefacto, el bot avisa y no consulta más; los demás artefactos siguen funcionando.
- Una persona que supera el límite por hora recibe un solo aviso y no consume más del tope. Al llegar al tope mensual de mensajes el bot deja de responder y el panel lo muestra.
- Un mensaje de un número de Kapso sin bot registrado se ignora.
- Las demás rutas de consulta no cambian (`images` vacío) y las pruebas existentes siguen pasando.

## 8. Fuera de alcance de esta versión

- Memoria de conversación y preguntas de seguimiento.
- Mensajes que no son texto (audio, imágenes recibidas, documentos).
- Mensajes iniciados por el programa (difusión, plantillas aprobadas): el bot solo responde.
- Ofrecer el contacto del programa o pasar a una persona: decisión expresa (2026-10-21).
- Modo con razonamiento.
- Textos y límites distintos por bot (BOT-8).
- Imágenes que dependan del contenido de la pregunta y no del documento, y asociación que sobreviva a una nueva versión del documento.
- Estadísticas propias del bot en Uso más allá de las del artefacto (consultas, gasto, valoración) y el contador mensual de mensajes.

## 9. Decisiones

**Resueltas el 2026-10-21**

1. Dominios del bot: los del artefacto asignado, editables en cualquier momento (BOT-3 y BOT-4). Qué dominios se asignan de inicio se decide al configurarlo y no bloquea la especificación.
2. Un solo bot hoy, estructura para varios (BOT-6).
3. Sin contacto del programa en las respuestas.
4. Límites propuestos en 3.3, a ajustar con el uso.
5. El servicio se crea desde la interfaz de Railway, como los demás.

**Resueltas en el plan (2026-10-24)** (la razón y las alternativas están en la [investigación de la spec 011](../specs/011-bot-whatsapp-kapso/research.md))

6. **Lenguaje del servicio:** Python 3.12 con FastAPI y `httpx`, en `whatsapp/` con un paquete propio (`mia_whatsapp`) que no importa `mia` (R1). El servicio se llama `mia-whatsapp`, atiende todos los números de WhatsApp, y los bots incrustados en páginas web no pasan por él (R16).
7. **Credencial de servicio y cómo identifica a cada bot:** una credencial compartida (`BOT_SERVICE_KEY`, encabezado `X-Bot-Service-Key`, el mismo valor en la API y en el servicio) más el `phone_number_id` de Kapso del mensaje; la API resuelve el artefacto asignado en las rutas `/bot/messages` y `/bot/query` (R2). La consulta del bot reutiliza la de los artefactos (`run_query`, R3).
8. **Contador mensual de mensajes (WAP-12):** una fila por bot y mes en la base de la API (`bot_message_counts`, incremento atómico), con el tope `BOT_MONTHLY_MESSAGE_CAP` en la API (R4).
9. **Qué imágenes se envían (pendiente 5 del borrador):** las de todo documento citado por la respuesta, en el orden de las fuentes (R6). Si el uso real muestra ruido, el siguiente paso es pedir además un puntaje mínimo de relevancia.
10. **Alcance de la primera entrega:** solo el sandbox de Kapso (2026-10-24); producción en la sección 11 (R17).

**Pendientes**

1. **Si la cuota gratuita alcanza (solo para producción, sección 11).** 2.000 mensajes de Kapso y 1.000 de Meta al mes dan 500 a 1.000 preguntas. Decidir antes de la campaña si se acepta ese límite (con el tope de WAP-12) o se contrata un plan de Kapso y se paga a Meta; falta la tarifa de Meta para el país de las personas que escriban.
2. **Lo que solo el sandbox de Kapso puede confirmar:** si admite el envío de imágenes (solo documenta texto e interactivos), la forma de la respuesta de Kapso a un envío, cuántos teléfonos admite y cuánto dura la sesión, y si Kapso avisa por algún evento cuando Meta no puede descargar el enlace de una imagen. Se anotan en la investigación de la spec al probar.

## 10. Para escalar más adelante

Nada de esto es de esta versión: el prototipo tiene una vigencia corta y un solo número. Es lo que convendría hacer, en este orden de probabilidad, si el bot crece, para que quien continúe sepa por dónde.

| Cuando pase esto | Qué conviene |
|---|---|
| Se quieren varios bots, de WhatsApp y también incrustados en las páginas web de los postgrados (mínimo dos de cada tipo: Postgrados de Computación y Analítica de Negocios van separados, anotado el 2026-10-24) | **WhatsApp: un solo servicio `mia-whatsapp` para todos los números.** Cada aviso de Kapso trae el número al que escribió la persona y la API resuelve el bot y su artefacto, así que un bot nuevo es una fila en el panel y apuntar el webhook de su número al mismo servicio (un servicio por bot multiplicaría el costo y las variables, y solo se justifica por otra cuenta de Kapso, aislar fallos o una carga muy distinta). **Web: sin servicio.** Un chat incrustado no tiene webhook, ni envío por Kapso, ni cuota de mensajes: es un componente de interfaz que llama a una ruta pública de la API, con identificador público del bot, orígenes permitidos y límite por IP (la clave de un artefacto no puede ir en el código de una página pública). Es una feature aparte, que reutiliza la tabla `bots` y el artefacto asignado. Cada bot usa su propio artefacto (dominios y tope diario). Con dos bots de WhatsApp se vuelven necesarios los textos, límites y tope mensual por bot (BOT-8) y revisar si el módulo Bots sigue siendo solo del alcance global. Detalle en [la investigación de la spec 011](../specs/011-bot-whatsapp-kapso/research.md) (R16). |
| Se agrega otro número de Kapso (otro programa u otro público) | Registrar otro bot en el módulo Bots con su artefacto y apuntar el webhook del número al mismo servicio (BOT-6). Si los textos o los límites deben ser distintos, pasarlos de variables del servicio a campos del bot (BOT-8). El plan gratuito de Kapso solo admite 1 número: hará falta un plan que admita más. |
| La cuota de mensajes se agota (sección 6) | Contratar un plan de Kapso y pagar los mensajes de servicio de Meta (tarifa según el país). El tope mensual de WAP-12 pasa de límite de la cuota gratuita a presupuesto de gasto. Mientras tanto, lo que más ahorra es no enviar mensajes de más: saludo dentro de la primera respuesta, texto y fuentes en un solo mensaje y pocas imágenes. |
| El servicio corre en más de una réplica o se reinicia a menudo | Los ids de mensajes ya vistos, los límites por número y el saludo por conversación viven hoy en la memoria del servicio: se pierden al reiniciar y no se comparten entre réplicas. Moverlos a la base de la API o a un almacén clave-valor. El contador mensual ya nace persistente (WAP-12). |
| Llegan ráfagas que la cola de WAP-9 no absorbe | Reemplazar la cola en memoria por una cola externa. El diseño ya lo permite: el webhook confirma de inmediato y procesa después (WAP-2), así que la cola es un cambio interno del servicio. |
| El espacio de la base gratuita se acerca a su límite por las imágenes (Neon free, 0,5 GB) | Mover las imágenes a un almacenamiento de objetos (Cloudflare R2 o similar). La ruta pública `GET /media/{id}` puede redirigir a la nueva ubicación, de modo que ni el bot ni el contrato de `images` cambian. Subirlas a Kapso (1 GB de medios en el plan gratuito) es otra opción, pero su duración no está documentada y habría que verificarla. |
| Se quiere memoria de conversación (preguntas de seguimiento) | Guardar los últimos mensajes de cada conversación en el mismo almacén y usarlos para reformular la búsqueda. Sube los tokens por consulta, así que se mide con el módulo Uso antes de dejarla encendida. No requiere un framework. |
| Se quiere un bot que decida qué buscar en varios pasos, o dar el modo con razonamiento | Primero un bucle simple con un máximo de iteraciones, como dice [ARQUITECTURA.md](ARQUITECTURA.md#orquestación-sin-langchain-ni-langgraph). Solo si crece más se evalúa LangGraph, para ese modo y detrás de la misma interfaz. El modo con razonamiento tarda más de 10 s (p95 de 11,2 s), pero el diseño asíncrono lo tolera; el costo por consulta sube bastante y habría que revisar los límites. |
| Se quiere ver cómo rinde cada bot | Estadísticas propias por bot en Uso (consultas, mensajes del mes, imágenes enviadas, "sin información" por tema), hoy fuera de alcance (sección 8). Es el dato que también decide si se retoma el reranker (V3, sección 2.10). |

## 11. Del sandbox a producción

La primera entrega funciona solo con el sandbox (2026-10-24). Esta sección es el camino, en orden, para abrir el bot al público; **nada de esto se implementa ni se valida en esta versión**. El diseño no cambia para ese paso: un número de producción se registra como un bot nuevo en el módulo Bots, con su `phone_number_id` y su artefacto, y el mismo servicio `mia-whatsapp` lo atiende.

| # | Qué hacer | Detalles y advertencias |
|---|---|---|
| 1 | **Cuenta de Meta de la institución** | Meta exige un Business Portfolio y una cuenta de WhatsApp Business (se pueden crear durante el alta), con razón social, dirección, teléfono y un **sitio web público con HTTPS**, sin problemas pendientes de verificación o de facturación. Puede pedir verificación del negocio y revisar el nombre que se muestra; los plazos no están documentados, por eso conviene empezarlo antes. Debe quedar a nombre de la institución, no de una cuenta personal. Preguntar a Comunicación o a TI si ya existe. |
| 2 | **Elegir el número** | Tres opciones en Kapso: (a) *instant setup*, un número de EE. UU. de Kapso (gratis en el plan gratuito, una sola vez, y se libera si pasa 30 días sin mensajes de producción; la documentación no aclara si sirve para atender público en Costa Rica); (b) un **número propio dedicado**, que pasa por completo a la API y deja de funcionar en la app de WhatsApp Business (recomendado para producción); (c) *coexistencia* con la app de WhatsApp Business, que mezclaría las conversaciones de la asistente con las del bot. |
| 3 | **Conectar el número en Kapso** | *Connected numbers > Connect new number* y el alta incorporada de Meta. Anotar el `phone_number_id` del número (no es el teléfono ni el id de la cuenta de WhatsApp Business). |
| 4 | **Plan y cuota** | El plan gratuito incluye 1 número, 2.000 mensajes al mes (recibidos y enviados) y 100 solicitudes por minuto; Meta cobra los mensajes de servicio desde el 2026-10-01 salvo 1.000 gratis al mes por número, con tarifa según el país (no publicada en la página de Kapso). Decidir antes de la campaña: aceptar entre 500 y 1.000 preguntas al mes con el tope de 1.800 (`BOT_MONTHLY_MESSAGE_CAP`), o contratar un plan y pagar a Meta, y entonces el tope pasa de límite de la cuota gratuita a presupuesto de gasto. Un **segundo número exige un plan de pago**; falta saber si la cuota es por cuenta o por número. |
| 5 | **Webhook del número** | Los avisos de mensajes son por número: crearlo con `POST https://api.kapso.ai/platform/v1/whatsapp/phone_numbers/{phone_number_id}/webhooks`, `url` de `mia-whatsapp`, `events` `["whatsapp.message.received"]` y un `secret_key` que se elige (puede ser el mismo para todos los números). Si Kapso agrupa los avisos (buffering), el servicio ya procesa los lotes. |
| 6 | **Registrar el bot** | En el módulo Bots: nombre, `phone_number_id` de producción y artefacto. El bot del sandbox puede quedar para pruebas. |
| 7 | **Revisar qué ve y qué publica** | El artefacto del bot solo con información que se pueda decir a cualquiera (no las actas del Consejo ni dominios con datos de personas); las imágenes asociadas son públicas. Revisar la lista de dominios que muestra el panel antes de abrir el número. |
| 8 | **Validar con el número real lo que el sandbox no cubrió** | Las imágenes (si el sandbox no las admitió), la forma de la respuesta de Kapso a un envío, los tiempos reales, el aspecto del formato y del pie de foto en el teléfono, y la batería del MVP (19 de 19). |
| 9 | **Ajustar los límites con datos reales** | 10 mensajes por hora y 30 por día por persona, cola de 20, 1 imagen por respuesta, tope mensual de 1.800 y tope diario del artefacto: se ajustan con el uso, mirando el módulo Uso y el consumo del módulo Bots. |
| 10 | **Operación** | Medir el costo del servicio nuevo en Railway durante la primera semana (la cuenta ya ronda 4 a 4,5 USD de los 5 incluidos, V3 sección 2.7) y mantener el límite de gasto de Railway. Definir quién atiende si el bot se cae o llega al tope mensual (el panel lo muestra). Vigilar el espacio de las imágenes en la base gratuita (0,5 GB). |
| 11 | **Cuando crezca** | La sección 10 (réplicas, cola externa, imágenes en almacenamiento de objetos, memoria de conversación) y, para varios bots, textos, límites y tope por bot (BOT-8), más los bots incrustados en páginas web, que son otra feature. |

**Lo que ya queda listo en la primera entrega y no habrá que rehacer**: la estructura para varios bots, los límites por persona y por ráfaga, el tope mensual persistente, el saludo con el aviso a terceros, la advertencia de acceso público en el panel, las imágenes asociadas a documentos y el simulador para pruebas sin gastar cuota.

## Anexo A. Fuentes consultadas (2026-10-21 y 2026-10-24)

- [Webhooks de Kapso: visión general](https://docs.kapso.ai/docs/platform/webhooks/overview) (respuesta en menos de 10 s, firma HMAC-SHA256)
- [Webhooks de Kapso: entrega](https://docs.kapso.ai/docs/platform/webhooks/advanced.md) (hasta 3 intentos, orden por conversación, pausa automática)
- [Enviar una imagen con Kapso](https://docs.kapso.ai/docs/whatsapp/send-messages/image.md) (imagen por enlace público con `image.link` y pie de foto)
- [Precios de Kapso](https://docs.kapso.ai/docs/whatsapp/pricing-faq.md) (plan gratuito: 1 número, 2.000 mensajes al mes, 1 GB de medios; mensajes de servicio de Meta facturables desde el 2026-10-01 con 1.000 gratis por número)
- [Límites de la API de Kapso](https://docs.kapso.ai/api/rate-limits.md) (100 solicitudes por minuto en el plan gratuito)
- [Conectar WhatsApp](https://docs.kapso.ai/docs/how-to/whatsapp/connect-whatsapp.md), [alta instantánea](https://docs.kapso.ai/docs/platform/phone-numbers/instant-setup.md), [sandbox](https://docs.kapso.ai/docs/how-to/whatsapp/use-sandbox-for-testing.md) y [resumen de webhooks](https://docs.kapso.ai/docs/platform/webhooks/overview.md) (2026-10-24: requisitos de Meta, opciones de número, sandbox solo con texto e interactivos, webhook por número con secreto elegido)
- [Nodo webhook de Kapso](https://docs.kapso.ai/docs/flows/step-types/webhook-node.md) (alternativa descartada: su tiempo máximo no está documentado)
