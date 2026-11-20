# Research: Ingesta básica de una página web

Decisiones de la fase 0. Todas las incógnitas del contexto técnico quedan resueltas aquí; no hay `NEEDS CLARIFICATION`. Lo que se comprobó en el código (el 2026-11-20) está marcado como **Verificado**.

## R1. Cómo extraer el texto del HTML

**Decisión**: un extractor propio sobre **`lxml`** (módulo `ingestion/web/extract.py`), sin `trafilatura` ni `readability`.

- **Verificado**: `lxml` 6.1.3 ya está instalado (lo trae `python-docx`); `beautifulsoup4`, `trafilatura` y `readability` no.
- Reglas generales: se descartan `script`, `style`, `noscript`, `template`, `iframe`, `svg`, `form`, `nav`, `header`, `footer`, `aside`, `button` y los elementos cuyo `id` o `class` indican menú, navegación, cookies, anuncios, redes sociales, migas de pan o pie de página (lista corta de palabras clave). El contenido se toma de `main`, `article` o `[role=main]` si existen y, si no, de `body`.
- Estructura: títulos (`h1` a `h6`) en su propia línea; párrafos; `ul`/`ol` con una viñeta con guion por elemento (la sangría de las anidadas se conserva con dos espacios); tablas con el **mismo formato de fila que el Excel**, reutilizando `lineas_de_tabla` de `ingestion/loaders/tabular.py` (`Encabezado: valor | Encabezado: valor`); `br` como salto de línea; espacios y líneas vacías normalizados; líneas duplicadas consecutivas colapsadas.
- Enlaces: cada `a[href]` con destino `http` o `https` (resuelto contra la dirección final de la página) se escribe `texto (https://...)`. Se omiten los destinos `#ancla`, `javascript:`, `mailto:` y `tel:` y queda solo el texto. Si el texto del enlace ya es la dirección, no se repite.
- Título del documento: `og:title`, si no `<title>`, si no el primer `h1`; se recorta el sufijo repetido del sitio ("| TEC") solo si coincide con el nombre del sitio y deja un título no vacío.

**Alternativas**: `trafilatura` extrae mejor el contenido principal de páginas arbitrarias, pero agrega varias dependencias (entre ellas bibliotecas de fechas y de análisis de direcciones) a una API que usa unos 340 MB en reposo, y su manejo de enlaces y de tablas no coincide con el formato del proyecto. `beautifulsoup4` es más cómodo pero también es una dependencia nueva para algo que `lxml` ya hace. **Criterio de reevaluación**: si en las páginas de prueba y en 2 o 3 páginas reales del TEC el ruido supera el 10 % (SC-005), se evalúa `trafilatura` como segunda implementación del extractor sin tocar el resto.

## R2. Cliente HTTP, y cómo evitar el rebinding de DNS

**Decisión**: `httpx` síncrono (la ruta es `def`, corre en el hilo de FastAPI), con **redirecciones manuales** (`follow_redirects=False`) y conexión a la **IP ya validada**.

- **Verificado**: `httpx` 0.28.1 ya es dependencia; `httpcore` 1.0.9 acepta la extensión de petición `sni_hostname` y la usa como `server_hostname` del TLS (se valida el certificado contra el nombre del sitio, no contra la IP).
- Para cada salto: se resuelve el nombre con `socket.getaddrinfo`, se comprueba **cada** IP devuelta (R3), se elige la primera válida y se pide `https://<IP>/ruta` con la cabecera `Host` y `extensions={"sni_hostname": <nombre>}`. Así una segunda resolución del nombre no puede apuntar a otra IP entre la comprobación y la conexión.
- Cabeceras: `User-Agent` claro (R4), `Accept: text/html,application/xhtml+xml;q=0.9,*/*;q=0.1`, `Accept-Language: es`, sin cookies persistentes (cliente nuevo por intento).
- Plazos: conexión 5 s, lectura 10 s y un **plazo total** de `WEB_FETCH_TIMEOUT_SECONDS` (15) para todo el intento, incluidos `robots.txt` y redirecciones (se comprueba el reloj entre pasos y se pasa el tiempo restante a cada petición).
- Cuerpo: se lee en bloques (`stream`, `iter_bytes()`) contando los bytes **ya descomprimidos** y se corta al pasar `WEB_MAX_PAGE_KB` (2048 KB) con el rechazo `too_large`, así una respuesta comprimida pequeña no puede expandirse más allá del tope. El reloj del plazo total se revisa **entre bloque y bloque**, porque los plazos de `httpx` son por operación y una respuesta que llega gota a gota podría pasar del plazo dentro de una sola lectura.
- `HTTP` plano: se permite (el spec acepta `http` y `https`), con la misma validación y conexión a la IP.

**Alternativas**: resolver una vez y volver a pedir por nombre (deja la ventana de rebinding abierta); un transporte `httpx` personalizado que fije la IP (más código, mismo efecto); `requests` o `urllib` (dependencia nueva o menos control de plazos y de TLS).

**Riesgo anotado**: conectar a la IP cambia la forma de las URLs y de los errores de TLS; se cubre con una prueba de transporte simulado y una verificación manual con una página real (quickstart).

## R3. Qué direcciones se rechazan (SSRF)

**Decisión**: solo `http` y `https`, sin credenciales en la dirección, y solo IPs **públicas**.

- Esquemas distintos de `http` y `https` (`ftp`, `file`, `javascript`, `data`, `mailto`, etc.): `invalid_url` antes de cualquier lectura. Direcciones con `usuario:clave@`: `invalid_url` (no se aceptan credenciales).
- Sin esquema (`tec.ac.cr/posgrado`): se antepone `https://` solo si lo escrito parece un nombre de sitio (un punto y sin espacios); si no, `invalid_url`.
- Una IP se rechaza (`private_address`) si `ipaddress` la marca como privada, de bucle local, enlace local, reservada, multicast o no especificada, o si es `169.254.169.254` (metadatos de la nube; ya cae en enlace local, se prueba aparte), e incluye IPv6 y direcciones IPv4 mapeadas a IPv6. Las formas "raras" de IPv4 (decimal, octal, hexadecimal) se normalizan con `socket.getaddrinfo`, que ya las interpreta, antes de comprobarlas.
- Nombres como `localhost` o terminados en `.local` o `.internal` se rechazan por su resolución, no por una lista.
- Se aplica **en cada salto** de redirección y a la dirección de `robots.txt`. Un nombre que no resuelve es `unreachable` (no `private_address`).
- Puertos: se aceptan los de la dirección (el sitio puede usar 8443); se rechaza el puerto 0.

**Alternativas**: lista de dominios permitidos (descartada: el spec no limita a sitios del TEC y las páginas del TEC no son las únicas útiles); solo comprobar el nombre sin resolverlo (insuficiente).

## R4. `robots.txt` y la identificación del cliente

**Decisión**: respetar `robots.txt` según **RFC 9309** con `urllib.robotparser`, y un `User-Agent` fijo y configurable (`WEB_USER_AGENT`).

- `User-Agent` por defecto: `MIA-Lector/1.0 (lectura de una pagina indicada por una persona administradora; Instituto Tecnologico de Costa Rica)`. No lleva correos ni datos personales. El token para comparar con `robots.txt` es `MIA-Lector`.
- Antes de pedir una página se pide `<origen>/robots.txt` con los mismos topes (cuerpo máximo 256 KB, plazo dentro del total). Resultado: 2xx se analiza; **4xx (incluido 404 y 403) se considera "sin restricciones"**; 5xx, tiempo agotado o error de red se considera **inalcanzable y se trata como prohibido** (`robots_unreachable` en el detalle interno, mostrado como `robots_disallowed`); redirecciones del propio `robots.txt` hasta 3 saltos validados como cualquier otra.
- Si el sitio cambia de origen por una redirección, se comprueba el `robots.txt` del nuevo origen antes de pedir ese salto.
- La comprobación usa la ruta y la consulta de la dirección. Una página prohibida se rechaza con `robots_disallowed` sin pedirla.
- El rechazo anti-bot de un `robots.txt` que responde 403 con captcha cuenta como 4xx (sin restricciones); la página misma luego se rechazará como `bot_blocked`. Es el comportamiento del RFC y es aceptable.

**Alternativas**: ignorar `robots.txt` (descartado por `Idea_Fuente_Web.md` y por cortesía); tratar 5xx como permitido (el RFC lo desaconseja).

## R5. Cómo se reconoce un bloqueo, un ingreso o una página sin contenido

**Decisión**: módulo `detect.py` con reglas por señales, en este orden, sobre la respuesta final y su cuerpo ya leído. Cada regla produce un código de rechazo (catálogo en [data-model.md](data-model.md)).

| Señal | Código |
|---|---|
| Estado 401, o 403 con `WWW-Authenticate`; o redirección a una ruta o sitio de ingreso conocido (segmentos `login`, `signin`, `sign-in`, `sso`, `auth`, `oauth`, `accounts`, `adfs`, `cas`; sitios `login.microsoftonline.com`, `accounts.google.com`) | `login_required` |
| Estado 403, 429 o 503 con cabecera `cf-mitigated: challenge`, o cuerpo con marcas de verificación (`Attention Required! \| Cloudflare`, `Just a moment...`, `cf-chl`, `challenge-platform`, `captcha`, `g-recaptcha`, `hcaptcha`, `Access denied`, `Request unsuccessful. Incapsula`, `Pardon Our Interruption`, `DDoS protection by`) | `bot_blocked` |
| Estado 200 pero el cuerpo tiene esas marcas y menos de `WEB_MIN_TEXT_CHARS` de texto útil (la pantalla de verificación con código de éxito, FR-008) | `bot_blocked` |
| Estado 200 con un `input type=password` y poco texto útil (un formulario de ingreso sin redirección) | `login_required` |
| Estado 403 sin ninguna de las señales anteriores | `forbidden` ("no permite el acceso: puede requerir iniciar sesión o bloquear la lectura automática") |
| Estado 429 | `rate_limited` |
| 404, 410 | `not_found` |
| Otros 4xx y 5xx | `server_error` (con el código en el mensaje) |
| Tipo de contenido que no es `text/html` ni `application/xhtml+xml`: `application/pdf` u otro binario | `not_html` (si es PDF, el mensaje dice que se sube como archivo) |
| Tras extraer, texto útil menor que `WEB_MIN_TEXT_CHARS` (por defecto 300) sin marcas de bloqueo | `no_content` (contenido que se arma con JavaScript o página vacía) |

- "Texto útil" es el largo del texto extraído sin la primera línea de origen ni el título.
- Las marcas son una lista corta en el código, cada una con una prueba con una página de prueba inventada. **Límite conocido**: una pantalla de bloqueo nueva puede no reconocerse; el respaldo es el mínimo de texto útil y la revisión posterior del texto. No se intenta esquivar nada (FR-009).
- Una redirección a un sitio distinto, no de ingreso, se acepta (la dirección final se guarda).

**Alternativas**: detectar con un modelo de lenguaje (costo y no determinismo; descartado); no distinguir causas (peor experiencia: el spec pide razones distintas, SC-002).

## R6. Forma del texto guardado

**Decisión**:

```text
Fuente: https://www.tec.ac.cr/ejemplo (consultada el 20 de noviembre de 2026)
<Título del documento>

<contenido extraído>
```

- Primera línea: dirección final y día de lectura en la zona horaria `CAP_TIMEZONE` (America/Costa_Rica), con el mes en español (FR-013, regla 9 de la normalización de `OPERACION.md`).
- Segunda línea: el nombre del documento (el nombre propio o el título). Da contexto a la búsqueda por similitud sin pretender la forma `<PROGRAMA>: <SECCIÓN>` (que queda fuera, ver las suposiciones del spec).
- Una línea en blanco y el contenido. Sin recorte silencioso: si el texto supera el tope de documento, se rechaza (R10).
- El texto se normaliza a Unicode NFC, sin caracteres de control ni espacios no separables.

## R7. Dónde se guarda el texto y qué columnas se agregan

**Decisión**: migración **`0015`** aditiva: `documents.source_url` (`String`, nula, con índice) y `documents.source_text` (`Text`, nula, **`deferred`**: no se lee al listar el inventario). La fecha de lectura es `uploaded_at` (se crea en el mismo instante). El archivo `uploads/<id>.web` se escribe igual que el de otros tipos para que el pipeline lo lea sin cambios.

- **Por qué en la base**: el disco de Railway no persiste, y FR-017 exige ver el texto después. Reconstruirlo desde los fragmentos de Qdrant sería impreciso (se solapan 200 caracteres) y dependería del almacén vectorial.
- **Por qué dos copias** (archivo y columna): el pipeline lee un archivo por contrato (`DocumentLoader.load(path)`); cambiarlo para leer de la base tocaría la ingesta de todos los tipos. La columna es la copia durable; el archivo es transitorio.
- **Tamaño**: acotado por `WEB_MAX_PAGE_KB` (2 MB de HTML); el texto extraído suele ser una fracción. Postgres (Neon) lo admite sin problema; SQLite también.
- `source_url` guarda la dirección **final** tal como se leyó (con su consulta), para mostrarla y compararla (R8).
- **Reversible**: `downgrade` quita las dos columnas (se pierde el texto guardado de los documentos web; los fragmentos siguen en Qdrant). Una API anterior a `0015` no arranca sobre una base que ya la aplicó: antes de volver atrás hay que correr `alembic downgrade 0014`.

**Alternativas**: una tabla `web_sources` (es la opción B de `Idea_Fuente_Web.md`, pensada para intervalos y ejecuciones programadas; sobra para una sola lectura); codificar la dirección dentro del nombre del archivo (frágil y no consultable); no guardar el texto (incumple FR-017).

## R8. Un documento por dirección

**Decisión**: la comparación se hace en Python sobre los documentos web del dominio (`source_url` no nula), con una **clave de comparación** de la dirección: esquema ignorado (`http` y `https` equivalen), servidor en minúscula sin el puerto por defecto, sin fragmento, ruta sin la barra final (salvo la raíz) y consulta conservada tal cual. Se comprueba **dos veces**: con la dirección escrita antes de leer (evita una lectura inútil) y con la dirección final tras las redirecciones (FR-015a).

- `www.` **no** se ignora en la clave (un sitio puede servir contenido distinto); el caso de `www` y sin `www` con el mismo texto lo cubre el duplicado por hash del texto (ya existente, `already_existed`).
- Pocos documentos web por dominio: el recorrido en Python es trivial y evita una columna de clave. El índice de `source_url` sirve para el filtro por dominio.
- El rechazo por dirección repetida es un `409` con `code="already_added"` e incluye el nombre y la fecha de lectura del documento existente; el duplicado por contenido responde `200` con `already_existed: true`, igual que un archivo repetido.

## R9. Auditoría de los rechazos

**Decisión**: reutilizar `audit.log_write(principal, "document.add_web", target, detail, result)` (**Verificado**: ya existe el campo `result` con `"ok"` o `"rechazado"`, y `ensure_domain` lo usa así). Aceptado: `target` es el id del documento y `detail` `"<nombre> en <dominio>"`. Rechazado: `target` es el id del dominio, `detail` es `"<código> <dirección sin consulta ni fragmento>"` y `result="rechazado"`.

- La dirección se registra **sin la consulta ni el fragmento** (pueden llevar tokens de sesión o datos personales) y las direcciones con credenciales no llegan a registrarse (se rechazan antes y se registra solo `invalid_url`). Una dirección que no se puede interpretar se registra con el texto fijo `(dirección no interpretable)`, nunca con lo escrito.
- Se audita cada rechazo, incluso antes de leer nada (FR-007a). El alcance fuera de rango ya lo audita `ensure_domain`.
- Nunca se registra contenido de la página.

## R10. Topes y ajustes nuevos

**Decisión**: cinco ajustes en `config.py`, todos con valores por defecto sensatos y sin cambios en `.env.example` obligatorios (se documentan):

| Ajuste | Valor | Para qué |
|---|---|---|
| `WEB_USER_AGENT` | ver R4 | identificación del cliente |
| `WEB_FETCH_TIMEOUT_SECONDS` | 15 (1 a 60) | plazo total del intento |
| `WEB_MAX_PAGE_KB` | 2048 (64 a 10240) | tope de bytes del HTML |
| `WEB_MAX_REDIRECTS` | 5 (0 a 10) | saltos de redirección |
| `WEB_MIN_TEXT_CHARS` | 300 (50 a 5000) | mínimo de texto útil |

- Tope de documento (FR-014): el texto extraído, en bytes UTF-8, se compara con `MAX_UPLOAD_MB` y se rechaza con el **mismo mensaje** (413). Con el tope de 2 MB de HTML casi nunca se alcanza, pero se prueba.
- No se agrega un límite global de lecturas por minuto (personas administradoras, bajo volumen).

## R11. Diseño de la ruta y reutilización de la subida

**Decisión**: archivo nuevo `api/routes/web_pages.py` con `POST /domains/{domain_id}/web-pages` (JSON `{url, name?, folder_id?}`) y `GET /domains/{domain_id}/documents/{document_id}/text`. Reutiliza `DocumentOut`, `ensure_domain`, `require_admin`, `ingest_document` y las comprobaciones de carpeta de `upload_document`, copiando solo las ~20 líneas que crean el `Document` y lanzan la ingesta (sincrónica o en segundo plano según `INGESTION_SYNC`).

- **Por qué no refactorizar `upload_document`**: es el camino de todas las subidas y tiene muchas pruebas; una función compartida es más limpia pero arriesga regresiones (FR-018). Se anota como deuda menor: si una tercera ruta de alta aparece, extraer entonces.
- Orden de las comprobaciones (cada una termina en rechazo auditado y sin efectos): ingesta activa (503) → dominio y alcance (404/403) → dirección válida y pública (400) → carpeta (404/422) → dirección repetida antes de leer (409) → lectura (422) → dirección final repetida (409) → extracción, mínimo y tope (422/413) → hash repetido (200 `already_existed`) → alta.
- La ruta es `def` (FastAPI la corre en el hilo del servidor); el plazo total acota el tiempo.
- Respuestas de rechazo: `{"detail": "<mensaje en español>", "code": "<código>"}` con el estado de [contracts/pagina-web-api.md](contracts/pagina-web-api.md). El panel muestra `detail`; las pruebas y scripts usan `code`.
- Seleccionable por factory: `get_page_fetcher(name)` con la única opción `http` por ahora (la variable `WEB_FETCHER=http` se agrega solo si hace falta; por defecto no se expone como ajuste), siguiendo el patrón de interfaz y factory.

## R12. Nombre del documento

**Decisión**: nombre propio opcional (se corta a 200 caracteres sin error si pasa de ahí, sin saltos de línea, espacios recortados). Si queda vacío: título de la página (R1); si no tiene: el servidor (`www.tec.ac.cr`). Se guarda en `filename` y es lo que citan las respuestas. No se puede editar después (spec). Los caracteres de control se eliminan. Sin extensión: el nombre no termina en `.web`.

## R13. Panel

**Decisión**: componentes de Mantine con el tema de `src/theme.ts`, siguiendo `web/admin/README.md#interfaz-mantine` (**leerlo antes de la implementación**, indica CLAUDE.md).

- Botón **"Agregar página web"** junto a "Subir archivos", en dominios y en carpetas (el destino lo da el nodo, igual que `UploadTarget`).
- `AgregarPaginaDialog`: dirección (obligatoria), nombre (opcional), aviso de datos personales visible y no bloqueante (como `CsvNotice` de la feature 021), botón que queda en estado de carga durante la lectura (hasta ~15 s) y **el rechazo con su razón en la misma ventana**, sin cerrarla, para corregir y reintentar. Al aceptar se cierra y se refresca el inventario.
- `TreeNode`: el tipo se muestra como `WEB` (ya sale de `source_type.toUpperCase()`), con la dirección como enlace (`rel="noopener noreferrer"`, abre en pestaña nueva), la fecha de lectura (`uploaded_at`) y el botón **"Ver texto"** que abre `TextoDocumentoDialog` (lectura de `GET .../text`).
- Validación en el cliente solo de lo obvio (vacío); la validación real es la de la API.

## R14. Pruebas sin red

**Decisión**: `tests/fixtures/web/*.html` con páginas **inventadas** (nada copiado de sitios reales): con contenido, con menú y pie, con tabla y listas anidadas, con enlaces y un PDF enlazado, de verificación anti-bot (con y sin código 200), de ingreso, vacía por JavaScript, en `windows-1252`. `HttpPageFetcher` recibe en su constructor la función de resolución de nombres y el transporte de `httpx` (con `httpx.MockTransport`), así que los saltos, `robots.txt`, los topes y los errores se simulan sin sockets. La prueba de la ruta sustituye el `PageFetcher` por uno falso (inyección en la ruta). Se agrega una prueba de que **ninguna petición** sale cuando la dirección es privada, usando un transporte que falla si se invoca.

## R15. Documentación y estado de la idea

**Decisión**: actualizar `ARQUITECTURA.md` (sexto tipo, paquete `web`, migración `0015`, rutas), `OPERACION.md` (cómo agregar una página, tabla de razones de rechazo con la acción sugerida, límites, qué no hace, cómo actualizar una página, aviso de `robots.txt` y términos de uso para sitios ajenos, y la sección "Cuidado con las migraciones"), los requerimientos donde listen tipos de fuente y `Idea_Fuente_Web.md` (estado: primera versión implementada con la feature 022; siguen pendientes el rastreo, los archivos enlazados, el inicio de sesión, la lectura periódica y las reglas por sitio). Se agregan los cinco ajustes `WEB_*` a la tabla de variables de `OPERACION.md`.
