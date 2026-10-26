"""Import a reproducible English-only Project Gutenberg metadata sample."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/gutenberg/pg_catalog.csv.gz"
OUTPUT = ROOT / "data/expanded/books.csv"
URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
FIELDS = ["id", "title", "description", "genres", "language", "year", "source", "source_url", "mood_tags", "theme_tags", "tag_provenance", "authors", "page_count", "publisher", "verified_warnings", "search_aliases"]
LANGUAGES = {"en": "English", "fr": "French", "de": "German", "es": "Spanish", "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "fi": "Finnish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "ru": "Russian", "zh": "Chinese", "ja": "Japanese", "hu": "Hungarian", "el": "Greek", "la": "Latin", "eo": "Esperanto"}


def _catalog_bytes(source: Path, refresh: bool = False) -> bytes:
    if source.exists() and not refresh:
        return source.read_bytes()
    source.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "StoryScout-NLP-course-project/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    source.write_bytes(payload)
    return payload


def import_catalog(source: Path = SOURCE, output: Path = OUTPUT, limit: int = 10_000, refresh: bool = False) -> int:
    if limit < 1:
        raise ValueError("limit must be positive")
    payload = _catalog_bytes(source, refresh)
    with gzip.open(io.BytesIO(payload), "rt", encoding="utf-8-sig", newline="") as file:
        source_rows = [row for row in csv.DictReader(file) if row.get("Type") == "Text" and row.get("Language") == "en" and row.get("Title", "").strip() and (row.get("Subjects", "").strip() or row.get("Bookshelves", "").strip())]
    # Hash sampling avoids selecting only the earliest catalog IDs; deterministic
    # sampling keeps imports stable across runs for the same source snapshot.
    source_rows.sort(key=lambda row: hashlib.sha256(row["Text#"].encode("utf-8")).digest())
    selected = source_rows[:limit]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for row in sorted(selected, key=lambda item: int(item["Text#"])):
            subjects = [x.strip().strip(" .") for x in (row.get("Subjects", "") + ";" + row.get("Bookshelves", "")).split(";") if x.strip()]
            subjects = list(dict.fromkeys(subjects))[:12]
            # Subjects are preserved as source-derived tags, never relabeled as genres.
            writer.writerow({
                "id": f"book_pg_{row['Text#']}", "title": row["Title"].strip(),
                "description": "Plot description is not supplied by this Project Gutenberg catalog record.",
                "genres": "", "language": LANGUAGES.get(row["Language"], row["Language"]), "year": "",
                "source": "project-gutenberg-catalog", "source_url": f"https://www.gutenberg.org/ebooks/{row['Text#']}",
                "mood_tags": "", "theme_tags": "|".join(subjects),
                "tag_provenance": "Project Gutenberg catalog subject/bookshelf fields; display text is a metadata-only notice",
                "authors": row.get("Authors", "").strip(), "page_count": "", "publisher": "",
                "verified_warnings": "", "search_aliases": "",
            })
    return len(selected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--refresh", action="store_true", help="Download the current official metadata snapshot")
    args = parser.parse_args()
    print(f"Wrote {import_catalog(args.source, args.output, args.limit, args.refresh):,} book records to {args.output}")
