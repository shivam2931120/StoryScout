"""Human relevance judgment templates and transparent summaries."""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = {"mode", "query", "domain", "rank", "item_id", "relevance_0_2"}


def create_judgment_template(results: pd.DataFrame, titles: dict[str, str]) -> pd.DataFrame:
    rows = []
    for result in results.to_dict(orient="records"):
        for rank, item_id in enumerate(filter(None, str(result.get("returned_ids", "")).split("|")), start=1):
            rows.append({
                "mode": result["mode"], "query": result["query"], "domain": result["domain"],
                "rank": rank, "item_id": item_id, "item_title": titles.get(item_id, item_id),
                "relevance_0_2": "", "annotator": "", "notes": "",
            })
    return pd.DataFrame(rows, columns=["mode", "query", "domain", "rank", "item_id", "item_title", "relevance_0_2", "annotator", "notes"])


def score_human_judgments(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(sorted(missing)))
    judged = frame.copy()
    judged["relevance_0_2"] = pd.to_numeric(judged["relevance_0_2"].replace("", pd.NA), errors="coerce")
    ratings = judged["relevance_0_2"].dropna()
    if not ratings.isin([0, 1, 2]).all():
        raise ValueError("Relevance must be 0, 1, 2, or blank.")
    judged = judged.dropna(subset=["relevance_0_2"])
    if judged.empty:
        return pd.DataFrame(columns=["mode", "domain", "query", "judged_items", "judged_precision", "judged_mrr"]), 0
    judged["rank"] = pd.to_numeric(judged["rank"], errors="coerce")
    judged = judged.dropna(subset=["rank"])
    per_item = judged.groupby(["mode", "domain", "query", "rank", "item_id"], as_index=False)["relevance_0_2"].mean()
    rows = []
    for (mode, domain, query), candidates in per_item.groupby(["mode", "domain", "query"]):
        candidates = candidates.sort_values("rank")
        relevant = candidates["relevance_0_2"] >= 1
        relevant_ranks = candidates.loc[relevant, "rank"]
        rows.append({
            "mode": mode, "domain": domain, "query": query,
            "judged_items": len(candidates), "judged_precision": float(relevant.mean()),
            "judged_mrr": float(1 / relevant_ranks.iloc[0]) if not relevant_ranks.empty else 0.0,
        })
    return pd.DataFrame(rows), len(judged)
