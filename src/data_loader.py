"""Catalog loading, normalization, and validation."""
from __future__ import annotations

from pathlib import Path
import pandas as pd
from .config import DATA_DIR, DEMO_FILES
from .preprocessing import normalize_text
from .schemas import CatalogItem, item_from_row

REQUIRED = ["id", "title", "description", "genres", "language", "year", "source", "source_url"]


def load_catalog(path: str | Path, media_type: str) -> list[CatalogItem]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [field for field in REQUIRED if field not in frame.columns]
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(missing)}")
    items = [item_from_row(row, media_type) for row in frame.to_dict(orient="records")]
    validate_catalog(items)
    return items


def validate_catalog(items: list[CatalogItem]) -> None:
    ids = [item.id for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate catalog IDs found")
    for item in items:
        if not item.id.startswith(("book_", "movie_")):
            raise ValueError(f"ID must have a domain prefix: {item.id}")
        if not item.title.strip() or not item.description.strip():
            raise ValueError(f"Missing title or description: {item.id}")
        if item.year is not None and not 1000 <= item.year <= 2100:
            raise ValueError(f"Invalid year for {item.id}")
        if item.page_count is not None and item.page_count <= 0:
            raise ValueError(f"Invalid page count for {item.id}")
        if item.runtime_minutes is not None and item.runtime_minutes <= 0:
            raise ValueError(f"Invalid runtime for {item.id}")


def catalog_status(items: list[CatalogItem]) -> str:
    sources = {item.source for item in items}
    return "demonstration data" if sources <= {"demo", "synthetic-demo"} else "expanded/user data"


def catalog_identity(item: CatalogItem) -> tuple[str, str]:
    """Deduplicate equivalent records while keeping re-releases distinct."""
    title = normalize_text(item.title)
    if item.media_type == "book":
        return title, normalize_text(item.authors or "")
    return title, str(item.year or "")


def load_active_catalogs(demo_files: dict | None = None, expanded_dir: str | Path | None = None) -> dict[str, list[CatalogItem]]:
    """Load the same demo + expanded records and dedupe policy everywhere."""
    demo_files = demo_files or DEMO_FILES
    expanded_dir = Path(expanded_dir) if expanded_dir else DATA_DIR / "expanded"
    catalogs = {domain: load_catalog(demo_files[domain], domain) for domain in ("book", "movie")}
    for domain, filename in (("book", "books.csv"), ("movie", "movies.csv")):
        path = expanded_dir / filename
        if not path.exists():
            continue
        known = {catalog_identity(item) for item in catalogs[domain]}
        for item in load_catalog(path, domain):
            identity = catalog_identity(item)
            if identity not in known:
                catalogs[domain].append(item)
                known.add(identity)
    apply_description_enrichment(catalogs)
    return catalogs


def apply_description_enrichment(catalogs: dict[str, list[CatalogItem]], path: str | Path | None = None) -> int:
    """Attach source-backed short summaries without overwriting catalog fields."""
    path = Path(path) if path else DATA_DIR / "enriched" / "descriptions.csv"
    if not path.exists():
        return 0
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"id", "description", "description_source", "description_source_url", "description_provenance"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing fields: {', '.join(sorted(missing))}")
    if frame["id"].duplicated().any():
        raise ValueError(f"{path} has duplicate item IDs")
    by_id = {item.id: item for items in catalogs.values() for item in items}
    applied = 0
    for row in frame.to_dict(orient="records"):
        item = by_id.get(row["id"])
        if not item or not row["description"].strip() or item.description_provenance:
            continue
        if not item.source.startswith(("movielens", "project-gutenberg")):
            continue
        item.description = row["description"].strip()
        item.description_source = row["description_source"].strip()
        item.description_source_url = row["description_source_url"].strip()
        item.description_provenance = row["description_provenance"].strip()
        applied += 1
    return applied
