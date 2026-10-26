# Submission checklist

- [x] One Streamlit interface supports books, movies, both, follow-ups, and cross-media references.
- [x] Small curated demo catalogs support immediate offline demonstration.
- [x] Expanded catalogs include 10,000 Project Gutenberg English book metadata records and 9,737 MovieLens movie records; source snapshots and reproducible importers are included.
- [x] Metadata gaps are kept unknown; metadata-only placeholder descriptions are omitted from search text.
- [x] Typed shared and per-domain preferences, negation, year/page/runtime filters, contradictions, and reset are implemented.
- [x] TF-IDF runs locally. Semantic retrieval uses CPU sentence embeddings when the model is installed; otherwise the app states that TF-IDF fallback is active.
- [x] Catalog indexes and embeddings have content/model/configuration-based cache keys; model weights are not included.
- [x] Cross-media retrieval, title ambiguity handling, exclusions, and grounded explanations are implemented.
- [x] 44-query retrieval and 25-conversation preference benchmarks ran. Actual results are in `artifacts/evaluation_results.json` and `evaluation_summary.md`.
- [x] Human annotation workflow exports candidate sheets and scores uploaded judgments separately; no independent human ratings have been collected yet.
- [x] Title-only held-out MovieLens multi-label genre experiment ran; book classifier was correctly skipped because expanded book metadata has no genre labels.
- [x] 35 tests pass; expanded catalog validation passes.
- [x] Dark UI uses SVG icon assets and no decorative emoji.
- [x] Local Streamlit server is running on port 8501.
- [ ] Browser visual QA could not run because the Chrome DevTools connector reports that the Chrome executable is missing.
- [ ] Public deployment remains incomplete: the Replit connector returned an internal “Unknown tool” error and this workspace has no configured deploy provider credentials. The local app is available at `http://localhost:8501`.
- [x] CPU-only Sentence Transformers model was downloaded, indexes were cached, and the semantic and hybrid retrieval benchmarks ran.

The primary remaining work is external: collect independent human relevance labels and connect a working Python hosting account for public deployment.
