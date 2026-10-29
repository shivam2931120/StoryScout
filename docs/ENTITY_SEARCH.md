# Exact title search and catalog coverage

This revision fixes entity recognition and search routing. Increasing embedding
scores cannot repair a title request that was mistakenly sent to narrative search.
The same pretrained local MiniLM, TF-IDF, passage indexes, genre experiment,
structured preferences, hard filters, and MMR discovery pipeline remain in place.
No pretrained encoder was fine-tuned, and no runtime external API is required.

## Routing policy

1. Normalize case, accents, punctuation, articles, ampersands, source alternate
   titles, and numbered Part I/II/III or Part One/Two/Three forms.
2. Extract title spans from conversational wrappers: Find/Show/Give me, Tell me
   about, I want to read/watch, I am looking for, Do you have, and polite variants.
   A named-title request containing genre words remains a title request.
3. Resolve exact local title/identity aliases before interpreting title words as
   moods, genres or negation. Author qualifiers and release years narrow matches.
   Explicit book/movie wording overrides inherited format selection.
4. Contiguous multiword title fragments, such as Harry Potter, produce a clearly
   labeled partial-title list, not an invented franchise identity or unrelated
   recommendations. Distinct media, authors and release years remain choices.
5. Close spellings are labeled suggestions and require selection; they are not
   automatically claimed as exact identities or selected reference narratives.
6. Short unresolved entity phrases and explicitly named missing titles report
   the lookup failure without narrative substitutes. Ambiguous bare phrases can
   be clarified with “stories about …”. This is conservative rule-based routing,
   not a trained named-entity or intent model. Its language coverage is limited.
7. Known character aliases, descriptive themes, mood/genre requests, numeric
   constraints and reference requests continue through the local NLP pipeline.
   Unknown reference titles cannot silently become weak fuzzy matches to another
   story. A misspelled reference yields choices before similarity search.

Title lookup does not promise preference compliance. An exact title remains
visible even if its runtime or unknown language conflicts with current filters;
the card states those conflicts. Filtered recommendations still enforce every
hard constraint. Numeric filter suffixes attached to a recognized title update
their own preference fields and expose conflicts. Words inside titles do not
become preferences. Follow-up topics/filters are retained until explicitly changed.

The UI labels **Exact title**, **Partial title · choose a match**, and **Spelling
suggestion**. Identity cards have no fabricated semantic score. Source excerpts,
original developer paraphrases, source-generated summaries, and optional AI
paraphrases have separate provenance/status labels.

## Source coverage

The full local directory now contains **19,793 records: 10,025 books and 9,768
movies**. Retrieval stays at **1,000 books and 1,500 movies** for free hosting.
The new source snapshot contains 20 books and 25 movies; one movie duplicates an
existing identity, so it adds 44 unique records. This is targeted coverage work,
not a claim that all popular titles or all recent releases are included.

Open Library exact-title/author searches and work pages supply book identity,
author strings, source aliases and attributed description excerpts of at most
50 words. We found unreliable edition-aggregated first publication years; those
reported values remain in provenance and the actual year field is unknown.
Book pages and original language are unknown unless a separate verified source
exists. No median edition length or translated-edition language is treated as
verified work metadata. Source descriptions may contain contributor errors.

Wikidata CC0 film identities/release dates are acquired from the public QLever
mirror. Direct Wikimedia requests were blocked in this environment. A bounded
class-label query includes animated film types and avoids expensive transitive
queries; HTTP 429 responses receive a bounded Retry-After/backoff. Eight films
have original short descriptions checked against linked distributor synopses.
Some additional metadata comes from explicit distributor film details. Top Gun:
Maverick was absent from the queried mirror snapshot, so its identity/year and
short description use Paramount's linked distributor entry. No model invents
facts to fill source gaps. Remaining metadata-only films are searchable identities
but do not acquire a fabricated plot. Source links/rights are in DATA_SOURCES.md.

Current indexed narrative coverage: **86 books and 1,464 movies**, represented by
**113 book passages and 10,327 movie passages**. Adding modern short descriptions
changes some compact candidates; it does not magically create full plot coverage.
Unknown metadata still cannot satisfy an explicit constraint.

## Actual verification

The new benchmark has 45 developer-authored requests, each executed fresh and
with inherited Dark/English/90-minute context: **90 routing/identity checks**.
It includes conversational wording, exact/source aliases, partial franchises,
misspellings, missing titles, wrong media/year, unknown references and discovery
controls. Canonical title comparison handles catalog trailing articles. The old
response format is treated fairly as exact unless it explicitly labels a spelling
suggestion; the benchmark does not require a new response field to pass old code.

The prior deployed revision passed **24/90**. The updated local app passed
**90/90**. Code and coverage changed together, so this is an application regression
comparison, not an isolated training experiment or universal accuracy figure.
Results: artifacts/entity_search/before.json and local.json. The existing 42-case
identity check now includes the newly available Orwell book alias and still passes.

**170 pytest tests**, **4 frontend checks**, production React build, **7 core HTTP
scenarios**, **11 topic/context/source checks**, **42 identity checks**, and **7
passage/provenance checks** passed locally. The 90 new HTTP checks also pass.
Serving and source acquisition are separate; offline operation uses committed
snapshots and prepared local model/index artifacts.

The broad 44-query recommendation benchmark was rerun with the expanded compact
catalog. Hybrid P@5 is **0.2666**, Recall@5 **0.7037**, MRR@5 **0.7670**, and hard
compliance **1.0**. Its previous MRR was 0.7855: the current incomplete labels do
not show a universal recommendation gain. New/unjudged candidates affect ranks.
The controlled passage ablation on the new catalog retains focal-detail MRR@5
**0.7333 -> 0.8000**; broader passage macro MRR is **0.7639 -> 0.7670**. Full results
are in artifacts/compact/ and artifacts/passages/. Earlier passage outputs are
preserved under artifacts/passages/previous_revision/. No benchmark numbers are
presented as probabilities or confidence scores.

## Reproduce

```bash
.venv/bin/python scripts/expand_title_coverage.py
.venv/bin/python scripts/prepare_compact_catalog.py
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx .venv/bin/python scripts/build_indexes.py
.venv/bin/python -m pytest -q
STORYSCOUT_CATALOG_PROFILE=compact STORYSCOUT_EMBEDDING_BACKEND=onnx .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
# In another terminal:
.venv/bin/python scripts/evaluate_entity_search.py
.venv/bin/python scripts/verify_api.py
```

The importer uses the bounded requests in data/catalog/coverage_requests.json and
reviewed distributor descriptions/facts in editorial_descriptions.json. Cached
responses avoid repeated acquisition calls; committed source snapshots allow
running without these services. Dependencies remain pinned in requirements-free.txt.

Browser validation also passed conversational Inception lookup (one exact-title
card), a labeled Interstellar typo suggestion, and an explicitly missing title
without new recommendation cards. No JavaScript errors were observed.

The added source catalog also passed **45/45** identity/media/year round trips
through the HTTP API (`scripts/verify_catalog_coverage.py`, measured output in
`artifacts/entity_search/coverage.json`). This caught and fixed over-stripping
literal words in names such as “The Book Thief” and “The Book of Eli”. The
extractor checks an entire candidate title before stripping another format noun.
The final 90-case route benchmark was rerun after this fix and still passes.
Docker separates artifact dependencies from runtime routing files so future
identity-only fixes do not invalidate the expensive NLP preparation stage.
