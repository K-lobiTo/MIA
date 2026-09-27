# Arquitectura de MIA

Documentación viva de cómo está implementado el sistema, para que cualquier desarrollador (humano o Claude Code) pueda orientarse sin releer todo el código. Se actualiza cada vez que cambia algo relevante de la arquitectura; para el "por qué" de las decisiones de alcance, ver [Definicion_Requerimientos_MVP.md](Definicion_Requerimientos_MVP.md).

## Concepto en una frase

Una API intermediaria (FastAPI) desacopla el almacenamiento (dominios de conocimiento en Qdrant + metadata en SQLite) de los "artefactos" de consulta (chatbots, interfaces internas) que la usarán más adelante. Cada pieza del pipeline (loader de documentos, embeddings, LLM, base vectorial) es una interfaz intercambiable seleccionable por configuración, no código hardcodeado.

## Estructura del código

```
src/mia/
├── config.py          Settings (pydantic-settings, lee .env)
├── api/
│   ├── main.py         App FastAPI, arma los routers, init_db() en el lifespan
│   └── routes/         health.py, domains.py, query.py
├── ingestion/
│   ├── loaders/        DocumentLoader (interfaz) + PdfLoader/DocxLoader/TxtLoader
│   └── chunker.py       chunk_text(): split con overlap, sin dependencias externas
├── rag/
│   ├── embeddings.py    EmbeddingProvider (interfaz) + get_embedding_provider(name)
│   ├── llm.py           LLMProvider (interfaz) + get_llm_provider(name)
│   └── providers/       una implementación por proveedor (local, openai, anthropic)
└── storage/
    ├── db.py            engine/session de SQLAlchemy (SQLite)
    ├── models.py        Domain, Document (metadata)
    └── vector_store.py  VectorStore (interfaz) + QdrantVectorStore + get_vector_store()
```

## El patrón que se repite: interfaz + factory por nombre

`DocumentLoader`, `EmbeddingProvider`, `LLMProvider` y `VectorStore` siguen el mismo patrón: una clase abstracta define el contrato, cada implementación concreta vive en su propio archivo, y una función `get_x(name)` hace el dispatch leyendo `settings` (que a su vez lee `.env`). Para agregar un proveedor nuevo (otro LLM, otro loader), se agrega una clase que implemente la interfaz y una rama en el factory correspondiente; no se toca el resto del sistema. Este es el mecanismo concreto detrás del requerimiento de "poder cambiar partes del pipeline sin que interfiera con el resto" (sección 3 de Definicion_Requerimientos_MVP.md).

## Por qué una sola colección de Qdrant

`QdrantVectorStore` usa una única colección (`mia_chunks`) con `domain` como campo de payload filtrable, en lugar de una colección por dominio. Esto permite filtrar por uno o varios dominios en la misma consulta (necesario para casos de uso que cruzan dominios) y agregar dominios nuevos sin crear infraestructura nueva. El trade-off aceptado: cambiar de modelo de embeddings con otra dimensionalidad requeriría migrar o versionar la colección.

## Qué funciona hoy vs. qué es interfaz sin implementar

**Funciona (probado con tests y en producción en Render):**
- CRUD básico de dominios y documentos (`/domains`, `/domains/{id}/documents`), con deduplicación por hash de archivo.
- `PdfLoader`, `DocxLoader`, `TxtLoader`: extracción real de texto.
- `chunk_text()`: chunking con overlap.
- Metadata store (SQLite + SQLAlchemy), inicializado automáticamente al arrancar la API.

**Interfaz definida, implementación pendiente (lanzan `NotImplementedError` a propósito, no es un bug):**
- Todos los `EmbeddingProvider` y `LLMProvider` concretos (`local`, `openai`, `anthropic`).
- `QdrantVectorStore.upsert()` / `.search()` (el cliente sí se conecta; falta la lógica).
- El endpoint `/query` (espera a que exista un `LLMProvider` real que consumir).

Cuando se implemente cualquiera de estos, actualizar esta sección.

## Despliegue

- **Desarrollo local:** `docker-compose.yml` levanta Qdrant local + la API con hot-reload.
- **Demo compartida / producción:** `render.yaml` (Blueprint de Render) despliega la API; Qdrant corre en Qdrant Cloud (clúster free tier, región N. Virginia en AWS). La API se conecta a uno u otro solo cambiando `QDRANT_URL`/`QDRANT_API_KEY` en `.env` (local) o en las variables de entorno de Render (producción): el código no cambia.

## Convenciones del proyecto

- Documentación, nombres de dominio/conceptos y mensajes de commit en español (el resto del proyecto, incluida la definición conceptual original, está en español).
- No usar guión largo (—) en ningún documento o texto generado para este proyecto (ver CLAUDE.md).
