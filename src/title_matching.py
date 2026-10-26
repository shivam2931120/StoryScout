from __future__ import annotations
from difflib import SequenceMatcher, get_close_matches
from .preprocessing import normalize_text
from .schemas import CatalogItem

def resolve_title(query: str, items: list[CatalogItem]) -> tuple[CatalogItem | None, list[CatalogItem]]:
    q = normalize_text(query)
    exact = [x for x in items if normalize_text(x.title) == q]
    if len(exact) == 1: return exact[0], exact
    if len(exact) > 1: return None, exact
    contains = [x for x in items if q in normalize_text(x.title) or normalize_text(x.title) in q]
    if len(contains) == 1: return contains[0], contains
    ranked = sorted(items, key=lambda x: SequenceMatcher(None, q, normalize_text(x.title)).ratio(), reverse=True)
    choices = [x for x in ranked if SequenceMatcher(None, q, normalize_text(x.title)).ratio() >= 0.55][:5]
    return (choices[0] if len(choices) == 1 else None), choices


def correct_catalog_query(query: str, items: list[CatalogItem]) -> str:
    """Correct a close spelling against known catalog titles and curated aliases."""
    normalized = normalize_text(query)
    if not normalized:
        return query
    candidates = [item.title for item in items]
    candidates.extend(alias for item in items for alias in item.search_aliases)
    normalized_candidates = list(dict.fromkeys(normalize_text(label) for label in candidates if label))
    # Exact aliases remain intact, including multiword character/topic names.
    for label_norm in normalized_candidates:
        if label_norm and (label_norm in normalized or normalized in label_norm):
            return query
    query_words = normalized.split()
    title_words = {word for label in normalized_candidates for word in label.split() if len(word) >= 5}
    corrections: dict[str, str] = {}
    for word in query_words:
        if len(word) < 5:
            continue
        match = get_close_matches(word, title_words, n=1, cutoff=0.78)
        if match and match[0] != word:
            corrections[word] = match[0]
    return " ".join(corrections.get(word, word) for word in query_words)
