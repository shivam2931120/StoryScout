# One image and one URL: React is built once; FastAPI serves it and the NLP API.
FROM node:24-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/artifacts/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=2 \
    STORYSCOUT_RETRIEVAL_MODE=hybrid \
    STORYSCOUT_USE_NVIDIA=false \
    PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements-api.txt requirements-semantic.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt
RUN useradd --create-home --uid 10001 scout && mkdir -p /app/artifacts && chown scout:scout /app/artifacts
COPY src/ ./src/
COPY scripts/build_indexes.py ./scripts/build_indexes.py
COPY scripts/train_text_genres.py ./scripts/train_text_genres.py
COPY data/ ./data/
RUN python scripts/train_text_genres.py && chown -R scout:scout /app/artifacts
USER scout
# Public model and indexes are prepared in the image, not committed to Git.
# RetrievalIndex supports a transparent TF-IDF fallback if semantic setup fails.
RUN python scripts/build_indexes.py
COPY api/ ./api/
COPY artifacts/evaluation_results.json artifacts/evaluation_summary.md artifacts/evaluation_query_results.csv artifacts/genre_classifier_results.json ./artifacts/
COPY artifacts/search_tuning/ ./artifacts/search_tuning/
COPY --from=frontend /web/dist ./frontend/dist/
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/ready',timeout=4)"
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
