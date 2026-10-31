from types import SimpleNamespace

import httpx

from src.bigbook import BigBookSource
from src.schemas import CatalogItem, ConversationState, Preferences


def response(payload):
    return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)


def test_bigbook_uses_header_and_maps_source_fields(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/search-books"):
            return response({"books": [[{"id": 41, "title": "A Known Novel"}]]})
        return response({
            "id": 41, "title": "A Known Novel", "authors": [{"name": "A. Writer"}],
            "publish_date": 2001, "number_of_pages": 240,
            "description": "A short sourced description.", "genres": [{"name": "Mystery"}],
            "identifiers": {"open_library_id": "OL41W"},
        })

    monkeypatch.setattr("src.bigbook.httpx.get", fake_get)
    source = BigBookSource("test-secret")
    items = source.search("A Known Novel", details_limit=5)
    assert len(items) == 1
    item = items[0]
    assert item.id == "book_bigbook_41" and item.media_type == "book"
    assert item.authors == "A. Writer" and item.page_count == 240 and item.year == 2001
    assert item.genres == ["mystery"] and item.source == "bigbook-api"
    assert item.source_url == "https://api.bigbookapi.com/41"
    assert calls[0][1]["headers"]["x-api-key"] == "test-secret"
    assert "api-key" not in calls[0][1]["params"]
    assert calls[0][1]["params"]["number"] == 8


def test_bigbook_failure_and_missing_key_fail_closed(monkeypatch):
    monkeypatch.setattr("src.bigbook.httpx.get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("offline")))
    assert BigBookSource("test-secret").search("Percy Jackson") == []
    assert BigBookSource("").search("Percy Jackson") == []


def test_bigbook_title_lookup_respects_books_selection(engine):
    item = CatalogItem(
        id="book_bigbook_7", media_type="book", title="Percy Jackson and the Lightning Thief",
        description="A young demigod discovers a hidden world of Greek myths.",
        authors="Rick Riordan", page_count=377, source="bigbook-api", retrieval_text="A young demigod discovers Greek myths.",
    )

    class Source:
        configured = True

        def search(self, query, **kwargs):
            assert query == "Percy Jackson"
            return [item]

        def details(self, book_id):
            return item if book_id == "7" else None

    engine.book_source = Source()
    state = ConversationState(media_selection="books", has_explicit_media=True)
    reply, results = engine.handle("Percy Jackson", state)
    assert not results
    assert "several titles" in reply
    assert engine.last_title_matches[0][0].id == item.id
    assert engine.title_directory.get(item.id) is None  # Never added to persistent/local identity data.


def test_exact_remote_book_title_wins_over_series_partial_matches(engine):
    exact = CatalogItem(
        "book_bigbook_exact", "book", "Percy Jackson", "A demigod discovers Greek myths.",
        authors="Rick Riordan", source="bigbook-api", retrieval_text="Greek myths",
    )
    sequel = CatalogItem(
        "book_bigbook_sequel", "book", "Percy Jackson and the Sea of Monsters", "A quest at sea.",
        authors="Rick Riordan", source="bigbook-api", retrieval_text="A quest at sea",
    )

    class Source:
        configured = True

        def search(self, query, **kwargs):
            return [sequel, exact]

    engine.book_source = Source()
    engine.handle("Percy Jackson", ConversationState(media_selection="books"))
    assert [item.title for item, _ in engine.last_title_matches] == ["Percy Jackson"]
    assert engine.last_title_match_kind == "exact"


def test_external_book_hard_page_filter_does_not_accept_unknown(engine):
    candidates = [
        CatalogItem("book_bigbook_1", "book", "Known Length", "space travel", page_count=240, source="bigbook-api", retrieval_text="space travel novel"),
        CatalogItem("book_bigbook_2", "book", "Unknown Length", "space travel", page_count=None, source="bigbook-api", retrieval_text="space travel novel"),
        CatalogItem("book_bigbook_3", "book", "Too Long", "space travel", page_count=500, source="bigbook-api", retrieval_text="space travel novel"),
    ]
    recs = engine.indexes["book"].rank_external("space travel", candidates, Preferences(max_pages=300), topic_query="space travel")
    assert [rec.item.id for rec in recs] == ["book_bigbook_1"]
    assert engine.indexes["book"].last_external_diagnostics["eligible_count"] == 1
