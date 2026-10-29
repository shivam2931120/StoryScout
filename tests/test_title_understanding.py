"""Real request forms and adversarial identity checks, separate from relevance."""
import pytest
from src.schemas import CatalogItem, ConversationState
from src.title_matching import TitleDirectory


@pytest.fixture
def enhanced(engine):
    engine.title_directory=TitleDirectory([
        dict(id='movie_inception',media_type='movie',title='Inception',description='',year=2010),
        dict(id='movie_hp1',media_type='movie',title="Harry Potter and the Sorcerer's Stone (a.k.a. Harry Potter and the Philosopher's Stone)",description='',year=2001),
        dict(id='movie_hp2',media_type='movie',title='Harry Potter and the Chamber of Secrets',description='',year=2002),
        dict(id='book_1984',media_type='book',title='Nineteen Eighty-Four',title_aliases=['1984'],description='',authors='George Orwell'),
        dict(id='movie_like',media_type='movie',title='Some Like It Hot',description='',year=1959),
        dict(id='book_thief',media_type='book',title='The Book Thief',description=''),
        dict(id='movie_eli',media_type='movie',title='The Book of Eli',description='',year=2010),
    ])
    return engine


@pytest.mark.parametrize('query',[
    'I want to watch Inception','Find Inception','Show me Inception','Tell me about Inception',
    'Can you show me Inception?','Please find the movie Inception','movie Inception',
    'I would like to watch Inception','Recommend Inception','What is Inception?',
    'Find me the movie called Inception','Inception movies','Give me Inception',
    'I am looking for Inception','Do you have Inception?','Show me details of Inception',
    'Tell me about a movie Inception','Find a title called Inception',
])
def test_conversational_title_identity(enhanced,query):
    _,results=enhanced.handle(query,ConversationState())
    assert not results
    assert [x.id for x,_ in enhanced.last_title_matches]==['movie_inception']
    assert enhanced.last_title_match_kind=='exact'


@pytest.mark.parametrize('query',['intersteler','Interstelar','Incepton'])
def test_common_typos_offer_suggestions_not_claimed_identity(enhanced,query):
    state=ConversationState();reply,results=enhanced.handle(query,state)
    assert not results and enhanced.last_title_matches
    assert 'Did you mean' in reply
    assert state.selected_reference_id is None
    assert enhanced.last_title_match_kind=='suggestion'


@pytest.mark.parametrize('query',['Harry Potter','Harry Potter movies','Find Harry Potter'])
def test_franchise_is_a_candidate_list(enhanced,query):
    state=ConversationState();_,results=enhanced.handle(query,state)
    assert not results
    assert {x.id for x,_ in enhanced.last_title_matches}=={'movie_hp1','movie_hp2'}
    assert enhanced.last_title_match_kind=='partial'
    assert state.selected_reference_id is None


def test_alternate_title_is_exact_not_fuzzy(enhanced):
    enhanced.handle("Harry Potter and the Philosopher's Stone",ConversationState())
    assert enhanced.last_title_match_kind=='exact'
    assert enhanced.last_title_matches[0][0].id=='movie_hp1'


def test_numeric_book_alias_disambiguates_media(enhanced):
    enhanced.handle('I want to read 1984',ConversationState(media_selection='movies'))
    assert enhanced.last_title_matches[0][0].id=='book_1984'


def test_title_like_word_does_not_trigger_reference_parser(enhanced):
    enhanced.handle('Some Like It Hot',ConversationState())
    assert enhanced.last_title_matches[0][0].id=='movie_like'


@pytest.mark.parametrize('query',['Atomic Habits','atomic habits','Oppenheimer','Find a movie called Unlisted Example','I want to read Missing Book Name'])
def test_missing_entities_never_get_narrative_substitutes(enhanced,query):
    state=ConversationState(last_content_query='space');state.preferences.max_runtime=90
    reply,results=enhanced.handle(query,state)
    assert not results and not enhanced.last_title_matches
    assert 'not in the local title directory' in reply
    assert state.last_content_query=='space' and state.preferences.max_runtime==90


@pytest.mark.parametrize('query',['Movies about space exploration','Recommend uplifting movies under two hours','Find a mystery book under 300 pages','Frodo Baggins','narnnia'])
def test_description_and_character_requests_keep_nlp(enhanced,query):
    _,results=enhanced.handle(query,ConversationState())
    assert not enhanced.last_title_lookup
    assert any(results.values())


def test_explicit_wrong_medium_does_not_return_other_domain(enhanced):
    state=ConversationState();_,results=enhanced.handle('Find a book called Inception',state)
    assert not results and not enhanced.last_title_matches
    assert state.media_selection=='books'


def test_author_qualifier_filters_identity(enhanced):
    enhanced.handle('1984 by George Orwell',ConversationState())
    assert [x.id for x,_ in enhanced.last_title_matches]==['book_1984']
    enhanced.handle('1984 by Wrong Author',ConversationState())
    assert not enhanced.last_title_matches


def test_unknown_reference_cannot_silently_become_another_title(enhanced):
    reply,results=enhanced.handle('Recommend books similar to Missing Reference Zzx',ConversationState())
    assert not results and 'could not identify the reference title' in reply


def test_misspelled_reference_requires_confirmation(enhanced):
    state=ConversationState();reply,results=enhanced.handle('Recommend books similar to Incepton',state)
    assert not results and 'Did you mean' in reply
    assert state.pending_title_choices==['movie_inception']
    assert state.selected_reference_id is None


def test_named_missing_title_with_genre_word_is_not_a_topic(enhanced):
    reply,results=enhanced.handle('Find a movie called Unlisted Horror Adventure',ConversationState())
    assert not results and not enhanced.last_title_matches
    assert 'not in the local title directory' in reply


def test_source_excerpt_is_not_mislabeled_as_ai():
    from api.main import item_payload
    item=CatalogItem('book_source','book','Source book','A sourced excerpt.',source='openlibrary-catalog',description_provenance='Attributed source work-description excerpt')
    assert item_payload(item)['description_status']=='sourced_excerpt'
    item.description_provenance='Original short developer paraphrase of linked synopsis'
    assert item_payload(item)['description_status']=='sourced_paraphrase'


def test_explicit_title_filter_suffix_updates_limits_without_parsing_title_words(enhanced):
    state=ConversationState();reply,results=enhanced.handle('Find Inception under 100 minutes',state)
    assert not results and enhanced.last_title_matches[0][0].id=='movie_inception'
    assert state.preferences.max_runtime==100 and state.preferences.max_pages is None
    assert 'not a verified filtered recommendation' in enhanced.last_title_matches[0][1]


def test_tell_me_about_book_sets_requested_medium(enhanced):
    state=ConversationState(media_selection='movies')
    enhanced.handle('Tell me about the book 1984',state)
    assert state.media_selection=='books'
    assert enhanced.last_title_matches[0][0].id=='book_1984'


def test_supplemental_snapshot_retains_provenance_and_unknown_metadata():
    import json
    from pathlib import Path
    records=json.loads((Path(__file__).resolve().parents[1]/'data/enriched/supplemental_catalog.json').read_text())['records']
    assert len({r['id'] for r in records})==len(records)
    books=[r for r in records if r['media_type']=='book']
    assert len(books)==20
    assert all(r['year'] is None and r['page_count'] is None for r in books)
    assert all(r['source_url'].startswith('https://') and r['authors'] for r in books)
    assert all(len(r['description'].split())<=50 for r in books)
    modern=next(r for r in records if r['title']=='Oppenheimer')
    assert modern['year']==2023
    assert 'universalpicturesathome.com' in modern['metadata_provenance']['runtime_minutes']['url']


def test_unconfirmed_reference_drops_previous_selection(enhanced):
    state=ConversationState(selected_reference_id='movie_001')
    reply,results=enhanced.handle('Recommend books similar to Incepton',state)
    assert not results and 'Did you mean' in reply
    assert state.selected_reference_id is None


@pytest.mark.parametrize('query',['Find a book called The Book Thief','Tell me about The Book Thief','Show me The Book Thief'])
def test_literal_book_word_survives_wrappers(enhanced,query):
    _,results=enhanced.handle(query,ConversationState())
    assert not results
    assert [x.id for x,_ in enhanced.last_title_matches]==['book_thief']


def test_literal_book_word_does_not_select_wrong_medium(enhanced):
    enhanced.handle('The Book of Eli',ConversationState())
    assert [x.id for x,_ in enhanced.last_title_matches]==['movie_eli']
