# Deploy the React + FastAPI application

The main application now uses React/Vite for the interface and the existing
Python NLP engine behind FastAPI. The production build is served by FastAPI
itself. One service hosts the interface, API, catalogs, and model. The previous
Streamlit application remains available as `app.py`, but Streamlit Community
Cloud cannot host this new full application. Your existing Streamlit deployment
will continue to show the Streamlit version until you migrate the link.

## Run locally (tested)

From `/home/shivam/StoryScout`:

```bash
.venv/bin/python -m pip install -r requirements-api.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The same server serves the built React files and
`/api/*`. `/docs` shows the API schema. `/api/health` reports preparing/ready/error;
`/api/ready` returns 200 only after search is ready. The page displays preparation
progress while the public MiniLM model and indexes load.

For frontend development, run `npm run dev` inside `frontend/` in a second
terminal. Open http://127.0.0.1:5173. Vite proxies `/api` to port 8000. Rebuild
with `npm run build` when reviewing production behavior on port 8000. No Node
server is needed in production.

## Container deployment

```bash
docker build -t storyscout .
docker run --rm --name storyscout -p 8000:8000 storyscout
```

The multi-stage Dockerfile builds React, installs CPU Python dependencies,
downloads the public embedding model, prepares indexes in the image, and runs
one Uvicorn worker as a non-root user. No API key is required to build or run.
Do not mount an empty directory over `artifacts/`: that hides the prepared model
and indexes. Weights and caches are excluded from Git and the Docker context;
the public weights downloaded during `docker build` live only in the image.

The container reads `$PORT`, defaulting to 8000. Allocate at least 2GB RAM for
the full catalog and semantic model, then observe your platform's memory
metrics; this is a practical starting point, not a guarantee. One worker avoids
duplicating model memory. If memory is limited, explicitly set
`STORYSCOUT_RETRIEVAL_MODE=tfidf`; this remains lexical NLP retrieval and the UI
accurately reports it. A tiny free instance may not hold the semantic model.

## Render: one web service

1. Commit and push the React/API/Docker changes to your GitHub repository
   `shivam2931120/StoryScout` on `main` (exclude keys, caches, node_modules, and
   design.zip).
2. In Render choose **New → Web Service**, connect GitHub, and select that repo.
3. Select branch `main`, **Docker** as the language/runtime, repository root as
   the root directory, and `./Dockerfile` as the Dockerfile path. Keep the Docker
   command empty so the Dockerfile's command is used.
4. Choose an instance with sufficient memory; compare current platform pricing
   before creating a paid instance. No paid resources are created by this repo.
5. Set `STORYSCOUT_RETRIEVAL_MODE=hybrid` and
   `STORYSCOUT_USE_NVIDIA=false`. Set the health-check path to `/api/ready`.
6. Deploy. Building scientific packages and downloading the public embedding
   model can take several minutes. Wait for `/api/ready` to return 200.
7. Open your Render URL. Verify books, movies, both, a cross-media request,
   follow-up filters, and a saved story. Pipeline shows the actual active mode.
8. Share the Render URL instead of the old Streamlit URL. Future pushes to the
   connected GitHub branch can trigger Render updates.

Official references checked during implementation:
[Docker on Render](https://render.com/docs/docker),
[web services and port binding](https://render.com/docs/web-services),
[health checks](https://render.com/docs/health-checks).

## Optional NVIDIA interpretation

The default app uses local rules, TF-IDF, and sentence embeddings. To enable
the existing optional query interpreter, set these only in the backend service's
private environment settings:

```text
STORYSCOUT_USE_NVIDIA=true
NVIDIA_API_KEY=<your-private-server-key>
```

Messages will then be sent to NVIDIA for interpretation. Catalog retrieval,
hard filters, and explanations still run in Python. Never place a secret in any
`VITE_*` variable: those become public JavaScript. `.streamlit/secrets.toml` can
still supply a local development key, but is excluded from Docker and Git.
The frontend does not display provider marketing text; its NLP page documents
whether external interpretation is active. API failures preserve local parsing.

## Separate frontend/backend hosting (optional)

The single-service setup is simpler. If separate hosting is required, build
React with `VITE_API_URL=https://your-python-service.example` and set the backend
`STORYSCOUT_ALLOWED_ORIGINS=https://your-frontend.example` (comma-separated for
multiple exact origins). Serve `frontend/dist` on a static host. The API still
requires a Python/container host with sufficient model memory. Rebuild the
frontend after changing its API URL. HTTPS is required for `crypto.randomUUID`
on non-localhost origins.

## Storage and limitations

Conversations and bookmarks persist in each browser's localStorage. They are
not cloud accounts, synchronized devices, or collaborative filtering. Each
request carries validated preference state, so one visitor cannot accidentally
inherit another visitor's conversation. Large or malformed request fields are
rejected. Catalog records and evaluation snapshots are local read-only inputs.
No private repository file is served by the static route. This is a college
project deployment, without account authentication or a usage quota system.

## Verification

```bash
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
.venv/bin/python scripts/verify_api.py
cd frontend && npm run build
```

Python API tests exercise state round-trips, reference selection, cross-media
inheritance, authoritative form filters, reset, independent client state,
invalid input, contradictions, unknown records, and preparation status. Browser
checks and actual container verification are recorded in `VERIFICATION.md`.


The latest NLP revision indexes 6,023 local plots and trains a lightweight
TF-IDF genre classifier during Docker build. First chunk embedding preparation
measured about 9.4 minutes on the development CPU; allow sufficient build time.
Subsequent document edits reuse unchanged vectors through an ignored cache
manifest. Model/cache files stay out of Git. The revised Dockerfile has not
been rebuilt in the latest verification pass; see `VERIFICATION.md`.
