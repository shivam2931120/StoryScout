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
:root{--bg:#20242d;--surface:#272d38;--surface-hi:#2c3340;--ink:#f4f5fb;--muted:#abb4c4;--accent:#b5a8ff;--teal:#77d9ca;--shade:rgba(9,12,19,.72);--glow:rgba(83,96,119,.26);--lift:9px 9px 22px var(--shade),-7px -7px 18px var(--glow);--press:inset 5px 5px 12px rgba(9,12,19,.62),inset -5px -5px 12px rgba(83,96,119,.20);--well:inset 8px 8px 18px rgba(9,12,19,.72),inset -6px -6px 15px rgba(83,96,119,.18)}
html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"],[data-testid="stSidebar"],[data-testid="stBottom"]{background:var(--bg)!important;color:var(--ink)}
.stApp,[data-testid="stAppViewContainer"]{color:var(--ink);font-family:'DM Sans',Inter,ui-sans-serif,system-ui,sans-serif}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stSidebar"]>div:first-child{background:var(--bg);box-shadow:8px 0 28px rgba(8,11,17,.24);border-right:1px solid rgba(190,200,220,.055)}
[data-testid="stMainBlockContainer"]{max-width:1240px;padding:2rem 2.4rem 4rem}
h1,h2,h3,h4{color:var(--ink)!important;letter-spacing:-.035em;font-family:'Plus Jakarta Sans','DM Sans',Inter,ui-sans-serif,system-ui,sans-serif}
h2{font-size:1.55rem!important} h3{font-size:1.2rem!important}
p,label,li,[data-testid="stMarkdownContainer"]{color:var(--ink)}
small,.stCaption,[data-testid="stCaptionContainer"]{color:var(--muted)!important}
.hero{position:relative;overflow:hidden;padding:1.2rem 1.5rem;margin:.2rem 0 1rem;border-radius:24px;background:var(--surface);box-shadow:var(--lift);border:1px solid rgba(201,208,224,.055)}
.hero:after{content:'';position:absolute;right:4%;top:3%;width:85px;height:85px;opacity:.07;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 120' fill='none' stroke='%23b5a8ff' stroke-width='2'%3E%3Cpath d='M60 5 70 48l43 12-43 10-10 43-10-43L7 60l43-12L60 5Z'/%3E%3Ccircle cx='60' cy='60' r='19'/%3E%3C/svg%3E") center/contain no-repeat;pointer-events:none}
.hero-kicker{display:inline-flex;align-items:center;gap:.5rem;color:var(--teal);font-size:.72rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;margin-bottom:.65rem}.hero-kicker svg{width:16px;height:16px}
.hero h1{font-size:clamp(1.8rem,3vw,2.5rem);line-height:1.1;margin:0 0 .3rem;font-weight:800}
.hero p{margin:0;color:#c0c8d6;max-width:48rem;line-height:1.5;font-size:.95rem}
.eyebrow{color:var(--muted);font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin:1.2rem 0 .65rem}
.card{background:var(--surface);color:var(--ink);border:1px solid rgba(201,208,224,.055);border-radius:23px;padding:1.2rem 1.4rem;margin:.8rem 0;box-shadow:var(--lift);transition:transform 250ms ease,box-shadow 250ms ease}
.card:hover{transform:translateY(-2px);box-shadow:12px 12px 25px rgba(9,12,19,.78),-8px -8px 20px rgba(83,96,119,.29)}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem}.card h4{font-size:1.14rem;margin:.05rem 0 .65rem}.card p{line-height:1.65;margin:.75rem 0;color:#d3d8e2}
.card-meta{font-size:.82rem;color:var(--muted);margin-top:.6rem}.card-why{margin-top:.95rem;padding:.7rem .9rem;border-radius:14px;background:#242a34;box-shadow:var(--press);color:#c9c2ff;font-size:.87rem;line-height:1.55}
.tag{display:inline-flex;align-items:center;min-height:25px;background:#303746;color:#d6d0ff;padding:.19rem .62rem;border-radius:999px;margin:.12rem .18rem .22rem 0;font-size:.73rem;box-shadow:var(--press)}
.stButton>button{min-height:48px;border:1px solid rgba(201,208,224,.055);border-radius:16px;color:#e9eaf2;background:var(--surface);box-shadow:var(--lift);transition:transform 220ms ease,box-shadow 220ms ease,border-color 220ms ease;font-weight:600;line-height:1.35}
.stButton>button:hover{color:#fff;border-color:rgba(181,168,255,.4);transform:translateY(-2px);box-shadow:11px 11px 23px rgba(9,12,19,.75),-7px -7px 17px rgba(83,96,119,.27)}
.stButton>button:active{transform:translateY(1px);box-shadow:var(--press)}
a[data-testid="stLinkButton"]{display:inline-flex;align-items:center;min-height:38px;padding:0 .85rem;margin:.1rem 0 .3rem;border-radius:13px;background:#2b3140;color:#c8c0ff!important;text-decoration:none!important;box-shadow:var(--press);font-size:.82rem;font-weight:600}
a[data-testid="stLinkButton"]:hover{color:#fff!important;background:#33394a}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,[tabindex="0"]:focus-visible{outline:2px solid var(--accent)!important;outline-offset:3px!important}
[data-testid="stChatInput"] textarea,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{color:var(--ink)!important;background:var(--surface)!important;border:1px solid rgba(201,208,224,.07)!important;border-radius:17px!important;box-shadow:var(--well)!important;min-height:48px}
[data-testid="stChatInput"]{background:var(--surface)!important;border:1px solid rgba(201,208,224,.07)!important;border-radius:20px!important;box-shadow:var(--well)!important}
[data-testid="stChatMessage"]{background:var(--surface)!important;border:1px solid rgba(201,208,224,.055)!important;border-radius:22px!important;box-shadow:var(--lift);padding:1rem 1.2rem!important;margin:.75rem 0!important}
[data-testid="stChatMessage"] p{line-height:1.65}
[data-testid="stAlert"]{background:var(--surface)!important;color:var(--ink)!important;border:1px solid rgba(201,208,224,.06)!important;border-radius:18px!important;box-shadow:var(--press)}
[data-baseweb="tab-list"]{gap:.65rem;border-bottom:1px solid rgba(180,190,210,.1);padding-bottom:.35rem}
[data-baseweb="tab"]{min-height:45px;color:var(--muted);background:transparent;border-radius:13px;padding:0 1rem;font-weight:600}
[aria-selected="true"][data-baseweb="tab"]{color:var(--accent)!important;background:#292e3a!important;box-shadow:var(--press)}
[data-testid="stRadio"] label,[data-testid="stSelectbox"] label{color:var(--ink)!important}
[data-baseweb="select"]>div{color:var(--ink);background:var(--surface);border:1px solid rgba(201,208,224,.07);border-radius:14px;box-shadow:var(--press);min-height:46px}
[data-testid="stSidebar"] h2{font-size:1.1rem!important;margin-top:.4rem}
.side-brand{display:flex;align-items:center;gap:.75rem;margin:.5rem 0 1.3rem;padding:.8rem .7rem;border-radius:18px;background:var(--surface);box-shadow:var(--lift)}
.side-mark{display:grid;place-items:center;width:42px;height:42px;border-radius:14px;background:#302e43;box-shadow:var(--press)}.side-mark svg{width:24px;height:24px}
.side-name{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:1.06rem;letter-spacing:-.03em}.side-note{font-size:.72rem;color:var(--muted);margin-top:.1rem}
.section-title{font-family:'Plus Jakarta Sans',sans-serif;font-size:1.5rem;font-weight:700;letter-spacing:-.04em;margin:1.35rem 0 .2rem}.group-title{display:flex;align-items:center;gap:.65rem;margin:1.4rem 0 .7rem;font:700 1.12rem 'Plus Jakarta Sans',sans-serif}.group-icon{display:grid;place-items:center;width:34px;height:34px;border-radius:12px;background:#302e43;box-shadow:var(--press)}.group-icon svg{width:18px;height:18px;stroke:var(--accent)}
.status-line{display:inline-flex;align-items:center;gap:.45rem;color:var(--teal);font-size:.77rem;font-weight:600}
hr{border-color:rgba(177,186,200,.12)}
@media(max-width:768px){[data-testid="stMainBlockContainer"]{padding:1.15rem .9rem 3rem}.hero{padding:1.45rem;border-radius:23px}.hero:after{font-size:6rem;right:3%}.card{padding:1rem;border-radius:19px}.card-top{display:block}[data-testid="stHorizontalBlock"]{gap:.55rem}.stButton>button{font-size:.82rem}}
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

with st.sidebar:
    book_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20M8 7h8M8 10h6"/></svg>'
    st.markdown(f'<div class="side-brand"><div class="side-mark">{book_svg}</div><div><div class="side-name">StoryScout</div></div></div>', unsafe_allow_html=True)
    mode = "hybrid"
    selection = st.radio("Show", ["books", "movies", "both"], format_func=lambda x: {"books":"Books","movies":"Movies","both":"Both"}[x], key="media_choice", on_change=update_media_from_widget)
    if st.button("Reset", use_container_width=True):
        st.session_state.state = ConversationState(); st.session_state.chat = []; st.session_state.last_results = {}; st.session_state.pending_media_choice = "both"; st.session_state.pending_filter_values = preference_widget_values(st.session_state.state.preferences); st.rerun()
    st.divider()

api_key = configured_api_key(st.secrets)
catalog_paths = [DEMO_FILES["book"], DEMO_FILES["movie"], ROOT / "data/expanded/books.csv", ROOT / "data/expanded/movies.csv", ROOT / "data/enriched/descriptions.csv"]
catalog_version = tuple((path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else (0, 0) for path in catalog_paths)
engine, catalogs = load_engine(mode, api_key, catalog_version)
st.session_state.state.retrieval_mode = mode
spark_svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m12 2 2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4L12 2Z"/></svg>'
st.markdown('<div class="hero"><h1>StoryScout</h1></div>', unsafe_allow_html=True)

tab_chat, tab_nlp, tab_eval, tab_data = st.tabs(["Discover", "NLP pipeline", "Evaluation", "Dataset"])
with tab_chat:
    examples = ["A short mystery book", "An uplifting movie under two hours", "A book like Interstellar"]
    cols = st.columns(len(examples))
    for i, example in enumerate(examples):
        if cols[i % 3].button(example, key=f"ex{i}", use_container_width=True): st.session_state.pending_prompt = example
    for message in st.session_state.chat:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    prompt = st.chat_input("What would you like to read or watch?")
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
    with st.expander("Preferences", expanded=False):
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
        st.markdown("### Latest recommendations")
        for domain, recs in st.session_state.last_results.items():
            kind_label = "Books" if domain == "book" else "Movies"
            st.markdown(f'<div class="group-title"><span class="group-icon">{book_svg if domain == "book" else spark_svg}</span>{kind_label}</div>', unsafe_allow_html=True)
            for rec in recs:
                item = rec.item
                length = f"{item.page_count} pages" if item.page_count else (f"{item.runtime_minutes} min" if item.runtime_minutes else None)
                creator = item.authors or item.director
                metadata = [value for value in [creator, str(item.year) if item.year else None, length] if value]
                display_tags = item.genres or item.theme_tags[:3]
                prefix = "" if item.genres else "Subject · "
                tags = " ".join(f'<span class="tag">{escape(prefix + g[:48])}</span>' for g in display_tags)
                if item.description_provenance:
                    tags += f'<span class="tag">AI summary · {escape(item.description_source.split(" (")[0])}</span>'
                description = item.description
                if item.source.startswith(("movielens", "project-gutenberg")) and not item.description_provenance:
                    description = ""
                meta_line = " &nbsp;·&nbsp; ".join(escape(value) for value in metadata)
                description_html = f"<p>{escape(description)}</p>" if description else ""
                meta_html = f'<div class="card-meta">{meta_line}</div>' if meta_line else ""
                st.markdown(f'<div class="card"><div class="card-top"><h4>{escape(item.title)}</h4></div>{tags}{description_html}{meta_html}<div class="card-why">{escape(rec.explanation)}</div></div>', unsafe_allow_html=True)
                if item.source_url.startswith(("https://", "http://")):
                    st.link_button("View source", item.source_url, key=f"source_{item.id}")
                if item.description_source_url.startswith(("https://", "http://")):
                    st.link_button("Summary source", item.description_source_url, key=f"summary_source_{item.id}")
with tab_nlp:
    st.markdown("""### How the pipeline works
1. A transparent rule baseline detects intent and explicit media.
2. Typed preference extraction handles genres, negation, mood, themes, language, years, pages, and runtime.
3. Hard filters are applied before ranking; unknown values cannot pass explicit constraints.
4. TF-IDF provides lexical similarity. Sentence-transformers provides shared semantic vectors when available. Hybrid scores use 45% lexical + 55% semantic after cosine calibration.
5. Results are explained only with catalog genres, tags, metadata, and similarity evidence.

The system is not an LLM, collaborative filter, rating predictor, or adaptation detector.
""")
with tab_eval:
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
with tab_data:
    st.markdown(f"**{catalog_status(catalogs['book'] + catalogs['movie'])}** · {len(catalogs['book']):,} books · {len(catalogs['movie']):,} movies")
    for domain, items in catalogs.items():
        source_counts = {}
        for item in items:
            source_counts[item.source] = source_counts.get(item.source, 0) + 1
        st.caption(("Books" if domain == "book" else "Movies") + " sources: " + " · ".join(f"{source}: {count:,}" for source, count in sorted(source_counts.items())))
    st.markdown("Source metadata, catalog subjects, and demo descriptions retain separate provenance. Unknown fields remain unknown. See `docs/DATA_SOURCES.md` for schemas, usage terms, import steps, and limitations.")
