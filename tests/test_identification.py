from dataclasses import asdict
from fastapi.testclient import TestClient
import pytest
from src.schemas import CatalogItem, ConversationState, Preferences
from src.retrieval import RetrievalIndex
from src.conversation import StoryScoutEngine
from src.identification import local_clues, is_identification, identify
from api.main import create_app

@pytest.fixture
def identifier(tmp_path):
    items=[
        CatalogItem('movie_dream','movie','Dream Job','A thief enters sleeping people’s dreams to steal secrets. His team creates dreams inside other dreams.',genres=['science fiction'],year=2010,runtime_minutes=148),
        CatalogItem('movie_ocean','movie','Ocean Job','A thief steals jewels from a casino. His team escapes across the ocean.',genres=['crime'],year=1990,runtime_minutes=100),
        CatalogItem('movie_animation','movie','Dream Animation','An animated child travels through dreams to rescue a friend.',genres=['animation'],year=2020,runtime_minutes=85),
        CatalogItem('movie_metadata','movie','Dream Thief','No plot available.',source='movielens',genres=['science fiction']),
    ]
    books=[CatalogItem('book_dream','book','Dream Novel','A thief enters sleeping people’s dreams to steal secrets.',page_count=250)]
    catalogs={'movie':items,'book':books}
    return StoryScoutEngine(catalogs,{d:RetrievalIndex(rows,'tfidf',artifact_dir=tmp_path/d) for d,rows in catalogs.items()},'tfidf')


def test_plot_detection_and_uncertainty():
    assert is_identification('What movie is about a thief in dreams?')
    assert is_identification('I can’t remember the title of a book about dreams')
    assert not is_identification('Recommend an uplifting movie under two hours')
    assert any(c.uncertain for c in local_clues('A thief enters dreams. Maybe it was animated.'))


def test_local_identification_prioritizes_plot_over_title(identifier):
    state=ConversationState(media_selection='movies')
    reply,results,details=identify(identifier,'A thief enters sleeping people’s dreams to steal secrets',state)
    assert results['movie'][0].item.id=='movie_dream'
    assert all(r.item.id!='movie_metadata' for r in results['movie'])
    assert details['question'] and details['assessment']=='local passage overlap'
    assert 'Possible description match' in results['movie'][0].explanation
    assert 'probabilities' in details['limitation']


def test_hard_filters_and_no_wrong_medium(identifier):
    state=ConversationState(media_selection='books',preferences=Preferences(max_pages=300))
    _,results,_=identify(identifier,'A thief enters dreams',state)
    assert set(results)=={'book'} and results['book']
    assert all(r.item.media_type=='book' and r.item.page_count<=300 for r in results['book'])


def test_clarification_keeps_clues_and_reset_clears_them(identifier):
    with TestClient(create_app(identifier)) as client:
        first=client.post('/api/chat',json={'message':'Identify this movie: a thief enters dreams'}).json()
        assert first['trace']['intent']=='identify' and first['identification']['question']
        second=client.post('/api/chat',json={'message':'His team creates dreams inside other dreams','state':first['state']}).json()
        assert 'thief' in second['state']['identification_query']
        assert 'inside other dreams' in second['state']['identification_query']
        assert second['results']['movie'][0]['item']['id']=='movie_dream'
        reset=client.post('/api/chat',json={'message':'Reset','state':second['state']}).json()
        assert reset['state']['identification_query']==''
        assert reset['identification'] is None


def test_grounded_assessment_rejects_fabricated_quotes_and_ids(identifier):
    class Model:
        def identify_task(self,task,clues,candidates):
            if task=='extract': return {'clues':[{'text':'invented aliens','uncertain':False}]}
            return {'evidence':[{'id':'movie_dream','clue':0,'verdict':'supported','quote':'Invented alien invasion!'},
                                {'id':'movie_nonexistent','clue':0,'verdict':'supported','quote':'A made up passage'}]}
    identifier.query_interpreter=Model()
    _,results,details=identify(identifier,'A thief enters sleeping people’s dreams to steal secrets',ConversationState(media_selection='movies'))
    assert details['extraction']=='local clause rules'
    assert details['assessment']=='local passage overlap'
    assert results['movie'][0].item.id=='movie_dream'
    assert 'alien invasion' not in results['movie'][0].explanation


def test_valid_contradiction_penalizes_candidate(identifier):
    class Model:
        def identify_task(self,task,clues,candidates):
            if task=='extract': return None
            row=next((r for r in candidates if r['id']=='movie_ocean'),None)
            return {'evidence':[{'id':'movie_ocean','clue':0,'verdict':'contradicted','quote':'A thief steals jewels from a casino.'}]} if row else None
    identifier.query_interpreter=Model()
    _,results,_=identify(identifier,'A thief steals secrets through dreams instead of jewels in a casino',ConversationState(media_selection='movies'))
    assert results['movie'][0].item.id!='movie_ocean'
    ocean=next((r for r in results['movie'] if r.item.id=='movie_ocean'),None)
    if ocean: assert ocean.score_components['clue_contradictions']>0


def test_description_genres_do_not_become_preferences(identifier):
    state=ConversationState(media_selection='movies')
    identifier.handle('Identify this movie: a thief is scared of a horror film while dreaming',state)
    assert state.preferences.preferred_genres==[]
    assert state.preferences.desired_mood is None


def test_explicit_mode_and_empty_results(identifier):
    with TestClient(create_app(identifier)) as client:
        result=client.post('/api/chat',json={'message':'Underwater sentient broccoli teleports through cheese','search_action':'identify','state':asdict(ConversationState(media_selection='books',preferences=Preferences(max_pages=1)))}).json()
        assert result['identification']['status']=='insufficient_evidence'
        assert not result['results']['book']
        assert result['identification']['question']


def test_preference_edit_keeps_identification_instead_of_generic_recommendations(identifier):
    with TestClient(create_app(identifier)) as client:
        first=client.post('/api/chat',json={'message':'Identify this movie: a thief enters dreams'}).json()
        state=first['state'];state['media_selection']='books';state['preferences']['max_pages']=300
        edited=client.post('/api/recommend',json={'message':'Apply preferences','state':state}).json()
        assert edited['identification'] and edited['trace']['intent']=='identify'
        assert set(edited['results'])=={'book'}
        assert edited['state']['identification_query']==first['state']['identification_query']
        assert all(r['item']['page_count']<=300 for r in edited['results']['book'])


def test_answer_to_animation_question_actually_narrows_results(identifier):
    state=ConversationState(media_selection='movies')
    identifier.handle('Identify this movie: someone travels through dreams',state)
    _,results=identifier.handle('It was animated',state)
    assert results['movie'] and all('animation' in r.item.genres for r in results['movie'])
    state.preferences=Preferences()
    identifier.handle('Maybe it was live action',state)
    assert 'animation' not in state.preferences.excluded_genres


def test_compact_catalog_retains_source_plotted_reference_titles(tmp_path, monkeypatch):
    from scripts import prepare_compact_catalog as compact
    movies=[CatalogItem(f'movie_{i}','movie',f'Catalog record {i}','A source plot.',retrieval_text='A source plot.',source='source') for i in range(1501)]
    anchor=CatalogItem('movie_anchor','movie','Inception','A source plot about dreams.',retrieval_text='A source plot about dreams.',source='source')
    monkeypatch.setattr(compact,'ROOT',tmp_path)
    monkeypatch.setattr(compact,'load_active_catalogs',lambda:{'book':[], 'movie':movies+[anchor]})
    compact.prepare()
    import gzip,json
    with gzip.open(tmp_path/'data/compact/catalogs.json.gz','rt') as stream: saved=json.load(stream)
    assert len(saved['movie'])==1500
    retained=next(x for x in saved['movie'] if x['id']==anchor.id)
    assert retained['runtime_minutes'] is None
    assert set(x['id'] for x in saved['movie']) <= set(x.id for x in movies+[anchor])
