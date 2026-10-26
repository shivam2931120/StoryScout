"""Rule-based structured preference extraction and deterministic merging."""
from __future__ import annotations
import re
from .schemas import Preferences, ParsedRequest
from .intents import detect_intent, detect_media

GENRES = ["mystery", "thriller", "science fiction", "fantasy", "romance", "comedy", "drama", "adventure", "history", "horror", "animation", "documentary", "crime", "dystopian", "family"]
GENRE_ALIASES = {"romance": ["romantic"]}
MOODS = ["uplifting", "cheerful", "comforting", "cozy", "hopeful", "inspiring", "thoughtful", "dark", "funny", "calm", "exciting", "lighthearted", "melancholic"]
THEMES = ["time travel", "space", "friendship", "identity", "coming of age", "found family", "survival", "magic", "journey", "artificial intelligence", "adventure", "justice"]

def _add_unique(values: list[str], new: list[str]) -> list[str]:
    result = list(values)
    for value in new:
        if value and value not in result:
            result.append(value)
    return result

def _number(text: str) -> int | None:
    try: return int(text)
    except ValueError: return None

def parse_preferences(text: str) -> ParsedRequest:
    lower = text.lower()
    pref = Preferences()
    explicit: set[str] = set()
    media = detect_media(text)
    # Explicit removals precede additions so "include horror" wins over a prior exclusion.
    for genre in GENRES:
        terms = [genre, *GENRE_ALIASES.get(genre, [])]
        negative = any(re.search(rf"\b(?:no|not|without|exclude|excluding)\s+(?:any\s+)?(?:[a-z-]+\s+(?:and|or)\s+)*{re.escape(term)}\b", lower) for term in terms)
        positive = any(re.search(rf"\b{re.escape(term)}\b", lower) for term in terms)
        if negative:
            pref.excluded_genres.append(genre); explicit.add("excluded_genres")
        if re.search(rf"\b(?:include|including|allow|actually include)\s+{re.escape(genre)}\b", lower):
            pref.positive_content.append(genre); explicit.add("include_genre")
        elif positive and not negative:
            pref.preferred_genres.append(genre); explicit.add("preferred_genres")
    for mood in MOODS:
        if re.search(rf"\b{re.escape(mood)}\b", lower):
            pref.desired_mood = mood; explicit.add("desired_mood")
    for theme in THEMES:
        aliases = {"artificial intelligence": [r"\bai\b", r"\brobots?\b"]}.get(theme, [])
        if re.search(rf"\b{re.escape(theme)}\b", lower) or any(re.search(alias, lower) for alias in aliases):
            pref.themes.append(theme); explicit.add("themes")
    lang = re.search(r"\b(?:in|language)\s+(english|hindi|spanish|french|german)\b", lower)
    if lang:
        pref.language = lang.group(1); explicit.add("language")
    years = re.search(r"\bbetween\s+(\d{4})\s+and\s+(\d{4})\b", lower)
    if years:
        pref.min_year, pref.max_year = int(years.group(1)), int(years.group(2)); explicit.add("year")
    after = re.search(r"\b(?:after|from)\s+(\d{4})\b", lower)
    before = re.search(r"\b(?:before|until|up to)\s+(\d{4})\b", lower)
    if after: pref.min_year = int(after.group(1)) + (1 if "after" in after.group(0) else 0); explicit.add("year")
    if before: pref.max_year = int(before.group(1)) - (1 if "before" in before.group(0) else 0); explicit.add("year")
    page = re.search(r"(?:under|less than|fewer than|up to|max(?:imum)?(?: of)?)\s+(\d+)\s*pages?", lower)
    if page: pref.max_pages = int(page.group(1)); explicit.add("max_pages")
    runtime = re.search(r"(?:under|less than|fewer than|up to|max(?:imum)?(?: of)?)\s+(\d+)\s*(?:minutes?|mins?)", lower)
    if runtime: pref.max_runtime = int(runtime.group(1)); explicit.add("max_runtime")
    hours = re.search(r"(?:under|less than|up to)\s+(\d+(?:\.\d+)?|one|two|three|four|five)\s*hours?", lower)
    if hours:
        amount = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(hours.group(1), float(hours.group(1)) if hours.group(1)[0].isdigit() else 0)
        pref.max_runtime = int(amount * 60); explicit.add("max_runtime")
    if "short" in lower or "shorter" in lower:
        explicit.add("short")
    if "graphic violence" in lower or "violence" in lower:
        pref.negative_content.append("graphic violence"); explicit.add("negative_content")
    reference = None
    match = re.search(r"(?:liked|enjoyed|like|similar to)\s+[\"']?([^\"'.!?]+)", text, re.I)
    if match: reference = match.group(1).strip(); pref.referenced_title = reference; explicit.add("referenced_title")
    return ParsedRequest(intent=detect_intent(text), media_selection=media, preferences=pref, reference_query=reference, explicit_fields=explicit, raw_text=text)


def merge_preferences(current: Preferences, incoming: Preferences, text: str, explicit_fields: set[str]) -> Preferences:
    merged = current.clone()
    lower = text.lower()
    if "include_genre" in explicit_fields:
        for genre in incoming.positive_content:
            merged.excluded_genres = [x for x in merged.excluded_genres if x != genre]
    merged.preferred_genres = _add_unique(merged.preferred_genres, incoming.preferred_genres)
    merged.excluded_genres = _add_unique(merged.excluded_genres, incoming.excluded_genres)
    merged.themes = _add_unique(merged.themes, incoming.themes)
    merged.positive_content = _add_unique(merged.positive_content, incoming.positive_content)
    merged.negative_content = _add_unique(merged.negative_content, incoming.negative_content)
    for field in ["desired_mood", "language", "min_year", "max_year", "referenced_title", "max_pages", "max_runtime"]:
        if field in explicit_fields and getattr(incoming, field) is not None:
            setattr(merged, field, getattr(incoming, field))
    if "year" in explicit_fields:
        merged.min_year = incoming.min_year
        merged.max_year = incoming.max_year
    if "short" in explicit_fields:
        # Documented policy: 300 pages/books and 110 minutes/movies unless a tighter domain limit exists.
        if "movie" in lower or "minutes" in lower:
            merged.max_runtime = min(merged.max_runtime or 10_000, 110)
        elif "book" in lower or "pages" in lower:
            merged.max_pages = min(merged.max_pages or 10_000, 300)
        else:
            merged.max_pages = min(merged.max_pages or 10_000, 300)
            merged.max_runtime = min(merged.max_runtime or 10_000, 110)
    contradictions = []
    if set(merged.preferred_genres) & set(merged.excluded_genres):
        contradictions.append("The same genre is both preferred and excluded: " + ", ".join(sorted(set(merged.preferred_genres) & set(merged.excluded_genres))))
    if merged.min_year and merged.max_year and merged.min_year > merged.max_year:
        contradictions.append("The year range is contradictory: minimum is after maximum.")
    merged.contradiction_messages = contradictions
    return merged
