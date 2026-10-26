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
18. **Why cache?** Index preparation and embeddings should not repeat on Streamlit reruns.
19. **What is the fallback?** TF-IDF lexical retrieval when the model is unavailable.
20. **How was retrieval evaluated?** Forty developer-authored judgments with per-domain P@5, Recall@5, MRR@5, hard-filter compliance, and latency; labels are not independent human ratings.
21. **Was evaluation independently human-rated?** No; limitations are stated.
22. **Why skip genre classification?** Fourteen book and thirteen movie demo records are insufficient for stable held-out metrics.
23. **Is an LLM integrated?** Optionally: NVIDIA Nemotron interprets the query when a server-side key is configured. The app still retrieves and explains items from its catalog.
24. **Is collaborative filtering used?** No; there is no user-behavior history.
25. **What would you add next?** Larger licensed catalogs, human judgments, calibrated multilingual models, and richer verified content metadata.
