import { useEffect, useState } from "react";
import { BarChart3, Brain, Download, LoaderCircle } from "lucide-react";
import { request, label } from "./api.js";
import EvaluationExtras from "./EvaluationExtras.jsx";

export function PipelinePage({ meta }) {
  const stages = [
    [
      "01",
      "Understand the request",
      "Rules identify recommendations, refinements, explanations, resets, and references to existing titles.",
    ],
    [
      "02",
      "Extract and remember preferences",
      "Typed Python models retain your meaningful topic, genres, exclusions, mood, themes, language, years, pages, and runtime. A refinement reconstructs the query from active preferences instead of searching administrative text.",
    ],
    [
      "03",
      "Filter verified metadata",
      "Selected genres match any chosen source genre. Source subject mappings are marked separately. Runtime, language, year, pages, and exclusions are applied before ranking; unknown values cannot pass explicit limits.",
    ],
    [
      "04",
      "Compare language and meaning",
      "Corpus TF-IDF learns keyphrases from local text. MiniLM encodes beginning, middle, and end chunks of full plot text into a shared book/movie space. A local supervised classifier learns genres from plot descriptions.",
    ],
    [
      "05",
      "Rank and explain",
      "Lexical/semantic similarity is reranked with active genre, mood, theme, and learned text-genre signals. Maximal marginal relevance reduces redundant narratives. Different picks excludes already shown IDs while preserving every hard filter.",
    ],
  ];
  return (
    <div className="info-page">
      <span className="eyebrow">
        <Brain size={14} />
        Behind the discovery
      </span>
      <h1>A conversation powered by NLP.</h1>
      <p className="page-lede">
        The interface is React. The language processing, retrieval, and
        evaluation are Python.
      </p>
      <div className="pipeline-steps">
        {stages.map(([n, title, description]) => (
          <article key={n}>
            <span>{n}</span>
            <div>
              <h3>{title}</h3>
              <p>{description}</p>
            </div>
          </article>
        ))}
      </div>
      <div className="info-panel">
        <h3>Running in this application</h3>
        {Object.entries(meta?.modes || {}).map(([domain, mode]) => (
          <p key={domain}>
            <strong>{label(domain)} search:</strong> {mode}
          </p>
        ))}
        <p>
          Model: <code>{meta?.model || "Loading…"}</code>
        </p>
        <p>Encoder runtime: {meta?.embedding_backend==='onnx'?'Quantized ONNX CPU; same pretrained MiniLM architecture':'Sentence Transformers CPU'}. Catalog profile: {meta?.catalog_profile || 'full'}.</p>
        <p>
          {meta?.optional_interpreter
            ? "Optional NVIDIA interpretation is enabled. Submitted messages are sent to NVIDIA; filtering and ranking remain in the local Python pipeline."
            : "Local rule extraction is active. Chat messages are processed by the Python engine without an external chat API."}
        </p>
        <p>
          The pretrained embedding model is used for inference. StoryScout does
          not train it or learn from browsing behavior.
        </p>
      </div>
    </div>
  );
}

export function EvaluationPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    request("/api/evaluation", null, controller.signal)
      .then(setData)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, []);
  const benchmark = data?.results?.retrieval_benchmark;
  return (
    <div className="info-page">
      <span className="eyebrow">
        <BarChart3 size={14} />
        Measured, not guessed
      </span>
      <h1>How the search performs.</h1>
      <p className="page-lede">
        Saved outputs from executed Python experiments. These are evaluation
        metrics, not recommendation confidence.
      </p>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      {!data && !error && <LoaderCircle className="spin" />}
      {benchmark && (
        <>
          <div className="metric-cards">
            <div>
              <strong>{benchmark.query_count}</strong>
              <span>Benchmark queries</span>
            </div>
            <div>
              <strong>
                {data.results.preference_extraction.labeled_conversations}
              </strong>
              <span>Preference conversations</span>
            </div>
            <div>
              <strong>
                {data.results.preference_extraction.labeled_messages}
              </strong>
              <span>Labeled messages</span>
            </div>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Precision@5</th>
                  <th>Recall@5</th>
                  <th>MRR@5</th>
                  <th>Constraint compliance</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(benchmark.models).map(([name, result]) => {
                  const m = result.macro_average_of_book_and_movie_metrics;
                  return (
                    <tr key={name}>
                      <td>{name === "tfidf" ? "TF-IDF" : label(name)}</td>
                      {m ? (
                        [
                          "precision_at_5",
                          "recall_at_5",
                          "mrr_at_5",
                          "hard_constraint_compliance",
                        ].map((field) => (
                          <td key={field}>{m[field]?.toFixed(3)}</td>
                        ))
                      ) : (
                        <td colSpan="4">Not measured</td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="info-panel">
            <h3>What these results mean</h3>
            <p>{benchmark.judgment_method}</p>
            <p>{benchmark.mixed_media_aggregation}</p>
            <p>
              Judgments are incomplete: relevant titles outside the labeled IDs
              can be undercounted. The small preference benchmark does not
              establish general extraction accuracy.
            </p>
            <p>
              Book and movie results are grouped. Independently fitted TF-IDF
              scores are not compared as a single ranking across both domains.
            </p>
          </div>
          <a
            className="text-button"
            download="storyscout-evaluation.json"
            href={
              "data:application/json;charset=utf-8," +
              encodeURIComponent(JSON.stringify(data.results, null, 2))
            }
          >
            Download actual results
            <Download size={15} />
          </a>
          {data.preference_search && <section className="info-panel"><h3>Do preference changes affect results?</h3><p>Executed source-metadata checks across five genre selections with a 120-minute limit. These checks measure filter behavior, not subjective relevance.</p><p>Distinct titles across five searches: {data.preference_search.baseline.unique_titles_across_five_preferences} before → {data.preference_search.current.unique_titles_across_five_preferences} now. Mean source-genre precision@5: {data.preference_search.baseline.mean_source_genre_precision_at_5.toFixed(2)} → {data.preference_search.current.mean_source_genre_precision_at_5.toFixed(2)}.</p><p>All current hard filters passed: {data.preference_search.current.all_hard_constraints_pass ? 'Yes' : 'No'}. All next-pick groups were nonempty and unseen: {data.preference_search.current.all_next_picks_nonempty_and_unseen ? 'Yes' : 'No'}.</p></section>}
          <EvaluationExtras classifiers={data.genre_classifier} textClassifiers={data.genre_text_classifier} />
        </>
      )}
    </div>
  );
}
