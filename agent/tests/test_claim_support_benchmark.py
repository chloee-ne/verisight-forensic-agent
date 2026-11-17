"""Tests for claim-support label-agreement metrics."""
from __future__ import annotations

import unittest

from benchmark.evaluate_claim_support import evaluate


class ClaimSupportAgreementTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = {
            "schema_version": 1,
            "scope": "claim_support_label_agreement",
            "annotation_status": "synthetic_demo",
            "examples": [
                {"id": "a", "reference_label": "supports", "system_label": "supports"},
                {"id": "b", "reference_label": "supports", "system_label": "contradicts"},
                {"id": "c", "reference_label": "contradicts", "system_label": "contradicts"},
                {"id": "d", "reference_label": "insufficient_evidence", "system_label": "abstain"},
            ],
        }

    def test_metrics_and_confusion_matrix(self) -> None:
        result = evaluate(self.data)
        metrics = result["metrics"]
        self.assertEqual(4, metrics["examples_total"])
        self.assertEqual(3, metrics["examples_answered"])
        self.assertEqual(0.75, metrics["coverage"])
        self.assertEqual(2, metrics["correct_labels"])
        self.assertEqual(0.5, metrics["accuracy_including_abstentions_as_incorrect"])
        self.assertEqual(round(2 / 3, 4), metrics["selective_accuracy_on_answered"])
        self.assertEqual(1, result["confusion_matrix_reference_rows_system_columns"]["insufficient_evidence"]["abstain"])

    def test_empty_examples_use_null_ratios(self) -> None:
        result = evaluate({**self.data, "examples": []})
        self.assertIsNone(result["metrics"]["coverage"])
        self.assertIsNone(result["metrics"]["accuracy_including_abstentions_as_incorrect"])
        self.assertIsNone(result["metrics"]["selective_accuracy_on_answered"])

    def test_invalid_label_is_rejected(self) -> None:
        bad = {**self.data, "examples": [
            {"id": "bad", "reference_label": "maybe", "system_label": "supports"}
        ]}
        with self.assertRaisesRegex(ValueError, "reference_label"):
            evaluate(bad)

    def test_duplicate_ids_are_rejected(self) -> None:
        bad = {**self.data, "examples": [
            {"id": "same", "reference_label": "supports", "system_label": "supports"},
            {"id": "same", "reference_label": "supports", "system_label": "supports"},
        ]}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate(bad)

    def test_unknown_annotation_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "annotation_status"):
            evaluate({**self.data, "annotation_status": "unverified"})

    def test_abstention_reduces_coverage(self) -> None:
        result = evaluate(self.data)
        self.assertEqual(0.75, result["metrics"]["coverage"])
        self.assertEqual(0.6667, result["metrics"]["selective_accuracy_on_answered"])

    def test_macro_f1_counts_observed_class_with_no_true_positives_as_zero(self) -> None:
        data = {
            **self.data,
            "examples": [
                {"id": "missed", "reference_label": "supports", "system_label": "contradicts"}
            ],
        }
        result = evaluate(data)
        self.assertEqual(0.0, result["per_class"]["supports"]["f1"])
        self.assertEqual(0.0, result["per_class"]["contradicts"]["f1"])
        self.assertIsNone(result["per_class"]["insufficient_evidence"]["f1"])
        self.assertEqual(0.0, result["metrics"]["macro_f1_over_defined_classes"])


if __name__ == "__main__":
    unittest.main()
