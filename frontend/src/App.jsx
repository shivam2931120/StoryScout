import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Bookmark,
  Brain,
  Check,
  ChevronRight,
  Compass,
  Download,
  Film,
  FolderOpen,
  Heart,
  LoaderCircle,
  Menu,
  MessageSquare,
  Orbit,
  Plus,
  RotateCcw,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import PreferencesDrawer from "./PreferencesDrawer.jsx";
import { PipelinePage, EvaluationPage } from "./InformationPages.jsx";
import {
  request,
  emptyPreferences,
  emptyState,
  newConversation,
  label,
  preferenceChips,
} from "./api.js";
import {
  Brand,
  Composer,
  Cover,
  DetailDrawer,
  Drawer,
  MediaTabs,
  StoryCard,
} from "./components.jsx";

const examples = [
  {
    icon: BookOpen,
    text: "A short mystery with a surprising twist",
    query: "Suggest a short mystery book with an unexpected ending.",
  },
  {
    icon: Film,
    text: "An uplifting movie under two hours",
    query: "Recommend an uplifting movie under two hours.",
  },
  {
    icon: Orbit,
    text: "Books with the atmosphere of Interstellar",
    query: "I enjoyed Interstellar. Recommend a book with similar themes.",
  },
  {
    icon: Heart,
    text: "Something comforting to read or watch",
    query: "I feel stressed. Suggest something comforting to read or watch.",
  },
];
const storageKey = "storyscout.library.v2";
function readLibrary() {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey));
    if (
      stored &&
      Array.isArray(stored.conversations) &&
      stored.conversations.length > 0 &&
      stored.conversations.every(
        (x) => x.id && x.state?.preferences && Array.isArray(x.turns),
      ) &&
      Array.isArray(stored.saved)
    )
      return stored;
  } catch {
    /* Fresh or unavailable browser storage. */
  }
  const initial = newConversation();
  return { conversations: [initial], currentId: initial.id, saved: [] };
}

export default function App() {
  const [library, setLibrary] = useState(readLibrary);
  const [storageError, setStorageError] = useState(false);
  const [page, setPage] = useState("discover");
  const [mobileNav, setMobileNav] = useState(false);
  const [meta, setMeta] = useState(null);
  const [startup, setStartup] = useState("Connecting to the story collection…");
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [details, setDetails] = useState(null);
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [shelfFilter, setShelfFilter] = useState("both");
  const [shelfSearch, setShelfSearch] = useState("");
  const [shelfSort, setShelfSort] = useState("recent");
  const bottom = useRef(null);
  const submitting = useRef(false);
  const current =
    library.conversations.find((x) => x.id === library.currentId) ||
    library.conversations[0];
  const savedIds = new Set(library.saved.map((x) => (x.item || x).id));
  const hasTurns = current.turns.length > 0;

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(library));
      setStorageError(false);
    } catch {
      setStorageError(true);
    }
  }, [library]);
  useEffect(() => {
    let stopped = false,
      timeout;
    const controller = new AbortController();
    async function load() {
      try {
        const health = await request("/api/health", null, controller.signal);
        if (stopped) return;
        if (health.status === "error") {
          setStartup(
            "Search preparation failed. Check the Python server logs.",
          );
          return;
        }
        if (health.status !== "ready") {
          setStartup("Preparing the local NLP model and search indexes…");
          timeout = setTimeout(load, 2000);
          return;
        }
        const result = await request("/api/meta", null, controller.signal);
        if (!stopped) {
          setMeta(result);
          setStartup("");
        }
      } catch (e) {
        if (!stopped) {
          setStartup(e.message);
          timeout = setTimeout(load, 5000);
        }
      }
    }
    load();
    return () => {
      stopped = true;
      clearTimeout(timeout);
      controller.abort();
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timeout = setTimeout(() => setToast(""), 2600);
    return () => clearTimeout(timeout);
  }, [toast]);
  useEffect(() => {
    if (!mobileNav) return;
    const panel = document.querySelector(".sidebar");
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panel.querySelector("button")?.focus();
    function handleKey(event) {
      if (event.key === "Escape") setMobileNav(false);
      if (event.key !== "Tab") return;
      const buttons = [
        ...panel.querySelectorAll("button:not(:disabled)"),
      ].filter((node) => node.getClientRects().length);
      const first = buttons[0],
        last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", handleKey);
      previous?.focus?.();
    };
  }, [mobileNav]);
  useEffect(() => {
    if (hasTurns)
      bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [current.turns.length, busy, hasTurns]);

  function updateConversation(id, update) {
    setLibrary((old) => ({
      ...old,
      conversations: old.conversations.map((x) =>
        x.id === id ? { ...x, ...update } : x,
      ),
    }));
  }
  function navigate(value) {
    setPage(value);
    setMobileNav(false);
    setError("");
  }
  function startNew() {
    if (busy) return;
    if (!hasTurns) {
      updateConversation(current.id, { ...newConversation(), id: current.id });
      setInput("");
      setError("");
      navigate("discover");
      return;
    }
    const next = newConversation();
    setLibrary((old) => ({
      ...old,
      conversations: [next, ...old.conversations].slice(0, 12),
      currentId: next.id,
    }));
    setInput("");
    setError("");
    navigate("discover");
  }
  function chooseMedia(media) {
    const state = {
      ...current.state,
      media_selection: media,
      has_explicit_media: true,
    };
    if (hasTurns) applyPreferences(state);
    else updateConversation(current.id, { state });
  }
  function saveStory(rec) {
    const item = rec.item || rec;
    const exists = savedIds.has(item.id);
    setLibrary((old) => ({
      ...old,
      saved: exists
        ? old.saved.filter((x) => (x.item || x).id !== item.id)
        : [{ ...rec, savedAt: Date.now() }, ...old.saved],
    }));
    setToast(exists ? "Removed from your library" : "Saved to your library");
  }
  async function send(text = input, overrides = {}) {
    if (!text.trim() || submitting.current || !meta) return;
    submitting.current = true;
    const id = current.id;
    const nextState = overrides.state || current.state;
    setBusy(true);
    setError("");
    setInput("");
    setDetails(null);
    setPage("discover");
    try {
      const result = await request(
        overrides.form ? "/api/recommend" : "/api/chat",
        {
          message: text.trim(),
          state: nextState,
          reference_id: overrides.referenceId || null,
          lookup_id: overrides.lookupId || null,
          per_domain: 3,
        },
      );
      const turn = {
        id: crypto.randomUUID(),
        user: overrides.display || text,
        reply: result.reply,
        results: result.results,
        choices: result.choices,
        title_matches: result.title_matches,
        state: result.state,
        trace: result.trace,
        time: Date.now(),
      };
      updateConversation(id, {
        title: current.turns.length ? current.title : text.slice(0, 65),
        turns: [...current.turns, turn].slice(-20),
        state: result.state,
        lastQuery: overrides.form ? current.lastQuery : text,
      });
    } catch (e) {
      setError(e.message);
      setInput(text);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  function applyPreferences(draft) {
    setPreferencesOpen(false);
    const state = {
      ...draft,
      has_explicit_media: true,
      preferences: { ...draft.preferences, contradiction_messages: [] },
    };
    updateConversation(current.id, { state });
    if (hasTurns)
      send(current.lastQuery || "Find stories", {
        form: true,
        state,
        display: "Apply my discovery preferences",
      });
    else setToast("Discovery preferences updated");
  }
  function similar(item, media) {
    const state = {
      ...current.state,
      media_selection: media,
      has_explicit_media: true,
    };
    send(`Find ${media} with themes similar to ${item.title}.`, {
      state,
      referenceId: item.id,
    });
  }
  function removeChip(chip) {
    if (busy) return;
    const state = structuredClone(current.state);
    if (chip.field === "media") state.media_selection = "both";
    else if (chip.field === "years") {
      state.preferences.min_year = null;
      state.preferences.max_year = null;
    } else if (chip.value)
      state.preferences[chip.field] = state.preferences[chip.field].filter(
        (x) => x !== chip.value,
      );
    else state.preferences[chip.field] = null;
    applyPreferences(state);
  }
  const chips = preferenceChips(current.state);
  const shelf = library.saved
    .filter((rec) => {
      const item = rec.item || rec;
      return (
        (shelfFilter === "both" ||
          item.media_type === (shelfFilter === "books" ? "book" : "movie")) &&
        `${item.title} ${item.authors || item.director || ""} ${(item.theme_tags || []).join(" ")}`
          .toLowerCase()
          .includes(shelfSearch.toLowerCase())
      );
    })
    .slice()
    .sort((a, b) => {
      const x = a.item || a,
        y = b.item || b;
      if (shelfSort === "title") return x.title.localeCompare(y.title);
      if (shelfSort === "year") return (y.year || 0) - (x.year || 0);
      return (b.savedAt || 0) - (a.savedAt || 0);
    });

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      {mobileNav && (
        <button
          className="nav-scrim"
          onClick={() => setMobileNav(false)}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={`sidebar ${mobileNav ? "nav-open" : ""}`}
        aria-label="Main navigation"
      >
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-close"
            onClick={() => setMobileNav(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>
        <button className="new-button" onClick={startNew} disabled={busy}>
          <Plus size={17} />
          New discovery
        </button>
        <nav className="primary-nav">
          <button
            className={page === "discover" ? "active" : ""}
            onClick={() => navigate("discover")}
          >
            <Compass size={18} />
            Discover
          </button>
          <button
            className={page === "saved" ? "active" : ""}
            onClick={() => navigate("saved")}
          >
            <Bookmark size={18} />
            Saved stories
            <span className="nav-count">{library.saved.length}</span>
          </button>
        </nav>
        <div className="recent">
          <div className="nav-heading">Recent conversations</div>
          {library.conversations
            .filter((x) => x.turns.length)
            .slice(0, 7)
            .map((conversation) => (
              <div
                className={`recent-row ${conversation.id === current.id && page === "discover" ? "current" : ""}`}
                key={conversation.id}
              >
                <button
                  disabled={busy}
                  onClick={() => {
                    setLibrary((old) => ({
                      ...old,
                      currentId: conversation.id,
                    }));
                    navigate("discover");
                  }}
                  title={conversation.title}
                >
                  <MessageSquare size={12} />
                  <span>{conversation.title}</span>
                </button>
                <button
                  className="icon-button delete-conversation"
                  aria-label={`Delete conversation ${conversation.title}`}
                  disabled={busy}
                  onClick={() => {
                    const remaining = library.conversations.filter(
                      (x) => x.id !== conversation.id,
                    );
                    const replacement = remaining.length
                      ? remaining
                      : [newConversation()];
                    setLibrary((old) => ({
                      ...old,
                      conversations: replacement,
                      currentId:
                        current.id === conversation.id
                          ? replacement[0].id
                          : old.currentId,
                    }));
                  }}
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          {!library.conversations.some((x) => x.turns.length) && (
            <p className="recent-empty">
              Good stories start here.
              <br />
              Your conversations will stay close.
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="nav-heading">Behind the scenes</div>
          {[
            ["pipeline", Brain, "NLP pipeline"],
            ["evaluation", BarChart3, "Evaluation"],
            ["dataset", FolderOpen, "Dataset"],
          ].map(([key, Icon, text]) => (
            <button
              key={key}
              className={page === key ? "active" : ""}
              onClick={() => navigate(key)}
            >
              <Icon size={16} />
              {text}
            </button>
          ))}
          <div className="local-library">
            <span className="status-dot" />
            <div>
              <strong>Your story collection</strong>
              <span>Saved in this browser</span>
            </div>
            <BookOpen size={17} />
          </div>
        </div>
      </aside>
      <div className="workspace" inert={mobileNav ? true : undefined}>
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMobileNav(true)}
              aria-label="Open navigation"
              aria-expanded={mobileNav}
            >
              <Menu size={20} />
            </button>
            <span className="mobile-logomark">
              <Brand small />
            </span>
            <div className="header-title">
              <strong>Discover your next story</strong>
              <span>Find books and films that fit your mood.</span>
            </div>
            <span className="header-divider" />
            {page === "discover" && (
              <MediaTabs
                value={current.state.media_selection}
                onChange={chooseMedia}
                disabled={busy}
              />
            )}
          </div>
          <button
            aria-label="Preferences"
            className="preferences-button"
            onClick={() => setPreferencesOpen(true)}
            disabled={busy || !meta}
          >
            <SlidersHorizontal size={16} />
            <span>Preferences</span>
          </button>
        </header>
        <main
          id="main-content"
          className={`main-content ${hasTurns && page === "discover" ? "has-conversation" : ""}`}
        >
          {storageError && (
            <div className="error-banner" role="alert">
              Browser storage is full or disabled. Changes will last only while
              this page is open.
            </div>
          )}
          {startup && (
            <div className="startup-banner" role="status">
              <LoaderCircle className="spin" size={15} />
              {startup}
            </div>
          )}
          {error && (
            <div className="error-banner" role="alert">
              <AlertCircle size={16} />
              <span>{error}</span>
              <button
                className="icon-button"
                onClick={() => setError("")}
                aria-label="Dismiss error"
              >
                <X size={15} />
              </button>
            </div>
          )}
          {page === "discover" && (
            <>
              {!hasTurns ? (
                <>
                  <section className="discovery-hero">
                    <span className="intro-badge">
                      <BookOpen size={13} />A LITTLE CURIOSITY GOES A LONG WAY
                    </span>
                    <h1>
                      What kind of story
                      <br className="hero-break" /> are you looking for?
                    </h1>
                    <p>
                      Describe a mood, a theme, or something you already love.
                    </p>
                    <div className="intro-composer">
                      <Composer
                        initial
                        value={input}
                        onChange={setInput}
                        onSubmit={() => send()}
                        busy={busy}
                        disabled={!meta}
                      />
                      <div className="suggestion-grid">
                        {examples.map(({ icon: Icon, text, query }) => (
                          <button
                            disabled={busy || !meta}
                            key={text}
                            onClick={() => send(query)}
                          >
                            <span className="suggestion-icon">
                              <Icon size={16} />
                            </span>
                            <span>{text}</span>
                            <ChevronRight size={15} />
                          </button>
                        ))}
                      </div>
                    </div>
                  </section>
                  <section className="starter-section">
                    <div className="section-header">
                      <div>
                        <h2>
                          <Sparkles size={17} />A few places to start
                        </h2>
                        <p>
                          A little adventure, a little wonder. See where the
                          story takes you.
                        </p>
                      </div>
                      <span className="section-note">
                        FROM THE DEMONSTRATION CATALOG
                      </span>
                    </div>
                    <div className="starter-grid">
                      {(meta?.starters || [])
                        .filter(
                          (item) =>
                            current.state.media_selection === "both" ||
                            item.media_type ===
                              (current.state.media_selection === "books"
                                ? "book"
                                : "movie"),
                        )
                        .map((item) => (
                          <StoryCard
                            key={item.id}
                            rec={item}
                            compact
                            saved={savedIds.has(item.id)}
                            onSave={saveStory}
                            onDetails={setDetails}
                          />
                        ))}
                    </div>
                  </section>
                  <footer className="discovery-footer">
                    <span>
                      <SlidersHorizontal size={13} />
                      Your mood. Your pace.
                    </span>
                    <span>·</span>
                    <span>
                      <BookOpen size={13} />
                      Across books and films.
                    </span>
                  </footer>
                </>
              ) : (
                <div className="conversation" aria-live="polite">
                  {current.turns.map((turn) => (
                    <section className="conversation-turn" key={turn.id}>
                      <div className="user-message">
                        <p>{turn.user}</p>
                        <span>
                          You ·{" "}
                          {new Date(turn.time).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                      <div className="assistant-message">
                        <span className="assistant-label">
                          <span>
                            <Sparkles size={13} />
                          </span>
                          StoryScout
                        </span>
                        <p>{turn.reply}</p>
                      </div>
                      {turn.choices?.length > 0 && (
                        <div className="reference-choices">
                          <p>Which title did you mean?</p>
                          {turn.choices.map((item) => (
                            <button
                              key={item.id}
                              disabled={busy}
                              onClick={() =>
                                send(`Find stories similar to ${item.title}`, {
                                  referenceId: item.id,
                                })
                              }
                            >
                              {item.title} · {item.year || "Year unknown"} ·{" "}
                              {label(item.media_type)}
                              <ArrowRight size={13} />
                            </button>
                          ))}
                        </div>
                      )}
                      {turn.title_matches?.length > 0 && (
                        <section className="recommendation-group">
                          <div className="group-header"><h2>Matching titles</h2><span>Catalog lookup · preferences retained</span></div>
                          <div className="recommendation-grid">
                            {turn.title_matches.map(rec => <StoryCard key={rec.item.id} rec={rec} saved={savedIds.has(rec.item.id)} onSave={saveStory} onDetails={setDetails} />)}
                          </div>
                        </section>
                      )}
                      {Object.entries(turn.results).map(([domain, recs]) => (
                        <section className="recommendation-group" key={domain}>
                          <div className="group-header">
                            <h2>
                              {domain === "book" ? (
                                <BookOpen size={17} />
                              ) : (
                                <Film size={17} />
                              )}{" "}
                              {domain === "book"
                                ? "Books to explore"
                                : "Movies to explore"}
                              <span className="count-badge">{recs.length}</span>
                            </h2>
                            <span>{turn.trace.retrieval?.[domain]?.eligible_count?.toLocaleString() ?? '—'} eligible · diversified by NLP</span>
                          </div>
                          {recs.length ? (
                            <div className="recommendation-grid">
                              {recs.map((rec) => (
                                <StoryCard
                                  key={rec.item.id}
                                  rec={rec}
                                  saved={savedIds.has(rec.item.id)}
                                  onSave={saveStory}
                                  onDetails={setDetails}
                                />
                              ))}
                            </div>
                          ) : (
                            <div className="empty-domain">
                              No verified{" "}
                              {domain === "book" ? "books" : "movies"} match
                              these filters. Choose a preference to change.
                            </div>
                          )}
                        </section>
                      ))}
                      <details className="trace">
                        <summary>
                          <Brain size={13} />
                          NLP processing details
                        </summary>
                        <p>
                          Intent: {turn.trace.intent} · {turn.trace.method}
                        </p>
                          {turn.trace.content_query && <p>Retained topic: {turn.trace.content_query}</p>}
                          {Object.entries(turn.trace.retrieval || {}).map(([domain,info])=><p key={domain}>{label(domain)}: {info.catalog_size.toLocaleString()} catalog entries → {info.eligible_count.toLocaleString()} eligible after hard filters; {info.plot_text_candidates.toLocaleString()} with full plot text. {info.diversification}. {Object.entries(info.filter_rejections).map(([reason,count])=>`${reason}: ${count.toLocaleString()}`).join(' · ')}</p>)}
                        <p>
                          Extracted fields:{" "}
                          {turn.trace.extracted_fields.join(", ") ||
                            "No new structured fields"}
                        </p>
                        <p>
                          {Object.entries(turn.trace.active_modes)
                            .map(([k, v]) => `${label(k)}: ${v}`)
                            .join(" · ")}
                        </p>
                        <p>Request processing: {turn.trace.latency_ms} ms</p>
                      </details>
                    </section>
                  ))}
                  {busy && (
                    <div className="thinking" role="status">
                      <LoaderCircle size={17} className="spin" />
                      Scouting your next story…
                    </div>
                  )}
                  <div className="conversation-end" ref={bottom} />
                </div>
              )}
              {hasTurns && (
                <div className="conversation-dock">
                  <div className="active-preferences">
                    <SlidersHorizontal size={12} />
                    {chips.map((chip, i) => (
                      <button
                        key={`${chip.field}-${i}`}
                        className={`chip ${chip.negative ? "negative" : ""}`}
                        disabled={busy}
                        title={`Remove ${chip.text}`}
                        onClick={() => removeChip(chip)}
                      >
                        {chip.text}
                        <X size={10} />
                      </button>
                    ))}
                    <button
                      className="edit-preferences"
                      onClick={() => setPreferencesOpen(true)}
                      disabled={busy}
                    >
                      Edit criteria
                      <ArrowRight size={12} />
                    </button>
                  </div>
                  <Composer
                    value={input}
                    onChange={setInput}
                    onSubmit={() => send()}
                    busy={busy}
                    disabled={!meta}
                  />
                  <div className="followup-pills">
                    {[
                      "Show different recommendations",
                      "Make it shorter",
                      "No horror",
                      "Why did you recommend this?",
                    ].map((text) => (
                      <button
                        key={text}
                        onClick={() => send(text)}
                        disabled={busy}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
          {page === "saved" && (
            <div className="saved-page">
              <span className="eyebrow">
                <Bookmark size={13} />
                Your personal collection
              </span>
              <div className="shelf-heading">
                <div>
                  <h1>Saved stories</h1>
                  <p>Your next great read or watch, all in one place.</p>
                </div>
                <span className="shelf-counter">
                  {library.saved.length}{" "}
                  {library.saved.length === 1 ? "story" : "stories"}
                </span>
              </div>
              <div className="shelf-toolbar">
                <MediaTabs value={shelfFilter} onChange={setShelfFilter} />
                <div className="shelf-search">
                  <Search size={16} />
                  <input
                    aria-label="Search your saved stories"
                    placeholder="Search title, author, or theme…"
                    value={shelfSearch}
                    onChange={(e) => setShelfSearch(e.target.value)}
                  />
                </div>
                <select
                  aria-label="Sort saved stories"
                  value={shelfSort}
                  onChange={(e) => setShelfSort(e.target.value)}
                >
                  <option value="recent">Recently saved</option>
                  <option value="title">Title (A–Z)</option>
                  <option value="year">Newest release</option>
                </select>
              </div>
              {shelf.length ? (
                <div className="saved-grid">
                  {shelf.map((rec) => (
                    <StoryCard
                      key={(rec.item || rec).id}
                      compact
                      rec={rec}
                      saved
                      onSave={saveStory}
                      onDetails={setDetails}
                    />
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <Bookmark size={28} />
                  <h2>
                    {library.saved.length
                      ? "No matching stories"
                      : "A shelf waiting for your stories."}
                  </h2>
                  <p>
                    {library.saved.length
                      ? "Try another title or change the media filter."
                      : "Save a book or film from your discoveries. You can come back to it any time."}
                  </p>
                  <button
                    className="secondary-button"
                    onClick={() => navigate("discover")}
                  >
                    Discover stories
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </div>
          )}
          {page === "pipeline" && <PipelinePage meta={meta} />}
          {page === "evaluation" && <EvaluationPage />}
          {page === "dataset" && (
            <div className="info-page">
              <span className="eyebrow">
                <FolderOpen size={14} />
                The collection
              </span>
              <h1>Stories with a source.</h1>
              <p className="page-lede">
                {meta?.counts.book.toLocaleString() || "…"} books and{" "}
                {meta?.counts.movie.toLocaleString() || "…"} movies in the recommendation index.
                {meta?.title_directory_count > 0 && ` ${meta.title_directory_count.toLocaleString()} source records searchable by title.`}
              </p>
              <div className="info-panel">
                <h3>Books</h3>
                <p>
                  Project Gutenberg public catalog metadata, plus 14 curated
                  demonstration records. Most expanded records provide titles,
                  authors, and subjects, with page counts and years unavailable.
                </p>
                <h3>Movies</h3>
                <p>
                  MovieLens latest-small metadata, plus 13 curated demonstration
                  records. MovieLens provides titles and genre labels, not plot
                  descriptions or runtimes. Separate Wikipedia text and verified
                  infobox fields now supplement this metadata.
                </p>
                <p>
                  {meta?.coverage?.movie?.plot_text?.toLocaleString() || "…"} locally
                  indexed movie plots; {meta?.coverage?.movie?.known_runtime?.toLocaleString() || "…"}
                  {" "}known runtimes. Unknown fields remain unknown.
                </p>
                <h3>Descriptions and provenance</h3>
                <p>
                  Demo descriptions are original short texts. Some records have
                  Wikipedia-sourced AI paraphrases, marked in their detail
                  panels. Expanded movie search indexes original source plot
                  text locally; cards show short opening excerpts. Learned
                  keywords, inferred moods, and predicted genres remain
                  separate from source facts. Unknown metadata cannot satisfy
                  explicit filters.
                </p>
                <h3>Usage terms</h3>
                <p>
                  MovieLens has research-use conditions. Project Gutenberg
                  metadata and text rights vary by jurisdiction.
                  Wikipedia-derived summaries require attribution under CC BY-SA
                  4.0. Consult the repository’s DATA_SOURCES.md before
                  redistributing a catalog.
                </p>
                <p>
                  Artwork is an original StoryScout illustration, not an
                  official publisher cover or movie poster.
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
      {preferencesOpen && (
        <PreferencesDrawer
          state={current.state}
          meta={meta}
          onClose={() => setPreferencesOpen(false)}
          onApply={applyPreferences}
          busy={busy}
        />
      )}{" "}
      {details && (
        <DetailDrawer
          rec={details}
          saved={savedIds.has((details.item || details).id)}
          onSave={saveStory}
          onClose={() => setDetails(null)}
          onSimilar={similar}
          busy={busy}
        />
      )}{" "}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
    </div>
  );
}
