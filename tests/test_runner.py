import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from read_vs_rag.io import load_jsonl
from read_vs_rag.judging import judge_run
from read_vs_rag.provider import BudgetExceeded, Gemini, Ledger, ProviderError
from read_vs_rag.reporting import report_run
from read_vs_rag.runner import load_experiment, run, run_one

ROOT = Path(__file__).resolve().parents[1]


def response(content, version="gemini-2.5-pro", cached=0):
    return {"modelVersion": version, "usageMetadata": {"promptTokenCount": 200,
            "candidatesTokenCount": 60, "thoughtsTokenCount": 40, "totalTokenCount": 300,
            "cachedContentTokenCount": cached},
            "candidates": [{"finishReason": "STOP", "content": content}]}


def final_content():
    return {"role": "model", "parts": [{"text": json.dumps({"answer": "18,942.94 crore INR",
            "abstain": False, "values": [{"value": 18942.94, "unit": "crore"}],
            "citations": [{"doc": "finance.md", "start": 11, "end": 11}]})}]}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        clock = patch("read_vs_rag.provider.date")
        mocked = clock.start()
        mocked.today.return_value = date(2026, 11, 17)
        mocked.fromisoformat.side_effect = date.fromisoformat
        self.addCleanup(clock.stop)
        self.config = load_experiment(ROOT / "configs/pilot.json")[0]["provider"]
        self.config["pricing"]["valid_through"] = "2999-12-31"

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
    def test_count_and_bill_thinking_and_cached_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Gemini(self.config, Ledger(Path(tmp, "ledger.jsonl"), 3., 100000))
            with patch.object(provider, "_post", side_effect=[{"totalTokens": 200}, response(final_content(), cached=100)]) as post:
                _, u = provider.generate("instruction", [{"role": "user", "parts": [{"text": "question"}]}], [],
                                         tag="test", seed=0, max_input_tokens=1000)
            self.assertEqual(post.call_args_list[0].args[0], "countTokens")
            self.assertAlmostEqual(u["cost_usd"], (100 * 1.25 + 100 * .125 + 100 * 10) / 1e6)
            self.assertAlmostEqual(provider.ledger.spent, u["cost_usd"])

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
    def test_reserves_before_network_and_keeps_ambiguous_charge(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Ledger(Path(tmp, "ledger.jsonl"), 3., 100000)
            provider = Gemini(self.config, ledger)
            def fake(action, payload):
                if action == "countTokens":
                    return {"totalTokens": 200}
                self.assertGreater(ledger.spent, 0)
                raise ProviderError("network timed out")
            with patch.object(provider, "_post", side_effect=fake), self.assertRaises(ProviderError):
                provider.generate("system", [], [], tag="test", seed=0, max_input_tokens=1000)
            self.assertGreater(Ledger(ledger.path, 3., 100000).spent, 0)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
    def test_input_cap_blocks_billable_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Gemini(self.config, Ledger(Path(tmp, "l.jsonl"), 3., 100000))
            with patch.object(p, "_post", return_value={"totalTokens": 1001}) as post, self.assertRaises(BudgetExceeded):
                p.generate("system", [], [], tag="test", seed=0, max_input_tokens=1000)
            self.assertEqual(post.call_count, 1)
            self.assertEqual(p.ledger.spent, 0)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
    def test_model_drift_is_billed_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Gemini(self.config, Ledger(Path(tmp, "l.jsonl"), 3., 100000))
            with patch.object(p, "_post", side_effect=[{"totalTokens": 200}, response(final_content(), version="other-model")]):
                with self.assertRaises(ProviderError):
                    p.generate("system", [], [], tag="test", seed=0, max_input_tokens=1000)
            self.assertGreater(p.ledger.spent, 0)
            self.assertEqual(len(p.calls), 1)

    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
    def test_expired_rates_block_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.config["pricing"]["valid_through"] = "2000-01-01"
            with self.assertRaises(ValueError):
                Gemini(self.config, Ledger(Path(tmp, "l.jsonl"), 3., 10000))


@patch.dict("os.environ", {"GEMINI_API_KEY": "test-only-not-a-real-key"})
class RunnerTests(unittest.TestCase):
    def setUp(self):
        clock = patch("read_vs_rag.provider.date")
        mocked = clock.start()
        mocked.today.return_value = date(2026, 11, 17)
        mocked.fromisoformat.side_effect = date.fromisoformat
        self.addCleanup(clock.stop)
        self.cfg, _, self.corpus, self.questions = load_experiment(ROOT / "configs/pilot.json")
        self.cfg["provider"]["pricing"]["valid_through"] = "2999-12-31"

    def test_agent_tool_round_trip_preserves_signature_and_hides_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Gemini(self.cfg["provider"], Ledger(Path(tmp, "l.jsonl"), 3., 400000))
            q = {**self.questions[0], "reference_answer": "GOLD_SENTINEL_DO_NOT_SEND"}
            signed = {"role": "model", "parts": [{"thoughtSignature": "signature-test",
                      "functionCall": {"id": "call-1", "name": "memory_read",
                                       "args": {"doc": "finance.md", "start": 5, "end": 12}}}]}
            generated = 0
            requests = []
            def fake(action, payload):
                nonlocal generated
                requests.append(copy.deepcopy(payload))
                if action == "countTokens":
                    return {"totalTokens": 200}
                generated += 1
                return response(signed if generated == 1 else final_content())
            with patch.object(provider, "_post", side_effect=fake):
                r = run_one(q, self.cfg["systems"][0], self.corpus, provider, self.cfg["budgets"], 0)
            self.assertEqual(r["status"], "ok")
            self.assertTrue(r["scores"]["correct"])
            self.assertEqual(r["scores"]["line_recall"], 1)
            self.assertEqual(r["scores"]["citation_seen_fraction"], 1)
            self.assertNotIn("GOLD_SENTINEL_DO_NOT_SEND", json.dumps(requests))
            self.assertIn(signed, requests[-1]["contents"])
            fr = requests[-1]["contents"][2]["parts"][0]["functionResponse"]
            self.assertEqual(fr["id"], "call-1")

    def test_full_context_refuses_silent_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Gemini(self.cfg["provider"], Ledger(Path(tmp, "l.jsonl"), 3., 400000))
            with patch.object(provider, "generate") as generate:
                row = run_one(self.questions[0], {"name": "full", "kind": "full_context"}, self.corpus,
                              provider, {**self.cfg["budgets"], "max_evidence_chars": 100}, 0)
            self.assertEqual(row["status"], "budget_exhausted")
            generate.assert_not_called()

    def test_invalid_output_is_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Gemini(self.cfg["provider"], Ledger(Path(tmp, "l.jsonl"), 3., 400000))
            bad = {"role": "model", "parts": [{"text": "not valid JSON"}]}
            with patch.object(p, "_post", side_effect=[{"totalTokens": 200}, response(bad)]):
                r = run_one(self.questions[0], self.cfg["systems"][0], self.corpus, p, self.cfg["budgets"], 0)
            self.assertEqual(r["status"], "invalid_output")
            self.assertFalse(r["scores"]["correct"])
            self.assertGreater(r["cost_usd"], 0)

    def test_resume_report_and_blinded_judge(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp, "run")
            def fake(self, action, payload):
                return {"totalTokens": 200} if action == "countTokens" else response(final_content())
            with patch.object(Gemini, "_post", fake):
                run(ROOT / "configs/pilot.json", output, limit=1)
            self.assertEqual(len(load_jsonl(output / "results.jsonl")), 2)
            with patch.object(Gemini, "_post") as post:
                run(ROOT / "configs/pilot.json", output, limit=1)
                post.assert_not_called()
            report = report_run(output)
            self.assertEqual(report["systems"][0]["completed_cells"], 1)
            self.assertEqual(report["systems"][0]["pending_cells"], 0)
            with self.assertRaises(ValueError):
                run(ROOT / "configs/pilot.json", output, limit=2)
            requests = []
            def judge_fake(self, action, payload):
                requests.append(payload)
                return {"totalTokens": 200} if action == "countTokens" else response({"role": "model", "parts": [
                    {"text": json.dumps({"correct": True, "supported": False, "reason": "test verdict"})}]})
            with patch.object(Gemini, "_post", judge_fake):
                judge_run(output, max_cost=1.)
            self.assertEqual(len(load_jsonl(output / "judgments.jsonl")), 2)
            payloads = [p["contents"][0]["parts"][0]["text"] for p in requests if "contents" in p]
            self.assertTrue(all('"system"' not in p and '"bm25"' not in p for p in payloads))
            report = report_run(output)
            self.assertEqual(report["systems"][0]["llm_judge_supported"]["mean"], 0)

    def test_pending_cells_stay_in_denominator_bounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp, "run")
            with patch.object(Gemini, "_post", side_effect=ProviderError("offline")):
                run(ROOT / "configs/pilot.json", output, limit=1)
            report = report_run(output)
            self.assertEqual(sum(s["pending_cells"] for s in report["systems"]), 1)
            missing = next(s for s in report["systems"] if s["pending_cells"])
            self.assertIsNone(missing["accuracy_on_scored"])
            self.assertEqual(missing["accuracy_upper_bound"], 1)


if __name__ == "__main__":
    unittest.main()
