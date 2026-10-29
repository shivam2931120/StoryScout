# Passage-level narrative matching

StoryScout now searches overlapping parts of the available description or plot,
so a specific detail can influence retrieval even when it is diluted in a
whole-document vector. This is local NLP, using the existing TF-IDF vocabulary
and pretrained MiniLM encoder; no inference API or model fine-tuning is involved.

## Implementation

Narrative text is divided into 112-word windows with 24 words of overlap. Exact
character offsets retain source provenance. Metadata-only catalog placeholders
are excluded. Up to 32 windows are retained per record; longer imported records
are sampled across the text, including both ends, and marked partial. All
currently hosted narratives fit within this limit: zero partially indexed records.

The compact profile has **93 book passages from 66 narrative-bearing books** and
**10,367 movie passages from 1,464 narrative-bearing movies**. This does not create
new books or movies: the retrieval catalog remains 1,000 books and 1,500 movies.
Most expanded book records still lack narrative descriptions and page counts.

The existing fitted TF-IDF vectorizer transforms passages without refitting its
vocabulary or IDF. Each normalized sparse row retains its 64 largest features,
stored as float32. The same MiniLM encoder embeds passages, stored as normalized
float16 vectors in memory-mapped files. Eligible passages are scored in blocks of
512. Original display descriptions and source metadata remain unchanged.

Explicit filters run before passage ranking. A candidate passage needs either
lexical cosine >= 0.12 with at least two matching query features (one for a
single-feature query), or semantic cosine >= 0.40. For each eligible record, its
best supported passage supplies P. The topic score becomes
`max(D, 0.55 * D + 0.45 * P)`, where D is its existing document topic score.
The existing mode-specific cosine calibration, preference channel, topic/quality
gates, bounded preference boosts, and MMR diversification still apply. Pure filter
requests do not receive arbitrary passage bonuses. Many passages yield one card
per title. Cross-media comparisons use the same encoder.

A recommendation affected by a passage includes its ordinal, passage count,
source URL, source-generated flag, and raw cosine values in NLP details. Raw plot
passages are withheld from explanations to avoid exposing endings. Source-generated
book summaries remain explicitly labeled; prose never supplies verified year,
runtime, page count, or warning fields. Similarity is not accuracy or probability.

## Caching and fallback

Sparse caches and passage embeddings are keyed by narrative text, ordered IDs,
window/pruning configuration, vectorizer configuration, and model version.
Unchanged passage embeddings can be reused incrementally. Edited narratives or
configuration changes invalidate relevant artifacts. Model files and large caches
are ignored by Git and prepared during the Docker build. Normal requests do not
re-embed catalog passages. If passage semantic encoding fails, lexical passage
retrieval remains available and is labeled accordingly. Set
`STORYSCOUT_PASSAGE_MATCHING=false` and restart to run the document-only baseline.

## Executed evaluation, 29 October 2026

The within-run ablation uses identical catalog data, encoder and filters, with
query caches cleared between modes. Only passage matching changes. Results for
all three modes and both benchmarks are in
[the comparison](../artifacts/passages/summary.md) and
[full JSON](../artifacts/passages/comparison.json).

| Hybrid benchmark | Document only MRR@5 | With passages MRR@5 | Recall@5 before / after |
|---|---:|---:|---:|
| 10 focal movie queries | 0.7333 | 0.8000 | 0.8000 / 0.8000 |
| 44 broad queries, domain macro average | 0.7824 | 0.7855 | 0.7129 / 0.7037 |

The focal set contains developer-authored paraphrases checked against seven
available movie plots. Moonrise Kingdom moves from third to first for its runaway
pen-pal detail. Groundhog Day and the Moonraker orchid query still miss the target.
Focal answer rate increases from 0.9 to 1.0, but precision among returned cards
falls from 0.5667 to 0.4433. Broad P@5 falls from 0.2703 to 0.2666. All measured
hard-filter compliance values remain 1.0. These incomplete judgments are neither
independent human evaluation nor evidence of universal accuracy improvements.
The synthetic unit fixture separately verifies recovery of a detail outside the
old beginning/middle/end embedding samples.

Validation: **119 pytest tests**, **4 frontend context tests**, production frontend
build, **7 core HTTP scenarios**, **11 relevance/context/source checks**,
**42 title identity checks**, and **7 passage/provenance HTTP checks** passed.
The details dialog was tested in a real browser, including null score fields,
passage provenance and withheld raw text.

The offline Docker container passed those HTTP checks under 512 MiB RAM and
0.1 CPU. Its cgroup peak reached exactly 512 MiB (including reclaimable file
cache); OOM and OOM-kill counts were zero. After the test, anonymous memory was
about 286 MiB and file cache about 181 MiB. This is a tight resource limit, not a
headroom guarantee. No paid service or larger hosting plan is required by this
change. Initial local passage preparation took 3.578 s for books and 403.662 s for
movies with document embeddings already cached; fresh model/document preparation
is additional. Warm local broad hybrid retrieval averaged 19.053 ms; free-host
latency is higher and depends on CPU allocation and idle wake-up.

## Reproduce

From the repository root, using the prepared virtual environment:

```bash
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx .venv/bin/python scripts/build_indexes.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx .venv/bin/python scripts/evaluate_passages.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx .venv/bin/python scripts/evaluate.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/verify_passage_matching.py --base-url http://127.0.0.1:8000
cd frontend
npm test
npm run build
```

Successful versions are recorded in
[dependency_versions.json](../artifacts/passages/dependency_versions.json).
See [Sentence Transformers semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
and [scikit-learn text features](https://scikit-learn.org/stable/modules/feature_extraction.html)
for the underlying embedding and lexical APIs.
