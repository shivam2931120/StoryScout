import { useEffect, useState } from "react";
import { BarChart3, Brain, Download, LoaderCircle } from "lucide-react";
import { request, label } from "./api.js";
import EvaluationExtras from "./EvaluationExtras.jsx";

export function PipelinePage({ meta }) {
  const stages = [
    [
      "01",
      "Understand the request",
      "Title identity is resolved first. Rules then identify recommendations, refinements, explanations, resets, and reference titles. New search explicitly clears prior criteria while keeping the chat history.",
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
      "Separate topic and preference queries prevent mood words from replacing your subject. Corpus TF-IDF learns keyphrases from local text, with a separate title/entity field. MiniLM encodes beginning, middle, and end chunks of full plot text into a shared book/movie space. A local supervised classifier learns genres from plot descriptions.",
    ],
    [
      "05",
      "Rank and explain",
      "Overlapping passages are matched independently, then aggregated to one book/movie result with whole-description context. A minimum topic match is required before bounded genre, mood, theme and learned genre boosts. A quality cutoff allows fewer results instead of filling slots with weak matches. Maximal marginal relevance reduces redundant narratives. Different picks excludes already shown IDs while preserving every hard filter.",
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
      {meta?.passages && <p>{Object.entries(meta.passages).map(([domain,stats])=>`${label(domain)}: ${stats.count.toLocaleString()} passages from ${stats.indexed_records.toLocaleString()} records (${stats.mode})`).join(" · ")}</p>}
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
          <p>Precision@5 counts all five slots, including deliberately unfilled ones. Precision among returned items and answer rate are reported separately. Missing judgments can undercount relevant new catalog records.</p>
          {data.passage_evaluation && <section className="info-panel">
            <h2>Passage matching: focal-detail queries</h2>
            <p>{data.passage_evaluation.focal_query_count} developer-authored movie queries checked against source plots. This is a small diagnostic set, not independent human evaluation.</p>
            <div className="table-scroll"><table><thead><tr><th>Hybrid retrieval</th><th>Recall@5</th><th>MRR@5</th><th>Answer rate</th></tr></thead><tbody>
              {Object.entries(data.passage_evaluation.results).map(([name,modes])=>{const m=modes.hybrid.focal.movie;return <tr key={name}><td>{name === "passages" ? "With passages" : "Whole description"}</td><td>{m.recall_at_5.toFixed(3)}</td><td>{m.mrr_at_5.toFixed(3)}</td><td>{m.answer_rate.toFixed(3)}</td></tr>;})}
            </tbody></table></div>
            <p>Only passage matching changes within this comparison. Broader benchmark trade-offs and all three retrieval modes are recorded in the project report; a match does not verify plot facts or content suitability.</p>
          </section>}
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Precision@5</th>
                  <th>Precision among returned</th>
                  <th>Answer rate</th>
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
                          "precision_when_returned",
                          "answer_rate",
                          "recall_at_5",
                          "mrr_at_5",
                          "hard_constraint_compliance",
                        ].map((field) => (
                          <td key={field}>{m[field]?.toFixed(3)}</td>
                        ))
                      ) : (
                        <td colSpan="6">Not measured</td>
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
