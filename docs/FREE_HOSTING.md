# StoryScout free hosting verification

The hosted build uses Render's `free` plan: one Docker web service in Singapore,
with 512 MB RAM and limited CPU. No paid compute or paid inference API is used.
The service is `srv-dbh16getlv9c73dk5jhg`; its assigned URL is
https://storyscout-eaw7.onrender.com. The public URL is live and verified; details are in `artifacts/deployment.json`.

## Preserved NLP

The official quantized ONNX export of all-MiniLM-L6-v2 replaces the heavier
PyTorch inference runtime in the hosted image. The same original tokenizer,
256-token limit, masked mean pooling and L2 normalization produce 384-dimensional
vectors for both domains. This is pretrained model inference, not new encoder
training. Six diagnostic comparisons to the original model produced cosine
similarities of 0.9922–0.9948; these are vector agreement measurements, not general
retrieval accuracy. Details: `artifacts/search_tuning/onnx_encoder_verification.json`.

TF-IDF, the locally trained plot-genre classifier's predictions, rule-based
intent/preference extraction, semantic mood/theme signals, hard filters,
cross-media references, MMR selection and unseen next picks remain implemented.
No API supplies recommendation lists or missing factual lengths/years.

## Compact catalog

- 1,000 books, retaining all demo/reference titles and 12 known page counts.
- 1,500 movies, including 1,451 source plots and all 1,322 known runtimes.
- Original source URLs, field provenance, unknown values, and usage terms remain.
- Selection is deterministic; the full source corpus remains in the repository
  and can be used with the full local profile.

## Executed compact benchmark

The same 44 developer-authored queries ran against this subset using its real
quantized semantic encoder. Mixed media are scored separately and macro-averaged.

| Method | P@5 | Recall@5 | MRR@5 | Hard compliance | Mean ms |
|---|---:|---:|---:|---:|---:|
| TF-IDF | 0.2519 | 0.6666 | 0.7111 | 1.000 | 12.0 |
| Semantic | 0.2888 | 0.7346 | 0.7515 | 1.000 | 17.4 |
| Hybrid | 0.2926 | 0.7500 | 0.7639 | 1.000 | 17.7 |

These timings are from the local workstation after indexing, not the free host.
The smaller candidate pool makes this a different experiment from the full
catalog; do not attribute the change solely to quantization. Judgments are
incomplete and not independent human evaluation. Full results and candidate CSV
are in `artifacts/compact/`, and the hosted Evaluation page selects those files.

Five preference-form genre edits with a 120-minute cap returned 25 distinct
titles, source-genre precision@5 1.00, and compliant runtimes. All next-pick groups
were nonempty and unseen. Three content topics survived length refinements.

## Resource and conversation checks

- 73 Python tests passed, including compact-profile loading and missing snapshot
  behavior, source constraints, fallback, state, and cache invalidation.
- The candidate Docker image ran with a hard **512 MB memory cap** and no swap.
  Observed working-set use after the checks was approximately **304 MiB**; the
  container stayed healthy and was not OOM-killed.
- All 7 real HTTP scenarios passed: book, movie, mixed, both cross-media
  directions, follow-up inheritance/exclusions, and reset.
- The same 7 scenarios passed with CPU additionally capped at **0.1**. Measured
  conversation times were approximately 0.6–1.5 seconds, excluding reset.
- Hugging Face/Transformers offline flags were enabled during container checks;
  cached local ONNX inference still reported hybrid search for both domains.

The container/API outputs are in `artifacts/compact/container_verification.json`
and `free_cpu_verification.json`. The final image also passed a cold start and all seven scenarios with both limits enforced from launch. Its peak cgroup memory was **303.3 MiB**, health was **healthy**, and OOM-killed was false. The native curl health probe avoids Python-process startup overhead under strict CPU limits. The startup checker allows 300 seconds; free cold starts can take minutes.

## Operational limits

Free hosting can sleep and take time to wake. Traffic shares one small CPU
instance; no uptime or concurrent-user latency guarantee is made. Conversations
and bookmarks are browser-local. Most book page counts and content-warning data
remain unknown. Use the Pipeline and Dataset pages to inspect active mode and
coverage. Paid deployment settings have been removed from the default blueprint.


## Public deployment verification

The live Render service reports `plan=free`, a compact 1,000/1,500 catalog,
ONNX encoding, hybrid search for both media and no external interpreter. Seven
public HTTP scenarios and all five preference/next-pick groups passed. A real
Brave browser submitted a mixed time-travel query, received six cards, and
requested six different follow-up titles without repeats. Saving The Time
Machine survived a page reload. At 390px mobile width, document width was also
390px; browser console had zero errors and warnings. Reports are under
`artifacts/compact/`; screenshots are ignored local files under output/playwright/.

GitHub: https://github.com/shivam2931120/StoryScout. Future application pushes to
main are connected to Render auto-deploy. No payment method or paid service was
created. The earlier full-catalog Docker verification remains historical.
