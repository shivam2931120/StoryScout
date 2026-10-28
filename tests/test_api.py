from dataclasses import asdict
from fastapi.testclient import TestClient
import pytest
from api.main import create_app
from src.schemas import ConversationState


@pytest.fixture
def client(engine):
    with TestClient(create_app(engine)) as current:
        yield current


def test_metadata_reports_actual_local_pipeline(client):
    assert client.get('/api/health').json() == {'status': 'ready'}
    meta = client.get('/api/meta').json()
    assert meta['counts'] == {'book': 14, 'movie': 13}
    assert meta['optional_interpreter'] is False
    assert all('TF-IDF' in x for x in meta['modes'].values())
    assert len(meta['starters']) == 4
    assert 'NVIDIA_API_KEY' not in str(meta)


def test_conversation_roundtrip_inherits_separate_limits(client):
    first = client.post('/api/chat', json={'message': 'Books under 250 pages and movies under 100 minutes'}).json()
    assert first['state']['preferences']['max_pages'] == 250
    assert first['state']['preferences']['max_runtime'] == 100
    second = client.post('/api/chat', json={'message': 'Only show books now', 'state': first['state']}).json()
    assert second['state']['media_selection'] == 'books'
    assert second['state']['preferences']['max_runtime'] == 100
    assert set(second['results']) == {'book'}
    assert all(x['item']['page_count'] <= 250 for x in second['results']['book'])


def test_form_filters_are_authoritative_over_old_query(client):
    state = asdict(ConversationState())
    state['media_selection'] = 'movies'
    state['preferences']['max_runtime'] = 100
    result = client.post('/api/recommend', json={'message': 'Recommend a movie under 200 minutes', 'state': state}).json()
    assert result['state']['preferences']['max_runtime'] == 100
    assert all(x['item']['runtime_minutes'] <= 100 for x in result['results']['movie'])


def test_cross_media_selected_reference_and_followup(client):
    result = client.post('/api/chat', json={'message': 'Recommend similar books', 'reference_id': 'movie_001'}).json()
    assert result['state']['selected_reference_id'] == 'movie_001'
    assert result['results']['book']
    followup = client.post('/api/chat', json={'message': 'Also show movies with that feeling', 'state': result['state']}).json()
    assert followup['state']['selected_reference_id'] == 'movie_001'
    assert followup['results']['movie']
    assert all(x['item']['id'] != 'movie_001' for x in followup['results']['movie'])
    assert all('Interstellar' in x['explanation'] for x in followup['results']['movie'])


def test_reset_clears_context_and_does_not_affect_another_request(client):
    first = client.post('/api/chat', json={'message': 'No horror. Books under 250 pages'}).json()
    reset = client.post('/api/chat', json={'message': 'Reset my preferences', 'state': first['state']}).json()
    assert reset['state']['preferences']['max_pages'] is None
    assert reset['state']['preferences']['excluded_genres'] == []
    assert reset['state']['selected_reference_id'] is None
    independent = client.post('/api/chat', json={'message': 'Recommend movies'}).json()
    assert independent['state']['preferences']['max_pages'] is None


def test_contradiction_and_unknown_metadata_cannot_pass_filters(client):
    state = asdict(ConversationState())
    state['preferences']['preferred_genres'] = ['horror']
    state['preferences']['excluded_genres'] = ['horror']
    result = client.post('/api/recommend', json={'message': 'horror', 'state': state}).json()
    assert result['results'] == {}
    assert result['state']['preferences']['contradiction_messages']
    strict = client.post('/api/chat', json={'message': 'Movies under 1 minutes'}).json()
    assert not any(strict['results'].values())


def test_validation_and_missing_reference(client):
    assert client.post('/api/chat', json={'message': '   '}).status_code == 422
    assert client.post('/api/chat', json={'message': 'x' * 2001}).status_code == 422
    assert client.post('/api/chat', json={'message': 'hi', 'reference_id': 'not-real'}).status_code == 404
    assert client.post('/api/chat', json={'message': 'hi', 'state': {'preferences': {'max_pages': -1}}}).status_code == 422
    assert client.get('/api/items/not-real').status_code == 404
    assert client.get('/api/nonexistent').status_code == 404
    assert client.get('/api/items/book_001').json()['title'] == 'The Hobbit'


def test_ambiguous_reference_ids_are_exposed_for_choice(client, engine):
    from src.schemas import CatalogItem
    engine.catalogs['movie'].extend([
        CatalogItem('movie_amb1', 'movie', 'Shared title', 'space journey', year=1990),
        CatalogItem('movie_amb2', 'movie', 'Shared title', 'space journey', year=2000),
    ])
    result = client.post('/api/chat', json={'message': 'I liked Shared title. Recommend a book like it.'}).json()
    assert {x['id'] for x in result['choices']} == {'movie_amb1', 'movie_amb2'}


def test_unprepared_server_has_honest_health_status():
    client = TestClient(create_app())
    assert client.get('/api/health').json()['status'] == 'preparing'
    assert client.get('/api/meta').status_code == 503


def test_shorter_follows_active_medium_without_touching_other_limit(client):
    first = client.post('/api/chat', json={'message': 'Only show books now'}).json()
    shorter = client.post('/api/chat', json={'message': 'Make it shorter', 'state': first['state']}).json()
    assert shorter['state']['preferences']['max_pages'] == 300
    assert shorter['state']['preferences']['max_runtime'] is None
    movies = client.post('/api/chat', json={'message': 'Only show movies now', 'state': shorter['state']}).json()
    shorter_movies = client.post('/api/chat', json={'message': 'Make it shorter', 'state': movies['state']}).json()
    assert shorter_movies['state']['preferences']['max_pages'] == 300
    assert shorter_movies['state']['preferences']['max_runtime'] == 110


def test_human_evaluation_template_and_validated_upload(client):
    template = client.get('/api/evaluation/template').json()
    assert 'relevance_0_2' in template['csv']
    result = client.post('/api/evaluation/judge', json={'csv_text': 'mode,query,domain,rank,item_id,relevance_0_2\ntfidf,space,book,1,book_001,2\n'}).json()
    assert result['rating_count'] == 1
    assert result['rows'][0]['judged_precision'] == 1.0
    assert client.post('/api/evaluation/judge', json={'csv_text': 'mode,query,domain,rank,item_id,relevance_0_2\ntfidf,space,book,0,book_001,2\n'}).status_code == 422
    assert client.post('/api/evaluation/judge', json={'csv_text': 'wrong,data\n1,2\n'}).status_code == 422
