# Operación de MIA

Guía práctica para desplegar, cargar documentos y mantener funcionando el prototipo. Pensada para quien retome el proyecto sin haber participado en su desarrollo. Cómo está construido el sistema: [ARQUITECTURA.md](ARQUITECTURA.md). Qué cambiar para producción: [ESCALABILIDAD.md](ESCALABILIDAD.md).

## Resumen del despliegue actual (costo cero)

| Pieza | Servicio | Plan | Límite relevante |
|---|---|---|---|
| API (consultas) | [Render](https://render.com), `render.yaml` | Free | 512 MB de RAM; se duerme tras 15 min sin tráfico (primera respuesta tarda 30-60 s); disco no persistente |
| Metadata (dominios, documentos) | [Neon](https://neon.tech) Postgres | Free | 0.5 GB; la base se suspende sin uso y despierta sola al conectarse |
| Vectores | [Qdrant Cloud](https://cloud.qdrant.io) | Free | 1 GB; el clúster se suspende tras 1 semana sin uso (se reactiva desde el panel) |
| LLM | Gemini (`gemini-3.5-flash-lite`, Google AI Studio) | Free | Cuota diaria de solicitudes; los datos del tier gratuito pueden usarse para mejorar los modelos de Google |
| Embeddings | Modelo local e5-small (ONNX), dentro de la imagen | Sin costo | Ninguno externo |
| Ingesta de actas | API corriendo en la máquina de quien opera | Sin costo | Requiere que esa máquina tenga los archivos |

## Variables de entorno

| Variable | Desarrollo (`.env`) | Render | Ingesta local a producción |
|---|---|---|---|
| `DATABASE_URL` | `sqlite:///./mia.db` | URL de Neon (secreto) | URL de Neon |
| `QDRANT_URL` / `QDRANT_API_KEY` | `http://localhost:6333` / vacío | Qdrant Cloud (secretos) | Qdrant Cloud |
| `QDRANT_COLLECTION` | `mia_chunks` | `mia_chunks` | `mia_chunks` |
| `EMBEDDING_PROVIDER` | `local` | `local` | `local` (debe coincidir con Render) |
| `LLM_PROVIDER` / `GEMINI_API_KEY` | `gemini` / clave | `gemini` / clave (secreto) | no se usa al ingerir |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `OPENROUTER_REASONING_EFFORT` / `OPENROUTER_ZDR` | solo si `LLM_PROVIDER=openrouter` | no se usa | no se usa al ingerir (en Railway: clave, id del modelo, `low`, `false`) |
| `GLM_API_KEY` / `GLM_THINKING` | solo si `LLM_PROVIDER=glm` | no se usa | no se usa al ingerir (en Cloud Run: clave de Z.ai / `true`) |
| `INGESTION_ENABLED` | `true` | `false` | `true` |
| `INGESTION_SYNC` | `false` | `false` | `false` (en Cloud Run: `true`) |
| `QUERY_SIMILARITY_THRESHOLD` | ver `.env.example` | igual | no se usa al ingerir |

Regla importante: **Render y la instancia que ingiere deben usar el mismo `EMBEDDING_PROVIDER` y la misma `QDRANT_COLLECTION`**. Si no, las preguntas se embeben con un modelo distinto al de los documentos y la búsqueda devuelve basura (o la API no arranca por diferencia de dimensión).

## Puesta en marcha desde cero

1. **Qdrant Cloud:** crear un clúster free, copiar su URL y una API key.
2. **Neon:** crear un proyecto free, copiar la *connection string* (`postgresql://...?sslmode=require`). La API crea las tablas sola al arrancar.
3. **Gemini:** crear una API key en [Google AI Studio](https://aistudio.google.com).
4. **Render:** *New → Blueprint*, apuntar al repositorio; Render lee `render.yaml`. Completar los secretos marcados como `sync: false`: `QDRANT_URL`, `QDRANT_API_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.
5. Verificar: `GET https://<servicio>.onrender.com/health` debe responder `{"status":"ok"}`.

Cada push a `main` redeploya Render automáticamente.

## Despliegue en Railway con OpenRouter (en preparación, 2026-10-07)

Reemplazo decidido de Render free: la API en [Railway](https://railway.com) (plan Hobby) y el LLM a través de [OpenRouter](https://openrouter.ai). Neon y Qdrant Cloud no cambian. Motivos y alternativas comparadas en [ESCALABILIDAD.md](ESCALABILIDAD.md), sección "Railway y OpenRouter".

**Costo y tope de gasto:**

| Pieza | Costo esperado | Tope duro |
|---|---|---|
| Railway Hobby | 5 USD al mes, que incluyen 5 USD de uso; MIA consume unos 4 a 4.5 USD (unos 340 MB de RAM en reposo, cobro por segundo) | Límite de uso (*Usage limits*): al alcanzarlo, Railway apaga los servicios en vez de seguir cobrando. Avisa por correo al 75 %, 90 % y 100 %. Los datos se conservan. |
| OpenRouter | Según consultas: unos 10 a 12 USD por 1000 consultas con un modelo sin razonamiento y GLM 5.3 (ver ESCALABILIDAD.md) | Saldo prepagado: al agotarse, las consultas fallan. Además, cada clave puede tener su propio límite de crédito. |

**Qué cambia frente a Render free:** la API no se duerme, y con memoria suficiente la ingesta se hace en el propio servidor (`INGESTION_ENABLED=true`, en segundo plano como en local), así que se pueden subir documentos desde Swagger o desde el futuro inventario sin levantar una API local. Railway redespliega solo con los push a `main` que cambian el código (`src/`, `Dockerfile`, `pyproject.toml` o `railway.json`, ver `watchPatterns` en `railway.json`); un cambio de documentación no reinicia la API.

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
7. Verificar: `GET <url>/health` debe responder `{"status":"ok"}`, y `python scripts/pruebas_mvp.py --url <url>` debe dar 15 de 15.
8. Apuntar el cliente web a Railway: `MIA_API_URL=<url> npm run dev` en `web/`.
9. Con Railway verificado, suspender el servicio de Render (*Settings > Suspend*) para que no haya dos APIs publicadas. Ambas leen las mismas bases, así que no hay datos que migrar.

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
INGESTION_SYNC=true uvicorn mia.api.main:app --env-file .env.produccion --port 8010
```

Ojo al copiar la URL de Neon en `DATABASE_URL`: debe empezar con `postgresql://` (si se editó la línea de SQLite, verificar que no quede un prefijo `sqlite:`). Con `Connection pooling` desactivado en el diálogo *Connect* de Neon.

**Carga de una carpeta completa (recomendado):** `scripts/cargar_carpeta.py` crea el dominio si no existe y sube todos los PDF, DOCX y TXT de una o varias carpetas (con subcarpetas), uno a la vez, informando el estado de cada uno:

```bash
python scripts/cargar_carpeta.py --url http://localhost:8010 \
  --dominio "Analítica de Negocios: Consejo de Área" \
  --descripcion "Actas del Consejo de Área Académica" \
  "tmp/Información_analítica_de_negocios/ACTAS"
```

`--excluir <texto>` omite los archivos cuyo nombre contenga ese texto (p. ej. un PDF escaneado sin texto). Los comandos exactos de la carga actual están en "Datos cargados" ([PRUEBAS_MVP.md](PRUEBAS_MVP.md)).

**Carga manual de un documento**, en `http://localhost:8010/docs`:

1. `GET /domains` para ver si el dominio ya existe; si no, `POST /domains` con `{"name": "Memoria del Consejo", "description": "..."}`. Guardar el `id`.
2. `POST /domains/{id}/documents` con cada archivo (PDF, DOCX o TXT). Responde enseguida con estado `pending`.
3. `GET /domains/{id}/documents` hasta que todos estén en `done`. Como referencia, un acta de ~180 páginas (~540 fragmentos) tarda unos minutos en una laptop.
4. Probar una consulta en Render (`POST /query` con `{"domains": ["<id>"], "question": "..."}`).

Subir dos veces el mismo archivo al mismo dominio no duplica nada: devuelve el documento existente.

Si un documento queda en `error`, ver el log de la API local (el mensaje empieza con "Fallo indexando documento"). Un documento que quedó en `processing` porque se cortó la API no se reintenta solo; hoy la forma de reintentar es borrar esa fila en Neon y sus puntos en Qdrant (filtro `document_id`) y volver a subir el archivo.

## Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Render se reinicia con "Out of memory" | Se ingirió en Render, o se cambió a un modelo más pesado | Mantener `INGESTION_ENABLED=false` en Render e ingerir localmente |
| La primera consulta tarda ~1 min | Render free se durmió tras 15 min sin tráfico | Normal. Opcional: un monitor gratuito (UptimeRobot, cron-job.org) que llame a `/health` cada 10 min |
| La API no arranca: "La colección ... tiene vectores de dimensión X" | Se cambió `EMBEDDING_PROVIDER` sin cambiar `QDRANT_COLLECTION` | Usar la colección que corresponde al proveedor, o reindexar |
| Error de conexión a Qdrant | El clúster free se suspendió tras 1 semana sin uso | Reactivarlo desde el panel de Qdrant Cloud |
| `/query` responde 502 tras ~2 min | Gemini saturado (503 "high demand", frecuente en el tier gratuito) o cuota agotada | Esperar unos minutos y reintentar; revisar la cuota en Google AI Studio. El proveedor corta tras 3 intentos para no dejar la consulta colgada |
| `/query` responde 500 y el log de Qdrant dice "Index required but not found for \"domain\"" | La colección se creó sin índices de payload (Qdrant Cloud los exige para filtrar) | Reiniciar la API: `ensure_collection()` crea los índices al arrancar |
| La respuesta es correcta pero incompleta ("el fragmento se interrumpe...") | La sección o lista ocupa más fragmentos de los que se recuperan | Verificar `QUERY_SEARCH_LIMIT` (8) y `QUERY_CONTEXT_NEIGHBORS` (1) en Render; subir los vecinos a 2 si el documento tiene secciones muy largas |
| Responde "no encontré información" a preguntas que sí tienen respuesta | El umbral es demasiado alto, o la instrucción del LLM es demasiado estricta | Revisar `QUERY_SIMILARITY_THRESHOLD` y `RAG_SYSTEM_PROMPT` (ver `specs/001-pipeline-ingesta-rag/research.md`) |

## Datos y privacidad

- Desde el 2026-10-06 MIA tiene documentos reales entregados por la Unidad de Posgrado en Computación (Mauricio Arroyo) y la Maestría en Analítica de Negocios (Martín Solís), en lugar de los datos de prueba del MVP (actas públicas del Consejo Institucional). Los archivos viven en `tmp/`, que está en `.gitignore`: **no se versionan documentos en el repositorio**.
- **No se cargaron las actas del Consejo de la Unidad de Posgrado en Computación** (20 actas de 2025): incluyen nombres de estudiantes con número de carné, cédulas, notas, becas y temas de salud, y con el LLM gratuito esos fragmentos se enviarían a Google. Quedan pendientes de un LLM que no use los datos o de una autorización explícita. Las actas de Analítica de Negocios sí se cargaron: tratan temas del programa (becas como política, presupuesto, admisión), sin datos de estudiantes; la única cédula es la de su coordinador en su designación ante FUNDATEC.
- El LLM recibe fragmentos de las actas en cada consulta. En el tier gratuito de Gemini, Google puede usar esos datos; antes de cargar actas no públicas, pasar a un plan pago o a un LLM local (ver [ESCALABILIDAD.md](ESCALABILIDAD.md)).
- La API no tiene autenticación: cualquiera con la URL de Render puede consultar. No publicar la URL fuera del equipo.
