from src.retrieval import RetrievalIndex
from src.schemas import CatalogItem, Preferences

def test_tfidf_fallback_is_available(catalogs):
    idx = RetrievalIndex(catalogs["book"], mode="tfidf")
    assert idx.active_mode == "TF-IDF lexical"
    assert idx.search("space survival", Preferences(), 3)


def test_failed_semantic_model_activates_real_lexical_fallback(catalogs,tmp_path,monkeypatch):
    import src.retrieval as retrieval
    def unavailable(): raise OSError('No local model and network unavailable')
    monkeypatch.setattr(retrieval,'_sentence_model',unavailable)
    index=RetrievalIndex(catalogs['book'],'hybrid',artifact_dir=tmp_path)
    assert not index.semantic_available
    assert index.active_mode=='TF-IDF fallback (semantic unavailable)'
    assert index.search('space survival',Preferences(),3)

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


def test_semantic_cache_reuses_unchanged_text_after_catalog_edit(tmp_path, monkeypatch):
    import numpy as np
    import src.retrieval as retrieval
    class LocalEncoder:
        def __init__(self): self.calls=[]
        def encode(self,texts,**kwargs):
            self.calls.extend(texts)
            return np.array([[1.,len(text)%19+1,sum(map(ord,text))%31+1] for text in texts],dtype=np.float32)
    encoder=LocalEncoder()
    monkeypatch.setattr(retrieval,'_sentence_model',lambda:encoder)
    a=CatalogItem('movie_a','movie','First','A careful investigation of an art theft.')
    b=CatalogItem('movie_b','movie','Second','Friends travel through space.')
    first=RetrievalIndex([a,b],'hybrid',artifact_dir=tmp_path)
    assert first.semantic_available
    unchanged=first.embeddings[0].copy()
    encoder.calls.clear()
    changed=CatalogItem('movie_b','movie','Second','A submarine crew explores an ocean trench.')
    second=RetrievalIndex([a,changed],'hybrid',artifact_dir=tmp_path)
    assert second.semantic_available
    np.testing.assert_allclose(second.embeddings[0],unchanged)
    assert any('ocean trench' in text for text in encoder.calls)
    assert not any('art theft' in text for text in encoder.calls)
