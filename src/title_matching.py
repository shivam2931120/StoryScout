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
    text=re.sub(r"\bpart\s+(one|two|three|i|ii|iii)\b",lambda m:"part "+{'one':'1','two':'2','three':'3','i':'1','ii':'2','iii':'3'}[m[1]],text)
    return re.sub(r"^(the|an|a)\s+", "", text)


def title_names(title):
    """Source identity aliases only; characters/themes are not title aliases."""
    names = [title]
    match = re.fullmatch(r"(.+?)\s+\((.+)\)", title)
    if match:
        names.extend([match[1], re.sub(r"^(?:a\.?k\.?a\.?|also known as)\s+", "", match[2], flags=re.I)])
    return list(dict.fromkeys(names))


def title_request(text):
    """Extract the entity span without sending conversational prose to search.

    Wrappers express lookup only if their remainder is not a descriptive request.
    Bare ambiguous short phrases are clarified rather than silently substituted.
    """
    text=re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", text.strip(), flags=re.I)
    patterns=[
        r"^(?:can you |could you |please )?(?:tell me about|what is|what's|details (?:of|about)|look up|search for (?:the )?title)\s+",
        r"^(?:i (?:want|would like|wish) to|i'd like to|let me)\s+(?:watch|read)\s+",
        r"^(?:i(?: am|'m)? looking for|looking for|do you have|have you got|i want|i would like|i'd like)\s+",
        r"^(?:show|give) me (?:details|information) (?:of|about|on)\s+",
        r"^(?:find|show|give|search(?: for)?|look up|recommend|suggest)(?:\s+me)?\s+",
        r"^(?:watch|read)\s+",
        r"^(?:the\s+)?(?:movie|film|book|novel)\s+",
    ]
    query=text; wrapped=False
    for pattern in patterns:
        match=re.match(pattern,text,re.I)
        if match:
            query=text[match.end():];wrapped=True;break
    requested='book' if re.search(r"\b(?:book|novel|read)\b",text[:len(text)-len(query)],re.I) else ('movie' if re.search(r"\b(?:movie|film|watch)\b",text[:len(text)-len(query)],re.I) else None)
    trailing=re.search(r"\s+(movies|films|books|novels)$",query,re.I)
    if trailing:
        requested="book" if trailing[1].lower() in {"books","novels"} else "movie"
        query=query[:trailing.start()];wrapped=True
    query=re.sub(r"\s+please[.!?]*$","",query,flags=re.I).strip(" \"'?!.")
    return query,wrapped,requested


def descriptive_request(text, active_items=()):
    from .preferences import GENRES, GENRE_ALIASES, MOODS, THEMES
    words=title_key(text)
    if not words:return True
    # Preserve discovery, constraints, reference similarity and follow-up commands.
    if re.search(r"\b(?:about|like|similar|with|without|under|over|after|before|between|shorter|longer|only|now|no|not|recommend|suggest|enjoyed|liked|loved|something|anything|stories|movies|books|films|novels|minutes|pages|reset|help|preferences|include|exclude|instead|more|less|feel|feeling)\b",words):return True
    signals=GENRES+MOODS+THEMES+[x for aliases in GENRE_ALIASES.values() for x in aliases]+['erotica','spacecraft','oxygen','exploration','robots','aliens','astronaut','detective','love','sad','stress','stressed','happy','gentle','warm','mind bending','twist','ending','pen pals','run away','historical','english','hindi','french','spanish','german']
    if any(re.search(rf"\b{re.escape(signal)}\b",words) for signal in signals):return True
    aliases={title_key(alias) for item in active_items for alias in item.search_aliases if len(alias)>=5}
    if words in aliases or get_close_matches(words,aliases,n=1,cutoff=.85):return True
    return len(words.split())>7


class TitleDirectory:
    """Local title identity index. Narrative similarity never establishes identity."""
    def __init__(self, records=()):
        self.records = {record["id"]: record for record in records}
        self.keys = {}
        for record in self.records.values():
            for name in title_names(record["title"])+record.get('title_aliases',[]):
                key=title_key(name)
                if key:self.keys.setdefault(key,set()).add(record['id'])
        self.last_match_kind='none'
        self.last_requested_media=None
        self.last_entity=''
        self.last_constraint_text=''

    @classmethod
    def load(cls, path: Path):
        if not path.exists():return cls()
        with gzip.open(path, "rt", encoding="utf-8") as stream:return cls(json.load(stream))

    def get(self, item_id):
        record = self.records.get(item_id)
        return CatalogItem(**record) if record else None

    def add_item(self, item: CatalogItem):
        """Add a request-time, provenance-carrying identity to process memory."""
        self.records[item.id] = {
            "id": item.id, "media_type": item.media_type, "title": item.title,
            "description": item.description, "year": item.year,
            "source": item.source, "source_url": item.source_url,
            "title_aliases": list(item.title_aliases), "genres": list(item.genres),
            "language": item.language, "runtime_minutes": item.runtime_minutes,
            "director": item.director, "retrieval_text": item.retrieval_text,
            "description_source": item.description_source,
            "description_source_url": item.description_source_url,
            "description_provenance": item.description_provenance,
            "text_source": item.text_source, "text_source_url": item.text_source_url,
            "metadata_provenance": item.metadata_provenance,
        }
        for name in title_names(item.title) + item.title_aliases:
            key = title_key(name)
            if key:
                self.keys.setdefault(key, set()).add(item.id)

    def lookup(self, text, active_items, selection="both"):
        query,wrapped,requested=title_request(text)
        self.last_requested_media=requested
        self.last_constraint_text=''
        # A title containing words such as "like" or "before" is still exact.
        candidates=[text.strip(" \"'?!."),query]
        active={item.id:item for item in active_items}
        local_keys={}
        for item in active_items:
            for name in title_names(item.title)+item.title_aliases:
                local_keys.setdefault(title_key(name),set()).add(item.id)
        def identities(key):return set(self.keys.get(key,()))|set(local_keys.get(key,()))
        ids=set();year=None;key='';author=None
        for candidate in candidates:
            exact=identities(title_key(candidate))
            if exact:
                if candidate==candidates[0]:
                    requested=None;self.last_requested_media=None
                ids=exact;key=title_key(candidate);query=candidate;break
        if not ids:
            # Only strip a format noun after trying the entire extracted title.
            # 'The Book Thief' and 'The Book of Eli' contain literal title words.
            leading=re.match(r"^(?:(?:the|a)\s+)?(movie|film|book|novel|title)\s+(?:(?:called|named|titled)\s+)?",query,re.I) if wrapped else None
            if leading:
                requested='book' if leading[1].lower() in {'book','novel'} else ('movie' if leading[1].lower() in {'movie','film'} else None)
                self.last_requested_media=requested;query=query[leading.end():]
            suffix=re.search(r'\s+(?:under|below|after|before|between)\s+(?:\d+|one\b|two\b|three\b)',query,re.I)
            if suffix:
                candidate=query[:suffix.start()].strip()
                if identities(title_key(candidate)):
                    self.last_constraint_text=query[suffix.start():].strip();query=candidate
            author_match=re.search(r'\s+by\s+(.+)$',query,re.I)
            if author_match:
                author=author_match[1].strip();query=query[:author_match.start()].strip()
            year_match=re.search(r"\s*\(?((?:18|19|20)\d{2})\)?\s*$",query)
            if year_match and query[:year_match.start()].strip():
                year=int(year_match[1]);query=query[:year_match.start()].strip()
            key=title_key(query);ids=identities(key)
        self.last_entity=query
        kind='exact' if ids else 'none'
        descriptive=descriptive_request(query,active_items)
        # Only contiguous title-token phrases (not shared individual words) can
        # establish a franchise/partial-title candidate list.
        if not ids and len(key.split())>=2 and not descriptive:
            for candidate in set(self.keys)|set(local_keys):
                if (' '+key+' ') in (' '+candidate+' '):ids.update(identities(candidate))
            if ids:kind='partial'
        approximate=False
        explicit_discovery=bool(re.search(r'\b(?:about|similar|under|over|after|before|between|without|shorter|preferences|recommend|suggest|enjoyed|liked|loved)\b',query,re.I))
        if not ids and len(key)>=5 and not explicit_discovery:
            cutoff=.92 if descriptive else (.80 if len(key)>=8 else .86)
            near=get_close_matches(key,set(self.keys)|set(local_keys),n=6,cutoff=cutoff)
            if near:
                best=SequenceMatcher(None,key,near[0]).ratio()
                for candidate in near:
                    if SequenceMatcher(None,key,candidate).ratio()>=best-.035:ids.update(identities(candidate))
                approximate=bool(ids)
                if ids:kind='suggestion'
        items=[active.get(item_id) or self.get(item_id) for item_id in sorted(ids)]
        items=[item for item in items if item and (year is None or item.year==year) and (not author or title_key(author) in title_key(item.authors or item.director or ''))]
        preferred=requested or {'books':'book','movies':'movie'}.get(selection)
        narrowed=[item for item in items if item.media_type==preferred]
        if requested or narrowed:items=narrowed
        unique={}
        for item in items:
            identity=(item.media_type,title_key(item.title),item.year,title_key(item.authors or '') if item.media_type=='book' else '')
            previous=unique.get(identity)
            if previous is None or (item.id in active and previous.id not in active) or item.source.startswith('demo'):unique[identity]=item
        self.last_match_kind=kind if items else 'missing'
        # Unrecognized concise entity phrases require clarification instead of
        # weak narrative substitutes. Descriptive topic requests keep local NLP.
        named_lookup=bool(re.search(r'\b(?:called|named|titled)\s+|^look up\s+',text,re.I))
        explicit=named_lookup or (wrapped and not descriptive) or (not descriptive and bool(key))
        return list(unique.values())[:10],approximate,explicit
