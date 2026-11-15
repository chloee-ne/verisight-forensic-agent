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
  in range, and a normalized quote of at least eight characters occurs on that page.
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
