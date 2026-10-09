# Operación de MIA

Guía práctica para desplegar, cargar documentos y mantener funcionando el prototipo. Pensada para quien retome el proyecto sin haber participado en su desarrollo. Cómo está construido el sistema: [ARQUITECTURA.md](ARQUITECTURA.md). Qué cambiar para producción: [ESCALABILIDAD.md](ESCALABILIDAD.md).

## Resumen del despliegue actual (desde 2026-10-07)

| Pieza | Servicio | Plan | Límite relevante |
|---|---|---|---|
| API (consultas e ingesta) | [Railway](https://railway.com), servicio `MIA`, `https://mia-main.up.railway.app` (`railway.json`) | Hobby (5 USD/mes) | Límite duro de gasto configurado en Railway (10 USD); disco no persistente. Hasta el 2026-10-07 la API estaba en Render free (`render.yaml`), hoy suspendido |
| Metadata (dominios, documentos) | [Neon](https://neon.tech) Postgres | Free | 0.5 GB; la base se suspende sin uso y despierta sola al conectarse |
| Vectores | [Qdrant Cloud](https://cloud.qdrant.io) | Free | 1 GB; el clúster se suspende tras 1 semana sin uso (se reactiva desde el panel) |
| LLM | [OpenRouter](https://openrouter.ai): modo literal con `z-ai/glm-5.3-flash` (razonamiento bajo) y modo con razonamiento con `z-ai/glm-5.3` (esfuerzo medio) | Saldo prepagado | Al agotarse el saldo, las consultas fallan (502). La cuenta exige proveedores de retención cero y que no entrenen con los datos |
| Embeddings | Modelo local e5-small (ONNX), dentro de la imagen | Sin costo | Ninguno externo |
| Sitios web (Consulta administrativa y panel) | Tres servicios más de Railway que sirven archivos estáticos: `mia-computacion`, `mia-administracion` y `mia-panel` (`https://<nombre>.up.railway.app`) | Mismo plan Hobby | Cada uno gasta solo mientras está encendido; se apagan con *Remove*. Sin auto-deploy: se despliegan con `railway up` (ver "Desplegar cambios") |
| Ingesta de documentos | La propia API en Railway, o una API local contra producción (cargas masivas con `scripts/cargar_carpeta.py`) | Sin costo adicional | Los archivos originales no quedan guardados en el servidor |

## Variables de entorno

| Variable | Desarrollo (`.env`) | Producción (Railway) | Ingesta local a producción |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///./mia.db` | URL de Neon (secreto) | URL de Neon |
| `QDRANT_URL` / `QDRANT_API_KEY` | `http://localhost:6333` / vacío | Qdrant Cloud (secretos) | Qdrant Cloud |
| `QDRANT_COLLECTION` | `mia_chunks` | `mia_chunks` | `mia_chunks` |
| `EMBEDDING_PROVIDER` | `local` | `local` | `local` (debe coincidir con producción) |
| `LLM_PROVIDER` / `GEMINI_API_KEY` | `gemini` / clave | `openrouter` / no se usa | no se usa al ingerir |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `OPENROUTER_REASONING_EFFORT` / `OPENROUTER_ZDR` | solo si `LLM_PROVIDER=openrouter` | no se usa | no se usa al ingerir (en Railway: clave, id del modelo, `low`, `false`) |
| `GLM_API_KEY` / `GLM_THINKING` | solo si `LLM_PROVIDER=glm` | no se usa | no se usa al ingerir (en Cloud Run: clave de Z.ai / `true`) |
| `INGESTION_ENABLED` | `true` | `true` | `true` |
| `INGESTION_SYNC` | `false` | `false` | `false` (en Cloud Run: `true`) |
| `QUERY_SIMILARITY_THRESHOLD` | ver `.env.example` | igual | no se usa al ingerir |
| `ADMIN_KEY` | una clave cualquiera | **obligatoria** (larga y aleatoria, secreto) | la misma de producción, para subir documentos |
| `DAILY_CAP_USD` / `CAP_TIMEZONE` | `3` / `America/Costa_Rica` | tope diario de toda la API y zona en que se reinicia | no se usa |
| `LLM_PROVIDER_LITERAL` / `LLM_MODEL_LITERAL` / `LLM_REASONING_EFFORT_LITERAL` | vacías (usa `LLM_PROVIDER` y `OPENROUTER_*`) | `openrouter` / id del modelo / `low` | no se usa al ingerir |
| `LLM_PROVIDER_RAZONAMIENTO` / `LLM_MODEL_RAZONAMIENTO` / `LLM_REASONING_EFFORT_RAZONAMIENTO` | vacías (modo no disponible) | `openrouter` / `z-ai/glm-5.3` / `medium` | no se usa al ingerir |
| `LLM_PRICE_IN_*` / `LLM_PRICE_OUT_*` | `0` | USD por millón de tokens; solo estiman el costo si el proveedor no lo informa | no se usa |
| `CORS_ORIGINS` | vacía (el panel usa el proxy de Vite) | direcciones de los sitios estáticos, separadas por comas | no se usa |
| `QUERY_SEARCH_LIMIT` / `QUERY_SEARCH_LIMIT_RAZONAMIENTO` | `8` / `16` | resultados de la búsqueda en modo literal y con razonamiento (de 1 a 50) | no se usa al ingerir |
| `MAX_UPLOAD_MB` | `25` | `25` | `25` |
| `OPENROUTER_MANAGEMENT_KEY` | vacía | vacía (no recomendada, ver "Topes de gasto y saldo") | no se usa |

Regla importante: **producción y la instancia que ingiere deben usar el mismo `EMBEDDING_PROVIDER` y la misma `QDRANT_COLLECTION`**. Si no, las preguntas se embeben con un modelo distinto al de los documentos y la búsqueda devuelve basura (o la API no arranca por diferencia de dimensión).

## Puesta en marcha desde cero

1. **Qdrant Cloud:** crear un clúster free, copiar su URL y una API key.
2. **Neon:** crear un proyecto free, copiar la *connection string* (`postgresql://...?sslmode=require`). La API crea las tablas sola al arrancar.
3. **Gemini:** crear una API key en [Google AI Studio](https://aistudio.google.com).
4. **Render:** *New → Blueprint*, apuntar al repositorio; Render lee `render.yaml`. Completar los secretos marcados como `sync: false`: `QDRANT_URL`, `QDRANT_API_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.
5. Verificar: `GET https://<servicio>.onrender.com/health` debe responder `{"status":"ok"}`.

Cada push a `main` redeploya Render automáticamente.

## Despliegue en Railway con OpenRouter (en producción desde 2026-10-07)

Reemplazó a Render free: la API en [Railway](https://railway.com) (plan Hobby) y el LLM a través de [OpenRouter](https://openrouter.ai). Neon y Qdrant Cloud no cambian. Motivos y alternativas comparadas en [ESCALABILIDAD.md](ESCALABILIDAD.md), sección "Railway y OpenRouter".

**Costo y tope de gasto:**

| Pieza | Costo esperado | Tope duro |
|---|---|---|
| Railway Hobby | 5 USD al mes, que incluyen 5 USD de uso; MIA consume unos 4 a 4.5 USD (unos 340 MB de RAM en reposo, cobro por segundo) | Límite de uso (*Usage limits*): al alcanzarlo, Railway apaga los servicios en vez de seguir cobrando. Avisa por correo al 75 %, 90 % y 100 %. Los datos se conservan. |
| OpenRouter | Según consultas: unos 10 a 12 USD por 1000 consultas con un modelo sin razonamiento y GLM 5.3 (ver ESCALABILIDAD.md) | Saldo prepagado: al agotarse, las consultas fallan. Además, cada clave puede tener su propio límite de crédito. |

**Qué cambia frente a Render free:** la API no se duerme, y con memoria suficiente la ingesta se hace en el propio servidor (`INGESTION_ENABLED=true`, en segundo plano como en local), así que se pueden subir documentos desde Swagger o desde el futuro panel de administración sin levantar una API local. Railway redespliega solo con los push a `main` que cambian el código (`src/`, `Dockerfile`, `pyproject.toml` o `railway.json`, ver `watchPatterns` en `railway.json`); un cambio de documentación no reinicia la API.

**Pasos, OpenRouter (una sola vez):**

1. Crear la cuenta en OpenRouter.
2. En *Settings > Privacy*, desactivar el uso de proveedores que pueden guardar o entrenar con los datos. La API ya lo pide en cada consulta (`data_collection: deny`), pero a nivel de cuenta protege también a cualquier otra clave.
3. En *Credits*, cargar saldo (10 a 15 USD alcanzan para un mes de piloto; comisión de 5.5 %). Dejar desactivada la recarga automática: el saldo es el tope.
4. En *Keys*, crear una clave para la API (p. ej. `mia-railway`) con un límite de crédito.
5. En [openrouter.ai/models](https://openrouter.ai/models), copiar el id exacto del modelo a usar (p. ej. el de Gemini 3.5 Flash-Lite o el de GLM-5.3-Flash).
6. Antes de desplegar, probarlo en local: en `.env`, `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` y `OPENROUTER_REASONING_EFFORT=low` (varios modelos razonan siempre y rechazan `none` con un error 400); levantar la API con `--env-file .env.produccion` como en "Cargar documentos" y correr `scripts/pruebas_mvp.py` contra ella. Así se comparan modelos (p. ej. Gemini Flash-Lite contra GLM-5.3-Flash) con las 15 preguntas de aceptación, por unos centavos.

**Pasos, Railway (una sola vez):**

1. Crear la cuenta y pasar al plan Hobby.
2. **Antes de desplegar**, en la configuración del espacio de trabajo, *Usage > Set usage limits*: alerta por correo en 6 USD y límite duro en 10 USD.
3. *New Project > Deploy from GitHub repo* y elegir este repositorio. Railway lee `railway.json`: construye con el `Dockerfile` y usa `/health` como chequeo de salud.
4. En el servicio, *Variables > Raw Editor*: pegar `deploy/railway/variables.example.env` y completar las credenciales de Neon, Qdrant Cloud y OpenRouter, y el `OPENROUTER_MODEL` elegido.
5. En *Settings*, elegir la región más cercana a Qdrant Cloud (este de Estados Unidos).
6. En *Settings > Networking*, *Generate Domain* para obtener la URL pública.
7. Verificar: `GET <url>/health` debe responder `{"status":"ok"}`, y `python scripts/pruebas_mvp.py --url <url> --clave <clave de un artefacto>` debe dar 19 de 19 (desde la versión 2 las consultas exigen la clave de un artefacto, ver "Artefactos y claves").
8. Apuntar la Consulta a Railway: `MIA_API_URL=<url> npm run dev` en `web/consulta/`, y escribir la clave del artefacto en la pantalla de clave.
9. Con Railway verificado, suspender el servicio de Render (*Settings > Suspend*) para que no haya dos APIs publicadas. Ambas leen las mismas bases, así que no hay datos que migrar.

## Panel de administración, artefactos y topes (versión 2)

La versión 2 agrega el panel de administración (`web/admin/`) y cambia cómo se accede a la API: las operaciones de administración piden la clave de administración y las consultas piden la clave de un artefacto. Cómo funciona por dentro: [ARQUITECTURA.md](ARQUITECTURA.md); qué se pidió: [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md).

### Artefactos y claves

- **Clave de administración:** la variable `ADMIN_KEY` de la API. Es la que se escribe en el panel (se recuerda en el navegador) y la que usan `scripts/cargar_carpeta.py` (`--clave`) y `scripts/reorganizar_v2.py`. Generar una larga y aleatoria: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Sin `ADMIN_KEY` en la instancia, las operaciones de administración responden 503.
- **Registrar un artefacto:** panel > *Artefactos y accesos* > *+ Nuevo artefacto*. Se elige qué puede consultar (unidades completas, dominios puntuales o todos), qué modos puede usar y su tope diario. La API genera su clave y **se muestra una sola vez**: copiarla en ese momento. Si se pierde o se filtra, *Regenerar clave* (la anterior deja de funcionar de inmediato).
- **Las dos instancias de la Consulta administrativa** son dos artefactos, con la misma aplicación y claves distintas. Configuración sugerida para empezar:

| Artefacto | Acceso | Modos | Tope total / de razonamiento |
|---|---|---|---|
| Consulta administrativa Postgrados Computación | Unidad Computación completa | literal y con razonamiento | 1.50 / 1.00 USD por día |
| Consulta administrativa Postgrados Administración Empresas | Unidad Administración de Empresas completa | literal y con razonamiento | 1.00 / 0.60 USD por día |

- Cambiar el acceso, los modos o los topes rige desde la consulta siguiente, sin reiniciar la API. Al crear un dominio nuevo, el panel avisa qué artefactos lo verán de inmediato (los que tienen la unidad completa o todos los dominios) y cuáles hay que habilitar a mano.
- Para probar con curl: `curl -H "X-Artifact-Key: mia_..." <url>/domains` (los dominios que ve ese artefacto) y `<url>/config` (sus modos).

### Topes de gasto y saldo

- **Tope por artefacto** (panel): USD por día para todos sus modos juntos, y uno menor opcional solo para el modo con razonamiento. Al alcanzarlo, ese artefacto (o ese modo) responde 429 hasta la medianoche de Costa Rica; los demás siguen. Un artefacto nuevo arranca en 0.50 USD.
- **Tope de toda la API** (`DAILY_CAP_USD` en Railway): no se cambia desde el panel a propósito, para que una clave de administración filtrada no pueda subirlo. Si los topes de los artefactos suman más que este, el panel avisa: un artefacto puede quedarse sin servicio por el gasto de otros.
- El costo de una consulta se conoce al terminar, así que un tope puede excederse por lo que cuesten las consultas que estaban en curso. `OPENROUTER_MAX_TOKENS` acota ese exceso.
- **Saldo en el módulo Uso:** se lee del **límite de crédito de la clave** de OpenRouter (`mia-railway`), no del saldo de la cuenta. MIA deja de responder con el menor de los dos: conviene mantener el límite de la clave cerca de lo que se cargó en la cuenta. Leer el saldo de toda la cuenta exige una clave de gestión (`OPENROUTER_MANAGEMENT_KEY`), que puede crear claves sin límite: si se filtrara desde el servidor, el daño pasaría de "el límite de la clave" a "todo el saldo". No se recomienda en producción.
- El módulo Uso incluye las consultas rechazadas (con costo cero) y puede descargar el registro en CSV. Las **preguntas pueden contener datos personales**: el registro solo se ve con la clave de administración y el CSV las omite salvo que se marque incluirlas.

### Publicar el panel como sitio estático

El panel se publica igual que la Consulta: como un servicio de Railway que sirve archivos estáticos (`web/admin/Dockerfile` y `web/admin/railway.json`). Se puede apagar con *Remove* cuando no se use.

1. En el proyecto de MIA: *New > GitHub Repo* y elegir este repositorio. Nombre sugerido: `mia-panel`.
2. *Settings > Source > Root Directory*: `web/admin`. **No** poner ruta en *Config-as-code* ni en *Dockerfile Path*: con una ruta fija Railway busca el `Dockerfile` de la raíz (el de la API) y la compilación falla con `"/pyproject.toml": not found`. Sin ruta, usa el `Dockerfile` de la carpeta.
3. *Variables*:
   - `VITE_API_URL` = URL de la API **con `https://`** y sin barra final (`https://mia-main.up.railway.app`). Es variable de **compilación**: si cambia, hay que volver a desplegar.
   - `PORT` = `3000` (Railway inyecta su propio `PORT`; con este valor el sitio escucha en el mismo puerto que el dominio).
4. *Settings > Networking > Generate Domain*, con puerto `3000`. *Replica Limits*: 0.5 vCPU y 512 MB bastan.
5. Agregar la dirección del panel a `CORS_ORIGINS` en la API (junto a las de la Consulta, separadas por coma, con `https://` y sin barra final) y desplegar la API; sin eso el navegador bloquea las llamadas.
6. Abrir el sitio e ingresar la clave de administración.

**Seguridad.** Un panel publicado es accesible desde internet: lo único que protege la administración es `ADMIN_KEY`, que debe ser larga y aleatoria y no compartirse. El código publicado no contiene ninguna clave; la clave se escribe en el navegador y se guarda solo ahí. Apagar el servicio (*Remove*) cuando no se use reduce la exposición. Para uso ocasional también se puede correr en local: `cd web/admin && MIA_API_URL=<url> npm run dev` (puerto 3001), sin CORS.

### Consulta administrativa (publicar las dos instancias)

La Consulta (`web/consulta/`) se compila una vez por instancia y se publica **dos veces**, una por unidad, para que cada dirección recuerde su propia clave y cada unidad tenga su enlace. Cada instancia es un servicio de Railway dentro del mismo proyecto que la API. La compilación es idéntica: lo que cambia es la clave con que se abre, que la API traduce en el nombre, los dominios y los modos de la instancia.

1. **Registrar los artefactos** en el panel (si no existen): `Consulta administrativa Postgrados Computación` (unidad Computación completa) y `Consulta administrativa Postgrados Administración Empresas` (unidad Administración de Empresas completa), ambos con los dos modos y su tope diario. Copiar cada clave `mia_...` al crearla: se muestra una sola vez.
2. **Crear los servicios en Railway** (una vez por instancia), en el proyecto de MIA: *New > GitHub Repo* y elegir este repositorio. Nombres sugeridos: `mia-computacion` y `mia-administracion`. En cada servicio:
   - *Settings > Source > Root Directory*: `web/consulta`. Railway usa el `Dockerfile` de esa carpeta (compila con Vite y sirve `dist` con `serve`).
   - Dejar vacíos *Config-as-code* y *Dockerfile Path*: con una ruta fija Railway busca el `Dockerfile` de la raíz (el de la API) y la compilación falla con `"/pyproject.toml": not found`. Sin ruta, usa el `Dockerfile` de `web/consulta`.
   - *Variables*: `VITE_API_URL` = URL de la API **con `https://`** (`https://mia-main.up.railway.app`, sin barra final). Sin esta variable la compilación falla con un mensaje claro. Es una variable de **compilación**: si cambia, hay que volver a desplegar. Agregar también `PORT` = `3000`: Railway inyecta su propio `PORT` (8080), y el dominio debe apuntar al mismo puerto en que escucha el sitio.
   - *Settings > Networking > Generate Domain*: la dirección pública de esa instancia.
3. **Permitir los orígenes:** agregar ambas direcciones a `CORS_ORIGINS` en la API (servicio `MIA`), separadas por coma, con `https://` y sin barra final, junto a las demás si ya hay. Sin eso el navegador bloquea las llamadas. Un cambio de variables exige un deploy de la API.
4. **Entregar a cada equipo** su enlace y su clave por un canal privado. Las claves se pueden regenerar desde el panel (la anterior deja de valer de inmediato).
5. **Verificar** abriendo cada sitio con su clave: debe mostrar su nombre y solo los dominios de su unidad.

**Apagar y encender un sitio (para compartirlo solo cuando haga falta).** En el servicio, *Deployments*, menú del despliegue activo, **Remove**: el enlace deja de responder y el servicio no consume crédito; su configuración y su dirección se conservan. Para encenderlo de nuevo, *Redeploy* sobre ese despliegue (o `railway redeploy -s mia-computacion` desde la CLI; `railway down -s mia-computacion` lo apaga). Se puede hacer desde el celular. Dos cosas más: la API no se apaga nunca (los sitios la necesitan), y para cortar el uso al instante sin esperar un deploy basta **desactivar el artefacto** en el panel: el sitio sigue publicado, pero la Consulta explica que fue desactivada.

**Costo.** Cada servicio solo gasta mientras está encendido, y un servidor de archivos estáticos consume muy poco; aun así descuenta del crédito del plan Hobby, que la API ya usa casi por completo, y el tope de uso configurado en Railway sigue siendo el límite. Alternativas que no consumen crédito: correr la Consulta en tu computador (`cd web/consulta && MIA_API_URL=<url> npm run dev`) para una demostración, o publicarla en un sitio estático gratuito (Render Static Sites o Vercel, con `VITE_API_URL` en la compilación y `dist` como carpeta publicada).

**Modos de respuesta.** Cada modo trae su instrucción al modelo y su cantidad de resultados de búsqueda. El modo con razonamiento recupera más fragmentos (`QUERY_SEARCH_LIMIT_RAZONAMIENTO`, 16 por defecto) y tarda decenas de segundos; si una instancia no tiene configurado su modelo (`LLM_PROVIDER_RAZONAMIENTO`) la opción aparece deshabilitada con el motivo.

### Migraciones y reorganización de los datos

- **Migraciones:** la API aplica las de Alembic al arrancar. La base de Neon, creada antes con `create_all`, se marca sola en la revisión `0001` y luego recibe `0002` (unidades, carpetas, artefactos y registro de consultas). Se puede correr a mano con `DATABASE_URL=<url> alembic upgrade head`.
- **Reorganización** (una sola vez): lleva los cinco dominios cargados a la estructura de unidades y carpetas, y reparte los 30 proyectos de graduación de Computación en sus tres tipos. **No vuelve a procesar ningún documento**; solo cambia el dominio de sus fragmentos en Qdrant. Se corre desde la laptop, porque lee las carpetas de origen de `tmp/`:

```bash
python scripts/reorganizar_v2.py --env-file .env.produccion --simular   # muestra los cambios sin escribir nada
python scripts/reorganizar_v2.py --env-file .env.produccion             # aplica
python scripts/reorganizar_v2.py --env-file .env.produccion             # una segunda vez: 0 cambios
```

`--simular` exige que el esquema ya esté migrado (desplegar primero). El script informa los documentos que no encontró en `tmp/` y, al final, la estructura resultante, que debe coincidir con la sección 2.3 de [Definicion_Requerimientos_V2.md](Definicion_Requerimientos_V2.md). El mapeo (dominios nuevos, carpetas y la clasificación de los proyectos) está en `scripts/datos/reorganizacion_v2.json`.

### Checklist de puesta en producción de la versión 2

**Ejecutado el 2026-10-08 y 2026-10-09** (versión 2 en producción). Se conserva como referencia, por ejemplo para repetirlo en otro entorno. Lo ejecuta quien administra MIA, en este orden. Aviso: en este proyecto Railway **no redespliega solo** al hacer el merge a `main` (ver "Desplegar cambios").

**Antes del merge**

1. **Variables en Railway** (servicio > *Variables*; el bloque listo para pegar está en `deploy/railway/variables.example.env`, sección "Versión 2"):
   - `ADMIN_KEY`: generarla **en tu máquina**, sin pasarla por chats ni correos: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Guardarla en un gestor de contraseñas: es la clave que se escribe en el panel.
   - `DAILY_CAP_USD` (3 por defecto) y `CAP_TIMEZONE` (`America/Costa_Rica`).
   - Modo literal: `LLM_PROVIDER_LITERAL=openrouter`, `LLM_MODEL_LITERAL=z-ai/glm-5.3-flash`, `LLM_REASONING_EFFORT_LITERAL=low`. Es lo que ya corre hoy en producción; si se omiten, el modo literal usa `LLM_PROVIDER` y `OPENROUTER_*` y da lo mismo.
   - Modo con razonamiento: `LLM_PROVIDER_RAZONAMIENTO=openrouter`, `LLM_MODEL_RAZONAMIENTO=z-ai/glm-5.3`, `LLM_REASONING_EFFORT_RAZONAMIENTO=medium`. Se eligió `medium` porque es el esfuerzo que se probó contra producción (15 de 15, ver [PRUEBAS_MVP.md](PRUEBAS_MVP.md)); con `high` el razonamiento puede consumir todo `OPENROUTER_MAX_TOKENS` (8000) y dejar la respuesta vacía. Si se quiere subir, probarlo antes con la pregunta de los créditos (criterio 7 de la versión 2: debe responder 12) y, de ser necesario, subir también `OPENROUTER_MAX_TOKENS`.
   - `LLM_PRICE_IN_*` y `LLM_PRICE_OUT_*` (USD por millón de tokens): OpenRouter informa el costo real de cada respuesta y estos precios solo se usan si no lo informara. Conviene ponerlos de todos modos: sin ellos esa estimación da 0 y los topes de gasto no contarían esa consulta. Referencia de Z.AI: `glm-5.3-flash` 0.15 y 0.5; `glm-5.3` 1.4 y 4.4. Cada proveedor de OpenRouter cobra distinto (de 0.06 a 2.8 por millón de tokens de entrada en `glm-5.3`), así que son una estimación y no una tarifa.
   - **Privacidad:** el modo con razonamiento manda los mismos fragmentos (incluidas las actas con datos personales) a otro modelo. La protección es la de la cuenta de OpenRouter (*Settings > Privacy*: solo proveedores de retención cero y que no entrenan), que aplica a todos los modelos; la API no expone la política de datos de cada proveedor, así que no se puede verificar desde fuera. `z-ai/glm-5.3` ya respondió 15 de 15 bajo esa configuración. Con `OPENROUTER_ZDR=true` la API lo exige en cada consulta, pero si algún modelo no tiene proveedores de retención cero, la consulta fallará en vez de ir a uno sin ella: si se activa, probar ambos modos.
   - Dejar `OPENROUTER_MODEL` como está.
   - **Sobre los redespliegues:** la versión que corre hoy en `main` ignora las variables que no conoce (la configuración usa `extra="ignore"`), así que agregarlas antes del merge no la afecta. Railway puede dejar los cambios de variables en espera hasta que se pulsa *Deploy*; conviene agregarlas todas juntas y no desplegar hasta el merge, para que un solo despliegue aplique variables y código. Si en tu panel se aplican de inmediato, el reinicio es inocuo.
2. **Probar la migración contra una copia de Neon.** Hasta ahora solo se probó en SQLite; esto la ejecuta sobre Postgres, con tus datos reales (migra, comprueba que se conservan, prueba que el nombre de dominio pase a ser único por unidad, y baja y sube una revisión).
   1. En Neon: *Branches > Create branch*, tomando como padre la rama de producción (copia los datos). En *Connect*, con la rama elegida, copiar la cadena de conexión con *Connection pooling* **desactivado** (la directa).
   2. Desde la laptop: `python scripts/probar_migracion.py --url '<cadena de la rama>' --produccion .env.produccion --es-una-copia`. Con `--produccion` el script se niega a correr si la cadena apunta a la misma base que la de producción (compara servidor y nombre de la base), y sin `--es-una-copia` no escribe nada.
   3. Debe terminar en `TODO BIEN`. Si no, **no hacer el merge** y mandar la salida completa: dice qué paso falló. La restricción única de `domains.name` se llama `domains_name_key` en Postgres y es el punto más probable de fallo.
   4. Borrar la rama de Neon al terminar (*Branches > Delete*): quedó modificada.
3. **Límite de la clave de OpenRouter:** ajustar el límite de crédito de `mia-railway` al saldo que hay en la cuenta, para que el módulo Uso muestre un saldo real.

**Merge y despliegue**

4. Hacer el merge de `dev` a `main` y desplegar la API (`railway up -s MIA --detach`). La API migra la base al arrancar: en el log debe verse `Running upgrade 0001 -> 0002`. Verificar `GET <url>/health`. **Desde este momento `/query` responde 401 sin clave de artefacto**, y subir documentos o crear dominios pide `X-Admin-Key`.

**Después del despliegue**

5. **Reorganizar los datos:** los tres comandos de "Migraciones y reorganización", en ese orden. Revisar que el resumen coincida con la sección 2.3 y que no queden documentos sin ubicar.
6. **Abrir el panel** (`MIA_API_URL=<url> npm run dev` en `web/admin`, o publicado) con la clave de administración: el inventario debe mostrar las dos unidades, Computación con 7 dominios y Administración de Empresas con 4, y los 162 documentos en "Listo".
7. **Registrar las dos instancias** de la Consulta administrativa (tabla de "Artefactos y claves") y copiar cada clave.
8. **Correr las pruebas de aceptación:** `python scripts/pruebas_mvp.py --url <url> --clave <clave de un artefacto con acceso a las dos unidades>`. Debe dar 19 de 19 en modo literal; ese artefacto debe tener las dos unidades. Si no se registró uno así, registrar uno de prueba y desactivarlo después. Opcional: `--modo razonamiento`.
9. **Entregar las claves** a quien use cada instancia, y actualizar lo que consultaba sin clave (scripts; el cliente web anterior ya no existe, lo reemplazó la Consulta administrativa).
10. **Publicar el panel** y las dos Consultas (secciones "Publicar el panel como sitio estático" y "Consulta administrativa") y agregar sus direcciones a `CORS_ORIGINS`.
11. **Mirar el módulo Uso:** que el saldo aparezca (o que explique por qué no) y que las consultas de las pruebas estén en el registro.

**Si algo falla:** volver a desplegar el commit anterior de `main` en Railway es seguro, porque las columnas y tablas nuevas son opcionales para la versión anterior. La reorganización de datos (dominios renombrados, proyectos repartidos) se queda: la versión anterior mostraría los nombres nuevos.

### Desplegar cambios (no hay auto-deploy)

**Atajo:** `scripts/servicios.py` enciende, apaga y consulta el estado de los cuatro servicios (`./scripts/servicios.py estado`, `encender [servicio...]`, `apagar [servicio...]`; la API va primero al encender y al final al apagar; espera cada despliegue y comprueba que responda). Apagar equivale a *Remove* y no borra nada. Los comandos de abajo son lo que hace por dentro.

Railway tiene los servicios conectados al repositorio como público, **sin su aplicación de GitHub instalada**, así que un push a `main` no dispara ningún deploy (el aviso es *"This is a public repository without a Railway GitHub App installation"*). Decisión tomada: mantener los deploys manuales. Hay dos formas:

```bash
cd <raíz del repositorio>           # con el árbol limpio y en la rama que se quiere publicar
railway up -s MIA --detach                  # API
railway up -s mia-computacion --detach      # Consulta de Computación
railway up -s mia-administracion --detach   # Consulta de Administración de Empresas
railway up -s mia-panel --detach            # panel de administración
```

`railway up` sube los archivos de la carpeta local (respeta `.gitignore`, así que `.env*`, `tmp/` y `mia.db` no se suben) y respeta el *Root Directory* de cada servicio. El despliegue no muestra commit en el panel de Railway. Alternativas: el botón **Deploy** del servicio, que aplica las variables en espera y el último commit, o instalar la aplicación de GitHub de Railway para activar el auto-deploy (entonces conviene fijar *Watch Paths* por servicio: `/web/consulta/**` y `/web/admin/**`).

**Reglas que dieron problemas:**
- Los cambios de variables hechos con la CLI (`--skip-deploys`) o en el panel quedan **en espera** hasta un deploy. `PORT`, `CORS_ORIGINS` y los demás se leen al arrancar; `VITE_API_URL` se usa al **compilar**, así que exige un deploy completo, no solo reiniciar.
- Los sitios estáticos necesitan `PORT=3000` (Railway inyecta 8080 y el dominio apunta al 3000) y `VITE_API_URL` con `https://`.
- En los servicios estáticos **no** fijar *Config-as-code* ni *Dockerfile Path* (hace que se use el `Dockerfile` de la raíz, el de la API).
- Para comprobar qué corre: `railway deployment list -s <servicio>` y los logs (`Accepting connections at http://localhost:3000` en los sitios).

## Despliegue en Cloud Run (alternativa, no adoptada)

Se preparó el 2026-10-06 y quedó descartado al requerir Google Cloud un prepago de 30 USD; los archivos quedan en `deploy/cloudrun/` por si se retoma. Motivos y alternativas comparadas en [ESCALABILIDAD.md](ESCALABILIDAD.md), sección "Migración a Cloud Run". Neon y Qdrant Cloud no cambian.

**Cómo se acota el gasto.** Cloud Run cobra por uso y Google no permite fijar un tope directo, así que se combinan dos cosas:
- Límites del servicio (`deploy/cloudrun/desplegar.sh`): como máximo 1 instancia de 1 vCPU y 1 GiB, cobro solo mientras se responde una petición y nada encendido sin tráfico. El peor caso (la API ocupada las 24 horas, p. ej. por un ataque) ronda los 2 USD por día. Con el uso del piloto queda dentro del plan gratuito.
- Corte por presupuesto (`deploy/cloudrun/configurar_corte.sh`): presupuesto mensual de 3 USD con alertas por correo al 33 %, 66 % y 100 %. Al llegar al 100 %, una función desactiva la facturación del proyecto y la API se apaga. Como Google informa el gasto con unas horas de retraso, la pérdida máxima ronda los 3 a 5 USD.

El LLM (GLM, de Z.ai) se cobra aparte, en la cuenta de Z.ai: el tope de ese gasto se maneja allí.

**Pasos (una sola vez):**

1. Crear un proyecto en [Google Cloud](https://console.cloud.google.com) y vincularle una cuenta de facturación (pide tarjeta).
2. Instalar la CLI `gcloud` y autenticarse: `gcloud auth login`.
3. Configurar el corte por presupuesto:
   ```bash
   gcloud billing accounts list    # copiar el ID de la cuenta (XXXXXX-XXXXXX-XXXXXX)
   PROYECTO=<id> CUENTA_FACTURACION=<id de la cuenta> deploy/cloudrun/configurar_corte.sh
   ```
   Requiere ser administrador de la cuenta de facturación. `MONTO=<USD>` cambia el presupuesto (3 por defecto).
4. Crear una API key en [Z.ai](https://z.ai) para GLM.
5. Copiar `deploy/cloudrun/env.cloudrun.example.yaml` a `.env.cloudrun.yaml` (en la raíz, ignorado por git) y completar las credenciales de Neon, Qdrant Cloud y Z.ai.
6. Desplegar: `PROYECTO=<id> deploy/cloudrun/desplegar.sh`. Construye la imagen en Google con el mismo Dockerfile y al terminar imprime la URL del servicio.
7. Verificar: `GET <url>/health` debe responder `{"status":"ok"}`.

Para redesplegar después de un cambio, repetir el paso 6 (no hay despliegue automático con cada push, a diferencia de Render).

**Diferencias con Render:**
- La ingesta se hace en el propio servidor (`INGESTION_ENABLED=true`): con 1 GiB alcanza. Como la CPU se frena al responder, se ingiere dentro de la misma petición (`INGESTION_SYNC=true`): `POST /domains/{id}/documents` tarda lo que tarde la ingesta y responde con el estado final (`done` o `error`), no con `pending`.
- No se duerme como Render: sin tráfico se apaga, pero vuelve a arrancar en pocos segundos.
- Si el corte por presupuesto se activa, la API deja de responder hasta reactivar la facturación del proyecto desde la consola (*Facturación > Administrar cuenta de facturación*). Antes de reactivarla, revisar en *Cloud Run > Métricas* qué consumió.
- Cada despliegue guarda una imagen en Artifact Registry. El plan gratuito incluye 0.5 GB: borrar las imágenes viejas desde la consola si se acumulan (cuestan centavos por GB al mes).

## Cargar documentos (ingesta)

La ingesta no se hace en Render (512 MB no alcanzan para actas de más de ~100 páginas; `POST /domains/{id}/documents` responde 503 allí). Se hace desde una máquina local con la misma API:

```bash
source .venv/bin/activate
# .env.produccion (ignorado por git) con las credenciales de producción:
#   DATABASE_URL=<Neon>, QDRANT_URL=<Qdrant Cloud>, QDRANT_API_KEY=<...>,
#   EMBEDDING_PROVIDER=local, QDRANT_COLLECTION=mia_chunks, INGESTION_ENABLED=true
# --env-file carga esas variables antes de arrancar y tienen prioridad sobre las de .env.
# (No usar `source .env.produccion`: la URL de Neon contiene "&" y el shell la corta.)
# INGESTION_SYNC=true: cada subida responde cuando el documento terminó de indexarse, así una carga
# masiva no acumula ingestas en espera dentro de la API.
# ADMIN_KEY debe estar también en .env.produccion: subir documentos y crear dominios exige la clave de administración.
INGESTION_SYNC=true uvicorn mia.api.main:app --env-file .env.produccion --port 8010
```

Ojo al copiar la URL de Neon en `DATABASE_URL`: debe empezar con `postgresql://` (si se editó la línea de SQLite, verificar que no quede un prefijo `sqlite:`). Con `Connection pooling` desactivado en el diálogo *Connect* de Neon.

**Carga de una carpeta completa (recomendado):** `scripts/cargar_carpeta.py` crea el dominio si no existe (dentro de la unidad indicada, que también crea si falta) y sube todos los PDF, DOCX y TXT de una o varias carpetas (con subcarpetas), uno a la vez, informando el estado de cada uno. Los documentos quedan en la raíz del dominio; para ordenarlos en carpetas, usar el panel:

```bash
python scripts/cargar_carpeta.py --url http://localhost:8010 --clave "$ADMIN_KEY" \
  --unidad "Administración de Empresas" --dominio "Memoria del Consejo" \
  --descripcion "Actas del Consejo de Área Académica" \
  "tmp/Información_analítica_de_negocios/ACTAS"
```

Desde el panel también se pueden subir documentos (en el inventario, *Subir* en un dominio o carpeta, o arrastrándolos). `--excluir <texto>` omite los archivos cuyo nombre contenga ese texto (p. ej. un PDF escaneado sin texto). Los comandos exactos de la carga actual están en "Datos cargados" ([PRUEBAS_MVP.md](PRUEBAS_MVP.md)).

**Carga manual de un documento**, en `http://localhost:8010/docs`:

1. `GET /domains` para ver si el dominio ya existe; si no, `GET /units` para elegir la unidad y `POST /domains` con `{"unit_id": "<id>", "name": "Memoria del Consejo", "description": "..."}`. Guardar el `id`. En Swagger, *Authorize* no aplica: las operaciones de administración piden el encabezado `X-Admin-Key`.
2. `POST /domains/{id}/documents` con cada archivo (PDF, DOCX o TXT) y, opcional, `folder_id`. Responde enseguida con estado `pending`.
3. `GET /domains/{id}/documents` hasta que todos estén en `done`. Como referencia, un acta de ~180 páginas (~540 fragmentos) tarda unos minutos en una laptop.
4. Probar una consulta (`POST /query` con `{"domains": ["<id>"], "question": "..."}` y el encabezado `X-Artifact-Key` de un artefacto con acceso a ese dominio).

Subir dos veces el mismo archivo al mismo dominio (en cualquier carpeta) no duplica nada: devuelve el documento existente con `already_existed: true`. El límite de tamaño por archivo es `MAX_UPLOAD_MB` (25).

Si un documento queda en `error`, ver el log de la API local (el mensaje empieza con "Fallo indexando documento"). Un documento que quedó en `processing` porque se cortó la API no se reintenta solo; hoy la forma de reintentar es borrar esa fila en Neon y sus puntos en Qdrant (filtro `document_id`) y volver a subir el archivo.

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Render se reinicia con "Out of memory" | Se ingirió en Render, o se cambió a un modelo más pesado | Mantener `INGESTION_ENABLED=false` en Render e ingerir localmente |
| Un sitio (Consulta o panel) responde 502 | El puerto del dominio no coincide con el que escucha el sitio (Railway inyecta `PORT=8080`) | Variable `PORT=3000` en el servicio y deploy; el puerto del dominio debe ser 3000 |
| La Consulta o el panel dicen "No se pudo conectar" | La dirección del sitio no está en `CORS_ORIGINS`, o `VITE_API_URL` no lleva `https://` | Corregir la variable (la de CORS en la API, la otra en el sitio) y desplegar |
| La compilación de un sitio falla con "Falta VITE_API_URL" o `"/pyproject.toml": not found` | Falta la variable, o se fijó la ruta de *Config-as-code* o del `Dockerfile` | Ver "Desplegar cambios" |
| La primera consulta tarda ~1 min | Render free se durmió tras 15 min sin tráfico | Normal. Opcional: un monitor gratuito (UptimeRobot, cron-job.org) que llame a `/health` cada 10 min |
| La API no arranca: "La colección ... tiene vectores de dimensión X" | Se cambió `EMBEDDING_PROVIDER` sin cambiar `QDRANT_COLLECTION` | Usar la colección que corresponde al proveedor, o reindexar |
| Error de conexión a Qdrant | El clúster free se suspendió tras 1 semana sin uso | Reactivarlo desde el panel de Qdrant Cloud |
| `/query` responde 502 tras ~2 min | Gemini saturado (503 "high demand", frecuente en el tier gratuito) o cuota agotada | Esperar unos minutos y reintentar; revisar la cuota en Google AI Studio. El proveedor corta tras 3 intentos para no dejar la consulta colgada |
| `/query` responde 500 y el log de Qdrant dice "Index required but not found for \"domain\"" | La colección se creó sin índices de payload (Qdrant Cloud los exige para filtrar) | Reiniciar la API: `ensure_collection()` crea los índices al arrancar |
| La respuesta es correcta pero incompleta ("el fragmento se interrumpe...") | La sección o lista ocupa más fragmentos de los que se recuperan | Verificar `QUERY_SEARCH_LIMIT` (8) y `QUERY_CONTEXT_NEIGHBORS` (1) en Render; subir los vecinos a 2 si el documento tiene secciones muy largas |
| Toda consulta responde 401 desde la versión 2 | Falta la clave del artefacto (`X-Artifact-Key`), o se regeneró y la que se usa es la anterior | Usar la clave vigente; si se perdió, regenerarla en el panel |
| Una consulta responde 403 | El artefacto está desactivado, o pide un dominio o un modo que no tiene permitido | Revisar el artefacto en el panel (*Artefactos y accesos*); el mensaje dice cuál es el motivo |
| Una consulta responde 429 | Se alcanzó un tope diario de gasto (de toda la API, del artefacto o de su modo con razonamiento) | El mensaje dice cuál. Se reinicia a la medianoche de Costa Rica; mientras tanto, subir el tope del artefacto desde el panel, o `DAILY_CAP_USD` en Railway |
| El panel dice "La clave guardada ya no es válida" | Se cambió `ADMIN_KEY` en la API | Ingresar la clave vigente |
| El panel publicado no carga datos y la consola dice que CORS bloqueó la petición | La dirección del sitio no está en `CORS_ORIGINS` | Agregarla en Railway, sin barra final |
| La API responde 503 al crear dominios o subir documentos | No hay `ADMIN_KEY` en la instancia, o `INGESTION_ENABLED=false` | Configurar la variable que corresponda |
| El módulo Uso muestra "No se pudo consultar OpenRouter" o "no tiene límite de crédito" | La clave de OpenRouter es inválida, OpenRouter no respondió, o la clave no tiene un límite de crédito | Ver el motivo en la tarjeta de saldo; ponerle un límite de crédito a `mia-railway` |
| Responde "no encontré información" a preguntas que sí tienen respuesta | El umbral es demasiado alto, o la instrucción del LLM es demasiado estricta | Revisar `QUERY_SIMILARITY_THRESHOLD` y `RAG_SYSTEM_PROMPT` (ver `specs/001-pipeline-ingesta-rag/research.md`) |

## Datos y privacidad

- Desde el 2026-10-06 MIA tiene documentos reales entregados por la Unidad de Posgrado en Computación (Mauricio Arroyo) y la Maestría en Analítica de Negocios (Martín Solís), en lugar de los datos de prueba del MVP (actas públicas del Consejo Institucional). Los archivos viven en `tmp/`, que está en `.gitignore`: **no se versionan documentos en el repositorio**.
- **Actas del Consejo de la Unidad de Posgrado en Computación** (20 actas de 2025, cargadas el 2026-10-07): incluyen nombres de estudiantes con número de carné, cédulas, notas, becas y temas de salud. No se cargaron mientras el LLM era Gemini gratuito, que puede usar los datos. Se cargaron al pasar a OpenRouter con la cuenta configurada para usar solo proveedores de **retención cero** y que **no entrenan** con los datos (*Settings > Privacy*). Esa configuración de cuenta es la que protege estas actas: no debe desactivarse. Como refuerzo, en Railway conviene `OPENROUTER_ZDR=true`, que exige lo mismo en cada consulta. El texto de las actas queda guardado en Qdrant Cloud y Neon, fuera del país; si la institución pide otra cosa, ver ESCALABILIDAD.md (modelo y almacenamiento propios). Las actas de Analítica de Negocios sí se cargaron: tratan temas del programa (becas como política, presupuesto, admisión), sin datos de estudiantes; la única cédula es la de su coordinador en su designación ante FUNDATEC.
- El LLM recibe fragmentos de los documentos en cada consulta. Con Gemini gratuito (el LLM anterior) Google podía usar esos datos; por eso las actas con datos personales esperaron al cambio a OpenRouter con retención cero.
- Desde la versión 2 la API exige claves: la de administración para gestionar y la de un artefacto para consultar, y cada artefacto solo ve los dominios que se le permitieron. Es un control mínimo, no un sistema de usuarios: todas las personas que usan un artefacto comparten su clave, y la clave de un sitio público (un chatbot) se puede copiar, por eso cada artefacto tiene su propio tope de gasto. No publicar las claves ni la clave de administración.
- El registro de consultas guarda las preguntas, que pueden contener datos personales (nombres de estudiantes, carnés). Solo se ve con la clave de administración, el CSV las omite por defecto, y no hay política de retención: se conservan durante todo el prototipo. Tratarlo con las mismas condiciones que los documentos con datos personales.
