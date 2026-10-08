# Escalabilidad: de prototipo a producción

El despliegue actual (ver [OPERACION.md](OPERACION.md)) está optimizado para costo cero durante la vigencia del prototipo (aprox. dos meses desde 2026-09-27). Este documento reúne lo que habría que cambiar para llevar MIA a producción y lo que ya se probó y descartó, con las mediciones que motivaron cada decisión, para que quien continúe no repita el camino.

La escala esperada es la de una Unidad académica: cientos o pocos miles de actas y pocas consultas simultáneas. El reto no es el volumen de tráfico, sino que los datos persistan, que la ingesta no afecte a la API y que se puedan sumar dominios y artefactos (Coordinación, WhatsApp, web) sin rediseñar.

## Limitaciones del prototipo actual

| Limitación | Consecuencia |
|---|---|
| API en Render free con 512 MB | No puede ingerir actas grandes; la ingesta se hace a mano desde una máquina local. |
| Render free se duerme tras 15 min | Primera consulta lenta (30-60 s). |
| Ingesta dentro del proceso de la API (`BackgroundTasks` + lock) | Solo funciona con una instancia; un reinicio a mitad de ingesta deja documentos en `processing` sin reintento. |
| Archivos originales solo en la máquina de quien ingiere | Reindexar (p. ej. al cambiar de modelo) requiere conseguir de nuevo los archivos. |
| Qdrant Cloud free se suspende tras 1 semana sin uso | Requiere reactivarlo a mano. |
| Gemini free como LLM | Cuotas diarias, saturación frecuente del modelo (503 "high demand", observado el 2026-09-28 durante más de 10 minutos), y Google puede usar los datos enviados. No apto para actas no públicas. |
| Sin autenticación | Cualquiera con la URL puede consultar. |
| Sin migraciones de base (`create_all`) | Cambiar el esquema de `Domain`/`Document` requiere intervención manual. |

## Arquitectura recomendada para producción

| Pieza | Recomendación | Por qué |
|---|---|---|
| **API** | Contenedor con 1-2 GB de RAM y al menos una instancia siempre encendida. Opción sugerida: Google Cloud Run (mismo Dockerfile, misma cuenta y facturación que Gemini). Alternativa: plan pago de Render con 2 GB. | Sin suspensión, y memoria suficiente para el modelo de embeddings local con margen. |
| **Metadata** | Postgres administrado (Neon pago, Cloud SQL o el de Render). Agregar Alembic para migraciones. | El código ya es compatible con Postgres (SQLAlchemy); solo cambia `DATABASE_URL`. |
| **Archivos originales** | Almacenamiento de objetos (Cloud Storage, S3 o equivalente). | Sobreviven a redeploys y permiten reindexar sin pedir los archivos otra vez. |
| **Ingesta** | Worker separado de la API: Cloud Run Jobs o una cola (Cloud Tasks, RQ, Celery). | Es lo que causó los OOM del prototipo. Separada, la API queda liviana y puede escalar a varias instancias, y las ingestas fallidas se reintentan. Ya estaba prevista como extensión en `specs/001-pipeline-ingesta-rag/research.md`. |
| **Embeddings** | Mantener el modelo local e5-small en ONNX, ahora con memoria suficiente. | Sin cuota ni costo por fragmento (reindexar todo es gratis), sin riesgo de que el proveedor retire el modelo y obligue a reindexar, umbral estable, y el texto completo de las actas no sale a un tercero (coherente con el Principio III de la constitución). `GeminiEmbeddingProvider` queda implementado como alternativa. |
| **Vectores** | Qdrant Cloud en plan pago cuando se supere el free (1 GB) o se necesite que no se suspenda. Alternativa a evaluar: `pgvector` en el mismo Postgres, para tener un componente menos. | La interfaz `VectorStore` permite cambiar sin tocar el resto. |
| **LLM** | Gemini pago o Anthropic (`AnthropicLLMProvider` ya implementado), y a futuro un LLM local cuando haya hardware (meta declarada del proyecto). | Sin cuotas del tier gratuito y con condiciones de uso de datos aptas para información institucional. |
| **Acceso** | API key por artefacto (Coordinación, WhatsApp, web), y permisos por dominio. | Pendiente de la sección 10 de `Definicion_Requerimientos_MVP.md`; necesario antes de exponer cualquier artefacto. |

Costo orientativo: del orden de USD 20 a 60 al mes en total (API siempre encendida, Postgres chico, almacenamiento, LLM pago con el volumen de una Unidad). Los precios cambian: verificar con las calculadoras de cada proveedor antes de decidir.

Antes de elegir proveedor conviene consultar con TI de la institución si ya existe un convenio con alguna nube (Google, Microsoft, AWS): puede abaratar costos y facilitar la aprobación de almacenar actas fuera de la institución, que es una decisión de gobernanza de datos además de técnica.

### Orden sugerido

1. Postgres pago o con respaldo + almacenamiento de objetos para los archivos (persistencia completa).
2. API en un host con 1-2 GB, manteniendo embeddings locales; volver a habilitar la ingesta por API.
3. Separar la ingesta en un worker con reintentos.
4. Autenticación por artefacto.
5. LLM con plan pago o local, según la sensibilidad de los dominios que se agreguen.
6. Recalibrar `QUERY_SIMILARITY_THRESHOLD` cada vez que se agregue un dominio o cambie el modelo de embeddings.

## Railway y OpenRouter (decisión del 2026-10-07)

Reemplaza a la decisión de Cloud Run de la sección siguiente, que quedó descartada porque Google Cloud pidió un prepago de 30 USD.

- **Hosting: Railway Hobby.** 5 USD al mes con 5 USD de uso incluido, cobro por segundo (unos 10 USD por GB de RAM al mes). MIA consume unos 4 a 4.5 USD, así que en la práctica cuesta 5 USD fijos. Sin límite de 512 MB (la ingesta vuelve al servidor), no se duerme, y tiene un límite duro de gasto que apaga los servicios al alcanzarlo, que era la condición para aceptar un cobro por uso. Frente a Render Standard (25 USD por 2 GB) resuelve lo mismo por la quinta parte; frente a Hetzner (precio fijo similar) evita administrar un servidor, que importa para el traspaso.
- **Modelos: OpenRouter.** Una sola cuenta de saldo prepagado (el saldo es el tope) y una sola clave para Gemini, GLM y otros, con la API compatible con OpenAI (`OpenRouterLLMProvider`). No recarga el precio de los modelos; cobra 5.5 % al cargar saldo. Frente a contratar directo (p. ej. GLM 5.3 en DeepInfra, algo más barato) suma esa comisión y un intermediario más en el camino de los datos, a cambio de tener modelos cerrados y abiertos en la misma cuenta. Cada consulta excluye proveedores que entrenan con los datos (`data_collection: deny`); con información sensible hay que activar además `OPENROUTER_ZDR=true` (solo proveedores de retención cero) y contar con la aprobación institucional.
- **Presupuesto de un mes de evaluación con usuarios:** unos 15 a 17 USD (5 de Railway y 10 a 12 de modelos para unas 1000 consultas).

## Migración a Cloud Run (decisión del 2026-10-06, descartada el 2026-10-07)

Con un presupuesto chico disponible se volvió a comparar el hosting de la API, ya sin la restricción de costo cero y sin tarjeta que llevó a Render free. Precios consultados en octubre de 2026:

| Opción | Costo/mes aprox. | Por qué no / por qué sí |
|---|---|---|
| Render Starter / Standard | 7 / 25 USD fijos | Lo más simple, pero Starter mantiene 512 MB (sin ingesta en el servidor). |
| Railway Hobby | 5 a 10 USD según uso | Despliegue simple; cobro por uso de RAM y CPU. |
| Fly.io | 6 a 11 USD | Similar a Railway, con precio fijo por máquina. |
| Hetzner VPS | ~5.50 EUR fijos | El más barato con 4 GB, pero hay que administrar el servidor: peor para el traspaso. |
| Vercel Hobby | 0 USD | Serverless: la ingesta en segundo plano requiere reescribirse y FastAPI necesita adaptar el despliegue. Encaja mejor para el cliente web. |
| **Google Cloud Run** | **~0 USD con el uso del piloto** | **Elegido.** Mismo Dockerfile, ingesta en el servidor, sin la espera de 30-60 s de Render. |

El riesgo de Cloud Run es el cobro variable: no tiene tope directo. Se acota con un máximo de 1 instancia (peor caso ~2 USD por día) y un corte automático de la facturación al llegar a un presupuesto de 3 USD. Detalle y pasos en [OPERACION.md](OPERACION.md), sección "Despliegue en Cloud Run".

En la misma decisión se eligió **GLM 5.3** (Z.ai) como LLM: 1.40 / 4.40 USD por millón de tokens de entrada / salida, más barato que Claude Sonnet 5.5 (2 / 10), con razonamiento y llamadas a herramientas. La API de Z.ai es compatible con la de OpenAI (`GLMLLMProvider`). Con el volumen del piloto (cientos de consultas al mes) el gasto esperado es de pocos dólares.

Pendiente aparte del hosting: las preguntas de agregación sobre muchos documentos (p. ej. "¿cuántos créditos suman todos los cursos?") hoy responden "sin información" porque la búsqueda no recupera fragmentos de todos los documentos, no por el LLM. Resolverlas requiere recuperación con herramientas (el LLM decide qué buscar) o extraer al ingerir datos estructurados como créditos y horas.

## Qué se probó y se descartó (2026-09-27)

Registro para no repetir caminos ya recorridos. Mediciones hechas con las actas 3436, 3437 y 3438 del Consejo Institucional del TEC (96, 180 y 113 páginas; 1189 fragmentos en total).

| Intento | Resultado | Detalle |
|---|---|---|
| `sentence-transformers` (PyTorch) en Render free | Descartado | Importar la librería ya ocupa ~715 MB; con el modelo cargado ~1.2 GB. El deploy moría por falta de memoria. |
| e5-small en ONNX fp32 | Descartado | ~890 MB con el modelo cargado. |
| e5-small en ONNX int8 + tokenizador `tokenizers` (Rust) de HuggingFace | Descartado | El tokenizador solo ocupaba ~286 MB (vocabulario de 250k). |
| e5-small en ONNX int8 + `sentencepiece` | **Adoptado** | ~340 MB la API en reposo. Vectores con similitud coseno ~0.995 frente al modelo original. |
| Ingesta en Render free con ONNX int8 | Descartado | Picos de 460-520 MB con actas de ~500 fragmentos; muerte por OOM en una prueba con Docker limitado a 512 MB, incluso ingiriendo de a un documento y en lotes. |
| Hugging Face Spaces (Docker, CPU basic) | Descartado | Desde 2026 los Spaces Docker en CPU gratuita requieren suscripción PRO (error 402 al crearlo). |
| `gemini-embedding-001` en tier gratuito | Descartado para el despliegue | Límite de 1000 textos por día (`embed_content_free_tier_requests`); cada fragmento cuenta como uno aunque se envíen en lotes. Las 3 actas de prueba ya superan un día de cuota. Con facturación habilitada costaría centavos, por lo que es viable en producción si se prefiere no alojar el modelo. |
| `gemini-embedding-2` | Descartado | Es multimodal: combina todos los textos de una llamada en un único embedding, en lugar de devolver uno por texto. |

Otras alternativas evaluadas sin probar: Google Cloud Run y Oracle Cloud Always Free (requieren tarjeta), Koyeb free (mismo límite de 512 MB), Railway (solo crédito de prueba; adoptada el 2026-10-07 al aceptar un gasto acotado, ver arriba).
