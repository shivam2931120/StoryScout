from __future__ import annotations
import sys
from html import escape
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.config import DEMO_FILES
from src.data_loader import load_active_catalogs, catalog_status
from src.schemas import ConversationState
from src.retrieval import RetrievalIndex
from src.conversation import StoryScoutEngine
from src.llm_interpreter import NemotronQueryInterpreter, configured_api_key
from src.preferences import GENRES
from src.human_evaluation import create_judgment_template, score_human_judgments

st.set_page_config(page_title="StoryScout", page_icon=str(ROOT / "assets" / "storyscout.svg"), layout="wide")
st.markdown("""<style>
:root{--canvas:#111315;--rail:#15181b;--surface:#1b1f23;--surface-2:#22272c;--surface-3:#292f35;--line:#252a2f;--line-strong:#30363d;--ink:#f0eee8;--muted:#a5adb5;--quiet:#7c858e;--teal:#79b8aa;--teal-hover:#65a395;--amber:#e5c07b;--danger:#e06c75}
html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stBottom"]{background:var(--canvas)!important;color:var(--ink)}
.stApp,[data-testid="stAppViewContainer"]{color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,sans-serif}
[data-testid="stHeader"]{background:transparent!important}
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color-scheme:dark}
[data-testid="stSidebar"]>div:first-child{background:var(--rail);border-right:1px solid var(--line)}
[data-testid="stMainBlockContainer"]{max-width:1320px;padding:1.5rem 2.2rem 5rem}
h1,h2,h3,h4{color:var(--ink)!important;letter-spacing:-.035em;font-family:Inter,ui-sans-serif,system-ui,sans-serif}
h1{font-weight:600!important}h2{font-size:1.45rem!important}h3{font-size:1.15rem!important}
p,label,li,[data-testid="stMarkdownContainer"]{color:var(--ink)}small,.stCaption,[data-testid="stCaptionContainer"]{color:var(--muted)!important}
.hero{position:relative;overflow:hidden;padding:2.4rem 1.5rem 1.8rem;margin:.5rem 0 1.2rem;text-align:center;border-radius:8px;background:transparent}
.hero-kicker{display:inline-flex;align-items:center;gap:.5rem;color:var(--teal);font-size:.7rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;margin-bottom:.8rem}.hero h1{font-size:clamp(1.9rem,4vw,2.5rem);line-height:1.15;margin:0 0 .5rem;font-weight:600}.hero p{margin:0 auto;color:var(--muted);max-width:42rem;line-height:1.65;font-size:.95rem}
.eyebrow{color:var(--quiet);font-size:.72rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;margin:1.1rem 0 .6rem}
.story-card{height:100%;min-height:275px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:1rem;transition:background .18s ease,border-color .18s ease;}
.story-card:hover{background:var(--surface-2);border-color:var(--line-strong)}
.story-cover{height:82px;display:flex;align-items:center;justify-content:center;margin:-1rem -1rem .9rem;background:linear-gradient(145deg,#253238,#171b1e);border-bottom:1px solid var(--line);color:var(--teal)}.story-cover.movie{background:linear-gradient(145deg,#34302a,#1b1d1e);color:var(--amber)}.story-cover svg{width:36px;height:36px}
.story-title{font-size:1.06rem;font-weight:600;line-height:1.35;margin:.2rem 0}.story-meta{font-size:.75rem;color:var(--muted);line-height:1.5;margin:.35rem 0}.story-desc{font-size:.83rem;line-height:1.55;color:var(--muted);margin:.65rem 0}.story-why{font-size:.8rem;line-height:1.5;color:#c4d9d3;background:rgba(121,184,170,.08);padding:.65rem .75rem;border-radius:5px;margin-top:.65rem}.chip{display:inline-flex;padding:.22rem .55rem;border-radius:999px;background:rgba(121,184,170,.1);color:var(--teal);font-size:.68rem;margin:.1rem .15rem .1rem 0}.story-head{display:flex;align-items:center;justify-content:space-between;gap:.5rem}.story-label{font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--quiet)}
.stButton>button{min-height:40px;border:1px solid var(--line-strong);border-radius:5px;color:var(--ink);background:var(--surface);box-shadow:none;transition:background .15s ease,border-color .15s ease;font-weight:500;line-height:1.35}
.stButton>button:hover{color:var(--ink);border-color:var(--teal);background:var(--surface-2)}.stButton>button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,[tabindex="0"]:focus-visible{outline:2px solid var(--teal)!important;outline-offset:2px!important}
a[data-testid="stLinkButton"]{display:inline-flex;align-items:center;min-height:36px;padding:0 .7rem;margin:.1rem 0 .25rem;border-radius:5px;background:var(--surface-2);color:var(--teal)!important;text-decoration:none!important;font-size:.8rem;font-weight:500}
[data-testid="stChatInput"] textarea,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{color:var(--ink)!important;background:var(--surface)!important;border:1px solid var(--line-strong)!important;border-radius:6px!important;min-height:44px}
[data-testid="stChatInput"]{background:var(--surface)!important;border:1px solid var(--line-strong)!important;border-radius:7px!important;box-shadow:0 8px 32px rgba(0,0,0,.25)!important}
[data-testid="stChatMessage"]{background:var(--surface)!important;border:1px solid var(--line)!important;border-radius:7px!important;box-shadow:none;padding:.85rem 1rem!important;margin:.6rem 0!important}
[data-testid="stChatMessage"] p{line-height:1.6}
[data-testid="stAlert"]{background:var(--surface)!important;color:var(--ink)!important;border:1px solid var(--line-strong)!important;border-radius:6px!important;box-shadow:none}
[data-baseweb="tab-list"]{gap:.4rem;border-bottom:1px solid var(--line);padding-bottom:.35rem}[data-baseweb="tab"]{min-height:42px;color:var(--muted);background:transparent;border-radius:4px;padding:0 .8rem;font-weight:500}[aria-selected="true"][data-baseweb="tab"]{color:var(--teal)!important;background:var(--surface-2)!important}
[data-testid="stRadio"] label,[data-testid="stSelectbox"] label{color:var(--ink)!important}[data-baseweb="select"]>div{color:var(--ink);background:var(--surface);border:1px solid var(--line-strong);border-radius:5px;min-height:42px}
[data-testid="stSidebar"] h2{font-size:1rem!important;margin-top:.3rem}.side-brand{display:flex;align-items:center;gap:.7rem;margin:.4rem 0 1rem;padding:.45rem .35rem}.side-mark{display:grid;place-items:center;width:36px;height:36px;border-radius:5px;background:var(--surface-2);color:var(--teal)}.side-mark svg{width:21px;height:21px}.side-name{font-weight:600;font-size:1rem;letter-spacing:-.02em}.side-note{font-size:.72rem;color:var(--muted);margin-top:.12rem}
.section-title{font-size:1.35rem;font-weight:600;letter-spacing:-.03em;margin:1.5rem 0 .2rem}.group-title{display:flex;align-items:center;gap:.55rem;margin:1.2rem 0 .65rem;font-weight:600;font-size:1.05rem}.group-icon{display:grid;place-items:center;width:28px;height:28px;border-radius:5px;background:var(--surface-2);color:var(--teal)}.group-icon svg{width:17px;height:17px}
.status-line{display:inline-flex;align-items:center;gap:.4rem;color:var(--teal);font-size:.75rem;font-weight:500}hr{border-color:var(--line)}
@media(max-width:768px){[data-testid="stMainBlockContainer"]{padding:1rem .85rem 4rem}.hero{padding:1.5rem .4rem}.story-card{min-height:0}.story-cover{height:66px}[data-testid="stHorizontalBlock"]{gap:.55rem}.stButton>button{font-size:.82rem}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{transition:none!important;scroll-behavior:auto!important}}
</style>""", unsafe_allow_html=True)

@st.cache_resource(show_spinner="Preparing local search indexes…")
def load_engine(mode: str, api_key: str | None, catalog_version: tuple):
    catalogs = load_active_catalogs()
    indexes = {domain: RetrievalIndex(items, mode=mode) for domain, items in catalogs.items()}
    interpreter = NemotronQueryInterpreter(api_key) if api_key else None
    return StoryScoutEngine(catalogs, indexes, mode, query_interpreter=interpreter), catalogs

if "state" not in st.session_state: st.session_state.state = ConversationState()
if "chat" not in st.session_state: st.session_state.chat = []
if "saved_story_ids" not in st.session_state: st.session_state.saved_story_ids = []

def update_media_from_widget() -> None:
    st.session_state.state.media_selection = st.session_state.media_choice
    st.session_state.state.has_explicit_media = True

def update_preferences_from_widgets() -> None:
    preferences = st.session_state.state.preferences
    preferences.preferred_genres = list(st.session_state.get("filter_preferred_genres", []))
    preferences.excluded_genres = list(st.session_state.get("filter_excluded_genres", []))
    preferences.max_pages = st.session_state.get("filter_max_pages", 0) or None
    preferences.max_runtime = st.session_state.get("filter_max_runtime", 0) or None
    preferences.min_year = st.session_state.get("filter_min_year", 0) or None
    preferences.max_year = st.session_state.get("filter_max_year", 0) or None
    contradictions = []
    overlap = set(preferences.preferred_genres) & set(preferences.excluded_genres)
    if overlap:
        contradictions.append("A genre cannot be both preferred and excluded: " + ", ".join(sorted(overlap)))
    if preferences.min_year and preferences.max_year and preferences.min_year > preferences.max_year:
        contradictions.append("The start year must be earlier than the end year.")
    preferences.contradiction_messages = contradictions

def preference_widget_values(preferences) -> dict:
    return {
        "filter_preferred_genres": list(preferences.preferred_genres),
        "filter_excluded_genres": list(preferences.excluded_genres),
        "filter_max_pages": preferences.max_pages or 0,
        "filter_max_runtime": preferences.max_runtime or 0,
        "filter_min_year": preferences.min_year or 0,
        "filter_max_year": preferences.max_year or 0,
    }

def preference_changes(before, after, old_media: str) -> list[str]:
    changes = []
    media_names = {"books": "Books", "movies": "Movies", "both": "Books + movies"}
    if old_media != st.session_state.state.media_selection:
        changes.append("Showing " + media_names[st.session_state.state.media_selection])
    list_fields = (("preferred_genres", "Genres"), ("excluded_genres", "Excluded"), ("themes", "Themes"))
    for field, label in list_fields:
        old, new = set(getattr(before, field)), set(getattr(after, field))
        if new - old: changes.append(f"{label}: " + ", ".join(sorted(new - old)))
        if old - new: changes.append(f"Removed {label.lower()}: " + ", ".join(sorted(old - new)))
    scalar_fields = (("desired_mood", "Mood"), ("language", "Language"), ("min_year", "From"), ("max_year", "Through"), ("max_pages", "Book limit"), ("max_runtime", "Movie limit"))
    for field, label in scalar_fields:
        old, new = getattr(before, field), getattr(after, field)
        if old != new and new is not None:
            unit = " pages" if field == "max_pages" else (" min" if field == "max_runtime" else "")
            changes.append(f"{label}: {new}{unit}")
        elif old is not None and new is None:
            changes.append(f"Cleared {label.lower()}")
    if before.referenced_title != after.referenced_title and after.referenced_title:
        changes.append("Similar to " + after.referenced_title)
    return changes

if "pending_media_choice" in st.session_state:
    st.session_state.media_choice = st.session_state.pop("pending_media_choice")
if "pending_filter_values" in st.session_state:
    for key, value in st.session_state.pop("pending_filter_values").items():
        st.session_state[key] = value
if "media_choice" not in st.session_state:
    st.session_state.media_choice = st.session_state.state.media_selection
for key, value in preference_widget_values(st.session_state.state.preferences).items():
    if key not in st.session_state:
        st.session_state[key] = value

book_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20M8 7h8M8 10h6"/></svg>'
movie_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m10 9 5 3-5 3V9ZM3 9h3m-3 6h3m12-6h3m-3 6h3"/></svg>'
bookmark_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 4.8A1.8 1.8 0 0 1 7.8 3h8.4A1.8 1.8 0 0 1 18 4.8V21l-6-4-6 4V4.8Z"/></svg>'
mode = "hybrid"
with st.sidebar:
    st.markdown(f'<div class="side-brand"><div class="side-mark">{book_svg}</div><div><div class="side-name">StoryScout</div><div class="side-note">Books and films, thoughtfully found</div></div></div>', unsafe_allow_html=True)
    if st.button("＋  New discovery", use_container_width=True, key="new_discovery"):
        st.session_state.state = ConversationState()
        st.session_state.chat = []
        st.session_state.last_results = {}
        st.session_state.pop("last_user_query", None)
        st.session_state.page_choice = "Discover"
        st.session_state.pending_media_choice = "both"
        st.session_state.pending_filter_values = preference_widget_values(st.session_state.state.preferences)
        st.rerun()
    st.radio("Library", ["Discover", "Saved stories", "NLP pipeline", "Evaluation", "Dataset"], key="page_choice", label_visibility="collapsed")
    st.caption(f"{len(st.session_state.saved_story_ids)} saved")
    st.divider()

api_key = configured_api_key(st.secrets)
catalog_paths = [DEMO_FILES["book"], DEMO_FILES["movie"], ROOT / "data/expanded/books.csv", ROOT / "data/expanded/movies.csv", ROOT / "data/enriched/descriptions.csv"]
catalog_version = tuple((path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else (0, 0) for path in catalog_paths)
engine, catalogs = load_engine(mode, api_key, catalog_version)
st.session_state.state.retrieval_mode = mode
spark_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m12 2 2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4L12 2Z"/></svg>'

page = st.session_state.page_choice
if page == "Discover":
    top_title, top_media = st.columns([2.1, 1.2], vertical_alignment="center")
    with top_title:
        st.markdown('<div class="story-label">StoryScout / Discovery</div><h3 style="margin:.2rem 0">Find your next story</h3>', unsafe_allow_html=True)
    with top_media:
        st.radio("Media format", ["both", "books", "movies"], format_func=lambda x: {"both":"All stories","books":"Books","movies":"Movies"}[x], key="media_choice", on_change=update_media_from_widget, horizontal=True, label_visibility="collapsed")
    if not st.session_state.chat:
        st.markdown('<div class="hero"><div class="hero-kicker">Your next favorite story</div><h1>What kind of story are you looking for?</h1><p>Describe a mood, a theme, or something you already love.</p></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="story-label" style="margin:1rem 0">Your conversation</div>', unsafe_allow_html=True)
    examples = ["A short mystery with a surprising twist", "An uplifting movie under two hours", "Books with the atmosphere of Interstellar", "Something comforting to read or watch"]
    if not st.session_state.chat:
        st.markdown('<div class="eyebrow">A few ways to begin</div>', unsafe_allow_html=True)
        cols = st.columns(2)
        for i, example in enumerate(examples):
            if cols[i % 2].button(example, key=f"ex{i}", use_container_width=True): st.session_state.pending_prompt = example
    for message in st.session_state.chat:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    prompt = st.chat_input("Refine your search or ask for a different story…")
    prompt = prompt or st.session_state.pop("pending_prompt", None)
    if prompt:
        preferences_before = st.session_state.state.preferences.clone()
        media_before = st.session_state.state.media_selection
        with st.spinner("Searching…"):
            reply, results = engine.handle(prompt, st.session_state.state)
        changes = preference_changes(preferences_before, st.session_state.state.preferences, media_before)
        if "reset" in prompt.lower() and st.session_state.state.preferences == st.session_state.state.preferences.__class__():
            changes = ["Preferences cleared"]
        if changes:
            reply += "\n\nUpdated: " + " · ".join(changes)
        if st.session_state.state.media_selection != st.session_state.media_choice:
            st.session_state.pending_media_choice = st.session_state.state.media_selection
        st.session_state.pending_filter_values = preference_widget_values(st.session_state.state.preferences)
        st.session_state.last_user_query = prompt
        st.session_state.chat.append({"role":"user","content":prompt}); st.session_state.chat.append({"role":"assistant","content":reply})
        st.session_state.last_results = results
        st.rerun()
    with st.expander("Discovery preferences", expanded=False):
        left, right = st.columns(2)
        left.multiselect("Prefer genres", GENRES, key="filter_preferred_genres", on_change=update_preferences_from_widgets)
        right.multiselect("Exclude genres", GENRES, key="filter_excluded_genres", on_change=update_preferences_from_widgets)
        book_filter, movie_filter = st.columns(2)
        book_filter.number_input("Max book pages", min_value=0, max_value=10000, step=10, key="filter_max_pages", on_change=update_preferences_from_widgets)
        movie_filter.number_input("Max movie minutes", min_value=0, max_value=1000, step=5, key="filter_max_runtime", on_change=update_preferences_from_widgets)
        year_from, year_to = st.columns(2)
        year_from.number_input("From year", min_value=0, max_value=2100, step=1, key="filter_min_year", on_change=update_preferences_from_widgets)
        year_to.number_input("To year", min_value=0, max_value=2100, step=1, key="filter_max_year", on_change=update_preferences_from_widgets)
        if st.session_state.state.preferences.contradiction_messages: st.warning("; ".join(st.session_state.state.preferences.contradiction_messages))
    if st.session_state.get("last_results"):
        st.markdown('<div class="section-title">Stories to explore</div><div class="story-meta">Grouped by format · selected for your request</div>', unsafe_allow_html=True)
        for domain, recs in st.session_state.last_results.items():
            kind_label = "Books" if domain == "book" else "Movies"
            st.markdown(f'<div class="group-title"><span class="group-icon">{book_svg if domain == "book" else movie_svg}</span>{kind_label}<span class="story-label">{len(recs)} recommendations</span></div>', unsafe_allow_html=True)
            grid = st.columns(3)
            for index, rec in enumerate(recs):
                item = rec.item
                saved = item.id in st.session_state.saved_story_ids
                creator = item.authors or item.director
                length = f"{item.page_count} pages" if item.page_count else (f"{item.runtime_minutes} min" if item.runtime_minutes else None)
                metadata = " · ".join(escape(value) for value in [creator, str(item.year) if item.year else None, length] if value)
                description = item.description
                if item.source.startswith(("movielens", "project-gutenberg")) and not item.description_provenance:
                    description = ""
                genre = " · ".join(item.genres[:2]) if item.genres else "Story"
                icon = book_svg if domain == "book" else movie_svg
                source_label = escape(item.description_source.split(" (")[0]) if item.description_provenance else ""
                with grid[index % len(grid)]:
                    st.markdown(f'<article class="story-card"><div class="story-cover {"movie" if domain == "movie" else "book"}">{icon}</div><div class="story-head"><span class="story-label">{kind_label[:-1] if kind_label.endswith("s") else kind_label}</span><span class="chip">{escape(genre)}</span></div><div class="story-title">{escape(item.title)}</div><div class="story-meta">{metadata or "Details unavailable"}</div>{f"<p class=\"story-desc\">{escape(description[:320])}</p>" if description else ""}<div class="story-why">{escape(rec.explanation)}</div>{f"<div class=\"story-label\" style=\"margin-top:.55rem\">Summary: {source_label}</div>" if source_label else ""}</article>', unsafe_allow_html=True)
                    save_col, details_col = st.columns([1, 1])
                    if save_col.button("Saved" if saved else "Save", key=f"save_{item.id}", use_container_width=True):
                        if saved: st.session_state.saved_story_ids.remove(item.id)
                        else: st.session_state.saved_story_ids.append(item.id)
                        st.rerun()
                    with details_col.popover("Details", use_container_width=True):
                        st.markdown(f"**{escape(item.title)}**")
                        st.write(description or "No sourced description is available for this catalog item.")
                        if metadata: st.caption(metadata)
                        if item.source_url.startswith(("https://", "http://")): st.link_button("Catalog source", item.source_url, key=f"source_{item.id}")
                        if item.description_source_url.startswith(("https://", "http://")): st.link_button("Description source", item.description_source_url, key=f"summary_source_{item.id}")
                        target_media = "movies" if domain == "book" else "books"
                        if st.button(f"Find {target_media} with similar themes", key=f"cross_{item.id}", use_container_width=True):
                            st.session_state.pending_prompt = f'I liked "{item.title}". Recommend {"a movie" if domain == "book" else "a book"} with similar themes.'
                            st.session_state.media_choice = target_media
                            st.session_state.state.media_selection = target_media
                            st.session_state.state.has_explicit_media = True
                            st.rerun()
                    st.write("")
elif page == "Saved stories":
    st.markdown('<div class="story-label">Your library</div><h2>Saved stories</h2>', unsafe_allow_html=True)
    saved = set(st.session_state.saved_story_ids)
    saved_items = [item for items in catalogs.values() for item in items if item.id in saved]
    if not saved_items:
        st.info("Stories you save from recommendations will appear here.")
    else:
        search_saved = st.text_input("Search saved stories", placeholder="Title, author, or theme")
        filtered = [x for x in saved_items if search_saved.lower() in (x.title + " " + str(x.authors or x.director or "") + " " + " ".join(x.theme_tags)).lower()]
        grid = st.columns(3)
        for i, item in enumerate(filtered):
            kind = "Book" if item.media_type == "book" else "Movie"
            creator = item.authors or item.director
            meta = " · ".join(str(v) for v in [creator, item.year, f"{item.page_count} pages" if item.page_count else (f"{item.runtime_minutes} min" if item.runtime_minutes else None)] if v)
            with grid[i % len(grid)]:
                st.markdown(f'<article class="story-card"><div class="story-cover {item.media_type}">{book_svg if item.media_type == "book" else movie_svg}</div><div class="story-label">{kind}</div><div class="story-title">{escape(item.title)}</div><div class="story-meta">{escape(meta) or "Details unavailable"}</div><p class="story-desc">{escape(item.description[:300]) if item.description_provenance else "No sourced description available."}</p></article>', unsafe_allow_html=True)
                if st.button("Remove from saved", key=f"unsave_{item.id}", use_container_width=True):
                    st.session_state.saved_story_ids.remove(item.id); st.rerun()
elif page == "NLP pipeline":
    st.markdown("""### How the pipeline works
1. A transparent rule baseline detects intent and explicit media.
2. Typed preference extraction handles genres, negation, mood, themes, language, years, pages, and runtime.
3. Hard filters are applied before ranking; unknown values cannot pass explicit constraints.
4. TF-IDF provides lexical similarity. Sentence-transformers provides shared semantic vectors when available. Hybrid scores use 45% lexical + 55% semantic after cosine calibration.
5. Results are explained only with catalog genres, tags, metadata, and similarity evidence.

The system is not an LLM, collaborative filter, rating predictor, or adaptation detector.
""")
elif page == "Evaluation":
    eval_file = ROOT / "artifacts/evaluation_summary.md"
    st.markdown(eval_file.read_text() if eval_file.exists() else "Evaluation has not been run yet. Run `python scripts/evaluate.py`.")
    st.markdown("#### Add human relevance judgments")
    result_file = ROOT / "artifacts/evaluation_query_results.csv"
    if result_file.exists():
        import pandas as pd
        evaluated = pd.read_csv(result_file, keep_default_na=False)
        title_by_id = {item.id: item.title for domain_items in catalogs.values() for item in domain_items}
        template = create_judgment_template(evaluated, title_by_id)
        st.caption("Download the retrieved items, then rate each one: 0 = not relevant, 1 = partly relevant, 2 = clearly relevant. Leave only genuinely unreviewed items blank. The benchmark labels above remain developer-authored.")
        st.download_button("Download judgment sheet", template.to_csv(index=False).encode("utf-8"), "storyscout_human_judgments.csv", "text/csv")
        upload = st.file_uploader("Upload a completed judgment sheet", type=["csv"], key="human_judgment_upload")
        if upload is not None:
            judged = pd.read_csv(upload, keep_default_na=False)
            try:
                human, rating_count = score_human_judgments(judged)
                if not rating_count:
                    st.info("No human ratings have been entered yet.")
                else:
                    st.caption(f"Scored {rating_count} human ratings across {len(human)} query/domain/model groups. Unrated items are excluded; these are judged-item precision and reciprocal-rank summaries, with catalog coverage incomplete.")
                    st.dataframe(human.groupby(["mode", "domain"])[["judged_precision", "judged_mrr"]].mean().round(3), use_container_width=True)
                    st.download_button("Download human evaluation summary", human.to_csv(index=False).encode("utf-8"), "storyscout_human_evaluation.csv", "text/csv")
            except ValueError as error:
                st.error(str(error))
    else:
        st.info("Run `python scripts/evaluate.py` to generate recommendations for annotation.")
    classifier_file = ROOT / "artifacts/genre_classifier_results.json"
    if classifier_file.exists():
        import json
        with st.expander("Genre classification experiment"):
            classifier_results = json.loads(classifier_file.read_text())
            for domain, result in classifier_results.items():
                st.markdown(f"**{domain.title()}:** {result['status']}")
                if result["status"] == "measured":
                    st.caption(f"Held-out micro F1 {result['micro_avg']['f1-score']:.3f}; macro F1 {result['macro_avg']['f1-score']:.3f}. Title-only TF-IDF, fixed split. This classifier is an experiment and does not assign catalog genres.")
                else:
                    st.caption(result.get("reason", "No supported experiment."))
elif page == "Dataset":
    st.markdown(f"**{catalog_status(catalogs['book'] + catalogs['movie'])}** · {len(catalogs['book']):,} books · {len(catalogs['movie']):,} movies")
    for domain, items in catalogs.items():
        source_counts = {}
        for item in items:
            source_counts[item.source] = source_counts.get(item.source, 0) + 1
        st.caption(("Books" if domain == "book" else "Movies") + " sources: " + " · ".join(f"{source}: {count:,}" for source, count in sorted(source_counts.items())))
    st.markdown("Source metadata, catalog subjects, and demo descriptions retain separate provenance. Unknown fields remain unknown. See `docs/DATA_SOURCES.md` for schemas, usage terms, import steps, and limitations.")
