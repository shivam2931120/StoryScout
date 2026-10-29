# StoryScout project report

## Abstract

StoryScout is a local-first conversational book and movie recommender. It combines rule-based intent and preference extraction, hard metadata filters, TF-IDF retrieval, shared CPU sentence embeddings, cross-media title similarity, local plot keyphrases, supervised genre classification, semantic mood/theme signals, diverse ranking, and catalog-grounded explanations in a React application connected to the Python NLP engine through FastAPI. The original Streamlit interface is retained as an alternative.

## Introduction and problem statement

People often describe the kind of story they want in everyday language and refine the request over several turns. Separate catalog filters make those refinements cumbersome. StoryScout keeps a compact conversation state and applies the same discovery flow to books and movies.

## Objectives and related approaches

The project demonstrates NLP through intent recognition, negation-aware information extraction, text normalization, lexical and semantic information retrieval, multi-label genre classification, and evaluation. It does not implement collaborative filtering, ratings prediction, or user-behavior learning. Optional Nemotron query interpretation may clarify a request; catalog records and final recommendations remain local and evidence-based.

## Dataset

The app includes a curated demo set of 14 books and 13 movies, 10,000 English Project Gutenberg catalog records, and 9,737 MovieLens latest-small movie records. The original public catalogs contain metadata. This revision supplements them with 6,382 original Wikipedia plots joined by exact title/year, plus source-backed runtime/language fields. There are 1,322 known movie runtimes and 1,334 known movie languages. Derived subject mappings cover 1,815 books, separately from catalog genres. Fifty-six records currently have short Nemotron paraphrases sourced from exact-title Wikipedia article leads; source URL, model, AI provenance, and Wikipedia attribution are stored separately. Forty-seven source-provided Gutenberg summaries (explicitly labeled automatically generated, not independently verified) now supplement book text. The hosted book description count increases from 20 to 66, without deriving factual fields from generated prose. Gutenberg provides titles, author strings, languages, and subject fields; MovieLens provides titles, years when present, and genres. Book page counts remain known for only 12 records. Other unavailable lengths, years, cast, and content warnings remain unknown. Demo metadata is kept distinct from public-source metadata. No ebook text, ratings, or user profiles are included. Source usage conditions and citations are in `DATA_SOURCES.md`.

## Architecture and methodology

The React chat sends validated conversation state to FastAPI, which passes user text through an interpretable rule baseline, structured dataclass preferences, title resolution, domain-specific hard filters, and a shared retrieval interface. Exact and fuzzy title resolution supports book-to-movie and movie-to-book requests. Reference context includes the selected record's description and metadata; a similarity is not an adaptation claim.

The lexical baseline uses word and bigram TF-IDF with cosine similarity. `sentence-transformers/all-MiniLM-L6-v2` produces normalized CPU embeddings for both catalogs. Semantic cosine below 0.18 is mapped to zero; values from 0.18 to 0.62 are mapped to [0, 1]. Hybrid retrieval combines these calibrated scores with fixed 45% lexical and 55% semantic weights. Separate topic and preference queries are scored. Hard constraints run first; topic gates and quality floors run before bounded multiplicative preference boosts and MMR diversity. Exact title identity lookup is separate, and source-generated summary provenance remains visible. Explicit new searches clear prior criteria, while follow-ups retain a removable topic. Selected genres match any source genre or documented subject mapping. Mood/theme prototypes and the plot classifier provide soft ranking signals. Unknown metadata cannot pass a year or length constraint, and unknown genres cannot pass an explicit genre exclusion. Explanation text cites supported genres, subjects, years, language, length, and similarity only.

## Actual evaluation results

The retrieval benchmark contains 44 developer-authored queries, including both domains, mixed requests, cross-media and same-media references, and constraints. Because relevance judgments are incomplete and hand-authored, metrics indicate performance only against those labels; unjudged catalog records may be relevant. Mixed requests are scored independently by domain, then book and movie metrics are macro-averaged.

On the currently hosted compact subset (1,000 books and 1,500 movies), quantized ONNX MiniLM actually ran. The full 10,005-book/9,744-movie sources remain available for offline preparation. Current measured results:

| Method | P@5 | Recall@5 | MRR@5 | Returned precision | Hard compliance | Mean ms |
|---|---:|---:|---:|---:|---:|---:|
| tfidf | 0.2297 | 0.6312 | 0.7454 | 0.4689 | 1.0000 | 10.2 |
| semantic | 0.2445 | 0.6559 | 0.7429 | 0.4405 | 1.0000 | 25.8 |
| hybrid | 0.2741 | 0.7222 | 0.7917 | 0.4660 | 1.0000 | 19.5 |

The prior compact hybrid measured MRR@5 0.7639, P@5 0.2926 and Recall@5 0.7500. The current hybrid improves first-hit rank and precision among returned recommendations, while P@5 and recall decrease because weak matches are withheld and the source catalog changed. This is not an isolated ablation or a universal accuracy guarantee. All query-domain cases are answered by the hybrid; slot fill is 0.7259. Hard compliance measures returned records, with answer coverage reported separately. The complete comparison, source limitations and pipeline defaults are in `NLP_RELEVANCE_UPDATE.md`.

Preference extraction reached 1.000 field exact match over 25 developer-authored conversation examples (33 messages). Some fields have low support, as recorded in the JSON. No human relevance ratings have been submitted. The Evaluation page now exports candidate results for human annotation and separately summarizes uploaded ratings.

The current executed genre experiment uses 6,379 plot-bearing movies and
plot-hash-grouped splits: 4,081 train, 1,021 validation, 1,277 test. TF-IDF fitting
and logistic-regression training use development data only; threshold selection
uses validation only. The plot model's held-out micro F1 is **0.6833**, versus
**0.4022** for a title-only baseline on the same test IDs. Full per-label
precision/recall/F1 and support are in `artifacts/genre_text_results.json`.
Predictions remain separate from catalog genres and provide bounded soft ranking
evidence. MiniLM itself is not trained. Book classification remains unsupported
because source genre labels are insufficient. The old title-only experiment is
retained as a historical artifact, not the current NLP implementation.

The executed preference-search regression compared five genre form edits with
the same 120-minute limit: distinct titles increased from 5 to 25, and source-genre
precision@5 from 0.28 to 1.00. All runtime/genre constraints and nonrepeating
next-pick checks passed. This measures filter behavior, not subjective relevance.

Quantized MiniLM inference ran successfully on CPU using the same pretrained encoder for both domains. The full local environment also supports Sentence Transformers/PyTorch. The app reports the active retrieval method and uses the cached model with local-only loading when available. See `artifacts/compact/evaluation_summary.md` and `artifacts/genre_text_results.json` for complete current outputs.

## Limitations

Public-source metadata is uneven: most expanded book records still lack descriptions, publication years, page counts, and source genre labels; MovieLens has no plot, language, runtime, director, cast, or warnings. Source-backed plots and metadata now supplement MovieLens, while book text/page coverage remains limited. Unknowns remain unknown. Authored relevance labels are incomplete. No independent human evaluation has yet been collected. The original interface was deployed on Streamlit Community Cloud. The React/FastAPI interface is deployed publicly as one free Render Docker service with a compact catalog and quantized local semantic encoder: https://storyscout-eaw7.onrender.com. Browser conversations and saved items are local to each device, without account synchronization.

## Future scope

Collect human relevance labels through the included workflow and expand source-backed descriptions in bounded batches. Any added source must preserve its license terms and field provenance.

## References

- Harper, F. M., and Konstan, J. A. (2015). “The MovieLens Datasets: History and Context.” ACM TiiS 5(4). [doi:10.1145/2827872](https://doi.org/10.1145/2827872).
- [Project Gutenberg offline catalog documentation](https://www.gutenberg.org/ebooks/offline_catalogs.html) and [catalog data policy](https://www.gutenberg.org/policy/robot_access.html).
- [Sentence Transformers API documentation](https://sbert.net/docs/package_reference/sentence_transformer/model.html).
- [NVIDIA Nemotron 3.5 Lightning model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b) and [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Terms_of_Use).
- scikit-learn documentation for [TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [OneVsRestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html), and [classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html).


## Free-tier deployment revision

The deployment now uses a deterministic 1,000-book / 1,500-movie subset and the
official quantized MiniLM ONNX encoder, preserving local semantic NLP while
reducing memory. The full local source corpus and Sentence Transformers runtime
remain available. The compact 44-query benchmark measured hybrid P@5 0.2926,
Recall@5 0.7500, MRR@5 0.7639 and hard-filter compliance 1.000. This is a smaller
candidate-pool experiment; it is not a controlled quantization improvement claim.
Candidate container checks passed under 512 MB / 0.1 CPU, with observed memory
around 304 MiB and seven successful HTTP scenarios. Current results, resource
checks and deployment status are recorded in FREE_HOSTING.md and artifacts/compact/.
