# Submission checklist

- [x] React + FastAPI and the retained Streamlit interface support books, movies, both, follow-ups, and cross-media references.
- [x] Small curated demo catalogs support immediate offline demonstration.
- [x] Expanded catalogs include 10,000 Project Gutenberg English book metadata records and 9,737 MovieLens movie records; source snapshots and reproducible importers are included.
- [x] Metadata gaps remain unknown; metadata-only placeholder descriptions are omitted from search text. Fifty-six source-backed Wikipedia + Nemotron summaries are stored as a separate, attributed dataset.
- [x] Typed shared and per-domain preferences, negation, year/page/runtime filters, contradictions, and reset are implemented.
- [x] TF-IDF and CPU sentence-transformer dependencies are in the deployment requirements; if the model cannot load, the app falls back to TF-IDF.
- [x] Catalog indexes and embeddings have content/model/configuration-based cache keys; model weights are not included.
- [x] Cross-media retrieval, title ambiguity handling, exclusions, and grounded explanations are implemented.
- [x] 44-query retrieval and 25-conversation preference benchmarks ran. Actual results are in `artifacts/evaluation_results.json` and `evaluation_summary.md`.
- [x] Human annotation workflow exports candidate sheets and scores uploaded judgments separately; no independent human ratings have been collected yet.
- [x] Plot-text and identical-split title-baseline held-out multi-label genre experiments ran; book classifier was correctly skipped because expanded book metadata has no genre labels.
- [x] 73 tests pass; expanded catalog validation passes.
- [x] Dark UI uses SVG icon assets and no decorative emoji.
- [x] React + FastAPI production app is running locally on port 8000.
- [x] Real browser QA runs through Playwright with the installed Brave executable: desktop discovery, preferences/details drawers, chat, saved persistence, and mobile layout.
- [x] Public GitHub repository is published at https://github.com/shivam2931120/StoryScout.
- [x] Project owner previously deployed the legacy `app.py` to Streamlit Community Cloud. The new React/FastAPI application needs a container/Python web host.
- [x] CPU-only Sentence Transformers model was downloaded, indexes were cached, and the semantic and hybrid retrieval benchmarks ran.

The React/FastAPI public deployment is live on Render free tier. Docker and Render steps are in DEPLOYMENT.md. Independent human relevance labels remain external work.

- [x] React follows the supplied design with functional drawers, navigation,
  browser-persisted conversations/bookmarks, and bundled SVG assets.
- [x] One production Docker image serves React and FastAPI; its baked model and
  indexes worked with Hugging Face offline mode enabled. Seven HTTP scenarios
  and a mixed browser search passed inside the container deployment.
- [x] React/FastAPI is public at https://storyscout-eaw7.onrender.com on Render free tier.


- [x] 6,382 local source plots, 1,322 known movie runtimes, and per-field provenance.
- [x] Current preference query rebuilding, desired/user mood separation, MMR,
  unseen next picks, and incremental document embedding reuse.
- [x] Current real-server preference regression and desktop browser checks passed.
- [x] The free-profile Docker revision was built, resource-limited, tested and deployed; the earlier full-profile container checks remain historical.


- [x] Free-tier compact catalogs and actual quantized semantic inference.
- [x] Compact retrieval evaluation and preference regression executed separately.
- [x] Seven HTTP scenarios under hard 512 MB RAM and 0.1 CPU limits.
- [x] Render free service created with no paid compute plan.
- [x] Public readiness, seven HTTP scenarios, preference regression, and desktop/mobile browser checks passed.
