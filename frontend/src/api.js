const base = (import.meta.env?.VITE_API_URL || "").replace(/\/$/, "");
export async function request(path, body, signal) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 65000);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort);
  try {
    const response = await fetch(`${base}${path}`, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Please check your preferences and try again.",
      );
    return data;
  } catch (error) {
    if (error.name === "AbortError")
      throw new Error("The search took too long. Please try again.");
    if (error instanceof TypeError)
      throw new Error(
        "Cannot reach StoryScout. Check that the Python server is running.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener("abort", abort);
  }
}

export const emptyPreferences = () => ({
  preferred_genres: [],
  excluded_genres: [],
  desired_mood: null,
  themes: [],
  language: null,
  min_year: null,
  max_year: null,
  referenced_title: null,
  positive_content: [],
  negative_content: [],
  max_pages: null,
  max_runtime: null,
  contradiction_messages: [],
});
export const emptyState = () => ({
  preferences: emptyPreferences(),
  media_selection: "both",
  has_explicit_media: false,
  selected_reference_id: null,
  last_recommendations: [],
  pending_title_choices: [],
  messages: [],
  retrieval_mode: "hybrid",
  last_content_query: "",
  identification_query: "",
  seen_recommendations: [],
});
export const newConversation = () => ({
  id: crypto.randomUUID(),
  title: "New discovery",
  state: emptyState(),
  turns: [],
  lastQuery: "",
});
export const label = (value) =>
  value ? value.charAt(0).toUpperCase() + value.slice(1) : "";
export const length = (item) =>
  item.media_type === "book"
    ? item.page_count
      ? `${item.page_count} pages`
      : "Pages unknown"
    : item.runtime_minutes
      ? `${Math.floor(item.runtime_minutes / 60) ? `${Math.floor(item.runtime_minutes / 60)}h ` : ""}${item.runtime_minutes % 60 ? `${item.runtime_minutes % 60}m` : ""}`.trim()
      : "Runtime unknown";

export function preferenceChips(state) {
  const p = state.preferences;
  return [
    {
      text:
        state.media_selection === "both"
          ? "Books & movies"
          : label(state.media_selection),
      field: "media",
    },
    ...(p.referenced_title ? [{text:`Like ${p.referenced_title}`, field:"reference"}] : []),
    ...p.preferred_genres.map((x) => ({
      text: label(x),
      field: "preferred_genres",
      value: x,
    })),
    ...p.excluded_genres.map((x) => ({
      text: `No ${x}`,
      field: "excluded_genres",
      value: x,
      negative: true,
    })),
    ...(p.desired_mood
      ? [{ text: label(p.desired_mood), field: "desired_mood" }]
      : []),
    ...p.themes.map((x) => ({ text: label(x), field: "themes", value: x })),
    ...(p.max_pages
      ? [{ text: `≤ ${p.max_pages} pages`, field: "max_pages" }]
      : []),
    ...(p.max_runtime
      ? [{ text: `≤ ${p.max_runtime} min`, field: "max_runtime" }]
      : []),
    ...(p.min_year || p.max_year
      ? [
          {
            text: `${p.min_year || "Any year"}–${p.max_year || "present"}`,
            field: "years",
          },
        ]
      : []),
    ...(p.language ? [{ text: label(p.language), field: "language" }] : []),
    ...p.negative_content.map((x) => ({
      text: `Avoid ${x}`,
      field: "negative_content",
      value: x,
      negative: true,
    })),
  ];
}


export function removeTopicTerm(topic, term) {
  const escaped = Array.from(term).map(char => "^$\\.*+?()[]{}|".includes(char) ? "\\" + char : char).join("");
  return topic.replace(new RegExp("\\b" + escaped + "\\b", "gi"), " ").replace(/\s+/g, " ").trim();
}
