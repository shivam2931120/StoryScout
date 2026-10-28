"""Rule-based structured preference extraction and deterministic merging."""
from __future__ import annotations
import re
from .schemas import Preferences, ParsedRequest
from .intents import detect_intent, detect_media

GENRES = ["mystery", "thriller", "science fiction", "fantasy", "romance", "comedy", "drama", "adventure", "history", "horror", "animation", "documentary", "crime", "dystopian", "family", "action", "war", "western", "musical", "film noir"]
GENRE_ALIASES = {"romance": ["romantic", "rom-com", "romcom"], "comedy":["rom-com","romcom"], "science fiction":["sci-fi","sci fi","scifi"], "family":["children","kids","kid friendly"], "history":["historical"], "film noir":["film-noir","noir"]}
MOODS = ["uplifting", "cheerful", "comforting", "cozy", "hopeful", "inspiring", "thoughtful", "dark", "funny", "calm", "exciting", "lighthearted", "melancholic"]
THEMES = ["time travel", "space", "friendship", "identity", "coming of age", "found family", "survival", "magic", "journey", "artificial intelligence", "adventure", "justice", "heist", "family"]

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
    desired = re.search(r'\b(?:recommend|suggest|looking for|give me|show me|find me)\b(.*)', lower)
    extraction_lower = desired.group(1) if desired else re.sub(r'\bi (?:liked|loved|enjoyed)\b[^.!?;]*[.!?;]', '', lower)
    pref = Preferences()
    explicit: set[str] = set()
    media = detect_media(text)
    # Explicit removals precede additions so "include horror" wins over a prior exclusion.
    for genre in GENRES:
        terms = [genre, *GENRE_ALIASES.get(genre, [])]
        negative = any(re.search(rf"\b(?:no|not|without|exclude|excluding|avoid|anything but)\s+(?:any\s+)?(?:[a-z-]+\s+(?:and|or)\s+)*{re.escape(term)}\b", extraction_lower) for term in terms)
        positive = any(re.search(rf"\b{re.escape(term)}\b", extraction_lower) for term in terms)
        if genre=='family' and not re.search(r'\bfamily\b',re.sub(r'\b(?:found|chosen) family\b','',extraction_lower)):
            positive=False
        if negative:
            pref.excluded_genres.append(genre); explicit.add("excluded_genres")
        if re.search(rf"\b(?:include|including|allow|actually include)\s+{re.escape(genre)}\b", lower):
            pref.positive_content.append(genre); explicit.add("include_genre")
        elif positive and not negative:
            pref.preferred_genres.append(genre); explicit.add("preferred_genres")
    aliases = {'feel-good':'uplifting','feel good':'uplifting','happy':'cheerful','warm':'comforting','gentle':'calm','less intense':'calm','not too intense':'calm','mind-bending':'thoughtful','mind bending':'thoughtful','cerebral':'thoughtful','fast-paced':'exciting','fast paced':'exciting','sad':'melancholic'}
    mood_hits=[]
    for term,mood in [(m,m) for m in MOODS]+list(aliases.items()):
        for match in re.finditer(rf'\b{re.escape(term)}\b',extraction_lower):
            # Feelings reported without a desired-content clause are not targets.
            if not desired and re.search(r'\b(?:i feel|i am|i\x27m)\s*$', extraction_lower[:match.start()]): continue
            mood_hits.append((match.start(),mood))
    if mood_hits:
        pref.desired_mood=max(mood_hits)[1]; explicit.add('desired_mood')
    for theme in THEMES:
        if theme=='family' and 'found family' in extraction_lower: continue
        aliases = {"artificial intelligence": [r"\bai\b", r"\brobots?\b"], 'space':[r'\bastronauts?\b',r'\bspacecraft\b'], 'time travel':[r'\btime loops?\b',r'\btime machine\b']}.get(theme, [])
        if re.search(rf"\b{re.escape(theme)}\b", extraction_lower) or any(re.search(alias, extraction_lower) for alias in aliases):
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
    if re.search(r'\b(?:no|not|without|avoid|exclude|excluding)\b.{0,50}\b(?:violence|violent)\b',lower):
        pref.negative_content.append("graphic violence"); explicit.add("negative_content")
    reference = None
    match = re.search(r"(?:liked|loved|enjoyed|like|similar to|atmosphere of|themes of)\s+[\"']?([^\"'.!?;]+)", text, re.I)
    if match:
        reference = re.split(r'\s+(?:with similar|under\s+\d|recommend|suggest|find)\b',match.group(1),maxsplit=1,flags=re.I)[0].strip()
        pref.referenced_title = reference; explicit.add("referenced_title")
    for field,pattern in {'max_pages':r'(?:no|remove|clear|forget)\s+(?:the\s+)?(?:book\s+)?page(?:s| count)?\s+limit', 'max_runtime':r'(?:no|remove|clear|forget)\s+(?:the\s+)?(?:movie\s+)?(?:runtime|duration|time)\s+limit', 'year':r'(?:any year|remove (?:the )?year|clear (?:the )?year)', 'genres':r'(?:any genre|clear (?:the )?genres)', 'desired_mood':r'(?:any mood|clear (?:the )?mood)'}.items():
        if re.search(pattern,lower): explicit.add('clear_'+field)
    if re.search(r'\b(?:instead|rather than|replace|change the genre)\b',lower):
        explicit.add('replace_genres')
        if 'instead of' in extraction_lower:
            previous=extraction_lower.split('instead of',1)[1]
            pref.preferred_genres=[g for g in pref.preferred_genres if not re.search(rf'\b{re.escape(g)}\b',previous)]
    return ParsedRequest(intent=detect_intent(text), media_selection=media, preferences=pref, reference_query=reference, explicit_fields=explicit, raw_text=text)


def merge_preferences(current: Preferences, incoming: Preferences, text: str, explicit_fields: set[str]) -> Preferences:
    merged = current.clone()
    lower = text.lower()
    if "include_genre" in explicit_fields:
        for genre in incoming.positive_content:
            merged.excluded_genres = [x for x in merged.excluded_genres if x != genre]
    merged.preferred_genres = _add_unique(merged.preferred_genres, incoming.preferred_genres)
    if 'replace_genres' in explicit_fields and incoming.preferred_genres:
        merged.preferred_genres = list(incoming.preferred_genres)
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
        # First "short" has defaults; a relative "shorter" actually tightens an existing cap.
        def shorter(value, step, default):
            return max(1,value-step) if value is not None and 'shorter' in lower else min(value or 10000,default)
        if "movie" in lower or "minutes" in lower:
            merged.max_runtime = shorter(merged.max_runtime,15,110)
        elif "book" in lower or "pages" in lower:
            merged.max_pages = shorter(merged.max_pages,50,300)
        else:
            merged.max_pages = shorter(merged.max_pages,50,300)
            merged.max_runtime = shorter(merged.max_runtime,15,110)
    for field in ('max_pages','max_runtime','desired_mood'):
        if 'clear_'+field in explicit_fields: setattr(merged,field,None)
    if 'clear_year' in explicit_fields: merged.min_year=merged.max_year=None
    if 'clear_genres' in explicit_fields: merged.preferred_genres=[]
    contradictions = []
    if set(merged.preferred_genres) & set(merged.excluded_genres):
        contradictions.append("The same genre is both preferred and excluded: " + ", ".join(sorted(set(merged.preferred_genres) & set(merged.excluded_genres))))
    if merged.min_year and merged.max_year and merged.min_year > merged.max_year:
        contradictions.append("The year range is contradictory: minimum is after maximum.")
    merged.contradiction_messages = contradictions
    return merged
