from __future__ import annotations
import re
from .schemas import ConversationState, CatalogItem, Recommendation
from .preferences import parse_preferences, merge_preferences
from .intents import detect_media
from .title_matching import resolve_title, correct_catalog_query, TitleDirectory, title_key
from .cross_media import reference_context
from .explanations import explain, explain_reference
from .query_understanding import build_search_query

class StoryScoutEngine:
    def __init__(self, catalogs: dict[str, list[CatalogItem]], indexes: dict[str, object], retrieval_mode: str = "hybrid", query_interpreter=None, title_directory=None, movie_source=None, book_source=None):
        self.catalogs, self.indexes, self.retrieval_mode = catalogs, indexes, retrieval_mode
        self.query_interpreter = query_interpreter
        self.last_diagnostics = {}
        self.title_directory = title_directory or TitleDirectory()
        self.movie_source = movie_source
        self.book_source = book_source
        self.last_title_matches = []
        self.last_title_lookup = False
        self.last_title_match_kind = "none"
        self.last_context_action = "auto"
        self.last_interpretation = {"status": "not_needed"}

    def _lookup_title(self, query, all_items, selection="both"):
        matches, approximate, explicit = self.title_directory.lookup(query, all_items, selection)
        requested = self.title_directory.last_requested_media
        if self.book_source and selection in {"books", "both"} and requested != "movie" and explicit:
            # The external source is a live candidate source only. Filter its
            # semantic results back to title-like matches for identity lookup;
            # do not retain remote records in the local title directory.
            remote = self.book_source.search(self.title_directory.last_entity, number=12, details_limit=12)
            phrase = self.title_directory.last_entity.casefold()
            phrase_terms = {x for x in phrase.split() if len(x) > 1}
            remote = [item for item in remote if (
                phrase and phrase in item.title.casefold()
                or phrase_terms and len(phrase_terms & set(item.title.casefold().split())) >= max(1, len(phrase_terms) - 1)
            )]
            preferred = requested or {"books": "book", "both": None}.get(selection)
            if preferred:
                remote = [item for item in remote if item.media_type == preferred]
            if selection == "books":
                if remote:
                    # Identity lookup is title-first: put exact normalized title
                    # matches ahead of series/partial matches, and use creator
                    # and year only as stable tie-breakers. Never rank a title
                    # by synopsis relevance for this path.
                    remote.sort(key=lambda item: (
                        title_key(item.title) != title_key(phrase),
                        -len(phrase_terms & set(title_key(item.title).split())),
                        item.title.casefold(), item.year or 0, item.authors or "",
                    ))
                    exact_remote = [item for item in remote if title_key(item.title) == title_key(phrase)]
                    matches, approximate = (exact_remote or remote), False
                    self.title_directory.last_match_kind = "exact" if exact_remote else "partial"
                elif matches:
                    matches = [item for item in matches if item.media_type == "book"]
            elif remote:
                ids = {item.id for item in matches}
                matches.extend(item for item in remote if item.id not in ids)
                if not self.title_directory.last_match_kind or self.title_directory.last_match_kind == "none":
                    self.title_directory.last_match_kind = "partial"
        if not self.movie_source or requested == "book":
            return matches, approximate, explicit
        if matches:
            # Hydrate only unambiguous exact local movie identities. Keep the
            # local result if TMDB does not confirm the same title and year.
            if self.title_directory.last_match_kind == "exact" and not approximate:
                hydrated = []
                for item in matches:
                    if item.media_type != "movie" or item.source == "tmdb-api":
                        hydrated.append(item)
                        continue
                    remote = self.movie_source.search(item.title)
                    exact, _ = self.movie_source.identity_matches(item.title, remote)
                    exact = [candidate for candidate in exact if item.year is None or candidate.year is None or candidate.year == item.year]
                    if len(exact) == 1:
                        candidate = self.movie_source.details(exact[0])
                        self.title_directory.add_item(candidate)
                        hydrated.append(candidate)
                    else:
                        hydrated.append(item)
                return hydrated, approximate, explicit
            return matches, approximate, explicit
        if not explicit:
            return matches, approximate, explicit
        # The source is consulted only after the local identity directory fails
        # on a likely title. It never receives a general recommendation prompt.
        remote = self.movie_source.search(self.title_directory.last_entity)
        if not remote:
            return matches, approximate, explicit
        matched, approximate = self.movie_source.identity_matches(self.title_directory.last_entity, remote)
        if not matched:
            return matches, approximate, explicit
        if not approximate:
            matched = [self.movie_source.details(item) for item in matched]
        for item in remote:
            self.title_directory.add_item(item)
        for item in matched:
            self.title_directory.add_item(item)
        requested = self.title_directory.last_requested_media
        preferred = requested or {"books": "book", "movies": "movie"}.get(selection)
        if preferred:
            matched = [item for item in matched if item.media_type == preferred]
        if matched:
            self.title_directory.last_match_kind = "suggestion" if approximate else "exact"
        return matched, approximate, explicit

    def get_item(self, item_id):
        local = next((item for group in self.catalogs.values() for item in group if item.id == item_id), None) or self.title_directory.get(item_id)
        if local or not self.book_source or not str(item_id).startswith("book_bigbook_"):
            return local
        return self.book_source.details(str(item_id).removeprefix("book_bigbook_"))

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
        self.last_interpretation = {"status": "not_needed"}
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
            matches, approximate, explicit = self._lookup_title(text, [x for group in self.catalogs.values() for x in group], state.media_selection)
            if lookup_id:
                selected = self.get_item(lookup_id)
                matches, approximate, explicit = ([selected] if selected else []), False, True
                if selected:
                    self.title_directory.last_match_kind = "exact"
                    self.title_directory.last_entity = selected.title
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
                    if approximate:
                        explanation = "Possible title spelling match; choose the intended title."
                    elif self.last_title_match_kind == "partial":
                        explanation = "Matched part of a catalog title; choose the intended title."
                    elif item.source == "tmdb-api":
                        explanation = "Exact movie title verified with TMDB. Metadata is linked to its source."
                    else:
                        explanation = "Matched the catalog title directly."
                    if conflicts:
                        explanation += " Current recommendation filters: " + "; ".join(conflicts) + ". This is a title lookup, not a verified filtered recommendation."
                    if state.preferences.negative_content and not item.verified_warnings:
                        explanation += " Content suitability is unknown; no verified warning labels are available."
                    self.last_title_matches.append((item, explanation))
                if len(self.last_title_matches) > 1:
                    # Keep candidate ordering stable and identity-oriented when
                    # multiple editions, adaptations, or franchise titles match.
                    entity_key = title_key(self.title_directory.last_entity)
                    self.last_title_matches.sort(key=lambda row: (
                        title_key(row[0].title) != entity_key,
                        row[0].year is None,
                        row[0].year or 0,
                        (row[0].authors or row[0].director or "").casefold(),
                        row[0].id,
                    ))
                if not matches:
                    reply = f"That title is not in the local title directory under ‘{self.title_directory.last_entity}’. It may be missing or spelled differently. Try the full title, release year, or author. For a topic search, say ‘stories about …’. I have not substituted unrelated titles."
                elif approximate:
                    reply = "Did you mean one of these titles? Choose the intended match."
                elif self.last_title_match_kind == "partial":
                    reply = "I found several titles containing that phrase. Choose the intended title to see related stories."
                else:
                    reply = "Found the title in the catalog." if len(matches) == 1 else "Several titles match. Choose the intended title to see related stories."
                state.selected_reference_id = matches[0].id if len(matches) == 1 and self.last_title_match_kind == "exact" and not approximate else None
                return reply, {}
        search_query = text
        nemotron_failed = False
        if self.query_interpreter and parsed.intent not in {"reset", "help", "show_preferences", "explain", "more"}:
            interpreted = self.query_interpreter.interpret(text, state.media_selection, state.preferences)
            if interpreted:
                self.last_interpretation = {"status": "used", "purpose": "soft preference extraction and query expansion"}
                # Rules own explicit instructions and hard constraints. The LLM
                # supplies missing soft attributes and a short expansion only.
                if parsed.intent == "recommend" and interpreted.get("intent") in {"similar", "refine"}:
                    parsed.intent = interpreted["intent"]
                requested_media = interpreted.get("media_selection")
                if parsed.media_selection is None and not state.has_explicit_media and requested_media in {"books", "movies", "both"}:
                    parsed.media_selection = requested_media
                reference = interpreted.get("reference_title")
                if not parsed.reference_query and reference and title_key(reference) in title_key(text):
                    parsed.reference_query = reference
                    parsed.preferences.referenced_title = reference
                    parsed.explicit_fields.add("referenced_title")
                expansion = interpreted.get("search_query", "").strip()
                search_query = text + (" " + expansion if expansion else "")
                from .preferences import GENRES, MOODS
                for name, vocabulary in (("preferred_genres", GENRES), ("excluded_genres", GENRES), ("themes", None)):
                    if name in parsed.explicit_fields or "clear_" + name in parsed.explicit_fields:
                        continue
                    if name in {"preferred_genres", "excluded_genres"} and ("clear_genres" in parsed.explicit_fields or "replace_genres" in parsed.explicit_fields):
                        continue
                    values = [v.lower() for v in interpreted.get(name, []) if vocabulary is None or v.lower() in vocabulary]
                    if name == "preferred_genres":
                        values = [v for v in values if v not in parsed.preferences.excluded_genres + state.preferences.excluded_genres]
                    if name == "excluded_genres":
                        values = [v for v in values if v not in parsed.preferences.preferred_genres]
                    if values:
                        setattr(parsed.preferences, name, list(dict.fromkeys(values)))
                        parsed.explicit_fields.add(name)
                mood = interpreted.get("desired_mood")
                if mood in MOODS and not ({"desired_mood", "clear_desired_mood"} & parsed.explicit_fields):
                    parsed.preferences.desired_mood = mood
                    parsed.explicit_fields.add("desired_mood")
                # Numeric/year/language and content-safety constraints are never
                # added or replaced by unverified model output.
            else:
                nemotron_failed = True
                self.last_interpretation = {"status": "fallback", "reason": getattr(self.query_interpreter, "last_error_code", "unavailable")}
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
            exact, approximate, _ = self._lookup_title(parsed.reference_query, all_items, "both")
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
            summary = self._request_confirmation(state)
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
            results[domain] = self.indexes[domain].search(query, state.preferences, top_k=10, exclude_ids=exclude,seen_ids=set(state.seen_recommendations),topic_query=topic)
            local_diagnostics = dict(self.indexes[domain].last_diagnostics)
            if domain == "book" and self.book_source and self.book_source.configured:
                # Keep the live request bounded: one search plus at most six
                # detail lookups per recommendation turn.
                remote_items = self.book_source.search(query or topic or "books", number=12, details_limit=6)
                remote_recs = self.indexes[domain].rank_external(
                    query, remote_items, state.preferences, top_k=10, topic_query=topic,
                    exclude_ids=exclude | (set(state.seen_recommendations) if exclude_seen else set()),
                )
                remote_diagnostics = dict(getattr(self.indexes[domain], "last_external_diagnostics", {}))
                combined = {rec.item.id: rec for rec in results[domain]}
                combined.update({rec.item.id: rec for rec in remote_recs})
                deduplicated = {}
                for rec in sorted(combined.values(), key=lambda rec: (-rec.score, rec.item.id)):
                    identity = (rec.item.title.casefold().strip(), (rec.item.authors or "").casefold().strip())
                    deduplicated.setdefault(identity, rec)
                results[domain] = list(deduplicated.values())[:10]
                local_diagnostics["on_demand_source"] = "Big Book API, NLP-reranked; no remote records cached"
                local_diagnostics["on_demand_candidates"] = remote_diagnostics.get("candidate_count", 0)
                local_diagnostics["on_demand_eligible"] = remote_diagnostics.get("eligible_count", 0)
                local_diagnostics["on_demand_filter_rejections"] = remote_diagnostics.get("filter_rejections", {})
                local_diagnostics["on_demand_returned"] = len(remote_recs)
            self.last_diagnostics[domain]=local_diagnostics
            for rec in results[domain]:
                rec.explanation = explain_reference(rec, reference, state.preferences) if reference else explain(rec, search_query, state.preferences)
        state.last_recommendations = [r.item.id for group in results.values() for r in group]
        state.seen_recommendations=list(dict.fromkeys(state.seen_recommendations+state.last_recommendations))[-300:]
        return results

    def preference_summary(self, state: ConversationState) -> str:
        p = state.preferences
        return f"Active media: {state.media_selection}. Genres: {', '.join(p.preferred_genres) or 'none'}. Excluded: {', '.join(p.excluded_genres) or 'none'}. Mood: {p.desired_mood or 'none'}. Themes: {', '.join(p.themes) or 'none'}. Years: {p.min_year or 'any'}–{p.max_year or 'any'}. Book pages: {p.max_pages or 'any'}. Movie runtime: {p.max_runtime or 'any'} minutes."

    @staticmethod
    def _request_confirmation(state: ConversationState) -> str:
        """Echo active constraints in short, user-checkable language."""
        p = state.preferences
        parts = ["Books" if state.media_selection == "books" else "Movies" if state.media_selection == "movies" else "Books and movies"]
        parts.extend(p.preferred_genres)
        if p.desired_mood:
            parts.append(p.desired_mood)
        if p.themes:
            parts.extend(p.themes[:2])
        if p.max_pages and state.media_selection in {"books", "both"}:
            parts.append(f"up to {p.max_pages} pages")
        if p.max_runtime and state.media_selection in {"movies", "both"}:
            parts.append(f"up to {p.max_runtime} minutes")
        if p.min_year or p.max_year:
            parts.append(f"{p.min_year or 'any year'}–{p.max_year or 'present'}")
        if p.excluded_genres:
            parts.append("no " + ", no ".join(p.excluded_genres))
        if p.language:
            parts.append(p.language)
        return "Searching with: " + " · ".join(dict.fromkeys(parts)) + "."

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
