# Research: Historial de chats con usuarios básicos en la Consulta web

Decisiones de diseño con su razón y las alternativas descartadas. La spec es [spec.md](spec.md); el contrato de la 014 que esta feature modifica en un punto es `specs/014-memoria-conversacion/`.

## R1. Contraseñas: `hashlib.scrypt` de la biblioteca estándar

**Decision**: la contraseña se guarda como `scrypt$<n>$<r>$<p>$<sal en base64>$<hash en base64>` con `hashlib.scrypt` (n=2^14, r=8, p=1, clave de 32 bytes, sal de 16 bytes aleatorios por contraseña). Los parámetros van dentro del texto guardado, así se pueden endurecer después sin invalidar las contraseñas existentes (se re-guardan al iniciar sesión si cambian). La comparación usa `hmac.compare_digest`. Mínimo de 10 caracteres (`PASSWORD_MIN_CHARS`). Al crear o restablecer, el panel ofrece una contraseña generada (`secrets.token_urlsafe`, 16 caracteres) y la persona administradora puede escribir una propia.

**Rationale**: scrypt es lento y consume memoria a propósito, justo lo que pide la spec, y viene en `hashlib` (medido: unos 70 ms por verificación y 16 MB), así que no suma dependencias ni cambia el `Dockerfile`. `hash_key` de las claves de artefacto usa SHA-256 y sigue siendo correcto para claves aleatorias de 256 bits; las contraseñas las elige una persona y por eso necesitan un hash lento.

**Alternatives considered**: `bcrypt` o `argon2-cffi` (dependencia nueva solo por este caso; scrypt de la biblioteca estándar da la misma propiedad); PBKDF2 (más débil frente a hardware especializado); guardar SHA-256 con sal (demasiado rápido para adivinar contraseñas).

## R2. Sesión: token opaco guardado como hash, en un encabezado propio

**Decision**: al iniciar sesión se crea fila en `consulta_sessions` con un token aleatorio (`secrets.token_urlsafe(32)`, prefijo `mias_` para reconocerlo) de la que se guarda solo su SHA-256. La vigencia es **deslizante**: `expires_at = ahora + SESSION_HOURS` (8 h) y se renueva con el uso, escribiendo como máximo una vez por minuto; además hay un tope absoluto `SESSION_MAX_DAYS` (7) desde la creación. Cerrar sesión borra la fila; desactivar a un usuario, restablecer su contraseña o cambiarla la borra junto con todas las demás sesiones del usuario (menos la actual al cambiarla). El token viaja en el encabezado **`X-Session-Token`**, que se suma a `X-Artifact-Key`; se agrega a `allow_headers` de CORS. En el navegador se guarda en `localStorage` (como la clave del artefacto), así la sesión sobrevive a recargar.

**Rationale**: la spec exige que la sesión deje de valer de inmediato en varios casos; con una fila por sesión es borrar una fila. Un encabezado propio no choca con `Authorization`, que el panel usa para el token de Microsoft (`optional_admin` intentaría validar como tal cualquier `Bearer` que llegue a una ruta de administración). Guardar solo el hash significa que una copia de la base no entrega sesiones utilizables.

**Alternatives considered**: JWT firmado sin estado (no se puede revocar antes de vencer sin una lista de revocaciones, que sería otra tabla); cookie `HttpOnly` (la Consulta es un sitio en otro origen que llama a la API: obligaría a cookies entre sitios con `SameSite=None`, CSRF y cambios de CORS con credenciales, a cambio de poco en un prototipo interno); `Authorization: Bearer` (choca con el panel).

## R3. Límite de intentos fallidos y mensajes que no filtran información

**Decision**: contadores **en memoria del proceso**, acotados (como el estado del bot): fallos recientes por usuario (normalizado) y por origen. Al llegar a `LOGIN_MAX_ATTEMPTS` (5) fallos dentro de `LOGIN_LOCK_MINUTES` (15) se bloquea esa clave del contador por ese tiempo; el bloqueo aplica **aunque la contraseña sea correcta**, responde 429 con `Retry-After` y un mensaje de espera. El origen tiene un tope mayor (`LOGIN_MAX_ATTEMPTS_PER_ORIGIN`, 20) para no bloquear a toda una red por un usuario que se equivoca. Un inicio correcto limpia el contador del usuario. El mensaje de un fallo es siempre el mismo ("Usuario o contraseña incorrectos.") para usuario inexistente, desactivado o contraseña errónea, y se hace una verificación `scrypt` contra una contraseña de relleno cuando el usuario no existe, para que el tiempo sea comparable. El bloqueo cuenta también intentos contra usuarios inexistentes (así no revela cuáles existen).

**Rationale**: memoria alcanza para una sola instancia (el despliegue de hoy) y evita una escritura por intento. Si la API se reinicia se pierden los contadores, lo que se acepta y se documenta; el atacante gana como máximo un puñado de intentos por reinicio. El 429 con `Retry-After` ya está expuesto en CORS (`expose_headers`).

**Alternatives considered**: tabla de intentos en la base (persiste a reinicios pero suma escrituras por cada fallo y necesita limpieza; innecesario con una instancia); bloquear la cuenta de forma permanente (permite a cualquiera dejar fuera a un usuario); retrasos crecientes sin bloqueo (más difícil de probar y de explicar).

## R4. Origen de la petición detrás del proxy de Railway

**Decision**: el origen es `request.client.host`, salvo que `TRUST_FORWARDED_FOR=on`, en cuyo caso se usa el **último** valor de `X-Forwarded-For` (el que agrega el proxy de confianza) y no el primero (que un cliente puede escribir). Por defecto está apagado, porque uvicorn con `127.0.0.1` como único proxy de confianza ve la IP del proxy de Railway; en producción se enciende si la medición muestra que todos llegan con el mismo origen. El límite por usuario es el que protege de verdad; el de origen es un refuerzo.

**Rationale**: leer `X-Forwarded-For` sin criterio permite falsificar el origen y esquivar el límite; usar el último valor es lo seguro cuando hay un solo proxy delante. Se deja como ajuste porque no se puede comprobar la topología de Railway desde las pruebas.

**Alternatives considered**: confiar siempre en `X-Forwarded-For` (falsificable); arrancar uvicorn con `--forwarded-allow-ips="*"` (cambia el `Dockerfile` y afecta a todas las rutas por una necesidad de una sola); sin límite por origen (deja pasar el relleno de contraseñas contra muchos usuarios desde un solo equipo).

## R5. Las conversaciones las guarda `POST /query`, y el servidor carga el historial de lo guardado

**Decision**: `QueryRequest` agrega `conversation_id` (opcional). Con una sesión válida (`X-Session-Token`) y el guardado activo (`CHAT_RETENTION_DAYS` mayor que 0):

1. **Antes** de buscar y de llamar al modelo se comprueba el espacio: si la conversación ya tiene `CHAT_MAX_TURNS` vueltas responde 409 `conversation_full`; si es una conversación nueva y el usuario ya tiene `CHAT_MAX_CONVERSATIONS`, 409 `too_many_conversations`. Así no se gasta el modelo en una vuelta que no se podría guardar. Un `conversation_id` que no es del usuario o no existe responde 404.
2. El **historial** que ve la consulta sale de las vueltas guardadas (las últimas N, con `sanitize_history` y la memoria del artefacto de la 014), y el `history` que mande el cliente se ignora. Con memoria 0 no hay historial.
3. Tras responder, se guarda la vuelta (pregunta, respuesta, fuentes, modo, `no_info`) en la conversación, que se crea si no se dio `conversation_id` (título de la primera pregunta). Si guardar falla, la respuesta se entrega igual y se marca `saved: false`.

Sin sesión (o con el guardado apagado) `POST /query` se comporta como en la 014: usa el `history` del cliente si el artefacto tiene memoria y no guarda nada.

**Rationale**: el servidor es la fuente de verdad de lo guardado, así lo que se retoma no depende de lo que el cliente quiera enviar (cierra una vía de manipular el historial y de inflar el costo) y se guarda con la misma transacción lógica que el registro de Uso. Guardar en el mismo `POST` evita un segundo viaje y que el cliente pueda guardar contenido que el servidor no produjo. Las vueltas fallidas no se guardan porque el guardado ocurre solo tras una respuesta.

**Alternatives considered**: ruta aparte `POST /conversations/{id}/turns` con el contenido que mande el cliente (permitiría guardar texto falso o no generado por MIA, y exige dos viajes); que el cliente siga enviando el `history` con sesión (duplica la fuente de verdad); separar la ruta de consulta con sesión en otra URL (duplica `run_query`).

## R6. Forma de la respuesta: igual que hoy sin sesión

**Decision**: `POST /query` devuelve el `QueryResponse` de siempre cuando no hay sesión. Con sesión devuelve una subclase `QueryResponseChat` con dos campos más, `conversation_id` y `saved`. El `response_model` de la ruta es la unión de las dos y la ruta devuelve la que corresponde; las pruebas de forma exacta de hoy siguen pasando para el caso anónimo y se agrega una para el caso con sesión. `POST /bot/query` no cambia.

**Rationale**: `BotQueryResponse` ya extiende `QueryResponse`; agregar campos al modelo base cambiaría la forma de la respuesta de todos los clientes (la 014 y la 013 las protegieron con pruebas de forma exacta). Una subclase solo para la consulta con sesión lo evita.

**Alternatives considered**: campos opcionales siempre presentes en `QueryResponse` (cambia la forma para todos); devolver el identificador en un encabezado (menos explícito y fuera del contrato JSON que el cliente ya tipa).

## R7. "Exigir inicio de sesión" por artefacto y los códigos de rechazo

**Decision**: columna `artifacts.require_login` (falsa por defecto), editable en el panel con el alcance del artefacto; cambios dejan línea `artifact.require_login` en `mia.admin`. Con ella encendida, `POST /query` sin sesión válida responde **401** con `code: "login_required"`. Una sesión presente pero inválida o vencida responde **401** con `code: "session_invalid"` (también con el ajuste apagado, para que el cliente la limpie y avise). `GET /config` con la clave del artefacto informa `artifact.require_login` y un bloque `chat` (`enabled` y `retention_days`) para que la Consulta decida qué mostrar.

La comprobación de `require_login` vive en la ruta `POST /query` (se la pasa a `run_query` como `session_missing`) y **no** alcanza a `POST /bot/query`: el bot no tiene sesión y un artefacto asignado a un bot con la opción encendida debe seguir respondiéndole (FR-031). El rechazo se registra en Uso con `outcome` `rejected_permission` y se devuelve como `AuthError` con `code`.

**Rationale**: la Consulta hoy interpreta cualquier 401 como "clave inválida" y la borra (`apiFetch`); el `code` permite distinguirlos sin un cambio de contrato para los clientes existentes, que no envían sesión. El `exception_handler` de `AuthError` ya devuelve `{detail, code}`.

**Alternatives considered**: 403 para "falta sesión" (la Consulta ya trata 403 como cambio de permisos y refresca la configuración, lo que no corresponde); un ajuste de instancia en vez de por artefacto (menos flexible: una Consulta puede exigir sesión y otra no).

## R8. Retención y limpieza sin planificador

**Decision**: la **actividad** de una conversación es su `updated_at`. `purge_expired(session)` borra las conversaciones (con sus vueltas) cuya actividad es anterior a `ahora - CHAT_RETENTION_DAYS` y las sesiones vencidas. Corre **al arrancar la API** (en el `lifespan`, después de las migraciones) y, además, de forma perezosa **como máximo una vez por hora por proceso** cuando llega una petición a las rutas de sesión o de conversaciones. `CHAT_RETENTION_DAYS=0` apaga el guardado y la limpieza borra **todas** las conversaciones guardadas en su próxima corrida (documentado como la forma de volver atrás y de desactivar por privacidad); los usuarios y sus contraseñas no se tocan. **Decisión del usuario (2026-11-04):** el borrado es deliberado y no se puede deshacer desde la aplicación; para poder recuperar conversaciones hay que mantener una retención mayor a 0 y restaurar una copia de la base dentro de ese lapso.

**Rationale**: no hay un planificador en el despliegue y agregar uno es una pieza más; con una API que arranca seguido y recibe tráfico de las mismas personas que usan el historial, la limpieza perezosa cumple la retención con margen de una hora. Borrar todo con 0 es lo coherente con "desactivar el guardado" cuando los datos pueden ser personales.

**Alternatives considered**: tarea periódica en un hilo de fondo (estado oculto, más difícil de probar); servicio cron de Railway (otro servicio que operar); no borrar con 0 (dejaría datos guardados para siempre en una instancia que decidió no guardarlos).

## R9. Título automático y datos de cada conversación

**Decision**: el título es la primera pregunta con espacios normalizados, recortada a 60 caracteres en un límite de palabra y con "..." si se cortó. Cada vuelta guarda `question` (hasta 2.000 caracteres, el máximo de la consulta), `answer` (hasta `CHAT_MAX_ANSWER_CHARS`, 20.000), `sources` (JSON con `{domain, document}` como los muestra la Consulta, sin el fragmento extraído), `mode`, `no_info` y la fecha. No se guarda la clave del artefacto, ni su identificador, ni teléfonos, ni las imágenes, ni los costos.

**Rationale**: es lo mínimo que hace falta para mostrar y retomar la conversación; menos datos guardados es menos riesgo. Sin el extracto del fragmento la vuelta guardada ocupa poco y no repite texto de documentos (los nombres bastan para saber de dónde salió).

**Alternatives considered**: guardar el extracto de cada fuente (la Consulta lo muestra desplegable; pesaría mucho y duplica documentos); guardar el artefacto de cada vuelta (cruza datos del artefacto con la conversación sin necesidad).

## R10. Usuarios: nombres, alcance y administración

**Decision**: el nombre de usuario es `^[a-z0-9._-]{3,40}$`, se normaliza a minúsculas al crear y al iniciar sesión (único sin distinguir mayúsculas). Un usuario tiene `unit_id` (programa) opcional: con programa lo gestionan el alcance global y las cuentas de ese programa; sin programa, solo el global. Una cuenta de programa solo puede crear usuarios de uno de sus programas. La lista muestra nombre, programa, estado, último acceso, **cantidad** de conversaciones y fecha de la última actividad, nunca texto. Rutas `GET/POST /consulta-users`, `PATCH /consulta-users/{id}` (activar o desactivar) y `POST /consulta-users/{id}/reset-password`; cada cambio deja una línea en `mia.admin` (`consulta_user.create`, `.update`, `.reset_password`) con el id y el nombre, nunca contraseñas. Un usuario no se borra (se desactiva); sus conversaciones se van con la retención.

**Rationale**: reutiliza `Principal`, `ensure_unit` y `ensure_global` tal como están, con el patrón de bots y artefactos. Que la administración vea solo conteos cumple FR-024.

**Alternatives considered**: borrar usuarios (arrastra el borrado de sus conversaciones por una acción de administración, que la spec no pide); usuarios siempre globales (el pedido fue "el mismo alcance que ya rige en el panel").

## R11. El registro de Uso no cambia

**Decision**: `QueryLog` no recibe ninguna columna nueva y no se enlaza con las conversaciones. La pregunta actual sigue guardándose como hoy; el texto de las respuestas y el historial no van a Uso. El identificador de la respuesta (el `id` de `QueryLog`) se devuelve igual, así la calificación de la Consulta (`POST /query/{id}/feedback`) sigue funcionando en la sesión actual; las vueltas guardadas no guardan ese identificador y por eso no se califican al reabrirlas.

**Rationale**: FR-026 dice "puede enlazarse solo si hace falta"; no hace falta, y no enlazar significa que borrar una conversación no deja un puntero colgando en Uso ni que Uso permita reconstruir conversaciones.

**Alternatives considered**: guardar `conversation_id` en `queries` (permite cruzar costos con conversaciones, pero amarra Uso al borrado y no lo pidió ninguna historia).

## R12. La Consulta: sesión, lista, retomar y compatibilidad

**Decision**: `api/session.ts` guarda el token en `localStorage` (con `try/catch`, como la clave) y expone un `useSession`. `apiFetch` agrega `X-Session-Token` si hay token, y distingue 401 por `code`: `session_invalid` limpia la sesión y muestra el inicio de sesión sin tocar la clave; `login_required` abre el inicio de sesión; un 401 sin `code` sigue siendo "clave inválida" como hoy. Con la sesión iniciada, la barra lateral lista las conversaciones (`GET /conversations`) con "Nueva conversación"; abrir una carga sus vueltas (`GET /conversations/{id}`) y las convierte en `Exchange` ya respondidos (`status` "answered" o "no_info"); preguntar envía `conversation_id`. Sin sesión todo es como hoy (incluida la conversación en la página, y el `history` de la 014). Con clave fija se muestra "Iniciar sesión" como opción y, si el artefacto la exige, la pantalla de inicio de sesión sustituye a la de la clave. El aviso de retención sale de `GET /config` (`chat.retention_days`). Una vuelta que no se pudo guardar (`saved: false`) muestra un aviso en esa vuelta. Si la sesión vence al preguntar, el texto escrito vuelve al campo (como `rejectionOf` hace con las preguntas rechazadas).

**Rationale**: reutiliza los patrones de la 014 (funciones puras con pruebas en Vitest y `renderToString`), y el cambio a `apiFetch` es el único punto compartido, acotado por el `code`.

**Alternatives considered**: guardar el token en `sessionStorage` (se perdería al cerrar la pestaña y la spec pide que sobreviva a recargar y a volver más tarde); una aplicación aparte para el historial (duplica el cliente).

## R13. Migración `0009` y su reversa

**Decision**: la revisión `0009` crea `consulta_users`, `consulta_sessions`, `conversations` y `conversation_turns` con sus índices y agrega `artifacts.require_login` (`Boolean`, no nula, `server_default=sa.false()` para que sirva igual en SQLite y Postgres). No cambia filas existentes. `downgrade` quita todo (se pierden usuarios, sesiones y conversaciones; documentado). Las claves foráneas llevan `ON DELETE CASCADE` y además el borrado se hace por código en el orden vueltas, conversación, porque SQLite no hace cumplir las claves foráneas sin `PRAGMA`. Se prueba con `tests/unit/test_migrations.py` y con `scripts/probar_migracion.py` (que pasa a esperar `0009`).

**Rationale**: igual que `0006` a `0008`: solo aditiva, reversible, y la regla de operación de "no desplegar una versión con menos migraciones que la base" se aplica igual (se documenta en OPERACION).

**Alternatives considered**: ninguna relevante (es el patrón del proyecto).

## R14. Qué se mide y cómo se valida

**Decision**: no hay modelo de lenguaje nuevo, así que no hay una medición con costo. La validación es: pruebas automáticas (una por historia, en el patrón de la 014), la batería del MVP en 19 de 19 sin sesión, la prueba de la migración con datos, y un recorrido manual en producción por quien administra ([quickstart.md](quickstart.md)). Los valores de partida de la retención, los topes y los intentos se pueden ajustar por variables sin código.

**Rationale**: la parte difícil de esta feature es la seguridad y el aislamiento, que se verifican con pruebas exactas, no con casos de calidad de respuesta.

**Alternatives considered**: ninguna.
