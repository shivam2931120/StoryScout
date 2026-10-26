import pandas as pd
import pytest

from src.human_evaluation import create_judgment_template, score_human_judgments


def test_template_splits_ranked_candidates_and_preserves_titles():
    results = pd.DataFrame([{"mode": "tfidf", "query": "space", "domain": "book", "returned_ids": "book_1|book_2"}])
    template = create_judgment_template(results, {"book_1": "Novel"})
    assert list(template["rank"]) == [1, 2]
    assert list(template["item_title"]) == ["Novel", "book_2"]
    assert list(template["relevance_0_2"]) == ["", ""]


def test_human_scores_ignore_unrated_candidates_and_average_annotators():
    frame = pd.DataFrame([
        {"mode":"tfidf","query":"q","domain":"book","rank":1,"item_id":"a","relevance_0_2":2},
        {"mode":"tfidf","query":"q","domain":"book","rank":1,"item_id":"a","relevance_0_2":0},
        {"mode":"tfidf","query":"q","domain":"book","rank":2,"item_id":"b","relevance_0_2":""},
    ])
    scores, count = score_human_judgments(frame)
    assert count == 2
    assert scores.iloc[0]["judged_items"] == 1
    assert scores.iloc[0]["judged_precision"] == 1.0
    assert scores.iloc[0]["judged_mrr"] == 1.0


def test_human_scores_reject_out_of_range_labels():
    frame = pd.DataFrame([{"mode":"tfidf","query":"q","domain":"movie","rank":1,"item_id":"m","relevance_0_2":3}])
    with pytest.raises(ValueError, match="0, 1, 2"):
        score_human_judgments(frame)
