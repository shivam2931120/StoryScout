from src.preferences import parse_preferences
from src.schemas import Preferences

def test_hard_filter_compliance(engine):
    pref = parse_preferences("movies under 100 minutes").preferences
    results = engine.indexes["movie"].search("uplifting movie", pref, 20)
    assert all(r.item.runtime_minutes is not None and r.item.runtime_minutes <= 100 for r in results)

def test_missing_metadata_cannot_pass(catalogs):
    from src.schemas import CatalogItem
    from src.retrieval import RetrievalIndex
    item = CatalogItem("book_x", "book", "Unknown Pages", "a mystery", ["mystery"])
    idx = RetrievalIndex([item], "tfidf")
    assert idx.search("mystery", Preferences(max_pages=300), 5) == []

def test_cross_media_and_reference_exclusion(engine):
    state = __import__('src.schemas', fromlist=['ConversationState']).ConversationState()
    reply, results = engine.handle("I enjoyed Interstellar. Recommend a book with similar themes.", state)
    assert results.get("book")
    assert all(r.item.id != "movie_001" for r in results.get("book", []))
    assert "adaptation" in results["book"][0].explanation

def test_empty_results_are_explicit(engine):
    state = __import__('src.schemas', fromlist=['ConversationState']).ConversationState()
    reply, results = engine.handle("books under 1 pages", state)
    assert not results and "No verified matches" in reply

def test_ambiguous_title_lookup(catalogs):
    from src.title_matching import resolve_title
    item, choices = resolve_title("The Martian", catalogs["book"] + catalogs["movie"])
    assert item is None and len(choices) >= 2

def test_typo_search_resolves_to_catalog_alias(engine):
    state = __import__('src.schemas', fromlist=['ConversationState']).ConversationState()
    _, results = engine.handle("narnnia", state)
    assert {r.item.title for r in results["book"]} >= {"The Lion, the Witch and the Wardrobe"}
