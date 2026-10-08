from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "mia_chunks"

    database_url: str = "sqlite:///./mia.db"

    embedding_provider: str = "local"
    llm_provider: str = "local"

    anthropic_api_key: str = ""
    anthropic_effort: str = "medium"

    gemini_api_key: str = ""

    openrouter_api_key: str = ""
    # Id del modelo en OpenRouter (openrouter.ai/models), p. ej. el de Gemini Flash-Lite o GLM 5.3.
    openrouter_model: str = ""
    # Esfuerzo de razonamiento: none, minimal, low, medium, high (vacío: el del modelo).
    # Algunos modelos razonan siempre y rechazan "none": para el modo sin razonamiento usar "low".
    openrouter_reasoning_effort: str = ""
    # Máximo de tokens de respuesta (incluido el razonamiento). Acota el costo de cada consulta; sin
    # él OpenRouter reserva saldo para la salida máxima del modelo y rechaza consultas con poco saldo.
    openrouter_max_tokens: int = 8000
    # Solo proveedores de retención cero de datos (necesario con información sensible).
    openrouter_zdr: bool = False

    glm_api_key: str = ""
    # Razonamiento antes de responder: mejora preguntas que combinan datos (p. ej. sumar créditos
    # de varios cursos) a cambio de más latencia y tokens de salida.
    glm_thinking: bool = True

    query_similarity_threshold: float = 0.8
    query_search_limit: int = 8
    # Fragmentos anteriores y posteriores que se suman a cada resultado relevante, para no cortar
    # listas o secciones que ocupan varios fragmentos (ver src/mia/rag/context.py).
    query_context_neighbors: int = 1
    # Documentos de hasta esta cantidad de fragmentos (~800 caracteres nuevos cada uno) se pasan
    # completos al LLM si alguno de sus fragmentos es relevante. 0 lo desactiva.
    query_full_document_max_chunks: int = 12

    # En Render free (512 MB) ingerir actas grandes agota la memoria: allí se desactiva y la ingesta
    # se hace desde una instancia local apuntando a las mismas bases (ver docs/OPERACION.md).
    ingestion_enabled: bool = True
    # Ingerir dentro de la misma petición en vez de en segundo plano. Necesario en Cloud Run con
    # cobro por petición: al responder se frena la CPU y una tarea en segundo plano no avanza.
    ingestion_sync: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
