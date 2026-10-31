# StoryScout evaluation summary

Active catalog: book: 1,000, movie: 1,500.
Retrieval benchmark: 44 developer-authored queries. Relevance labels are metadata-based and not independently human-rated.

Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged. Bootstrap intervals are clustered by query text and describe this labeled sample only.

## Retrieval

### tfidf
Status: measured

- book: P@5 0.2741, Recall@5 0.7593, MRR@5 0.8056, nDCG@5 0.733, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.6667, 0.9259])
- movie: P@5 0.1852, Recall@5 0.5031, MRR@5 0.6049, nDCG@5 0.4662, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.4537, 0.75])
- Domain macro average: P@5 0.2297, Recall@5 0.6312, MRR@5 0.7052, hard-filter compliance 1.0
- Mean search latency after indexing: 11.726 ms; index setup: 956.03 ms
- Per-category metrics are in `evaluation_results.json` under `by_category`.

### semantic
Status: measured

- book: P@5 0.2963, Recall@5 0.8333, MRR@5 0.8519, nDCG@5 0.7902, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.7407, 0.9444])
- movie: P@5 0.1926, Recall@5 0.4784, MRR@5 0.6031, nDCG@5 0.4616, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.4401, 0.7698])
- Domain macro average: P@5 0.2445, Recall@5 0.6559, MRR@5 0.7275, hard-filter compliance 1.0
- Mean search latency after indexing: 21.908 ms; index setup: 1708.31 ms
- Per-category metrics are in `evaluation_results.json` under `by_category`.

### hybrid
Status: measured

- book: P@5 0.3037, Recall@5 0.8457, MRR@5 0.8704, nDCG@5 0.8097, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.7593, 0.963])
- movie: P@5 0.2296, Recall@5 0.5617, MRR@5 0.6636, nDCG@5 0.532, hard-filter compliance 1.0 (27 domain queries; MRR 95% interval [0.5309, 0.7963])
- Domain macro average: P@5 0.2666, Recall@5 0.7037, MRR@5 0.767, hard-filter compliance 1.0
- Mean search latency after indexing: 22.075 ms; index setup: 1519.25 ms
- Per-category metrics are in `evaluation_results.json` under `by_category`.

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
