import { useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  Film,
  RotateCcw,
  SlidersHorizontal,
} from "lucide-react";
import { emptyState, label } from "./api.js";
import { Drawer, MediaTabs } from "./components.jsx";

export default function PreferencesDrawer({
  state,
  meta,
  onClose,
  onApply,
  busy,
}) {
  const [draft, setDraft] = useState(() => structuredClone(state));
  const p = draft.preferences;
  const set = (key, value) =>
    setDraft((d) => ({
      ...d,
      preferences: { ...d.preferences, [key]: value },
    }));
  const toggle = (field, value) =>
    set(
      field,
      p[field].includes(value)
        ? p[field].filter((x) => x !== value)
        : [...p[field], value],
    );
  const overlap = p.preferred_genres.filter((x) =>
    p.excluded_genres.includes(x),
  );
  const invalidYears = p.min_year && p.max_year && p.min_year > p.max_year;
  return (
    <Drawer
      title="Discovery preferences"
      eyebrow="Make it your kind of story"
      icon={SlidersHorizontal}
      onClose={onClose}
      footer={
        <>
          <button
            className="quiet-button"
            onClick={() => setDraft(emptyState())}
          >
            <RotateCcw size={14} />
            Reset preferences
          </button>
          <button
            className="primary-button"
            disabled={busy || overlap.length > 0 || !!invalidYears}
            onClick={() => onApply(draft)}
          >
            Apply preferences
            <ArrowRight size={14} />
          </button>
        </>
      }
    >
      <section className="filter-section">
        <h3>Media format</h3>
        <MediaTabs
          value={draft.media_selection}
          onChange={(value) =>
            setDraft((d) => ({
              ...d,
              media_selection: value,
              has_explicit_media: true,
            }))
          }
        />
      </section>
      {["preferred_genres", "excluded_genres"].map((field) => (
        <section className="filter-section" key={field}>
          <div className="filter-label">
            <h3>
              {field === "preferred_genres"
                ? "Genres (match any selected)"
                : "Excluded genres"}
            </h3>
            <span>{p[field].length} selected</span>
          </div>
          <div
            className={`genre-options ${field === "excluded_genres" ? "exclusions" : ""}`}
          >
            {(meta?.genres || []).map((genre) => (
              <button
                key={genre}
                aria-pressed={p[field].includes(genre)}
                className={p[field].includes(genre) ? "selected" : ""}
                onClick={() => toggle(field, genre)}
              >
                {label(genre)}
                {p[field].includes(genre) && <Check size={13} />}
              </button>
            ))}
          </div>
        </section>
      ))}
      {overlap.length > 0 && (
        <p className="inline-error" role="alert">
          Choose whether to prefer or exclude {overlap.join(", ")}.
        </p>
      )}
      <section className="filter-section">
        <h3>Desired mood</h3>
        <select
          value={p.desired_mood || ""}
          onChange={(e) => set("desired_mood", e.target.value || null)}
          aria-label="Desired mood"
        >
          <option value="">Any mood</option>
          {(meta?.moods || []).map((x) => (
            <option key={x} value={x}>
              {label(x)}
            </option>
          ))}
        </select>
      </section>
      <section className="filter-section length-filter">
        <div className="filter-label">
          <h3>
            <BookOpen size={15} />
            Max book length
          </h3>
          <span>{p.max_pages ? `${p.max_pages} pages` : "No limit"}</span>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={p.max_pages != null}
            onChange={(e) => set("max_pages", e.target.checked ? 350 : null)}
          />
          Set a page limit
        </label>
        {p.max_pages != null && (
          <input
            aria-label="Maximum book pages"
            type="number"
            min="1"
            max="10000"
            value={p.max_pages}
            onChange={(e) =>
              set(
                "max_pages",
                Math.max(1, Math.min(10000, Number(e.target.value))),
              )
            }
          />
        )}
      </section>
      <section className="filter-section length-filter">
        <div className="filter-label">
          <h3>
            <Film size={15} />
            Max movie runtime
          </h3>
          <span>{p.max_runtime ? `${p.max_runtime} minutes` : "No limit"}</span>
        </div>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={p.max_runtime != null}
            onChange={(e) => set("max_runtime", e.target.checked ? 120 : null)}
          />
          Set a runtime limit
        </label>
        {p.max_runtime != null && (
          <input
            aria-label="Maximum movie minutes"
            type="number"
            min="1"
            max="1000"
            value={p.max_runtime}
            onChange={(e) =>
              set(
                "max_runtime",
                Math.max(1, Math.min(1000, Number(e.target.value))),
              )
            }
          />
        )}
      </section>
      <section className="filter-section">
        <h3>Release period</h3>
        <div className="year-inputs">
          <label>
            From
            <input
              type="number"
              min="1"
              max="2100"
              placeholder="Any year"
              value={p.min_year || ""}
              onChange={(e) =>
                set("min_year", e.target.value ? Number(e.target.value) : null)
              }
            />
          </label>
          <span>—</span>
          <label>
            Through
            <input
              type="number"
              min="1"
              max="2100"
              placeholder="Present"
              value={p.max_year || ""}
              onChange={(e) =>
                set("max_year", e.target.value ? Number(e.target.value) : null)
              }
            />
          </label>
        </div>
        {invalidYears && (
          <p className="inline-error" role="alert">
            The start year must be earlier than the end year.
          </p>
        )}
      </section>
      <section className="filter-section">
        <h3>Language</h3>
        <select
          aria-label="Language"
          value={p.language || ""}
          onChange={(e) => set("language", e.target.value || null)}
        >
          <option value="">Any language</option>
          {["english", "hindi", "french", "spanish", "german"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </section>
      <section className="filter-section">
        <h3>Content preferences</h3>
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={p.negative_content.includes("graphic violence")}
            onChange={() => toggle("negative_content", "graphic violence")}
          />
          Avoid graphic violence
        </label>
        <p className="filter-help">
          Records with known warnings are excluded. Unknown content information
          is shown as uncertain.
        </p>
      </section>
    </Drawer>
  );
}
