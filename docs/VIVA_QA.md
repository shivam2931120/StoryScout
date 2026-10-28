# Viva Q&A

1. **Why is this NLP?** It parses natural-language intent, negation, preferences, references, and semantic text similarity.
2. **Why not keyword search only?** TF-IDF misses paraphrases; embeddings capture related meaning.
3. **How do books and movies share a space?** Both descriptions are encoded by the same sentence-transformer model.
4. **How do exclusions work?** Explicit excluded genres and verified warnings become hard filters.
5. **Why is similarity not accuracy?** It is a ranking signal, not a correctness probability.
6. **How does memory work?** A typed conversation state merges deterministic preference updates.
7. **What happens on “only books”?** It changes media selection while retaining applicable preferences.
8. **Why separate pages/runtime?** They are different units and must not leak across domains.
9. **What does unknown runtime mean?** It cannot pass an explicit runtime limit.
10. **How is negation detected?** Transparent patterns match “no”, “not”, “without”, and “exclude”.
11. **How is mood detected?** A curated vocabulary maps requested mood words; it is not a trained sentiment model.
12. **How are references resolved?** Exact, containment, and fuzzy title matching are attempted.
13. **What if titles are ambiguous?** The engine returns choices instead of silently choosing.
14. **How are endings protected?** The catalog contains no ending-spoiling generated explanation.
15. **Does it detect adaptations?** No; it explicitly avoids that claim.
16. **How are hard filters applied?** Before ranking, so an ineligible item cannot win on similarity.
17. **What is hybrid retrieval?** A weighted lexical/semantic combination after cosine scoring.
18. **Why cache?** Model and index preparation should not repeat for each HTTP request. FastAPI shares one loaded model/index set; the older Streamlit app also caches them across reruns.
19. **What is the fallback?** TF-IDF lexical retrieval when the model is unavailable.
20. **How was retrieval evaluated?** Forty-four developer-authored queries with per-domain P@5, Recall@5, MRR@5, hard-filter compliance, and latency; labels are not independent human ratings.
21. **Was evaluation independently human-rated?** No; limitations are stated.
22. **Was genre classification trained?** The movie experiment uses title-only TF-IDF and one-vs-rest logistic regression with a fixed held-out split. Book classification is skipped because too few records have genre labels. Predicted labels do not replace source genres.
23. **Is an LLM integrated?** Optionally: with a private server key and `STORYSCOUT_USE_NVIDIA=true`, NVIDIA Nemotron interprets the query. The default React/API application runs local rules and retrieval, and never requires the external interpreter.
24. **Is collaborative filtering used?** No. Bookmarks and conversations are stored per browser, but are not used to learn recommendations from user behavior.
25. **What would you add next?** Larger licensed catalogs, human judgments, calibrated multilingual models, and richer verified content metadata.


### Current NLP revision: what was actually trained?
A TF-IDF + one-vs-rest logistic regression movie genre classifier was trained on
6,020 source-labeled plots. Plot-hash-grouped splits isolate test records, and
thresholds are selected using validation only. MiniLM itself was not fine-tuned.
The held-out title baseline and plot model share the same 1,204 test films.

### Why did runtime searches previously repeat the same movies?
Only 12 movies had known runtime, so a runtime filter removed nearly all imported
records. Source-backed metadata now increases that pool to 1,322 known runtimes.
Ranking also uses current genre/mood/theme preferences and diverse selection.

### Are predicted genres factual labels?
No. They are a separate experimental text feature. Explicit genre filters use
source labels or documented source-subject mappings, and predicted genres never
verify a runtime, year, page count, language, or warning.
