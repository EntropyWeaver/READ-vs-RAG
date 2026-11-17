import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from read_vs_rag.corpus import Corpus
from read_vs_rag.retrieval import Retriever
from read_vs_rag.runner import run_one
from read_vs_rag.selector import CHECKED, assess, review_candidate, run_cascade


class SelectorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name, "accounts.md")
        path.write_text("Amounts in crore\n(₹ in crore)\n| Description |2024-25|2023-24|\n"
                        "|Total Revenue Receipts|150.00|130.00|\n"
                        "Revenue Receipts of ₹ 90.00 crore (60 per cent of total Revenue Receipts).\n",
                        encoding="utf-8")
        self.corpus = Corpus(tmp.name)
        self.question_text = "What were total Revenue Receipts for 2024-25?"
        self.question = {"question": self.question_text, "unanswerable": False,
                         "expected_values": [{"value": 150, "unit": "crore"}], "reference_answer": "150 crore"}

    def stage(self, value, line, unit="crore"):
        entries = [line.as_dict() for line in self.corpus.lines("accounts.md", line, line)]
        return {"status": "ok", "error": None, "error_scope": None,
                "prediction": {"abstain": False, "answer": f"{value} {unit}",
                               "values": [{"value": value, "unit": unit}],
                               "citations": [{"doc": "accounts.md", "start": line, "end": line}]},
                "trace": [{"result": {"entries": entries}}],
                "scores": {"correct": value == 150 and unit == "crore", "unanswerable": False},
                "calls": [], "cost_usd": .01, "reserved_or_billed_usd": .01, "latency_s": 2,
                "input_tokens": 200, "output_tokens": 20, "thinking_tokens": 10, "evidence_chars": 200}

    def test_verified_hybrid_skips_read_and_respects_the_year(self):
        get_stage = Mock(return_value=self.stage(150, 4))
        result = run_cascade(self.question, self.corpus, "selector", get_stage)
        get_stage.assert_called_once_with("hybrid")
        self.assertEqual(result["routing"]["decision"], "hybrid")
        self.assertEqual(result["routing"]["stages"][0]["reason"], CHECKED)
        self.assertEqual(assess(self.question_text, self.stage(130, 4), self.corpus), "period_not_supported")
        self.assertEqual(assess(self.question_text, self.stage(150, 4, "inr"), self.corpus), "unit_not_supported")

    def test_subtotal_escalates_and_keeps_both_stage_costs(self):
        get_stage = Mock(side_effect=[self.stage(90, 5), self.stage(150, 4)])
        result = run_cascade(self.question, self.corpus, "selector", get_stage)
        self.assertEqual(result["routing"]["stages"][0]["reason"], "subtotal_or_total")
        self.assertEqual(result["routing"]["decision"], "read")
        self.assertEqual(result["cost_usd"], .02)
        self.assertEqual(result["latency_s"], 4)
        self.assertEqual([r["stage"] for r in result["trace"]], ["hybrid", "read"])

    def test_abstention_and_citations_that_model_did_not_see(self):
        wrong = self.stage(130, 4)
        wrong["trace"].clear()
        result = run_cascade(self.question, self.corpus, "selector", lambda stage: wrong)
        self.assertEqual(result["routing"]["decision"], "abstain")
        self.assertEqual(result["routing"]["stages"][0]["reason"], "citation_not_exposed")
        self.assertTrue(result["prediction"]["abstain"])
        self.assertFalse(result["scores"]["correct"])

    def test_reviewer_only_receives_question_prediction_and_evidence(self):
        provider = Mock()
        provider.config = {"max_output_tokens": 500}
        provider.pricing = {"input_per_million": 1, "output_per_million": 10}
        provider.ledger.spent_for.side_effect = [0, .001]
        provider.calls = []
        provider.generate.return_value = (
            {"parts": [{"text": '{"supported": false, "reason": "Wrong year column."}'}]}, {})
        budgets = {"max_input_tokens": 6000, "max_question_tokens": 10000, "max_question_cost_usd": .1}
        result, accepted, reason = review_candidate(
            self.question_text, self.stage(130, 4), self.corpus, provider, "study", budgets, 0)
        self.assertFalse(accepted)
        self.assertEqual(reason, "Wrong year column.")
        self.assertEqual(result["status"], "ok")
        _, messages, declarations = provider.generate.call_args.args
        self.assertEqual(declarations, [])
        data = json.loads(messages[0]["parts"][0]["text"])
        self.assertEqual(set(data), {"question", "proposal", "cited_text", "nearby_context"})
        self.assertEqual(data["cited_text"][0][1], 4)
        self.assertAlmostEqual(result["reserved_or_billed_usd"], .011)

    def test_runner_reviews_then_falls_back_and_counts_all_provider_calls(self):
        question = {**self.question, "id": "delta", "category": "arithmetic", "split": "test",
                    "question": "By how much did Total Revenue Receipts increase between 2023-24 and 2024-25?",
                    "expected_values": [{"value": 20, "unit": "crore"}]}
        provider = Mock()
        provider.config = {"max_output_tokens": 100}
        provider.pricing = {"input_per_million": 1, "output_per_million": 10}
        provider.ledger.spent_for.return_value = 0
        provider.calls = []
        payloads = iter([
            {"text": json.dumps(self.stage(60, 4)["prediction"])},
            {"text": '{"supported": false, "reason": "Incorrect subtraction."}'},
            {"functionCall": {"name": "memory_read", "args": {"doc": "accounts.md", "start": 1, "end": 4}}},
            {"text": json.dumps(self.stage(20, 4)["prediction"])},
            {"text": '{"supported": true, "reason": "150 minus 130."}'},
        ])

        def generate(instruction, contents, tools, **kwargs):
            usage = {"total_tokens": 120, "input_tokens": 100, "output_tokens": 20,
                     "thinking_tokens": 0, "cost_usd": .001, "tag": kwargs["tag"]}
            provider.calls.append(usage)
            return {"role": "model", "parts": [next(payloads)]}, usage

        provider.generate.side_effect = generate
        budgets = {"max_read_lines": 100, "max_tool_result_chars": 3000, "max_evidence_chars": 5000,
                   "max_model_calls": 2, "max_tool_calls": 2, "max_input_tokens": 1000,
                   "max_question_tokens": 5000, "max_question_cost_usd": .1}
        hybrid = {"name": "hybrid", "kind": "rag", "retriever": "bm25", "k": 2}
        selector = {"name": "selector", "kind": "selector", "hybrid": hybrid,
                    "read": {"name": "read", "kind": "read"}}
        result = run_one(question, selector, self.corpus, provider, budgets, 0,
                         Retriever(self.corpus, hybrid))
        self.assertEqual(result["routing"]["decision"], "read")
        self.assertEqual([s["review"]["accepted"] for s in result["routing"]["stages"]], [False, True])
        self.assertTrue(result["scores"]["correct"])
        self.assertEqual(len(result["calls"]), 5)
        self.assertAlmostEqual(result["cost_usd"], .005)
