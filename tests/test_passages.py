"""Synthetic narrative fixtures test retrieval behavior; not real catalog facts."""
from dataclasses import asdict
import numpy as np
import pytest
from fastapi.testclient import TestClient
from api.main import create_app
from src.conversation import StoryScoutEngine
from src.passages import narrative_text, passage_spans
from src.retrieval import RetrievalIndex
from src.schemas import CatalogItem, Preferences


def test_overlapping_windows_cover_body_with_exact_character_offsets():
    text='  '+' '.join(f'word{i}' for i in range(900))+'\n'
    spans,partial=passage_spans(text)
    covered=set()
    for start,end in spans:
        for word in text[start:end].split():covered.add(word)
    assert covered=={f'word{i}' for i in range(900)}
    assert not partial
    assert spans[1][0]<spans[0][1]
    assert text[spans[-1][0]:spans[-1][1]].endswith('word899')


def test_extreme_imports_disclose_partial_sampling():
    text=' '.join(f'word{i}' for i in range(6000))
    spans,partial=passage_spans(text)
    assert partial and len(spans)==32
    assert text[spans[0][0]:spans[0][1]].startswith('word0 ')
    assert text[spans[-1][0]:spans[-1][1]].endswith('word5999')


def test_unknown_metadata_is_not_a_narrative_passage():
    item=CatalogItem('movie_unknown','movie','Unknown','Plot is not supplied; genre: comedy.',source='movielens-latest-small')
    assert narrative_text(item)==''
    custom=CatalogItem('book_custom','book','Custom','A sailor finds a lost island.',source='user-csv')
    assert 'sailor' in narrative_text(custom)


@pytest.fixture
def passage_engine(tmp_path,monkeypatch):
    import src.retrieval as retrieval
    class Encoder:
        def __init__(self):self.calls=[]
        def encode(self,texts,**kwargs):
            self.calls.extend(texts)
            return np.array([[1.,0.] if 'dolphin acoustic code' in text or 'underwater signal translation' in text else [0.,1.] for text in texts],dtype=np.float32)
    encoder=Encoder();monkeypatch.setattr(retrieval,'_sentence_model',lambda:encoder)
    words=['village market family festival garden painting childhood memories']*90
    # This clue is between the old beginning/middle/end samples.
    body=' '.join(words[:25])+'. Researchers decode a dolphin acoustic code. '+' '.join(words[25:])
    item=CatalogItem('movie_hidden','movie','Harbor Chronicle','A synthetic long-plot evaluation fixture.',retrieval_text=body,genres=['adventure'],runtime_minutes=95,language='English',source='synthetic-demo',text_source='Developer-authored synthetic narrative')
    books=[CatalogItem('book_one','book','Everyday Life','A quiet day in a village.',source='synthetic-demo')]
    catalogs={'book':books,'movie':[item]}
    indexes={key:RetrievalIndex(items,'semantic',artifact_dir=tmp_path/key) for key,items in catalogs.items()}
    return StoryScoutEngine(catalogs,indexes,'semantic'),encoder,tmp_path


def test_specific_paraphrase_retrieved_from_hidden_middle_passage(passage_engine):
    engine,_,path=passage_engine
    item=engine.catalogs['movie'][0]
    baseline=RetrievalIndex([item],'semantic',artifact_dir=path/'baseline',passage_matching=False)
    assert baseline.search('underwater signal translation',Preferences())==[]
    results=engine.indexes['movie'].search('underwater signal translation',Preferences())
    assert len(results)==1 and results[0].item.id=='movie_hidden'
    evidence=results[0].passage_match
    assert evidence and evidence['passage_number']>1
    assert evidence['semantic_similarity']>.99


def test_passages_never_override_hard_filters_or_reference_exclusion(passage_engine):
    engine,_,_=passage_engine;index=engine.indexes['movie']
    for pref in [Preferences(max_runtime=90),Preferences(language='french'),Preferences(excluded_genres=['adventure'])]:
        assert index.search('underwater signal translation',pref)==[]
    assert index.search('underwater signal translation',Preferences(),exclude_ids={'movie_hidden'})==[]


def test_api_exposes_passage_provenance_without_plot_text(passage_engine):
    engine,_,_=passage_engine
    with TestClient(create_app(engine)) as client:
        data=client.post('/api/chat',json={'message':'Movies about underwater signal translation'}).json()
        rec=data['results']['movie'][0]
        assert rec['passage_match']['source']=='Developer-authored synthetic narrative'
        assert 'dolphin acoustic code' not in str(data)
        assert 'retrieval_text' not in rec['item']
        assert 'passage' in rec['explanation']


def test_passage_artifacts_reused_and_changed_text_invalidates(passage_engine):
    engine,encoder,path=passage_engine
    original=engine.catalogs['movie'][0]
    encoder.calls.clear()
    again=RetrievalIndex([original],'semantic',artifact_dir=path/'movie')
    # Preparation may encode mood/theme prototypes, but no narrative chunks.
    assert not any('village market' in text for text in encoder.calls)
    assert again.passages.semantic_available
    changed=CatalogItem(**{**asdict(original),'retrieval_text':original.retrieval_text+' A submarine visits a coral reef.'})
    encoder.calls.clear()
    RetrievalIndex([changed],'semantic',artifact_dir=path/'movie')
    assert any('coral reef' in text for text in encoder.calls)
    assert len(list((path/'movie').glob('passages_*.npy')))==2


def test_passage_lexical_fallback_still_retrieves_specific_detail(tmp_path,monkeypatch):
    import src.retrieval as retrieval
    monkeypatch.setattr(retrieval,'_sentence_model',lambda:(_ for _ in ()).throw(OSError('offline')))
    body=' '.join(['family village garden market festival history']*60)+'. Engineers repair a submarine oxygen valve.'
    item=CatalogItem('book_oxygen','book','Deep Repair','A synthetic fixture.',retrieval_text=body,source='synthetic-demo')
    index=RetrievalIndex([item],'hybrid',artifact_dir=tmp_path)
    result=index.search('submarine oxygen valve',Preferences())
    assert not index.semantic_available
    assert result and result[0].passage_match
    assert result[0].passage_match['semantic_similarity'] is None
    assert index.passages.mode=='TF-IDF passages'


def test_passage_semantic_failure_is_honest_lexical_fallback(tmp_path,monkeypatch):
    import src.retrieval as retrieval
    class Encoder:
        def encode(self,texts,**kwargs):
            if any(len(text.split())==112 for text in texts):raise RuntimeError('Synthetic passage encoder failure')
            return np.array([[1.,0.] for _ in texts],dtype=np.float32)
    monkeypatch.setattr(retrieval,'_sentence_model',lambda:Encoder())
    item=CatalogItem('book_failure','book','Test','A synthetic fixture.',retrieval_text=' '.join(['forest river village market memory']*80),source='synthetic-demo')
    index=RetrievalIndex([item],'hybrid',artifact_dir=tmp_path)
    assert index.semantic_available
    assert not index.passages.semantic_available
    assert index.passages.embedding_error=='RuntimeError'
    assert index.passages.mode=='TF-IDF passages'


def test_disabling_passages_skips_new_artifacts(tmp_path):
    item=CatalogItem('book_one','book','Test','A sailor explores an island.',source='synthetic-demo')
    index=RetrievalIndex([item],'tfidf',artifact_dir=tmp_path,passage_matching=False)
    assert index.passages is None
    assert not list(tmp_path.glob('passage*'))


def test_cross_media_aggregation_keeps_one_card_per_item(passage_engine):
    engine,_,path=passage_engine
    film=engine.catalogs['movie'][0]
    book=CatalogItem('book_hidden','book','An Island Chronicle','Synthetic test description.',retrieval_text=film.retrieval_text,source='synthetic-demo')
    engine.catalogs['book']=[book]
    engine.indexes['book']=RetrievalIndex([book],'semantic',artifact_dir=path/'cross_book')
    result=engine.recommend('underwater signal translation',__import__('src.schemas',fromlist=['ConversationState']).ConversationState(last_content_query='underwater signal translation'))
    assert len(result['book'])==1 and len(result['movie'])==1
    assert all(rec.passage_match for group in result.values() for rec in group)
