# Research: Datos de contacto de quienes escriben al bot de WhatsApp

Cada decisión con su razón y lo descartado. Los datos de partida salen del código actual (`whatsapp/src/mia_whatsapp/`, `src/mia/api/routes/bot_service.py`) y de la spec.

## R1. El teléfono viaja en la llamada que ya existe (`POST /bot/messages`)

**Decisión**: `POST /bot/messages` acepta un `phone` opcional y devuelve un bloque `contact` con el estado del contacto de esa persona (o `null`). Si `phone` llega, la API obtiene o crea el contacto **después** de contar el mensaje y de calcular el estado del bot. El servicio solo envía `phone` con `BOT_CONTACT=on`.

**Razón**: el servicio ya llama a esta ruta con cada mensaje recibido (paso 2 de `flow.py`), así que el estado del contacto llega sin un viaje de ida y vuelta más. Las escrituras de los pasos siguientes (invitación, datos) son pocas por persona.

**Alternativas**:
- Una ruta `GET /bot/contacts/lookup` en cada mensaje: un viaje más por mensaje de cada persona, para un dato que casi siempre es el mismo.
- Guardar el estado en la memoria del servicio: se pierde al reiniciar y repetiría invitaciones (viola FR-005 y SC-009).
- Un fallo del contacto no debe afectar el conteo: la API envuelve la parte del contacto, registra el fallo sin datos y devuelve `contact: null`; el servicio lo trata como "sin función" (FR-025).

## R2. Quién decide qué: el servicio entiende el texto, la API guarda y valida

**Decisión**: reconocer correo, nombre, negativa, borrado y reapertura es del servicio (`contacts.py`), igual que la aclaración de la 013 (la API decide la ambigüedad porque ve los vectores; aquí el texto es del servicio). La API **vuelve a validar** todo lo que recibe: forma del correo, largos, teléfono, estado permitido y transiciones.

**Razón**: la API nunca debe confiar en el servicio para la integridad de los datos guardados, y el servicio es quien ve el mensaje. Las reglas son deterministas, sin modelo (principio III y costo cero).

**Alternativa descartada**: enviar el texto crudo a la API para que ella lo interprete. Acerca texto libre de personas a la API y a sus registros, y mezcla conversación con almacenamiento.

## R3. Reclamo atómico de la invitación

**Decisión**: antes de enviar la invitación, el servicio llama a `PUT /bot/contacts` con el evento `claim_invite`. La API hace un `UPDATE ... SET status='invitada' WHERE id = ? AND status = 'pendiente'` y devuelve si **ganó** (filas afectadas = 1). Solo quien gana envía la invitación. Si el envío falla, el servicio manda `release_invite` y el contacto vuelve a `pendiente`.

**Razón**: dos mensajes simultáneos de una persona nueva (o un reintento de Kapso que escapó del filtro de duplicados tras un reinicio) verían ambos `pendiente`. Con el reclamo atómico en la base, solo uno invita, en SQLite y en Postgres. Cubre SC-004 y el borde "el envío falla".

**Alternativas**: marcar `invitada` después de enviar (permite dos invitaciones en la carrera); un candado en memoria del servicio (no sirve con reinicios ni con más de una instancia).

## R4. Reglas de texto para reconocer los datos

**Decisión** (todas por reglas, en español, `whatsapp/src/mia_whatsapp/contacts.py`):

1. **Frases de control** (se evalúan primero, en cualquier estado): *borrado* (verbo `borrar`, `borra`, `eliminar`, `elimina`, `quitar` más `mis datos`, `mi información`, `mi correo` o `mi nombre`) y *reapertura* (`dejar mis datos`, `actualizar mis datos`, `quiero dejar mi correo`). Se normaliza sin tildes, en minúsculas y con espacios simples.
2. **Con el contacto en `invitada`**, el mensaje se clasifica así, en este orden:
   - **Negativa**: el texto normalizado (sin tildes, en minúsculas, sin signos de puntuación) **coincide exactamente** con una de estas frases: `no`, `no gracias`, `omitir`, `paso`, `ahora no`, `prefiero no`, `no quiero`, `no deseo`, `saltar`, `cancelar`, admitiendo a lo sumo `gracias` o `por ahora` al final (máximo 4 palabras en total). Un texto que solo **empieza** con una de ellas ("no encuentro la matrícula", "no sé cuándo abren", "paso a paso para inscribirme") **no** es una negativa: es una pregunta y sigue el flujo normal. Una negativa consume el mensaje, así que la regla debe ser estricta.
   - **"Para qué"**: el texto normalizado tiene **hasta 60 caracteres** y contiene `para que`, `por que`, `privacidad`, `que hacen con` o `quien ve` junto con `datos`, `correo` o `numero` (`nombre` no cuenta: es demasiado común en preguntas sobre programas). Se responde la explicación fija (`BOT_TEXT_CONTACT_WHY`) y el contacto sigue en `invitada`.
   - **Con correo**: una coincidencia de la forma `usuario@dominio.tld` (largo máximo 254). El resto del texto, sin el correo y sin frases de relleno (`mi correo es`, `y`, `soy`, `me llamo`, `mi nombre es`), se evalúa como nombre.
   - **Con `@` pero sin forma de correo válida**: correo inválido (ver R6).
   - **Solo nombre**: se acepta si el mensaje trae un introductor (`soy`, `me llamo`, `mi nombre es`) o si tiene de 2 a 4 palabras, todas con mayúscula inicial (se admiten las partículas `de`, `del`, `la`, `las`, `los`, `y`, `van`, `von` en minúscula), solo letras, espacios, puntos, apóstrofes y guiones, y sin `?`, `¿` ni dígitos. Una sola palabra sin introductor ni correo **no** se toma como nombre. Además, en este caso (sin introductor ni correo) el texto **no** es un nombre si alguna de sus palabras, sin tildes y en minúsculas, está en la lista de palabras de dominio: `programa`, `programas`, `maestria`, `doctorado`, `posgrado`, `licenciatura`, `requisito`, `requisitos`, `admision`, `matricula`, `inscripcion`, `costo`, `costos`, `horario`, `horarios`, `beca`, `becas`, `curso`, `cursos`, `plan`, `fecha`, `fechas`, `informacion`. Así "Requisitos de Admisión" o "Maestría Computación" son preguntas y no nombres. Con introductor ("soy ...") o con correo en el mismo mensaje no se aplica la lista.
   - **Cualquier otra cosa** es una pregunta: se cierra la invitación como no aceptada (`declino`) y el mensaje sigue el flujo normal de consulta.
3. El nombre se recorta a 80 caracteres y se descarta si queda vacío o es una palabra de relleno (`hola`, `gracias`, `ok`, `si`, `buenas`, y similares).

**Razón**: un falso positivo guarda una pregunta como si fuera un nombre, y es el riesgo principal de reconocer texto libre. Por eso un texto en minúsculas ("requisitos de admisión") o de una sola palabra sin introductor ("Admisión") se toma como pregunta y no como nombre. La lista de palabras de dominio cubre los casos típicos ("Requisitos de Admisión", "Maestría Computación"); una frase capitalizada que no use ninguna de esas palabras podría pasar la regla y se acepta como límite conocido, porque la confirmación le dice a la persona qué se guardó y cómo corregirlo. Se prefiere perder un nombre (la persona puede reenviarlo) a guardar lo que no era. Los casos se fijan en pruebas de tabla (`test_contacts_rules.py`), con la misma disciplina que `test_casos_aclaracion.py` de la 013.

**Alternativas**: un modelo de lenguaje para extraer nombre y correo (más preciso, pero manda datos personales a un tercero, cuesta, y rompe la independencia de proveedor sin necesidad); pedir los datos en dos pasos separados, nombre y luego correo (reglas triviales, pero cada paso es otro mensaje de la cuota y otro punto de abandono).

## R5. Los mensajes que responden la invitación no llegan a la consulta

**Decisión**: si el mensaje se clasifica como datos, negativa, corrección de correo, "para qué", borrado o reapertura, el flujo de contacto lo consume: responde con su texto fijo y **no** llama a `/bot/query` ni lo guarda en el contexto de la 013. Solo lo que se clasifica como pregunta sigue el flujo normal.

**Razón**: así el nombre y el correo nunca llegan al modelo de lenguaje ni al registro de Uso (SC-005), y no se gasta modelo (FR-017). Si hay una aclaración de programa pendiente (013), la invitación **no** interviene (R8).

## R6. Correo inválido: un solo reintento

**Decisión**: una columna booleana `email_retried`. El primer correo con `@` pero sin forma válida guarda el nombre si lo hubo, responde `BOT_TEXT_CONTACT_EMAIL_RETRY` (con un ejemplo) y marca `email_retried`. Un segundo intento inválido cierra la invitación (`entrego` si ya hay nombre, `declino` si no) con `BOT_TEXT_CONTACT_DECLINED`, sin insistir y sin consultar.

**Razón**: FR-012 ("una sola vez"). Una columna evita un estado más y se guarda en la base (sobrevive al reinicio).

## R7. CSV en el servidor, con la neutralización que ya existe

**Decisión**: `GET /contacts?format=csv` devuelve el CSV con las mismas filas y filtros que la lista, con BOM UTF-8 para que Excel respete los acentos, y reutiliza la función que neutraliza celdas que empiezan con `=`, `+`, `-` o `@` (`usage/log.py` ya la tiene para el CSV de Uso; se extrae a un lugar común si hace falta). El panel lo descarga con `apiDownload`, como la descarga del registro de consultas.

**Razón**: mismo patrón que `GET /usage/queries?format=csv` (respuesta de texto, `Content-Disposition`), sin dependencia nueva. La descarga entrega todo lo filtrado (no una página), con un tope de seguridad de 50.000 filas.

## R8. Orden de pasos en el flujo y convivencia con la 013

**Decisión** (en `_process`, después del límite por persona y del bot desactivado):

1. Con `BOT_CONTACT=on` y un `contact` devuelto:
   - Si hay una aclaración de programa pendiente (`conversations.pending`), **no se aplica ninguna regla de contacto** y la respuesta se trata como respuesta a la aclaración. La invitación sigue abierta.
   - Si el mensaje es de texto, se evalúan las frases de control (borrado, reapertura) y, en estado `invitada`, las reglas de R4.
2. El resto del flujo es el de siempre. **Después** de enviar la respuesta, si el contacto está `pendiente` y el resultado fue `respondido`, `sin_informacion` o `imagen_fallida`, se reclama la invitación (R3) y se envía en un mensaje aparte. **No** se invita tras `aclaracion` (dos mensajes del bot seguidos, uno preguntando el programa y otro pidiendo datos, confunden), ni tras avisos de límite, `no_disponible`, `no_texto` o `muy_largo`.
3. Si el contacto está `invitada` y el mensaje no es un dato (una pregunta o un mensaje que no es texto), se cierra como `declino` **solo si la respuesta a ese mensaje se envió bien**, sea cual sea su resultado (respuesta, sin información, aclaración, "no es texto", "muy largo"); falla en silencio. Si el envío falló, el contacto sigue `invitada` y la persona todavía puede contestar la invitación.
4. Las frases de borrado y de reapertura funcionan en **cualquier** estado del contacto. La reapertura desde `pendiente` o `invitada` no cambia nada salvo reiniciar `email_retried` y volver a enviar la invitación.

**Límite conocido (borrado y cuota)**: los pasos de contacto corren después del tope mensual, del límite por persona y del bot desactivado, como cualquier otra respuesta. Con el tope mensual alcanzado el bot no responde nada (ni siquiera "borrar mis datos") y con el límite por persona solo avisa una vez. En esos casos la vía para borrar es el panel (o la base). Se documenta en `docs/OPERACION.md`; mover el borrado antes de esos pasos no ayudaría con el tope, porque con el tope alcanzado no se puede enviar ningún mensaje.

**Razón**: la respuesta a la pregunta no se retrasa (SC-010) y no hay dos mensajes del bot que compitan por la atención de la persona.

## R9. Cuota de mensajes

**Decisión**: la invitación es un mensaje enviado más y se suma con la misma `_count_sent`; no se pide ningún permiso nuevo. Costo por persona nueva: recibido 1 + enviado 2 (respuesta e invitación) y, si contesta los datos, recibido 1 + enviado 1. Con el tope mensual de 1.800, el costo del contacto es de unos 5 mensajes por persona que entrega datos frente a 2 sin la función.

**Aproximación aceptada**: el estado "tope alcanzado" se conoce al recibir el mensaje; entre la respuesta y la invitación podría alcanzarse. El margen entre el tope (1.800) y la cuota del plan (2.000) lo absorbe; la invitación no es crítica y `_count_sent` ya ignora los fallos de conteo.

## R10. Un solo registro por teléfono y por bot, creado por la API

**Decisión**: restricción única `(bot_id, phone)`; "obtener o crear" con la inserción protegida ante `IntegrityError` (si otro mensaje creó el registro primero, se lee). El teléfono se normaliza en la API (solo dígitos, de 7 a 15; se guarda con prefijo `+`). Sin teléfono real (el aviso trae solo un identificador de usuario) el servicio no envía `phone` y no hay contacto (FR-023).

**Razón**: la unicidad en la base es la única garantía real contra duplicados concurrentes (SC-004). El identificador de usuario de Kapso (BSUID) no sirve para contactar a nadie fuera de WhatsApp, así que no se guarda.

**Alternativa descartada**: usar el `conversation.id` de Kapso como clave cuando no hay teléfono. Daría registros sin teléfono, que no cumplen el propósito (contactar) ni lo que se pidió.

## R11. Borrado: de la persona y del panel

**Decisión**: tres operaciones distintas, todas auditadas sin datos personales:
- **La persona** (`erase` desde el servicio): borra nombre y correo, deja el registro con `declino` y `email_retried=false` (queda el teléfono como constancia de que ya se preguntó, FR-016).
- **El panel, un contacto** (`DELETE /contacts/{id}`): borra la fila; si la persona escribe de nuevo es una persona nueva (historia 6, escenario 7).
- **El panel, por filtro** (`DELETE /contacts?...&expected=N`): exige que el conteo esperado coincida con el actual (409 si cambió entre la vista y el borrado), para que la confirmación de la ventana ("se borrarán N") sea cierta.

**Razón**: la persona necesita que el bot recuerde que ya fue invitada y rechazó; la administración, en cambio, puede eliminar por completo. El conteo esperado evita borrar más de lo confirmado.

## R12. Controles, textos y privacidad de los registros

**Decisión**:
- **Ajuste**: `BOT_CONTACT` en el servicio (`off` por defecto, `on`), validado como `BOT_CLARIFY`. Las rutas de la API existen siempre (protegidas con la credencial de servicio) y el módulo del panel se ve siempre; apagar la función solo detiene las invitaciones y el guardado.
- **Textos** `BOT_TEXT_CONTACT_INVITE`, `_THANKS`, `_DECLINED`, `_EMAIL_RETRY`, `_WHY`, `_ERASED`, `_NO_DATA` (ver [contracts/servicio-contactos.md](contracts/servicio-contactos.md)). Quedan **fuera** de `contact_warnings` (que avisa de textos que parecen traer el contacto de un programa): los textos de esta feature piden un correo y llevan un ejemplo con `@` legítimamente.
- **Registros**: el log del servicio agrega solo `contacto=<evento>` (`invitada`, `entrego`, `declino`, `borrado`, ...). Nunca el teléfono, el nombre ni el correo.
- **Auditoría** de la API: `contact.export` (conteo y filtros), `contact.delete` (id del contacto) y `contact.delete_filtered` (conteo y filtros). El teléfono no se escribe, ni siquiera enmascarado, en el registro de administración; el id basta para identificar en la base. Por eso `mia.contacts.phone` solo normaliza: no hay enmascarado del teléfono (nada lo usaría).

**Razón**: cumple FR-019, FR-024, FR-027 y FR-033 con el mismo mecanismo que las demás funciones del bot.

## R13. Descartado: usar los contactos de Kapso

Kapso ofrece contactos propios (`create_whatsapp_contact`, `update_whatsapp_contact`). Se descarta: dejaría los datos en un tercero, fuera de la base y sin el control de borrado, de auditoría y de acceso que pide la spec, y ataría el registro a un proveedor intercambiable (el bot ya está pensado para migrar de número y de plan).

## R14. Verificación de la implementación (2026-11-12)

- **Pruebas:** `pytest` de la raíz (incluye `whatsapp/tests/`): 2363 pasan y 6 se omiten (las omitidas son las de siempre, que piden servicios externos); `whatsapp/tests/` solo: 577 pasan; Vitest del panel: 201 pasan en 26 archivos; `ruff check src tests scripts whatsapp` limpio; `npm run typecheck` y `npm run build` sin errores. No hay guiones largos nuevos.
- **Pruebas existentes tocadas, solo lo inevitable:** las aserciones de la revisión de migraciones (`"0011"` a `"0012"` en `test_migrations.py`, `test_equivalences.py` y `test_probar_migracion.py`), el conjunto de parámetros de `log_result` en `test_logs.py` (se sumó `contacto`), y las listas de capacidades y de módulos del panel (`capabilities.test.ts`, `visibleModules.test.ts`). Todas las demás pasan sin cambios (SC-007), incluido el recorrido de la 011 con la función apagada.
- **Un cambio de contrato respecto del diseño:** con `BOT_CONTACT=off` (o sin `phone`) la respuesta de `POST /bot/messages` **no trae el campo `contact`** (en vez de `contact: null`) para que sea idéntica a la de antes y las pruebas de la 011 no cambien. El servicio lo trata igual que nulo (`contracts/bot-contactos-api.md` actualizado).
- **Un 422 que repetía el dato:** el 422 por defecto de FastAPI incluye lo recibido (`input`), así que una petición mal formada a `PUT /bot/contacts` o `POST /bot/messages` devolvía el teléfono o el nombre. Se agregó un manejador en `api/main.py` que quita `input` y `ctx` solo en esas dos rutas (prueba en `test_contacts_privacidad.py`).
- **Ensayo de migración:** `scripts/probar_migracion.py` sobre una base SQLite vacía: todo bien, ida y vuelta incluida (la `0012` sube y baja). Falta repetirlo con una rama de Neon, que es del usuario antes de desplegar.
- **Recorrido del quickstart (secciones 2 a 4):** el recorrido de la sección 2 (pasos 1 a 9) está cubierto por pruebas automáticas con el servicio y la API reales en un solo proceso y Kapso simulado (`tests/unit/test_bot_end_to_end.py` y `whatsapp/tests/test_flow_contacts.py`); la sección 3 (privacidad) por `tests/unit/test_contacts_privacidad.py`; la sección 4 (panel) por `test_contacts_admin_api.py` y `ContactosPage.test.tsx`. **Pendiente, hecho a mano por el usuario:** abrir el CSV en una hoja de cálculo real, ver el módulo en el panel en desarrollo (`npm run dev`) con una API y un Qdrant levantados, y la prueba con el sandbox de Kapso (T039 y T041).

