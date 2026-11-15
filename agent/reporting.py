"""Build an HTML dossier from one saved VeriSight investigation run.

The exporter is deliberately offline: it never calls a model and never invents
checklist coverage, facts, approvals, signatures, or financial figures.
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUN_ID_RE = re.compile(r"^run-[A-Za-z0-9._-]{1,124}$")


class ReportError(ValueError):
    """The requested run cannot be exported safely."""


def list_run_ids(root: Path) -> list[str]:
    runs_dir = Path(root) / "workspace" / "runs"
    if not runs_dir.is_dir():
        return []
    return [
        folder.name
        for folder in runs_dir.iterdir()
        if folder.is_dir() and (folder / "progress.json").is_file()
    ]


def load_run(root: Path, run_id: str) -> dict[str, Any]:
    root = Path(root)
    if not RUN_ID_RE.fullmatch(run_id or ""):
        raise ReportError("Invalid run ID.")
    progress_path = root / "workspace" / "runs" / run_id / "progress.json"
    case_path = root / "workspace" / "case_records" / f"{run_id}.json"
    if not progress_path.is_file():
        raise ReportError(f"No saved progress file exists for run {run_id}.")
    if not case_path.is_file():
        raise ReportError(f"No case record exists for run {run_id}.")
    try:
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        case = json.loads(case_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReportError(f"Saved run data is invalid JSON: {error}") from None
    if not isinstance(progress, dict) or not isinstance(case, dict):
        raise ReportError("Saved run data must contain JSON objects for progress and case records.")

    if progress.get("run_id") != run_id:
        raise ReportError("Progress Run ID does not match the requested Run ID.")

    if case.get("run_id") != run_id:
        raise ReportError("Case record Run ID does not match the requested Run ID.")

    damages_path = progress_path.parent / "damages_quantification.json"
    damages = None
    if damages_path.is_file():
        try:
            candidate = json.loads(damages_path.read_text(encoding="utf-8"))
            if candidate.get("run_id") == run_id and candidate.get("schema_version") == 2:
                damages = candidate
        except (OSError, json.JSONDecodeError, AttributeError):
            damages = None

    return {"run_id": run_id, "progress": progress, "case": case, "damages": damages}


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _privileged_ids(case: dict) -> set[str]:
    return {
        document_id
        for flag in _as_list(_as_dict(case).get("flags"))
        if isinstance(flag, dict)
        and flag.get("kind") == "privileged"
        and isinstance((document_id := flag.get("document_id")), str)
    }


def _source_text(source: dict, hidden: set[str]) -> str:
    doc = source.get("document_id", "")
    if doc in hidden:
        return "Privileged source withheld"
    return f"{_e(doc)} · p.{_e(source.get('page', '—'))}"


def _render_checklist(case: dict) -> str:
    checklist = _as_dict(case.get("checklist"))
    if not checklist:
        return '<p class="muted">No checklist is recorded for this run.</p>'
    rows = []
    for item_id, entry in checklist.items():
        if not isinstance(entry, dict):
            continue
        status = entry.get("status", "unknown")
        question = entry.get("question", "")
        fact_ids = _as_list(entry.get("facts"))
        rows.append(
            "<tr>"
            f"<td>{_e(item_id)}</td><td>{_e(question)}</td>"
            f"<td><span class='status'>{_e(status)}</span></td>"
            f"<td>{len(fact_ids)}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Item</th><th>Question</th><th>Recorded status</th>"
        "<th>Fact IDs</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )



def _render_signature_status_warning(case: dict) -> str:
    checklist = _as_dict(case.get("checklist"))
    flagged = [
        item_id
        for item_id, entry in checklist.items()
        if isinstance(entry, dict)
        and entry.get("status") == "proven"
        and entry.get("needs_signature_check") is True
    ]

    if not flagged:
        return ""

    labels = ", ".join(_e(item_id) for item_id in flagged)

    return (
        '<p class="notice"><strong>Signature-authenticity caution:</strong> '
        f"The checklist records {labels} as proven, but this is an "
        "application-recorded status, not independent authentication. "
        "This report does not establish signature authenticity or signer "
        "identity. Human review of the signature and candidate reference "
        "is required.</p>"
    )

def _render_facts(case: dict) -> str:
    hidden = _privileged_ids(case)
    facts = [
        fact for fact in _as_list(case.get("facts"))
        if isinstance(fact, dict) and fact.get("document_id") not in hidden
    ]
    if not facts:
        return '<p class="muted">No non-privileged facts are recorded.</p>'
    rows = []
    for fact in facts:
        rows.append(
            "<tr>"
            f"<td>{_e(fact.get('id'))}</td><td>{_e(fact.get('item'))}</td>"
            f"<td>{_source_text(fact, hidden)}</td>"
            f"<td>{_e(fact.get('quote'))}</td>"
            f"<td>{_e(fact.get('claim'))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Fact</th><th>Checklist item</th><th>Source</th>"
        "<th>Recorded quotation</th><th>Agent interpretation</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_signatures(case: dict) -> str:
    hidden = _privileged_ids(case)
    checks = _as_list(case.get("signature_checks"))
    if not checks:
        return '<p class="muted">No signature-screening results are recorded.</p>'
    rows = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        target = check.get("document_id", "")
        reference = _as_dict(check.get("reference"))
        target_text = (
            "Privileged target withheld"
            if target in hidden
            else f"{_e(target)} · p.{_e(check.get('page'))}"
        )
        reference_text = (
            _source_text(reference, hidden) if reference else "No candidate reference recorded"
        )
        review = _as_dict(check.get("reference_review"))
        review_decision = review.get("decision", "not recorded")
        rows.append(
            "<tr>"
            f"<td>{target_text}</td><td>{reference_text}</td>"
            f"<td>{_e(check.get('verdict', 'unknown'))}</td>"
            f"<td>{_e(review_decision)}</td><td>{_e(check.get('reason', ''))}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Target</th><th>Candidate reference</th><th>Visual result</th>"
        "<th>Reference provenance review</th><th>Model note</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        + '<p class="notice">Visual screening does not authenticate a signature or establish signer identity. '
          "The candidate reference must be independently reviewed by a human.</p>"
    )


def _render_damages(damages: dict | None, hidden: set[str]) -> str:
    if not damages:
        return '<p class="muted">No source-linked calculation is recorded for this run.</p>'
    display = damages.get("display") or {}
    sources = damages.get("sources") or {}
    rows = [
        ("Stated contractual cap", display.get("contract_cap", "—"), sources.get("contract_cap")),
        ("Stated claim", display.get("stated_claim", "—"), sources.get("uncapped_claim")),
        ("Arithmetic difference vs. cap", display.get("difference_vs_cap", "—"), None),
        ("Claim-to-cap multiplier", display.get("claim_to_cap_multiplier", "—"), None),
    ]
    body = []
    for label, value, source in rows:
        source_html = _source_text(source, hidden) if isinstance(source, dict) else "—"
        body.append(
            f"<tr><td>{_e(label)}</td><td><strong>{_e(value)}</strong></td>"
            f"<td>{source_html}</td></tr>"
        )
    basis_source = sources.get("legal_basis")
    basis_html = (
        f"<p><strong>Recorded basis source:</strong> {_source_text(basis_source, hidden)}</p>"
        if isinstance(basis_source, dict)
        else ""
    )
    limitations = damages.get("limitations") or []
    notes = "".join(f"<li>{_e(note)}</li>" for note in limitations)
    return (
        "<p><span class='status warning'>CALCULATED FROM SUPPLIED INPUTS · NOT VERIFIED</span></p>"
        "<table><thead><tr><th>Measure</th><th>Value</th><th>Recorded source</th></tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
        + f"<p><strong>Asserted basis:</strong> {_e(damages.get('legal_basis_statement', ''))}</p>"
        + basis_html
        + "<h3>Interpretation limits</h3><ul>" + notes + "</ul>"
    )


def build_report_html(data: dict[str, Any]) -> str:
    run_id = data["run_id"]
    progress = _as_dict(data.get("progress"))
    case = _as_dict(data.get("case"))
    damages = data.get("damages")
    hidden = _privileged_ids(case)
    checklist = _as_dict(case.get("checklist"))
    statuses = {
        state: sum(
            1 for item in checklist.values()
            if isinstance(item, dict) and item.get("status") == state
        )
        for state in ("proven", "escalated", "open")
    }
    total = len(checklist)
    fact_count = sum(
        1 for fact in _as_list(case.get("facts"))
        if isinstance(fact, dict) and fact.get("document_id") not in hidden
    )
    open_requests = sum(
        1 for req in _as_list(case.get("requests"))
        if isinstance(req, dict) and req.get("status") == "open"
    )
    memo = _as_dict(case.get("memo"))
    memo_status = memo.get("status", "not submitted")
    review = _as_dict(memo.get("review"))
    review_status = review.get("decision", "not recorded")
    memo_checks = case.get("memo_checks") or []
    if not isinstance(memo_checks, list):
        memo_checks = []

    latest_memo_check = memo_checks[-1] if memo_checks else None

    memo_was_submitted = (
        bool(memo)
        and str(memo_status).strip().lower() not in ("", "not submitted")
    )

    if not memo_was_submitted:
        check_status = "not applicable — no memo submitted"
    else:
        check_status = (
            "passed" if isinstance(latest_memo_check, dict)
            and latest_memo_check.get("passed") is True
            else "failed" if isinstance(latest_memo_check, dict)
            else "not run"
        )

    memo_attempt_html = ""
    if not memo_was_submitted:
        if isinstance(latest_memo_check, dict):
            latest_attempt_status = (
                "passed" if latest_memo_check.get("passed") is True
                else "failed"
            )
        else:
            latest_attempt_status = "not run"

        memo_attempt_html = (
            f"<p><strong>Memo verification attempts:</strong> "
            f"{len(memo_checks)}</p>"
            f"<p><strong>Latest attempt:</strong> "
            f"{_e(latest_attempt_status)}</p>"
        )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    memo_html = (
        f"<p><strong>Conclusion:</strong> {_e(memo.get('conclusion', ''))}</p>"
        f"<p><strong>Remaining gaps:</strong> {_e(memo.get('gaps', ''))}</p>"
        if memo else '<p class="muted">No memo has been submitted.</p>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VeriSight AI — Investigation Dossier</title>
<style>
:root{{--bg:#0b1220;--panel:#121e30;--line:#2a3a50;--text:#edf4fb;--muted:#9db0c4;--accent:#65c4f1;--warn:#f0bf65;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;padding:32px}}
main{{max-width:1120px;margin:auto}}header{{border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:26px}}
h1{{font-size:28px;margin:0}}h2{{font-size:19px;margin:0 0 16px}}h3{{font-size:15px;color:var(--muted)}}
.muted{{color:var(--muted)}}.sub{{color:var(--muted);margin-top:5px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:22px 0}}
.card,.section{{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:19px;margin-bottom:18px}}
.metric{{font-size:27px;font-weight:700;color:var(--accent)}}.status{{display:inline-block;border:1px solid var(--line);border-radius:7px;padding:3px 8px;font-size:12px;color:var(--accent)}}.warning{{color:var(--warn);border-color:#806435}}
table{{width:100%;border-collapse:collapse;font-size:13px;overflow-wrap:anywhere}}th,td{{padding:10px 9px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}}th{{color:var(--muted);font-weight:600}}
.notice{{border-left:3px solid var(--warn);padding:9px 12px;color:var(--muted);background:#1a2534}}
footer{{color:var(--muted);font-size:12px;margin-top:28px}}@media(max-width:650px){{body{{padding:16px}}table{{display:block;overflow-x:auto}}}}
</style>
</head>
<body><main>
<header>
  <h1>VeriSight AI</h1>
  <div class="sub">Evidence-linked investigation dossier · Run {_e(run_id)}</div>
  <div class="sub">Generated {_e(generated)} · Status: {_e(progress.get('status', 'unknown'))} · Verification mode: {_e(progress.get('verification', 'unknown'))}</div>
</header>
<div class="grid">
  <div class="card"><h3>Checklist items recorded as proven</h3><div class="metric">{statuses['proven']} / {total}</div><div class="muted">Agent-recorded status; not an independent truth determination.</div></div>
  <div class="card"><h3>Escalated / open items</h3><div class="metric">{statuses['escalated']} / {statuses['open']}</div><div class="muted">Escalated / still open.</div></div>
  <div class="card"><h3>Recorded non-privileged facts</h3><div class="metric">{fact_count}</div><div class="muted">Quotations checked against extracted source-page text when recorded.</div></div>
  <div class="card"><h3>Open evidence requests</h3><div class="metric">{open_requests}</div><div class="muted">Requests still awaiting response.</div></div>
</div>
{_render_signature_status_warning(case)}
<section class="section"><h2>1. Checklist state</h2>{_render_checklist(case)}</section>
<section class="section"><h2>2. Recorded facts and source quotations</h2>{_render_facts(case)}</section>
<section class="section"><h2>3. Multimodal signature screening</h2>{_render_signatures(case)}</section>
<section class="section"><h2>4. Financial arithmetic</h2>{_render_damages(damages, hidden)}</section>
<section class="section"><h2>5. Memo and human review</h2>
<p><strong>Memo status:</strong> {_e(memo_status)}</p>
<p><strong>Human sign-off:</strong> {_e(review_status)}</p>
<p><strong>Latest memo verification:</strong> {_e(check_status)}</p>
{memo_attempt_html}
{memo_html}
</section>
<footer>
This dossier reports saved application records. It is not a forensic opinion, legal advice, proof of liability,
authentication of a signature, or a determination that claimed amounts are recoverable. AI outputs and
recorded facts require qualified human review. Privileged documents are omitted from the fact table.
</footer>
</main></body></html>"""


def export_report(root: Path, run_id: str, output: Path | None = None) -> Path:
    root = Path(root)

    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ReportError("A valid, explicit run ID is required.")

    data = load_run(root, run_id)
    html_text = build_report_html(data)

    target = (
        Path(output)
        if output is not None
        else root.parent / "VeriSight_Forensic_Report.html"
    )
    target.parent.mkdir(parents=True, exist_ok=True)

    # Exclusive creation prevents overwriting an existing report,
    # including when two export processes run concurrently.
    try:
        with target.open("x", encoding="utf-8", newline="") as handle:
            handle.write(html_text)
    except FileExistsError:
        raise ReportError(
            f"Refusing to overwrite existing file: {target}"
        ) from None

    return target
