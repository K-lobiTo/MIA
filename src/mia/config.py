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

    query_similarity_threshold: float = 0.8
    query_search_limit: int = 8
    # Fragmentos anteriores y posteriores que se suman a cada resultado relevante, para no cortar
    # listas o secciones que ocupan varios fragmentos (ver src/mia/rag/context.py).
    query_context_neighbors: int = 1

    # En Render free (512 MB) ingerir actas grandes agota la memoria: allí se desactiva y la ingesta
    # se hace desde una instancia local apuntando a las mismas bases (ver docs/OPERACION.md).
    ingestion_enabled: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
