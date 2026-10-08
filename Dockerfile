FROM python:3.12-slim

# Usuario sin privilegios (uid 1000, también el que exigen plataformas como Hugging Face Spaces).
RUN useradd -m -u 1000 user

WORKDIR /app

ENV HF_HOME=/app/.hf_cache
# Menos arenas de malloc por hilo: evita que la memoria se fragmente y crezca al ingerir.
ENV MALLOC_ARENA_MAX=2

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# Descarga el modelo de embeddings en el build; en ejecución se usa solo la copia local.
RUN python -c "from mia.rag.providers.local_embeddings import download_model_files; download_model_files()"
ENV HF_HUB_OFFLINE=1

# SQLite (mia.db) y uploads/ se escriben en /app.
RUN chown -R user:user /app
USER user

# Railway y Render asignan el puerto en la variable PORT; sin ella (local, docker compose) se usa 8000.
CMD ["sh", "-c", "uvicorn mia.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
