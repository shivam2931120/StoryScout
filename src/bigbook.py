"""On-demand Big Book API adapter.

This adapter deliberately keeps no cache or local copy: Big Book API terms
restrict copying/persisting its records. Calls use the secret header, never a
query-string key. Returned records live only for the current request.
"""
from __future__ import annotations

import html
import os
import re
from typing import Any

import httpx

from .schemas import CatalogItem

API_ROOT = "https://api.bigbookapi.com"


def _int_or_none(value: Any) -> int | None:
    try:
        number = float(value)
        return int(number) if number.is_integer() and number > 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _description(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return re.sub(r"\s+", " ", text).strip()[:4000]


def _authors(value: Any) -> str | None:
    if not isinstance(value, list):
        return None
    names = [str(row.get("name", "")).strip() for row in value if isinstance(row, dict)]
    names = [name for name in names if name]
    return ", ".join(dict.fromkeys(names)) or None


class BigBookSource:
    """Small request-scoped client for live book candidates and metadata."""

    def __init__(self, api_key: str | None = None, *, client: Any = None):
        self.api_key = (api_key if api_key is not None else os.getenv("BIGBOOK_API_KEY", "")).strip()
        self.client = client

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.configured:
            return None
        headers = {"x-api-key": self.api_key, "Accept": "application/json"}
        try:
            response = (self.client or httpx).get(
                f"{API_ROOT}/{path.lstrip('/')}",
                params=params or {},
                headers=headers,
                timeout=8.0,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except (httpx.HTTPError, ValueError, TypeError):
            return None

    def details(self, book_id: str | int) -> CatalogItem | None:
        if not str(book_id).isdigit():
            return None
        payload = self._get(str(book_id))
        if not payload or not payload.get("title"):
            return None
        title = str(payload["title"]).strip()
        if not title:
            return None
        api_id = str(payload.get("id", book_id))
        source_url = f"{API_ROOT}/{api_id}"
        description = _description(payload.get("description"))
        year = _int_or_none(payload.get("publish_date"))
        pages = _int_or_none(payload.get("number_of_pages"))
        genres = payload.get("genres", [])
        if isinstance(genres, dict):
            genres = [genres.get("name", "")]
        if not isinstance(genres, list):
            genres = []
        genres = list(dict.fromkeys(
            str(x.get("name", "") if isinstance(x, dict) else x).strip().lower().replace("_", " ")
            for x in genres if str(x.get("name", "") if isinstance(x, dict) else x).strip()
        ))
        item = CatalogItem(
            id=f"book_bigbook_{api_id}", media_type="book", title=title,
            description=description or "Description unavailable from the book record.",
            genres=genres, language="Unknown", year=year, source="bigbook-api",
            source_url=source_url, authors=_authors(payload.get("authors")),
            page_count=pages, publisher=None,
            description_source="Big Book API" if description else "",
            description_source_url=source_url if description else "",
            description_provenance="Description returned on demand by Big Book API; not locally retained" if description else "",
            retrieval_text=description,
            metadata_provenance={
                "title": {"source": "Big Book API", "url": source_url},
                **({"authors": {"source": "Big Book API", "url": source_url}} if payload.get("authors") else {}),
                **({"year": {"source": "Big Book API publish_date", "url": source_url}} if year else {}),
                **({"page_count": {"source": "Big Book API number_of_pages", "url": source_url}} if pages else {}),
                **({"genres": {"source": "Big Book API", "url": source_url}} if genres else {}),
            },
        )
        return item

    @staticmethod
    def _flatten_books(payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = payload.get("books", [])
        if not isinstance(rows, list):
            return []
        flattened = []
        for row in rows:
            if isinstance(row, dict):
                flattened.append(row)
            elif isinstance(row, list):
                flattened.extend(book for book in row if isinstance(book, dict))
        seen: set[str] = set()
        result = []
        for row in flattened:
            key = str(row.get("id", ""))
            if key.isdigit() and key not in seen and row.get("title"):
                seen.add(key)
                result.append(row)
        return result

    def search(self, query: str, *, number: int = 8, details_limit: int = 8) -> list[CatalogItem]:
        """Fetch current candidates and their metadata; retain nothing between calls."""
        query = query.strip()
        if not query or not self.configured:
            return []
        payload = self._get("search-books", {
            "query": query, "number": max(1, min(int(number), 20)),
        })
        if not payload:
            return []
        rows = self._flatten_books(payload)
        found: list[CatalogItem] = []
        for row in rows[:max(0, min(int(details_limit), 10))]:
            item = self.details(row["id"])
            if item:
                found.append(item)
        return found
