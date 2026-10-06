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

## Despliegue en Cloud Run (en preparación, 2026-10-06)

Reemplazo previsto de Render free. Motivos y alternativas comparadas en [ESCALABILIDAD.md](ESCALABILIDAD.md), sección "Migración a Cloud Run". Neon y Qdrant Cloud no cambian.

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

## Cargar actas (ingesta)

La ingesta no se hace en Render (512 MB no alcanzan para actas de más de ~100 páginas; `POST /domains/{id}/documents` responde 503 allí). Se hace desde una máquina local con la misma API:

```bash
source .venv/bin/activate
# .env.produccion (ignorado por git) con las credenciales de producción:
#   DATABASE_URL=<Neon>, QDRANT_URL=<Qdrant Cloud>, QDRANT_API_KEY=<...>,
#   EMBEDDING_PROVIDER=local, QDRANT_COLLECTION=mia_chunks, INGESTION_ENABLED=true
# --env-file carga esas variables antes de arrancar y tienen prioridad sobre las de .env.
# (No usar `source .env.produccion`: la URL de Neon contiene "&" y el shell la corta.)
uvicorn mia.api.main:app --env-file .env.produccion --port 8010
```

Ojo al copiar la URL de Neon en `DATABASE_URL`: debe empezar con `postgresql://` (si se editó la línea de SQLite, verificar que no quede un prefijo `sqlite:`). Con `Connection pooling` desactivado en el diálogo *Connect* de Neon.

Luego, en `http://localhost:8010/docs`:

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

- Las actas cargadas en la prueba del MVP (sesiones 3436 a 3438 del Consejo Institucional del TEC) son públicas. Los archivos de prueba viven en `tmp/`, que está en `.gitignore`: **no se versionan documentos en el repositorio**.
- El LLM recibe fragmentos de las actas en cada consulta. En el tier gratuito de Gemini, Google puede usar esos datos; antes de cargar actas no públicas, pasar a un plan pago o a un LLM local (ver [ESCALABILIDAD.md](ESCALABILIDAD.md)).
- La API no tiene autenticación: cualquiera con la URL de Render puede consultar. No publicar la URL fuera del equipo.
