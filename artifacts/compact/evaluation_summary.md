# StoryScout evaluation summary

Active catalog: book: 1,000, movie: 1,500.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.2963, Recall@5 0.8333, MRR@5 0.8519, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2074, Recall@5 0.5, MRR@5 0.5704, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2519, Recall@5 0.6666, MRR@5 0.7111, hard-filter compliance 1.0
- Mean search latency after indexing: 11.982 ms; index setup: 866.0 ms

### semantic
Status: measured

- book: P@5 0.3333, Recall@5 0.9259, MRR@5 0.9383, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2444, Recall@5 0.5432, MRR@5 0.5648, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2888, Recall@5 0.7346, MRR@5 0.7515, hard-filter compliance 1.0
- Mean search latency after indexing: 17.356 ms; index setup: 1311.82 ms

### hybrid
Status: measured

- book: P@5 0.3333, Recall@5 0.9259, MRR@5 0.9259, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2519, Recall@5 0.5741, MRR@5 0.6019, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2926, Recall@5 0.75, MRR@5 0.7639, hard-filter compliance 1.0
- Mean search latency after indexing: 17.716 ms; index setup: 1225.69 ms

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
