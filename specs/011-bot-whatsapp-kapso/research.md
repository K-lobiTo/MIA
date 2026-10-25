# Research: Bot de WhatsApp con Kapso

Decisiones de diseño con su razón y las alternativas. Los requerimientos de partida están en [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md) y las reglas verificables en [spec.md](spec.md). Los datos de Kapso se verificaron el 2026-10-24 en su documentación: [eventos de webhook](https://docs.kapso.ai/docs/platform/webhooks/event-types), [seguridad de webhooks](https://docs.kapso.ai/docs/platform/webhooks/security.md) y [enviar un texto](https://docs.kapso.ai/docs/whatsapp/send-messages/text.md); el resto (reintentos, enlace de imagen, cuota del plan gratuito) viene del Anexo A del documento de requerimientos (2026-10-21).

Las cuatro decisiones que la spec dejó al plan son R1 (lenguaje), R2 (credencial de servicio), R4 (contador mensual) y R6 (qué imágenes se envían).

## R1. El servicio: Python con FastAPI, en la carpeta `whatsapp/`, con paquete propio

**Decision**: el bot es un servicio de Python 3.12 con FastAPI y `httpx`, en una carpeta nueva `whatsapp/` (`whatsapp/pyproject.toml`, `whatsapp/Dockerfile`, `whatsapp/railway.json`, `whatsapp/src/mia_whatsapp/`, `whatsapp/tests/`). Es un paquete aparte que **no importa `mia`**: habla con la API solo por HTTP. En Railway se crea desde la interfaz con *Root Directory* `whatsapp`, igual que `web/admin` y `web/consulta`.

**Rationale**:
- **Misma herramienta que el resto del proyecto**: `pytest`, `ruff`, `httpx` y FastAPI ya se usan (recomendación del documento de requerimientos, sección 9). Quien continúe el proyecto no aprende otro lenguaje.
- **Imagen pequeña**: el paquete `mia` arrastra `onnxruntime`, `qdrant-client`, `sentencepiece` y el modelo de embeddings (la imagen de la API pesa gigas). El bot solo necesita cuatro dependencias, así que su imagen y su consumo en Railway son una fracción.
- **Sin acoplar canal y motor** (decisión del 2026-10-21): el bot no toca Qdrant ni la base; solo llama a rutas de la API. Cambiar de proveedor de WhatsApp es cambiar un cliente dentro del bot.
- Todo el trabajo del bot es de entrada y salida de red (webhook, API de MIA, API de Kapso): `asyncio` con un solo proceso alcanza para las decenas de mensajes por minuto del plan gratuito.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| TypeScript con el SDK de Kapso | Otro lenguaje, otra herramienta de pruebas y de lint, y el SDK no aporta nada que `httpx` no haga en tres llamadas (enviar texto, enviar imagen y verificar la firma). |
| Una ruta dentro de la API de MIA con tareas en segundo plano | Mezcla el canal con el motor; la API está cerca de su límite de memoria (512 MB) y un reinicio de la API para actualizar el bot interrumpiría las consultas de los demás artefactos. Fue descartada el 2026-10-21. |
| Nodo `webhook` o agentes de Kapso | Su tiempo máximo de espera no está documentado y moverían la lógica de límites y de saldo fuera del repositorio. |
| Poner el bot dentro de `src/` como segundo paquete del mismo `pyproject.toml` | La imagen del bot instalaría las dependencias de la API (`pip install .`). |

## R2. Credencial de servicio compartida más el número de Kapso del mensaje

**Decision**: el servicio del bot se identifica ante la API con una **credencial de servicio**, la variable `BOT_SERVICE_KEY`, que existe con el mismo valor en la API y en el bot. La envía en el encabezado `X-Bot-Service-Key` y la API la compara con `hmac.compare_digest` (como `ADMIN_KEY`). Vacía en la API, las rutas del bot responden 401 (están apagadas). Cada llamada incluye `number_id`, el `phone_number_id` de Kapso al que escribió la persona (viene en cada aviso). La API busca el bot de ese número, toma su **artefacto asignado** y consulta con la configuración de ese artefacto.

**Rationale**:
- **La clave de un artefacto no se puede leer** (solo se guarda su hash, ART-2), así que el bot no puede llevarla en una variable ni la API puede dársela. Con esta credencial el artefacto asignado vive en la base y se cambia desde el panel sin tocar el servicio (BOT-3 y SC-006).
- **Una credencial para todos los bots**: un solo servicio atiende todos los números, así que no hay un secreto por bot que repartir. Un bot nuevo es una fila en el panel.
- **Poder acotado**: la credencial solo abre las rutas `/bot/...` (contar mensajes y consultar con el artefacto de un bot registrado). No sirve para administrar ni para consultar con otro artefacto, a diferencia de `ADMIN_KEY`.
- **Las mismas reglas que un artefacto**: la ruta del bot ejecuta el mismo código de consulta (R3), así que permisos, topes diarios y registro en Uso valen igual (FR-028).
- **La API nunca recibe el teléfono de la persona**: `number_id` es el número de la institución, no el de quien escribe (FR-027 y SC-010 se cumplen por construcción).

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Guardar la clave del artefacto en una variable del bot | Obliga a reiniciar el servicio para cambiarla y a regenerar la clave del artefacto para tenerla a mano (lo que invalida a los demás clientes del artefacto). Es justo lo que se quiso evitar. |
| Guardar la clave del artefacto en claro en la tabla `bots` | Rompe ART-2 (clave solo como hash) y deja un secreto que el panel podría filtrar. |
| Una clave propia por bot, guardada como hash | Es el patrón de los artefactos, pero con un solo servicio que atiende todos los números solo agrega pasos (mostrar una vez, copiar a una variable) sin ganar seguridad. Si algún día hay un servicio por bot, es el cambio natural. |
| Reutilizar `ADMIN_KEY` | Daría al servicio público poder de administración sobre todo MIA. |

## R3. Reutilizar la consulta: una función `run_query` y una ruta nueva `POST /bot/query`

**Decision**: el cuerpo de `query()` en `src/mia/api/routes/query.py` pasa a una función `run_query(payload, artifact, session)` sin cambiar su lógica, y la ruta `POST /query` la llama con el artefacto de la clave. La ruta nueva `POST /bot/query` la llama con el artefacto del bot, con `mode = "literal"` fijo y `domains` = los dominios que el artefacto cubre hoy (`allowed_domain_ids`, calculados en cada consulta). Un artefacto sin dominios responde "sin información" sin buscar.

**Rationale**:
- **Un solo camino de consulta**: topes, rechazos, registro, búsqueda híbrida, reranker, citas y respuestas completas valen igual para el bot, y lo que se corrija en uno se corrige en el otro. Los demás artefactos no cambian (FR-039).
- **Los dominios los decide la API**: como el bot no tiene la lista, el panel manda. Un dominio nuevo de una unidad ya permitida queda visible desde la consulta siguiente (BOT-4).
- **El modo literal lo fija el servidor**: aunque el artefacto asignado permita razonamiento, la ruta del bot no acepta otro modo (FR-013). Si el artefacto asignado no permite literal, el rechazo de siempre (403) llega al bot, que responde "no disponible".
- Las pruebas existentes parchean funciones del módulo `mia.api.routes.query`; dejar `run_query` allí no las rompe.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Que el bot llame a `POST /query` con la clave del artefacto | Imposible (R2): la clave no se puede leer. |
| Copiar la lógica de la consulta en la ruta del bot | Dos caminos que se desincronizan (el reranker, la híbrida y las citas ya los hicieron crecer). |
| Un parámetro oculto en `POST /query` para el bot | Mezcla dos tipos de cliente en una ruta y exigiría que `POST /query` aceptara la credencial de servicio. |

## R4. Contador mensual: tabla en la base de la API, un incremento atómico por llamada

**Decision**: tabla nueva `bot_message_counts` (clave `bot_id` + `month`, con `received` y `sent`), en la base de la API. El servicio la actualiza con `POST /bot/messages` (`received` y `sent` a sumar) y la misma respuesta dice el estado: `ok`, `disabled`, `cap_reached` o `unknown_bot`. El tope mensual es la variable `BOT_MONTHLY_MESSAGE_CAP` **de la API** (1.800 por defecto), igual para todos los bots. El mes es el mes calendario en la zona de `CAP_TIMEZONE`, como el día de los topes de gasto.

**Rationale**:
- **Persistente y compartido**: sobrevive a los reinicios del bot (SC-008) y es la misma cifra que muestra el panel (BOT-1), sin que el panel hable con el bot.
- **Una fila por bot y mes** da historial gratis y evita el reinicio del contador el día 1 (la fila nueva nace en cero).
- **Atómico**: `UPDATE ... SET received = received + n`; si no hay fila se inserta y, si otro proceso la insertó a la vez, se reintenta el `UPDATE`. Funciona igual en SQLite y Postgres.
- **El tope en la API** (no en el bot) porque el panel lo muestra y porque es lo que decide `cap_reached`; es el mismo valor para todos los bots (BOT-8: por bot queda para cuando haya más de uno).
- **Orden de llamadas**: `received = 1` al llegar el mensaje (y de ahí se decide si responder), `sent = k` tras enviar. Cada mensaje recibido cuesta dos o tres llamadas rápidas a la API; el plan gratuito de Kapso da 100 por minuto a Kapso, la API de MIA no tiene ese límite.
- **Se pasa del tope por poco como máximo**: los mensajes en vuelo cuando se alcanza el tope se envían; la reserva de 200 mensajes (1.800 de 2.000) lo absorbe.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Columnas `month` y `month_count` dentro de `bots`, con reinicio al cambiar de mes | Hay que cambiar el mes con cuidado ante dos servicios a la vez y no hay historial. |
| Contador solo en memoria del bot | Se pierde al reiniciar (lo que la spec prohíbe, FR-024). |
| Que el panel pregunte a Kapso por el consumo | No está documentado un endpoint de consumo del plan, y el conteo propio también cuenta los mensajes no respondidos. |
| Tope mensual por bot (columna) | Fuera de alcance (BOT-8). Se agrega como columna cuando haya más de un bot. |

## R5. Imágenes: en la base como binario, validadas por su contenido, con identificador público que rota

**Decision**: tabla `document_images` (migración `0007`), con la imagen en una columna binaria (`LargeBinary`, cargada solo cuando se sirve: columna `deferred`), el tipo, el tamaño, la descripción, la posición y un `public_id` aleatorio (`secrets.token_urlsafe(24)`, 192 bits). La API valida por el **contenido**, no por el nombre ni por el tipo que declara el navegador: firma PNG (`89 50 4E 47 0D 0A 1A 0A`) con el trozo `IEND` al final, o JPEG (`FF D8 FF`) con el marcador `FF D9` al final, y un tamaño máximo (`MAX_IMAGE_MB`, 2 por defecto, con la lectura de un byte de más como en `upload_document`). Reemplazar una imagen cambia el contenido **y** el `public_id`: el enlace anterior deja de servir. `GET /media/{public_id}` es público, sin clave, con `Cache-Control: public, max-age=3600`, `X-Content-Type-Options: nosniff` y el tipo guardado.

**Rationale**:
- **El disco de Railway no persiste** y Kapso necesita un enlace público (decisión del 2026-10-21): la base de Neon ya existe y no suma cuentas ni servicios.
- **Validar la firma y el final del archivo** rechaza un archivo con otro formato aunque se llame `.png`, y una imagen truncada o cortada (la spec pide rechazar corruptas). Decodificar con una biblioteca de imágenes sumaría una dependencia y memoria a una API que está al límite.
- **`deferred`**: listar imágenes para el panel o para la respuesta de una consulta no debe leer megabytes de la base.
- **El id público rota al reemplazar** para que el enlace anterior muera (IMG-3), y no es adivinable: nadie enumera imágenes ajenas.
- **Caché de una hora**: Kapso o Meta pueden bajar la imagen una vez por envío; la caché evita ir a la base cada vez. Como al reemplazar el enlace cambia, la caché nunca sirve algo vigente equivocado; al quitar una imagen puede seguir sirviéndose desde cachés externas hasta una hora (se acepta y se documenta).
- **Espacio**: a 2 MB, 100 imágenes son unos 200 MB de los 0,5 GB de Neon free; es la limitación conocida de la spec, con el camino de salida en la sección 10 del documento de requerimientos.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Almacenamiento de objetos (R2, S3) | Cuenta y servicio nuevos para el prototipo; queda como escala (sección 10). La ruta `/media/{id}` puede redirigir sin cambiar el contrato. |
| Subir las imágenes a Kapso | Su duración y su cuota (1 GB) no están documentadas; habría que verificarlo. |
| Pillow para decodificar | Dependencia y RAM extra en la API; la firma y el final del archivo cubren lo que importa. |
| Identificador secuencial o el id interno de la fila | Adivinable: cualquiera podría recorrer las imágenes. |

## R6. Qué imágenes se envían: las de los documentos de las fuentes que la respuesta cita

**Decision**: `run_query` calcula las imágenes **después** de elegir las fuentes (las que el modelo cita con `QUERY_CITED_SOURCES=on`): toma el documento de cada fuente en su orden, quita repetidos, y busca sus imágenes por posición con **una sola consulta** a la base. El resultado va en `images` de `QueryResponse` como `{url, caption, document}` con `url = "/media/{public_id}"` (relativa) y `document` el nombre del archivo. Una respuesta "sin información" devuelve la lista vacía. El bot toma las primeras `BOT_MAX_IMAGES` (1 por defecto) y construye el enlace con `MIA_API_URL`. Si la consulta de imágenes falla, la respuesta se entrega sin ellas con un aviso en el registro.

**Rationale**:
- **Es la pregunta pendiente 5 del documento**: se elige "todo documento citado", como allí se recomienda; si el uso real muestra ruido, el siguiente paso es exigir un puntaje mínimo.
- **Depende de las citas**: con `QUERY_CITED_SOURCES=off` las fuentes son todos los pasajes entregados al modelo y se mandarían imágenes de documentos que no aportaron. La spec lo asume encendida; la ruta del bot **no la enciende por su cuenta** (es un cambio de despliegue, ver quickstart) y la nota de Uso permite ver si se rompe.
- **URL relativa**: la API no conoce su dirección pública (detrás del proxy de Railway, `request.base_url` puede decir `http`); el bot ya conoce `MIA_API_URL`.
- **Fallar sin imágenes**: una consulta que ya gastó modelo no debe perder su respuesta por una falla de las imágenes.
- **Los demás artefactos** reciben el campo nuevo (`images: []` si no hay) sin cambiar nada más (FR-038).

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Imágenes de todos los fragmentos recuperados | Manda imágenes de documentos que solo se le pasaron al modelo. |
| Puntaje mínimo de relevancia por documento | Más piezas sin evidencia de que haga falta (pendiente 5, se retoma con datos). |
| Que el modelo elija la imagen | Gasta tokens y rompe la regla de que el administrador no decide cuándo se envía, el RAG sí. |
| URL absoluta desde un ajuste `PUBLIC_BASE_URL` | Otra variable que puede quedar mal puesta; el bot ya tiene la dirección. |

## R7. Webhook de Kapso: firma, deduplicación y confirmación inmediata

**Decision**: `POST /webhooks/kapso` en el bot:
1. Lee el **cuerpo crudo** y verifica `X-Webhook-Signature` (HMAC-SHA256 del cuerpo con `KAPSO_WEBHOOK_SECRET`, en hexadecimal minúscula, sin prefijo) con `hmac.compare_digest`. Firma ausente o inválida: 401, sin procesar.
2. Solo atiende el evento `whatsapp.message.received` (encabezado `X-Webhook-Event`); cualquier otro evento recibe 200 y se ignora. Si Kapso entrega en lote (`batch: true`, `data: [...]`), procesa cada elemento con la misma forma.
3. Deduplica por `message.id` (y por `X-Idempotency-Key` si llega) con un conjunto con vigencia en memoria (R8).
4. Responde 200 **antes** de procesar: la consulta corre en una tarea de fondo (`BackgroundTasks`, que FastAPI ejecuta tras enviar la respuesta).

**Rationale**:
- Kapso exige 200 en menos de 10 s, reintenta hasta 3 veces y pausa el aviso si fallan muchas entregas seguidas (Anexo A): confirmar de inmediato y sin depender de la consulta evita reintentos y pausas (FR-011).
- **El cuerpo debe firmarse crudo**: si se parsea y se vuelve a serializar, la firma no coincide. Por eso el receptor lee los bytes primero.
- **Sin protección contra repetición documentada** (no hay marca de tiempo en la firma): la deduplicación por `message.id` cubre los reintentos y un mensaje repetido por un atacante que reuse una firma válida no se responde dos veces.
- **El número no se asume** (FR-021): la dirección de respuesta sale de `message.from` si existe, si no de `conversation.phone_number`, y si tampoco, del identificador de usuario `message.from_user_id`, que Kapso envía como `recipient` (R9).

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Procesar dentro de la petición del webhook | Una consulta lenta (p95 de 5 s, hasta 30 s en una falla) arriesga el límite de 10 s y los reintentos. |
| Cola externa (Redis) | Una pieza más sin necesidad con un solo proceso; está en la sección 10 del documento como escala. |
| Responder 200 aun con firma inválida | Aceptaría tráfico no firmado; 401 es lo que Kapso documenta. |

## R8. Estado en memoria del bot y sus límites

**Decision**: el bot guarda en memoria, acotado y con vigencia:
- **Mensajes ya vistos**: diccionario `id -> hora` con vigencia de 24 h (`BOT_SEEN_TTL_HOURS`) y tope de 50.000 entradas (las más viejas salen primero).
- **Límite por persona**: por clave de persona, las horas de los mensajes aceptados en la última hora y el último día (ventanas deslizantes: 10 por hora, 30 por día), y la marca de "ya avisado" mientras dura el bloqueo. Los mensajes bloqueados no suman a la ventana, para que el bloqueo termine cuando pasa la ventana y no se prolongue por insistir.
- **Saludo**: la hora del último saludo por persona; se saluda de nuevo pasadas 24 h.
- **Consultas simultáneas**: un `asyncio.Semaphore(5)` y un contador de espera: con 20 esperando, el mensaje se descarta sin respuesta (queda en el registro).
- **Clave de persona**: SHA-256 de una sal aleatoria del proceso más el identificador que haya (`from_user_id`, `from`, `conversation.phone_number` o `conversation.id`). El número nunca se guarda en claro, ni se escribe en el registro.
- Una limpieza periódica (cada minuto) retira lo vencido; los diccionarios tienen tope de tamaño (50.000 personas) para que una ráfaga de números distintos no agote la memoria.

**Rationale**:
- Es el diseño que el documento de requerimientos acepta para el prototipo (un proceso, reinicios raros); el contador mensual, lo único que no debe perderse, ya vive en la API (R4).
- **La sal por proceso** hace que ni siquiera un volcado de memoria permita recuperar teléfonos de los hashes, y que la clave cambie en cada reinicio (se acepta: reiniciar reinicia los límites).
- **Acotar los diccionarios** es la defensa contra el ataque que más se puede temer con un número público: muchos números distintos que llenan la memoria.
- **No sumar los bloqueados a la ventana** cumple SC-007 ("se procesan 0 mensajes suyos más hasta que pasa la ventana") sin castigar eternamente a quien insiste.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Estado en la base de la API (ids vistos y límites) | Una escritura por mensaje para algo que se tolera perder; es el camino de escala si hay réplicas (sección 10). |
| Redis | Servicio nuevo sin necesidad con un solo proceso. |
| Guardar el teléfono en claro en memoria | Innecesario: solo hace falta reconocer a la persona, no saber cuál es. |

## R9. Enviar por Kapso: texto, imagen, dirección de respuesta y límite de 100 por minuto

**Decision**: el cliente de Kapso (`httpx`) envía a `POST {KAPSO_API_URL}/{phone_number_id}/messages` (por defecto `https://api.kapso.ai/meta/whatsapp/v24.0`) con el encabezado `X-API-Key`:
- **Texto**: `{"messaging_product": "whatsapp", "to": "<teléfono>", "type": "text", "text": {"body": "..."}}`.
- **Imagen**: `{"messaging_product": "whatsapp", "to": "<teléfono>", "type": "image", "image": {"link": "<MIA_API_URL>/media/<id>", "caption": "..."}}`.
- **Sin teléfono** (identificadores de usuario): se cambia `to` por `"recipient": "<from_user_id>"` más `"recipient_type": "individual"`.
- Un **limitador de envíos** (`BOT_KAPSO_RATE_PER_MIN`, 90 por defecto) espera antes de superar los 100 por minuto del plan gratuito.
- Un fallo de red o un 5xx se reintenta **una vez** tras un segundo; un 4xx no se reintenta. Un fallo de la imagen no afecta al texto ya enviado y queda en el registro (FR-035).

**Rationale**:
- Es la forma documentada por Kapso para texto, imagen por enlace público y destinatarios por identificador de usuario; los mensajes que no son plantillas exigen una ventana de servicio de 24 h abierta, que siempre lo está porque el bot solo responde a un mensaje que acaba de llegar.
- **El limitador** evita perder respuestas ante una ráfaga (5 consultas a la vez con 2 o 3 envíos cada una) sin necesidad de una cola externa.
- **Un solo reintento** cubre un tropiezo de red sin multiplicar mensajes que cuestan cuota.
- **Faltan en la documentación consultada** la forma de la respuesta y los códigos de error de Kapso: el cliente trata cualquier 2xx como entregado y registra el cuerpo de un error (sin teléfonos) para diagnóstico; se confirma con el número de pruebas (quickstart).
- **Límite conocido de los fallos de imagen**: Kapso responde al envío cuando acepta el mensaje, y Meta descarga el enlace de la imagen después, de forma asíncrona. Si esa descarga falla (por ejemplo, el enlace ya no sirve porque la imagen se reemplazó), el bot no lo sabe: el envío ya figuraba como aceptado. Solo se registran los rechazos que Kapso devuelve al enviar. Se acepta en el prototipo; el sandbox dirá si Kapso informa un estado de fallo por otro evento (tarea de anotación de hallazgos), y ese evento sería el camino para registrarlos.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| SDK de Kapso | R1. |
| Responder sin limitador y reintentar los 429 | Gasta cuota en reintentos y demora más a todos. |
| Reintentar varias veces | Un mensaje de más cuesta cuota del plan, que es el límite real. |

## R10. Formato del texto: de Markdown a WhatsApp, fuentes breves y partición

**Decision**: una función pura convierte la respuesta del modelo (Markdown) al formato de WhatsApp: `**negrita**` y `__negrita__` a `*negrita*`, `*cursiva*` y `_cursiva_` a `_cursiva_`, `~~x~~` a `~x~`, encabezados `#` a una línea en `*negrita*`, `[texto](enlace)` a `texto (enlace)`, listas con `-` o `*` a `- `, tablas a filas de texto, y bloques de código quedan entre comillas invertidas. Debajo va una línea **`Fuentes: a.pdf, b.pdf`** (hasta 3 nombres y "y N más" si hay más). El saludo, si toca, va antes dentro del mismo mensaje. Si el total supera **4.000 caracteres** (margen bajo el límite de 4.096) se parte por párrafos y, si hace falta, por oraciones, sin cortar una palabra. El pie de foto de una imagen se recorta a 1.024 caracteres.

**Rationale**:
- Una sola conversión, probada con casos, evita que la persona vea `**` o `###`; el modo literal responde a veces con encabezados y listas.
- **Fuentes y saludo en el mismo mensaje** ahorran mensajes de la cuota (sección 6 del documento): un mensaje por respuesta salvo que exceda el tamaño.
- Partir por párrafos conserva el sentido y mantiene el orden.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Pedir al modelo que escriba ya en formato WhatsApp | Cambiaría las instrucciones del modo literal, que comparten todos los artefactos. |
| Enviar las fuentes en un mensaje aparte | Un mensaje más por respuesta (cuota). |
| Cortar en el límite exacto | Parte palabras y listas. |

## R11. Panel: módulo Bots solo global e imágenes dentro del Inventario

**Decision**:
- **Módulo Bots** (`web/admin/src/modules/bots/`, entrada en `MODULES`): lista (nombre, número, artefacto, estado, dominios, mensajes del mes frente al tope con barra), formulario de registro y de cambio de artefacto (con la advertencia de BOT-7) y un interruptor de activo. La API exige **alcance global** para ver y escribir bots (el número y la cuota son de toda la institución, no de un programa), y el panel esconde la entrada a quien no es global (`canManageBots`, como `canEditEquivalences`).
- **Imágenes** (`modules/inventario/`): botón "Imágenes" en cada fila de documento, con un contador, que abre un diálogo (Mantine `Modal`) con la lista de imágenes del documento (miniatura, descripción editable, subir y bajar, reemplazar, quitar), el selector de archivo con las reglas de formato y de tamaño comprobadas antes de subir, y la advertencia de que la imagen será pública. El contador sale de `image_count` en `GET /inventory` (una consulta agrupada, sin N+1).
- Las miniaturas se piden por `GET /media/{public_id}` (público); el panel las lista con `GET /domains/{d}/documents/{doc}/images`.

**Rationale**:
- Es el patrón de los módulos existentes (`MODULES`, hooks de `@tanstack/react-query`, Mantine con `src/theme.ts`, ADM-3) y de las reglas del panel (`web/admin/README.md#interfaz-mantine`).
- **Bots solo global**: es lo más simple y seguro; un administrador de un programa no debe poder apuntar el número de la institución a otro artefacto. Las imágenes en cambio siguen el alcance del documento (FR-036).
- **Subir y bajar con botones** (no arrastrar y soltar): accesible, probable con Vitest y suficiente para pocas imágenes por documento.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Bots visibles para administradores de programa con su artefacto en alcance | Complica el permiso sin necesidad con un solo bot y un solo público. |
| Página aparte para imágenes | Se pidió desde el inventario del documento (historia 3). |
| Arrastrar y soltar para ordenar | Más código y más difícil de probar para pocas imágenes. |

## R12. Despliegue: carpeta `whatsapp/`, servicio `mia-whatsapp`, `servicios.py` ampliado

**Decision**: `whatsapp/Dockerfile` (imagen `python:3.12-slim`, usuario sin privilegios, `pip install .`, `uvicorn mia_whatsapp.main:create_app --factory --port ${PORT:-8000}`) y `whatsapp/railway.json` (`healthcheckPath: /health`). El servicio lo crea el usuario desde la interfaz de Railway con *Root Directory* `whatsapp`, sin ruta en *Config-as-code* ni en *Dockerfile Path* (como `web/admin`, ver [OPERACION.md](../../docs/OPERACION.md)). `scripts/servicios.py` suma el servicio `mia-whatsapp` (URL, ruta `/health`) a `SERVICIOS`, **después** de la API y antes de los sitios; `encender` y `apagar` lo incluyen. Variables nuevas: las de la API (`BOT_SERVICE_KEY`, `BOT_MONTHLY_MESSAGE_CAP`, `MAX_IMAGE_MB`) en `.env.example` y `deploy/railway/variables.example.env`; las del bot en `whatsapp/.env.example`. En Kapso se registra el webhook del número hacia `https://<dominio de mia-whatsapp>/webhooks/kapso` con el evento de mensaje recibido.

**Rationale**:
- Es el flujo de los demás servicios y el que pidió el usuario; la API migra la base al arrancar, así que **se despliega primero la API** (con las migraciones `0006` y `0007`) y después el bot.
- El orden de `SERVICIOS` ya es "la API primero, al apagar al final"; el bot depende de la API.
- **La URL del servicio** (`https://mia-whatsapp.up.railway.app`) se confirma cuando el usuario cree el servicio; la lista del script usa ese nombre.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Un `Dockerfile` en la raíz para el bot | Ya es el de la API; Railway lo usaría con *Root Directory* vacío. |
| Un despliegue automático desde GitHub | Railway no tiene instalada la aplicación de GitHub (OPERACION.md, "Desplegar cambios"). |

## R13. Pruebas: API, servicio con Kapso simulado, simulador local y número de pruebas

**Decision**:
- **API** (`tests/unit/`): `test_bots.py` (rutas de `/bots`, alcance global, auditoría, número y nombre únicos, cambio de artefacto), `test_bot_service.py` (credencial, `/bot/messages`: estados, contador atómico y mes nuevo; `/bot/query`: artefacto asignado, modo literal fijo, dominios del artefacto, rechazos, registro en Uso sin teléfono, cambio de artefacto o de dominios que rige al instante), `test_images.py` (rutas de imágenes: formato, tamaño, final del archivo, alcance, orden, reemplazo con id nuevo, `/media`), `test_query_images.py` (`images` en la respuesta: orden de fuentes, sin información, sin citas, documento sin imágenes, falla de la consulta de imágenes), `test_migrations.py` (cabeza `0007`, subida y bajada), y `test_config.py` (variables nuevas).
- **Servicio** (`whatsapp/tests/`): el receptor con `httpx.MockTransport` (sin biblioteca nueva) y Kapso y la API simulados: firma inválida, evento ignorado, lote, duplicado, no texto, pregunta larga, sin información, 429 y 403, límites por persona, cola, tope mensual, saludo una vez en 24 h, dirección de respuesta sin teléfono, partición, formato, imagen que falla.
- **Simulador local** (`whatsapp/scripts/`): `enviar_webhook.py` (firma y envía un aviso de ejemplo al bot) y `kapso_falso.py` (recibe lo que el bot envía y lo imprime), para recorrer el flujo completo en la laptop sin Kapso.
- **Número de pruebas (sandbox) de Kapso**: es la prueba real de la historia 7, con el bot registrado con su `phone_number_id`.
- **Batería del MVP** (`scripts/pruebas_mvp.py`) y las pruebas existentes: deben dar lo mismo (SC-011).

**Rationale**: `httpx.MockTransport` ya está en `httpx` (sin dependencia nueva), y probar el receptor a nivel de HTTP cubre firma, 200 inmediato y duplicados como los verá Kapso. Los pocos datos que no se pudieron verificar en la documentación (forma de la respuesta de Kapso) los cubre el sandbox.

## R14. Privacidad y exposición pública

**Decision**:
- **La API nunca recibe el teléfono de la persona** (R2): `number_id` es el número de la institución.
- **El bot no escribe teléfonos ni textos de preguntas en su registro**: solo el resultado (`respondido`, `sin_informacion`, `no_disponible`, `limite`, `descartado`...), el tiempo y un identificador de mensaje truncado.
- **Los dominios del bot son los del artefacto asignado**: el panel advierte al asignarlo que el bot responde a cualquiera (BOT-7) y que el contenido debe poder decirse a cualquiera; **el control de acceso que exige la constitución para un artefacto público es ese**: el artefacto solo ve los dominios que se le dieron y no se asignan las actas del Consejo ni dominios con datos de personas. La advertencia lista los dominios que verá.
- **Las imágenes son públicas**: se avisa al subirlas (FR-033) y los enlaces no son adivinables.
- **El saludo** informa que las preguntas pasan por WhatsApp (Meta), Kapso y el proveedor del modelo (FR-020).
- **Nada nuevo sale a servicios de terceros** salvo Kapso y Meta (por ser el canal) y OpenRouter (como hoy).

**Rationale**: cumple el apartado de datos sensibles de la constitución y la regla del 2026-10-15 (datos tratados como públicos para pruebas) sin agregar un mecanismo nuevo de autenticación (cuyo alcance es incremental, ver la constitución). El riesgo real es **humano** (asignar un dominio equivocado): por eso la advertencia nombra los dominios.

## R15. Migraciones `0006` y `0007`, aditivas

**Decision**: dos migraciones solo aditivas, con `downgrade`: `0006_bots` (tablas `bots` y `bot_message_counts`) y `0007_imagenes_de_documentos` (tabla `document_images`). Ninguna cambia tablas ni filas existentes. Los scripts y las pruebas que fijan la cabeza (`DESTINO = "0005"` y `BAJAR_A = "0004"` en `scripts/probar_migracion.py`; `"0005"` en `tests/unit/test_migrations.py`) se actualizan a `0007` y `0005`.

**Rationale**: separar las dos permite volver atrás por partes y cada una responde a una parte de la spec (bots, imágenes). Los datos de las imágenes no se pierden al bajar solo la `0006`.

**Procedimiento**: como siempre (OPERACION.md, "Desplegar cambios"): la API migra al arrancar; no desplegar `main` anterior sobre una base ya migrada; para volver atrás, `alembic downgrade 0005` antes (se pierden los bots y las imágenes: conviene anotar los bots y exportar las imágenes si se quieren conservar).

## R16. Varios bots y varios canales: un servicio de WhatsApp para todos los números, y los bots web aparte

**Decision** (2026-10-24, a raíz de que habrá mínimo dos bots de WhatsApp y dos bots incrustados en páginas web, de Postgrados de Computación y de Analítica de Negocios):
- **Un solo servicio de Railway para todos los bots de WhatsApp**: `mia-whatsapp`, carpeta `whatsapp/`, paquete `mia_whatsapp`. Cada aviso de Kapso trae el `phone_number_id` del número, y la API resuelve el bot y su artefacto (R2). Un bot nuevo de WhatsApp es una fila en el panel y apuntar el webhook de su número al mismo servicio.
- **El nombre dice el canal**, no "bot": como los bots incrustados en páginas web no pasan por este servicio, llamarlo `mia-bot` confundiría. Se decide antes de crear el servicio en Railway, cuando renombrar no cuesta nada.
- **Los bots web no necesitan un servicio**: no hay webhook firmado, ni envío por Kapso, ni cuota de mensajes, ni límite por teléfono. Un chat incrustado es un componente de interfaz que llama a una ruta pública de la API (con identificador público del bot, orígenes permitidos y límite por IP). La API ya hace la consulta, los topes y el registro. Es una feature aparte (012), que reutilizará la tabla `bots` y el artefacto asignado.
- **Cada bot, su artefacto**: Computación y Analítica usan artefactos distintos, con sus dominios y su tope diario.

**Lo que la 011 deja como está** (se revisa con la 012): las rutas `/bot/...` de la API, la credencial `BOT_SERVICE_KEY` y la tabla `bots` conservan su nombre. Son del servicio de WhatsApp, y cuando haya bots web se decide si se renombran a `/whatsapp/...` o si la tabla gana una columna `channel`. Hoy es una migración aditiva igual de simple, así que no se adelanta.

**Rationale**:
- **Costo y operación**: un servicio por bot multiplicaría el gasto en Railway (la cuenta ya ronda 4 a 4,5 USD de los 5 incluidos) y las variables y despliegues.
- **Se separaría solo por un motivo real**: otra cuenta de Kapso con otra clave, aislar fallos entre programas o una carga muy distinta.
- **El secreto de firma lo elegimos nosotros** (verificado el 2026-10-24 en la documentación de Kapso): el webhook se crea por número, con una llamada a su API que incluye el `secret_key`. Se puede usar el mismo secreto en los webhooks de todos los números, así que el servicio mantiene un solo `KAPSO_WEBHOOK_SECRET`.
- **Lo que se vuelve necesario con dos bots de WhatsApp**: textos, límites y tope mensual por bot (BOT-8) y revisar si el módulo Bots sigue siendo solo del alcance global. El plan gratuito de Kapso admite un solo número: el segundo bot exige un plan de pago, y falta saber si la cuota mensual de mensajes es por cuenta o por número.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Un servicio por bot de WhatsApp | Costo y operación multiplicados sin un motivo de aislamiento todavía. |
| Un solo servicio para WhatsApp y web | El canal web no usa nada de lo que hace el servicio y exigiría una credencial de servicio en un navegador público. |
| Llamarlo `mia-bot` y que atienda lo que venga | El nombre engaña cuando existan bots web, y renombrar después cuesta el servicio, el dominio y el webhook de Kapso. |

## R17. Alcance de esta entrega: solo el sandbox de Kapso

**Decision** (2026-10-24): la entrega se construye, se prueba y se acepta **solo con el sandbox de Kapso**, porque por ahora no es posible más (no hay cuenta de Meta ni número de producción). El camino a producción se documenta en la sección 11 de [Definicion_Requerimientos_Bot_WhatsApp.md](../../docs/Definicion_Requerimientos_Bot_WhatsApp.md) y no se implementa ni se valida.

**Qué cambia respecto del plan original**:
- **Entorno de aceptación**: la historia 7 pasa a P1 y es donde se verifican las demás. Solo escriben los teléfonos registrados como de prueba (sesión con código de 6 caracteres que vence a los 15 minutos; cuántos teléfonos admite y cuánto dura la sesión no está documentado).
- **Las imágenes son el riesgo principal**: la documentación del sandbox lista como soportados solo texto y mensajes interactivos y no habla de imágenes. La primera tarea de la validación es enviar una imagen por enlace al sandbox. Si la rechaza, el texto llega igual (R9), el fallo queda registrado y la historia 2 se verifica con `kapso_falso.py` y las pruebas automáticas hasta tener un número de producción. No se cambia el diseño de las imágenes.
- **El `phone_number_id` del sandbox** no se indica en la documentación consultada. Se obtiene del primer aviso: el servicio registra el `number_id` de un mensaje de un número sin bot (es el número de la institución, no un dato de una persona), y con él se registra el bot en el panel.
- **El webhook del sandbox** se agrega desde su configuración *Sandbox WhatsApp* (*Manage Webhooks*) con el evento de mensaje recibido; si ese formulario no pide el secreto de firma, se crea con la llamada de la API de R7 (el secreto lo elegimos).
- **El aviso necesita una dirección pública**: se despliega `mia-whatsapp` en Railway (quickstart, paso 6) o se usa un túnel hacia la laptop.

**Qué no cambia**: el servicio, la API, las imágenes, el panel y los límites se construyen completos. Los límites, el tope mensual y la advertencia de acceso público se conservan porque ya son parte del diseño, cuestan poco y evitan rehacer código al pasar a producción; con el sandbox se prueban con teléfonos de prueba o con el simulador. Registrar un número de producción es registrar un bot nuevo en el panel con su `phone_number_id`.

**Rationale**:
- No hay otra opción disponible hoy, y el sandbox usa la misma API y los mismos avisos que un número real, así que lo construido sirve tal cual.
- **Recortar los límites o el contador** ahorraría poco y exigiría reescribirlos para producción.

**Alternatives considered**:

| Alternativa | Por qué no |
|---|---|
| Esperar al registro en Meta para empezar | Construir no depende de Meta (R13); solo el lanzamiento al público lo necesita. |
| Quitar límites, tope mensual y conteo mientras sea sandbox | Es poco código y tendría que volver a escribirse; además son parte de lo que se verifica. |
| Un modo "sandbox" con comportamiento propio en el servicio | Dos comportamientos que mantener; el sandbox ya se comporta como un número real. |

## R18. Riesgos abiertos

| Riesgo | Qué se hace |
|---|---|
| La cuota gratuita (2.000 mensajes de Kapso, 1.000 gratuitos de Meta por número) da 500 a 1.000 preguntas al mes | Es decisión del usuario antes de la campaña (spec, Assumptions). El tope mensual (1.800) protege la cuota; el panel muestra el consumo. |
| `QUERY_CITED_SOURCES` apagada manda imágenes de documentos que no aportaron | Se enciende al cerrar V3 (acción de despliegue, quickstart paso 6); sin eso, no se asocian imágenes. |
| Kapso reintenta o repite un aviso firmado | Deduplicación por `message.id` (R7). |
| Una ráfaga de números distintos | Cola de 20 con descarte, memoria acotada, limitador de envíos (R8 y R9). |
| `GET /media` es público y sirve megabytes desde la base | Imágenes de hasta 2 MB, caché de una hora; si hay abuso, el camino es un almacenamiento de objetos con CDN (sección 10). |
| Costo de Railway del servicio nuevo | Servicio pequeño (cuatro dependencias, un proceso); se mide en la primera semana (V3, sección 2.7: la cuenta ya ronda 4 a 4,5 USD de los 5 incluidos). |
| La respuesta de Kapso a un envío no se pudo verificar en la documentación consultada | El cliente trata 2xx como entregado y registra los errores; se confirma con el número de pruebas. |
| El sandbox puede no admitir imágenes (solo documenta texto e interactivos) | Se prueba primero (R17); si no, las imágenes se verifican con el simulador y la prueba real queda para un número de producción. |
| El `phone_number_id` y la duración de la sesión del sandbox no están documentados | El `number_id` se lee del primer aviso (R17); si la sesión vence, se crea otra desde *Add Test Number*. |
| Nunca se llega a producción y el trabajo de límites queda sin uso real | Es poco código y queda probado con el simulador; la sección 11 del documento de requerimientos deja el camino listo. |
