# NLP relevance and conversation update

## Implemented changes

- **Coverage:** canonical title/year joins recover 6,382 Wikipedia movie plots,
  up from 6,023. Ampersands, punctuation, accents, articles and source-provided
  alternate titles are normalized; ambiguous source matches are skipped.
- **Book text:** 47 Gutenberg summaries were acquired by exact ebook ID and
  normalized title, restricted to English records with `copyright=false`.
  The source marks these as automatically generated. Their status is displayed
  on cards and details; they are not independently verified plot facts.
  Forty-six attach as new summaries: hosted book descriptions increase from
  20 to 66. No publication year, page count, language or genre is extracted from
  generated prose. The free semantic subset remains 1,000 books/1,500 movies,
  with 1,455 movie plot texts; the title directory covers 19,749 source records.
- **Topic before taste:** pure topic and preference-expanded queries have
  separate lexical/semantic scores. The topic channel contributes 80% of
  initial relevance when a narrative topic exists. A separate small sparse
  title/character-alias field helps entity queries survive long plot documents.
- **Bounded boosts:** genre, mood, theme and learned genre signals multiply
  established relevance, with maxima 12%, 8%, 10% and 4% respectively. A zero
  topic match cannot become relevant solely because the mood matches.
- **Quality selection:** candidates must clear domain-specific topic gates and
  a relative/absolute relevance floor before MMR diversity. Returning fewer
  results or no matches is supported. Filters are never silently relaxed.
- **Query understanding:** factual/filter language such as “published”,
  “English”, “released” and “classic” is excluded from narrative topic gates.
  Adjectival language requests are extracted. Whole entity spellings and
  curated single-token aliases may be corrected; arbitrary words in prose
  are no longer rewritten to resemble catalog titles.
- **Conversation:** explicit **New search** clears old criteria, seen results
  and references while preserving this chat and the selected media format.
  **Follow-up** retains the topic and can append meaningful new details.
  Active criteria and topic are visible/removable. Form changes use the current
  topic, not the stale text of an earlier request. Similarity actions clear an
  unrelated prior topic. Pronouns can refer to the last exact title match.

## Ranking defaults, not learned confidence

`src/relevance.py` holds transparent engineering defaults. Topic gates use
lexical cosine ≥0.045 for books / ≥0.035 for movies, or raw semantic cosine
≥0.30 / ≥0.32 respectively. Subsequent score floors are 0.045 / 0.055 and at
least half the best passing base score. These cutoffs are not probabilities,
independent calibration results or a universally optimal policy. An exact title
lookup uses identity matching separately. Source-generated summaries receive a
0.85 text-quality factor; undescribed metadata records receive 0.65.

When only genres are requested, verified genre matches remain eligible even
without a synopsis. With factual filters alone, metadata completeness and
narrative diversity guide selection, while reported text similarity stays zero.
Unknown metadata still cannot satisfy an explicit factual constraint.

## Executed results

All 107 pytest checks pass. The real HTTP server passed 11 new topic/context/
source-disclosure checks, seven original conversation flows and 42 title cases.
The React build and four JavaScript topic/chip checks pass. Quantized semantic
inference actually ran locally; fallback remains tested separately.

The existing 44-query benchmark uses incomplete developer-authored identities.
Mixed requests are scored per domain, then macro-averaged. The following compares
releases with both data and ranking changes; it does not isolate causal effects:

| Hybrid metric | Before | After |
|---|---:|---:|
| MRR@5 | 0.7639 | 0.7917 |
| Precision among returned items | 0.3963 | 0.4660 |
| Precision@5 (empty slots count) | 0.2926 | 0.2741 |
| Recall@5 | 0.7500 | 0.7222 |
| Returned-record hard compliance | 1.0000 | 1.0000 |

First-hit ranking and judged precision among returned recommendations improve;
P@5 and recall decrease. The new hybrid answers every query-domain case but fills
0.7259 of available slots. Do not call this universal accuracy
improvement. New valid source records may be absent from the relevance labels.
`answer_rate`, slot fill and the old nonempty-compliant-query metric are retained
separately; empty answers are not disguised as returned-record violations or as
successful recommendations.

The source-plot genre experiment was rerun on 6,379 labeled films:
4,081 train, 1,021 validation and
1,277 test. Held-out micro F1 is
0.6833
for plots versus
0.4022
for the same-split title baseline. This is genre classification, not recommender
accuracy. MiniLM remains pretrained and has not been fine-tuned.

## Reproduce

```bash
.venv/bin/python scripts/prepare_nlp_catalog.py --plots-only
.venv/bin/python scripts/enrich_book_summaries.py --pages 64
# Replay locally cached public responses without network:
.venv/bin/python scripts/enrich_book_summaries.py --pages 64 --offline
.venv/bin/python scripts/train_text_genres.py
.venv/bin/python scripts/prepare_compact_catalog.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx \
  .venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
npm --prefix frontend test
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx \
  STORYSCOUT_EVALUATION_DIR=artifacts/compact .venv/bin/python scripts/evaluate.py
.venv/bin/python scripts/verify_relevance_upgrade.py --base-url http://127.0.0.1:8000
```

Bundled cleaned snapshots work without running acquisition. The acquisition
observed repeated timeouts for uncached multi-ID queries and later catalog pages;
12 public pages were cached successfully. The final cache-only run saved 47
summaries and marked the remaining 52 requested pages unavailable. No missing
summaries were fabricated. Future online runs cache responses and stop scheduling
external calls after repeated network failures. See the source manifest.

## Further NLP experiments suggested, not implemented

1. Label desired tone and narrative themes on a small, independently reviewed
   corpus. Compare a trained multi-label mood/theme classifier against the current
   transparent prototype baseline. Distinguish desired mood from user sentiment.
2. Benchmark a retrieval-trained small encoder with its documented query/document
   formatting. Re-embed both media consistently; compare held-out quality, latency
   and peak memory before replacing MiniLM. Do not add untrained prefixes to MiniLM.
3. Annotate harder conversational negation and contrast (“not about war”, “sad
   but hopeful”, “comedy instead of romance”). Evaluate slot extraction and topic
   replacement separately before introducing a small trained intent/slot model.

A cross-encoder reranker is a possible offline experiment, but should not be added
to the 512 MB server without measured relevance gains and resource headroom.

## Documentation references

- [Gutendex API schema and pagination](https://gutendex.com/)
- [Gutenberg source terms and permissions](https://www.gutenberg.org/policy/permission.html)
- [Sentence Transformers semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)
- [Retrieve and rerank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)
