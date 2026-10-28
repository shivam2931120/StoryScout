# Full-catalog verification snapshot — 2026-10-28

For the current free-tier image and deployment, see [FREE_HOSTING.md](FREE_HOSTING.md). The following records the earlier full-catalog revision.

- `python -m pytest -q`: **71 passed**. Tests cover source constraints, state,
  media, mood/negation, separate lengths, refinements, cross-media references,
  unseen next picks, source/inference separation, and incremental embedding cache
  reuse. A fake encoder isolates the cache test; full semantic execution was
  separately verified against the real model.
- `npm run build`: passed. The built React app is served by FastAPI.
- `scripts/verify_api.py`: **7 real HTTP scenarios passed** for books, movies,
  both, both cross-media directions, follow-up and reset. Output:
  `artifacts/api_verification.json`.
- Both domains report hybrid TF-IDF + CPU sentence embeddings.
- `scripts/evaluate_search_tuning.py`: five genre form edits produced 25 unique
  movies, all genre/runtime checks passed, and all next-pick sets were nonempty
  and unseen. Three follow-up topics were preserved. See
  `artifacts/search_tuning/preference_v2_results.json`.
- The local plot-genre classifier was trained and tested: micro F1 **0.6807**
  versus **0.4138** for the identical-split title baseline, on 1,204 held-out films.
  Full per-label reports are in `artifacts/genre_text_results.json`.

## Browser checks

Playwright used installed Brave at 1440 × 1000. A crime movie query under 120
minutes rendered matching results. The “Show different recommendations” action
rendered a different set. Changing the live preferences from Crime to Family
rendered RV, Heidi, and Yours, Mine and Ours with known compliant runtimes.
The Evaluation page rendered the actual plot/title classifier comparison and
preference-search checks. Browser console: **0 errors and 0 warnings**.
Screenshots: `output/playwright/nlp-preferences.png` and `nlp-evaluation.png`.
The browser was closed after verification; the single API/demo server remains
on http://127.0.0.1:8000.

## Actual retrieval measurements

| Method | P@5 | Recall@5 | MRR@5 | Hard compliance | Mean ms |
|---|---:|---:|---:|---:|---:|
| tfidf | 0.2370 | 0.6265 | 0.6642 | 1.000 | 46.2 |
| semantic | 0.2296 | 0.6188 | 0.6772 | 1.000 | 89.4 |
| hybrid | 0.2445 | 0.6497 | 0.7098 | 1.000 | 81.7 |

44 developer-authored queries; domains evaluated separately and macro-averaged.
Judgments are incomplete, not independent human ratings. Semantic results are
included because the model actually ran. Source genre checks and classifier F1
measure different components; none are recommendation confidence percentages.
See `SEARCH_TUNING.md` for baseline comparison and preparation timing.

## Deployment scope

The previous React migration's Docker image was built and checked offline
(`artifacts/container_verification.json`). **That is a historical result**.
At the time of this full-catalog snapshot, its Dockerfile trained the plot classifier and
builds new text indexes, but that image had not been rebuilt in that verification pass. Current free-tier container and deployment checks are recorded in FREE_HOSTING.md. Current checks used the local production React build and
Python environment. Public deployment has not been performed in this revision.

## Remaining limitations

Only 12 books have known page counts; book-length filters retain a small pool.
Movie runtime coverage is 1,322 of 9,744, and full plot coverage is 6,023.
Mood/theme inferences are experimental text signals. Unknown warnings do not
certify content safety. MiniLM is pretrained and was not fine-tuned. No external
chat API is required or used by the default running app.
