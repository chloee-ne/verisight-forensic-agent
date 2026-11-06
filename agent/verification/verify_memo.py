"""The memo rules. Called when the agent calls submit_memo with VERIFICATION=on, and by
./helper verify RUN --memo.

    run_verification(ctx, memo) -> {"passed": bool, "feedback": [problem, ...]}
"""

from __future__ import annotations

from agent_kit.document_text import normalize


def _failure(message: str) -> dict:
    """Return a verification failure, never an approval."""
    return {"passed": False, "feedback": [message]}


def _validate_findings(memo: dict, checklist: dict) -> tuple | dict:
    """Validate memo structure before applying business rules."""
    raw_findings = memo.get("findings", [])

    if raw_findings is None:
        raw_findings = []

    if not isinstance(raw_findings, list):
        return _failure("memo findings must be a list")

    findings = {}
    problems = []

    for index, finding in enumerate(raw_findings):
        label = f"finding {index + 1}"

        if not isinstance(finding, dict):
            return _failure(f"{label} must be an object")

        item = finding.get("item")
        if not isinstance(item, str) or not item.strip():
            return _failure(
                f"{label} must contain a non-empty string 'item'"
            )

        if item not in checklist:
            return _failure(
                f"{label} references unknown checklist item '{item}'"
            )

        status = finding.get("status")
        if status not in ("proven", "not_proven", "escalated"):
            return _failure(
                f"{label} has an invalid status for checklist item '{item}'"
            )

        if not isinstance(finding.get("summary"), str):
            return _failure(
                f"{label} must contain a string 'summary'"
            )

        citations = finding.get("citations")
        if not isinstance(citations, list):
            return _failure(
                f"{label} must contain a list 'citations'"
            )

        if len(citations) > 3:
            return _failure(
                f"{label} contains more than 3 citations"
            )

        for citation_index, citation in enumerate(citations):
            citation_label = (
                f"{label} citation {citation_index + 1}"
            )

            if not isinstance(citation, dict):
                return _failure(
                    f"{citation_label} must be an object"
                )

            document_id = citation.get("document_id")
            if (
                not isinstance(document_id, str)
                or not document_id.strip()
            ):
                return _failure(
                    f"{citation_label} must contain a non-empty "
                    "'document_id'"
                )

            page = citation.get("page")
            if not isinstance(page, int) or isinstance(page, bool):
                return _failure(
                    f"{citation_label} must contain an integer 'page'"
                )

            quote = citation.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                return _failure(
                    f"{citation_label} must contain a non-empty string "
                    "'quote'"
                )

        if item in findings:
            problems.append(
                f"duplicate finding for checklist item {item}"
            )
            continue

        findings[item] = finding

    return findings, problems


def run_verification(ctx, memo: dict) -> dict:
    case = ctx.case
    checklist = case.data["checklist"]

    if not checklist:
        return {
            "passed": False,
            "feedback": [
                "there is no checklist yet: call set_checklist first"
            ],
        }

    if not isinstance(memo, dict):
        return _failure("memo must be an object")

    validation = _validate_findings(memo, checklist)

    if isinstance(validation, dict):
        return validation

    findings, problems = validation

    for item, entry in checklist.items():
        finding = findings.get(item)

        if finding is None:
            problems.append(f"no finding for {item}")
            continue

        problems += _item_problems(
            case,
            item,
            entry,
            finding,
        )

    if case.open_requests():
        problems.append("an evidence request is still open")

    return {
        "passed": not problems,
        "feedback": problems,
    }


def _item_problems(case, item: str, entry: dict, finding: dict) -> list:
    problems = []

    checklist_status = entry.get("status")
    finding_status = finding.get("status")
    proven = finding_status == "proven"
    citations = finding["citations"]

    if checklist_status == "open":
        problems.append(
            f"{item} is neither proven nor escalated: "
            "record a fact or call request_evidence"
        )
    elif checklist_status in ("proven", "escalated"):
        if finding_status != checklist_status:
            problems.append(
                f"{item} is {checklist_status} in the checklist "
                f"but {finding_status} in the memo"
            )
    else:
        problems.append(
            f"{item} has an invalid checklist status: {checklist_status}"
        )

    if proven and not citations:
        problems.append(
            f"{item} is marked proven but cites nothing"
        )

    if proven and entry.get("needs_signature_check"):
        problems += _signature_problems(
            case,
            item,
            citations,
        )

    for citation in citations:
        problems += _citation_problems(
            case,
            item,
            citation,
        )

    return problems


def _signature_problems(case, item: str, citations: list) -> list:
    cited = {
        citation["document_id"]
        for citation in citations
    }

    checks = [
        check
        for check in case.data["signature_checks"]
        if check.get("document_id") in cited
    ]

    if not checks:
        return [
            f"{item} rests on a signature, but no cited document "
            "was checked with check_signatures"
        ]

    return [
        f"{item} is marked proven, but the signature on "
        f"{check['document_id']} p{check.get('page')} is "
        f"{check.get('verdict')}: mark the item not proven "
        "and name it as a gap"
        for check in checks
        if check.get("verdict") != "consistent"
    ]


def _citation_problems(case, item: str, citation: dict) -> list:
    document_id = citation["document_id"]
    page = citation["page"]

    if case.flagged(document_id):
        return [
            f"{document_id} is confidential and can never be cited"
        ]

    quote = normalize(citation["quote"])

    if any(
        fact["item"] == item
        and fact["document_id"] == document_id
        and fact["page"] == page
        and normalize(fact["quote"]) == quote
        for fact in case.data["facts"]
    ):
        return []

    return [
        f"citation has no matching recorded fact for checklist item "
        f"{item}: {document_id} p{page}"
    ]
