"""Evaluate claim-support labels against explicitly annotated reference labels.

This evaluator scores classification agreement only. It does not establish legal,
factual, or semantic correctness of the underlying claims.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

LABELS = ("supports", "contradicts", "insufficient_evidence")
PREDICTION_LABELS = (*LABELS, "abstain")


def _validate(data: Any) -> None:
    if not isinstance(data, dict):
        raise ValueError("benchmark input must be a JSON object")
    if data.get("schema_version") != 1:
        raise ValueError("'schema_version' must be 1")
    if data.get("scope") != "claim_support_label_agreement":
        raise ValueError("'scope' must be 'claim_support_label_agreement'")
    if data.get("annotation_status") not in ("synthetic_demo", "independently_adjudicated"):
        raise ValueError("'annotation_status' must identify synthetic or independently adjudicated labels")
    examples = data.get("examples")
    if not isinstance(examples, list):
        raise ValueError("'examples' must be a list")
    seen: set[str] = set()
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            raise ValueError(f"example {index} must be an object")
        example_id = example.get("id")
        if not isinstance(example_id, str) or not example_id.strip():
            raise ValueError(f"example {index} must have a non-empty string id")
        if example_id in seen:
            raise ValueError(f"duplicate example id: {example_id}")
        seen.add(example_id)
        if example.get("reference_label") not in LABELS:
            raise ValueError(f"example {example_id!r} has an invalid reference_label")
        if example.get("system_label") not in PREDICTION_LABELS:
            raise ValueError(f"example {example_id!r} has an invalid system_label")


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    """Compute agreement, coverage, selective accuracy, and per-class metrics."""
    _validate(data)
    examples = data["examples"]
    matrix = {
        gold: {pred: 0 for pred in PREDICTION_LABELS}
        for gold in LABELS
    }
    for item in examples:
        matrix[item["reference_label"]][item["system_label"]] += 1

    total = len(examples)
    answered = sum(
        count
        for gold in LABELS
        for pred, count in matrix[gold].items()
        if pred != "abstain"
    )
    correct = sum(matrix[label][label] for label in LABELS)
    per_class: dict[str, dict[str, float | int | None]] = {}
    f1_values: list[float] = []

    for label in LABELS:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in LABELS if other != label)
        fn = sum(matrix[label][other] for other in PREDICTION_LABELS if other != label)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        # F1 is defined whenever the class has at least one true or predicted
        # example. In that case, zero true positives must contribute F1 = 0.
        f1_denominator = 2 * tp + fp + fn
        f1 = 2 * tp / f1_denominator if f1_denominator else None
        per_class[label] = {
            "support": sum(matrix[label].values()),
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        }
        if f1 is not None:
            f1_values.append(f1)

    return {
        "scope": "claim_support_label_agreement",
        "annotation_status": data["annotation_status"],
        "warning": (
            "These metrics measure agreement with supplied labels only. They do not "
            "prove that labels are correct or that a legal/factual claim is true."
        ),
        "metrics": {
            "examples_total": total,
            "examples_answered": answered,
            "coverage": round(answered / total, 4) if total else None,
            "correct_labels": correct,
            "accuracy_including_abstentions_as_incorrect": (
                round(correct / total, 4) if total else None
            ),
            "selective_accuracy_on_answered": (
                round(correct / answered, 4) if answered else None
            ),
            "macro_f1_over_defined_classes": (
                round(sum(f1_values) / len(f1_values), 4) if f1_values else None
            ),
        },
        "confusion_matrix_reference_rows_system_columns": matrix,
        "per_class": per_class,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate VeriSight claim-support label agreement against reference annotations."
    )
    parser.add_argument("case_file", type=Path)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.case_file.read_text(encoding="utf-8"))
        result = evaluate(data)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Benchmark input error: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
