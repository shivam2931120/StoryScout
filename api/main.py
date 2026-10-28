"""React's API, backed by the same local NLP engine as the Streamlit app.

State is explicitly passed per request. No shared global conversation, no key in
responses, and no dependency on an external LLM for recommendations.
"""
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
import asyncio
import json
import io
import logging
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.models import ChatRequest, JudgmentRequest
from src.config import ROOT, MODEL_NAME
from src.conversation import StoryScoutEngine
from src.data_loader import load_active_catalogs, catalog_status
from src.description_enrichment import get_server_api_key
from src.llm_interpreter import NemotronQueryInterpreter
from src.preferences import GENRES, MOODS, parse_preferences
from src.retrieval import RetrievalIndex
from src.human_evaluation import create_judgment_template, score_human_judgments

logger = logging.getLogger(__name__)


def make_engine() -> StoryScoutEngine:
    mode = os.getenv("STORYSCOUT_RETRIEVAL_MODE", "hybrid")
    if mode not in {"hybrid", "semantic", "tfidf"}:
        raise ValueError("STORYSCOUT_RETRIEVAL_MODE must be hybrid, semantic, or tfidf")
    catalogs = load_active_catalogs()
    indexes = {domain: RetrievalIndex(items, mode=mode) for domain, items in catalogs.items()}
    # External interpretation is an explicit server option; local NLP is default.
    key = get_server_api_key() if os.getenv("STORYSCOUT_USE_NVIDIA", "false").lower() == "true" else None
    return StoryScoutEngine(catalogs, indexes, mode, NemotronQueryInterpreter(key) if key else None)


def item_payload(item):
    payload = asdict(item)
    payload.pop('retrieval_text',None)  # Full plots stay local; display excerpts avoid revealing endings.
    metadata_only = item.source.startswith(("movielens", "project-gutenberg"))
    if metadata_only and not item.description_provenance:
        payload["description"] = None
    payload["description_status"] = ('sourced_excerpt' if item.retrieval_text and not item.description_provenance.startswith('AI') else 'sourced_ai') if item.description_provenance else ("unavailable" if metadata_only else "original_demo")
    return payload


def create_app(engine: StoryScoutEngine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        if app.state.engine is None:
            async def prepare():
                try:
                    app.state.engine = await asyncio.to_thread(make_engine)
                except Exception:
                    logger.exception("Local catalog preparation failed")
                    app.state.preparation_failed = True
            task = asyncio.create_task(prepare())
        else:
            task = None
        yield
        if task is not None:
            await task

    app = FastAPI(title="StoryScout NLP API", version="2.0.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.preparation_failed = False
    app.state.lock = threading.Lock()
    origins = [x.strip() for x in os.getenv("STORYSCOUT_ALLOWED_ORIGINS", "").split(",") if x.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def ready_engine():
        if app.state.engine is None:
            raise HTTPException(503, "Search preparation failed. Check server logs." if app.state.preparation_failed else "Preparing local search indexes. Please try again shortly.")
        return app.state.engine

    def modes(current):
        return {domain: index.active_mode for domain, index in current.indexes.items()}

    @app.get("/api/health")
    def health():
        return {"status": "error" if app.state.preparation_failed else ("ready" if app.state.engine is not None else "preparing")}

    @app.get("/api/ready")
    def readiness():
        current = ready_engine()
        return {"status": "ready", "modes": modes(current)}

    @app.get("/api/meta")
    def metadata():
        current = ready_engine()
        titles = ["The Hobbit", "Interstellar", "The Little Prince", "Paddington 2"]
        all_items = [x for items in current.catalogs.values() for x in items]
        starters = [next((x for x in all_items if x.title == title and x.source.startswith("demo")), None) for title in titles]
        return {"counts": {k: len(v) for k, v in current.catalogs.items()}, "status": catalog_status(all_items),
                "genres": GENRES, "moods": MOODS, "modes": modes(current), "model": MODEL_NAME,
                "coverage":{domain:{'plot_text':sum(bool(x.retrieval_text) for x in items),'descriptions':sum(bool(x.retrieval_text or x.description_provenance or x.source=='demo') for x in items),
                    'known_runtime':sum(x.runtime_minutes is not None for x in items),'known_pages':sum(x.page_count is not None for x in items),'source_languages':sum(x.language.lower()!='unknown' for x in items),
                    'subject_genre_mappings':sum(bool(x.subject_genres) for x in items)} for domain,items in current.catalogs.items()},
                "nlp_profiles":"Corpus TF-IDF keyphrases, chunk-pooled MiniLM vectors, semantic mood/theme prototypes, locally trained plot genre classifier, MMR selection",
                "optional_interpreter": current.query_interpreter is not None,
                "starters": [item_payload(x) for x in starters if x is not None]}

    def respond(request: ChatRequest, parse: bool):
        if not request.message.strip():
            raise HTTPException(422, "Write a title, topic, or request first.")
        current = ready_engine()
        state = request.state.to_domain()
        prior_seen=list(state.seen_recommendations)
        state.messages = state.messages[-60:]
        state.retrieval_mode = current.retrieval_mode
        items = {x.id: x for group in current.catalogs.values() for x in group}
        if request.reference_id and request.reference_id not in items:
            raise HTTPException(404, "Reference title is not in this catalog.")
        if state.selected_reference_id and state.selected_reference_id not in items:
            state.selected_reference_id = None
        pref = state.preferences
        # Recompute contradictions from real preferences, never trust client flags.
        pref.contradiction_messages = []
        overlap = set(pref.preferred_genres) & set(pref.excluded_genres)
        if overlap:
            pref.contradiction_messages.append("A genre cannot be both preferred and excluded: " + ", ".join(sorted(overlap)))
        if pref.min_year and pref.max_year and pref.min_year > pref.max_year:
            pref.contradiction_messages.append("The start year must be earlier than the end year.")
        start = time.perf_counter()
        with app.state.lock:
            current.last_diagnostics={}
            if parse:
                reply, results = current.handle(request.message, state, reference_id=request.reference_id)
            elif pref.contradiction_messages:
                reply, results = "Please resolve these preferences: " + " ".join(pref.contradiction_messages), {}
            else:
                reference = items.get(state.selected_reference_id)
                results = current.recommend(request.message, state, reference)
                reply = "Your preferences are applied. Here are the matching stories." if any(results.values()) else current.empty_message(state)
            diagnostics={k:dict(v) for k,v in current.last_diagnostics.items()}
        results = {domain: group[:request.per_domain] for domain, group in results.items()}
        state.last_recommendations = [rec.item.id for group in results.values() for rec in group]
        state.seen_recommendations=[] if parse and parse_preferences(request.message).intent=='reset' else list(dict.fromkeys(prior_seen+state.last_recommendations))[-300:]
        state.messages = state.messages[-60:]
        parsed = parse_preferences(request.message)
        trace = {"intent": parsed.intent if parse else "preference_edit", "method": "rule baseline" + (" + optional NVIDIA interpretation" if current.query_interpreter else ""),
                 "extracted_fields": sorted(parsed.explicit_fields) if parse else [], "active_modes": modes(current),
                 "retrieval":diagnostics,"content_query":state.last_content_query,
                 "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
        return {"reply": reply, "state": asdict(state), "results": {domain: [{"item": item_payload(rec.item), "similarity_score": rec.score,
                "lexical_score": rec.lexical_score, "semantic_score": rec.semantic_score, "explanation": rec.explanation,
                "score_components":rec.score_components,"matched_terms":rec.matched_terms} for rec in group] for domain, group in results.items()},
                "choices": [item_payload(items[x]) for x in state.pending_title_choices if x in items], "trace": trace}

    @app.post("/api/chat")
    def chat(request: ChatRequest):
        return respond(request, parse=True)

    @app.post("/api/recommend")
    def recommend(request: ChatRequest):
        """Authoritative form filters: rank with the query, without reparsing old limits."""
        return respond(request, parse=False)

    @app.get("/api/evaluation")
    def evaluation():
        path = ROOT / "artifacts/evaluation_results.json"
        return {"results": json.loads(path.read_text()) if path.exists() else None,
                "summary": (ROOT / "artifacts/evaluation_summary.md").read_text() if (ROOT / "artifacts/evaluation_summary.md").exists() else "Not evaluated yet.",
                "genre_classifier": json.loads((ROOT / "artifacts/genre_classifier_results.json").read_text()) if (ROOT / "artifacts/genre_classifier_results.json").exists() else None,
                "genre_text_classifier": json.loads((ROOT/'artifacts/genre_text_results.json').read_text()) if (ROOT/'artifacts/genre_text_results.json').exists() else None,
                "preference_search": json.loads((ROOT/'artifacts/search_tuning/preference_v2_results.json').read_text()) if (ROOT/'artifacts/search_tuning/preference_v2_results.json').exists() else None,
                "judgments": "Developer-authored judgments; not independent human evaluation."}

    @app.get("/api/evaluation/template")
    def judgment_template():
        import pandas as pd
        current = ready_engine()
        path = ROOT / "artifacts/evaluation_query_results.csv"
        if not path.exists():
            raise HTTPException(404, "Run scripts/evaluate.py to prepare candidates first.")
        titles = {x.id: x.title for group in current.catalogs.values() for x in group}
        frame = create_judgment_template(pd.read_csv(path, keep_default_na=False), titles)
        return {"csv": frame.to_csv(index=False), "filename": "storyscout-human-judgments.csv"}

    @app.post("/api/evaluation/judge")
    def human_judgments(request: JudgmentRequest):
        import pandas as pd
        try:
            frame = pd.read_csv(io.StringIO(request.csv_text), keep_default_na=False)
            if "rank" in frame:
                ranks = pd.to_numeric(frame["rank"], errors="coerce")
                if not ranks.between(1, 5).all():
                    raise ValueError("Ranks must be from 1 through 5.")
            if "relevance_0_2" in frame and not frame["relevance_0_2"].astype(str).isin(["", "0", "1", "2", "0.0", "1.0", "2.0"]).all():
                raise ValueError("Relevance must be 0, 1, 2, or blank.")
            scored, count = score_human_judgments(frame)
            return {"rating_count": count, "rows": scored.to_dict(orient="records"), "csv": scored.to_csv(index=False)}
        except (ValueError, pd.errors.ParserError) as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/items/{item_id}")
    def item(item_id: str):
        current = ready_engine()
        found = next((x for group in current.catalogs.values() for x in group if x.id == item_id), None)
        if found is None:
            raise HTTPException(404, "Title is not in this catalog.")
        return item_payload(found)

    dist = ROOT / "frontend/dist"
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "API endpoint not found.")
        # Only serve known public files. Never expose repository files or secrets.
        if path in {"favicon.svg", "art/space.svg", "art/mystery.svg", "art/journey.svg", "art/warm.svg"} and (dist / path).is_file():
            return FileResponse(dist / path)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        raise HTTPException(404, "Build the React frontend with cd frontend && npm run build, or use the Vite dev server.")

    return app


app = create_app()
