# VeriSight Citation-Traceability Benchmark

This small, offline benchmark measures one narrow property: **whether a finding's
citations can be traced to text on the stated page of a known, non-privileged
document**.

It is deliberately separate from the Muse Spark checklist judge and claims judge.
It uses deterministic Python string matching and synthetic fixtures; it makes no
model calls and requires no API key.

## Run it

From the repository's `agent/` directory:

```bash
python -m benchmark.evaluate benchmark/sample_case.json
python -m unittest tests.test_benchmark -v
```

On Windows with the project virtual environment:

```bash
.venv/Scripts/python.exe -m benchmark.evaluate benchmark/sample_case.json
.venv/Scripts/python.exe -m unittest tests.test_benchmark -v
```

## Metrics

- **Citation precision:** valid citations divided by all citations. A citation is
  valid only when its document exists, it is not privileged, the page number is
  in range, and a normalized quote of at least eight characters occurs on that page. Quote matching enforces word boundaries, so a phrase embedded inside a longer word does not count as a match; surrounding punctuation is allowed.
- **Finding traceability:** findings with at least one valid citation divided by
  all findings. Findings with no citations are untraceable.
- **Failure reasons:** each invalid citation receives an explicit machine-readable
  reason, such as `unknown_document`, `page_out_of_range`,
  `quote_not_found_on_page`, or `privileged_document`.

If a denominator is zero, its ratio is reported as JSON `null`, not zero or 100%.

## Input format

A case is a JSON object with:
- `documents`: document ID to an object containing a `pages` list; page 1 is
  the first string in the list.
- `privileged_document_ids`: optional list of document IDs that cannot be cited.
- `findings`: list of finding objects with an optional `id` and a `citations`
  list. Each citation has `document_id`, integer `page`, and `quote`.

See `sample_case.json` for a fully synthetic example.

## Important interpretation limits

This benchmark does **not** establish:
- whether the quote logically or semantically supports the claim;
- whether the source document is authentic, complete, or admissible;
- whether the transcription matches the original image perfectly;
- whether a signature is genuine or who signed it;
- whether a legal, accounting, or forensic conclusion is correct.

A high score means only that the tested citations are traceable under this
fixture's deterministic rules. It is not a forensic accuracy score and must not
be presented as one. Expand the fixture set and obtain independent human
annotations before making broader performance claims.


## Claim-support label-agreement evaluator (experimental)

A separate evaluator, `benchmark.evaluate_claim_support`, computes agreement
between a system's exported claim-support label and a reference annotation. It
supports three reference labels: `supports`, `contradicts`, and
`insufficient_evidence`; the system may also return `abstain`.

Run from `agent/`:

```bash
.venv/Scripts/python.exe -m benchmark.evaluate_claim_support benchmark/claim_support_sample.json
.venv/Scripts/python.exe -m unittest tests.test_claim_support_benchmark -v
```

Reported metrics include coverage, accuracy (with abstentions counted as
incorrect), selective accuracy on answered examples, per-class precision/recall/F1,
and a confusion matrix. Macro-F1 includes every class with at least one reference
or predicted example; an observed class with no true positives contributes F1 = 0. The sample is explicitly marked `synthetic_demo`: its
labels are illustrative, not actual VeriSight model outputs or independent
human adjudications. For a real evaluation, export the system's actual labels
and have qualified reviewers independently adjudicate the reference labels
using a written annotation protocol. Keep disagreements and ambiguous cases
visible; do not silently convert them into a forced label.

This measures **label agreement only**. It does not establish that the reference
labels are correct, that a cited source is authentic, or that a legal/factual
claim is true. Do not combine this score with citation traceability into a
single "forensic accuracy" number.
