from dataclasses import asdict
import gzip
import csv
import numpy as np
from fastapi.testclient import TestClient
from api.main import create_app
from src.schemas import CatalogItem, Preferences, ConversationState
from src.retrieval import RetrievalIndex
from src.query_understanding import build_search_query
from src.title_matching import correct_catalog_query
from src.data_loader import apply_nlp_sources
from scripts.enrich_book_summaries import summary_record
from scripts.prepare_nlp_catalog import title_key


def test_mood_cannot_rescue_a_nonmatching_topic(tmp_path):
    items = [
        CatalogItem('movie_space', 'movie', 'Rescue Mission', 'Astronauts repair oxygen equipment on a stranded spacecraft near Mars.', genres=['science fiction']),
        CatalogItem('movie_feud', 'movie', 'Cruel Feud', 'A dark disturbing tragedy of jealousy, murder and obsessive revenge.', genres=['science fiction']),
        CatalogItem('movie_home', 'movie', 'Home Again', 'A gentle community welcomes a new family.', genres=['science fiction']),
    ]
    index = RetrievalIndex(items, 'tfidf', artifact_dir=tmp_path)
    index.mood_alignment['dark'] = np.array([0.,1.,0.])
    result = index.search('spacecraft oxygen repair dark disturbing tragic', Preferences(desired_mood='dark'), topic_query='spacecraft oxygen repair')
    assert [x.item.id for x in result] == ['movie_space']
    assert index.last_diagnostics['quality_rejections'] == 2


def test_unrelated_request_returns_nothing_despite_active_genre_and_mood(engine):
    state = ConversationState(media_selection='movies')
    state.preferences = Preferences(preferred_genres=['romance'], desired_mood='dark')
    reply, result = engine.handle('Volcanic octopus diplomacy', state)
    assert not any(result.values())
    assert 'none match the topic strongly enough' in reply
    assert state.preferences.preferred_genres == ['romance']


def test_no_filter_match_is_distinguished_from_low_relevance(engine):
    reply, _ = engine.handle('Space movies under 1 minutes', ConversationState())
    assert 'No verified matches satisfy' in reply


def test_explicit_new_search_clears_filters_but_retains_chat_history(engine):
    with TestClient(create_app(engine)) as client:
        first = client.post('/api/chat', json={'message':'Crime movies about a prison escape under 100 minutes'}).json()
        first['state']['preferences']['language'] = 'french'
        second = client.post('/api/chat', json={'message':'Fantasy movies about magic', 'state':first['state'], 'search_action':'new'}).json()
        assert second['state']['preferences']['language'] is None
        assert second['state']['preferences']['max_runtime'] is None
        assert second['state']['preferences']['preferred_genres'] == ['fantasy']
        assert 'prison' not in second['state']['last_content_query']
        assert len(second['state']['messages']) == 2
        assert second['trace']['context_action'] == 'new'
        assert second['trace']['retained_preferences'] == []
        assert second['results']['movie']


def test_natural_new_search_command_resets_context(engine):
    state = ConversationState(media_selection='movies', last_content_query='prison escape')
    state.preferences.max_runtime = 70
    engine.handle('New search: fantasy movies about magic', state)
    assert state.preferences.max_runtime is None
    assert 'prison' not in state.last_content_query


def test_explicit_followup_adds_meaningful_topic_details():
    _, topic = build_search_query('Also set in Japan', Preferences(), 'a prison escape', True)
    assert 'prison escape' in topic and 'japan' in topic


def test_form_clear_topic_does_not_reparse_stale_message(engine):
    with TestClient(create_app(engine)) as client:
        state = asdict(ConversationState(media_selection='movies'))
        state['preferences']['preferred_genres'] = ['comedy']
        body = client.post('/api/recommend', json={'message':'space exploration', 'state':state}).json()
        assert not body['state']['last_content_query']
        assert 'space' not in body['trace']['retrieval']['movie']['query_text']


def test_pronoun_similarity_uses_last_exact_title(engine):
    state = ConversationState(media_selection='movies')
    engine.handle('Interstellar', state)
    _, result = engine.handle('Recommend books like it', state)
    assert state.selected_reference_id == 'movie_001'
    assert result['book']


def test_unknown_words_are_not_rewritten_as_title_words(catalogs):
    text = 'volcanic diplomacy with strange microorganisms'
    assert correct_catalog_query(text, catalogs['book']+catalogs['movie']) == text


def test_source_summary_requires_identity_and_does_not_fill_factual_fields(tmp_path):
    expected = {'book_pg_99':'A Sample Book'}
    row = {'id':99,'title':'A Sample Book','copyright':False,'languages':['en'],
           'summaries':['A traveler explores a distant island and meets a family of artists. Their friendships change the journey. (This is an automatically generated summary.)']}
    record = summary_record(row, expected)
    assert record and 'Source-generated' in record['provenance']
    assert 'automatically generated' not in record['summary_text']
    assert summary_record({**row,'title':'Another Book'},expected) is None
    assert summary_record({**row,'copyright':True},expected) is None
    with gzip.open(tmp_path/'book_summaries.csv.gz','wt',newline='') as stream:
        writer=csv.DictWriter(stream,list(record));writer.writeheader();writer.writerow(record)
    item = CatalogItem('book_pg_99','book','A Sample Book','Metadata only',source='project-gutenberg-catalog')
    apply_nlp_sources({'book':[item],'movie':[]},tmp_path)
    assert item.retrieval_text and item.description_provenance.startswith('Source-generated')
    assert item.page_count is None and item.year is None and item.language == 'Unknown'
    assert item.genres == []


def test_movie_source_join_handles_ampersands_and_articles():
    assert title_key('Love & Other Drugs') == title_key('Love and Other Drugs')
    assert title_key('Dark Knight, The') == title_key('The Dark Knight')


def test_filter_descriptors_are_not_mistaken_for_narrative_topics():
    for text in ['classic romance book','science fiction book published after 2000','English family fantasy book','fantasy adventure across books and films','mystery book but no horror']:
        from src.preferences import parse_preferences
        _, topic = build_search_query(text, parse_preferences(text).preferences)
        assert not topic, (text, topic)


def test_compliance_reports_returned_records_and_answer_coverage_separately():
    from scripts.evaluate import aggregate_rows
    common = dict(precision_at_5=0, recall_at_5=0, mrr_at_5=0, hits=0, constraint_violations=0, nonempty_compliant_query_rate=0)
    metrics=aggregate_rows([{**common,'returned_count':0},{**common,'returned_count':1,'nonempty_compliant_query_rate':1}])
    assert metrics['hard_constraint_compliance'] == 1.
    assert metrics['answer_rate'] == .5
    assert metrics['nonempty_compliant_query_rate'] == .5


def test_adjectival_language_is_extracted_without_reference_language_leaking():
    from src.preferences import parse_preferences
    assert parse_preferences('English science fiction books').preferences.language == 'english'
    assert parse_preferences('I loved The English Patient. Recommend French movies').preferences.language == 'french'


def test_query_embeddings_are_singleton_and_reused_across_domains(tmp_path, monkeypatch):
    import src.retrieval as retrieval
    class Encoder:
        def __init__(self): self.query_calls=[]; self.serving=False
        def encode(self,texts,**kwargs):
            if self.serving:
                assert len(texts)==1
                self.query_calls.extend(texts)
            return np.array([[1.,len(text)%19+1,sum(map(ord,text))%31+1] for text in texts],dtype=np.float32)
    model=Encoder()
    monkeypatch.setattr(retrieval,'_sentence_model',lambda:model)
    books=RetrievalIndex([CatalogItem('book_space','book','Space Voyage','Astronauts repair spacecraft oxygen equipment.')],'hybrid',artifact_dir=tmp_path/'book')
    movies=RetrievalIndex([CatalogItem('movie_space','movie','Space Mission','Astronauts repair spacecraft oxygen equipment.')],'hybrid',artifact_dir=tmp_path/'movie')
    model.serving=True
    for index in [books,movies]:
        assert index.search('spacecraft oxygen',Preferences(),topic_query='spacecraft oxygen')
    assert model.query_calls==['spacecraft oxygen']
