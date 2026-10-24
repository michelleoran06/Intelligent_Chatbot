# Imagen única para los tres servicios (backend, chat y panel); cada uno cambia el comando.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATA_DIR=/app/data

WORKDIR /app

# libgomp1: requerida por onnxruntime (modelo de embeddings de ChromaDB)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Descarga el modelo de embeddings al construir la imagen y no en la primera petición (Sección 18.2)
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; DefaultEmbeddingFunction()(['precarga del modelo'])"

COPY . .
RUN mkdir -p /app/data

EXPOSE 8000 8501 8502
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
