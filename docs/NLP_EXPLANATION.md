# NLP explanation

Intent recognition has an understandable rule baseline: words such as “recommend”, “similar”, “reset”, “why”, and “preferences” map to actions. Bare title/topic phrases are treated as searches. When a server-side NVIDIA key is configured, Nemotron can interpret and normalize a request before retrieval; local rules remain the fallback. Media words update the current selection; follow-ups inherit it.

Preference extraction converts text into a dataclass. Genre rules detect positive terms and negation such as “no horror”. Mood is the requested recommendation mood, so “I feel sad; suggest cheerful” selects cheerful. Regular expressions parse years, pages, minutes, and hours. Separate page and runtime fields prevent cross-domain leakage.

TF-IDF weighs words by how distinctive they are in the catalog; cosine similarity compares the request vector with each item. Sentence Transformers creates dense sentence vectors that capture related wording such as “space rescue” and “astronaut survival”. Both domains use the same model, enabling cross-media semantic comparison. Lexical cosine lies in [0, 1]; raw semantic cosine lies in [-1, 1]. We map semantic cosine values below 0.18 to zero and values from 0.18 to 0.62 onto [0, 1], then combine them with fixed 45% lexical and 55% semantic weights. This prevents weak or negative cosine values from receiving an artificial positive score. These are ranking similarities, not probabilities or accuracy. A fallback clearly labels lexical retrieval when embeddings are unavailable. Optional AI descriptions are short paraphrases of exact-title Wikipedia source text; the source, model, and generated provenance are retained separately from original catalog metadata.

Hard filters run first. Unknown metadata cannot pass a declared year/page/runtime/language constraint; records with unknown genres cannot pass explicit genre exclusions. Selected genres are explicit OR filters using source labels or marked subject mappings. Moods and themes are soft text-ranking evidence. Explanations cite only stored metadata and supported tags. The current movie classifier learns from source plot text using TF-IDF plus one-vs-rest logistic regression, with training-only feature fitting, validation-only threshold selection, and a plot-hash-grouped held-out test set. A title-only baseline uses identical splits. Book classification is skipped because public book-catalog records have no genre labels.

Conversation state stores messages, shared preferences, domain-specific lengths, media selection, reference, last IDs, and retrieval mode. Media selection and editable filters stay synchronized with the chat. Follow-up replies summarize changed filters. If a request only provides filters and has no matching catalog terms, the app returns eligible items and explains that no text similarity signal was found. Cross-media similarity uses the selected record’s description and supported metadata, not only its title. Human relevance ratings are collected separately through an exported CSV sheet; unreviewed candidates are not silently counted as negative labels.


## Interface and NLP boundaries

React displays the conversation, cards, and drawers. FastAPI validates requests,
then invokes the same Python intent, preference, filtering, retrieval, and
explanation modules as the original Streamlit interface. The frontend does not
forward every query to a language model or replace NLP with fixed demo responses.
The default API runs local rules and the CPU MiniLM model. NVIDIA interpretation
is optional, explicitly enabled at the server, and never supplies catalog facts.
The NLP page shows active methods and evaluation loads actual experiment files.


## Text-rich local discovery

The catalog stores original movie plot text locally. TF-IDF learns which words
and two-word phrases distinguish documents; the top phrases are shown in item
details. MiniLM encodes up to three chunks (beginning, middle, end), whose vectors
are averaged and normalized. This gives long plots more representation than a
single truncated opening. It is an approximation, not complete long-document
reasoning. The same pretrained encoder maps books and movies into 384 dimensions.

Transparent sentences describe possible moods and themes. Their vector alignment
with each record supplies soft ranking features. These are rule-defined semantic
prototypes, not a trained sentiment model. A separate supervised genre classifier
is genuinely trained locally on plots. Its output is labeled experimental and
never replaces catalog genres or factual metadata.

The conversation stores the meaningful content topic separately from filters.
“Make it shorter” retains that topic while reducing movie runtime by 15 minutes
or book length by 50 pages; unset limits begin at 110 minutes or 300 pages.
With both media active, the policies apply independently. Preference-form edits
rebuild the query from the current values so stale mood/genre words cannot
continue dominating the previous search.

After filtering and scoring, maximal marginal relevance (MMR) balances relevance
with difference from already selected narratives. “Show different recommendations”
excludes seen IDs. It does not sample arbitrary titles or relax constraints.
See `SEARCH_TUNING.md` for exact scoring weights and executed measurements.


The free hosted profile uses the same pretrained MiniLM architecture via its
official quantized ONNX export, with the original tokenizer, 256-token cap,
masked mean pooling and L2 normalization. It does not import PyTorch. Both
media share 384-dimensional vectors, while TF-IDF, preference merging, hard
filters, mood/theme signals, classifier predictions and MMR remain local Python.
The compact source subset contains 1,000 books and 1,500 movies. Its model cache
keys include the ONNX backend to prevent mixing quantized and original vectors.
The full local profile continues to use Sentence Transformers when configured.

## Topic relevance and context controls

The current pipeline keeps topic text separate from mood/genre expansions. It
requires a topic match before multiplying by small preference bonuses, then
removes weak candidates before selecting diverse results. These are transparent
rules, not trained confidence scores. New search clears old criteria; follow-ups
retain a removable topic and visible filters. Source-provided automatic summaries
are labeled and never populate factual metadata. See [the executed comparison
and further NLP experiments](NLP_RELEVANCE_UPDATE.md).

## Passage matching update

Overlapping narrative passages now supplement whole-document retrieval, with one
card per title and source-grounded passage evidence. See [implementation, actual
ablation results, caching, and validation](PASSAGE_MATCHING.md).
