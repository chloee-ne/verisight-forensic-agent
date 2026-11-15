"""Deterministic citation-traceability benchmark for synthetic VeriSight cases.

This measures whether citations point to an available, non-privileged document page
and whether the quoted text appears on that page. It does NOT judge whether a quote
semantically proves a legal or factual claim.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


_SPACE = re.compile(r"\\s+")
_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u00a0": " ",
    }
)


def normalize(value: str) -> str:
    """Normalize whitespace, common typography, and case for quote matching."""
    return _SPACE.sub(" ", value.translate(_TRANSLATION)).strip().lower()


def _validate_case(case: dict[str, Any]) -> None:
    if not isinstance(case, dict):
        raise ValueError("benchmark case must be a JSON object")
    if not isinstance(case.get("documents"), dict):
        raise ValueError("'documents' must be an object keyed by document ID")
    if not isinstance(case.get("findings"), list):
        raise ValueError("'findings' must be a list")
    privileged = case.get("privileged_document_ids", [])
    if not isinstance(privileged, list) or any(not isinstance(x, str) for x in privileged):
        raise ValueError("'privileged_document_ids' must be a list of strings")
    for document_id, document in case["documents"].items():
        if not isinstance(document_id, str) or not isinstance(document, dict):
            raise ValueError("each document must be an object keyed by a string ID")
        pages = document.get("pages")
        if not isinstance(pages, list) or any(not isinstance(page, str) for page in pages):
            raise ValueError(f"document {document_id!r} must contain a list of page strings")
    for index, finding in enumerate(case["findings"]):
        if not isinstance(finding, dict):
            raise ValueError(f"finding {index + 1} must be an object")
        citations = finding.get("citations", [])
        if not isinstance(citations, list):
            raise ValueError(f"finding {index + 1} citations must be a list")
        for citation in citations:
            if not isinstance(citation, dict):
                raise ValueError(f"finding {index + 1} contains a non-object citation")


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    """Return citation-level and finding-level traceability metrics."""
    _validate_case(case)
    documents = case["documents"]
    privileged = set(case.get("privileged_document_ids", []))
    citation_results: list[dict[str, Any]] = []
    finding_results: list[dict[str, Any]] = []

    for index, finding in enumerate(case["findings"], start=1):
        finding_id = finding.get("id", f"finding-{index}")
        valid_for_finding = 0
        citations = finding.get("citations", [])

        for citation_index, citation in enumerate(citations, start=1):
            document_id = citation.get("document_id")
            page = citation.get("page")
            quote = citation.get("quote")
            reason = None

            if not isinstance(document_id, str) or not document_id:
                reason = "missing_document_id"
            elif document_id in privileged:
                reason = "privileged_document"
            elif document_id not in documents:
                reason = "unknown_document"
            elif isinstance(page, bool) or not isinstance(page, int):
                reason = "invalid_page_number"
            elif page < 1 or page > len(documents[document_id]["pages"]):
                reason = "page_out_of_range"
            elif not isinstance(quote, str) or len(normalize(quote)) < 8:
                reason = "quote_too_short_or_missing"
            elif normalize(quote) not in normalize(documents[document_id]["pages"][page - 1]):
                reason = "quote_not_found_on_page"

            valid = reason is None
            if valid:
                valid_for_finding += 1
            citation_results.append(
                {
                    "finding_id": finding_id,
                    "citation_index": citation_index,
                    "valid": valid,
                    "reason": reason,
                }
            )

        finding_results.append(
            {
                "finding_id": finding_id,
                "traceable": valid_for_finding > 0,
                "valid_citations": valid_for_finding,
                "citation_count": len(citations),
            }
        )

    citation_count = len(citation_results)
    valid_citations = sum(result["valid"] for result in citation_results)
    finding_count = len(finding_results)
    traceable_findings = sum(result["traceable"] for result in finding_results)

    return {
        "scope": "citation_traceability_only",
        "warning": (
            "A traceable quote is not proof that the quote supports the claim, "
            "that the source is authentic, or that a legal conclusion is correct."
        ),
        "metrics": {
            "citations_total": citation_count,
            "citations_valid": valid_citations,
            "citations_invalid": citation_count - valid_citations,
            "citation_precision": (
                round(valid_citations / citation_count, 4) if citation_count else None
            ),
            "findings_total": finding_count,
            "findings_traceable": traceable_findings,
            "findings_untraceable": finding_count - traceable_findings,
            "finding_traceability": (
                round(traceable_findings / finding_count, 4) if finding_count else None
            ),
        },
        "citations": citation_results,
        "findings": finding_results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate citation traceability in a synthetic VeriSight benchmark case."
    )
    parser.add_argument("case_file", type=Path, help="Path to a benchmark case JSON file")
    args = parser.parse_args(argv)

    try:
        case = json.loads(args.case_file.read_text(encoding="utf-8"))
        result = evaluate_case(case)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Benchmark input error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
