from src.intents import detect_media
from src.preferences import parse_preferences, merge_preferences
from src.schemas import Preferences, ConversationState
from src.conversation import StoryScoutEngine

def test_media_detection():
    assert detect_media("suggest a book") == "books"
    assert detect_media("recommend a movie") == "movies"
    assert detect_media("books and movies") == "both"

def test_negation_and_mood():
    parsed = parse_preferences("I feel sad; suggest something cheerful with no horror")
    assert parsed.preferences.desired_mood == "cheerful"
    assert "horror" in parsed.preferences.excluded_genres

def test_standalone_exclusion_updates_preferences(engine):
    state = ConversationState()
    reply, _ = engine.handle("No horror", state)
    assert "horror" in state.preferences.excluded_genres
    assert "I can recommend" not in reply

def test_cheerful_is_recommendation_mood():
    assert parse_preferences("I feel sad; suggest something cheerful").preferences.desired_mood == "cheerful"

def test_bare_title_or_topic_is_a_search():
    assert parse_preferences("frodo baggins").intent == "recommend"

def test_separate_constraints():
    a = parse_preferences("books under 250 pages").preferences
    b = parse_preferences("movies under 90 minutes").preferences
    assert a.max_pages == 250 and a.max_runtime is None
    assert b.max_runtime == 90 and b.max_pages is None

def test_year_parsing():
    p = parse_preferences("movies between 2000 and 2020").preferences
    assert p.min_year == 2000 and p.max_year == 2020
    assert parse_preferences("after 2015").preferences.min_year == 2016

def test_merge_and_contradiction():
    current = Preferences(excluded_genres=["horror"])
    incoming = parse_preferences("actually include horror").preferences
    merged = merge_preferences(current, incoming, "actually include horror", {"include_genre"})
    assert "horror" not in merged.excluded_genres
    bad = merge_preferences(Preferences(preferred_genres=["mystery"]), parse_preferences("no mystery").preferences, "no mystery", {"excluded_genres"})
    assert bad.contradiction_messages

def test_media_switch_and_reset(engine):
    state = ConversationState()
    engine.handle("only books", state)
    assert state.media_selection == "books"
    engine.handle("reset my preferences", state)
    assert state.media_selection == "both" and not state.preferences.preferred_genres
