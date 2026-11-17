import json
import unittest
from collections import Counter
from pathlib import Path

from read_vs_rag.audit import comparisons, flatten
from read_vs_rag.io import load_jsonl, sha256_file

ROOT = Path(__file__).resolve().parents[1]


class PublishedAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ROOT / "data/upstream"
        cls.rows = load_jsonl(cls.source / "results.jsonl")
        cls.questions = {q["id"]: q for q in load_jsonl(cls.source / "questions.jsonl") if q["verified"]}

    def test_pinned_files_are_intact(self):
        manifest = json.loads((self.source / "manifest.json").read_text(encoding="utf-8"))
        for path, info in manifest["files"].items():
            self.assertEqual(sha256_file(self.source / path), info["sha256"])

    def test_reported_headline_counts(self):
        observed = Counter(r["system"] for r in self.rows if r["correct"])
        self.assertEqual(observed, {"read": 30, "bm25": 26, "dense": 8, "hybrid": 15,
                                    "agentic_rag": 14, "read_naive_grep": 34, "read_no_outline": 34})

    def test_source_scoring_disagreements_are_retained(self):
        flat = [flatten(r, self.questions[r["question_id"]]) for r in self.rows]
        self.assertEqual(sum(r["unanswerable"] and r["judge_correct"] is True and r["correct"] is False
                             for r in flat), 9)

    def test_bm25_paired_null_reproduced(self):
        flat = [flatten(r, self.questions[r["question_id"]]) for r in self.rows]
        c = next(c for c in comparisons(flat, "main", 1000) if c["system"] == "bm25")
        self.assertEqual((c["mcnemar"]["wins"], c["mcnemar"]["losses"]), (13, 9))
        self.assertEqual(c["p_holm"], 1.)
        self.assertLess(c["delta"]["low"], 0)


if __name__ == "__main__":
    unittest.main()
