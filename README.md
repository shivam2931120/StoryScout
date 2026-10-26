# StoryScout

StoryScout is a local-first college NLP project: one conversational assistant for book discovery (BookBuddy) and mood-aware movie discovery (CinemaSense). It combines rule-based intent detection, typed preference extraction, TF-IDF lexical retrieval, optional Sentence Transformers embeddings, hard filters, cross-media similarity, grounded explanations, and a Streamlit chat UI.

The interface uses a dark neumorphic theme. No API key is required: TF-IDF runs locally, and the public MiniLM model can be downloaded without credentials. If you later use a gated Hugging Face model, set `HF_TOKEN` in your shell or Streamlit secrets; never put tokens in source files or commit them.

Optional NVIDIA Nemotron query interpretation can normalize misspellings, identify intent, and extract explicitly stated filters. Store `NVIDIA_API_KEY` in `.streamlit/secrets.toml` (ignored by Git) or the server environment. The key is only read server-side and is never rendered in the app. User messages submitted while configured are sent to NVIDIA's API. The integration uses NVIDIA's OpenAI-compatible chat completions endpoint. Without a key or when the API is unavailable, local parsing and catalog retrieval continue to work.

## Quick start

```bash
cd StoryScout
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install 'torch==2.14.1+cpu' --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r requirements-semantic.txt
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
.venv/bin/streamlit run app.py
```

## Deploy

Push this repository to GitHub, then open [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app**, and select this repository, the `main` branch, and `app.py`. The app does not require a secret to run. The checked-in dependencies use the local TF-IDF NLP fallback on Community Cloud; install the optional CPU Sentence Transformers dependencies from `requirements-semantic.txt` only when the deployment environment has enough memory. If you configure `NVIDIA_API_KEY` in Streamlit's app Secrets, it is used only on the server for optional query interpretation. Never commit API keys or `.streamlit/secrets.toml`.

The bundled demonstration catalog contains 14 books and 13 movies. Project Gutenberg metadata adds 10,000 English book records; MovieLens latest-small adds 9,737 movie records. The active deduplicated catalog contains 10,005 books and 9,744 movies. Neither public source contains plot descriptions, and missing fields remain unknown. If the embedding model is cached, hybrid retrieval uses `sentence-transformers/all-MiniLM-L6-v2` on CPU. If the model is not available, the app reports and uses TF-IDF fallback. Model weights are not committed.

## Verified environment

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

`.venv/bin/python scripts/evaluate.py` evaluates 44 retrieval queries and 25 preference conversations, writing JSON, a readable summary, and per-query CSV results under `artifacts/`. Labels are developer-authored, not independent human evaluation. Mixed-media retrieval is scored separately per domain. Semantic metrics are omitted unless the sentence embedding model actually runs. The Evaluation tab exports a judgment sheet for human relevance ratings and summarizes completed sheets separately. Run `.venv/bin/python scripts/train_classifiers.py` for the held-out movie genre experiment using title-only features; books with too few labeled genres are skipped.

## Troubleshooting

- If `sentence-transformers` is unavailable, the default hybrid mode automatically falls back to TF-IDF; the app identifies this as lexical retrieval, not semantic retrieval.
- If Streamlit is unavailable, use the same engine from Python modules and run the tests.
- Explicit filters never relax automatically. Unknown page count/runtime/year cannot satisfy that hard filter.

Main files to study: `src/preferences.py`, `src/retrieval.py`, `src/conversation.py`, `app.py`, and `tests/`.
