# StoryScout

**Live application:** https://storyscout-eaw7.onrender.com — Render free tier, local semantic NLP, no API key required.

StoryScout is a college NLP project: one conversational assistant for book discovery (BookBuddy) and mood-aware movie discovery (CinemaSense). It combines rule-based intent detection, typed preference extraction, TF-IDF lexical retrieval, shared CPU Sentence Transformer embeddings, hard filters, cross-media similarity, and grounded explanations. The main interface is React, connected to the Python engine through FastAPI. The previous Streamlit app remains available for comparison.

The interface follows the supplied dark archival design: charcoal surfaces, teal highlights, bundled SVG artwork and icons, real preference and item drawers, a responsive conversation view, saved stories, and recent conversations. Bookmarks and conversations persist in the current browser. No API key is required: TF-IDF runs locally, and the public MiniLM model can be downloaded without credentials. Decorative artwork is not an official publisher cover or movie poster.

Optional NVIDIA Nemotron query interpretation can normalize misspellings, identify intent, and extract explicitly stated filters. Store `NVIDIA_API_KEY` in `.streamlit/secrets.toml` (ignored by Git) or the server environment. The key is only read server-side and is never rendered in the app. User messages submitted while configured are sent to NVIDIA's API. The integration uses NVIDIA's OpenAI-compatible chat completions endpoint. Without a key or when the API is unavailable, local parsing and catalog retrieval continue to work.

## Quick start

React + FastAPI (the current application):

```bash
cd /home/shivam/StoryScout
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-api.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. FastAPI serves the built interface and API on one
URL. During frontend development, `npm run dev` in `frontend/` starts Vite on
port 5173 with an API proxy to the Python server. The production application
needs one Python server and no separate Node server. See
[deployment instructions](docs/DEPLOYMENT.md).

The default React/API app uses local NLP without an external chat API. An optional server-side `TMDB_API_KEY` enables on-demand movie title verification when the local title directory misses a likely named movie or reference. TMDB supplies exact identity and linked metadata; local preference extraction, hard filters, and NLP ranking remain authoritative. The key is never sent to the browser or saved to the repository. The Dataset page includes TMDB's required logo and notice. TMDB's developer API is for non-commercial use with attribution; review [its current terms and attribution rules](https://developer.themoviedb.org/docs/faq) before sharing or monetizing the app.

Set
`STORYSCOUT_USE_NVIDIA=true` and a private backend `NVIDIA_API_KEY` only if you
want the optional interpreter. Local filtering and ranking remain in Python.

Original Streamlit application:

```bash
cd StoryScout
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
.venv/bin/streamlit run app.py
```

## Deploy

For **React + FastAPI**, the root multi-stage Dockerfile builds the interface,
caches the quantized MiniLM model and indexes for a compact free-tier catalog, and serves everything from one
container web service. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for exact
Docker and Render settings, environment variables, and memory guidance.
Streamlit Community Cloud can continue serving the previous Streamlit app;
it cannot serve the new React + FastAPI application.

The following instructions apply to the older **Streamlit interface**:

Push this repository to GitHub, then open [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app**, and select this repository, the `main` branch, and `app.py`. The app does not require a secret to run. `requirements.txt` installs the CPU sentence-embedding model used locally; first startup downloads the model and builds its indexes. If model download or loading fails, the app falls back to TF-IDF. `NVIDIA_API_KEY` is optional for query interpretation and sourced description enrichment; configure it only in Streamlit's app Secrets. Never commit API keys or `.streamlit/secrets.toml`.

The bundled demonstration catalog contains 14 books and 13 movies. Project Gutenberg metadata adds 10,000 English book records; MovieLens latest-small adds 9,737 movie records. The current active deduplicated catalog contains 10,025 books and 9,768 movies, including a sourced supplemental book/movie snapshot. Movie search now includes 6,382 locally indexed Wikipedia plots and 1,322 known runtimes. Book coverage is still mostly title/author/subject metadata, with only 12 known page counts. Optional Wikipedia-sourced, Nemotron-paraphrased descriptions live separately in `data/enriched/descriptions.csv`; records without a source match remain undescribed. Hybrid retrieval uses `sentence-transformers/all-MiniLM-L6-v2` on CPU when available and falls back to TF-IDF if model download/loading fails. Model weights are not committed.

## Verified environment

React/FastAPI migration: React 19.3.1, Vite 7.3.7, Lucide React 0.468.0,
Node 24.18.0, FastAPI 0.162.0, Uvicorn 0.54.0, Pydantic 2.14.1, and httpx
0.28.1. Exact frontend resolutions are committed in `frontend/package-lock.json`.
See [verification notes](docs/VERIFICATION.md) for the browser/API checks and
deployment build status. [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[Vite proxy configuration](https://vite.dev/config/server-options), and
[React state](https://react.dev/reference/react/useState) follow their official APIs.

Verified environment: Python 3.14.4, pandas 2.3.3, NumPy 2.5.4, scikit-learn 1.9.1, Streamlit 1.66.1, pytest 9.1.1, PyTorch 2.14.1+cpu, Sentence Transformers 5.7.0, and Transformers 5.20.2. CUDA is unavailable, so the tested setup is CPU-only. The embedding implementation follows the official [`SentenceTransformer.encode`](https://sbert.net/docs/package_reference/sentence_transformer/model.html) API.

## Preparation and data

`scripts/prepare_data.py [books.csv] [movies.csv]` validates normalized user-supplied CSV files. Rebuild the included MovieLens normalized catalog with:

```bash
.venv/bin/python scripts/import_movielens.py
```

MovieLens is provided under research-only conditions. Rebuild the English book subset from the included Project Gutenberg metadata with:

```bash
.venv/bin/python scripts/import_gutenberg_catalog.py
```

Both normalized catalogs are already included. Read `docs/DATA_SOURCES.md` and source terms before redistribution or use. To fetch additional records from public CC0 Wikidata metadata, run:

```bash
.venv/bin/python scripts/acquire_wikidata_catalog.py --limit 1000
```

This writes `data/expanded/books.csv` and `data/expanded/movies.csv` when the public endpoints are available. The app loads these records alongside the demo catalog and rebuilds its cached indexes when the files change. The query limit is a maximum, not a guaranteed record count. See `docs/DATA_SOURCES.md` for provenance and current acquisition limitations.

## Evaluation and classifier

`.venv/bin/python scripts/evaluate.py` evaluates 44 retrieval queries and 25 preference conversations, writing JSON, a readable summary, and per-query CSV results under `artifacts/`. Labels are developer-authored, not independent human evaluation. Mixed-media retrieval is scored separately per domain. Semantic metrics are omitted unless the sentence embedding model actually runs. The Evaluation tab exports a judgment sheet for human relevance ratings and summarizes completed sheets separately. Run `.venv/bin/python scripts/train_text_genres.py` for the new plot-based genre classifier and an identical-split title baseline. Full per-label held-out results are saved to `artifacts/genre_text_results.json`. The older `train_classifiers.py` experiment remains available for comparison. Books lack sufficient source genre labels for a supervised experiment.

To add optional summaries for records with no supplied description, configure `NVIDIA_API_KEY` server-side and run `.venv/bin/python scripts/enrich_descriptions.py`. The script looks up exact-title Wikipedia leads, asks Nemotron to paraphrase only the supplied source text, and saves summaries with source URL, model, and provenance in `data/enriched/descriptions.csv`. No summary is created when an exact source page is not found or the model returns no grounded text. Review the source terms before redistribution; Wikipedia summaries are attributed under CC BY-SA 4.0. Existing search indexes are invalidated when this file changes.

## Troubleshooting

- If `sentence-transformers` is unavailable, the default hybrid mode automatically falls back to TF-IDF; the app identifies this as lexical retrieval, not semantic retrieval.
- If Streamlit is unavailable, use the same engine from Python modules and run the tests.
- Explicit filters never relax automatically. Unknown page count/runtime/year cannot satisfy that hard filter.
- If TMDB title lookup is unavailable or its key is invalid, StoryScout falls back to its local title directory. TMDB search results are not persisted into the NLP indexes; a returned unknown runtime cannot satisfy a runtime limit.

Main files to study: `src/preferences.py`, `src/retrieval.py`,
`src/conversation.py`, `api/main.py`, `api/models.py`, `frontend/src/App.jsx`,
`frontend/src/components.jsx`, and `tests/`. The NLP modules remain independent
of both interfaces. `app.py` is the retained Streamlit alternative.

## Local NLP search revision

Search uses local source text, not generated API recommendations. See
[search tuning and measured evidence](docs/SEARCH_TUNING.md). Preferences are
rebuilt into the query; selected genres match any chosen source genre (or a
marked Gutenberg subject mapping), while inferred genres remain soft evidence.
“Show different recommendations” excludes previously shown IDs without relaxing
filters. The MiniLM encoder is pretrained; the TF-IDF genre classifier is trained
locally from plot text.

The prepared supplement files are already bundled. To reproduce preparation:

```bash
.venv/bin/python scripts/prepare_nlp_catalog.py --plots-only
.venv/bin/python scripts/enrich_wikipedia_metadata.py --limit 1500
.venv/bin/python scripts/train_text_genres.py
.venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
# With the local API server running:
.venv/bin/python scripts/evaluate_search_tuning.py
.venv/bin/python scripts/verify_api.py
```

Metadata acquisition is bounded, resumable, and can encounter public API rate
limits. The bundled snapshot works offline after model/index preparation.

## Free hosted profile

The default Docker/Render deployment now uses the **free** plan with 1,000
books and 1,500 movies (1,455 with plot text; 1,322 with known runtimes). The
full 10,025/9,768 source catalog remains available locally. A deterministic
subset preserves demo references and prioritizes verified lengths/source text.

The free runtime uses the official quantized MiniLM ONNX export, original
tokenizer and masked mean pooling. It keeps local semantic retrieval, TF-IDF,
classification features, structured preferences and diversity; no chat API is
required. PyTorch/Sentence Transformers remain available in the full local
setup. `requirements-free.txt` pins the lightweight hosting dependencies.

See `docs/DEPLOYMENT.md` for terminal deployment commands and
`artifacts/compact/` for compact-profile evaluation. The two profiles' metrics
are kept separate. Free hosting can sleep when idle and has limited CPU.

Bare title searches use a separate local directory of all 19,793 source records,
including records outside the compact semantic index. Title words do not become
preferences; remakes and filter conflicts are shown explicitly. See
[title lookup behavior and its executed benchmark](docs/TITLE_LOOKUP.md).

Current search improvements, source-summary provenance, context controls, actual
before/after metrics and suggested NLP experiments: [NLP relevance update](docs/NLP_RELEVANCE_UPDATE.md).

## Passage matching update

Overlapping narrative passages now supplement whole-document retrieval, with one
card per title and source-grounded passage evidence. See [implementation, actual
ablation results, caching, and validation](docs/PASSAGE_MATCHING.md).

## Conversational title search revision

Exact title extraction, source aliases, franchise choices, spelling suggestions,
missing-title handling, and source-backed modern coverage are implemented. See
[the current policy, executed checks, and limitations](docs/ENTITY_SEARCH.md).
