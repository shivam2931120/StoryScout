"""Transparent rule-based intent and media recognition baseline."""
import re
from .schemas import MediaSelection

def detect_media(text: str) -> MediaSelection | None:
    lower = text.lower()
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
