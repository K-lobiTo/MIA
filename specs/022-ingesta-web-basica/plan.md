# Implementation Plan: Ingesta básica de una página web

**Branch**: `dev` (feature `022-ingesta-web-basica`, sin rama propia) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/022-ingesta-web-basica/spec.md`

## Summary

Se agrega **`web`** como sexto tipo de fuente. Una persona administradora escribe la dirección de **una página**; la API la lee **en la misma petición**, comprueba que se puede leer y, solo entonces, crea un documento normal del dominio con el texto extraído. Si no se puede leer (inicio de sesión, anti-bot, página vacía sin JavaScript, error de red, `robots.txt`, etc.) responde con un **código de rechazo estable y un mensaje en español** y no crea nada. El resto del camino (fragmentado, vectorización, búsqueda, citas, duplicados por contenido, eliminación) es el existente y no cambia.

El diseño separa tres piezas, siguiendo el patrón de interfaz y factory del proyecto:

1. **`PageFetcher`** (interfaz nueva, con una implementación `HttpPageFetcher`): lee una dirección con `httpx` (dependencia que ya existe), con topes de tiempo y de bytes, **sin seguir enlaces**, validando cada salto de redirección contra la red interna (SSRF), respetando `robots.txt` y reconociendo bloqueos y pantallas de ingreso. Es el punto de extensión para una lectura con navegador en una versión futura.
2. **Extractor de HTML** (`lxml`, que ya está instalado por `python-docx`): contenido principal como texto regular, con enlaces escritos `texto (dirección)` y tablas con el formato de fila del Excel. **Sin dependencia nueva.**
3. **`WebLoader`** (un `DocumentLoader` más): lee el texto ya extraído y guardado como `uploads/<id>.web`, de modo que el pipeline de ingesta **no cambia**.

Persistencia: una **migración aditiva `0015`** agrega `documents.source_url` y `documents.source_text` (el texto extraído, para poder verlo después, porque el disco de Railway no persiste). Una ruta nueva `POST /domains/{id}/web-pages` agrega la página y `GET /domains/{id}/documents/{doc}/text` devuelve el texto. En el panel, una ventana "Agregar página web" y otra "Ver texto".

Decisiones principales (detalle y alternativas en [research.md](research.md)):

- **Extractor propio sobre `lxml`**, sin `trafilatura` (R1): cero dependencias nuevas; se mide con las páginas de prueba y se reevalúa si no alcanza SC-005.
- **Cliente `httpx` con la IP ya validada** (conexión a la IP resuelta y comprobada, con el nombre del sitio para TLS), redirecciones manuales con tope y comprobación en cada salto (R2, R3).
- **`robots.txt` según RFC 9309**, identificándose con un `User-Agent` claro y configurable (R4).
- **Detección de bloqueo e ingreso por señales** (código, cabeceras del proveedor, texto característico, formulario de contraseña) incluso con código 200 (R5).
- **Un documento por dirección**: comparación por dirección normalizada, además del hash del texto (R8).
- **Rechazos auditados** con la acción `document.add_web` y `result="rechazado"`, sin contenido y sin parámetros de la dirección (R9).

## Technical Context

**Language/Version**: Python 3.12+ (API `mia`), TypeScript con React 19 y Mantine (panel `web/admin/`)

**Primary Dependencies**: `httpx` (cliente HTTP, ya en `pyproject.toml`), `lxml` (HTML, ya instalado como dependencia de `python-docx`; se declara de forma explícita en `pyproject.toml` por ser ahora una dependencia directa), biblioteca estándar (`ipaddress`, `socket`, `urllib.robotparser`, `urllib.parse`). **Ninguna dependencia nueva de terceros** (solo se declara `lxml`, que ya estaba presente).

**Storage**: migración `0015` aditiva: `documents.source_url` (texto, nula, con índice) y `documents.source_text` (texto largo, nula, cargada solo cuando se pide). Sin tablas nuevas. `source_type` gana el valor `web`. El archivo `uploads/<id>.web` es solo el puente hacia el cargador, como `uploads/<id>.<tipo>` para los demás.

**Testing**: `pytest` en la raíz y Vitest en `web/admin/`. Las pruebas **no usan la red**: páginas HTML inventadas en `tests/fixtures/web/`, un `PageFetcher` con resolución de nombres y transporte `httpx` inyectables, y respuestas simuladas para errores de conexión (FR-020).

**Target Platform**: Railway (API y panel); instancia local de ingesta con `INGESTION_ENABLED=true`.

**Project Type**: web-service (API) + aplicación web (panel). Sin servicios nuevos.

**Performance Goals**: la **comprobación** de la página (lectura, extracción y decisión de aceptar o rechazar) termina en menos de **20 s** incluso con un sitio lento (SC-003), con un plazo total de lectura de 15 s por defecto (`WEB_FETCH_TIMEOUT_SECONDS`) que incluye `robots.txt` y redirecciones y que se revisa también mientras se lee el cuerpo. Con `INGESTION_SYNC=true` (producción) la respuesta de una página **aceptada** llega cuando termina su procesamiento, igual que al subir un archivo; el rechazo siempre responde dentro del plazo.

**Constraints**: entorno de costo cero; la lectura ocupa un hilo de la API durante su plazo (solo personas administradoras, sin concurrencia relevante); tope de 2 MB de HTML por página (memoria acotada); mensajes y documentación en español, sin guion largo; la lectura nunca alcanza la red interna ni ejecuta nada de la página.

**Scale/Scope**: un paquete nuevo `ingestion/web/` (cuatro módulos), un cargador, una ruta nueva con dos endpoints, una migración, cinco ajustes de configuración, dos ventanas del panel y la documentación.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Evaluación |
|---|---|
| I. Almacenamiento y consulta desacoplados | **Cumple.** Solo cambia la ingesta y el inventario; los artefactos siguen consultando solo por la API. |
| II. Pipeline modular e intercambiable | **Cumple.** "Web scraping" es el ejemplo literal del principio: un tipo de fuente nuevo es un `DocumentLoader` más seleccionado por nombre en `get_loader`, y la lectura de la red queda tras la interfaz `PageFetcher` con su factory, de modo que cambiarla (por ejemplo, por una lectura con navegador) no toca el resto. Fragmentado, embeddings y almacén no se modifican. |
| III. Independencia del proveedor de LLM | **No aplica** (no se usa el modelo). |
| IV. Extensibilidad de dominios | **Cumple.** Se agregan páginas a un dominio existente sin migrar datos (la migración es aditiva y nula por defecto). |
| V. Trazabilidad de respuestas | **Cumple.** El documento web se cita por su nombre legible y dominio; además conserva su dirección y fecha de lectura (primera línea del texto y campo `source_url`). |
| Datos sensibles de personas | **Cumple con cuidado.** Las páginas pueden traer nombres y contactos de coordinación. No se filtran automáticamente; el panel muestra un aviso, el texto se puede revisar y eliminar, y los permisos por dominio son los de siempre (la constitución sigue exigiendo control de acceso antes de exponer datos de personas en un artefacto público). |
| Seguridad de la lectura | **Cumple por diseño.** Es la primera funcionalidad que hace peticiones salientes a direcciones escritas por una persona: la comprobación contra la red interna en cada salto, los topes y la auditoría son requisitos (FR-004, FR-010, FR-007a), no mejoras. |
| Estilo (sin guion largo, español) | **Cumple.** |

Sin violaciones: no hace falta la tabla de complejidad. **Re-evaluación tras el diseño (Phase 1): sin cambios.** Los riesgos propios están en la sección "Riesgos".

## Project Structure

### Documentation (this feature)

```text
specs/022-ingesta-web-basica/
├── plan.md              # Este archivo
├── research.md          # Phase 0: decisiones R1 a R15
├── data-model.md        # Phase 1: columnas nuevas, resultado de la comprobación y códigos de rechazo
├── quickstart.md        # Phase 1: guía de validación (sin red y con una página real del TEC)
├── contracts/
│   └── pagina-web-api.md   # Phase 1: endpoints, códigos de rechazo, formato del texto y del panel
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks, no lo crea este comando)
```

### Source Code (repository root)

```text
src/mia/
├── ingestion/
│   ├── web/                           # NUEVO paquete
│   │   ├── __init__.py
│   │   ├── errors.py                  # WebRejection(code, message): catálogo de códigos y mensajes
│   │   ├── urls.py                    # normalizar la dirección escrita, esquemas, clave de comparación, host público
│   │   ├── fetcher.py                 # PageFetcher (interfaz), HttpPageFetcher, get_page_fetcher(); robots.txt; saltos; topes
│   │   ├── detect.py                  # bloqueo anti-bot, pantalla de ingreso y página sin contenido
│   │   └── extract.py                 # HTML a texto (lxml): contenido principal, enlaces, listas, tablas, título
│   └── loaders/
│       ├── base.py                    # get_loader: rama "web"
│       └── web_loader.py              # NUEVO: WebLoader (lee uploads/<id>.web)
├── api/routes/
│   ├── web_pages.py                   # NUEVO: POST /domains/{id}/web-pages y GET .../documents/{doc}/text
│   ├── domains.py                     # DocumentOut gana source_url y uploaded_at (solo lectura)
│   └── inventory.py                   # DocumentNode gana source_url
├── api/main.py                        # registra el router nuevo
├── storage/
│   ├── models.py                      # Document.source_url y Document.source_text (deferred)
│   └── migrations/versions/0015_fuente_web_de_documento.py   # NUEVA, aditiva
└── config.py                          # WEB_USER_AGENT, WEB_FETCH_TIMEOUT_SECONDS, WEB_MAX_PAGE_KB, WEB_MAX_REDIRECTS, WEB_MIN_TEXT_CHARS

web/admin/src/
├── api/types.ts, api/webPages.ts      # tipos y llamadas (agregar página, ver texto)
└── modules/inventario/
    ├── AgregarPaginaDialog.tsx        # NUEVO: dirección, nombre opcional, aviso de datos personales, rechazo con su razón
    ├── TextoDocumentoDialog.tsx       # NUEVO: ver el texto extraído y la dirección
    ├── InventarioPage.tsx             # botón "Agregar página web" junto a "Subir archivos", en dominio y carpeta
    ├── TreeNode.tsx                   # tipo WEB, enlace a la dirección, fecha de lectura y botón "Ver texto"
    └── inventoryUtils.ts              # aviso de datos personales de la página web y validación mínima de la dirección

tests/
├── fixtures/web/                      # NUEVO: HTML inventado (con contenido, con ruido, anti-bot, vacía, de ingreso, tabla, enlaces)
└── unit/
    ├── test_web_urls.py               # NUEVO: esquemas, red interna, clave de comparación
    ├── test_web_fetcher.py            # NUEVO: saltos, robots, topes, bloqueos, errores de red (transporte simulado)
    ├── test_web_detect.py             # NUEVO
    ├── test_web_extract.py            # NUEVO: ruido, títulos, listas, tablas, enlaces, codificación
    ├── test_web_loader.py             # NUEVO
    ├── test_web_pages_api.py          # NUEVO: alta, rechazos, duplicados, permisos, auditoría, ingesta desactivada
    └── test_web_text_api.py           # NUEVO: ver el texto
    # sin cambios de resultado: test_documents*.py, test_loaders_base.py (se amplía el rechazo de tipos si lista tipos)

docs/
├── ARQUITECTURA.md                    # sexto tipo, paquete web, migración 0015, rutas
├── OPERACION.md                       # cómo agregar una página, razones de rechazo, límites y qué no hace
├── Definicion_Requerimientos_MVP.md / _V2.md   # donde listen los tipos de fuente
└── Idea_Fuente_Web.md                 # estado: primera versión implementada (feature 022); qué sigue pendiente
```

**Structure Decision**: se sigue la estructura existente (un cargador por tipo en `ingestion/loaders/`, registrado en el factory) y se agrega un paquete propio `ingestion/web/` para lo que no es un cargador: leer la red y extraer el HTML. Se separa en módulos pequeños para poder probar cada uno sin red (dirección, lectura, detección, extracción). La ruta va en un archivo nuevo, `web_pages.py`, y no dentro de `domains.py`, para no tocar la subida de archivos (riesgo de regresión) a costa de unas veinte líneas de alta de documento repetidas (R11).

## Riesgos

- **SSRF y rebinding de DNS**: la API haría peticiones a direcciones elegidas por una persona. Se mitiga validando cada salto, conectando a la IP ya validada y rechazando redes privadas, de bucle local, enlace local, reservadas y el servicio de metadatos (R2, R3). Es el riesgo de seguridad principal; tiene pruebas propias y una verificación manual en el quickstart.
- **Detección de bloqueo incompleta**: pantallas de verificación nuevas pueden no reconocerse y llegar como "contenido". La defensa de respaldo es el mínimo de texto útil (`WEB_MIN_TEXT_CHARS`) y que la persona revise el texto después de agregar (FR-017). Se documenta como límite conocido, no como garantía (R5).
- **Calidad de la extracción propia**: un extractor sobre `lxml` con reglas generales puede dejar ruido o perder contenido en estructuras raras. Se mide con las páginas de prueba (SC-005) y con 2 o 3 páginas reales del TEC; si no alcanza, se evalúa `trafilatura` como dependencia (R1).
- **Un hilo ocupado hasta 15 s por lectura**: aceptable con pocas personas administradoras; sin cola ni límite global. Si se usa en carga masiva, habría que mover la lectura a un script (fuera de alcance).
- **Datos personales en la página**: no se pueden filtrar de forma fiable; aviso, revisión y eliminación (como CSV, feature 021).
- **Falsa seguridad del `robots.txt`**: respetarlo no sustituye revisar los términos de uso del sitio; la responsabilidad para sitios ajenos al TEC es de quien agrega la fuente (se documenta).
- **Migración `0015`**: una API anterior no arranca sobre una base que ya la aplicó. Se respeta la regla de despliegue de `CLAUDE.md` y `OPERACION.md` ("Cuidado con las migraciones"): no desplegar una versión con menos migraciones que las de la base.
