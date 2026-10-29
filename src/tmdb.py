"""Small, optional TMDB movie-title source for server-side entity resolution.

TMDB data is fetched only for a likely named movie/reference title, held in
process memory, and never written into the local recommendation indexes.
StoryScout's local NLP remains responsible for interpreting and ranking queries.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import logging
import os
import re
import threading
import time

import httpx

from .schemas import CatalogItem
from .title_matching import title_key

logger = logging.getLogger(__name__)

TMDB_GENRES = {
    12: "Adventure", 14: "Fantasy", 16: "Animation", 18: "Drama",
    27: "Horror", 28: "Action", 35: "Comedy", 36: "History",
    37: "Western", 53: "Thriller", 80: "Crime", 99: "Documentary",
    9648: "Mystery", 10402: "Music", 10749: "Romance",
    10751: "Family", 10752: "War", 878: "Science Fiction",
    10770: "TV Movie",
}

LANGUAGES = {"en": "English", "hi": "Hindi", "fr": "French", "es": "Spanish", "de": "German", "ja": "Japanese", "ko": "Korean", "it": "Italian", "zh": "Chinese", "pt": "Portuguese", "ru": "Russian"}


class TMDBMovieSource:
    """Query TMDB v3 with a server-side API key; failures remain non-fatal."""

    def __init__(self, api_key: str | None = None, timeout: float = 2.8):
        self.api_key = (api_key if api_key is not None else os.getenv("TMDB_API_KEY", "")).strip()
        self.timeout = timeout
        self._cache: dict[str, tuple[float, list[CatalogItem]]] = {}
        self._detail_cache: dict[str, tuple[float, CatalogItem]] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str) -> list[CatalogItem]:
        query = " ".join(query.split()).strip()
        key = title_key(query)
        if not self.configured or not key:
            return []
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return list(cached[1])
        try:
            response = httpx.get(
                "https://api.themoviedb.org/3/search/movie",
                params={"api_key": self.api_key, "query": query, "include_adult": "false", "language": "en-US", "page": 1},
                headers={"Accept": "application/json", "User-Agent": "StoryScout/1.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            items = [item for row in results[:8] if isinstance(row, dict) and (item := self._to_item(row))]
        except (httpx.HTTPError, ValueError, TypeError) as error:
            # Do not include request URLs or exception strings: v3 auth is a
            # query parameter and diagnostic logging must never disclose it.
            logger.info("TMDB title lookup unavailable (%s)", type(error).__name__)
            items = []
        with self._lock:
            self._cache[key] = (now + 6 * 60 * 60, list(items))
            if len(self._cache) > 256:
                self._cache.pop(next(iter(self._cache)))
        return items

    @staticmethod
    def _to_item(row: dict) -> CatalogItem | None:
        tmdb_id = row.get("id")
        title = str(row.get("title") or row.get("original_title") or "").strip()
        if not tmdb_id or not title:
            return None
        release = str(row.get("release_date") or "")
        year_match = re.match(r"^(\d{4})-\d{2}-\d{2}$", release)
        year = int(year_match[1]) if year_match else None
        original_language = str(row.get("original_language") or "").lower()
        language = LANGUAGES.get(original_language, original_language or "Unknown")
        genre_values = row.get("genre_ids", [])
        if not genre_values and isinstance(row.get("genres"), list):
            genre_values = [genre.get("id") for genre in row["genres"] if isinstance(genre, dict)]
        genres = list(dict.fromkeys(TMDB_GENRES.get(int(value), "") for value in genre_values if str(value).isdigit()))
        genres = [genre for genre in genres if genre]
        overview = str(row.get("overview") or "").strip()
        aliases = [str(row.get("original_title") or "").strip()]
        aliases = [alias for alias in aliases if alias and title_key(alias) != title_key(title)]
        source_url = f"https://www.themoviedb.org/movie/{int(tmdb_id)}"
        provenance = {"year": {"source": "TMDB movie search result", "url": source_url},
                      "genres": {"source": "TMDB movie search result", "url": source_url},
                      "language": {"source": "TMDB original_language", "url": source_url}}
        if overview:
            provenance["description"] = {"source": "TMDB movie overview", "url": source_url}
        return CatalogItem(
            id=f"movie_tmdb_{int(tmdb_id)}", media_type="movie", title=title,
            description=overview or "TMDB has no synopsis for this title.",
            retrieval_text=overview, genres=genres, language=language, year=year,
            source="tmdb-api", source_url=source_url, title_aliases=aliases,
            director=None, runtime_minutes=None,
            description_source="TMDB" if overview else "", description_source_url=source_url if overview else "",
            description_provenance="TMDB movie overview" if overview else "",
            text_source="TMDB" if overview else "", text_source_url=source_url if overview else "",
            metadata_provenance=provenance,
        )

    def details(self, item: CatalogItem) -> CatalogItem:
        """Hydrate exact search hits with detail fields such as runtime."""
        if not self.configured or not item.id.startswith("movie_tmdb_"):
            return item
        now = time.monotonic()
        with self._lock:
            cached = self._detail_cache.get(item.id)
            if cached and cached[0] > now:
                return cached[1]
        try:
            response = httpx.get(
                f"https://api.themoviedb.org/3/movie/{item.id.removeprefix('movie_tmdb_')}",
                params={"api_key": self.api_key, "language": "en-US"},
                headers={"Accept": "application/json", "User-Agent": "StoryScout/1.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            detail = response.json()
            if not isinstance(detail, dict) or int(detail.get("id", -1)) != int(item.id.rsplit("_", 1)[-1]):
                return item
            hydrated = self._to_item(detail)
            runtime = detail.get("runtime")
            if hydrated is None:
                return item
            hydrated.runtime_minutes = runtime if isinstance(runtime, int) and runtime > 0 else None
            hydrated.metadata_provenance["runtime_minutes"] = {
                "source": "TMDB movie details", "url": hydrated.source_url,
            }
            with self._lock:
                self._detail_cache[item.id] = (now + 6 * 60 * 60, hydrated)
            return hydrated
        except (httpx.HTTPError, ValueError, TypeError):
            logger.info("TMDB movie details unavailable")
            return item

    @staticmethod
    def identity_matches(query: str, items: list[CatalogItem]) -> tuple[list[CatalogItem], bool]:
        """Return exact title/alternate-name matches or cautious suggestions."""
        key = title_key(query)
        exact = [item for item in items if any(title_key(name) == key for name in [item.title, *item.title_aliases])]
        if exact:
            return exact, False
        ranked = sorted(items, key=lambda item: max(SequenceMatcher(None, key, title_key(name)).ratio() for name in [item.title, *item.title_aliases]), reverse=True)
        suggestions = [item for item in ranked if max(SequenceMatcher(None, key, title_key(name)).ratio() for name in [item.title, *item.title_aliases]) >= .86][:4]
        return suggestions, bool(suggestions)
