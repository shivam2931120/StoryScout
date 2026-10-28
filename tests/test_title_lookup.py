"""Title identity must not be confused with narrative relevance or preferences."""
from dataclasses import asdict
from fastapi.testclient import TestClient
import pytest
from api.main import create_app
from src.schemas import CatalogItem, ConversationState
from src.title_matching import TitleDirectory, title_key


@pytest.fixture
def directory_engine(engine):
    records = [
        dict(id='movie_outside', media_type='movie', title='Love and Other Drugs', description='', genres=['romance', 'drama'], year=2010, source='movielens'),
        dict(id='movie_dark', media_type='movie', title='The Dark Knight', description='', genres=['action'], year=2008, source='movielens'),
        dict(id='movie_no', media_type='movie', title='No Country for Old Men', description='', year=2007, source='movielens'),
        dict(id='movie_short', media_type='movie', title='The Big Short', description='', year=2015, source='movielens'),
        dict(id='movie_remake1', media_type='movie', title='A Shared Title', description='', year=1990),
        dict(id='movie_remake2', media_type='movie', title='A Shared Title', description='', year=2000),
        dict(id='book_same', media_type='book', title='A Shared Title', description='', year=1980),
    ]
    engine.title_directory = TitleDirectory(records)
    return engine


@pytest.mark.parametrize('text,expected', [
    ('love and other drugs', 'movie_outside'), ('LOVE & OTHER DRUGS', 'movie_outside'),
    ('Find the movie called Love & Other Drugs', 'movie_outside'),
    ('the dark knight', 'movie_dark'), ('no country for old men', 'movie_no'),
    ('The Big Short', 'movie_short'), ('The Dark Knight (2008)', 'movie_dark'),
])
def test_exact_title_bypasses_semantic_ranking_and_preserves_preferences(directory_engine, text, expected):
    state = ConversationState(media_selection='movies', last_content_query='erotica')
    state.preferences.desired_mood = 'dark'
    state.preferences.language = 'english'
    state.preferences.max_runtime = 90
    previous = asdict(state.preferences)
    reply, results = directory_engine.handle(text, state)
    assert results == {}
    assert [item.id for item, _ in directory_engine.last_title_matches] == [expected]
    assert asdict(state.preferences) == previous
    assert state.last_content_query == 'erotica'
    assert 'not a verified filtered recommendation' in directory_engine.last_title_matches[0][1]
    assert directory_engine.last_diagnostics == {}


def test_normalization():
    assert title_key('Amélie') == title_key('AMELIE')
    assert title_key('Hobbit, The') == title_key('The Hobbit')
    assert title_key('Love & Other Drugs') == title_key('Love and Other Drugs')


def test_ambiguous_matches_keep_media_and_year(directory_engine):
    state = ConversationState()
    directory_engine.handle('A Shared Title', state)
    assert len(directory_engine.last_title_matches) == 3
    directory_engine.handle('A Shared Title (1990)', state)
    assert [x.id for x, _ in directory_engine.last_title_matches] == ['movie_remake1']
    state.media_selection = 'movies'
    directory_engine.handle('A Shared Title', state)
    assert len(directory_engine.last_title_matches) == 2


def test_lookup_is_not_a_cross_client_or_reset_leak(directory_engine):
    with TestClient(create_app(directory_engine)) as client:
        first = client.post('/api/chat', json={'message': 'Love & Other Drugs'}).json()
        assert first['title_matches'][0]['item']['id'] == 'movie_outside'
        assert first['title_matches'][0]['item']['description'] is None
        assert first['trace']['intent'] == 'title_lookup'
        assert first['trace']['extracted_fields'] == []
        assert client.get('/api/items/movie_outside').status_code == 200
        second = client.post('/api/chat', json={'message': 'Recommend comforting movies'}).json()
        assert second['title_matches'] == []
        assert second['results']['movie']
        reset = client.post('/api/chat', json={'message': 'Reset', 'state': first['state']}).json()
        assert reset['title_matches'] == []
        assert reset['state']['last_content_query'] == ''


def test_explicit_unknown_title_has_no_random_substitute(directory_engine):
    reply, results = directory_engine.handle('Find a movie called Qzx Impossible Title', ConversationState())
    assert 'not in the local title directory' in reply
    assert results == {}


def test_reference_directory_and_filtered_recommendations(directory_engine):
    with TestClient(create_app(directory_engine)) as client:
        response = client.post('/api/chat', json={'message': 'Recommend similar movies under 100 minutes', 'reference_id': 'movie_outside'})
        assert response.status_code == 200
        body = response.json()
        assert body['state']['selected_reference_id'] == 'movie_outside'
        assert body['title_matches'] == []
        assert all(rec['item']['runtime_minutes'] <= 100 for rec in body['results']['movie'])
        assert all('no sourced synopsis' in rec['explanation'] for rec in body['results']['movie'])


def test_fuzzy_match_is_labeled_as_suggestion(directory_engine):
    directory_engine.handle('Love and Other Drugz', ConversationState())
    assert 'Possible title spelling' in directory_engine.last_title_matches[0][1]


def test_normal_recommend_request_not_mistaken_for_unknown_title(directory_engine):
    _, results = directory_engine.handle('Find a movie under 100 minutes', ConversationState())
    assert results['movie']
    assert directory_engine.last_title_lookup is False


def test_known_reference_similarity_still_excludes_reference(directory_engine):
    _, results = directory_engine.handle('I enjoyed Interstellar. Recommend movies with similar themes.', ConversationState())
    assert directory_engine.last_title_matches == []
    assert all(rec.item.id != 'movie_001' for rec in results['movie'])


def test_numeric_title_and_lookup_wrapper(directory_engine):
    directory_engine.title_directory = TitleDirectory([dict(id='book_numeric', media_type='book', title='1984', description='', year=1949)])
    directory_engine.handle('1984', ConversationState())
    assert directory_engine.last_title_matches[0][0].id == 'book_numeric'
    directory_engine.handle('Look up 1984', ConversationState())
    assert directory_engine.last_title_matches[0][0].id == 'book_numeric'


def test_source_alternate_titles_are_searchable(directory_engine):
    directory_engine.title_directory = TitleDirectory([dict(id='movie_alt', media_type='movie', title='1984 (Nineteen Eighty-Four)', description='', year=1984)])
    for query in ['1984', 'Nineteen Eighty-Four', '1984 (Nineteen Eighty-Four)']:
        directory_engine.handle(query, ConversationState())
        assert directory_engine.last_title_matches[0][0].id == 'movie_alt'


def test_title_wrapper_updates_explicit_format_without_parsing_title_words(directory_engine):
    state = ConversationState(media_selection='movies')
    directory_engine.handle('Find a book called The Hobbit', state)
    assert state.media_selection == 'books'
    assert state.has_explicit_media
    assert state.preferences.desired_mood is None


def test_reference_without_description_or_genres_cannot_claim_content_similarity(directory_engine):
    reply, results = directory_engine.handle('Recommend similar movies', ConversationState(), reference_id='movie_no')
    assert results == {}
    assert 'no synopsis or genre metadata' in reply
