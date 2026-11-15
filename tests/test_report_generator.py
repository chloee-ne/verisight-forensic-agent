"""Integration tests for the legacy-compatible report export wrapper."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_forensics_and_export as generator


RUN_ID = "run-test-001"


class ReportGeneratorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

        self.agent_root = Path(self.temp.name)
        self.case_dir = self.agent_root / "workspace" / "case_records"
        self.progress_dir = self.agent_root / "workspace" / "runs" / RUN_ID

        self.case_dir.mkdir(parents=True)
        self.progress_dir.mkdir(parents=True)

        self.case = {
            "run_id": RUN_ID,
            "checklist": {
                "signature_authenticity": {
                    "status": "proven",
                    "question": "Was the signature authentic?",
                    "facts": ["F1"],
                }
            },
            "facts": [
                {
                    "id": "F1",
                    "item": "signature_authenticity",
                    "document_id": "DOC-1",
                    "page": 1,
                    "claim": "A signature appears on the document.",
                    "quote": "Signed",
                }
            ],
            "signature_checks": [
                {
                    "signer": "Test Signer",
                    "document_id": "DOC-1",
                    "page": 1,
                    "verdict": "consistent",
                    "reason": "Visual screening only.",
                    "reference": {"document_id": "REF-1", "page": 1},
                }
            ],
            "requests": [],
            "memo": None,
            "memo_checks": [],
        }

        self.progress = {
            "run_id": RUN_ID,
            "status": "needs_input",
            "model": "test-model",
            "verification": True,
        }

        self.write_data()

        self.patch = mock.patch.object(
            generator, "AGENT_ROOT", self.agent_root
        )
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write_data(self):
        (self.case_dir / f"{RUN_ID}.json").write_text(
            json.dumps(self.case), encoding="utf-8"
        )
        (self.progress_dir / "progress.json").write_text(
            json.dumps(self.progress), encoding="utf-8"
        )

    def test_legacy_command_uses_canonical_report_generator(self):
        output = self.agent_root / "canonical-report.html"

        result = generator.main(
            [RUN_ID, "--output", str(output)]
        )

        self.assertEqual(result, 0)
        self.assertTrue(output.is_file())

        report = output.read_text(encoding="utf-8")
        self.assertIn("Investigation Dossier", report)
        self.assertIn("Multimodal signature screening", report)
        self.assertIn("Evidence-linked investigation dossier", report)

    def test_consistent_screening_does_not_authenticate_signature(self):
        output = self.agent_root / "signature-report.html"

        generator.main([RUN_ID, "--output", str(output)])

        report = output.read_text(encoding="utf-8")
        self.assertIn("Visual screening does not authenticate a signature or establish signer identity.", report)
        self.assertIn("independently reviewed by a human.", report)

    def test_invalid_run_id_is_rejected_before_output_creation(self):
        output = self.agent_root / "must-not-exist.html"

        with self.assertRaises(SystemExit) as raised:
            generator.main(["../outside", "--output", str(output)])

        self.assertEqual(raised.exception.code, 2)
        self.assertFalse(output.exists())

    def test_existing_output_is_never_overwritten(self):
        output = self.agent_root / "existing-report.html"
        original = "KEEP THIS EXISTING FILE"
        output.write_text(original, encoding="utf-8")

        with self.assertRaises(SystemExit) as raised:
            generator.main([RUN_ID, "--output", str(output)])

        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_legacy_module_no_longer_has_independent_build_report(self):
        self.assertFalse(hasattr(generator, "build_report"))


if __name__ == "__main__":
    unittest.main()
