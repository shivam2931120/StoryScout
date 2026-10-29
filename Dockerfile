# Free-tier image: one service, local quantized semantic NLP, no PyTorch runtime.
FROM node:24-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim-bookworm AS nlp
WORKDIR /app
ENV PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements-free.txt ./
RUN pip install --no-cache-dir -r requirements-free.txt
COPY src/ ./src/
COPY scripts/train_text_genres.py scripts/prepare_compact_catalog.py scripts/prepare_onnx_model.py scripts/build_indexes.py ./scripts/
COPY data/ ./data/
# Training uses the source corpus; the hosted subset is selected afterwards.
RUN mkdir -p artifacts && python scripts/train_text_genres.py && python scripts/prepare_compact_catalog.py && python scripts/prepare_onnx_model.py
ENV STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx
RUN python scripts/build_indexes.py && python -c "import json; from pathlib import Path; assert all(json.loads(p.read_text())['embeddings_cached'] and json.loads(p.read_text()).get('passage_embeddings_cached') is not False for p in Path('artifacts').glob('*_index_meta.json')), 'Semantic preparation failed'"

FROM python:3.14-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MALLOC_ARENA_MAX=2 \
    STORYSCOUT_RETRIEVAL_MODE=hybrid STORYSCOUT_USE_NVIDIA=false \
    STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 scout
COPY --from=nlp /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/
COPY --from=nlp /usr/local/bin/ /usr/local/bin/
COPY --from=nlp /app/src/ ./src/
COPY --from=nlp --chown=scout:scout /app/artifacts/ ./artifacts/
COPY --from=nlp /app/data/compact/ ./data/compact/
COPY data/evaluation_queries.json data/preference_evaluation.json ./data/
COPY api/ ./api/
COPY artifacts/evaluation_results.json artifacts/evaluation_summary.md artifacts/evaluation_query_results.csv artifacts/genre_classifier_results.json ./artifacts/
COPY artifacts/search_tuning/ ./artifacts/search_tuning/
COPY artifacts/compact/ ./artifacts/compact/
COPY artifacts/passages/ ./artifacts/passages/
COPY --from=frontend /web/dist ./frontend/dist/
USER scout
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s CMD curl --fail --silent --max-time 4 "http://127.0.0.1:${PORT:-8000}/api/ready" > /dev/null
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
