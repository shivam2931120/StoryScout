import { useState } from "react";
import { Download, Upload } from "lucide-react";
import { request, label } from "./api.js";

function download(text, filename) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/csv;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function EvaluationExtras({ classifiers, textClassifiers }) {
  const [scored, setScored] = useState(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function template() {
    setError("");
    setPending(true);
    try {
      const result = await request("/api/evaluation/template");
      download(result.csv, result.filename);
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  }
  async function upload(file) {
    if (!file) return;
    if (file.size > 1_000_000) {
      setError("Please use a judgment sheet smaller than 1MB.");
      return;
    }
    setError("");
    setPending(true);
    try {
      setScored(
        await request("/api/evaluation/judge", { csv_text: await file.text() }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      {textClassifiers && <section className="info-panel"><h3>Locally trained genre NLP: title vs plot text</h3><p>TF-IDF + one-vs-rest logistic regression, evaluated on the same {textClassifiers.test_records.toLocaleString()} held-out films. Plot-hash grouping prevents duplicate text leaking across splits. Genre labels are never appended to classifier input.</p><div className="table-scroll"><table><thead><tr><th>Input</th><th>Micro F1</th><th>Macro F1</th></tr></thead><tbody>{Object.entries(textClassifiers.models).map(([name,result])=><tr key={name}><td>{name==='plot_text'?'Full plot text':'Title baseline'}</td><td>{result.classification_report['micro avg']['f1-score'].toFixed(3)}</td><td>{result.classification_report['macro avg']['f1-score'].toFixed(3)}</td></tr>)}</tbody></table></div><p>{textClassifiers.train_records.toLocaleString()} training records and {textClassifiers.validation_records.toLocaleString()} validation records. Threshold selection uses validation only; final test labels are untouched. Predictions remain separate from source metadata.</p></section>}
      {!textClassifiers && classifiers && (
        <section className="info-panel">
          <h3>Supervised genre classification experiment</h3>
          <p>
            TF-IDF with one-vs-rest logistic regression. Held-out labels remain
            separate from catalog genres and retrieval. Features contain title
            text only, with no appended genre labels.
          </p>
          {Object.entries(classifiers).map(([domain, experiment]) => (
            <p key={domain}>
              <strong>{label(domain)}:</strong>{" "}
              {experiment.status === "measured"
                ? `Micro F1 ${experiment.micro_avg["f1-score"].toFixed(3)} · macro F1 ${experiment.macro_avg["f1-score"].toFixed(3)} · ${experiment.test_records.toLocaleString()} held-out records.`
                : `Skipped. ${experiment.reason}`}
            </p>
          ))}
        </section>
      )}
      <section className="info-panel">
        <h3>Add human relevance judgments</h3>
        <p>
          Download the candidates, rate each title 0 (not relevant), 1 (partly
          relevant), or 2 (clearly relevant), then upload your sheet. Leave only
          genuinely unreviewed items blank. Uploaded ratings are scored
          separately from the benchmark and are not stored on the server.
        </p>
        <div className="evaluation-actions">
          <button
            className="secondary-button"
            disabled={pending}
            onClick={template}
          >
            <Download size={14} />
            Download judgment sheet
          </button>
          <label className="secondary-button upload-label">
            <Upload size={14} />
            Score a completed CSV
            <input
              type="file"
              accept=".csv,text/csv"
              aria-label="Upload relevance judgments"
              disabled={pending}
              onChange={(e) => upload(e.target.files?.[0])}
            />
          </label>
        </div>
        {error && (
          <p className="inline-error" role="alert">
            {error}
          </p>
        )}
        {scored && (
          <div className="judgment-output">
            <p>
              {scored.rating_count
                ? `${scored.rating_count} human ratings scored across ${scored.rows.length} query/domain/model groups.`
                : "No human ratings have been entered yet."}
            </p>
            {scored.rating_count > 0 && (
              <>
                <p>
                  Unrated items are excluded. Judged-item precision and MRR
                  describe only reviewed candidates; incomplete judgments cannot
                  establish catalog-wide recall.
                </p>
                <button
                  className="text-button"
                  onClick={() =>
                    download(scored.csv, "storyscout-human-evaluation.csv")
                  }
                >
                  Download per-query scores
                  <Download size={13} />
                </button>
              </>
            )}
          </div>
        )}
      </section>
    </>
  );
}
