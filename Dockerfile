FROM python:3.12-slim

WORKDIR /app

ENV HF_HOME=/app/.hf_cache

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

# Descarga el modelo de embeddings en el build para que el arranque en frío no dependa de HuggingFace.
RUN python -c "from mia.rag.providers.local_embeddings import download_model_files; download_model_files()"

CMD ["uvicorn", "mia.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
