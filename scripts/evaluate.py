"""Run retrieval and preference checks against transparent developer labels."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json
import statistics
import sys
import time
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import ARTIFACT_DIR
from src.data_loader import load_active_catalogs
from src.retrieval import RetrievalIndex
from src.cross_media import reference_context
from src.preferences import parse_preferences, merge_preferences
from src.schemas import Preferences

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR=Path(os.getenv('STORYSCOUT_EVALUATION_DIR',str(ARTIFACT_DIR)))
QUERY_FILE = ROOT / "data/evaluation_queries.json"
PREFERENCE_FILE = ROOT / "data/preference_evaluation.json"


def preferences_for(row: dict) -> Preferences:
    preferences = parse_preferences(row["query"]).preferences
    for field, value in row.get("constraints", {}).items():
        setattr(preferences, field, value)
    return preferences


def compliant(item, constraints: dict) -> bool:
    if item.year is None and (constraints.get("min_year") is not None or constraints.get("max_year") is not None):
        return False
    if constraints.get("min_year") is not None and item.year < constraints["min_year"]:
        return False
    if constraints.get("max_year") is not None and item.year > constraints["max_year"]:
        return False
    if constraints.get("language") and constraints["language"].casefold() not in item.language.casefold().split('|'):
        return False
    if set(constraints.get("excluded_genres", [])) & set(item.genres):
        return False
    if constraints.get("excluded_genres") and not item.genres:
        return False
    if item.media_type == "book" and constraints.get("max_pages") is not None:
        if item.page_count is None or item.page_count > constraints["max_pages"]:
            return False
    if item.media_type == "movie" and constraints.get("max_runtime") is not None:
        if item.runtime_minutes is None or item.runtime_minutes > constraints["max_runtime"]:
            return False
    return True


def aggregate_rows(rows: list[dict]) -> dict:
    if not rows:
        return {"queries": 0, "precision_at_5": None, "recall_at_5": None, "mrr_at_5": None, "hard_constraint_compliance": None}
    return {
        "queries": len(rows),
        "precision_at_5": round(statistics.mean(row["precision_at_5"] for row in rows), 4),
        "recall_at_5": round(statistics.mean(row["recall_at_5"] for row in rows), 4),
        "mrr_at_5": round(statistics.mean(row["mrr_at_5"] for row in rows), 4),
        "hard_constraint_compliance": round(1-sum(row['constraint_violations'] for row in rows)/sum(row['returned_count'] for row in rows),4) if sum(row['returned_count'] for row in rows) else None,
        "answer_rate": round(statistics.mean(bool(row['returned_count']) for row in rows),4),
        "precision_when_returned": round(statistics.mean(row['hits']/row['returned_count'] for row in rows if row['returned_count']),4) if any(row['returned_count'] for row in rows) else None,
        "slot_fill_rate": round(sum(row['returned_count'] for row in rows)/(5*len(rows)),4),
        "nonempty_compliant_query_rate": round(statistics.mean(row['nonempty_compliant_query_rate'] for row in rows),4),
    }


def evaluate_mode(mode: str, catalogs: dict, queries: list[dict]) -> tuple[dict, list[dict]]:
    started = time.perf_counter()
    indexes = {media: RetrievalIndex(items, mode=mode) for media, items in catalogs.items()}
    preparation_ms = (time.perf_counter() - started) * 1000
    semantic_ran = all(index.semantic_available for index in indexes.values())
    if mode == "semantic" and not semantic_ran:
        return {"status": "not run: sentence embedding model unavailable", "semantic_ran": False, "index_preparation_ms": round(preparation_ms, 2)}, []

    by_domain: dict[str, list[dict]] = defaultdict(list)
    details = []
    latencies = []
    items_by_id = {item.id: item for values in catalogs.values() for item in values}
    for row in queries:
        active_domains = ["book", "movie"] if row["media"] == "both" else (["book"] if row["media"] == "books" else ["movie"])
        relevant_all = set(row["relevant_ids"])
        preferences = preferences_for(row)
        reference = items_by_id.get(row.get("reference_id"))
        for domain in active_domains:
            relevant = {item_id for item_id in relevant_all if item_id.startswith(domain + "_")}
            start = time.perf_counter()
            query_text = row["query"]
            excluded = set()
            if reference:
                query_text = reference_context(reference) + " " + query_text
                if reference.media_type == domain:
                    excluded.add(reference.id)
            recommendations = indexes[domain].search(query_text, preferences, top_k=5, exclude_ids=excluded)
            latencies.append((time.perf_counter() - start) * 1000)
            returned = recommendations[:5]
            returned_ids = [rec.item.id for rec in returned]
            hits = sum(item_id in relevant for item_id in returned_ids)
            row_metrics = {
                "precision_at_5": hits / 5,
                "recall_at_5": hits / len(relevant) if relevant else 0.0,
                "mrr_at_5": next((1 / rank for rank, item_id in enumerate(returned_ids, 1) if item_id in relevant), 0.0),
                "hard_constraint_compliance": float(all(compliant(rec.item, row.get("constraints", {})) for rec in returned)) if returned else None,
                "returned_count": len(returned), "hits": hits,
                "constraint_violations":sum(not compliant(rec.item,row.get('constraints',{})) for rec in returned),
                "nonempty_compliant_query_rate":float(bool(returned) and all(compliant(rec.item, row.get('constraints', {})) for rec in returned)),
            }
            by_domain[domain].append(row_metrics)
            details.append({
                "mode": mode, "query": row["query"], "reference_id": row.get("reference_id", ""), "category": row.get("category", ""), "domain": domain,
                "relevant_ids": "|".join(sorted(relevant)), "returned_ids": "|".join(returned_ids),
                "hits": hits, **row_metrics,
            })
    domain_metrics = {domain: aggregate_rows(by_domain[domain]) for domain in ("book", "movie")}
    active = [metrics for metrics in domain_metrics.values() if metrics["queries"]]
    metric_keys = ("precision_at_5", "recall_at_5", "mrr_at_5", "hard_constraint_compliance", "answer_rate", "precision_when_returned", "slot_fill_rate", "nonempty_compliant_query_rate")
    macro = {key: round(statistics.mean(metrics[key] for metrics in active if metrics[key] is not None), 4) if any(metrics[key] is not None for metrics in active) else None for key in metric_keys} if active else {}
    used_fallback = mode == "hybrid" and not semantic_ran
    return {
        "status": "measured" if not used_fallback else "measured with TF-IDF fallback; semantic component unavailable",
        "semantic_ran": semantic_ran,
        "retrieval_used": "TF-IDF fallback" if used_fallback else mode,
        "index_preparation_ms": round(preparation_ms, 2),
        "mean_query_latency_ms_after_indexing": round(statistics.mean(latencies), 3) if latencies else None,
        "by_domain": domain_metrics,
        "macro_average_of_book_and_movie_metrics": macro,
    }, details


def evaluate_preferences(examples: list[dict]) -> dict:
    rows = []
    fields = sorted({field for example in examples for field in example["expected"]})
    for example in examples:
        state = Preferences()
        media = "both"
        detected_media = None
        for message in example["messages"]:
            parsed = parse_preferences(message)
            detected_media = parsed.media_selection
            if parsed.media_selection:
                media = parsed.media_selection
            state = merge_preferences(state, parsed.preferences, message, parsed.explicit_fields)
        observed = {"media": media, **state.__dict__}
        for field in example["expected"]:
            expected = example["expected"][field]
            actual = observed.get(field)
            if field == "media" and len(example["messages"]) == 1 and expected is None:
                actual = detected_media
            if isinstance(expected, list):
                expected, actual = sorted(expected), sorted(actual or [])
            rows.append((field, expected == actual))
    per_field = {}
    for field in fields:
        checks = [passed for name, passed in rows if name == field]
        per_field[field] = {"support": len(checks), "exact_match": round(sum(checks) / len(checks), 4)}
    return {
        "labeled_conversations": len(examples),
        "labeled_messages": sum(len(example["messages"]) for example in examples),
        "relevance_judgments": "developer-authored expected fields; not independent annotation",
        "field_exact_match": per_field,
        "overall_labeled_field_exact_match": round(sum(passed for _, passed in rows) / len(rows), 4) if rows else None,
    }


def main() -> None:
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    preference_examples = json.loads(PREFERENCE_FILE.read_text(encoding="utf-8"))
    catalogs = load_active_catalogs()

    results = {
        "metric_definitions":{"hard_constraint_compliance":"fraction of returned records satisfying all explicit constraints; null when no records returned", "answer_rate":"fraction of query-domain cases with any result", "precision_when_returned":"mean judged hits / returned count over answered cases only", "precision_at_5":"judged hits / 5, including intentionally unfilled slots", "nonempty_compliant_query_rate":"legacy metric: fraction of query-domain cases both answered and fully compliant"},
        "active_catalog": {domain: {"records": len(items), "source_counts": {source: sum(item.source == source for item in items) for source in sorted({item.source for item in items})}} for domain, items in catalogs.items()},
        "retrieval_benchmark": {"query_count": len(queries), "judgment_method": "Developer-authored relevance IDs grounded in catalog metadata; no independent human evaluation.", "mixed_media_aggregation": "Book and movie metrics are calculated independently for each mixed query, then domain-level means are macro-averaged.", "models": {}},
        "preference_extraction": evaluate_preferences(preference_examples),
    }
    query_details = []
    for mode in ("tfidf", "semantic", "hybrid"):
        metrics, details = evaluate_mode(mode, catalogs, queries)
        results["retrieval_benchmark"]["models"][mode] = metrics
        query_details.extend(details)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "evaluation_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    if query_details:
        with (OUTPUT_DIR / "evaluation_query_results.csv").open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=query_details[0].keys(),lineterminator='\n')
            writer.writeheader(); writer.writerows(query_details)
    catalog_summary = ", ".join(f"{domain}: {values['records']:,}" for domain, values in results["active_catalog"].items())
    lines = ["# StoryScout evaluation summary", "", f"Active catalog: {catalog_summary}.", f"Retrieval benchmark: {len(queries)} developer-authored queries. Relevance labels are metadata-based and not independently human-rated.", "", "Mixed-media queries are scored separately for each active domain; book and movie averages are then macro-averaged.", "", "## Retrieval", ""]
    for mode, metrics in results["retrieval_benchmark"]["models"].items():
        lines += [f"### {mode}", f"Status: {metrics['status']}", ""]
        if metrics.get("by_domain"):
            for domain, values in metrics["by_domain"].items():
                lines.append(f"- {domain}: P@5 {values['precision_at_5']}, Recall@5 {values['recall_at_5']}, MRR@5 {values['mrr_at_5']}, hard-filter compliance {values['hard_constraint_compliance']} ({values['queries']} domain queries)")
            macro = metrics["macro_average_of_book_and_movie_metrics"]
            lines.append(f"- Domain macro average: P@5 {macro['precision_at_5']}, Recall@5 {macro['recall_at_5']}, MRR@5 {macro['mrr_at_5']}, hard-filter compliance {macro['hard_constraint_compliance']}")
            lines.append(f"- Mean search latency after indexing: {metrics['mean_query_latency_ms_after_indexing']} ms; index setup: {metrics['index_preparation_ms']} ms")
        lines.append("")
    lines += ["## Preference extraction", "", f"{results['preference_extraction']['labeled_conversations']} developer-authored labeled conversations; overall field exact match {results['preference_extraction']['overall_labeled_field_exact_match']}.", "", "| Field | Exact match | Support |", "|---|---:|---:|"]
    for field, values in results["preference_extraction"]["field_exact_match"].items():
        lines.append(f"| {field} | {values['exact_match']} | {values['support']} |")
    lines += ["", "Limitations: labels are developer-authored and incomplete; valid results outside the judged IDs can be undercounted. Semantic metrics are omitted unless the model actually ran.", ""]
    (OUTPUT_DIR / "evaluation_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
