from __future__ import annotations
from .schemas import ConversationState, CatalogItem, Recommendation
from .preferences import parse_preferences, merge_preferences
from .intents import detect_media
from .title_matching import resolve_title, correct_catalog_query
from .cross_media import reference_context
from .explanations import explain, explain_reference

class StoryScoutEngine:
    def __init__(self, catalogs: dict[str, list[CatalogItem]], indexes: dict[str, object], retrieval_mode: str = "hybrid", query_interpreter=None):
        self.catalogs, self.indexes, self.retrieval_mode = catalogs, indexes, retrieval_mode
        self.query_interpreter = query_interpreter

    def reset(self, state: ConversationState) -> ConversationState:
        state.messages.clear(); state.preferences = state.preferences.__class__(); state.media_selection = "both"; state.has_explicit_media = False; state.selected_reference_id = None; state.last_recommendations.clear(); state.pending_title_choices.clear()
        return state

    def _active_domains(self, selection: str) -> list[str]:
        return ["book", "movie"] if selection == "both" else (["book"] if selection == "books" else ["movie"])

    def handle(self, text: str, state: ConversationState) -> tuple[str, dict[str, list[Recommendation]]]:
        parsed = parse_preferences(text)
        search_query = text
        nemotron_failed = False
        if self.query_interpreter and parsed.intent not in {"reset", "help", "show_preferences", "explain"}:
            interpreted = self.query_interpreter.interpret(text, state.media_selection, state.preferences)
            if interpreted:
                model_intent = interpreted.get("intent")
                if model_intent and not (parsed.intent == "recommend" and model_intent == "help"):
                    parsed.intent = model_intent
                requested_media = interpreted.get("media_selection")
                if parsed.media_selection is None and requested_media in {"books", "movies", "both"}:
                    parsed.media_selection = requested_media
                if interpreted.get("reference_title"):
                    parsed.reference_query = str(interpreted["reference_title"]).strip()
                    parsed.preferences.referenced_title = parsed.reference_query
                    parsed.explicit_fields.add("referenced_title")
                search_query = str(interpreted.get("search_query") or text).strip() or text
                for name in ("preferred_genres", "excluded_genres", "themes", "negative_content"):
                    values = list(getattr(parsed.preferences, name))
                    values.extend(str(value).lower() for value in (interpreted.get(name) or []))
                    setattr(parsed.preferences, name, list(dict.fromkeys(values)))
                for name in ("desired_mood", "language", "min_year", "max_year", "max_pages", "max_runtime"):
                    value = interpreted.get(name)
                    if name not in parsed.explicit_fields and value is not None:
                        setattr(parsed.preferences, name, value)
                parsed.explicit_fields.update(str(value) for value in (interpreted.get("explicit_fields") or []))
            else:
                nemotron_failed = True
        state.messages.append({"role": "user", "content": text})
        if parsed.intent == "reset": self.reset(state); return "Preferences and recommendation context reset.", {}
        if parsed.media_selection:
            state.media_selection, state.has_explicit_media = parsed.media_selection, True
        state.preferences = merge_preferences(state.preferences, parsed.preferences, text, parsed.explicit_fields)
        if parsed.intent == "show_preferences": return self.preference_summary(state), {}
        if parsed.intent == "help": return "Try a title or topic such as “Frodo Baggins”, “Narnia”, or “space exploration”, or ask for a mood, genre, year, page, or runtime limit.", {}
        if state.preferences.contradiction_messages:
            return "I found a contradiction: " + " ".join(state.preferences.contradiction_messages) + " Please choose which constraint to keep.", {}
        if parsed.intent == "explain":
            return self.explain_last(state), {}
        domains = self._active_domains(state.media_selection)
        search_query = correct_catalog_query(search_query, self.catalogs["book"] + self.catalogs["movie"])
        reference = None
        if parsed.reference_query:
            reference, choices = resolve_title(parsed.reference_query, self.catalogs["book"] + self.catalogs["movie"])
            if reference is None and choices:
                state.pending_title_choices = [x.id for x in choices]
                return "I found multiple possible reference titles: " + ", ".join(x.title for x in choices) + ". Please name one.", {}
            if reference: state.selected_reference_id = reference.id
        results: dict[str, list[Recommendation]] = {}
        for domain in domains:
            query = search_query
            exclude = {reference.id} if reference and reference.media_type == domain and parsed.intent == "similar" else set()
            if reference: query = reference_context(reference) + " " + search_query
            results[domain] = self.indexes[domain].search(query, state.preferences, top_k=5, exclude_ids=exclude)
            for rec in results[domain]:
                rec.explanation = explain_reference(rec, reference, state.preferences) if reference else explain(rec, text, state.preferences)
        state.last_recommendations = [r.item.id for group in results.values() for r in group]
        if any(results.values()):
            summary = "Here are grounded similarity results, grouped by medium."
            if state.preferences.contradiction_messages: summary += " Note: " + " ".join(state.preferences.contradiction_messages)
            if nemotron_failed:
                summary += " I used local search for this request."
            return summary, results
        message = self.empty_message(state)
        if nemotron_failed:
            message += " I used local search for this request."
        return message, {}

    def preference_summary(self, state: ConversationState) -> str:
        p = state.preferences
        return f"Active media: {state.media_selection}. Genres: {', '.join(p.preferred_genres) or 'none'}. Excluded: {', '.join(p.excluded_genres) or 'none'}. Mood: {p.desired_mood or 'none'}. Themes: {', '.join(p.themes) or 'none'}. Years: {p.min_year or 'any'}–{p.max_year or 'any'}. Book pages: {p.max_pages or 'any'}. Movie runtime: {p.max_runtime or 'any'} minutes."

    def explain_last(self, state: ConversationState) -> str:
        if not state.last_recommendations: return "There are no recommendations to explain yet."
        return "The last results were selected using the active hard filters first, then TF-IDF and, when available, sentence-embedding similarity. Each card lists the grounded matching evidence."

    def empty_message(self, state: ConversationState) -> str:
        p = state.preferences
        constraints = []
        if p.max_pages: constraints.append(f"books ≤ {p.max_pages} pages")
        if p.max_runtime: constraints.append(f"movies ≤ {p.max_runtime} minutes")
        if p.min_year or p.max_year: constraints.append(f"years {p.min_year or 'any'}–{p.max_year or 'any'}")
        return "No verified matches satisfy the current filters" + (" (" + ", ".join(constraints) + ")" if constraints else "") + ". I will not silently relax them; choose a less restrictive filter if you want to broaden the search."
