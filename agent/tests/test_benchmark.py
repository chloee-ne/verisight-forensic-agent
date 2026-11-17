"""Offline tests for the deterministic citation-traceability benchmark."""

from __future__ import annotations

import unittest

from benchmark.evaluate import evaluate_case


class CitationBenchmarkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "documents": {
                "DOC-A": {"pages": ["The supplier confirmed delivery on 12 May 2026."]},
                "DOC-PRIV": {"pages": ["Privileged legal advice for counsel only."]},
            },
            "privileged_document_ids": ["DOC-PRIV"],
            "findings": [
                {
                    "id": "valid",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 1,
                            "quote": "supplier confirmed delivery",
                        }
                    ],
                },
                {
                    "id": "bad-page",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 2,
                            "quote": "supplier confirmed delivery",
                        }
                    ],
                },
                {
                    "id": "invented",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 1,
                            "quote": "The supplier paid all invoices",
                        }
                    ],
                },
                {
                    "id": "privileged",
                    "citations": [
                        {
                            "document_id": "DOC-PRIV",
                            "page": 1,
                            "quote": "Privileged legal advice",
                        }
                    ],
                },
                {"id": "no-citation", "citations": []},
            ],
        }

    def test_metrics_count_only_page_verified_non_privileged_quotes(self) -> None:
        result = evaluate_case(self.case)
        self.assertEqual(
            {
                "citations_total": 4,
                "citations_valid": 1,
                "citations_invalid": 3,
                "citation_precision": 0.25,
                "findings_total": 5,
                "findings_traceable": 1,
                "findings_untraceable": 4,
                "finding_traceability": 0.2,
            },
            result["metrics"],
        )
        self.assertEqual("citation_traceability_only", result["scope"])

    def test_invalid_citation_reasons_are_explicit(self) -> None:
        result = evaluate_case(self.case)
        reasons = [item["reason"] for item in result["citations"]]
        self.assertEqual(
            [None, "page_out_of_range", "quote_not_found_on_page", "privileged_document"],
            reasons,
        )

    def test_typographic_and_whitespace_normalization(self) -> None:
        case = {
            "documents": {"DOC-A": {"pages": ["The vendor’s  final   report is signed."]}},
            "findings": [
                {
                    "id": "normalized",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 1,
                            "quote": "vendor's final report",
                        }
                    ],
                }
            ],
        }
        self.assertTrue(evaluate_case(case)["findings"][0]["traceable"])

    def test_malformed_case_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "'documents'"):
            evaluate_case({"findings": []})

    def test_quote_embedded_inside_longer_word_is_rejected(self) -> None:
        case = {
            "documents": {"DOC-A": {"pages": ["Xsupplier confirmed deliveryY"]}},
            "findings": [
                {
                    "id": "partial-word",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 1,
                            "quote": "supplier confirmed delivery",
                        }
                    ],
                }
            ],
        }
        result = evaluate_case(case)
        self.assertFalse(result["findings"][0]["traceable"])
        self.assertEqual("quote_not_found_on_page", result["citations"][0]["reason"])

    def test_quote_with_surrounding_punctuation_is_accepted(self) -> None:
        case = {
            "documents": {"DOC-A": {"pages": ["The report states: “vendor confirmed delivery.”"]}},
            "findings": [
                {
                    "id": "punctuation",
                    "citations": [
                        {
                            "document_id": "DOC-A",
                            "page": 1,
                            "quote": "vendor confirmed delivery",
                        }
                    ],
                }
            ],
        }
        self.assertTrue(evaluate_case(case)["findings"][0]["traceable"])

    def test_empty_findings_have_undefined_ratio(self) -> None:
        result = evaluate_case({"documents": {}, "findings": []})
        self.assertIsNone(result["metrics"]["finding_traceability"])


if __name__ == "__main__":
    unittest.main()
