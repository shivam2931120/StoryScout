# StoryScout evaluation summary

Active catalog: book: 10,005, movie: 9,744.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.1778, Recall@5 0.5556, MRR@5 0.484, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1778, Recall@5 0.3426, MRR@5 0.3296, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.1778, Recall@5 0.4491, MRR@5 0.4068, hard-filter compliance 1.0
- Mean search latency after indexing: 16.152 ms; index setup: 134.66 ms

### semantic
Status: measured

- book: P@5 0.163, Recall@5 0.5062, MRR@5 0.4488, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1704, Recall@5 0.2932, MRR@5 0.2994, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.1667, Recall@5 0.3997, MRR@5 0.3741, hard-filter compliance 1.0
- Mean search latency after indexing: 94.087 ms; index setup: 4201.93 ms

### hybrid
Status: measured

- book: P@5 0.1926, Recall@5 0.5617, MRR@5 0.5586, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2074, Recall@5 0.3858, MRR@5 0.3549, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2, Recall@5 0.4738, MRR@5 0.4567, hard-filter compliance 1.0
- Mean search latency after indexing: 100.741 ms; index setup: 177.41 ms

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
