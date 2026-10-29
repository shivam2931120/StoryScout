# Title identity and content recommendations

The deployed compact catalog originally omitted *Love and Other Drugs*. The
chat path also treated bare titles as description queries. Its words were ranked
alongside the inherited Dark mood, producing unrelated films. TF-IDF was not
rejecting an exact title: the record was absent from that index and there was no
separate title lookup path.

Title lookup now runs before preference interpretation. It uses a local compressed
metadata directory covering all 10,005 book and 9,744 movie source records. Case,
punctuation, accents, initial/trailing articles and `&`/`and` are normalized.
An optional trailing release year narrows remakes. Close spelling suggestions are
labeled as suggestions. Character/topic search aliases are excluded from title identity
matching and remain signals for NLP discovery. Identical media/title/year records are deduplicated,
preferring active/demo records. Several distinct matches remain visible as cards;
opening the intended card selects its details and similarity actions.

A title lookup does not change mood, language, length limits or the conversation's
previous discovery topic. Words inside titles such as *The Dark Knight*, *The Big
Short* and *No Country for Old Men* do not become preference instructions.
Explicit `Find a movie called ...` searches with no match report the missing title.
Ordinary topic requests continue through the NLP recommendation pipeline.

Cards under **Matching titles** are identity results, not filtered recommendations.
Any hard-filter conflict or unknown constrained metadata is stated on the card.
They have no fabricated similarity score. All recommendation searches still use
hard filters and the existing local TF-IDF, MiniLM, genre, mood and diversity
pipeline over the 1,000-book/1,500-movie compact semantic catalog. The full title
directory does not imply full semantic indexing or complete plot coverage.

A source-linked synopsis is displayed only when available. Similarity actions can
use directory entries outside the compact index; when a reference has no sourced
synopsis, its catalog genres/metadata are used and the explanation states that
narrative similarity is limited. No API-generated plot facts are added.

Run:

```bash
.venv/bin/python scripts/prepare_compact_catalog.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/evaluate_title_lookup.py --base-url http://127.0.0.1:8000
```

The executed local HTTP benchmark passed **42/42** cases (21 queries, each fresh
and with inherited Dark/English/runtime preferences). Expected identities are
listed in `data/title_lookup_evaluation.json`; actual IDs and timings are in
`artifacts/title_lookup_results.json`. These developer-authored identity checks
are separate from the incomplete relevance judgments used for Precision@5,
Recall@5 and MRR@5. They do not measure universal title coverage or independent
human recommendation quality. Titles absent from the source catalog cannot be
looked up offline.

Validation also passed all **93 pytest tests** and **seven HTTP conversation
scenarios**, covering books, movies, mixed results, both cross-media directions,
refinement and reset. The React production build succeeded.

The last unambiguous exact title is retained as reference context for pronouns
such as “books like it”. An explicit similarity action discards an unrelated
prior topic while keeping visible filters; New search clears prior criteria.

## Conversational title search revision

Exact title extraction, source aliases, franchise choices, spelling suggestions,
missing-title handling, and source-backed modern coverage are implemented. See
[the current policy, executed checks, and limitations](ENTITY_SEARCH.md).
