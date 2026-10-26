"""Search text normalization without destroying original display fields."""
import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"[^\w\s'-]", " ", text).strip()


def build_query_text(text: str) -> str:
    # Keep negation words for embedding inputs and lexical retrieval.
    return normalize_text(text)
