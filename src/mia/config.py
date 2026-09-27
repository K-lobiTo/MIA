from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "mia_chunks"

    database_url: str = "sqlite:///./mia.db"

    embedding_provider: str = "local"
    llm_provider: str = "local"

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
