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
