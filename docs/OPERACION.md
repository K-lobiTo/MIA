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
| `INGESTION_ENABLED` | `true` | `false` | `true` |
| `QUERY_SIMILARITY_THRESHOLD` | ver `.env.example` | igual | no se usa al ingerir |

Regla importante: **Render y la instancia que ingiere deben usar el mismo `EMBEDDING_PROVIDER` y la misma `QDRANT_COLLECTION`**. Si no, las preguntas se embeben con un modelo distinto al de los documentos y la búsqueda devuelve basura (o la API no arranca por diferencia de dimensión).

## Puesta en marcha desde cero

1. **Qdrant Cloud:** crear un clúster free, copiar su URL y una API key.
2. **Neon:** crear un proyecto free, copiar la *connection string* (`postgresql://...?sslmode=require`). La API crea las tablas sola al arrancar.
3. **Gemini:** crear una API key en [Google AI Studio](https://aistudio.google.com).
4. **Render:** *New → Blueprint*, apuntar al repositorio; Render lee `render.yaml`. Completar los secretos marcados como `sync: false`: `QDRANT_URL`, `QDRANT_API_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`.
5. Verificar: `GET https://<servicio>.onrender.com/health` debe responder `{"status":"ok"}`.

Cada push a `main` redeploya Render automáticamente.

## Cargar actas (ingesta)

La ingesta no se hace en Render (512 MB no alcanzan para actas de más de ~100 páginas; `POST /domains/{id}/documents` responde 503 allí). Se hace desde una máquina local con la misma API:

```bash
source .venv/bin/activate
# .env.produccion (ignorado por git) con las credenciales de producción:
#   DATABASE_URL=<Neon>, QDRANT_URL=<Qdrant Cloud>, QDRANT_API_KEY=<...>,
#   EMBEDDING_PROVIDER=local, QDRANT_COLLECTION=mia_chunks, INGESTION_ENABLED=true
# Las variables exportadas tienen prioridad sobre las de .env.
set -a && source .env.produccion && set +a
uvicorn mia.api.main:app
```

Luego, en `http://localhost:8000/docs`:

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
| `/query` responde 502 | Gemini no disponible o cuota agotada | Esperar o revisar la cuota en Google AI Studio |
| Las respuestas dicen "no hay información" pero listan fuentes | El umbral de similitud deja pasar fragmentos poco relevantes | Ajustar `QUERY_SIMILARITY_THRESHOLD` (ver `specs/001-pipeline-ingesta-rag/research.md`) |

## Datos y privacidad

- Las actas cargadas en la prueba del MVP (sesiones 3436 a 3438 del Consejo Institucional del TEC) son públicas. Los archivos de prueba viven en `tmp/`, que está en `.gitignore`: **no se versionan documentos en el repositorio**.
- El LLM recibe fragmentos de las actas en cada consulta. En el tier gratuito de Gemini, Google puede usar esos datos; antes de cargar actas no públicas, pasar a un plan pago o a un LLM local (ver [ESCALABILIDAD.md](ESCALABILIDAD.md)).
- La API no tiene autenticación: cualquiera con la URL de Render puede consultar. No publicar la URL fuera del equipo.
