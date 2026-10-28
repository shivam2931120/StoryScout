# Free deployment: React + FastAPI + local semantic NLP

Live and verified: https://storyscout-eaw7.onrender.com. Service ID: `srv-dbh16getlv9c73dk5jhg`; plan: `free`. See FREE_HOSTING.md for actual checks.

The root Dockerfile and `render.yaml` target Render's **free** web-service plan.
One container serves React and the Python API. No API key, payment method,
external inference endpoint, database, or separate frontend host is required.

## What fits the free profile

The source repository keeps the full catalog and research experiments. The
container loads a deterministic subset of **1,000 books and 1,500 movies**.
`prepare_compact_catalog.py` preserves demo/reference titles, prioritizes known
movie runtimes and plot text, then uses stable hashes. It never fabricates data.

Semantic search runs the official quantized ONNX export of the pretrained
`sentence-transformers/all-MiniLM-L6-v2` model. It retains the original tokenizer,
256-token truncation, masked mean pooling and normalized 384-dimensional vectors.
TF-IDF, local genre predictions, mood/theme signals, hard filters, MMR and
conversation state remain in Python. The full local setup can still use Sentence
Transformers/PyTorch; the free image does not load PyTorch.

The public model, compact data, TF-IDF indexes and embeddings are prepared during
Docker build. Normal startup and requests do not download models or call a chat
API. Model/cache files are excluded from Git. The runtime is a non-root user.

## Terminal deployment

```bash
cd /home/shivam/StoryScout
# Run tests and build/test the image before publishing:
.venv/bin/python -m pytest -q
docker build -t storyscout:free .
docker run -d --name storyscout-free-check --memory=512m --memory-swap=512m \
  -p 8001:8000 storyscout:free
.venv/bin/python scripts/verify_api.py --base-url http://127.0.0.1:8001 \
  --output artifacts/free_container_verification.json

# Authenticate once if these CLIs are not already connected:
gh auth login
render login

# Push reviewed application files; keys, caches and design.zip are ignored.
git add .
git commit -m "Deploy StoryScout with compact local semantic NLP"
git push origin main

render blueprints validate render.yaml --output json
render services create --name storyscout --type web_service --runtime docker \
  --repo https://github.com/shivam2931120/StoryScout --branch main \
  --region singapore --plan free --num-instances 1 \
  --health-check-path /api/ready \
  --env-var STORYSCOUT_RETRIEVAL_MODE=hybrid \
  --env-var STORYSCOUT_USE_NVIDIA=false \
  --env-var STORYSCOUT_CATALOG_PROFILE=compact \
  --env-var STORYSCOUT_EMBEDDING_BACKEND=onnx --confirm --output json
```

Record the returned service ID and URL. Deploys are created automatically from
`main`. Inspect with `render deploys list SERVICE_ID --output json` and
`render logs --resources SERVICE_ID --limit 50 --output json`. Verify the public
URL using `scripts/verify_api.py --base-url YOUR_URL`. Do not create a second
service on each update; push to `main` or trigger `render deploys create` for the
existing service.

The service's Docker command stays empty so its image command binds to
`0.0.0.0:$PORT`. Readiness is `/api/ready`, which returns 200 after indexes load.

## Reproduce compact preparation locally

```bash
.venv/bin/python -m pip install -r requirements-free.txt
.venv/bin/python scripts/prepare_compact_catalog.py
.venv/bin/python scripts/prepare_onnx_model.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx \
  .venv/bin/python scripts/build_indexes.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx \
  .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

React is built with `npm ci && npm run build` from `frontend/`. The container
builds it automatically. To run the full local catalog and PyTorch encoder,
install `requirements-api.txt` and leave both profile/backend variables unset.
The free image bundles only the compact catalog; changing its profile to full
is not supported by that image.

## Evaluation and limits

Full-catalog and compact-profile evaluation results are stored separately.
The hosted Evaluation page uses `artifacts/compact/` when available. The plot
classifier's held-out report remains an experiment on the larger source corpus;
it is not a claim of accuracy for every recommendation.

Free services can sleep when idle, have limited CPU/RAM, and can take time to
wake. No uptime or multi-user performance guarantee is made. Browser conversations
and bookmarks stay in each device's localStorage. Missing book page counts and
unknown warning labels remain limitations. The UI reports actual active modes;
a model-loading failure is shown as TF-IDF fallback, never semantic retrieval.

Official references: [Render Docker](https://render.com/docs/docker),
[free services](https://render.com/docs/free),
[health checks](https://render.com/docs/health-checks),
[MiniLM model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
[ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html).
