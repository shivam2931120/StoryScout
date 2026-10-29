# StoryScout evaluation summary

Active catalog: book: 1,000, movie: 1,500.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.2741, Recall@5 0.7593, MRR@5 0.8056, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1852, Recall@5 0.5031, MRR@5 0.6852, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2297, Recall@5 0.6312, MRR@5 0.7454, hard-filter compliance 1.0
- Mean search latency after indexing: 11.398 ms; index setup: 1995.62 ms

### semantic
Status: measured

- book: P@5 0.2963, Recall@5 0.8333, MRR@5 0.8642, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1926, Recall@5 0.4784, MRR@5 0.6031, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2445, Recall@5 0.6559, MRR@5 0.7336, hard-filter compliance 1.0
- Mean search latency after indexing: 19.982 ms; index setup: 2013.14 ms

### hybrid
Status: measured

- book: P@5 0.3111, Recall@5 0.8642, MRR@5 0.8642, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2296, Recall@5 0.5617, MRR@5 0.7006, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2703, Recall@5 0.7129, MRR@5 0.7824, hard-filter compliance 1.0
- Mean search latency after indexing: 17.777 ms; index setup: 1216.32 ms

## Preference extraction

25 developer-authored labeled conversations; overall field exact match 1.0.

| Field | Exact match | Support |
|---|---:|---:|
| desired_mood | 1.0 | 4 |
| excluded_genres | 1.0 | 8 |
| language | 1.0 | 1 |
| max_pages | 1.0 | 7 |
| max_runtime | 1.0 | 7 |
| max_year | 1.0 | 2 |
| media | 1.0 | 25 |
| min_year | 1.0 | 2 |
| positive_content | 1.0 | 3 |
| preferred_genres | 1.0 | 5 |
| themes | 1.0 | 3 |

Limitations: labels are developer-authored and incomplete; valid results outside the judged IDs can be undercounted. Semantic metrics are omitted unless the model actually ran.
