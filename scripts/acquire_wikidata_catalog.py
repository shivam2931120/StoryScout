"""Fetch a reproducible CC0 book/movie catalog from Wikidata SPARQL."""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENDPOINTS = ["https://qlever.dev/api/wikidata", "https://query.wikidata.org/sparql"]
FIELDS = ["id", "title", "description", "genres", "language", "year", "source", "source_url", "mood_tags", "theme_tags", "tag_provenance", "authors", "page_count", "publisher", "director", "runtime_minutes", "cast", "verified_warnings"]


def query_for(domain: str, limit: int) -> str:
    instance = "Q571" if domain == "book" else "Q11424"
    book = domain == "book"
    return f'''SELECT ?item ?itemLabel ?itemDescription
      (SAMPLE(?yearValue) AS ?year) (SAMPLE(?pageValue) AS ?pages)
      (SAMPLE(?runtimeValue) AS ?runtime)
      (GROUP_CONCAT(DISTINCT ?authorLabel; separator="|") AS ?authors)
      (GROUP_CONCAT(DISTINCT ?directorLabel; separator="|") AS ?directors)
      (GROUP_CONCAT(DISTINCT ?castLabel; separator="|") AS ?cast)
      (GROUP_CONCAT(DISTINCT ?genreLabel; separator="|") AS ?genres)
      (GROUP_CONCAT(DISTINCT ?languageLabel; separator="|") AS ?languages)
    WHERE {{
      ?item wdt:P31 wd:{instance}; rdfs:label ?itemLabel; schema:description ?itemDescription.
      FILTER(LANG(?itemLabel)="en" && LANG(?itemDescription)="en")
      OPTIONAL {{ ?item wdt:P577 ?date. BIND(YEAR(?date) AS ?yearValue) }}
      OPTIONAL {{ ?item wdt:P1104 ?pageValue }}
      OPTIONAL {{ ?item wdt:P2047 ?runtimeValue }}
      OPTIONAL {{ ?item wdt:P136 ?genre. ?genre rdfs:label ?genreLabel. FILTER(LANG(?genreLabel)="en") }}
      OPTIONAL {{ ?item wdt:P407 ?language. ?language rdfs:label ?languageLabel. FILTER(LANG(?languageLabel)="en") }}
      {'OPTIONAL { ?item wdt:P50 ?author. ?author rdfs:label ?authorLabel. FILTER(LANG(?authorLabel)="en") }' if book else ''}
      {'OPTIONAL { ?item wdt:P57 ?director. ?director rdfs:label ?directorLabel. FILTER(LANG(?directorLabel)="en") }' if not book else ''}
      {'OPTIONAL { ?item wdt:P161 ?castMember. ?castMember rdfs:label ?castLabel. FILTER(LANG(?castLabel)="en") }' if not book else ''}
    }} GROUP BY ?item ?itemLabel ?itemDescription LIMIT {limit}'''


def read_rows(endpoint: str, query: str) -> list[dict]:
    url = endpoint + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": "StoryScout/1.0 (educational NLP catalog importer)", "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    return payload["results"]["bindings"]


def value(row: dict, field: str, default: str = "") -> str:
    return row.get(field, {}).get("value", default)


def flatten(row: dict, domain: str) -> dict[str, str]:
    qid = value(row, "item").rsplit("/", 1)[-1]
    year = value(row, "year")
    try:
        year = str(int(float(year))) if year else ""
    except ValueError:
        year = ""
    runtime = value(row, "runtime")
    try:
        runtime = str(round(float(runtime))) if runtime else ""
    except ValueError:
        runtime = ""
    pages = value(row, "pages")
    try:
        pages = str(round(float(pages))) if pages else ""
    except ValueError:
        pages = ""
    genres = value(row, "genres").replace(",", " ").replace("|", "|")
    result = {field: "" for field in FIELDS}
    result.update({
        "id": f"{domain}_wd_{qid}",
        "title": value(row, "itemLabel"),
        "description": value(row, "itemDescription"),
        "genres": genres,
        "language": value(row, "languages").split("|")[0] or "Unknown",
        "year": year,
        "source": "wikidata-cc0",
        "source_url": value(row, "item"),
        "tag_provenance": "Wikidata CC0 statements and English item description",
        "authors": value(row, "authors").split("|")[0] if domain == "book" else "",
        "page_count": pages if domain == "book" else "",
        "director": value(row, "directors").split("|")[0] if domain == "movie" else "",
        "runtime_minutes": runtime if domain == "movie" else "",
        "cast": "|".join(value(row, "cast").split("|")[:5]) if domain == "movie" else "",
    })
    return result


def acquire(domain: str, limit: int, endpoints: list[str] = ENDPOINTS) -> list[dict[str, str]]:
    query = query_for(domain, limit)
    last_error = None
    for endpoint in endpoints:
        try:
            rows = read_rows(endpoint, query)
            records = [flatten(row, domain) for row in rows]
            records = [row for row in records if row["id"].split("_wd_")[-1] and row["title"] and row["description"]]
            seen = set()
            return [row for row in records if not (row["id"] in seen or seen.add(row["id"]))]
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            last_error = error
            print(f"{endpoint} unavailable: {type(error).__name__}: {error}")
            time.sleep(1)
    raise RuntimeError(f"Could not acquire {domain} data from Wikidata endpoints: {last_error}")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1000, help="Maximum results per domain (not a guaranteed count)")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "expanded")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 5000:
        parser.error("--limit must be between 1 and 5000")
    for domain, name in (("book", "books.csv"), ("movie", "movies.csv")):
        rows = acquire(domain, args.limit)
        target = args.output_dir / name
        write_csv(target, rows)
        print(f"Wrote {len(rows)} sourced {domain} records to {target}")
        time.sleep(1)


if __name__ == "__main__":
    main()
