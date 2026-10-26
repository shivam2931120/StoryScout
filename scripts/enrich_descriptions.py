"""Add source-backed, concise descriptions to metadata-only catalog records."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_loader import load_active_catalogs
from src.description_enrichment import NemotronDescriptionSummarizer, find_wikipedia_source, get_server_api_key

OUTPUT = ROOT / "data" / "enriched" / "descriptions.csv"
CACHE = ROOT / "artifacts" / ".cache" / "wikipedia_description_cache.json"
FIELDS = ["id", "description", "description_source", "description_source_url", "description_provenance", "generation_model"]


def _read_output() -> dict[str, dict[str, str]]:
    if not OUTPUT.exists():
        return {}
    with OUTPUT.open(encoding="utf-8", newline="") as file:
        return {row["id"]: row for row in csv.DictReader(file)}


def _write_output(rows: dict[str, dict[str, str]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temp_path = OUTPUT.with_suffix(".csv.tmp")
    with temp_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows[key] for key in sorted(rows))
    temp_path.replace(OUTPUT)


def _read_cache() -> dict[str, dict[str, str] | None]:
    try:
        value = json.loads(CACHE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_cache(cache: dict[str, dict[str, str] | None]) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def run(max_candidates: int, batch_size: int, requested_ids: set[str] | None = None) -> int:
    api_key = get_server_api_key()
    if not api_key:
        raise SystemExit("Set NVIDIA_API_KEY in the environment or .streamlit/secrets.toml before enrichment.")
    summarizer = NemotronDescriptionSummarizer(api_key)
    catalogs = load_active_catalogs()
    output = _read_output()
    cache = _read_cache()
    total_added = 0

    for domain, items in catalogs.items():
        pending: list[dict[str, str]] = []
        candidates = [item for item in items
                      if item.source.startswith(("movielens", "project-gutenberg"))
                      and not item.description_provenance and item.id not in output
                      and (not requested_ids or item.id in requested_ids)]
        candidates.sort(key=lambda item: hashlib.sha256(item.id.encode("utf-8")).hexdigest())
        visited = 0
        for item in candidates:
            if visited >= max_candidates:
                break
            visited += 1
            if item.id not in cache:
                try:
                    cache[item.id] = find_wikipedia_source(item)
                except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
                    print(f"Source lookup skipped ({type(error).__name__}).")
                else:
                    _write_cache(cache)
                time.sleep(0.15)
            if visited % 25 == 0:
                print(f"{domain.title()}: checked {visited}/{min(max_candidates, len(candidates))} candidate titles.")
            source = cache.get(item.id)
            if source:
                pending.append({
                    "id": item.id,
                    "title": item.title,
                    "media_type": item.media_type,
                    "year": str(item.year or "unknown"),
                    "source_excerpt": source["excerpt"][:2600],
                    "source_title": source["title"],
                    "source_url": source["url"],
                })

        print(f"{domain.title()}: {len(pending)} source excerpts from {visited} title lookups.")
        for offset in range(0, len(pending), batch_size):
            batch = pending[offset:offset + batch_size]
            try:
                summaries = summarizer.summarize_batch(batch)
            except Exception as error:
                print(f"Nemotron batch skipped ({type(error).__name__}); catalog originals remain unchanged.")
                continue
            for record in batch:
                description = summaries.get(record["id"])
                if not description:
                    continue
                output[record["id"]] = {
                    "id": record["id"],
                    "description": description,
                    "description_source": "Wikipedia (CC BY-SA 4.0)",
                    "description_source_url": record["source_url"],
                    "description_provenance": "AI paraphrase of the exact-title Wikipedia article lead; verify details with source",
                    "generation_model": summarizer.model,
                }
            _write_output(output)
            added = len(summaries)
            total_added += added
            print(f"{domain.title()}: added {added} sourced summaries ({min(offset + batch_size, len(pending))}/{len(pending)} processed).")
            time.sleep(0.2)
    print(f"Saved {len(output)} descriptions to {OUTPUT}; added {total_added} this run.")
    print("Only source-backed paraphrases are written. Unmatched titles and empty model replies remain unknown.")
    return total_added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-candidates-per-domain", type=int, default=100,
                        help="Maximum Wikipedia title lookups per domain (default: 100).")
    parser.add_argument("--batch-size", type=int, default=6,
                        help="Items sent in each source-grounded model request (default: 6).")
    parser.add_argument("--item-id", action="append", default=[],
                        help="Enrich this exact catalog ID; repeat to select multiple records.")
    args = parser.parse_args()
    if not 1 <= args.max_candidates_per_domain <= 1000:
        parser.error("--max-candidates-per-domain must be between 1 and 1000")
    if not 1 <= args.batch_size <= 10:
        parser.error("--batch-size must be between 1 and 10")
    run(args.max_candidates_per_domain, args.batch_size, set(args.item_id) or None)


if __name__ == "__main__":
    main()
