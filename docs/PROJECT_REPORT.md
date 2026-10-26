# StoryScout project report

## Abstract

StoryScout is a local-first conversational book and movie recommender. It combines rule-based intent and preference extraction, hard metadata filters, TF-IDF retrieval, shared CPU sentence embeddings, cross-media title similarity, source-backed AI-paraphrased descriptions, and catalog-grounded explanations in a single Streamlit application.

## Introduction and problem statement

People often describe the kind of story they want in everyday language and refine the request over several turns. Separate catalog filters make those refinements cumbersome. StoryScout keeps a compact conversation state and applies the same discovery flow to books and movies.

## Objectives and related approaches

The project demonstrates NLP through intent recognition, negation-aware information extraction, text normalization, lexical and semantic information retrieval, multi-label genre classification, and evaluation. It does not implement collaborative filtering, ratings prediction, or user-behavior learning. Optional Nemotron query interpretation may clarify a request; catalog records and final recommendations remain local and evidence-based.

## Dataset

The app includes a curated demo set of 14 books and 13 movies, 10,000 English Project Gutenberg catalog records, and 9,737 MovieLens latest-small movie records. The public catalogs mostly contain metadata, not plot summaries. Fifty-six records currently have short Nemotron paraphrases sourced from exact-title Wikipedia article leads; source URL, model, AI provenance, and Wikipedia attribution are stored separately. Gutenberg provides titles, author strings, languages, and subject fields; MovieLens provides titles, years when present, and genres. Page counts, runtimes, directors, cast, most years, and content warnings remain unknown. Demo metadata is kept distinct from public-source metadata. No ebook text, ratings, or user profiles are included. Source usage conditions and citations are in `DATA_SOURCES.md`.

## Architecture and methodology

One Streamlit chat passes user text through an interpretable rule baseline, structured dataclass preferences, title resolution, domain-specific hard filters, and a shared retrieval interface. Exact and fuzzy title resolution supports book-to-movie and movie-to-book requests. Reference context includes the selected record's description and metadata; a similarity is not an adaptation claim.

The lexical baseline uses word and bigram TF-IDF with cosine similarity. `sentence-transformers/all-MiniLM-L6-v2` produces normalized CPU embeddings for both catalogs. Semantic cosine below 0.18 is mapped to zero; values from 0.18 to 0.62 are mapped to [0, 1]. Hybrid retrieval combines these calibrated scores with fixed 45% lexical and 55% semantic weights. Hard constraints run first. Unknown metadata cannot pass a year or length constraint, and unknown genres cannot pass an explicit genre exclusion. Explanation text cites supported genres, subjects, years, language, length, and similarity only.

## Actual evaluation results

The retrieval benchmark contains 44 developer-authored queries, including both domains, mixed requests, cross-media and same-media references, and constraints. Because relevance judgments are incomplete and hand-authored, metrics indicate performance only against those labels; unjudged catalog records may be relevant. Mixed requests are scored independently by domain, then book and movie metrics are macro-averaged.

On the active deduplicated catalogs (10,005 books and 9,744 movies), the executed TF-IDF run measured macro Precision@5 **0.1704**, Recall@5 **0.4244**, MRR@5 **0.4031**, and hard-constraint compliance **1.000**. Mean retrieval latency after indexing was 13.600 ms. Sentence embeddings actually ran: semantic-only retrieval measured **0.1593 / 0.3873 / 0.3710** for macro P@5 / Recall@5 / MRR@5; hybrid measured **0.1852 / 0.4491 / 0.4250**, with hard-constraint compliance **1.000**. Mean query latency was 86.470 ms for semantic and 85.417 ms for hybrid. The first semantic index preparation after the final catalog change took 108.816 seconds; cached hybrid preparation was 234 ms. These values come from `artifacts/evaluation_results.json`; they should not be interpreted as general recommendation accuracy.

Preference extraction reached 1.000 field exact match over 25 developer-authored conversation examples (33 messages). Some fields have low support, as recorded in the JSON. No human relevance ratings have been submitted. The Evaluation page now exports candidate results for human annotation and separately summarizes uploaded ratings.

The executed title-only, one-vs-rest logistic regression genre experiment used 9,744 movies, a fixed 80/20 split (`random_state=42`), training-only TF-IDF, and a training support cutoff of 20. Held-out micro precision/recall/F1 were **0.3175 / 0.4708 / 0.3792**; macro were **0.2303 / 0.3608 / 0.2737**; weighted were **0.3647 / 0.4708 / 0.4053**. It uses title text only, does not append genre labels to inputs, and is an experiment rather than the app's genre source. Book classification was skipped because the available book records contain no genre labels outside the tiny demo set.

Sentence Transformers ran successfully on CPU using the same model for both domains. The app reports the active retrieval method and uses the cached model with local-only loading when available. See `artifacts/evaluation_summary.md` and `artifacts/genre_classifier_results.json` for complete outputs.

## Limitations

Public-source metadata is uneven: the expanded book source has no plot descriptions, publication years, page counts, or genres; MovieLens has no plot, language, runtime, director, cast, or warnings. Only two records currently have source-backed short descriptions. This limits filtering and semantic recall, and unknowns remain unknown. Authored relevance labels are incomplete. No independent human evaluation has yet been collected. The repository is deployed through Streamlit Community Cloud by the project owner; the hosted build after the latest dependency and data changes could not be inspected from this environment.

## Future scope

Collect human relevance labels through the included workflow and expand source-backed descriptions in bounded batches. Any added source must preserve its license terms and field provenance.

## References

- Harper, F. M., and Konstan, J. A. (2015). “The MovieLens Datasets: History and Context.” ACM TiiS 5(4). [doi:10.1145/2827872](https://doi.org/10.1145/2827872).
- [Project Gutenberg offline catalog documentation](https://www.gutenberg.org/ebooks/offline_catalogs.html) and [catalog data policy](https://www.gutenberg.org/policy/robot_access.html).
- [Sentence Transformers API documentation](https://sbert.net/docs/package_reference/sentence_transformer/model.html).
- [NVIDIA Nemotron 3.5 Lightning model card](https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b) and [Wikimedia reuse terms](https://foundation.wikimedia.org/wiki/Terms_of_Use).
- scikit-learn documentation for [TfidfVectorizer](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [OneVsRestClassifier](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html), and [classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html).
