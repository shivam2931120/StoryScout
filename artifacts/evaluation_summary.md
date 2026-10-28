# StoryScout evaluation summary

Active catalog: book: 10,005, movie: 9,744.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.2889, Recall@5 0.821, MRR@5 0.8519, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1852, Recall@5 0.4321, MRR@5 0.4765, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.237, Recall@5 0.6265, MRR@5 0.6642, hard-filter compliance 1.0
- Mean search latency after indexing: 46.168 ms; index setup: 3420.16 ms

### semantic
Status: measured

- book: P@5 0.3259, Recall@5 0.9074, MRR@5 0.9444, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1333, Recall@5 0.3302, MRR@5 0.4099, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2296, Recall@5 0.6188, MRR@5 0.6772, hard-filter compliance 1.0
- Mean search latency after indexing: 89.428 ms; index setup: 8739.97 ms

### hybrid
Status: measured

- book: P@5 0.3333, Recall@5 0.9259, MRR@5 0.9444, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1556, Recall@5 0.3735, MRR@5 0.4753, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2445, Recall@5 0.6497, MRR@5 0.7098, hard-filter compliance 1.0
- Mean search latency after indexing: 81.724 ms; index setup: 4692.05 ms

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
