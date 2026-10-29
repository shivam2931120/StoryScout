from __future__ import annotations
import re
from .schemas import ConversationState, CatalogItem, Recommendation
from .preferences import parse_preferences, merge_preferences
from .intents import detect_media
from .title_matching import resolve_title, correct_catalog_query, TitleDirectory
from .cross_media import reference_context
from .explanations import explain, explain_reference
from .query_understanding import build_search_query

class StoryScoutEngine:
    def __init__(self, catalogs: dict[str, list[CatalogItem]], indexes: dict[str, object], retrieval_mode: str = "hybrid", query_interpreter=None, title_directory=None):
        self.catalogs, self.indexes, self.retrieval_mode = catalogs, indexes, retrieval_mode
        self.query_interpreter = query_interpreter
        self.last_diagnostics = {}
        self.title_directory = title_directory or TitleDirectory()
        self.last_title_matches = []
        self.last_title_lookup = False
        self.last_title_match_kind = "none"
        self.last_context_action = "auto"

    def get_item(self, item_id):
        return next((item for group in self.catalogs.values() for item in group if item.id == item_id), None) or self.title_directory.get(item_id)

    def reset(self, state: ConversationState) -> ConversationState:
        state.messages.clear(); state.preferences = state.preferences.__class__(); state.media_selection = "both"; state.has_explicit_media = False; state.selected_reference_id = None; state.last_recommendations.clear(); state.pending_title_choices.clear()
        state.last_content_query=''; state.seen_recommendations.clear()
        return state

    def new_search(self, state):
        """Explicit user action: retain chat history/format, clear old criteria."""
        state.preferences = state.preferences.__class__()
        state.selected_reference_id = None
        state.last_content_query = ''
        state.last_recommendations.clear()
        state.seen_recommendations.clear()
        state.pending_title_choices.clear()

    def _active_domains(self, selection: str) -> list[str]:
        return ["book", "movie"] if selection == "both" else (["book"] if selection == "books" else ["movie"])

    def handle(self, text: str, state: ConversationState, *, reference_id: str | None = None, lookup_id: str | None = None, search_action: str = "auto") -> tuple[str, dict[str, list[Recommendation]]]:
        self.last_diagnostics={}
        self.last_title_matches = []
        self.last_title_lookup = False
        self.last_title_match_kind = "none"
        command = re.match(r"^(?:start (?:a )?new search|new search|start fresh)\s*[:;,.!-]?\s*", text, re.I)
        if command:
            search_action = 'new'
            text = text[command.end():].strip() or 'Show stories'
        self.last_context_action = search_action
        if search_action == 'new':
            self.new_search(state)
        if search_action == 'similar':
            state.last_content_query = ''
        parsed = parse_preferences(text)
        # Resolve the complete title before interpreting words such as dark, no,
        # short or romance as instructions. Similarity requests keep the NLP path.
        controls = {"reset", "reset my preferences", "help", "show preferences", "why did you recommend this"}
        if not reference_id and parsed.intent not in {"reset", "help", "show_preferences", "explain", "more"} and text.strip().lower().rstrip("?.!") not in controls:
            matches, approximate, explicit = self.title_directory.lookup(text, [x for group in self.catalogs.values() for x in group], state.media_selection)
            if lookup_id:
                selected = self.get_item(lookup_id)
                matches, approximate, explicit = ([selected] if selected else []), False, True
            if matches or explicit:
                self.last_title_lookup = True
                self.last_title_match_kind = self.title_directory.last_match_kind
                state.pending_title_choices.clear()
                requested_media = self.title_directory.last_requested_media
                if requested_media:
                    state.media_selection = "books" if requested_media == "book" else "movies"
                    state.has_explicit_media = True
                if self.title_directory.last_constraint_text:
                    suffix=parse_preferences(self.title_directory.last_constraint_text)
                    state.preferences=merge_preferences(state.preferences,suffix.preferences,self.title_directory.last_constraint_text,suffix.explicit_fields)
                state.messages.append({"role": "user", "content": text})
                for item in matches:
                    _, conflicts = self.indexes[item.media_type]._hard_filter(item, state.preferences)
                    if state.preferences.language and item.language.lower() == "unknown":
                        conflicts = ["language is unknown; cannot verify " + state.preferences.language if note.startswith("language is not ") else note for note in conflicts]
                    explanation = "Possible title spelling match; choose the intended title." if approximate else ("Matched part of a catalog title; choose the intended title." if self.last_title_match_kind == "partial" else "Matched the catalog title directly.")
                    if conflicts:
                        explanation += " Current recommendation filters: " + "; ".join(conflicts) + ". This is a title lookup, not a verified filtered recommendation."
                    if state.preferences.negative_content and not item.verified_warnings:
                        explanation += " Content suitability is unknown; no verified warning labels are available."
                    self.last_title_matches.append((item, explanation))
                if not matches:
                    reply = f"That title is not in the local title directory under ‘{self.title_directory.last_entity}’. It may be missing or spelled differently. Try the full title, release year, or author. For a topic search, say ‘stories about …’. I have not substituted unrelated titles."
                elif approximate:
                    reply = "Did you mean one of these titles? Choose the intended match."
                elif self.last_title_match_kind == "partial":
                    reply = "These catalog titles contain that name. Choose the one you meant."
                else:
                    reply = "Found the title in the catalog." if len(matches) == 1 else "Several titles match. Open the one you meant."
                state.selected_reference_id = matches[0].id if len(matches) == 1 and self.last_title_match_kind == "exact" and not approximate else None
                return reply, {}
        search_query = text
        nemotron_failed = False
        if self.query_interpreter and parsed.intent not in {"reset", "help", "show_preferences", "explain", "more"}:
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
        merge_text = text
        if "short" in parsed.explicit_fields and parsed.media_selection is None:
            if state.media_selection == "books": merge_text += " books"
            elif state.media_selection == "movies": merge_text += " movies"
        state.preferences = merge_preferences(state.preferences, parsed.preferences, merge_text, parsed.explicit_fields)
        if parsed.intent == "show_preferences": return self.preference_summary(state), {}
        if parsed.intent == "help": return "Try a title or topic such as “Frodo Baggins”, “Narnia”, or “space exploration”, or ask for a mood, genre, year, page, or runtime limit.", {}
        if state.preferences.contradiction_messages:
            return "I found a contradiction: " + " ".join(state.preferences.contradiction_messages) + " Please choose which constraint to keep.", {}
        if parsed.intent == "explain":
            return self.explain_last(state), {}
        search_query = correct_catalog_query(search_query, self.catalogs["book"] + self.catalogs["movie"])
        reference = None
        all_items = self.catalogs["book"] + self.catalogs["movie"]
        if reference_id:
            reference = self.get_item(reference_id)
            if reference:
                state.selected_reference_id = reference.id
                state.preferences.referenced_title = reference.title
                state.pending_title_choices.clear()
        elif parsed.reference_query and parsed.reference_query.lower().strip() in {'it', 'this', 'that', 'this one', 'that one'} and state.selected_reference_id:
            reference = self.get_item(state.selected_reference_id)
            if reference:
                state.preferences.referenced_title = reference.title
                state.pending_title_choices.clear()
        elif parsed.reference_query:
            exact, approximate, _ = self.title_directory.lookup(parsed.reference_query, all_items)
            if approximate:
                state.selected_reference_id=None
                state.pending_title_choices=[x.id for x in exact]
                return "Did you mean one of these reference titles? Choose the intended title before I compare its story.", {}
            reference, choices = (exact[0] if len(exact) == 1 and self.title_directory.last_match_kind == 'exact' else None), exact
            if not choices:
                state.selected_reference_id=None
                return f"I could not identify the reference title ‘{parsed.reference_query}’. Try its full title, author, or release year. I have not substituted another story.", {}
            if reference is None and choices:
                state.selected_reference_id=None
                state.pending_title_choices = [x.id for x in choices]
                return "I found multiple possible reference titles: " + ", ".join(x.title for x in choices) + ". Please name one.", {}
            if reference:
                state.selected_reference_id = reference.id
                state.pending_title_choices.clear()
            else:
                state.selected_reference_id = None
        elif state.selected_reference_id and (parsed.intent in {'refine','more','similar'} or re.match(r"^(also|only|make|what about|show me|more|shorter)\b", text.lower().strip())):
            reference = self.get_item(state.selected_reference_id)
        else:
            state.selected_reference_id = None
            state.preferences.referenced_title = None
            state.pending_title_choices.clear()
        if reference and reference.source.startswith(("movielens", "project-gutenberg", "wikidata-catalog", "openlibrary-catalog")) and not (reference.retrieval_text or reference.description_provenance or reference.genres or reference.theme_tags):
            return f"I found '{reference.title}', but its source has no synopsis or genre metadata for meaningful content comparison. Choose a described reference or search for themes directly.", {}
        followup = search_action == 'refine' or parsed.intent in {'refine','more'} or 'replace_genres' in parsed.explicit_fields or bool(re.match(r'^(also|only|make|what about|show me|more|shorter)\b',text.lower().strip()))
        effective, topic = build_search_query(search_query,state.preferences,state.last_content_query,followup)
        state.last_content_query=topic
        results = self.recommend(effective, state, reference, exclude_seen=parsed.intent=='more', prepared=True)
        if any(results.values()):
            summary = "Here are stories to explore, selected for your request."
            if nemotron_failed:
                summary += " I used local search for this request."
            return summary, results
        message = self.empty_message(state)
        if parsed.intent == 'more': message='No additional relevant, unseen titles match your current preferences. You can change a filter or start a new discovery.'
        if nemotron_failed:
            message += " I used local search for this request."
        return message, {}

    def recommend(self, search_query: str, state: ConversationState, reference: CatalogItem | None = None, *, exclude_seen: bool=False, prepared: bool=False) -> dict[str, list[Recommendation]]:
        """Shared ranking path for conversations and explicit preference-form edits."""
        results: dict[str, list[Recommendation]] = {}
        if not prepared:
            search_query, topic=build_search_query(search_query,state.preferences,state.last_content_query,bool(state.last_content_query))
            state.last_content_query=topic
        self.last_diagnostics={}
        for domain in self._active_domains(state.media_selection):
            query = search_query
            exclude = {reference.id} if reference and reference.media_type == domain else set()
            if exclude_seen: exclude.update(state.seen_recommendations+state.last_recommendations)
            if reference: query = reference_context(reference) + " " + search_query
            if not query and not any((state.preferences.preferred_genres,state.preferences.excluded_genres,state.preferences.max_pages,state.preferences.max_runtime,state.preferences.min_year,state.preferences.max_year,state.preferences.language)):
                query='An engaging story about discovery, human relationships and adventure'
            topic = (reference_context(reference) + ' ' if reference else '') + state.last_content_query
            results[domain] = self.indexes[domain].search(query, state.preferences, top_k=5, exclude_ids=exclude,seen_ids=set(state.seen_recommendations),topic_query=topic)
            self.last_diagnostics[domain]=dict(self.indexes[domain].last_diagnostics)
            for rec in results[domain]:
                rec.explanation = explain_reference(rec, reference, state.preferences) if reference else explain(rec, search_query, state.preferences)
        state.last_recommendations = [r.item.id for group in results.values() for r in group]
        state.seen_recommendations=list(dict.fromkeys(state.seen_recommendations+state.last_recommendations))[-300:]
        return results

    def preference_summary(self, state: ConversationState) -> str:
        p = state.preferences
        return f"Active media: {state.media_selection}. Genres: {', '.join(p.preferred_genres) or 'none'}. Excluded: {', '.join(p.excluded_genres) or 'none'}. Mood: {p.desired_mood or 'none'}. Themes: {', '.join(p.themes) or 'none'}. Years: {p.min_year or 'any'}–{p.max_year or 'any'}. Book pages: {p.max_pages or 'any'}. Movie runtime: {p.max_runtime or 'any'} minutes."

    def explain_last(self, state: ConversationState) -> str:
        if not state.last_recommendations: return "There are no recommendations to explain yet."
        return "The last results were selected using the active hard filters first, then whole-description and indexed-passage matching with TF-IDF and, when available, sentence embeddings. Each card lists grounded metadata and passage evidence."

    def empty_message(self, state: ConversationState) -> str:
        p = state.preferences
        constraints = []
        if p.max_pages: constraints.append(f"books ≤ {p.max_pages} pages")
        if p.max_runtime: constraints.append(f"movies ≤ {p.max_runtime} minutes")
        if p.min_year or p.max_year: constraints.append(f"years {p.min_year or 'any'}–{p.max_year or 'any'}")
        if any(value.get('eligible_count', 0) > 0 and value.get('quality_rejections', 0) > 0 for value in self.last_diagnostics.values()):
            return "Some titles pass your filters, but none match the topic strongly enough. Try a broader topic or another reference title. Your filters have been retained."
        return "No verified matches satisfy the current filters" + (" (" + ", ".join(constraints) + ")" if constraints else "") + ". I will not silently relax them; choose a less restrictive filter if you want to broaden the search."
