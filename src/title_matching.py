from __future__ import annotations
import gzip
import json
import re
import unicodedata
from pathlib import Path
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
    # Only correct a close whole entity phrase. Rewriting individual words in
    # free-form requests can silently change the intended subject.
    matches = get_close_matches(normalized, normalized_candidates, n=2, cutoff=0.88)
    if matches:
        first = SequenceMatcher(None, normalized, matches[0]).ratio()
        second = SequenceMatcher(None, normalized, matches[1]).ratio() if len(matches)>1 else 0.
        if first-second >= .03:
            return matches[0]
    aliases = {normalize_text(alias) for item in items for alias in item.search_aliases if len(alias) >= 5 and ' ' not in alias}
    words = normalized.split()
    for number, word in enumerate(words):
        close = get_close_matches(word, aliases, n=2, cutoff=.88)
        if close and (len(close) == 1 or SequenceMatcher(None, word, close[0]).ratio()-SequenceMatcher(None, word, close[1]).ratio() >= .03):
            words[number] = close[0]
    corrected = ' '.join(words)
    return corrected if corrected != normalized else query


# Title identity is separate from content similarity: words inside a title are
# not mood/genre instructions. The compact deployment keeps this directory local.
def title_key(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold().replace("&", " and "))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r",\s*(the|an|a)$", lambda m: "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^(the|an|a)\s+", "", text)


def title_names(title):
    """Source titles sometimes include an alternate title in parentheses."""
    names = [title]
    match = re.fullmatch(r"(.+?)\s+\((.+)\)", title)
    if match:
        names.extend([match[1], match[2]])
    return names


class TitleDirectory:
    """Small source metadata directory; no model vectors or full plot copies."""
    def __init__(self, records=()):
        self.records = {record["id"]: record for record in records}
        self.keys = {}
        for record in self.records.values():
            for name in title_names(record["title"]):
                self.keys.setdefault(title_key(name), set()).add(record["id"])

    @classmethod
    def load(cls, path: Path):
        if not path.exists():
            return cls()
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return cls(json.load(stream))

    def get(self, item_id):
        record = self.records.get(item_id)
        return CatalogItem(**record) if record else None

    def lookup(self, text, active_items, selection="both"):
        explicit = bool(re.match(r"^(?:look up|search for (?:the )?title|(?:find|show|search for) (?:(?:the|a) )?(?:movie|film|book|title) (?:called|named))\s+", text, re.I))
        query = re.sub(r"^(?:find|show|search(?: for)?|look up)\s+(?:(?:the|a)\s+)?(?:movie|film|book|title)(?:\s+(?:called|named))?\s+", "", text.strip(), flags=re.I)
        query = re.sub(r"^look up\s+", "", query, flags=re.I).strip(" \"'?!.")
        year_match = re.search(r"\s*\(?((?:18|19|20)\d{2})\)?\s*$", query)
        if year_match and not query[:year_match.start()].strip():
            year_match = None
        year = int(year_match[1]) if year_match else None
        if year_match:
            query = query[:year_match.start()]
        key = title_key(query)
        active = {item.id: item for item in active_items}
        ids = set(self.keys.get(key, ()))
        ids.update(item.id for item in active_items if key in {title_key(a) for a in title_names(item.title)})
        # Typo matches are suggestions, never an automatic exact-title claim.
        approximate = False
        if not ids and len(key) >= 8:
            near = get_close_matches(key, self.keys, n=3, cutoff=0.92)
            for candidate in near:
                ids.update(self.keys[candidate])
            approximate = bool(ids)
        items = [active.get(item_id) or self.get(item_id) for item_id in sorted(ids)]
        items = [item for item in items if item and (year is None or item.year == year)]
        requested = "movie" if re.match(r"^(?:find|show|search(?: for)?|look up)\s+(?:(?:the|a)\s+)?(?:movie|film)\b", text, re.I) else ("book" if re.match(r"^(?:find|show|search(?: for)?|look up)\s+(?:(?:the|a)\s+)?book\b", text, re.I) else None)
        # An inherited format narrows ambiguity only if a match exists in it.
        preferred = requested or {"books": "book", "movies": "movie"}.get(selection)
        narrowed = [item for item in items if item.media_type == preferred]
        if requested or narrowed:
            items = narrowed
        unique = {}
        for item in items:
            identity = (item.media_type, title_key(item.title), item.year)
            previous = unique.get(identity)
            if previous is None or (item.id in active and previous.id not in active) or item.source.startswith('demo'):
                unique[identity] = item
        return list(unique.values())[:10], approximate, explicit
