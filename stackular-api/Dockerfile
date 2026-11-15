# Backend image for a Hugging Face Docker Space (also runs anywhere Docker does).
FROM python:3.12-slim

# HF Spaces run containers as uid 1000; give that user a writable home for the model cache.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# CPU-only torch first: the default Linux wheel drags in GBs of CUDA libraries a CPU Space can't use.
RUN pip install --no-cache-dir --user torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Bake the embedding model into the image so a cold start doesn't download it.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en')"

COPY --chown=user main.py rag.py ./

# Keys come from the Space's Secrets (env vars), not a .env file.
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
