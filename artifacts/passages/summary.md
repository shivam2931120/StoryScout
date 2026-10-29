# Passage retrieval ablation

Within-run ablation; identical data, encoder, query-cache reset and hard filters. Only passage_matching differs.

Developer-authored focal-detail paraphrases verified against the cached source plot text. Relevant IDs are incomplete; not independent human evaluation.

Seven known movies, selected for available narrative text. These queries are not representative of all users and do not establish general accuracy.

| Method | Passages | Benchmark/domain | P@5 | Recall@5 | MRR@5 | Returned precision | Hard compliance |
|---|---|---|---:|---:|---:|---:|---:|
| tfidf | whole_document | broad/book | 0.2741 | 0.7593 | 0.8056 | 0.5667 | 1.0 |
| tfidf | whole_document | broad/movie | 0.1852 | 0.5031 | 0.6481 | 0.3942 | 1.0 |
| tfidf | whole_document | focal/movie | 0.18 | 0.9 | 0.8333 | 0.7167 | 1.0 |
| semantic | whole_document | broad/book | 0.2963 | 0.8333 | 0.8457 | 0.5975 | 1.0 |
| semantic | whole_document | broad/movie | 0.1926 | 0.4784 | 0.6031 | 0.2438 | 1.0 |
| semantic | whole_document | focal/movie | 0.14 | 0.7 | 0.65 | 0.49 | 1.0 |
| hybrid | whole_document | broad/book | 0.3111 | 0.8642 | 0.8642 | 0.6309 | 1.0 |
| hybrid | whole_document | broad/movie | 0.2296 | 0.5617 | 0.6636 | 0.3 | 1.0 |
| hybrid | whole_document | focal/movie | 0.16 | 0.8 | 0.7333 | 0.51 | 1.0 |
| tfidf | passages | broad/book | 0.2741 | 0.7593 | 0.8056 | 0.5667 | 1.0 |
| tfidf | passages | broad/movie | 0.1852 | 0.5031 | 0.6049 | 0.3942 | 1.0 |
| tfidf | passages | focal/movie | 0.18 | 0.9 | 0.9 | 0.7167 | 1.0 |
| semantic | passages | broad/book | 0.2963 | 0.8333 | 0.8519 | 0.6025 | 1.0 |
| semantic | passages | broad/movie | 0.1926 | 0.4784 | 0.6031 | 0.2438 | 1.0 |
| semantic | passages | focal/movie | 0.16 | 0.8 | 0.6533 | 0.46 | 1.0 |
| hybrid | passages | broad/book | 0.3037 | 0.8457 | 0.8704 | 0.6253 | 1.0 |
| hybrid | passages | broad/movie | 0.2296 | 0.5617 | 0.6636 | 0.2938 | 1.0 |
| hybrid | passages | focal/movie | 0.16 | 0.8 | 0.8 | 0.4433 | 1.0 |
