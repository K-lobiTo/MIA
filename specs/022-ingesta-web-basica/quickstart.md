# Quickstart: validar la ingesta de una página web

Guía para comprobar la feature de punta a punta. Los detalles de los endpoints están en [contracts/pagina-web-api.md](contracts/pagina-web-api.md) y los de las columnas y los códigos en [data-model.md](data-model.md). Las pruebas automáticas no usan la red; la parte con una página real es manual y de solo lectura.

## Requisitos

```bash
source .venv/bin/activate
pip install -e ".[dev]"
docker compose up -d qdrant                    # Qdrant local
cp .env.example .env                           # si no existe; INGESTION_ENABLED=true
(cd web/admin && npm install)                  # panel
```

La base de desarrollo migra al arrancar la API (`0015` se aplica sola). Para comprobarlo: `alembic current` debe mostrar `0015 (head)`.

## 1. Pruebas automáticas (sin red)

```bash
pytest tests/unit/test_web_urls.py tests/unit/test_web_fetcher.py tests/unit/test_web_detect.py \
       tests/unit/test_web_extract.py tests/unit/test_web_loader.py \
       tests/unit/test_web_pages_api.py tests/unit/test_web_text_api.py
(cd web/admin && npm test -- inventario)
pytest                                         # todo el conjunto: sin regresiones (SC-009)
ruff check src tests scripts whatsapp
```

Resultado esperado: todo pasa. Las páginas de prueba (`tests/fixtures/web/`) son inventadas; ninguna prueba abre un socket.

## 2. Escenarios de aceptación con la API local

Arrancar con ingesta sincrónica para ver el estado final en la respuesta:

```bash
INGESTION_SYNC=true uvicorn mia.api.main:app --reload     # http://localhost:8000/docs
```

Con un dominio existente (`$DOM`) y la clave de administración (`$KEY`):

| # | Qué hacer | Resultado esperado |
|---|---|---|
| 1 | `POST /domains/$DOM/web-pages` con una página pública del TEC (por ejemplo, la de un posgrado) | `201`, `source_type: "web"`, `source_url` con la dirección final, estado `done` (con `INGESTION_SYNC=true`) |
| 2 | `GET /domains/$DOM/documents/{id}/text` | el texto empieza con `Fuente: <dirección> (consultada el <día>)`, sin menús ni pie de página; los enlaces salen como `texto (https://...)` |
| 3 | Preguntar por un dato de esa página a un artefacto con acceso al dominio | la respuesta trae el dato y cita el documento con su nombre legible (SC-006) |
| 4 | Repetir el paso 1 con la misma dirección | `409 already_added` con la fecha de lectura (FR-015a); el inventario no cambia |
| 5 | Repetir con la misma dirección escrita con barra final o con `http://` | `409 already_added` (clave de comparación) |
| 6 | Agregar una dirección distinta que lleve al mismo texto | `200` con `already_existed: true` |
| 7 | Eliminar el documento y agregar otra vez | vuelve a quedar `done` y las respuestas usan el texto nuevo |

## 3. Rechazos (nada se crea)

En cada caso la respuesta es `4xx/5xx` con `code`, el inventario del dominio queda igual (`GET /inventory`) y el registro `mia.admin` (salida de la API) tiene una línea `document.add_web` con `"result": "rechazado"`, el código y la dirección **sin consulta**:

| Dirección | `code` esperado |
|---|---|
| `https://www.acm.org/` (protección anti-bot al 2026-11-15; el resultado depende del sitio ese día: puede ser `bot_blocked`, `forbidden` o `robots_disallowed`) | uno de esos tres, nunca un documento |
| una página que pida iniciar sesión (por ejemplo, un correo o un campus virtual) | `login_required` o `forbidden` |
| `https://www.tec.ac.cr/no-existe-xyz` | `not_found` |
| `https://sitio-que-no-existe.invalid/` | `unreachable` |
| un PDF público (`https://.../archivo.pdf`) | `not_html` (el mensaje sugiere subirlo como archivo) |
| `ftp://ejemplo.com/a`, `javascript:alert(1)`, `https://usuario:clave@ejemplo.com/` | `invalid_url` |
| `http://localhost:8000/`, `http://127.0.0.1/`, `http://169.254.169.254/latest/meta-data/`, `http://[::1]/`, `http://2130706433/` | `private_address` (sin ninguna lectura: SC-007) |
| una dirección corta que redirige a `http://127.0.0.1/` | `private_address` (se comprueba cada salto) |
| con `INGESTION_ENABLED=false` | `503 ingestion_disabled` y ninguna lectura |

Las pruebas automáticas cubren los mismos casos con páginas y transportes simulados; esta tabla comprueba el comportamiento con sitios reales una vez.

### Verificación manual del SSRF (obligatoria antes de dar por terminada la feature)

1. Con un servidor local de prueba (`python -m http.server 9999` en una carpeta vacía) intentar `POST` con `http://localhost:9999/`: debe responder `private_address` **y el servidor no debe registrar ninguna petición**.
2. Con un sitio público cuyo nombre se resuelve a una IP pública, comprobar que la lectura funciona con `https` (el certificado se valida contra el nombre del sitio aunque la conexión vaya a la IP ya validada, R2).

## 4. Solo se lee la página indicada

Agregar una página con enlaces a otras páginas y a un PDF y comprobar, con el registro de peticiones de la API (`HTTPX` en nivel `INFO`) o con las pruebas automáticas, que salen **solo** estas peticiones: `robots.txt` y la página (más sus redirecciones). El texto no debe contener nada del contenido de las páginas ni del PDF enlazados, y cada enlace debe verse como `texto (https://...)` (SC-004).

## 5. Panel

```bash
(cd web/admin && npm run dev)
```

1. En un dominio, "Agregar página web", pegar una dirección del TEC y confirmar: el botón muestra progreso, la ventana se cierra, el documento aparece con tipo `WEB`, su dirección como enlace y la fecha de lectura.
2. "Ver texto" abre el texto extraído; cerrar.
3. Intentar una dirección que se rechaza: la ventana **no se cierra**, muestra la razón y deja corregir y reintentar.
4. El aviso de datos personales se ve siempre que se abre la ventana (SC-007 del CSV se repite aquí como comprobación visual).
5. Eliminar el documento web desde el inventario: desaparece y deja de responder.

La revisión visual en navegador es de la persona dueña del proyecto (lo que ya se hizo con las features 020 y 021).

## 6. Medir la calidad con páginas reales del TEC (SC-005 y SC-006)

Con 2 o 3 páginas de programas del TEC (las mismas que hoy se normalizan a mano):

1. Agregarlas y revisar con "Ver texto" que no queden menús, botones ni pie de página, y que las cifras y fechas principales estén (SC-005: ruido de menos del 10 %, datos principales al 100 %).
2. Hacer 10 preguntas con palabras de una persona real (también sin nombrar el programa) y comprobar que al menos 8 se responden con el valor correcto y citan la página (SC-006). Anotar los resultados en `research.md` o en `OPERACION.md`.
3. Si el ruido supera el 10 %, **no** seguir con la extracción propia: evaluar `trafilatura` como segunda implementación (R1 de [research.md](research.md)).

Recordar los límites de esta primera versión: no ve pestañas ni acordeones que dependan de JavaScript, no repite el nombre del programa en cada sección ni aplica el título `<PROGRAMA>: <SECCIÓN>`; para eso sigue valiendo subir un texto normalizado a mano (ver `docs/OPERACION.md`).

## 7. Después de validar

- Actualizar `docs/ARQUITECTURA.md`, `docs/OPERACION.md`, los requerimientos y el estado de `docs/Idea_Fuente_Web.md` (FR-019).
- Desplegar: la migración `0015` se aplica al arrancar la API; respetar la regla de `CLAUDE.md` (no desplegar una versión con menos migraciones que las de la base) y recordar que Railway no redespliega solo: `scripts/servicios.py encender` tras el merge a `main` y el `push`.

## Resultado del recorrido (2026-11-20)

Hecho por quien implementó la feature; sin comprobar en un navegador (la revisión visual es de la persona dueña).

**Automático.** `pytest` completo: 2933 pasan y 6 se omiten (sin regresiones); `ruff check src tests scripts whatsapp` limpio; en `web/admin/`: `npx tsc --noEmit` limpio y 246 pruebas de Vitest. Ninguna prueba nueva abre un socket (`grep` de `socket.socket`, `urlopen` y `requests.` sin resultados) y `tests/fixtures/web/` solo tiene HTML inventado.

**Sección 3, SSRF (manual, con un servidor local `python -m http.server 9999`).** Con el lector real (`HttpPageFetcher`) se probaron 11 direcciones: `http://localhost:9999/`, `http://127.0.0.1:9999/`, `http://[::1]:9999/`, `http://2130706433:9999/`, `http://0x7f000001:9999/`, `http://0.0.0.0:9999/`, `http://169.254.169.254/latest/meta-data/`, `http://10.0.0.1/`, `http://192.168.0.1/`, `http://localhost.:9999/` y `http://127.1:9999/`. Todas respondieron `private_address` y **el registro del servidor local quedó vacío (0 bytes): ninguna petición llegó a él**. Desviación del guion: no se probó una dirección corta pública que redirija a `127.0.0.1`, porque requiere un servicio público de prueba; ese caso (cada salto se valida y no se pide nada a la IP interna) lo cubren `test_una_redireccion_a_la_red_interna_se_rechaza_sin_pedir_nada_a_esa_ip` y `test_un_robots_txt_que_redirige_se_sigue_y_se_valida_como_cualquier_direccion`.

**Sección 3 y 6, sitios reales (manual, solo lectura, 4 lecturas, sin esquivar nada).** Tiempos de la comprobación completa (robots.txt, página y extracción):

| Dirección | Resultado | Tiempo |
|---|---|---|
| `https://www.tec.ac.cr/` | aceptada: 131 857 bytes de HTML a 4 908 caracteres y 69 líneas de texto, enlaces con su dirección | 2,0 s |
| `https://www.tec.ac.cr/posgrados` | aceptada: 134 715 bytes a 6 192 caracteres y 74 líneas | 3,2 s |
| `https://www.acm.org/` | rechazada `bot_blocked` (el mismo comportamiento que ya se había visto el 2026-11-15) | 1,9 s |
| `https://tecdigital.tec.ac.cr/` | rechazada `robots_disallowed` (su `robots.txt` no permite leerla) | 1,1 s |

- **SC-003:** todas las comprobaciones terminaron en menos de 4 s (meta: menos de 20 s).
- **TLS con conexión a la IP validada (R2):** las dos páginas del TEC se leyeron con HTTPS real conectando a la IP ya validada, con el nombre del sitio en `Host` y en el SNI: el certificado se valida contra el nombre y no falla.
- **SC-005 (calidad, a ojo sobre 2 páginas):** sin menús, pie de página ni avisos de cookies; los títulos, los párrafos y los datos principales están; cada enlace queda como `texto (dirección)`. Ruido observado: una línea suelta con un valor de color (`rgb(216,232,243)`) en la página de posgrados, 1 de 74 líneas (menos del 2 %, dentro de la meta de menos del 10 %). Los botones "Ver más" se conservan con su dirección porque son enlaces del contenido. No se justifica pasar a `trafilatura`.
- **No se probó** con una página de un programa concreto con pestañas (el límite conocido: lo que depende de JavaScript no se ve).

**Pendiente (no medible en la máquina de desarrollo).** SC-006 (10 preguntas con el modelo real sobre páginas agregadas) necesita Qdrant y el modelo de embeddings; queda para T052 de la persona dueña.
