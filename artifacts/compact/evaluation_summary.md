# StoryScout evaluation summary

Active catalog: book: 1,000, movie: 1,500.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.2741, Recall@5 0.7593, MRR@5 0.8056, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1852, Recall@5 0.5031, MRR@5 0.6049, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2297, Recall@5 0.6312, MRR@5 0.7052, hard-filter compliance 1.0
- Mean search latency after indexing: 18.641 ms; index setup: 1007.9 ms

### semantic
Status: measured

- book: P@5 0.2963, Recall@5 0.8333, MRR@5 0.8519, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.1926, Recall@5 0.4784, MRR@5 0.6031, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2445, Recall@5 0.6559, MRR@5 0.7275, hard-filter compliance 1.0
- Mean search latency after indexing: 17.714 ms; index setup: 1577.2 ms

### hybrid
Status: measured

- book: P@5 0.3037, Recall@5 0.8457, MRR@5 0.8704, hard-filter compliance 1.0 (27 domain queries)
- movie: P@5 0.2296, Recall@5 0.5617, MRR@5 0.6636, hard-filter compliance 1.0 (27 domain queries)
- Domain macro average: P@5 0.2666, Recall@5 0.7037, MRR@5 0.767, hard-filter compliance 1.0
- Mean search latency after indexing: 21.136 ms; index setup: 1618.94 ms

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
