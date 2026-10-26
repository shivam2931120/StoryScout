from src.explanations import explain
from src.schemas import CatalogItem, Preferences, Recommendation

def test_explanation_uses_known_fields_only():
    item = CatalogItem("book_1", "book", "A", "A short description", ["mystery"], year=2020, page_count=200)
    text = explain(Recommendation(item, .5), "mystery", Preferences(preferred_genres=["mystery"], max_pages=250))
    assert "mystery" in text and "200 pages" in text
    assert "award" not in text.lower() and "rating" not in text.lower()
