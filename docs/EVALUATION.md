# Search evaluation

StoryScout evaluates separate capabilities separately. Run from the repository
root after installing `requirements-api.txt` and preparing the local catalog.
No API key is required; provider interpretation is deliberately disabled in the
offline benchmarks so that model/API variability cannot hide local NLP results.

```bash
.venv/bin/python scripts/evaluate.py
.venv/bin/python scripts/evaluate_identification.py --mode hybrid
# Reproduce the free-tier catalog/encoder instead of the full local profile:
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx \
STORYSCOUT_EVALUATION_DIR=artifacts/compact .venv/bin/python scripts/evaluate.py --modes hybrid
# Optional real service tests for API routing/title identity:
.venv/bin/python scripts/evaluate_entity_search.py --base-url http://127.0.0.1:8000
.venv/bin/python scripts/evaluate_title_lookup.py --base-url http://127.0.0.1:8000
```

Set `STORYSCOUT_CATALOG_PROFILE=compact` and
`STORYSCOUT_EMBEDDING_BACKEND=onnx` to evaluate the same bounded catalog and
encoder used by the free deployment. The default uses the active local catalog.
Outputs are written under `artifacts/` (or `STORYSCOUT_EVALUATION_DIR` for the
main recommendation evaluation). They are generated results; rerun after code,
data, model, or dependency changes.

## What is measured

| Capability | Dataset | Main measures |
|---|---|---|
| Preference-based recommendations | 44 labeled queries across 25 categories in `data/evaluation_queries.json` | P@5, Recall@5, MRR@5, binary nDCG@5, hard-filter compliance, answer rate, slot fill, query latency |
| Plot identification | 12 broad plot queries plus 10 source-backed focal-detail queries | Top-1, Hit@3, MRR@5, Recall@5, nDCG@5, target coverage |
| Preference extraction | Labeled multi-message examples in `data/preference_evaluation.json` | Per-field and overall exact match |
| Title identity and routing | `data/entity_search_evaluation.json` and `data/title_lookup_evaluation.json` | Exact/partial/typo/missing behavior, media selection, preference retention; performed through HTTP |
| Human recommendation judgments | Evaluation page's downloadable judgment sheet | Rated-item precision/MRR; graded nDCG@5 only when every returned top-five item is judged; judgment coverage |

By default the recommendation benchmark compares TF-IDF, semantic-only, and
hybrid retrieval on identical catalog/query data. Pass `--modes hybrid` (or
any subset) to run selected modes. With multiple modes, paired query-level
metric deltas and bootstrap intervals are reported. A mode is reported as unavailable
when its required sentence model did not run. Plot identification reports the
active index mode and evaluates against the active catalog, not only the tiny
demo set. Targets absent from the active catalog cause the identification run
to stop instead of silently lowering the score.

The 95% intervals use a deterministic percentile bootstrap with 2,000
resamples. Recommendation intervals resample query texts as clusters, keeping
the book and movie halves of a mixed-media request together. Identification
resamples query cases. These intervals describe variation within these curated
benchmarks; they do **not** certify real-world accuracy. The labeled sets are
small, developer-authored, and incomplete. Valid recommendations not listed in
the labels may be counted as misses. The identification set is not a
representative sample of vague user descriptions.

## How to make the benchmark stronger

1. Add queries before changing ranking rules; record expected relevant IDs,
   media, query category, and why each label is relevant.
2. Keep a frozen test set separate from examples used to tune thresholds.
   Prefer splitting by target title/franchise, not by paraphrase, to avoid
   near-duplicate leakage.
3. Have two people independently rate recommendation results from 0 (not
   relevant) to 2 (strong fit), then adjudicate disagreements. Do not include
   API-generated or synthetic recommendations as their own ground truth.
4. Include out-of-catalog titles, ambiguity, spelling errors, negation,
   follow-ups, each hard filter, and queries with multiple valid matches.
5. Report per-category results and every regression, not only one overall
   number. Do not infer performance on all books/movies from this sample.

The app's human-evaluation utility avoids treating blank labels as relevant.
Its graded nDCG is left undefined until all returned items in the top five for
that query have been rated. This prevents a partially completed sheet from
looking like a complete relevance result.

## Latest executed run

Run on 2026-10-31 with the compact deployment catalog and ONNX MiniLM encoder;
all three local retrieval modes ran. The Nemotron interpreter was disabled.

| Retriever | Query-domain cases | Macro MRR@5 | Macro nDCG@5 | Hard-filter compliance |
|---|---:|---:|---:|---:|
| TF-IDF | 54 | 0.7052 | 0.5996 | 1.0000 |
| Semantic | 54 | 0.7275 | 0.6259 | 1.0000 |
| Hybrid | 54 | 0.7670 | 0.6708 | 1.0000 |
| Hybrid, books | 27 | 0.8704 | 0.8097 | 1.0000 |
| Hybrid, movies | 27 | 0.6636 | 0.5320 | 1.0000 |

Hybrid macro MRR@5 has a 95% bootstrap interval of 0.6696–0.8539; Recall@5 is
0.7037. Paired hybrid-minus-TF-IDF deltas are +0.0644 MRR@5 (interval
−0.0170–0.1515) and +0.0698 nDCG@5 (0.0072–0.1364). The other paired
ranking intervals include zero. This is evidence of ranking improvement only
on this authored sample, not proof of a general gain.

| Capability | Sample | Result |
|---|---:|---|
| Preference extraction | 25 labeled conversations / 33 messages | Field exact match 1.0000 on authored examples; field supports range from 1 to 25 |
| Plot identification | 22 queries; target coverage 1.0000 | Top-1 0.8636 (19/22); Hit@3 0.9091; MRR@5 0.8864 |
| Plot identification, broad / focal | 12 broad + 10 focal-detail cases | Top-1 0.8333 / 0.9000 |

These are reproducible measurements on the current labeled sets, not an
independent user study. Movie recommendation ranking is weaker than book
ranking on this set, and authored relevance labels are incomplete. Inspect the
case-level CSV and JSON; collect and adjudicate more human judgments before
claiming general accuracy.
