# Data sources and limitations

The bundled CSVs contain 14 books and 13 movies in a small, curated demonstration catalog. Their descriptions are short project-written summaries, not copied long plot text. `source=demo` and `tag_provenance=curated demo metadata` mark that origin. Unknown metadata remains blank. The app marks warning metadata as incomplete; a missing warning is not proof of safety.

## MovieLens catalog

`data/source/movielens/` contains the source `movies.csv`, `links.csv`, and license/readme copied from MovieLens latest-small. `python scripts/import_movielens.py` reproducibly creates `data/expanded/movies.csv`; the normalized catalog contains 9,737 unique title/year records (out of 9,742 source rows; malformed or duplicate title/year rows are excluded). It stores MovieLens IDs, listed genres, the year only when present in the source title, and MovieLens links. Language, plot, director, runtime, cast, and warnings are unknown. A short display-only notice explains the missing plot; the notice is excluded from retrieval text, so it cannot masquerade as plot evidence. App-level duplicates use normalized title+year for movies and normalized title+author for books; demo records take precedence on an identity collision.

MovieLens is supplied for research under its stated conditions: no commercial/revenue-bearing use without permission, acknowledge the dataset in resulting publications, do not imply University of Minnesota/GroupLens endorsement, and redistribute transformations under the same conditions. Cite F. Maxwell Harper and Joseph A. Konstan (2015), “The MovieLens Datasets: History and Context,” ACM TiiS 5(4), DOI [10.1145/2827872](https://doi.org/10.1145/2827872). The source describes this as a development dataset, not a shared research benchmark. Its 2018 snapshot has title/year/genre only and incomplete coverage. See the included `README.txt` and the [GroupLens dataset page](https://grouplens.org/datasets/movielens/latest/).

The normalized schema is: `id`, `title`, `description`, `genres` (pipe-separated), `language`, `year`, `source`, `source_url`, `mood_tags`, `theme_tags`, `tag_provenance`, plus book fields `authors`, `page_count`, `publisher`, or movie fields `director`, `runtime_minutes`, `cast`, `verified_warnings`. Unknown values are blank and stay unknown.

## Optional sourced short descriptions

`data/enriched/descriptions.csv` is a separate, additive file for records whose original catalog has no synopsis. The current snapshot contains 56 descriptions (6 books and 50 movies). `scripts/enrich_descriptions.py` searches English Wikipedia for an exact normalized title, retrieves the article lead through the MediaWiki API, and asks the configured Nemotron model to paraphrase only that provided text in at most 40 words. The prompt forbids adding facts from model memory; empty or ungrounded responses are discarded. Each row stores the catalog ID, generated description, Wikipedia page URL, model ID, and AI provenance. The app uses these descriptions in search documents while retaining the original MovieLens or Gutenberg source fields. It labels the summary as AI-generated and links the source.

No Wikipedia match means no generated summary. The script can be run incrementally, with a default maximum of 100 candidate lookups per medium; use `--item-id` for targeted records or increase `--max-candidates-per-domain` in bounded batches. It caches source lookups under ignored `artifacts/.cache/`, so repeated runs do not repeat requests. Configure `NVIDIA_API_KEY` in the environment or ignored `.streamlit/secrets.toml`; the key is never written into catalog files. Wikipedia text and paraphrases are attributed to their source URL and distributed under CC BY-SA 4.0; see [Wikimedia's reuse terms](https://foundation.wikimedia.org/wiki/Terms_of_Use) and [MediaWiki search API](https://www.mediawiki.org/wiki/API:Search). Review each source before using the generated text.

## Project Gutenberg catalog

`data/source/gutenberg/pg_catalog.csv.gz` is the official compressed machine-readable catalog snapshot. Rebuild the book subset with `python scripts/import_gutenberg_catalog.py`; `--limit 10000` is the default. The importer selects English text records with subject metadata, then uses a stable SHA-256 sample so the first catalog IDs do not dominate. `--refresh` fetches the current feed before rebuilding. The Project Gutenberg catalog page explicitly provides its machine-readable metadata for building databases and derivatives, and its robot-access policy states that catalog data are public domain. See the [offline catalogs](https://www.gutenberg.org/ebooks/offline_catalogs.html), [robot access](https://www.gutenberg.org/policy/robot_access.html), and [terms of use](https://www.gutenberg.org/policy/terms_of_use.html).

The normalized subset includes title, author string, language, source subjects/bookshelves, and a stable landing-page link. Source subjects remain original theme metadata. Conservative, documented subject-to-genre mappings are stored separately in `subject_genres`; they never overwrite catalog genres. The display description is a metadata-only notice and is excluded from retrieval text. The catalog has no reliable original publication year, plot descriptions, page counts, publishers, or content warnings, so these remain unknown. No ebook text is downloaded or redistributed. Project Gutenberg cautions that works' copyright status can differ outside the United States; users should check local law before accessing works. A missing safety warning does not certify suitability.

`src/data_loader.py` validates required fields, prefixed IDs, duplicate IDs, descriptions, years, lengths, and genre formatting. `scripts/prepare_data.py books.csv movies.csv` validates user-supplied normalized CSVs.

## Reproducible expanded catalog import

Run `python scripts/acquire_wikidata_catalog.py --limit 1000` to query the public Wikidata Query Service (with QLever as the first endpoint and WDQS as fallback). It writes `data/expanded/books.csv` and `data/expanded/movies.csv`; available records are not guaranteed to reach the requested limit. The app detects these files, merges them with the demo records, and invalidates its cached indexes when the files change. The IDs are prefixed by medium and use Wikidata entity IDs. Source URLs point to each entity.

The imported short `description` is Wikidata's English entity description. It is often a concise type or topic label, not a plot synopsis. Genres, author/director, publication year, language, runtime, page count, and cast come only from available Wikidata statements. Missing statements stay unknown. No ratings, content warnings, page counts, runtimes, or summaries are inferred. Wikidata structured data is released under CC0; see [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing), [data access](https://www.wikidata.org/wiki/Help:Data_access), and its [listed alternate SPARQL endpoints](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/Alternative_endpoints).

Acquisition was attempted for this revision, but the main Wikidata endpoint returned HTTP 429 and both listed QLever addresses returned HTTP 502; Open Library's API request timed out and the Gutendex API returned HTTP 403. The approved Project Gutenberg catalog feed was reachable, so it now supplies a 10,000-record English book subset. Open Library remains a possible future source, but its API documentation asks bulk users to use monthly data dumps rather than treat the search API as a bulk backend. [IMDb's non-commercial terms](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX) prohibit republishing or repurposing that dataset to create a movie database, so it is not used here.

## Local NLP supplements (2026-10-28)

The active catalog still has **10,005 books and 9,744 movies**. New sources
supplement existing IDs, without inventing records:

- **6,023 movie plots**, joined by exact normalized title and year, excluding
  ambiguous source-page matches. `data/enriched/movie_plots.csv.gz` stores up to
  18,000 characters of original plot text plus a short extractive opening excerpt.
  Only the excerpt is sent to the browser. Full text is indexed locally.
- The original [Justin Robischon Wikipedia Movie Plots corpus](https://www.kaggle.com/datasets/jrobischon/wikipedia-movie-plots)
  was acquired through a [pinned public mirror](https://huggingface.co/datasets/vishnupriyavr/wiki-movie-plots-with-summaries/tree/a1feef074ae0580338cf2dd8e98a43ca98637fa6).
  **Generated summary columns are ignored**. The mirror declares CC BY-SA 4.0;
  rows retain their original Wikipedia page URLs for attribution/history.
  Corpus revision and download checksum are in `nlp_sources_manifest.json`.
- **1,344 supplemental metadata rows** from Wikidata and Wikipedia infoboxes
  produce **1,322 known movie runtimes** and **1,334 known movie languages** in
  the active catalog, including existing demo values. Some supplemental rows
  have language only. Runtime and language coverage are counted independently.
- Wikidata joins use exact existing IMDb external IDs and explicit duration units;
  these structured statements are CC0. The endpoint returned repeated HTTP 429,
  so acquisition continued using exact plot-source Wikipedia pages.
- The infobox importer accepts a single explicit minutes value and rejects
  conflicting versions. Language comes only from explicit infobox language fields,
  never nationality/country inference. Each imported field retains the exact
  Wikipedia revision URL and CC BY-SA attribution. See the official
  [MediaWiki revisions API](https://www.mediawiki.org/wiki/API:Revisions).
- **1,815 books** have a conservative genre mapping from supplied Gutenberg
  subjects. These are rule-derived mappings with provenance, not classifier labels.
  Book page counts remain known for only **12 records**; a page limit therefore
  still yields a small verified book pool.

`src/data_loader.py` keeps source metadata, full source text, subject mappings,
local classifier predictions, TF-IDF keywords, and semantic mood/theme inference
in separate fields. Predictions never fill unknown years, lengths, or languages.
A mood alignment score is an experimental text signal, not a verified emotional
response or content-safety label. Full plots can contain spoilers; cards use only
opening excerpts and explanations avoid citing endings.

Scripts: `prepare_nlp_catalog.py --plots-only` rebuilds exact plot matches;
`enrich_wikipedia_metadata.py --limit 1500` performs bounded, cached infobox
acquisition. Source snapshots are bundled for immediate use; API availability
can affect future acquisitions. MovieLens research-use conditions continue to
apply to the combined catalog.


## Free-hosting subset

`data/compact/catalogs.json.gz` is a deterministic subset of the same sourced
records: 1,000 books and 1,500 movies, including all 1,322 known movie runtimes,
1,451 movie plots and all demo/reference titles. No metadata is generated to
fill gaps. `scripts/prepare_compact_catalog.py` prioritizes demo titles, known
movie runtimes and source plots; books prioritize descriptions and documented
subject mappings, with stable SHA-256 tie breaking. The manifest records counts
and policy. Source URLs, per-field provenance, and original usage terms remain.
The compressed snapshot permits low-memory loading without reading the full
expanded catalogs. Both full source datasets and reproducible scripts remain
in the repository. The model is the official Apache-2.0 quantized ONNX export
of all-MiniLM-L6-v2 at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`;
weights and model checksums stay in the ignored artifact cache/container image.
