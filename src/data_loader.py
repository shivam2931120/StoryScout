"""Catalog loading, normalization, and validation."""
from __future__ import annotations

from pathlib import Path
import re
import json
import os,gzip
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
    if demo_files is None and expanded_dir is None and os.getenv('STORYSCOUT_CATALOG_PROFILE')=='compact':
        with gzip.open(DATA_DIR/'compact/catalogs.json.gz','rt',encoding='utf-8') as source:
            catalogs={domain:[CatalogItem(**row) for row in rows] for domain,rows in json.load(source).items()}
        for items in catalogs.values():validate_catalog(items)
        return catalogs
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
    supplemental=DATA_DIR/'enriched/supplemental_catalog.json'
    if supplemental.exists():
        for row in json.loads(supplemental.read_text()).get('records',[]):
            item=CatalogItem(**row)
            if item.media_type not in catalogs:raise ValueError('Invalid supplemental media type')
            if not item.source_url.startswith('https://'):raise ValueError('Supplemental record requires source URL')
            known={catalog_identity(x) for x in catalogs[item.media_type]}
            if catalog_identity(item) not in known:
                catalogs[item.media_type].append(item)
        for items in catalogs.values():validate_catalog(items)
    apply_description_enrichment(catalogs)
    apply_nlp_sources(catalogs)
    return catalogs


def apply_nlp_sources(catalogs: dict[str, list[CatalogItem]], directory: str | Path | None = None) -> None:
    """Join local factual sources. Predictions never populate source metadata."""
    directory = Path(directory) if directory else DATA_DIR / 'enriched'
    by_id = {item.id: item for items in catalogs.values() for item in items}
    subject_rules={'mystery':r'detective and mystery (?:stories|fiction)|mystery fiction',
        'science fiction':r'science fiction', 'fantasy':r'fantasy fiction|fantastic fiction|fairy tales',
        'romance':r'love stories|romance fiction', 'adventure':r'adventure stories|adventure fiction',
        'history':r'historical fiction', 'horror':r'horror tales|ghost stories|gothic fiction',
        'comedy':r'humorous stories|humorous fiction|comic fiction', 'family':r"children's stories|children's literature", 'drama':r'\bdrama\b'}
    for item in catalogs['book']:
        if not item.genres and item.source.startswith('project-gutenberg'):
            subjects=' '.join(item.theme_tags).lower()
            item.subject_genres=[genre for genre,pattern in subject_rules.items() if re.search(pattern,subjects)]
            if item.subject_genres:
                item.metadata_provenance['subject_genres']={'source':'Deterministic mapping of supplied Gutenberg subject headings; not model predictions','url':item.source_url}
    summaries = directory / 'book_summaries.csv.gz'
    if summaries.exists():
        frame = pd.read_csv(summaries, dtype=str, keep_default_na=False)
        if frame['id'].duplicated().any():
            raise ValueError('Duplicate book summary IDs')
        for row in frame.to_dict(orient='records'):
            item = by_id.get(row['id'])
            if not item or not item.source.startswith('project-gutenberg') or item.description_provenance:
                continue
            if not row['summary_text'].strip() or not row['source_url'].startswith('https://www.gutenberg.org/ebooks/'):
                continue
            item.retrieval_text = row['summary_text']
            item.text_source, item.text_source_url = row['source'], row['source_url']
            item.description, item.description_provenance = row['opening_excerpt'], row['provenance']
            item.description_source, item.description_source_url = row['source'], row['source_url']
    plots = directory / 'movie_plots.csv.gz'
    if plots.exists():
        frame = pd.read_csv(plots, dtype=str, keep_default_na=False)
        if frame['id'].duplicated().any(): raise ValueError('Duplicate plot IDs')
        for row in frame.to_dict(orient='records'):
            item = by_id.get(row['id'])
            if not item: continue
            item.retrieval_text = row['plot_text']
            item.text_source, item.text_source_url = row['source'], row['source_url']
            if not item.director and row.get('director'):
                item.director = row['director']
                item.metadata_provenance['director'] = {'source':row['source'],'url':row['source_url']}
            if item.source.startswith('movielens') and not item.description_provenance:
                item.description = row['opening_excerpt']
                item.description_source = row['source']
                item.description_source_url = row['source_url']
                item.description_provenance = 'Extractive opening excerpt of the original Wikipedia plot; full text indexed locally; CC BY-SA 4.0'
    metadata = directory / 'movie_metadata.csv'
    if metadata.exists():
        frame = pd.read_csv(metadata, dtype=str, keep_default_na=False)
        if frame['id'].duplicated().any(): raise ValueError('Duplicate metadata IDs')
        for row in frame.to_dict(orient='records'):
            item = by_id.get(row['id'])
            if not item: continue
            provenance = {'source':row['source'],'url':row['source_url'],'license':row.get('license','')}
            if not item.runtime_minutes and row['runtime_minutes']:
                value = int(row['runtime_minutes'])
                if not 1 <= value <= 1000: raise ValueError('Invalid sourced runtime')
                item.runtime_minutes = value
                item.metadata_provenance['runtime_minutes'] = provenance
            if item.language.lower() == 'unknown' and row['language']:
                item.language = row['language']
                item.metadata_provenance['language'] = provenance
    predictions=directory/'genre_predictions.json'
    if predictions.exists():
        for item_id, genres in json.loads(predictions.read_text()).get('items',{}).items():
            if item_id in by_id: by_id[item_id].predicted_genres=genres


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
