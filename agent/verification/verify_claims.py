"""Pre-built: is each finding supported by the quotes it cites?

Called by the submit_memo tool after verify_memo passes, and by ./helper verify RUN --memo.

    run_verification(ctx, memo) -> {"passed": bool, "feedback": [problem, ...]}

A failed or malformed model judgement must never approve a memo.
"""

from __future__ import annotations

import json

from agent_kit.settings import model

PROMPT = """CLAIMS TO CHECK. Each finding below states a claim and the exact quotes cited for it.
For each finding, decide whether the quotes support the claim as written. A claim that goes
beyond what its quotes say is unsupported.

{findings}

Answer only with JSON: {{"unsupported": [{{"item": "<item>", "reason": "one sentence"}}]}}
(an empty list when every claim is supported)."""


def _failure(message: str) -> dict:
    """Return a verification failure, never an approval."""
    return {"passed": False, "feedback": [message]}


def run_verification(ctx, memo: dict) -> dict:
    findings = [
        {
            "item": f.get("item"),
            "claim": f.get("summary", ""),
            "quotes": [c.get("quote", "") for c in f.get("citations") or []],
        }
        for f in memo.get("findings") or []
        if isinstance(f, dict)
        and f.get("status") == "proven"
        and f.get("citations")
    ]

    if not findings:
        return {"passed": True, "feedback": []}

    try:
        response = ctx.client.responses.create(
            model=model(),
            input=PROMPT.format(findings=json.dumps(findings, indent=1)),
            text={"format": {"type": "json_object"}},
        )
    except Exception as error:
        return _failure(
            f"Claims verification could not be completed because the model API failed: "
            f"{type(error).__name__}: {error}"
        )

    output_text = getattr(response, "output_text", None)
    if not isinstance(output_text, str) or not output_text.strip():
        return _failure(
            "Claims verification failed: the model returned no readable response."
        )

    try:
        result = json.loads(output_text)
    except (json.JSONDecodeError, TypeError):
        return _failure(
            "Claims verification failed: the model returned invalid JSON."
        )

    if not isinstance(result, dict):
        return _failure(
            "Claims verification failed: the response must be a JSON object."
        )

    if "unsupported" not in result or not isinstance(result["unsupported"], list):
        return _failure(
            "Claims verification failed: the response must contain an "
            "'unsupported' list."
        )

    valid_items = {finding["item"] for finding in findings}

    problems = []
    for index, finding in enumerate(result["unsupported"]):
        if not isinstance(finding, dict):
            return _failure(
                f"Claims verification failed: unsupported entry {index + 1} "
                "is not an object."
            )

        item = finding.get("item")
        reason = finding.get("reason")

        if (
            not isinstance(item, str)
            or not item.strip()
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            return _failure(
                f"Claims verification failed: unsupported entry {index + 1} "
                "must contain non-empty string fields 'item' and 'reason'."
            )

        if item not in valid_items:
            return _failure(
                f"Claims verification failed: unsupported entry {index + 1} "
                f"references unknown memo item '{item}'."
            )

        problems.append(
            f"{item}: the finding is not supported by its quotes ({reason})"
        )

    return {"passed": not problems, "feedback": problems}
