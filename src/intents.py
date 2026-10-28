"""Transparent rule-based intent and media recognition baseline."""
import re
from .schemas import MediaSelection

def detect_media(text: str) -> MediaSelection | None:
    lower = text.lower()
    requested=re.search(r'\b(?:recommend|suggest|find me|show me)\b(.*)',lower)
    if requested: lower=requested.group(1)
    else: lower=re.sub(r'\bi (?:liked|loved|enjoyed)\b[^.!?;]*[.!?;]','',lower)
    book = bool(re.search(r"\b(book|books|novel|novels|read|reading)\b", lower))
    movie = bool(re.search(r"\b(movie|movies|film|films|watch|watching|cinema)\b", lower))
    if book and movie:
        return "both"
    if book:
        return "books"
    if movie:
        return "movies"
    return None


def detect_intent(text: str) -> str:
    lower = text.lower().strip()
    if lower in {"reset", "reset preferences", "start over", "clear"} or "reset my" in lower:
        return "reset"
    if lower in {"help", "what can you do"} or "unsupported" in lower:
        return "help"
    if "why did you recommend" in lower or lower.startswith("explain"):
        return "explain"
    if lower=='more' or re.search(r'\b(?:more|other|different|another)\s+(?:books?|movies?|films?|recommendations?|picks)\b',lower) or any(x in lower for x in ['show more','different picks','different recommendations','other recommendations','another set','more recommendations','more movies','more books']):
        return 'more'
    if re.fullmatch(r'(?:only\s+)?(?:books?|movies?|films?|both|all stories)(?:\s+only|\s+now)?[.!]?',lower):
        return 'refine'
    if "what are my preferences" in lower or "show active preferences" in lower or "my preferences" == lower:
        return "show_preferences"
    if any(x in lower for x in ["similar", "like it", "liked ", "enjoyed ", "recommend something like"]):
        return "similar"
    if any(x in lower for x in ["suggest", "recommend", "find", "looking for", "give me"]):
        return "recommend"
    if any(x in lower for x in ["only show", "switch to", "include ", "exclude ", "under ", "after ", "before ", "between ", "make it shorter", "shorter", "actually"]):
        return "refine"
    if re.search(r"\b(?:no|not|without|exclude|excluding)\s+(?:any\s+)?[a-z]+", lower):
        return "refine"
    # Short title/topic phrases are searches too; users need not write commands.
    return "recommend"
