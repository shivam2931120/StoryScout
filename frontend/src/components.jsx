import { useEffect, useRef } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  BookOpen,
  Check,
  Clock,
  Film,
  LoaderCircle,
  Orbit,
  Sparkles,
  X,
} from "lucide-react";
import { label, length } from "./api.js";

export function Brand({ small = false }) {
  return (
    <div className={`brand ${small ? "small" : ""}`}>
      <span className="brand-mark">
        <BookOpen size={21} />
        <span className="brand-star">
          <Sparkles size={10} />
        </span>
      </span>
      {!small && <span>StoryScout</span>}
    </div>
  );
}

export function MediaTabs({ value, onChange, disabled = false }) {
  return (
    <div className="media-tabs" role="group" aria-label="Media format">
      {[
        ["both", "All stories"],
        ["books", "Books"],
        ["movies", "Movies"],
      ].map(([key, text]) => (
        <button
          type="button"
          key={key}
          aria-pressed={value === key}
          className={value === key ? "selected" : ""}
          disabled={disabled}
          onClick={() => onChange(key)}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

export function Cover({ item, large = false }) {
  const tags = [...(item.genres || []), ...(item.theme_tags || [])].join(" ");
  const art = /space|science fiction|time travel/.test(tags)
    ? "space"
    : /mystery|crime|horror|thriller/.test(tags)
      ? "mystery"
      : /family|romance|comedy/.test(tags)
        ? "warm"
        : /fantasy|adventure|journey/.test(tags)
          ? "journey"
          : "warm";
  return (
    <div
      className={`cover cover-${art} ${large ? "cover-large" : ""}`}
      aria-hidden="true"
    >
      <img src={`/art/${art}.svg`} alt="" />
      <div className="cover-shade" />
      <div className="cover-text">
        <span>
          {item.media_type === "book"
            ? "A literary journey"
            : "A cinematic journey"}
        </span>
        <strong>{item.title}</strong>
        <i>{item.authors || item.director || "StoryScout collection"}</i>
      </div>
      <span className={`format-badge ${item.media_type}`}>
        {item.media_type === "book" ? (
          <BookOpen size={11} />
        ) : (
          <Film size={11} />
        )}{" "}
        {label(item.media_type)}
      </span>
    </div>
  );
}

export function StoryCard({ rec, saved, onSave, onDetails, compact = false }) {
  const item = rec.item || rec;
  return (
    <article className={`story-card ${compact ? "compact" : ""}`}>
      <button
        className="cover-button"
        onClick={() => onDetails(rec)}
        aria-label={`View details for ${item.title}`}
      >
        <Cover item={item} />
      </button>
      <div className="story-body">
        <div className="card-overline">
          <span>
            {(item.genres?.length ? item.genres : item.theme_tags || [])
              .slice(0, 2)
              .map(label)
              .join(" / ") || "From the catalog"}
          </span>
          {compact && (
            <button
              className={`icon-button bookmark ${saved ? "is-saved" : ""}`}
              onClick={() => onSave(rec)}
              aria-label={`${saved ? "Unsave" : "Save"} ${item.title}`}
              aria-pressed={saved}
            >
              <Bookmark size={17} fill={saved ? "currentColor" : "none"} />
            </button>
          )}
        </div>
        <button
          className="title-button"
          aria-label={`View ${item.title}`}
          onClick={() => onDetails(rec)}
        >
          <h3>{item.title}</h3>
        </button>
        <p className="creator">
          {item.authors ||
            (item.director ? `Dir. ${item.director}` : "Creator unknown")}
        </p>
        <p className="item-meta">
          {item.year || "Year unknown"}
          <span>·</span>
          {length(item)}
        </p>
        <p className="description">
          {item.description ||
            "Explore this catalog entry by its available genres, subjects, and metadata."}
        </p>
        {!compact && rec.explanation && (
          <div className="rationale">
            <Sparkles size={13} />
            <p>{rec.explanation}</p>
          </div>
        )}
        <div className="card-actions">
          {!compact ? (
            <button
              className={`save-button ${saved ? "is-saved" : ""}`}
              onClick={() => onSave(rec)}
              aria-label={`${saved ? "Unsave" : "Save"} ${item.title}`}
              aria-pressed={saved}
            >
              <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
              <span>{saved ? "Saved" : "Save"}</span>
            </button>
          ) : (
            <span className="catalog-dot">
              {item.media_type === "book"
                ? "Read something remarkable"
                : "Watch something memorable"}
            </span>
          )}
          <button className="text-button" onClick={() => onDetails(rec)}>
            {compact ? "Explore story" : "View details"}
            <ArrowRight size={13} />
          </button>
        </div>
      </div>
    </article>
  );
}

export function Composer({
  value,
  onChange,
  onSubmit,
  busy,
  disabled,
  initial = false,
}) {
  const ref = useRef(null);
  useEffect(() => {
    if (initial) ref.current?.focus();
  }, [initial]);
  return (
    <form
      className={`composer ${initial ? "composer-initial" : ""}`}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <textarea
        ref={ref}
        aria-label="Your story request"
        placeholder={
          initial
            ? "A comforting book, a clever thriller, or something like Interstellar…"
            : "Refine your search or ask for something different…"
        }
        rows={initial ? 3 : 1}
        value={value}
        maxLength={2000}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
          ) {
            event.preventDefault();
            if (value.trim() && !busy && !disabled) onSubmit();
          }
        }}
      />
      <div className="composer-bottom">
        <span className="composer-hint">
          <Sparkles size={14} />
          {initial ? (
            <>A good story starts with a little curiosity.</>
          ) : (
            "Keep the conversation going."
          )}
        </span>
        <button
          className="primary-button"
          type="submit"
          disabled={!value.trim() || busy || disabled}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <>
              {initial ? "Scout" : "Send"}
              {initial ? <ArrowRight size={15} /> : <ArrowUpRight size={15} />}
            </>
          )}
        </button>
      </div>
    </form>
  );
}

export function Drawer({
  title,
  eyebrow,
  icon: Icon = Sparkles,
  onClose,
  children,
  footer,
}) {
  const dialog = useRef(null);
  useEffect(() => {
    const node = dialog.current;
    const previous = document.activeElement;
    node.showModal();
    return () => {
      node.close();
      previous?.focus?.();
    };
  }, []);
  return (
    <dialog
      ref={dialog}
      className="drawer"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="drawer-inner">
        <div className="drawer-header">
          <div>
            <span className="eyebrow">
              <Icon size={14} />
              {eyebrow}
            </span>
            <h2>{title}</h2>
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close drawer"
          >
            <X size={20} />
          </button>
        </div>
        <div className="drawer-content">{children}</div>
        {footer && <div className="drawer-footer">{footer}</div>}
      </div>
    </dialog>
  );
}

export function DetailDrawer({ rec, saved, onSave, onClose, onSimilar, busy }) {
  const item = rec.item || rec;
  return (
    <Drawer
      title={item.title}
      eyebrow={`${label(item.media_type)} discovery`}
      icon={item.media_type === "book" ? BookOpen : Film}
      onClose={onClose}
      footer={
        <span className="footer-note">
          <span className="status-dot" />
          Source-linked catalog entry
        </span>
      }
    >
      <div className="detail-art">
        <Cover item={item} large />
        <span className="art-credit">StoryScout illustrative artwork</span>
      </div>
      <p className="detail-creator">
        {item.authors
          ? `By ${item.authors}`
          : item.director
            ? `Directed by ${item.director}`
            : "Creator unknown"}
      </p>
      <div className="metadata-grid">
        {[
          ["Format", label(item.media_type)],
          ["Length", length(item)],
          ["Year", item.year || "Unknown"],
        ].map(([key, val]) => (
          <div key={key}>
            <span>{key}</span>
            <strong>{val}</strong>
          </div>
        ))}
      </div>
      <section className="detail-section">
        <h3>Synopsis</h3>
        <p>
          {item.description ||
            "This source provides catalog metadata only. A verified plot description is not available."}
        </p>
        {item.description_status === "sourced_ai" && (
          <span className="provenance">
            AI paraphrase of a sourced Wikipedia excerpt. Verify details with
            the linked source.
          </span>
        )}
      </section>
      {rec.explanation && (
        <section className="fit-panel">
          <h3>
            <Sparkles size={16} />
            Why this fits your request
          </h3>
          <p>{rec.explanation}</p>
        </section>
      )}
      <div className="detail-tags">
        {(item.genres || []).map((x) => (
          <span className="chip" key={x}>
            {label(x)}
          </span>
        ))}
        {(item.theme_tags || []).slice(0, 6).map((x) => (
          <span className="chip muted" key={x}>
            {label(x)}
          </span>
        ))}
      </div>
      <div className="detail-links">
        {item.source_url?.startsWith("https://") && (
          <a href={item.source_url} target="_blank" rel="noreferrer">
            Catalog source
            <ArrowUpRight size={14} />
          </a>
        )}
        {item.description_source_url?.startsWith("https://") && (
          <a
            href={item.description_source_url}
            target="_blank"
            rel="noreferrer"
          >
            Description source
            <ArrowUpRight size={14} />
          </a>
        )}
      </div>
      {rec.similarity_score != null && (
        <details className="score-details">
          <summary>How the NLP engine compared this story</summary>
          <p>
            Similarity score: {rec.similarity_score.toFixed(3)}
            <br />
            TF-IDF cosine: {rec.lexical_score?.toFixed(3)}
            {rec.semantic_score != null && (
              <>
                <br />
                Embedding cosine: {rec.semantic_score.toFixed(3)}
              </>
            )}
          </p>
          <p>
            Similarity measures text overlap and meaning. It is not accuracy or
            a probability of enjoyment. Genres, themes, and source metadata may
            be incomplete.
          </p>
          <p>Tag provenance: {item.tag_provenance}</p>
          {item.nlp_keywords?.length > 0 && <p>Local TF-IDF keyphrases: {item.nlp_keywords.join(' · ')}</p>}
          {item.predicted_genres?.length > 0 && <p>Experimental text-classified genres: {item.predicted_genres.join(', ')}. These predictions do not replace source genres.</p>}
          {Object.keys(item.inferred_moods || {}).length > 0 && <p>Text-inferred tones: {Object.keys(item.inferred_moods).slice(0,4).join(', ')}. These are soft NLP inferences, not verified content labels.</p>}
          {rec.score_components && <p>Reranking signals: {Object.entries(rec.score_components).map(([key,value])=>`${key.replaceAll('_',' ')} ${value.toFixed(3)}`).join(' · ')}. Alignment values are not confidence percentages.</p>}
        </details>
      )}
      {Object.entries(item.metadata_provenance || {}).map(([field,source]) => <p className="provenance" key={field}>{field.replaceAll('_',' ')}: <a href={source.url} target="_blank" rel="noreferrer">{source.source}</a></p>)}
      <div className="detail-buttons">
        <button
          className="primary-button"
          disabled={busy}
          onClick={() =>
            onSimilar(item, item.media_type === "book" ? "books" : "movies")
          }
        >
          <Orbit size={16} />
          Find similar stories
        </button>
        <button
          className="secondary-button"
          disabled={busy}
          onClick={() =>
            onSimilar(item, item.media_type === "book" ? "movies" : "books")
          }
        >
          {item.media_type === "book" ? (
            <Film size={16} />
          ) : (
            <BookOpen size={16} />
          )}
          Find {item.media_type === "book" ? "movies" : "books"} with similar
          themes
        </button>
        <button
          className={`quiet-button ${saved ? "is-saved" : ""}`}
          onClick={() => onSave(rec)}
        >
          <Bookmark size={16} fill={saved ? "currentColor" : "none"} />
          {saved ? "Saved to your library" : "Save to my library"}
        </button>
      </div>
      <p className="detail-note">
        Shared themes and descriptions do not establish an adaptation
        relationship. Unknown content warnings cannot guarantee suitability.
      </p>
    </Drawer>
  );
}
