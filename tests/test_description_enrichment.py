import io
import json

from src.data_loader import apply_description_enrichment
from src.description_enrichment import NemotronDescriptionSummarizer, find_wikipedia_source
from src.schemas import CatalogItem


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_wikipedia_lookup_requires_exact_title_and_returns_attributed_source():
    item = CatalogItem("movie_1", "movie", "A Film (2000)", "Metadata only", source="movielens-latest-small", year=2000)

    def opener(request, timeout):
        if "list%3Dsearch" in request.full_url or "list=search" in request.full_url:
            payload = {"query": {"search": [{"title": "A Film (film)"}, {"title": "A Different Film"}]}}
        else:
            payload = {"query": {"pages": {"1": {"title": "A Film (film)", "extract": "A Film is a 2000 film. " + "A sourced introductory description. " * 8}}}}
        return FakeResponse(json.dumps(payload).encode())

    result = find_wikipedia_source(item, opener=opener)
    assert result and result["title"] == "A Film (film)"
    assert result["url"].startswith("https://en.wikipedia.org/wiki/")
    assert "sourced introductory" in result["excerpt"]


def test_wikipedia_lookup_rejects_nonmatching_title():
    item = CatalogItem("book_1", "book", "The Original Novel", "Metadata only", source="project-gutenberg-catalog")

    def opener(request, timeout):
        return FakeResponse(json.dumps({"query": {"search": [{"title": "The Completely Different Novel"}]}}).encode())

    assert find_wikipedia_source(item, opener=opener) is None


def test_nemotron_summarizer_uses_only_provided_source_and_limits_output():
    class FakeCompletions:
        def create(self, **kwargs):
            body = json.loads(kwargs["messages"][1]["content"])
            assert body[0]["source_excerpt"] == "Wikipedia source text"
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {
                "content": json.dumps({"summaries": [{"id": "book_1", "description": "A faithful short summary from the supplied source."}]})
            })})]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})})()
    summarizer = NemotronDescriptionSummarizer("test-only", client=client)
    result = summarizer.summarize_batch([{
        "id": "book_1", "title": "A book", "media_type": "book", "year": "1900",
        "source_excerpt": "Wikipedia source text", "source_title": "A book", "source_url": "https://en.wikipedia.org/wiki/A_book",
    }])
    assert result == {"book_1": "A faithful short summary from the supplied source."}


def test_catalog_enrichment_changes_search_text_and_preserves_original_source(tmp_path):
    import pandas as pd

    item = CatalogItem("movie_1", "movie", "A Film", "Plot description not provided.", source="movielens-latest-small")
    path = tmp_path / "descriptions.csv"
    pd.DataFrame([{
        "id": item.id, "description": "A grounded summary about a lost astronaut.",
        "description_source": "Wikipedia (CC BY-SA 4.0)",
        "description_source_url": "https://en.wikipedia.org/wiki/A_Film",
        "description_provenance": "AI paraphrase of source lead",
    }]).to_csv(path, index=False)
    applied = apply_description_enrichment({"movie": [item]}, path)
    assert applied == 1
    assert item.source == "movielens-latest-small"
    assert "lost astronaut" in item.search_text
    assert item.description_source_url.endswith("A_Film")
    assert apply_description_enrichment({"movie": [item]}, path) == 0
