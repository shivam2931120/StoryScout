import json
from types import SimpleNamespace

from src.schemas import ConversationState
from src.conversation import StoryScoutEngine
from src.llm_interpreter import NemotronQueryInterpreter, configured_api_key


class FakeCompletions:
    def __init__(self, payload):
        self.payload = payload
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        message = SimpleNamespace(content=json.dumps(self.payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def narnia_payload():
    return {
        "intent": "recommend", "media_selection": "books", "search_query": "Narnia fantasy adventure",
        "reference_title": None, "preferred_genres": ["fantasy"], "excluded_genres": [],
        "desired_mood": None, "themes": ["adventure"], "language": None,
        "min_year": None, "max_year": None, "max_pages": None, "max_runtime": None,
        "negative_content": [], "explicit_fields": ["preferred_genres", "themes"],
    }


def test_key_source_is_server_only(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    assert configured_api_key({"NVIDIA_API_KEY": "server-secret"}) == "server-secret"
    monkeypatch.setenv("NVIDIA_API_KEY", "environment-secret")
    assert configured_api_key({"NVIDIA_API_KEY": "streamlit-secret"}) == "environment-secret"


def test_nemotron_normalizes_query_and_drives_local_retrieval(catalogs):
    fake = FakeCompletions(narnia_payload())
    interpreter = NemotronQueryInterpreter("test-only", client=SimpleNamespace(chat=SimpleNamespace(completions=fake)))
    engine = StoryScoutEngine(catalogs, {m: __import__("src.retrieval", fromlist=["RetrievalIndex"]).RetrievalIndex(catalogs[m], "tfidf") for m in catalogs}, query_interpreter=interpreter)
    state = ConversationState()
    reply, results = engine.handle("narnnia", state)
    assert results["book"]
    assert state.media_selection == "books"
    assert interpreter.last_call_ok is True
    assert fake.kwargs["model"] == "nvidia/nemotron-3.5-lightning-30b-a3b"
    request_payload = json.loads(fake.kwargs["messages"][1]["content"])
    assert request_payload["message"] == "narnnia"
    assert "catalog_titles" not in request_payload


def make_interpreter(payload):
    return NemotronQueryInterpreter("test-only", client=SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(payload))))


def test_model_cannot_override_explicit_constraints_or_issue_reset(engine):
    payload = narnia_payload()
    payload.update(intent="reset", media_selection="books", desired_mood="dark", max_runtime=200, max_pages=999,
                   preferred_genres=["horror"], explicit_fields=["desired_mood", "max_runtime", "max_pages", "preferred_genres"])
    engine.query_interpreter = make_interpreter(payload)
    state = ConversationState(media_selection="movies", has_explicit_media=True)
    engine.handle("Recommend cheerful movies under 90 minutes, no horror", state)
    assert state.preferences.max_runtime == 90
    assert state.preferences.max_pages is None
    assert state.preferences.desired_mood == "cheerful"
    assert state.media_selection == "movies"
    assert "horror" not in state.preferences.preferred_genres
    assert "horror" in state.preferences.excluded_genres


def test_model_cannot_change_inherited_media(engine):
    engine.query_interpreter = make_interpreter(narnia_payload())
    state = ConversationState(media_selection="movies", has_explicit_media=True)
    engine.handle("Something welcoming with unlikely friendships", state)
    assert state.media_selection == "movies"


def test_invalid_model_response_uses_local_nlp(engine):
    from src.schemas import Preferences
    for value in [True, -10, "300", {"value": 300}]:
        payload = narnia_payload()
        payload["max_pages"] = value
        interpreter = make_interpreter(payload)
        assert interpreter.interpret("a short book", "books", Preferences()) is None
        assert interpreter.last_call_ok is False
    engine.query_interpreter = make_interpreter({"intent": "reset"})
    state = ConversationState()
    _, results = engine.handle("Recommend comedy movies under 120 minutes", state)
    assert results["movie"]
    assert state.preferences.max_runtime == 120
    assert engine.last_interpretation["status"] == "fallback"


def test_nemotron_expands_language_but_ranking_stays_local(engine):
    payload = narnia_payload()
    payload.update(media_selection="inherit", search_query="space exploration survival astronaut", preferred_genres=[], themes=["space", "survival"])
    engine.query_interpreter = make_interpreter(payload)
    state = ConversationState(media_selection="movies", has_explicit_media=True)
    _, results = engine.handle("A journey beyond our planet with a struggle to stay alive", state)
    assert engine.last_interpretation["status"] == "used"
    assert engine.last_diagnostics["movie"]["catalog_size"] == len(engine.catalogs["movie"])
    assert results["movie"]
    assert all(rec.item in engine.catalogs["movie"] for rec in results["movie"])


def test_network_timeout_retains_local_results(engine):
    def timeout(**kwargs):
        raise TimeoutError("simulated provider timeout")
    engine.query_interpreter = NemotronQueryInterpreter("test-only", client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=timeout))))
    state = ConversationState()
    _, results = engine.handle("Recommend comedy movies under 120 minutes", state)
    assert results["movie"]
    assert state.preferences.max_runtime == 120
    assert engine.last_interpretation["status"] == "fallback"
