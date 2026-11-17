import json
import tempfile
import unittest
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from read_vs_rag.io import load_jsonl
from read_vs_rag.judging import judge_run
from read_vs_rag.openai_provider import OpenAI
from read_vs_rag.provider import BudgetExceeded, Ledger, ProviderError
from read_vs_rag.runner import run


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/openai-mini.json"
MODEL = "gpt-5.4-mini-2026-03-17"


def api_response(output):
    return {
        "status": "completed",
        "model": MODEL,
        "usage": {
            "input_tokens": 2000, "input_tokens_details": {"cached_tokens": 1024},
            "output_tokens": 300, "output_tokens_details": {"reasoning_tokens": 200},
            "total_tokens": 2300,
        },
        "output": output,
    }


def answer(payload):
    return {"type": "message", "role": "assistant", "status": "completed", "id": "msg_test",
            "content": [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]}


@patch.dict("os.environ", {"OPENAI_API_KEY": "fake-test-key"})
class OpenAITests(unittest.TestCase):
    def test_run_with_tool_results_and_optional_judge(self):
        reasoning = {"type": "reasoning", "id": "rs_test", "summary": [], "encrypted_content": "encrypted"}
        call = {"type": "function_call", "id": "fc_test", "call_id": "call_test", "name": "memory_read",
                "arguments": '{"doc":"finance.md","start":5,"end":12}'}
        final = answer({"answer": "18,942.94 crore INR", "abstain": False,
                        "values": [{"value": 18942.94, "unit": "crore"}],
                        "citations": [{"doc": "finance.md", "start": 11, "end": 11}]})
        requests = []

        def fake_post(provider, action, body):
            if action == "count":
                self.assertNotIn("max_output_tokens", body)
                self.assertNotIn("store", body)
                if body.get("text", {}).get("format", {}).get("type") == "json_object":
                    self.assertIn({"role": "user", "content": "Return a JSON object."}, body["input"])
                return {"input_tokens": 2000}
            self.assertFalse(body["store"])
            requests.append(body)
            if body.get("tools") and not any(item.get("type") == "function_call_output"
                                             for item in body["input"]):
                return api_response([reasoning, call])
            if "You evaluate document QA" in body["instructions"]:
                return api_response([answer({"correct": True, "supported": True, "reason": "verified"})])
            return api_response([final])

        with tempfile.TemporaryDirectory() as tmp, patch.object(OpenAI, "_post", fake_post):
            run(ROOT / "configs/pilot.json", tmp, limit=1, provider_config=CONFIG)
            rows = load_jsonl(Path(tmp) / "results.jsonl")
            read = next(row for row in rows if row["system"] == "read")
            self.assertTrue(read["scores"]["correct"])
            self.assertEqual(read["scores"]["line_recall"], 1)
            self.assertEqual(read["output_tokens"], 200)
            self.assertEqual(read["thinking_tokens"], 400)
            self.assertAlmostEqual(read["cost_usd"], 2 * (976 * .75 + 1024 * .075 + 300 * 4.5) / 1e6)
            continuation = next(body for body in requests if reasoning in body["input"])
            self.assertIn(call, continuation["input"])
            tool_result = next(item for item in continuation["input"] if item.get("type") == "function_call_output")
            self.assertEqual(tool_result["call_id"], "call_test")
            self.assertIn("Revenue surplus", tool_result["output"])
            self.assertEqual(len(requests), 3)
            judgments = load_jsonl(judge_run(tmp, max_cost=.1))
            self.assertEqual(len(judgments), 2)
            self.assertTrue(all(row["judgment"]["supported"] for row in judgments))

    def test_count_blocks_generation_and_ambiguous_failure_retains_reservation(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "budget.jsonl"
            provider = OpenAI(config, Ledger(path, .1, 10000))
            params = {"tag": "test", "seed": 0, "max_input_tokens": 3000}
            with patch.object(provider, "_post", return_value={"input_tokens": 3001}) as post:
                with self.assertRaises(BudgetExceeded):
                    provider.generate("JSON", [{"role": "user", "parts": [{"text": "question"}]}], [], **params)
                self.assertEqual(post.call_count, 1)
                self.assertFalse(path.exists())
            with patch.object(provider, "_post", side_effect=[{"input_tokens": 2000}, ProviderError("timeout")]):
                with self.assertRaises(ProviderError):
                    provider.generate("JSON", [{"role": "user", "parts": [{"text": "question"}]}], [], **params)
            self.assertEqual(load_jsonl(path)[0]["event"], "reserve")

    def test_parallel_run_accounts_for_each_cell_independently(self):
        cfg = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        cfg.update(workers=2, project_root=str(ROOT))
        both_running = Barrier(2, timeout=5)
        final = answer({"answer": "18,942.94 crore INR", "abstain": False,
                        "values": [{"value": 18942.94, "unit": "crore"}], "citations": []})

        def fake_post(provider, action, body):
            if action == "count":
                return {"input_tokens": 2000}
            both_running.wait()
            return api_response([final])

        with tempfile.TemporaryDirectory() as tmp, patch.object(OpenAI, "_post", fake_post):
            config = Path(tmp) / "config.json"
            config.write_text(json.dumps(cfg), encoding="utf-8")
            output = Path(tmp) / "run"
            run(config, output, limit=1, provider_config=CONFIG)
            rows = load_jsonl(output / "results.jsonl")
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual(row["status"], "ok")
                self.assertAlmostEqual(row["cost_usd"], row["reserved_or_billed_usd"])
