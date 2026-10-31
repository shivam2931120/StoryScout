# Identify a story from remembered plot clues

Select **Identify a story** or write “Identify this movie: …”. Describe events,
characters, settings or unusual objects. Answer the follow-up in the same chat.
Use **New search** or **New discovery** to begin again. Existing visible factual
filters remain active; changing the media selector or preference drawer reruns
identification against those filters.

## Pipeline

1. Rule detection routes identification separately from recommendations. Plot
   mood and genre words do not automatically become preference filters.
2. Local clause splitting extracts up to six clues and marks uncertain memories.
   Optional Nemotron extraction must quote contiguous spans from the user's
   description; invented clues are discarded.
3. Whole-query and per-clue retrieval use local TF-IDF, cached MiniLM embeddings
   when available, and the existing narrative-passage index. A broader hybrid
   recall path avoids recommendation diversity and quality cutoffs hiding a
   potential identity. Hard filters and media selection still apply.
4. At most eight candidates undergo clause-to-passage TF-IDF comparison.
   Nemotron can then assess support and contradictions using only selected source
   excerpts. IDs, clue indexes, verdicts and literal quotes are validated. Missing
   information does not count as contradiction. Model assessments are inferences;
   quote validation alone does not prove entailment.
5. Ranking combines 65% retrieval score, 35% weighted clue coverage and a 40%
   weighted contradiction penalty. Uncertain clues receive half weight. The
   coefficients are explicit heuristics, not fitted confidence estimates. Weak
   alternatives below max(0.08, 55% of the best score) are removed.
6. Results say **possible matches**, display quoted text overlap/support or note
   unverified details, and ask a follow-up. Candidate medium, animation metadata
   and year differences can guide the question. A definite animation or year
   answer narrows subsequent searches; uncertain answers remain soft clues.

## Offline and free-tier behavior

No extra model weights are loaded. Existing TF-IDF, passage and embedding caches
are reused. Two optional NVIDIA requests each have a 12-second timeout and no
retry. If extraction or assessment fails, local extraction/retrieval/evidence
continue. No external provider records are acquired by identification; its
coverage is limited to the local catalog's described records. In particular,
Big Book API availability alone does not add books to this plot index.

## Verification and evaluation

Run:

```bash
.venv/bin/pytest tests/test_identification.py -q
.venv/bin/python scripts/evaluate_identification.py --mode tfidf
# Optional, only report semantic performance if active_modes confirms it ran:
.venv/bin/python scripts/evaluate_identification.py --mode hybrid
```

The benchmark is in `data/identification_queries.json`; actual execution outputs
are saved to `artifacts/identification/`. It contains 12 developer-authored
paraphrases using the small bundled demo catalog. Top-1 accuracy, Hit@3 and MRR@3
use relevant IDs; book/movie ambiguity permits multiple relevant IDs. This is a
small smoke benchmark, not independent evaluation or an accuracy guarantee for
vague memories. Automated tests additionally cover misleading clues, fabricated
model evidence/IDs, absent plots, media/length filters, empty results, clarification,
preference editing and reset. Pretrained embeddings have not been fine-tuned.

Missing catalog coverage, incorrect remembered details and underspecified clues
can prevent identification. The model cannot add an unknown title as a result.

Mixed identification ranks compare per-domain cosine/reranking heuristics; these
scores are not cross-domain calibrated. Unlike the main recommendation evaluation,
this small diagnostic reports a combined top-three identity shortlist.

The compact selection explicitly retains a small documented set of popular
reference titles when existing source plots are available (including Inception).
The 1,500-movie cap is unchanged; omitted or undescribed titles still cannot be
identified from plot text. The selection list is in `prepare_compact_catalog.py`.

A compact-catalog diagnostic used “A thief enters people’s dreams to steal
secrets. He is hired to plant an idea in someone’s mind.” Pure TF-IDF did not
retain a supported match; hybrid MiniLM retrieval plus live Nemotron comparison
retained Inception with both clues supported by source quotes. This is one
diagnostic example, not a general performance estimate. Retrieval also expands
simple inflections against the fitted TF-IDF vocabulary, excluding stop words;
original phrasing remains intact for semantic encoding. Quote validation tolerates
JSON apostrophe escaping, whitespace and typographic quote differences, then
returns an actual source span capped at 200 characters. Incoming quotes up to
500 characters are accepted only when they match both supplied excerpts and the
original plot.
