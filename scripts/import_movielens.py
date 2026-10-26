"""Normalize the public MovieLens latest-small title/genre catalog."""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/source/movielens"
OUTPUT = ROOT / "data/expanded/movies.csv"
FIELDS = ["id", "title", "description", "genres", "language", "year", "source", "source_url", "mood_tags", "theme_tags", "tag_provenance", "director", "runtime_minutes", "cast", "verified_warnings", "search_aliases"]
GENRES = {"sci-fi": "science fiction", "children": "family", "film-noir": "film noir", "(no genres listed)": ""}


def convert(source: Path = SOURCE, output: Path = OUTPUT) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    rows = []
    with (source / "movies.csv").open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            raw_title = row["title"].strip()
            match = re.search(r"\s*\((\d{4})\)$", raw_title)
            year = int(match.group(1)) if match else ""
            title = raw_title[:match.start()].strip() if match else raw_title
            if not title:
                continue
            dedupe_key = f"{title.casefold()}|{year}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            genres = []
            for genre in row.get("genres", "").split("|"):
                normalized = GENRES.get(genre.casefold(), genre.casefold())
                if normalized and normalized not in genres:
                    genres.append(normalized)
            genre_text = "|".join(genres)
            if genres:
                description = "Plot description is not provided in the MovieLens title metadata."
            else:
                description = "Plot description and genre information are not provided in the MovieLens title metadata."
            rows.append({
                "id": f"movie_ml_{row['movieId']}", "title": title, "description": description,
                "genres": genre_text, "language": "", "year": year, "source": "movielens-latest-small",
                "source_url": f"https://movielens.org/movies/{row['movieId']}",
                "mood_tags": "", "theme_tags": "", "tag_provenance": "MovieLens genre metadata; description is a generated metadata-only notice, not plot content",
                "director": "", "runtime_minutes": "", "cast": "", "verified_warnings": "", "search_aliases": "",
            })
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(f"Wrote {convert(args.source, args.output):,} MovieLens records to {args.output}")
