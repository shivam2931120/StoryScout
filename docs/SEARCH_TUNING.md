# Local NLP search revision

The repeated recommendations had two causes: only 12 movie records had known
runtime, and form changes could leave the old genre/mood in the search text.
The previous live-server behavior is preserved in
`artifacts/search_tuning/preference_v1_baseline.json`: all five genre edits
returned exactly the same five titles.

## What is processed locally

The active corpus contains 10,005 books and 9,744 movies. MovieLens genre/year
metadata is supplemented with 6,023 exact-title/year Wikipedia plots and source
infobox/Wikidata facts. There are now 1,322 known runtimes and 1,334 known movie
languages. Gutenberg subjects yield 1,815 explicitly marked rule-derived genre
mappings. Only 12 books have known page counts; book length searches remain
limited by that honest coverage constraint.

Text processing and ranking require no external chat API:

1. Rules recognize intent, desired medium, exclusions, mood, themes and limits.
   The meaningful query topic is stored independently of filters.
2. A follow-up keeps the topic. A form edit removes old mood/genre descriptors
   and rebuilds the query from current preferences. Administrative phrases such
   as “apply my discovery preferences” do not become content-search terms.
3. Hard filters reject unknown year/length/language when explicitly constrained.
   Selected genres use OR matching over source genres or documented subject
   mappings. Learned genre predictions never satisfy this hard filter.
4. TF-IDF learns unigrams/bigrams from source text, with English stop words,
   sublinear term frequency and a 60,000-feature vocabulary per domain.
   Top document terms become visible, locally extracted keyphrases.
5. The same pretrained `all-MiniLM-L6-v2` CPU model encodes up to three 140-word
   chunks per document: beginning, middle and end. Their normalized vectors
   are mean-pooled and normalized again. This samples long plots rather than
   silently representing only the opening; it does not encode every sentence.
6. Semantic cosine is clipped/scaled from [0.18, 0.62] to [0, 1]. Hybrid text
   similarity is 0.45 × lexical cosine + 0.55 × scaled semantic cosine.
7. Transparent mood/theme prototype sentences are encoded locally. Alignment
   is `clip((cosine - 0.12) / 0.35, 0, 1)` (TF-IDF fallback: `clip(4*cosine,0,1)`).
   These soft signals are not trained sentiment predictions or safety labels.
8. A separate supervised multi-label classifier learns movie genres from plot
   descriptions using TF-IDF and one-vs-rest logistic regression. Predictions
   remain distinct from catalog labels and metadata.
9. Reranking uses active weights: text .55, source genre coverage .25, mood .20,
   theme .25 and learned genre overlap .10. Only present components enter the
   denominator. Metadata-only documents receive a .65 text factor. Previously
   shown IDs receive a bounded .035 penalty. None are probabilities.
10. MMR chooses from up to 80 eligible candidates, balancing relevance (.84)
    against cosine similarity to already selected items (.16). “Show different
    recommendations” explicitly excludes served IDs, with every filter retained.
    Filter-only results carry zero text relevance rather than fabricated scores.

Books and movies remain separate result groups. Their independently fitted
TF-IDF scores are never treated as a cross-domain calibrated ranking.

## Executed supervised experiment

`python scripts/train_text_genres.py` ran on **6,020 source-labeled plots**.
Plot-hash groups isolate identical plot text across splits: train 3,853,
validation 963, test 1,204 (fixed seeds 42/43). Labels require at least 30 training
examples. Vocabulary, weights and threshold selection never fit on test data;
thresholds are chosen on validation, then the model refits on development.

The plot model achieved held-out **micro F1 0.6807**, compared with **0.4138**
for the title-only baseline on the same test IDs. Complete per-label precision,
recall, F1 and support are saved in `artifacts/genre_text_results.json`.
This measures genre classification, not recommendation accuracy. MiniLM itself
was not trained or fine-tuned. The model pickle is an ignored local artifact;
Docker trains the lightweight classifier during its build.

## Reproduce and inspect

```bash
.venv/bin/python scripts/prepare_nlp_catalog.py --plots-only
.venv/bin/python scripts/enrich_wikipedia_metadata.py --limit 1500
.venv/bin/python scripts/train_text_genres.py
.venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate.py
# With API running on port 8000:
.venv/bin/python scripts/evaluate_search_tuning.py
.venv/bin/python scripts/verify_api.py
```

The NLP details below each response expose the retained content topic, filter
pool counts and ranking method. Item details expose extracted terms, separately
marked text inferences, ranking components, and field provenance. Original plot
text stays on the server. Opening excerpts and explanations avoid revealing
endings, although the local source corpus itself can contain spoilers.

The 44-query relevance benchmark has incomplete developer-authored judgments.
New, valid movie candidates may be unjudged and counted as misses. The separate
preference-edit benchmark checks source genre membership, verified runtime,
unseen next picks and topic retention; it does not establish subjective relevance.
See the JSON outputs and current evaluation summary for executed results.

## Limits

Mood suitability is subjective; semantic similarity does not guarantee it.
Genre labels are imperfect and multiple genres are common. Metadata acquisition
can be rate-limited; the bundled source snapshots keep normal search offline.
No API generates missing runtimes, years, page counts, languages or warnings.
There is no collaborative filtering, behavior-based personalization, verified
adaptation detection, or independent human recommendation study.


## Executed search checks (2026-10-28)

Five genre edits with a 120-minute cap returned **25 distinct titles**, versus
**5** in the saved old-server baseline. Mean source-genre precision@5 increased
from **0.28 to 1.00**. All current genre/runtime filters passed, and each genre's
next five picks were nonempty and disjoint from its first five. Three content
requests retained their topic across “Make it shorter.” These are mechanical
source-metadata checks, not independent human relevance judgments.

The existing 44-query retrieval benchmark reran with the actual semantic model:

| Method | P@5 | Recall@5 | MRR@5 | Hard compliance | Mean ms |
|---|---:|---:|---:|---:|---:|
| tfidf | 0.2370 | 0.6265 | 0.6642 | 1.000 | 46.2 |
| semantic | 0.2296 | 0.6188 | 0.6772 | 1.000 | 89.4 |
| hybrid | 0.2445 | 0.6497 | 0.7098 | 1.000 | 81.7 |

The earlier hybrid baseline was P@5 0.1852, Recall@5 0.4491 and MRR@5 0.4250.
Labels are incomplete and developer-authored; new valid candidates can be
unjudged. The data and ranking changed together, so this is a system comparison,
not a controlled attribution of gains to a single component. The 25-conversation
preference field benchmark retained exact match 1.000 on its labeled fields.

First preparation was separate: movie chunk embeddings took **565 seconds** on
this CPU. A later two-record correction reused unchanged document vectors;
book setup took 6.3 seconds including model load and movie setup 14.3 seconds
including new TF-IDF fitting. Normal requests reuse loaded artifacts. Timings
are measurements on this workstation, not hosted-service guarantees.
