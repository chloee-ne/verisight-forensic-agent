"""The verification layer (VERIFICATION=on): the checks you build in agent/verification/
(verify_checklist.py, verify_memo.py), and the tools running them inside a real run of the agent loop,
with escalation, resume, attorney sign-off, ./helper verify, and continuing from a checklist."""

from __future__ import annotations

import json
import os
import unittest

from types import SimpleNamespace
from unittest.mock import Mock

from verification import verify_claims

from agent_kit import tools
from agent_kit.case_record import CaseRecord
from agent_kit.progress import branch, new_run
from agent_kit.settings import verification_enabled
from scripts import verify
from tests import support


ALL_INITIAL = list(support.INITIAL)
READ_ALL = (
    "analyze_document",
    {"document_ids": ALL_INITIAL, "request": "readiness, statements, signatures"},
)
FLAG = (
    "flag_privileged",
    {"document_id": "DOC-MEMO", "reason": "attorney work product"},
)
FACTS = [
    (
        "record_fact",
        {
            "item": "not_ready",
            "document_id": "DOC-REPORT",
            "page": 1,
            "quote": "Open Severity 1 defects: 21",
            "claim": "21 Sev-1 open",
        },
    ),
    (
        "record_fact",
        {
            "item": "ready_statement",
            "document_id": "DOC-MINUTES",
            "page": 1,
            "quote": "Mr. Lindgren confirmed the system is ready for go-live",
            "claim": "said ready",
        },
    ),
    (
        "record_fact",
        {
            "item": "seniority",
            "document_id": "DOC-MINUTES",
            "page": 1,
            "quote": "Erik Lindgren, Engagement Partner",
            "claim": "engagement partner",
        },
    ),
    (
        "record_fact",
        {
            "item": "counterevidence",
            "document_id": "DOC-REPORT",
            "page": 1,
            "quote": "Overall status is green",
            "claim": "reported green",
        },
    ),
]
ASK = (
    "request_evidence",
    {
        "item": "timing",
        "need": "Internal vendor readiness assessments dated before the go-live decision.",
    },
)
AFTER_RELEASE = [
    (
        "analyze_document",
        {
            "document_ids": ["DOC-DRAFT", "DOC-CERT"],
            "request": "what the vendor knew and who signed",
        },
    ),
    (
        "record_fact",
        {
            "item": "timing",
            "document_id": "DOC-DRAFT",
            "page": 1,
            "quote": "Recommendation: NO-GO",
            "claim": "internal no-go before the statement",
        },
    ),
    (
        "check_signatures",
        {
            "document_id": "DOC-CERT",
            "page": 1,
            "signer": "Dana Okafor",
            "reference_document_id": "DOC-REF",
            "reference_page": 1,
        },
    ),
    (
        "record_fact",
        {
            "item": "signatures",
            "document_id": "DOC-CERT",
            "page": 1,
            "quote": "I certify that all exit criteria have been satisfied",
            "claim": "cert presented as signed by Okafor",
        },
    ),
]


def cite(item, doc, quote):
    return {
        "item": item,
        "status": "proven",
        "summary": item,
        "citations": [{"document_id": doc, "page": 1, "quote": quote}],
    }


GOOD_MEMO = (
    "submit_memo",
    {
        "conclusion": "Yes.",
        "gaps": "None.",
        "findings": [
            cite("not_ready", "DOC-REPORT", "Open Severity 1 defects: 21"),
            cite(
                "ready_statement",
                "DOC-MINUTES",
                "Mr. Lindgren confirmed the system is ready for go-live",
            ),
            cite("timing", "DOC-DRAFT", "Recommendation: NO-GO"),
            cite("seniority", "DOC-MINUTES", "Erik Lindgren, Engagement Partner"),
            cite(
                "signatures",
                "DOC-CERT",
                "I certify that all exit criteria have been satisfied",
            ),
            cite("counterevidence", "DOC-REPORT", "Overall status is green"),
        ],
    },
)
EARLY_MEMO = (
    "submit_memo",
    {
        "conclusion": "Yes.",
        "gaps": "",
        "findings": [
            cite(
                "timing",
                "DOC-MINUTES",
                "Mr. Lindgren confirmed the system is ready for go-live",
            )
        ],
    },
)


SKIP = unittest.skipUnless(
    verification_enabled(),
    "verification layer tests (VERIFICATION=on, or ./helper test --verification)",
)
GROUND_TRUTH_TEXT = [g["question"] for g in support.GROUND_TRUTH]


def context(root, client, run_id: str = "") -> tools.Context:
    run_id = run_id or new_run(root, instructions="i", objective="o")
    return tools.Context(client, root, run_id, CaseRecord(root, run_id), True)

@SKIP
class VerifyClaimsFailureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.memo = {
            "findings": [
                {
                    "item": "timing",
                    "status": "proven",
                    "summary": "The vendor issued a no-go recommendation.",
                    "citations": [
                        {"quote": "Recommendation: NO-GO"}
                    ],
                }
            ]
        }

    def run_check(self, output_text: str):
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(output_text=output_text)
                )
            )
        )
        ctx = SimpleNamespace(client=client)
        return verify_claims.run_verification(ctx, self.memo)

    def test_valid_empty_unsupported_list_passes(self) -> None:
        result = self.run_check('{"unsupported": []}')
        self.assertTrue(result["passed"])
        self.assertEqual([], result["feedback"])

    def test_unsupported_claim_fails(self) -> None:
        result = self.run_check(
            '{"unsupported": [{"item": "timing", '
            '"reason": "the quote does not establish a date"}]}'
        )
        self.assertFalse(result["passed"])
        self.assertIn("timing", result["feedback"][0])

    def test_unknown_item_fails_closed(self) -> None:
        result = self.run_check(
            '{"unsupported": [{"item": "fake_item", '
            '"reason": "unsupported"}]}'
        )
        self.assertFalse(result["passed"])
        self.assertIn("unknown memo item", result["feedback"][0])

    def test_non_string_response_fails_closed(self) -> None:
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(
                    return_value=SimpleNamespace(output_text=None)
                )
            )
        )
        ctx = SimpleNamespace(client=client)

        result = verify_claims.run_verification(ctx, self.memo)

        self.assertFalse(result["passed"])
        self.assertIn("no readable response", result["feedback"][0])
    def test_invalid_json_fails_closed(self) -> None:
        result = self.run_check("not valid JSON")
        self.assertFalse(result["passed"])
        self.assertIn("invalid JSON", result["feedback"][0])

    def test_missing_unsupported_field_fails_closed(self) -> None:
        result = self.run_check('{"result": "supported"}')
        self.assertFalse(result["passed"])
        self.assertIn("unsupported", result["feedback"][0])

    def test_non_list_unsupported_fails_closed(self) -> None:
        result = self.run_check('{"unsupported": "none"}')
        self.assertFalse(result["passed"])
        self.assertIn("'unsupported' list", result["feedback"][0])

    def test_unsupported_entry_missing_fields_fails_closed(self) -> None:
        result = self.run_check(
            '{"unsupported": [{"item": "timing"}]}'
        )
        self.assertFalse(result["passed"])
        self.assertIn("non-empty string fields", result["feedback"][0])
    def test_model_api_failure_fails_closed(self) -> None:
        client = SimpleNamespace(
            responses=SimpleNamespace(
                create=Mock(side_effect=RuntimeError("API unavailable"))
            )
        )
        ctx = SimpleNamespace(client=client)

        result = verify_claims.run_verification(ctx, self.memo)

        self.assertFalse(result["passed"])
        self.assertIn("API failed", result["feedback"][0])

class VerifyHelperOrderTest(unittest.TestCase):
    def test_claims_check_is_skipped_when_memo_rules_fail(self) -> None:
        ctx = SimpleNamespace(
            case=SimpleNamespace(
                data={
                    "memo": {
                        "conclusion": "Test",
                        "findings": [],
                        "gaps": [],
                    }
                }
            )
        )

        rules = SimpleNamespace(
            run_verification=Mock(
                return_value={
                    "passed": False,
                    "feedback": ["memo rules failed"],
                }
            )
        )
        claims_check = Mock()

        original_import = verify.importlib.import_module
        original_claims = verify.verify_claims.run_verification

        try:
            verify.importlib.import_module = Mock(return_value=rules)
            verify.verify_claims.run_verification = claims_check
            result = verify.verify_memo(ctx)
        finally:
            verify.importlib.import_module = original_import
            verify.verify_claims.run_verification = original_claims

        self.assertFalse(result["passed"])
        self.assertIn("memo rules failed", result["rules"])
        claims_check.assert_not_called()

class ChecklistCheckTest(unittest.TestCase):
    """verification/verify_checklist.py: the agent's checklist against the ground truth."""

    def setUp(self) -> None:
        from verification import verify_checklist

        self.verify = verify_checklist.run_verification
        self.root, tmp = support.make_root()
        self.addCleanup(tmp.cleanup)
        self.fake = support.scripted(self.root, [])
        self.ctx = context(self.root, self.fake.client)

    def test_a_complete_checklist_passes(self) -> None:
        result = self.verify(self.ctx, support.CHECKLIST_ITEMS)
        self.assertEqual(
            (True, 1.0, ""), (result["passed"], result["score"], result["feedback"])
        )

    def test_a_partial_checklist_fails_with_a_score_and_feedback(self) -> None:
        result = self.verify(self.ctx, support.PARTIAL_CHECKLIST[1]["items"])
        self.assertFalse(result["passed"])
        self.assertAlmostEqual(5 / 6, result["score"], places=2)
        self.assertTrue(result["feedback"])

    def test_the_judge_sees_the_ground_truth_but_the_feedback_does_not_repeat_it(
        self,
    ) -> None:
        result = self.verify(self.ctx, support.PARTIAL_CHECKLIST[1]["items"])
        judge = [c[1] for c in self.fake.calls if c[0] == "respond"][-1]
        self.assertIn(GROUND_TRUTH_TEXT[3], json.dumps(judge))
        self.assertFalse(
            [q for q in GROUND_TRUTH_TEXT if q.lower() in result["feedback"].lower()]
        )
        self.assertNotIn("seniority", result["feedback"])

    def test_no_ground_truth_passes(self) -> None:
        (self.root / "ground_truth/case.json").unlink()
        result = self.verify(self.ctx, support.PARTIAL_CHECKLIST[1]["items"])
        self.assertEqual((True, None), (result["passed"], result["score"]))

@SKIP
class MemoRulesTest(unittest.TestCase):
    """verification/verify_memo.py: the memo rules."""

    def setUp(self) -> None:
        from verification import verify_memo

        self.root, tmp = support.make_root()
        self.addCleanup(tmp.cleanup)
        self.fake = support.scripted(self.root, [])
        self.ctx = context(self.root, self.fake.client)
        self.case = self.ctx.case
        self.case.set_checklist(support.CHECKLIST_ITEMS)
        self.verify = verify_memo.run_verification

    def problems(self, memo: dict) -> list:
        result = self.verify(self.ctx, memo)
        self.assertEqual(not result["feedback"], result["passed"])
        return result["feedback"]

    def read(self, ids: list) -> None:
        from agent_kit.tools.analyze_document import analyze

        analyze(self.fake.client, self.root, ids, "x")

    def test_unsettled_items_and_unmatched_citations_are_problems(self) -> None:
        found = self.problems(EARLY_MEMO[1])
        self.assertTrue(any("neither proven nor escalated" in p for p in found))
        self.assertTrue(any("no matching recorded fact" in p for p in found))
        self.assertTrue(any("no finding for not_ready" in p for p in found))


    def test_malformed_memo_inputs_fail_closed(self) -> None:
        invalid_memos = [
            "not an object",
            {"findings": "not a list"},
            {"findings": [None]},
            {
                "findings": [
                    {
                        "item": "unknown_item",
                        "status": "proven",
                        "summary": "Unknown item",
                        "citations": [],
                    }
                ]
            },
            {
                "findings": [
                    {
                        "item": "not_ready",
                        "status": "proven",
                        "summary": "Invalid citations",
                        "citations": "not a list",
                    }
                ]
            },
            {
                "findings": [
                    {
                        "item": "not_ready",
                        "status": "proven",
                        "summary": "Invalid page",
                        "citations": [
                            {
                                "document_id": "DOC-REPORT",
                                "page": True,
                                "quote": "Some evidence",
                            }
                        ],
                    }
                ]
            },
        ]

        for memo in invalid_memos:
            with self.subTest(memo=memo):
                result = self.verify(self.ctx, memo)
                self.assertFalse(result["passed"])
                self.assertTrue(result["feedback"])


    def signature_finding(self) -> dict:
        support.release(self.root)
        self.read(["DOC-CERT"])
        quote = "I certify that all exit criteria have been satisfied"
        self.case.record_fact("signatures", "DOC-CERT", 1, quote, "c")
        return {"findings": [cite("signatures", "DOC-CERT", quote)]}

    def test_signature_items_need_a_signature_check_on_a_cited_document(self) -> None:
        memo = self.signature_finding()
        self.assertTrue(
            any("no cited document was checked" in p for p in self.problems(memo))
        )
        self.case.add_signature_check(
            {
                "document_id": "DOC-REF",
                "page": 1,
                "signer": "Dana Okafor",
                "verdict": "consistent",
            }
        )
        self.assertTrue(
            any("no cited document was checked" in p for p in self.problems(memo))
        )

    def test_a_proven_item_cannot_rest_on_an_inconsistent_signature(self) -> None:
        memo = self.signature_finding()
        self.case.add_signature_check(
            {
                "document_id": "DOC-CERT",
                "page": 1,
                "signer": "Dana Okafor",
                "verdict": "inconsistent",
                "reason": "different hand",
            }
        )
        found = self.problems(memo)
        self.assertTrue(
            any("DOC-CERT p1 is inconsistent" in p and "not proven" in p for p in found)
        )
        self.assertEqual("signature", self.case.data["flags"][0]["kind"])

    def test_confidential_documents_are_never_cited(self) -> None:
        self.read(["DOC-MEMO"])
        self.case.flag_privileged("DOC-MEMO", "work product")
        memo = {
            "findings": [
                cite(
                    "counterevidence",
                    "DOC-MEMO",
                    "Attorney work product for the review team",
                )
            ]
        }
        self.assertTrue(any("confidential" in p for p in self.problems(memo)))

    def test_an_open_request_is_a_problem(self) -> None:
        self.case.open_request(
            "timing", "the draft assessment", "missing_evidence", ALL_INITIAL
        )
        self.assertTrue(
            any("request is still open" in p for p in self.problems({"findings": []}))
        )

    def test_a_good_memo_has_no_problems(self) -> None:
        self.read(ALL_INITIAL)
        support.release(self.root)
        self.read(["DOC-DRAFT", "DOC-CERT"])
        for _name, args in FACTS + [AFTER_RELEASE[1], AFTER_RELEASE[3]]:
            fact: dict = dict(args)
            self.case.record_fact(
                fact["item"],
                fact["document_id"],
                fact["page"],
                fact["quote"],
                fact["claim"],
            )
        self.case.add_signature_check(
            {
                "document_id": "DOC-CERT",
                "page": 1,
                "signer": "Dana Okafor",
                "verdict": "consistent",
            }
        )
        self.assertEqual([], self.problems(GOOD_MEMO[1]))

    def test_duplicate_findings_for_the_same_item_are_rejected(self) -> None:
        self.read(["DOC-REPORT"])
        self.case.record_fact(
            "not_ready",
            "DOC-REPORT",
            1,
            "Open Severity 1 defects: 21",
            "21 Sev-1 defects remain open",
        )

        finding = cite(
            "not_ready",
            "DOC-REPORT",
            "Open Severity 1 defects: 21",
        )

        memo = {
            "findings": [
                finding,
                dict(finding),
            ]
        }

        found = self.problems(memo)

        self.assertTrue(
            any("duplicate" in problem.lower() for problem in found),
            found,
        )

    def test_a_fact_cannot_be_cited_for_a_different_checklist_item(self) -> None:
        self.read(["DOC-REPORT"])
        # Record a fact for the actual checklist item.
        self.case.record_fact(
            "not_ready",
            "DOC-REPORT",
            1,
            "Open Severity 1 defects: 21",
            "21 Sev-1 defects remain open",
        )

        # Mark counterevidence as proven using a different quote.
        self.case.record_fact(
            "counterevidence",
            "DOC-REPORT",
            1,
            "Overall status is green",
            "The report stated overall status was green",
        )

        # Incorrectly cite the not_ready fact under counterevidence.
        memo = {
            "findings": [
                cite(
                    "counterevidence",
                    "DOC-REPORT",
                    "Open Severity 1 defects: 21",
                )
            ]
        }

        found = self.problems(memo)

        self.assertTrue(
            any("no matching recorded fact" in problem for problem in found),
            found,
        )
    def test_a_proven_checklist_item_cannot_be_escalated_in_the_memo(self) -> None:
        self.read(["DOC-REPORT"])
        self.case.record_fact(
            "not_ready",
            "DOC-REPORT",
            1,
            "Open Severity 1 defects: 21",
            "21 Sev-1 defects remain open",
        )

        memo = {
            "findings": [
                {
                    "item": "not_ready",
                    "status": "escalated",
                    "summary": "The issue requires further investigation.",
                    "citations": [],
                }
            ]
        }

        found = self.problems(memo)

        self.assertTrue(
            any("not_ready" in problem for problem in found),
            found,
        )

@SKIP
class VerifiedRunTest(unittest.TestCase):
    """The tools running the checks inside a real run of the agent loop."""

    def setUp(self) -> None:
        from legal_agent.loop import resume_run, run_agent

        self.run_agent, self.resume_run = run_agent, resume_run
        self.root, tmp = support.make_root()
        self.addCleanup(tmp.cleanup)

    def initial(self) -> list:
        return [support.CHECKLIST, READ_ALL, FLAG, *FACTS, EARLY_MEMO, ASK]

    def tool_results(self, run_id: str, name: str) -> list:
        return [
            out for n, _args, out in support.tool_calls(self.root, run_id) if n == name
        ]

    def test_verification_tools_are_offered(self) -> None:
        fake = support.scripted(self.root, [support.CHECKLIST])
        self.run_agent(root=self.root, client=fake.client, turns=1)
        offered = {t["name"] for t in support.first_agent_request(fake)["tools"]}
        self.assertTrue(
            {"flag_privileged", "request_evidence", "check_signatures"} <= offered
        )

    def test_an_incomplete_checklist_gets_feedback_not_the_ground_truth(self) -> None:
        fake = support.scripted(
            self.root, [support.PARTIAL_CHECKLIST, support.CHECKLIST, READ_ALL]
        )
        result = self.run_agent(root=self.root, client=fake.client, turns=3)
        refused = self.tool_results(result["run_id"], "set_checklist")[0]
        self.assertEqual({"error", "feedback"}, set(refused))
        sent = json.dumps(support.agent_requests(fake))
        self.assertFalse([q for q in GROUND_TRUTH_TEXT if q in sent])
        self.assertNotIn("score", sent)
        case = support.case(self.root, result["run_id"])
        self.assertEqual([False, True], [c["passed"] for c in case["checklist_checks"]])
        self.assertAlmostEqual(0.83, case["checklist_checks"][0]["score"], places=2)
        self.assertTrue(case["checklist"]["seniority"]["added_after_check"])

    def test_the_checklist_is_accepted_after_three_refusals(self) -> None:
        partial = support.PARTIAL_CHECKLIST
        fake = support.scripted(self.root, [partial, partial, partial, READ_ALL])
        result = self.run_agent(root=self.root, client=fake.client, turns=4)
        case = support.case(self.root, result["run_id"])
        self.assertEqual(5, len(case["checklist"]))
        last = case["checklist_checks"][-1]
        self.assertEqual(
            (False, True, 3), (last["passed"], last["accepted"], last["attempt"])
        )

    def test_early_memo_is_refused_and_missing_evidence_escalates(self) -> None:
        fake = support.scripted(self.root, self.initial())
        result = self.run_agent(root=self.root, client=fake.client, turns=20)
        self.assertEqual("needs_input", result["status"])
        refused = self.tool_results(result["run_id"], "submit_memo")[0]
        self.assertEqual("memo", refused["check"])
        case = support.case(self.root, result["run_id"])
        self.assertEqual(
            ("timing", "missing_evidence"),
            (case["requests"][0]["item"], case["requests"][0]["rule"]),
        )
        self.assertIsNone(case["memo"])

    def test_escalating_before_reading_everything_is_refused(self) -> None:
        fake = support.scripted(self.root, [support.CHECKLIST, ASK])
        result = self.run_agent(root=self.root, client=fake.client, turns=2)
        self.assertIn(
            "read every visible document",
            self.tool_results(result["run_id"], "request_evidence")[0]["error"],
        )

    def test_resume_without_new_evidence_makes_no_model_call(self) -> None:
        fake = support.scripted(self.root, self.initial())
        result = self.run_agent(root=self.root, client=fake.client, turns=20)
        before = len(fake.calls)
        resumed = self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=5
        )
        self.assertEqual("needs_input", resumed["status"])
        self.assertIn("nothing new", resumed["note"])
        self.assertEqual(before, len(fake.calls))

    def test_release_resume_verified_memo_then_signoff(self) -> None:
        fake = support.scripted(self.root, self.initial() + AFTER_RELEASE + [GOOD_MEMO])
        result = self.run_agent(root=self.root, client=fake.client, turns=20)
        support.release(self.root)
        resumed = self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=10
        )
        self.assertEqual(
            (result["run_id"], "awaiting_signoff"),
            (resumed["run_id"], resumed["status"]),
        )
        first_after = support.agent_requests(fake)[len(self.initial())]
        self.assertIn(
            "Released documents: DOC-CERT, DOC-DRAFT", json.dumps(first_after["input"])
        )
        case = CaseRecord(self.root, result["run_id"])
        self.assertEqual("awaiting_signoff", case.data["memo"]["status"])
        self.assertEqual(
            ["memo", "memo", "claims"], [c["check"] for c in case.data["memo_checks"]]
        )
        self.assertEqual("consistent", case.data["signature_checks"][0]["verdict"])
        case.review_memo(True, "approved")
        done = self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=5
        )
        self.assertEqual("done", done["status"])
        self.assertEqual(
            "done", support.progress(self.root, result["run_id"])["status"]
        )

    def test_a_rejected_memo_goes_back_to_the_agent(self) -> None:
        fake = support.scripted(
            self.root, self.initial() + AFTER_RELEASE + [GOOD_MEMO, GOOD_MEMO]
        )
        result = self.run_agent(root=self.root, client=fake.client, turns=20)
        support.release(self.root)
        self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=10
        )
        CaseRecord(self.root, result["run_id"]).review_memo(
            False, "Explain the counterevidence more fully."
        )
        again = self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=5
        )
        self.assertEqual("awaiting_signoff", again["status"])
        self.assertIn("rejected", str(support.agent_requests(fake)[-1]["input"]))

    def test_unsupported_claims_refuse_the_memo(self) -> None:
        fake = support.scripted(
            self.root,
            self.initial() + AFTER_RELEASE + [GOOD_MEMO],
            unsupported=lambda text: [
                {"item": "timing", "reason": "the quote gives no date"}
            ],
        )
        result = self.run_agent(root=self.root, client=fake.client, turns=20)
        support.release(self.root)
        resumed = self.resume_run(
            root=self.root, run_id=result["run_id"], client=fake.client, turns=10
        )
        refused = self.tool_results(result["run_id"], "submit_memo")[-1]
        self.assertEqual("claims", refused["check"])
        self.assertNotEqual("awaiting_signoff", resumed["status"])

    def test_three_refused_memos_escalate_to_a_person(self) -> None:
        fake = support.scripted(
            self.root, [support.CHECKLIST, READ_ALL, EARLY_MEMO, EARLY_MEMO, EARLY_MEMO]
        )
        result = self.run_agent(root=self.root, client=fake.client, turns=10)
        self.assertEqual(("needs_input", 5), (result["status"], result["turn"]))
        self.assertEqual(
            "memo_refused",
            support.case(self.root, result["run_id"])["requests"][0]["rule"],
        )

    def test_a_flagged_document_cannot_be_read_again(self) -> None:
        reread = ("analyze_document", {"document_ids": ["DOC-MEMO"], "request": "x"})
        fake = support.scripted(self.root, [support.CHECKLIST, READ_ALL, FLAG, reread])
        result = self.run_agent(root=self.root, client=fake.client, turns=4)
        self.assertIn(
            "confidential",
            self.tool_results(result["run_id"], "analyze_document")[-1]["error"],
        )


@SKIP
class ContinueFromSessionOneTest(unittest.TestCase):
    """./helper verify on a finished Session 1 run, then ./helper branch from its checklist."""

    def setUp(self) -> None:
        from legal_agent.loop import resume_run, run_agent

        self.run_agent, self.resume_run = run_agent, resume_run
        self.root, tmp = support.make_root()
        self.addCleanup(tmp.cleanup)

    def test_verify_finds_the_memo_and_checklist_problems(self) -> None:
        run_id = self._session_one()
        fake = support.scripted(self.root, [])
        memo = verify.verify_memo(verify.context(fake.client, self.root, run_id))
        self.assertFalse(memo["passed"])
        self.assertTrue(any("no finding" in p for p in memo["rules"]))
        checklist = verify.verify_checklist(
            verify.context(fake.client, self.root, run_id)
        )
        self.assertFalse(checklist["passed"])
        self.assertAlmostEqual(0.83, checklist["score"], places=2)
        self.assertTrue(checklist["feedback"])
        self.assertEqual(
            "answered", support.progress(self.root, run_id)["status"]
        )  # the run is unchanged

    def test_branch_continues_from_the_checklist_with_verification_on(self) -> None:
        run_id = self._session_one()
        fake = support.scripted(self.root, [support.CHECKLIST, support.PLAN, READ_ALL])
        new_id = branch(fake.client, self.root, run_id)
        self.assertNotEqual(run_id, new_id)
        progress = support.progress(self.root, new_id)
        refused = json.loads(progress["messages"][-1]["output"])
        self.assertEqual({"error", "feedback"}, set(refused))
        self.assertEqual(
            (True, "paused", 0),
            (progress["verification"], progress["status"], progress["turn"]),
        )
        self.assertEqual(run_id, progress["notes"]["branched_from"])
        self.assertEqual("set_checklist", progress["messages"][-2]["name"])
        resumed = self.resume_run(
            root=self.root, run_id=new_id, client=fake.client, turns=3
        )
        self.assertEqual("paused", resumed["status"])
        first = support.agent_requests(fake)[0]
        self.assertIn("verification layer on", json.dumps(first["input"]))
        self.assertEqual(
            "checklist refused", json.loads(first["input"][-2]["output"])["error"]
        )
        case = support.case(self.root, new_id)
        self.assertEqual([False, True], [c["passed"] for c in case["checklist_checks"]])
        self.assertEqual(6, len(case["checklist"]))
        self.assertEqual(
            5, len(support.case(self.root, run_id)["checklist"])
        )  # the Session 1 run is unchanged

    def _session_one(self) -> str:
        os.environ["VERIFICATION"] = "off"
        try:
            fake = support.scripted(
                self.root,
                [support.PARTIAL_CHECKLIST, READ_ALL, FACTS[0], FACTS[1], EARLY_MEMO],
            )
            result = self.run_agent(root=self.root, client=fake.client, turns=10)
        finally:
            os.environ["VERIFICATION"] = "on"
        self.assertEqual("answered", result["status"])
        return result["run_id"]


if __name__ == "__main__":
    unittest.main()
