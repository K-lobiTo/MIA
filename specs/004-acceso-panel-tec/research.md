# Research: Acceso al panel con cuentas del TEC y separación por unidad

Decisiones técnicas del plan. Cada una: decisión, razón y alternativas descartadas.

## 1. Qué token manda el panel a la API: el token de identidad (ID token)

**Decisión**: el panel envía el ID token de Microsoft en `Authorization: Bearer`. La API exige
`aud == ENTRA_CLIENT_ID`.

**Razón**: la solicitud a TI es de una aplicación de una sola página que solo lee quién inicia sesión
(`openid`, `profile`, `email`). Con eso el único token que MIA puede validar es el ID token: su
audiencia es el client ID y trae el correo y `amr`. Un access token con los permisos de Microsoft Graph
no se debe validar fuera de Graph.

**Descartado**: *exponer una API propia con su scope* (access token con audiencia MIA): es el patrón
más correcto, pero obliga a TI a un paso más ("Expose an API") y complica la solicitud ya redactada,
para un prototipo de cinco personas. *Sesión propia emitida por MIA tras validar el ID token*: agrega
firmar, vencer y revocar tokens propios; no se justifica. Riesgo aceptado: un ID token no está pensado
para viajar a una API, pero aquí lo emite la misma aplicación a la que va dirigido, dura una hora y
solo se envía por HTTPS a la API de MIA. Se documenta en ARQUITECTURA.

## 2. Biblioteca del panel: `@azure/msal-browser`

**Decisión**: usar `@azure/msal-browser` (v4 o la vigente al instalar) con flujo de código y PKCE,
`cacheLocation: "sessionStorage"`, `loginRedirect` y `acquireTokenSilent`.

**Razón**: implementa PKCE, la renovación en silencio con el refresh token de las aplicaciones de una
página (24 h), la caché y la validación del ID token del lado del navegador. Hacerlo a mano (unas 150
líneas) deja la renovación y los casos de error de Microsoft por nuestra cuenta, y la seguridad de un
flujo OAuth no es el lugar para ahorrar una dependencia. Cumple FR-001, FR-004 y FR-005 (renovación).

**Detalles que importan**:
- *Redirección en vez de ventana emergente*: funciona en celular y no depende de que el navegador
  permita ventanas. La dirección de redirección es el origen del sitio con barra final, igual a la
  registrada en `docs/REGISTRO_APLICACION_TEC.md`.
- *Respuesta en la query y no en el fragmento* (`responseMode: "query"`): el panel usa `HashRouter`, y
  el fragmento `#code=...` chocaría con las rutas. Se verifica en el navegador (quickstart).
- *Cerrar sesión solo en el navegador*: `logoutRedirect` con `onRedirectNavigate: () => false` borra la
  caché local sin cerrar la sesión de Microsoft del navegador (cerrarla en Microsoft no es lo que se
  pide y exigiría registrar otra dirección de salida). El siguiente inicio de sesión suele ser un clic.
- *Servidor de identidad simulado*: MSAL acepta una autoridad propia con `protocolMode: "OIDC"`,
  `knownAuthorities` y `authorityMetadata` en la configuración; con eso no consulta a Microsoft.
  `VITE_ENTRA_AUTHORITY` (opcional, solo desarrollo) apunta a ella.

**Descartado**: *implementar PKCE a mano* (arriba). *Auth.js/otro proveedor*: pensado para servidores.

## 3. Validación del token en la API: PyJWT con claves en caché

**Decisión**: `jwt.decode(..., algorithms=["RS256"], audience=client_id, issuer=..., leeway=60,
options={"require": ["exp", "iat", "aud", "iss"]})`, y después se comparan a mano `tid` y `amr`. Las
claves públicas se bajan de `https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys` con
`httpx`, se guardan en memoria 1 hora y se vuelven a bajar si llega un `kid` desconocido, con un
mínimo de 5 minutos entre bajadas (para que tokens falsos con `kid` inventado no obliguen a consultar
sin fin). Si la bajada falla y hay claves guardadas, se siguen usando; si no hay ninguna, se responde
503.

**Razón**: PyJWT ya está instalada, es de uso corriente y verifica firma, emisor, audiencia, `exp` y
`nbf`. Solo se admite RS256 (nunca `none` ni HS256, para evitar confusión de algoritmos). El emisor y
la URL de claves salen del tenant fijo del TEC (`ENTRA_TENANT_ID`, con el valor del TEC por defecto),
no del token ni de la configuración OpenID descargada: menos piezas y nada que un token pueda influir.

**Origen de claves inyectable**: una dependencia `get_key_source()` devuelve un objeto con
`get_key(kid)`; en producción es el de Microsoft, en pruebas se sustituye con
`app.dependency_overrides`. No hay variable de entorno que cambie las claves de confianza: no hay
"puerta trasera" configurable en producción.

**Descartado**: *`PyJWKClient`* (caché propia, usa `urllib`, difícil de simular sin red y sin control
de la frecuencia de bajadas). *`msal` de Python o `authlib`*: dependencias grandes para una sola
verificación. *Consultar el documento OpenID en cada arranque*: una dependencia de red más.

## 4. Segundo factor: claim `amr` con `mfa`, exigido por defecto

**Decisión**: `ENTRA_REQUIRE_MFA=true` por defecto. Con él, el token debe traer `amr` con `"mfa"`; sin
él se rechaza con 403 y código `mfa_required`. Con `false` no se comprueba.

**Razón**: Entra incluye `amr` en el ID token v2 y agrega `mfa` cuando se hizo verificación en dos
pasos. Si la política del TEC no lo emite (por ejemplo, el segundo factor se satisface por una
sesión anterior y `amr` solo trae `pwd`), la variable permite seguir sin cambiar código. Eso solo se
sabrá con el inicio de sesión real: queda como pendiente en el quickstart.

## 5. El correo: `email`, luego `preferred_username`, siempre en minúsculas

**Decisión**: se toma `email` si existe y, si no, `preferred_username`; se pasa a minúsculas y se busca
en la lista. Debe contener `@`.

**Razón**: la solicitud a TI pide el claim opcional `email` pero lo marca "recomendado": puede faltar.
`preferred_username` en cuentas del TEC es el UPN, que normalmente coincide con el correo. Se usa el
correo como clave de la lista, no el `oid`, porque el operador carga la lista antes de que la persona
haya iniciado sesión alguna vez. Riesgo aceptado: si TI cambiara el correo de una persona, hay que
actualizar la lista (documentado en OPERACION).

**Descartado**: *`oid` o `sub`* (el operador no los conoce de antemano). *Verificar dominio
`@itcr.ac.cr`*: ya lo garantiza `tid` (solo cuentas del directorio del TEC) y la lista.

## 6. Cómo viaja la identidad por la API: `Principal`

**Decisión**: `require_admin` (en `security.py`) devuelve un `Principal(email, is_global, unit_ids,
source)` y las rutas lo reciben con `Depends`. Hay tres orígenes: `entra` (Bearer válido y en la lista),
`automation` (`X-Admin-Key` correcta: global, `email=None`) y nada (401). Si llegan ambas
credenciales, gana `Authorization`. `optional_admin` devuelve `None` si no llegó ninguna, para
`GET /domains`, que con la clave de un artefacto debe seguir funcionando igual.

**Razón**: una sola puerta de entrada, y las rutas dejan de saber de dónde vino la identidad. Los
filtros por alcance son funciones puras de `access/scope.py` (reciben `Principal` y `Session`), fáciles
de probar. Cada petición consulta la tabla de administradores, así que desactivar o cambiar el alcance
rige desde la siguiente petición (FR-023, SC-004) sin cachés que invalidar.

## 7. Códigos de error: `detail` más `code`

**Decisión**: las respuestas de acceso son `{"detail": "texto en español", "code": "..."}`, con un
manejador para `AuthError` (subclase de `HTTPException`). Códigos: `unauthenticated` (401, sin
credenciales), `invalid_token` (401, firma, emisor, audiencia o tenant), `token_expired` (401),
`not_authorized` (403, correo fuera de la lista o inactivo), `mfa_required` (403),
`out_of_scope` (403, escritura en unidad ajena), `global_only` (403, saldo o crear unidades),
`login_not_configured` (503), `identity_unavailable` (503, sin claves de Microsoft).

**Razón**: el panel ya lee `detail` como texto; `code` se suma sin romper nada, y las pruebas y el panel
distinguen cada caso sin comparar frases. Los mensajes de `detail` no revelan por qué falló la firma.

## 8. Alcance por unidad: reglas puras y 404 en lecturas ajenas

**Decisión**: `scope.py` define: un dominio está en alcance si su unidad lo está (un dominio sin unidad
solo para global); un artefacto está en alcance si no es `all_domains`, tiene acceso configurado y todas
sus unidades y los dominios puntuales (por su unidad) están en alcance. Lecturas y cambios de
artefactos, consultas y documentos de otra unidad responden 404 (no revela que existen); escrituras
nuevas (crear dominio, carpeta o documento, o un artefacto con acceso ajeno) responden 403
`out_of_scope`.

**Usage**: el filtro de artefactos pasa a ser una lista exacta: `None` significa todos y la lista vacía
significa ninguno. Hoy `if artifact_ids:` trata la vacía como "todos", lo que con alcance de unidad sin
artefactos mostraría todo; se corrige en `usage/aggregate.py` con pruebas. Los ids pedidos por quien
consulta se intersectan con los del alcance. Consultas sin artefacto (`artifact_id` nulo) solo las ve el
alcance global.

**Bloque `global` de `GET /artifacts`**: expone gasto de toda la API, así que para alcance de unidad se
devuelve `null` (y los costos medios por modo se calculan solo con sus artefactos). El saldo de
OpenRouter responde 403 `global_only`.

## 9. Lista de administradores: dos tablas

**Decisión**: `admins` (`email` único en minúsculas, `is_global`, `active`, fechas) y `admin_units`
(`admin_id`, `unit_id`), siguiendo el patrón `Artifact` / `ArtifactUnit`. El alcance es global o un
conjunto no vacío de unidades; el script no permite uno vacío.

**Razón**: coincide con cómo ya se modelan los accesos de artefactos, y una unidad se identifica por
`id` (renombrarla no rompe el alcance). Desactivar es un campo, no un borrado: conserva el historial de
quién tuvo acceso. Volver a agregar un correo desactivado lo reactiva y reemplaza su alcance.

**Descartado**: *columna de texto con unidades separadas por comas* (el repositorio ya evitó ese patrón
para accesos). *Variable de entorno con la lista*: el requisito pide base de datos y cambiarla
reiniciaría la API.

## 10. Registro de escrituras: logger JSON

**Decisión**: `audit.log(principal, action, target, result="ok")` escribe una línea JSON con
`ts`, `actor` (correo o `"automatizacion"`), `action`, `target` y `result` por el logger `mia.admin`, con
su propio handler a la salida estándar (los logs de Railway). Se llama desde cada ruta de escritura y en
los rechazos `out_of_scope`. Nunca recibe tokens ni claves: solo ids y nombres.

**Razón**: FR-026 pide atribución sin tabla. La salida estándar de la API ya es lo que Railway guarda y
muestra; un handler propio evita que el nivel INFO se pierda por la configuración del logger raíz.

## 11. ADMIN_KEY como clave de automatización

**Decisión**: `X-Admin-Key` sigue aceptada y produce un `Principal` global con `source="automation"`.
Si `ADMIN_KEY` está vacía se ignora el encabezado: la petición se trata como sin credenciales (401).
Cambia lo actual (503 "no configurada") por pedido del requisito: no revelar que la clave existe.
Los scripts `cargar_carpeta.py` y `reorganizar_v2.py` no cambian (el segundo escribe directo en la
base). `CORS` deja de necesitar `X-Admin-Key` para el navegador, pero se conserva en `allow_headers`
(inofensivo) y se suma `Authorization`.

## 12. Despliegue y variables

- **API**: `ENTRA_CLIENT_ID` (vacío: el inicio de sesión responde 503 `login_not_configured`, y la clave
  de automatización sigue funcionando), `ENTRA_TENANT_ID` (valor del TEC por defecto),
  `ENTRA_REQUIRE_MFA` (`true`). No se agrega URL de claves configurable (decisión 3).
- **Panel**: `VITE_ENTRA_CLIENT_ID` (variable de compilación; si falta, la compilación no falla y el
  panel muestra "inicio de sesión no configurado"), `VITE_ENTRA_TENANT_ID` (opcional, TEC por defecto) y
  `VITE_ENTRA_AUTHORITY` (opcional, solo para el servidor simulado). Al ser variables de compilación,
  cambiarlas exige volver a desplegar el panel con `railway up`.
- **Orden de despliegue**: API con la migración (aplica `0003` al arrancar) y `ENTRA_CLIENT_ID`; cargar
  correos con `scripts/admin.py`; luego el panel con `VITE_ENTRA_CLIENT_ID`. El panel anterior (con
  clave compartida) deja de funcionar apenas la API nueva esté en línea, porque `GET /inventory` ya
  exige credenciales: conviene desplegar ambos juntos y avisar a las personas.

## 13. Qué se prueba y cómo (sin client ID)

- **API**: la fixture de pruebas genera un par RSA, firma tokens con él (`iss`, `aud`, `tid`, `amr`,
  `exp` configurables) e inyecta un origen de claves con esa clave pública. Cubre: global, unidad,
  correo fuera de la lista, desactivado, sin MFA, vencido, tenant ajeno, audiencia ajena, firma de otra
  clave, `alg: none`, `kid` desconocido, claves no disponibles y `ADMIN_KEY` activa y vacía.
- **Panel**: Vitest sobre `auth/config.ts`, `auth/errors.ts` y la lógica de qué se muestra según el
  alcance. MSAL no se prueba con Vitest (es biblioteca de terceros).
- **Navegador**: `scripts/idp_simulado.py` levanta un IdP mínimo (`/authorize`, `/token`, claves) que
  firma ID tokens con una clave local, y arranca la API con esas claves inyectadas. Prueba el flujo
  completo de MSAL (redirección, PKCE, renovación, cierre) con cuentas simuladas de cada alcance.
  **No prueba**: la configuración real del directorio del TEC, el claim `amr` real, ni la asignación de
  usuarios de TI. Eso queda pendiente hasta tener el client ID.
