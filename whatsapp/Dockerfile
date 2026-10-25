# Servicio del bot de WhatsApp (feature 011): recibe los avisos de Kapso, consulta a la API de MIA y responde.
# Imagen pequeña a propósito: no incluye el paquete `mia` (ni onnxruntime, Qdrant ni el modelo de embeddings), solo
# FastAPI, uvicorn, httpx y pydantic-settings. Se publica como servicio de Railway con Root Directory `whatsapp`.
FROM python:3.12-slim

# Usuario sin privilegios (uid 1000, como la imagen de la API).
RUN useradd -m -u 1000 user

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

USER user

# Railway define el puerto en la variable PORT; sin ella (local, docker run) se usa 8000. La aplicación se crea con una
# fábrica (`--factory`): la configuración se lee al arrancar y, si falta una variable obligatoria, el servicio no arranca
# y el mensaje nombra la variable.
CMD ["sh", "-c", "uvicorn mia_whatsapp.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
