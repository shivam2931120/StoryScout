# Submission checklist

- [x] One Streamlit interface supports books, movies, both, follow-ups, and cross-media references.
- [x] Small curated demo catalogs support immediate offline demonstration.
- [x] Expanded catalogs include 10,000 Project Gutenberg English book metadata records and 9,737 MovieLens movie records; source snapshots and reproducible importers are included.
- [x] Metadata gaps remain unknown; metadata-only placeholder descriptions are omitted from search text. Fifty-six source-backed Wikipedia + Nemotron summaries are stored as a separate, attributed dataset.
- [x] Typed shared and per-domain preferences, negation, year/page/runtime filters, contradictions, and reset are implemented.
- [x] TF-IDF and CPU sentence-transformer dependencies are in the deployment requirements; if the model cannot load, the app falls back to TF-IDF.
- [x] Catalog indexes and embeddings have content/model/configuration-based cache keys; model weights are not included.
- [x] Cross-media retrieval, title ambiguity handling, exclusions, and grounded explanations are implemented.
- [x] 44-query retrieval and 25-conversation preference benchmarks ran. Actual results are in `artifacts/evaluation_results.json` and `evaluation_summary.md`.
- [x] Human annotation workflow exports candidate sheets and scores uploaded judgments separately; no independent human ratings have been collected yet.
- [x] Title-only held-out MovieLens multi-label genre experiment ran; book classifier was correctly skipped because expanded book metadata has no genre labels.
- [x] 40 tests pass; expanded catalog validation passes.
- [x] Dark UI uses SVG icon assets and no decorative emoji.
- [x] Local Streamlit server is running on port 8501.
- [ ] Browser visual QA could not run because the Chrome DevTools connector reports that the Chrome executable is missing.
- [x] Public GitHub repository is published at https://github.com/shivam2931120/StoryScout.
- [x] Project owner deployed the app from `main` / `app.py` to Streamlit Community Cloud; this environment cannot inspect the hosted deployment status.
- [x] CPU-only Sentence Transformers model was downloaded, indexes were cached, and the semantic and hybrid retrieval benchmarks ran.

The primary remaining work is external: collect independent human relevance labels and check the hosted deployment after repository updates.
