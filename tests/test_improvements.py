from src.preferences import merge_preferences, parse_preferences
from src.retrieval import RetrievalIndex, combine_hybrid_scores
from src.schemas import CatalogItem, Preferences
from src.data_loader import catalog_identity
from src.title_matching import correct_catalog_query


def test_compound_negations_and_common_aliases_are_extracted():
    parsed = parse_preferences("Exclude comedy and horror from movies; not romantic")
    assert set(parsed.preferences.excluded_genres) == {"comedy", "horror", "romance"}


def test_worded_hours_becomes_movie_limit():
    parsed = parse_preferences("Recommend a movie under two hours")
    assert parsed.preferences.max_runtime == 120
    assert parsed.preferences.max_pages is None


def test_year_range_replaces_conversation_year_filters():
    parsed = parse_preferences("Books between 1990 and 2010")
    merged = merge_preferences(Preferences(min_year=1980, max_year=2020), parsed.preferences, "Books between 1990 and 2010", parsed.explicit_fields)
    assert (merged.min_year, merged.max_year) == (1990, 2010)


def test_filter_only_query_returns_verified_runtime_matches(engine):
    preferences = parse_preferences("movie under 100 minutes").preferences
    results = engine.indexes["movie"].search("under 100 minutes", preferences, top_k=5)
    assert results
    assert all(result.item.runtime_minutes is not None and result.item.runtime_minutes <= 100 for result in results)
    assert all(result.score == 0 for result in results)


def test_filter_only_explanation_discloses_missing_text_signal(catalogs):
    index = RetrievalIndex(catalogs["movie"], mode="tfidf")
    preferences = Preferences(max_runtime=100)
    result = index.search("under 100 minutes", preferences, top_k=1)[0]
    from src.explanations import explain
    explanation = explain(result, "under 100 minutes", preferences)
    assert "no matching text terms" in explanation


def test_metadata_only_notice_is_never_a_retrieval_signal():
    item = CatalogItem(id="movie_ml_1", media_type="movie", title="A title", description="Plot summary is not provided. Listed genres: comedy.", genres=["comedy"], source="movielens-latest-small")
    assert "plot summary" not in item.search_text
    assert "comedy" in item.search_text


def test_genre_exclusion_rejects_unknown_genres():
    item = CatalogItem(id="book_pg_1", media_type="book", title="A title", description="Metadata only", source="project-gutenberg-catalog")
    index = RetrievalIndex([item], mode="tfidf")
    assert index.search("a story", Preferences(excluded_genres=["horror"])) == []


def test_large_catalog_search_keeps_original_item_indexes():
    items = [CatalogItem(id=f"movie_{i}", media_type="movie", title=f"Title {i}", description="science fiction", genres=["science fiction"]) for i in range(150)]
    index = RetrievalIndex(items, mode="tfidf")
    assert index.search("science fiction", Preferences(), top_k=5)


def test_hybrid_score_maps_cosine_components_to_shared_unit_range():
    import numpy as np
    combined = combine_hybrid_scores(np.array([0.8, 0.8]), np.array([-1.0, 1.0]))
    assert np.allclose(combined, [0.36, 0.91])


def test_fuzzy_query_correction_uses_catalog_title_tokens(catalogs):
    corrected = correct_catalog_query("Narnnia fantasy adventure", catalogs["book"] + catalogs["movie"])
    assert "narnia" in corrected


def test_catalog_identity_keeps_movie_releases_and_distinct_authors():
    movie_1995 = CatalogItem("movie_a", "movie", "Same Title", "", year=1995)
    movie_2005 = CatalogItem("movie_b", "movie", "Same Title", "", year=2005)
    book_a = CatalogItem("book_a", "book", "Same Title", "", authors="Author A")
    book_b = CatalogItem("book_b", "book", "Same Title", "", authors="Author B")
    assert catalog_identity(movie_1995) != catalog_identity(movie_2005)
    assert catalog_identity(book_a) != catalog_identity(book_b)
