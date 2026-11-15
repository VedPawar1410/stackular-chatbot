# Backend image for Render (free web service, 512 MB RAM); runs anywhere Docker does.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    FASTEMBED_CACHE_PATH=/home/user/.cache/fastembed \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# No torch: embeddings run on fastembed (ONNX), which keeps the image and RAM small.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Bake the embedding model into the image so a cold start doesn't download it.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en')"

COPY --chown=user main.py rag.py ./

# Keys come from the host's environment variables, not a .env file.
# Render injects $PORT (default 10000); fall back to 8000 elsewhere.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
