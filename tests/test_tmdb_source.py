from types import SimpleNamespace

import httpx
import pytest

from src.schemas import ConversationState
from src.tmdb import TMDBMovieSource


def sample_payload():
    return {"results": [{"id": 27205, "title": "Inception", "original_title": "Inception",
                         "overview": "A skilled thief enters dreams to plant an idea.",
                         "release_date": "2010-07-15", "original_language": "en",
                         "genre_ids": [28, 878, 53]}]}


def test_tmdb_maps_sourced_fields_and_unknown_runtime(monkeypatch):
    def fake_get(url, **kwargs):
        assert url.endswith("/search/movie")
        assert kwargs["params"]["query"] == "Inception"
        return SimpleNamespace(raise_for_status=lambda: None, json=sample_payload)

    monkeypatch.setattr("src.tmdb.httpx.get", fake_get)
    item = TMDBMovieSource("test-key").search("Inception")[0]
    assert item.title == "Inception" and item.id == "movie_tmdb_27205"
    assert item.year == 2010 and item.runtime_minutes is None
    assert item.genres == ["Action", "Science Fiction", "Thriller"]
    assert item.description_provenance == "TMDB movie overview"
    assert item.source_url.endswith("/movie/27205")


def test_tmdb_disambiguates_exact_and_returns_typo_suggestions(monkeypatch):
    monkeypatch.setattr("src.tmdb.httpx.get", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=sample_payload))
    source = TMDBMovieSource("test-key")
    found, approximate = source.identity_matches("Inception", source.search("Inception"))
    assert found[0].title == "Inception" and not approximate
    suggestions, approximate = source.identity_matches("Incepton", source.search("Inception"))
    assert suggestions and approximate


def test_unconfigured_and_failed_tmdb_stay_local(monkeypatch, engine):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    source = TMDBMovieSource("")
    assert source.search("Inception") == []
    engine.movie_source = source
    reply, results = engine.handle("Find a movie called Missing Famous Title", ConversationState())
    assert not results and not engine.last_title_matches
    assert "not in the local title directory" in reply


def test_external_exact_movie_lookup_is_never_mislabeled_as_recommendation(monkeypatch, engine):
    monkeypatch.setattr("src.tmdb.httpx.get", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=sample_payload))
    engine.movie_source = TMDBMovieSource("test-key")
    state = ConversationState()
    reply, results = engine.handle("Find a movie called Inception", state)
    assert not results
    assert "Found the title" in reply
    item, explanation = engine.last_title_matches[0]
    assert item.id == "movie_tmdb_27205" and "TMDB" in explanation
    assert engine.get_item(item.id).runtime_minutes is None


def test_cross_media_reference_can_use_tmdb_title(monkeypatch, engine):
    monkeypatch.setattr("src.tmdb.httpx.get", lambda *a, **k: SimpleNamespace(raise_for_status=lambda: None, json=sample_payload))
    engine.movie_source = TMDBMovieSource("test-key")
    reply, _ = engine.handle("Recommend books similar to Inception", ConversationState())
    assert "could not identify" not in reply
    assert engine.get_item("movie_tmdb_27205") is not None


def test_tmdb_network_failure_does_not_leak_key_or_break_search(monkeypatch, engine, caplog):
    def fail(*args, **kwargs):
        raise httpx.ConnectError("simulated network failure")

    monkeypatch.setattr("src.tmdb.httpx.get", fail)
    engine.movie_source = TMDBMovieSource("secret-test-value")
    reply, results = engine.handle("Find a movie called Missing Famous Title", ConversationState())
    assert not results and "not in the local title directory" in reply
    assert "secret-test-value" not in caplog.text
