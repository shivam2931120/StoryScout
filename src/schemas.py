"""Typed domain objects shared by the StoryScout pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MediaType = Literal["book", "movie"]
MediaSelection = Literal["books", "movies", "both"]


@dataclass
class CatalogItem:
    id: str
    media_type: MediaType
    title: str
    description: str
    genres: list[str] = field(default_factory=list)
    language: str = "Unknown"
    year: int | None = None
    source: str = "demo"
    source_url: str = ""
    mood_tags: list[str] = field(default_factory=list)
    theme_tags: list[str] = field(default_factory=list)
    search_aliases: list[str] = field(default_factory=list)
    tag_provenance: str = "catalog metadata"
    authors: str | None = None
    page_count: int | None = None
    publisher: str | None = None
    director: str | None = None
    runtime_minutes: int | None = None
    cast: str | None = None
    verified_warnings: list[str] = field(default_factory=list)
    description_source: str = ""
    description_source_url: str = ""
    description_provenance: str = ""
    retrieval_text: str = ""
    text_source: str = ""
    text_source_url: str = ""
    metadata_provenance: dict[str, dict[str, str]] = field(default_factory=dict)
    nlp_keywords: list[str] = field(default_factory=list)
    inferred_moods: dict[str, float] = field(default_factory=dict)
    inferred_themes: dict[str, float] = field(default_factory=dict)
    subject_genres: list[str] = field(default_factory=list)
    predicted_genres: list[str] = field(default_factory=list)

    @property
    def search_text(self) -> str:
        # MovieLens supplies labels, not plot text; its explanatory display
        # placeholder must never become a shared lexical/semantic signal.
        metadata_only_source = self.source.startswith("movielens") or self.source.startswith("project-gutenberg")
        searchable_description = self.retrieval_text or ("" if metadata_only_source and not self.description_provenance else self.description)
        parts = [self.title, searchable_description, " ".join(self.genres),
                 " ".join(self.mood_tags), " ".join(self.theme_tags), " ".join(self.search_aliases)]
        parts.extend(x for x in [self.authors, self.director, self.language] if x and x.lower() != 'unknown')
        return " ".join(parts)


@dataclass
class Preferences:
    preferred_genres: list[str] = field(default_factory=list)
    excluded_genres: list[str] = field(default_factory=list)
    desired_mood: str | None = None
    themes: list[str] = field(default_factory=list)
    language: str | None = None
    min_year: int | None = None
    max_year: int | None = None
    referenced_title: str | None = None
    positive_content: list[str] = field(default_factory=list)
    negative_content: list[str] = field(default_factory=list)
    max_pages: int | None = None
    max_runtime: int | None = None
    contradiction_messages: list[str] = field(default_factory=list)

    def clone(self) -> "Preferences":
        return Preferences(**{k: list(v) if isinstance(v, list) else v for k, v in self.__dict__.items()})


@dataclass
class ConversationState:
    messages: list[dict[str, str]] = field(default_factory=list)
    preferences: Preferences = field(default_factory=Preferences)
    media_selection: MediaSelection = "both"
    has_explicit_media: bool = False
    selected_reference_id: str | None = None
    last_recommendations: list[str] = field(default_factory=list)
    retrieval_mode: str = "hybrid"
    pending_title_choices: list[str] = field(default_factory=list)
    last_content_query: str = ""
    seen_recommendations: list[str] = field(default_factory=list)


@dataclass
class ParsedRequest:
    intent: str
    media_selection: MediaSelection | None = None
    preferences: Preferences = field(default_factory=Preferences)
    reference_query: str | None = None
    explicit_fields: set[str] = field(default_factory=set)
    explanation_target: str | None = None
    raw_text: str = ""


@dataclass
class Recommendation:
    item: CatalogItem
    score: float
    lexical_score: float = 0.0
    semantic_score: float | None = None
    explanation: str = ""
    filter_notes: list[str] = field(default_factory=list)
    score_components: dict[str, float | None] = field(default_factory=dict)
    matched_terms: list[str] = field(default_factory=list)
    passage_match: dict[str, Any] | None = None


def item_from_row(row: dict[str, Any], media_type: MediaType) -> CatalogItem:
    """Convert a normalized CSV row into a typed catalog record."""
    def optional_int(value: Any) -> int | None:
        try:
            if value in (None, "", "Unknown", "unknown"):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    split = lambda value: [x.strip().lower() for x in str(value or "").split("|") if x.strip()]
    return CatalogItem(
        id=str(row.get("id", "")), media_type=media_type, title=str(row.get("title", "Unknown")),
        description=str(row.get("description", "")),
        description_source=str(row.get("description_source") or ""),
        description_source_url=str(row.get("description_source_url") or ""),
        description_provenance=str(row.get("description_provenance") or ""),
        genres=split(row.get("genres")),
        language=str(row.get("language") or "Unknown"), year=optional_int(row.get("year")),
        source=str(row.get("source") or "unknown"), source_url=str(row.get("source_url") or ""),
        mood_tags=split(row.get("mood_tags")), theme_tags=split(row.get("theme_tags")),
        search_aliases=split(row.get("search_aliases")),
        tag_provenance=str(row.get("tag_provenance") or "unknown"), authors=row.get("authors") or None,
        page_count=optional_int(row.get("page_count")), publisher=row.get("publisher") or None,
        director=row.get("director") or None, runtime_minutes=optional_int(row.get("runtime_minutes")),
        cast=row.get("cast") or None, verified_warnings=split(row.get("verified_warnings")),
    )
