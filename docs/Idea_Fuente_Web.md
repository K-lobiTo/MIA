# Idea a futuro: páginas web como fuente de información (scraping periódico)

**Estado (actualizado el 2026-11-20):** **la primera versión, mínima, está implementada** con la feature 022 ([specs/022-ingesta-web-basica/](../specs/022-ingesta-web-basica/)): una persona administradora agrega **una sola página** desde el Inventario ("Agregar página web"), el sistema la lee en el momento, la limpia y la agrega como documento; si no se puede leer (inicio de sesión, anti-bot, contenido por JavaScript, `robots.txt`, error de red) lo dice ahí mismo y no crea nada. **Sigue sin implementarse** lo demás de este documento: el rastreo de varias páginas, la lectura de archivos enlazados, el inicio de sesión, la **lectura periódica** (cada X días), las reglas por sitio, el navegador automatizado y la ACM. Este documento conserva el análisis de viabilidad que se hizo antes de decidir, para quien continúe. Las decisiones abiertas que esa primera versión tomó están en la sección "Qué resolvió la feature 022" al final. Quien lo pidió (el dueño del proyecto) **no va a implementar** el resto: lo tomará otra persona.

## Qué se pidió

Que un dominio pueda tener, además de documentos subidos, **páginas web como fuente**, leídas de forma **periódica** (cada X días) para mantener la información al día. El ejemplo que se dio fue el sitio de la ACM. En los requerimientos originales ya estaba previsto como ampliación: `WebScraperLoader (ACM)` en [Definicion_Requerimientos_MVP.md](Definicion_Requerimientos_MVP.md) y "páginas web (ACM, repositorio Orion)" en [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md) (sección de extensiones).

## Veredicto de viabilidad

**Viable técnicamente**, con tres condiciones:

1. **Elegir fuentes que lo permitan**: respetar `robots.txt` y los términos de uso, y que no tengan protección anti-bot. Las páginas del propio TEC son las más seguras.
2. **Aceptar una calidad automática "buena", no "normalizada a mano"**: la extracción automática más reglas por sitio no iguala el proceso manual descrito en [OPERACION.md](OPERACION.md) ("Preparar documentos que vienen de páginas web (normalización)").
3. **Decidir dónde corre el scraping**: se recomienda **fuera del servidor de la API** (ver opciones), por memoria y costo.

## El sitio de la ACM no sirve como primer objetivo

Comprobado el 2026-11-15 con peticiones HTTP simples desde un equipo de desarrollo (3 peticiones, con cabeceras de navegador):

- `https://www.acm.org/robots.txt` se sirve y lista algunas rutas excluidas (`/Member/`, `/calendar`, `/live-search`, entre otras) más el `sitemap.xml`.
- `https://www.acm.org/`, `/about-acm` y `/sitemap.xml` respondieron **403** con la página **"Attention Required! | Cloudflare"** (protección anti-bot con captcha).
- **No se intentó esquivar la protección**, y no se recomienda: haría falta un navegador automatizado (pesado) y chocaría con la protección del sitio y, probablemente, con sus términos de uso (no se leyeron; hay que revisarlos antes de decidir).

Antes de scrapear la ACM hay que ver si ofrece alternativas (feeds, datos abiertos) o pedir autorización. El caso con más valor y menos riesgo son las **páginas del propio TEC** (programas de posgrado), que hoy ya se normalizan a mano.

## Qué ya existe y se puede reutilizar

| Pieza | Dónde | Cómo ayuda |
|---|---|---|
| Interfaz de cargadores y factory | `src/mia/ingestion/loaders/base.py` (`DocumentLoader`, `get_loader`) | Es el punto de extensión previsto. La feature 018 (Excel) es el ejemplo más reciente de agregar un tipo de fuente: [specs/018-ingesta-excel/](../specs/018-ingesta-excel/) (spec, plan, tareas y decisiones R1 a R9). |
| Pipeline de ingesta | `src/mia/ingestion/pipeline.py` (`ingest_document`) | Texto → fragmentos → embeddings → Qdrant, con cerrojo (un documento a la vez) y estados `pending`, `processing`, `done`, `error`. No cambia. |
| Eliminación completa | `src/mia/ingestion/removal.py`, feature 012 | Para reemplazar el contenido viejo de una fuente. |
| Detección de duplicados por hash | `Document.file_hash`, ruta de carga en `src/mia/api/routes/domains.py` | Sirve para no reingestar si la página no cambió. |
| Nota de estado del documento | `Document.status_note`, `LoaderError` y `DocumentLoader.notes` (feature 018) | Para informar a la persona administradora un fallo de la fuente o una lectura parcial, sin recortar en silencio. |
| Carga por API y por script | `POST /domains/{id}/documents`, `scripts/cargar_carpeta.py` | Una fuente web puede subir su texto por la API existente. |
| Carpetas, permisos por dominio y auditoría | feature 002 y siguientes | Una fuente vive en un dominio y una carpeta como cualquier documento. |

## Qué falta

- **Programador de tareas**: no existe ninguno. Solo hay `BackgroundTasks` de FastAPI, nada periódico.
- **Modelo de fuente web**: hoy un `Document` no guarda URL de origen, intervalo, última ejecución ni último resultado. Haría falta una tabla nueva (por ejemplo, `web_sources`: URL, dominio, carpeta, intervalo en días, última ejecución, último hash, estado) y su migración. Una nueva migración exige respetar la regla de despliegue de `CLAUDE.md` y `OPERACION.md` ("Cuidado con las migraciones").
- **Operación "reemplazar"**: borrar los fragmentos viejos e ingestar los nuevos sin dejar el documento vacío ni inconsistente entre medio, y sin que una consulta lo vea a medias. Se ha de reingestar **solo si cambió el contenido** (comparar el hash del texto extraído).
- **Extracción y normalización automática** del HTML (ver "El riesgo grande").
- **Qué hacer si la página desaparece o falla**: decisión abierta (ver abajo).

## El riesgo grande: la calidad, no la técnica

[OPERACION.md](OPERACION.md) ("Preparar documentos que vienen de páginas web (normalización)") documenta lo aprendido con los posgrados del TEC: el texto crudo de una página baja la calidad de las respuestas aunque la información esté. Un scraper tendría que resolver, o aceptar que no resuelve, lo siguiente:

| Regla manual (resumida) | ¿Se puede automatizar? |
|---|---|
| Un documento por tema, no por página | Parcial: depende de la estructura de cada sitio (reglas por sitio). |
| Quitar menús, botones, pie de página y enlaces de interés | Sí, con extracción del contenido principal (por ejemplo, `trafilatura` o `readability`), con ajustes por sitio. |
| No cargar contactos del programa (el bot no los da) | Parcial: filtros por patrón (correos, teléfonos) con revisión. |
| Repetir el nombre del programa en cada encabezado y que la **primera línea sea `<PROGRAMA>: <SECCIÓN>`** (de ahí sale el nombre que ofrece el bot al aclarar, feature 013) | Solo con configuración por fuente (el nombre del programa y la sección). |
| Materializar los enlaces (`texto (https://...)`) | Sí: convertir cada ancla en su texto más su dirección. |
| Reconstruir pestañas, acordeones y tablas | No de forma genérica: reglas por sitio; las páginas que cargan el contenido con JavaScript exigen un navegador automatizado. |
| Texto plano regular, una idea por línea | Parcial (convertir tablas a viñetas, limpiar líneas sueltas). |
| Normalizar mayúsculas, siglas y fechas | Parcial. |
| Indicar la fuente y la fecha de consulta en la primera línea | Sí. |
| Verificar contra la página y probar con preguntas reales | No: sigue siendo manual (al menos la primera vez por fuente). |

Conclusión práctica: una fuente web automática sale **bien, pero no igual** que un documento normalizado a mano. Conviene medir cada fuente nueva con las mismas 3 a 5 preguntas con palabras de una persona real, también sin nombrar el programa, comprobando la fuente que cita el bot.

## Cómo hacerlo: opciones

| Opción | Qué es | Esfuerzo | Comentario |
|---|---|---|---|
| **A. Script fuera del servidor** | Un script (`scripts/`) baja la página, extrae y normaliza el texto y lo sube por la API existente, **reemplazando** el documento si cambió. Se ejecuta cada X días con una tarea programada de GitHub Actions (gratuita) o desde la laptop de quien administra. | Bajo | Va en la línea de "ingestar en la laptop" (ver [OPERACION.md](OPERACION.md) y [ESCALABILIDAD.md](ESCALABILIDAD.md)), sin servicio nuevo en Railway y sin costo. Se configura con un archivo (URL, dominio, carpeta, intervalo, reglas), no con el panel. Necesita la operación "reemplazar" en la API. |
| **B. Fuentes en el panel con ejecución programada** | Un módulo del panel para registrar URL, dominio, carpeta e intervalo en días, con estado y último resultado; una tarea programada ejecuta el scraping. | Medio a alto | Es lo que describe la petición original. Exige tabla, migración, programador, API de administración y pantalla (en el estilo del módulo Bots o Usuarios). Puede apoyarse en A como motor. |
| **C. Programador dentro de la API** | Igual que B, pero el scraping corre en el servicio de la API. | Medio | **No se recomienda**: la API usa unos 340 MB en reposo en un plan de 5 USD, y el scraping más la ingesta competirían por memoria con las consultas. |

**Camino sugerido:** A con 2 o 3 páginas del TEC, medir la calidad como se dijo arriba, y **solo entonces** decidir si B vale la pena.

## Decisiones abiertas

1. **Qué fuentes concretas**, y si de verdad se quiere la ACM (ver la sección sobre la ACM) o era solo un ejemplo de sitio con noticias o eventos.
2. **Cuántas fuentes y con qué frecuencia** (cada cuántos días, por fuente). Define si basta un archivo de configuración o hace falta el panel.
3. **Si una página desaparece o falla**: eliminar el documento, conservar el último contenido bueno (con aviso en `status_note`) o reintentar N veces. Se recomienda conservar y avisar.
4. **Cuál es el contenido que importa**: toda la página o solo una sección (por selector), y si se sigue enlaces (rastreo de varias páginas) o solo la URL dada. Rastrear varias páginas multiplica el costo, el riesgo legal y el ruido; empezar con una URL por fuente.
5. **Cómo se muestra a quien consulta**: el nombre del documento se ve como fuente citada. Hace falta un nombre legible y, quizá, la URL y la fecha de consulta en el texto (regla 9 de la normalización).
6. **Legal y de cortesía**: `robots.txt`, términos de uso, derechos de autor del contenido, identificación del cliente (un `User-Agent` claro), límite de velocidad y horario. Para sitios ajenos al TEC, pedir autorización.
7. **Contenido con datos personales**: las páginas pueden traer nombres y contactos; aplicar la regla de no cargar contactos del programa y la política de datos del proyecto.

## Qué hay que construir (resumen)

- **Para A**: el script de extracción y normalización con configuración por fuente; la operación de reemplazo de un documento en la API (o un script que combine eliminar y subir de forma segura); la tarea programada y su documentación en [OPERACION.md](OPERACION.md); pruebas con páginas guardadas como archivos de prueba (no depender de la red en las pruebas).
- **Para B, además**: tabla y migración de fuentes, rutas de administración con alcance por dominio, módulo del panel con estado y último resultado, auditoría de cada ejecución (sin contenido) y mensajes de error en `status_note`.
- **Siempre**: respetar el estilo del proyecto (español, sin guion largo), actualizar [ARQUITECTURA.md](ARQUITECTURA.md) y [OPERACION.md](OPERACION.md), y trabajar con Spec Kit en la rama `dev` (la feature 018 es el modelo más cercano de flujo y de nivel de detalle).

## Camino sugerido (si se aprueba)

1. Decidir las fuentes y la frecuencia (decisiones 1 y 2) y revisar sus términos de uso.
2. Especificar la feature (`speckit-specify`), empezando por la opción A.
3. Primera entrega con 2 o 3 páginas del TEC, un documento por sección y medición con preguntas reales.
4. Después, según resultados: el panel (opción B) y más fuentes.

## Qué resolvió la feature 022

Primera versión, deliberadamente básica (el resto de este documento sigue vigente para lo que falta):

- **Una dirección por fuente** (decisión abierta 4): se lee solo la página indicada, sin seguir enlaces ni abrir archivos enlazados; los enlaces quedan escritos como `texto (dirección)`.
- **Rechazo en el momento y sin rastro** en lugar de "conservar el último contenido bueno" (decisión abierta 3, que no aplica porque no hay lectura periódica): cada intento rechazado se informa con su razón y queda auditado, sin crear documento.
- **Legal y de cortesía** (decisión abierta 6): respeta `robots.txt` (RFC 9309), se identifica como `MIA-Lector`, no esquiva protecciones y se niega a leer redes internas. Para sitios ajenos al TEC, revisar términos de uso y derechos de autor sigue siendo de quien agrega la fuente.
- **Cómo se muestra a quien consulta** (decisión abierta 5): un nombre legible (el indicado, el título de la página o el sitio) y la primera línea `Fuente: <dirección> (consultada el <día>)`.
- **Datos personales** (decisión abierta 7): no se filtran; aviso en el panel y revisión con "Ver texto".
- **Dónde corre**: dentro de la API (una sola página es breve y acotada: plazo de 15 s y 2 MB), no la opción A (script) ni la C (programador dentro de la API) de este documento; la lectura periódica sigue sin existir.
- **Calidad**: "buena, no igual a la normalizada a mano" (extractor propio sobre `lxml`; si en las mediciones no alcanza, evaluar `trafilatura`).
- **Para actualizar una página**: eliminar el documento y volver a agregarla (un solo documento web por dirección en cada dominio).
