from src.retrieval import RetrievalIndex
from src.schemas import CatalogItem, Preferences

def test_tfidf_fallback_is_available(catalogs):
    idx = RetrievalIndex(catalogs["book"], mode="tfidf")
    assert idx.active_mode == "TF-IDF lexical"
    assert idx.search("space survival", Preferences(), 3)

def test_index_changes_with_data():
    a = [CatalogItem("book_1", "book", "A", "mystery story", ["mystery"])]
    b = a + [CatalogItem("book_2", "book", "B", "space story", ["science fiction"])]
    assert len(RetrievalIndex(a, "tfidf").items) != len(RetrievalIndex(b, "tfidf").items)


def test_persistent_tfidf_cache_is_invalidated_by_content(tmp_path):
    first = [CatalogItem("book_1", "book", "A", "mystery story", ["mystery"])]
    second = first + [CatalogItem("book_2", "book", "B", "space story", ["science fiction"])]
    RetrievalIndex(first, "tfidf", artifact_dir=tmp_path)
    RetrievalIndex(second, "tfidf", artifact_dir=tmp_path)
    assert len(list(tmp_path.glob("tfidf_*.pkl"))) == 2
