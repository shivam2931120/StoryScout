from dataclasses import asdict
from pathlib import Path
import csv
import gzip
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from src.conversation import StoryScoutEngine
from src.data_loader import apply_nlp_sources
from src.intents import detect_media
from src.preferences import parse_preferences, merge_preferences
from src.query_understanding import build_search_query, content_chunks
from src.retrieval import RetrievalIndex
from src.schemas import CatalogItem, ConversationState, Preferences
from scripts.enrich_wikipedia_metadata import extract_fields


@pytest.fixture
def variety_engine(tmp_path):
    films=[]
    for genre in ['comedy','crime','family']:
        for i in range(8):
            desc={'comedy':'Funny musicians on a joyful road trip with jokes and friendship.',
                  'crime':'A detective investigates a prison escape and a clever bank robbery.',
                  'family':'A kind child befriends a lost animal and finds a welcoming home.'}[genre]
            films.append(CatalogItem(f'movie_test_{genre}_{i}','movie',f'{genre} story {i}',desc+f' Episode {i}.',genres=[genre],runtime_minutes=80+i,language='English'))
    books=[CatalogItem('book_test_1','book','Prison memoir','A prison escape and justice.',genres=['crime'],page_count=200,language='English')]
    catalogs={'book':books,'movie':films}
    return StoryScoutEngine(catalogs,{k:RetrievalIndex(v,mode='tfidf',artifact_dir=tmp_path/k) for k,v in catalogs.items()},'tfidf')


def test_genre_form_changes_do_not_return_identical_titles(variety_engine):
    with TestClient(create_app(variety_engine)) as client:
        groups=[]
        for genre in ['comedy','crime','family']:
            state=asdict(ConversationState());state['media_selection']='movies'
            state['preferences'].update(preferred_genres=[genre],max_runtime=120)
            data=client.post('/api/recommend',json={'message':'Recommend an uplifting family movie under two hours','state':state,'per_domain':5}).json()
            rows=data['results']['movie']
            assert len(rows)==5
            assert all(genre in x['item']['genres'] for x in rows)
            groups.append({x['item']['id'] for x in rows})
        assert not groups[0]&groups[1] and not groups[1]&groups[2]


def test_followup_retains_meaningful_topic(variety_engine):
    state=ConversationState()
    variety_engine.handle('Find movies about a prison escape',state)
    assert 'prison escape' in state.last_content_query
    variety_engine.handle('Under 100 minutes',state)
    assert 'prison escape' in state.last_content_query
    assert 'prison escape' in variety_engine.last_diagnostics['movie']['query_text']


def test_different_picks_exclude_only_served_results_and_preserve_filters(variety_engine):
    with TestClient(create_app(variety_engine)) as client:
        first=client.post('/api/chat',json={'message':'Comedy movies under 90 minutes','per_domain':3}).json()
        second=client.post('/api/chat',json={'message':'Show different recommendations','state':first['state'],'per_domain':3}).json()
        a={x['item']['id'] for x in first['results']['movie']};b={x['item']['id'] for x in second['results']['movie']}
        assert a and b and not a&b
        assert len(first['state']['seen_recommendations'])==3
        assert all('comedy' in x['item']['genres'] and x['item']['runtime_minutes']<=90 for x in second['results']['movie'])
        assert second['state']['preferences']['max_runtime']==90


def test_more_returns_a_full_unseen_batch_and_echoes_active_filters(variety_engine):
    with TestClient(create_app(variety_engine)) as client:
        first=client.post('/api/chat',json={'message':'Comedy movies under 100 minutes','per_domain':5}).json()
        first_rows=first['results']['movie']
        assert len(first_rows)==5
        assert 'Movies' in first['reply'] and 'comedy' in first['reply'] and '100 minutes' in first['reply']
        second=client.post('/api/chat',json={'message':'Show different recommendations','state':first['state'],'per_domain':5}).json()
        second_rows=second['results']['movie']
        assert second_rows
        assert not ({x['item']['id'] for x in first_rows} & {x['item']['id'] for x in second_rows})
        assert all('comedy' in x['item']['genres'] and x['item']['runtime_minutes']<=100 for x in second_rows)
        assert second['state']['preferences']['max_runtime']==100


def test_reset_clears_retained_topic_and_seen_ids(variety_engine):
    state=ConversationState()
    variety_engine.handle('Comedy movies about friendship',state)
    assert state.seen_recommendations
    variety_engine.handle('Reset',state)
    assert not state.last_content_query and not state.seen_recommendations


def test_no_cross_client_query_diagnostics_leak(variety_engine):
    with TestClient(create_app(variety_engine)) as client:
        client.post('/api/chat',json={'message':'Crime movies about a prison escape'})
        other=client.post('/api/chat',json={'message':'Show active preferences'}).json()
        assert other['trace']['retrieval']=={}


@pytest.mark.parametrize('text,genre',[('sci-fi movies','science fiction'),('a rom-com','comedy'),('an action film','action'),('historical books','history')])
def test_genre_aliases(text,genre):
    assert genre in parse_preferences(text).preferences.preferred_genres


def test_reported_emotion_does_not_override_requested_tone():
    parsed=parse_preferences('I feel melancholic; suggest a cheerful movie')
    assert parsed.preferences.desired_mood=='cheerful'
    assert parse_preferences('Make it less intense').preferences.desired_mood=='calm'
    parsed=parse_preferences('I feel sad; suggest a cheerful movie')
    query,topic=build_search_query('I feel sad; suggest a cheerful movie',parsed.preferences)
    assert 'sad' not in query and not topic and 'cheerful' in query
    query,_=build_search_query('I feel stressed; find movies about a prison escape',Preferences())
    assert 'prison escape' in query and 'stressed' not in query


def test_reference_medium_is_distinct_from_requested_medium():
    assert detect_media('I enjoyed the movie Interstellar. Recommend a book like it.')=='books'
    assert detect_media('I liked the book The Hobbit. Suggest a movie like it.')=='movies'


def test_relative_shorter_actually_tightens_limit():
    old=Preferences(max_runtime=120,max_pages=300)
    parsed=parse_preferences('Make the movies shorter')
    merged=merge_preferences(old,parsed.preferences,'Make the movies shorter',parsed.explicit_fields)
    assert merged.max_runtime==105 and merged.max_pages==300


def test_explicit_limit_removal_and_genre_replacement():
    old=Preferences(preferred_genres=['romance'],max_runtime=90)
    parsed=parse_preferences('Actually comedy instead. Remove the runtime limit')
    merged=merge_preferences(old,parsed.preferences,parsed.raw_text,parsed.explicit_fields)
    assert merged.preferred_genres==['comedy'] and merged.max_runtime is None


def test_form_query_removes_old_mood_and_genre():
    query,topic=build_search_query('Recommend an uplifting family movie under two hours',Preferences(preferred_genres=['crime'],desired_mood='dark'))
    assert 'uplifting' not in query and 'family' not in query
    assert 'crime' in query and 'dark' in query


def test_unknown_runtime_and_classifier_predictions_cannot_satisfy_facts(tmp_path):
    item=CatalogItem('movie_unknown','movie','Unknown','A warm comedy.',predicted_genres=['family'])
    index=RetrievalIndex([item],mode='tfidf',artifact_dir=tmp_path)
    assert index.search('family',Preferences(preferred_genres=['family']))==[]
    assert index.search('comedy',Preferences(max_runtime=100))==[]


def test_infobox_uses_explicit_units_and_rejects_ambiguous_versions():
    assert extract_fields('{{Infobox film\n| runtime = 105 minutes<ref>citation</ref>\n| language = [[English language|English]]\n| country = USA\n}}')==(105,'English')
    assert extract_fields('{{Infobox film\n| runtime = 105 minutes; extended version 120 minutes\n| country = USA\n}}')==(None,'')
    assert extract_fields('{{Infobox film\n| runtime = unknown\n| country = United States\n}}')==(None,'')


def test_profiles_have_local_keywords_and_score_evidence(variety_engine):
    _,results=variety_engine.handle('A funny comedy movie under 90 minutes',ConversationState())
    rec=results['movie'][0]
    assert rec.item.nlp_keywords and rec.matched_terms
    assert rec.score_components['genre_coverage']==1
    assert rec.score_components['mood_alignment']>0


def test_plot_chunks_cover_middle_and_end():
    words=[f'word{x}' for x in range(1000)]
    chunks=content_chunks(' '.join(words))
    assert len(chunks)==3 and 'word0' in chunks[0] and 'word999' in chunks[-1]
