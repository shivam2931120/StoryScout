export function isLiveBook(item) {
  return item?.source === "bigbook-api" || String(item?.id || "").startsWith("book_bigbook_");
}

export function persistentLibrary(library) {
  // Big Book API records and derived response data stay request-scoped.
  const cleanState = (state = {}) => ({
    ...state,
    selected_reference_id: String(state.selected_reference_id || "").startsWith("book_bigbook_") ? null : state.selected_reference_id,
    last_recommendations: (state.last_recommendations || []).filter((id) => !String(id).startsWith("book_bigbook_")),
    seen_recommendations: (state.seen_recommendations || []).filter((id) => !String(id).startsWith("book_bigbook_")),
    pending_title_choices: (state.pending_title_choices || []).filter((id) => !String(id).startsWith("book_bigbook_")),
  });
  return {
    ...library,
    saved: library.saved.filter((row) => !isLiveBook(row.item || row)),
    conversations: library.conversations.map((conversation) => ({
      ...conversation,
      state: cleanState(conversation.state),
      turns: conversation.turns.map((turn) => ({
        ...turn,
        results: Object.fromEntries(Object.entries(turn.results || {}).map(([domain, records]) => [
          domain, records.filter((record) => !isLiveBook(record.item || record)),
        ])),
        choices: (turn.choices || []).filter((item) => !isLiveBook(item)),
        title_matches: (turn.title_matches || []).filter((record) => !isLiveBook(record.item || record)),
        state: cleanState(turn.state),
        trace: turn.trace ? { ...turn.trace, retrieval: Object.fromEntries(Object.entries(turn.trace.retrieval || {}).filter(([domain]) => domain !== "book")) } : turn.trace,
      })),
    })),
  };
}
