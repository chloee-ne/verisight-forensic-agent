from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from reporting import ReportError, build_report_html, export_report


class ReportingTests(unittest.TestCase):
    def sample(self):
        return {
            "run_id": "run-demo-123",
            "progress": {"status": "awaiting_signoff", "verification": True},
            "case": {
                "checklist": {
                    "cap": {"question": "What is the stated cap?", "status": "proven", "facts": ["F1"]},
                    "signature": {"question": "Who signed?", "status": "escalated", "facts": []},
                    "timing": {"question": "When?", "status": "open", "facts": []},
                },
                "facts": [
                    {
                        "id": "F1", "item": "cap", "document_id": "DOC-MSA", "page": 4,
                        "quote": "Liability cap: $1,000", "claim": "The stated cap is $1,000."
                    },
                    {
                        "id": "F2", "item": "privileged", "document_id": "DOC-PRIV", "page": 1,
                        "quote": "Secret attorney note", "claim": "Do not show."
                    },
                ],
                "flags": [{"kind": "privileged", "document_id": "DOC-PRIV"}],
                "signature_checks": [
                    {
                        "document_id": "DOC-CERT", "page": 2, "verdict": "consistent",
                        "reason": "Similar visible loops.", "reference": {"document_id": "DOC-REF", "page": 1},
                        "reference_review": {"decision": "pending"}
                    }
                ],
                "requests": [{"id": "R1", "status": "open"}],
                "memo": {"status": "awaiting_signoff", "conclusion": "Maybe.", "gaps": "Signature review pending."},
                "memo_checks": [{"check": "memo", "passed": False}],
            },
            "damages": None,
        }

    def test_report_uses_saved_state_and_does_not_invent_signoff(self):
        output = build_report_html(self.sample())
        self.assertIn("1 / 3", output)
        self.assertIn("awaiting_signoff", output)
        self.assertIn("Human sign-off:</strong> not recorded", output)
        self.assertIn("pending", output)
        self.assertNotIn("Attorney Signed Off", output)
        self.assertNotIn("83% Verified", output)

    def test_report_withholds_privileged_fact_and_escapes_html(self):
        data = self.sample()
        data["case"]["facts"][0]["quote"] = "<script>alert(1)</script>"
        output = build_report_html(data)
        self.assertNotIn("Secret attorney note", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>alert(1)</script>", output)

    def test_financial_panel_explicitly_says_not_verified(self):
        data = self.sample()
        data["damages"] = {
            "schema_version": 2,
            "run_id": "run-demo-123",
            "display": {
                "contract_cap": "$1,000.00",
                "stated_claim": "$2,500.00",
                "difference_vs_cap": "$1,500.00",
                "claim_to_cap_multiplier": "2.50x",
            },
            "legal_basis_statement": "Asserted exception",
            "sources": {
                "contract_cap": {"document_id": "DOC-MSA", "page": 4},
                "uncapped_claim": {"document_id": "DOC-CLAIM", "page": 1},
                "legal_basis": {"document_id": "DOC-MSA", "page": 12},
            },
            "limitations": ["Arithmetic only."],
        }
        output = build_report_html(data)
        self.assertIn("CALCULATED FROM SUPPLIED INPUTS · NOT VERIFIED", output)
        self.assertIn("$1,500.00", output)

    def test_export_requires_an_explicit_run_id_and_real_saved_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "missing.html"

            with self.assertRaises(TypeError):
                export_report(root, output=output)

            with self.assertRaises(ReportError):
                export_report(root, run_id="run-demo-123", output=output)

            self.assertFalse(output.exists())

            (root / "workspace/runs").mkdir(parents=True)
            (root / "workspace/case_records").mkdir(parents=True)
            run_dir = root / "workspace/runs/run-demo-123"
            run_dir.mkdir()
            (run_dir / "progress.json").write_text(
                json.dumps({"run_id": "run-demo-123", "status": "done", "started": "2026-11-10T00:00:00Z"})
            )
            sample_case = self.sample()["case"]
            sample_case["run_id"] = "run-demo-123"
            (root / "workspace/case_records/run-demo-123.json").write_text(
                json.dumps(sample_case)
            )
            output = root / "report.html"
            created = export_report(root, run_id="run-demo-123", output=output)
            self.assertEqual(output, created)
            self.assertTrue(output.is_file())
            self.assertIn("run-demo-123", output.read_text())


    def test_export_refuses_to_overwrite_existing_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "workspace/runs/run-demo-123").mkdir(parents=True)
            (root / "workspace/case_records").mkdir(parents=True)

            progress = {
                "run_id": "run-demo-123",
                "status": "done",
                "started": "2026-11-10T00:00:00Z",
            }
            case = self.sample()["case"]
            case["run_id"] = "run-demo-123"

            (root / "workspace/runs/run-demo-123/progress.json").write_text(
                json.dumps(progress), encoding="utf-8"
            )
            (root / "workspace/case_records/run-demo-123.json").write_text(
                json.dumps(case), encoding="utf-8"
            )

            output = root / "existing-report.html"
            original = "DO NOT OVERWRITE"
            output.write_text(original, encoding="utf-8")

            with self.assertRaises(ReportError):
                export_report(root, run_id="run-demo-123", output=output)

            self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_export_rejects_mismatched_case_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "workspace/runs/run-demo-123").mkdir(parents=True)
            (root / "workspace/case_records").mkdir(parents=True)

            (root / "workspace/runs/run-demo-123/progress.json").write_text(
                json.dumps({"run_id": "run-demo-123"}), encoding="utf-8"
            )
            (root / "workspace/case_records/run-demo-123.json").write_text(
                json.dumps({"run_id": "run-another-case"}), encoding="utf-8"
            )

            with self.assertRaises(ReportError):
                export_report(root, run_id="run-demo-123", output=root / "report.html")

            self.assertFalse((root / "report.html").exists())

    def test_export_rejects_invalid_run_id_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "report.html"

            with self.assertRaises(ReportError):
                export_report(root, run_id="../outside", output=output)

            self.assertFalse(output.exists())

    def test_proven_signature_check_item_displays_authenticity_caution(self):
        data = self.sample()

        self.assertNotIn(
            "Signature-authenticity caution",
            build_report_html(data),
        )

        data["case"]["checklist"]["signature"]["status"] = "proven"
        data["case"]["checklist"]["signature"]["needs_signature_check"] = True

        output = build_report_html(data)

        self.assertIn("Signature-authenticity caution", output)
        self.assertIn("not independent authentication", output)
        self.assertIn("does not establish signature authenticity", output)
        self.assertIn("Human review", output)

    def test_skipped_memo_verification_is_not_reported_as_passed(self):
        data = self.sample()
        data["case"]["memo_checks"] = [
            {"check": "claims", "passed": True, "status": "skipped"}
        ]

        output = build_report_html(data)

        self.assertIn(
            "Latest memo verification:</strong> skipped",
            output,
        )
        self.assertNotIn(
            "Latest memo verification:</strong> passed",
            output,
        )

    def test_unsubmitted_memo_reports_verification_history_without_misleading_status(self):
        data = self.sample()
        data["case"]["memo"] = None
        data["case"]["memo_checks"] = [
            {"check": "memo", "passed": False},
            {"check": "memo", "passed": False},
            {"check": "memo", "passed": False},
        ]

        output = build_report_html(data)

        self.assertIn("Memo status:</strong> not submitted", output)
        self.assertIn(
            "Latest memo verification:</strong> not applicable — no memo submitted",
            output,
        )
        self.assertIn("Memo verification attempts:</strong> 3", output)
        self.assertIn("Latest attempt:</strong> failed", output)
        self.assertIn("No memo has been submitted.", output)
        self.assertNotIn(
            "Latest memo verification:</strong> failed",
            output,
        )

    def test_submitted_memo_retains_failed_verification_status(self):
        data = self.sample()
        data["case"]["memo"] = {
            "status": "submitted",
            "conclusion": "Pending review.",
            "gaps": "Signature review.",
        }
        data["case"]["memo_checks"] = [
            {"check": "memo", "passed": False}
        ]

        output = build_report_html(data)

        self.assertIn("Memo status:</strong> submitted", output)
        self.assertIn(
            "Latest memo verification:</strong> failed",
            output,
        )


if __name__ == "__main__":
    unittest.main()
