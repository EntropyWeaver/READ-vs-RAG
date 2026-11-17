import copy
import json
import tempfile
import unittest
from pathlib import Path

from read_vs_rag.corpus import Corpus, ReadTools, bounded_result, normalize
from read_vs_rag.io import load_jsonl
from read_vs_rag.metrics import numeric_match, parse_prediction, score, validate_questions
from read_vs_rag.provider import BudgetExceeded, Ledger
from read_vs_rag.retrieval import BM25, chunk_corpus
from read_vs_rag.stats import holm, mcnemar, paired_comparison, wilson

ROOT = Path(__file__).resolve().parents[1]


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(ROOT / "examples/corpus")
        self.tools = ReadTools(self.corpus)

    def test_normalization_original_coordinates(self):
        out = self.tools.call("memory_grep", {"query": "48964.89"})
        self.assertEqual(len(out["entries"]), 1)
        e = out["entries"][0]
        self.assertIn("48,964.89", e["text"])
        self.assertEqual(self.corpus.docs[e["doc"]][e["line"] - 1], e["text"])

    def test_naive_ablation_differs(self):
        out = ReadTools(self.corpus, normalized=False).call("memory_grep", {"query": "48964.89"})
        self.assertEqual(out["entries"], [])

    def test_unicode_and_numeric_normalization(self):
        self.assertEqual(normalize("４８,９６４.８９")[1], "48964.89")
        self.assertEqual(normalize("Co-\u00adoperation")[1], "cooperation")

    def test_empty_normalized_query_rejected(self):
        with self.assertRaises(ValueError):
            self.tools.call("memory_grep", {"query": "***"})

    def test_span_bounds_and_paths(self):
        for doc, start, end in [("../outside.md", 1, 2), ("finance.md", 0, 1),
                                ("finance.md", 1, 999), ("finance.md", True, 2)]:
            with self.assertRaises(ValueError):
                self.corpus.lines(doc, start, end)

    def test_read_line_cap(self):
        with self.assertRaises(ValueError):
            ReadTools(self.corpus, max_lines=2).call("memory_read", {"doc": "finance.md", "start": 1, "end": 3})

    def test_outline_ablation(self):
        tool = ReadTools(self.corpus, outline=False)
        self.assertNotIn("memory_outline", [t["name"] for t in tool.declarations()])
        with self.assertRaises(ValueError):
            tool.call("memory_outline", {})

    def test_clipping_never_claims_missing_lines(self):
        lines = self.corpus.all_lines()
        out = bounded_result(lines, 180)
        self.assertTrue(out["truncated"])
        self.assertLessEqual(len(json.dumps(out, ensure_ascii=False)), 180)
        for e in out["entries"]:
            self.assertEqual(e["text"], self.corpus.docs[e["doc"]][e["line"] - 1])

    def test_grep_pagination(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "x.md").write_text("needle\n" * 83)
            t = ReadTools(Corpus(tmp))
            a = t.call("memory_grep", {"query": "needle"})
            b = t.call("memory_grep", {"query": "needle", "offset": a["next_offset"]})
            c = t.call("memory_grep", {"query": "needle", "offset": b["next_offset"]})
            self.assertEqual(len(a["entries"]) + len(b["entries"]) + len(c["entries"]), 83)
            self.assertIsNone(c["next_offset"])

    def test_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp, "corpus")
            root.mkdir()
            outside = Path(tmp, "outside.md")
            outside.write_text("secret")
            try:
                (root / "escape.md").symlink_to(outside)
            except OSError:
                self.skipTest("Symlink privilege unavailable")
            with self.assertRaises(ValueError):
                Corpus(root)


class RetrievalTests(unittest.TestCase):
    def test_chunks_cover_every_line_without_invented_coordinates(self):
        corpus = Corpus(ROOT / "examples/corpus")
        for contextual in (True, False):
            for size in (80, 500, 2000):
                chunks = chunk_corpus(corpus, size, 2, contextual)
                seen = {(line.doc, line.line) for c in chunks for line in c.lines}
                self.assertEqual(seen, {(line.doc, line.line) for line in corpus.all_lines()})

    def test_bm25_retrieves_numeric_reference(self):
        corpus = Corpus(ROOT / "examples/corpus")
        chunks = chunk_corpus(corpus, 150)
        hits = BM25(chunks).search("48964.89", 1)
        self.assertTrue(hits)
        self.assertIn("48,964.89", chunks[hits[0][0]].text)

    def test_empty_lexical_hit_is_not_a_fabricated_top_k(self):
        corpus = Corpus(ROOT / "examples/corpus")
        self.assertEqual(BM25(chunk_corpus(corpus)).search("qzxyunknownterm", 8), [])

    def test_contextual_chunk_carries_real_heading(self):
        corpus = Corpus(ROOT / "examples/corpus")
        chunks = chunk_corpus(corpus, 120, 0, True)
        c = next(c for c in chunks if "| Small residual" in c.text)
        self.assertIn("## Statement 2", c.text)
        self.assertIn("Amounts are in lakh", c.text)


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.corpus = Corpus(ROOT / "examples/corpus")
        self.questions = load_jsonl(ROOT / "examples/questions.jsonl")

    def test_fixture_hashes_and_annotations(self):
        validate_questions(self.questions, self.corpus)

    def test_corpus_drift_rejected(self):
        q = copy.deepcopy(self.questions)
        q[0]["corpus_hashes"]["finance.md"] = "changed"
        with self.assertRaises(ValueError):
            validate_questions(q, self.corpus)

    def test_units_convert(self):
        self.assertTrue(numeric_match([{"value": 700, "unit": "crore"}], [{"value": 70000, "unit": "lakh"}]))

    def test_wrong_units_do_not_pass(self):
        self.assertFalse(numeric_match([{"value": 700, "unit": "crore"}], [{"value": 700, "unit": "lakh"}]))
        self.assertFalse(numeric_match([{"value": 7, "unit": "percent"}], [{"value": 7, "unit": "crore"}]))

    def test_near_zero_does_not_disappear(self):
        self.assertFalse(numeric_match([{"value": .0002, "unit": "crore"}], [{"value": 0, "unit": "crore"}]))

    def test_signs_and_shotgun_answers(self):
        self.assertFalse(numeric_match([{"value": -5, "unit": "count"}], [{"value": 5, "unit": "count"}]))
        self.assertFalse(numeric_match([{"value": 5, "unit": "count"}],
                                       [{"value": 5, "unit": "count"}, {"value": 7, "unit": "count"}]))

    def test_duplicate_gold_requires_distinct_matches(self):
        e = [{"value": 5, "unit": "count"}, {"value": 5, "unit": "count"}]
        self.assertFalse(numeric_match(e, [{"value": 5, "unit": "count"}, {"value": 8, "unit": "count"}]))

    def test_strict_answer_schema(self):
        p = {"answer": "No data", "abstain": True, "values": [], "citations": []}
        self.assertTrue(parse_prediction(json.dumps(p))["abstain"])
        for wrong in ({**p, "abstain": "false"}, {**p, "values": [{"value": float('nan'), "unit": "inr"}]},
                      {**p, "values": [{"value": 3, "unit": "inr"}]}):
            with self.assertRaises(ValueError):
                parse_prediction(json.dumps(wrong))

    def test_invalid_and_unseen_citations(self):
        q = self.questions[0]
        p = {"answer": "18942.94 crore", "abstain": False, "values": q["expected_values"],
             "citations": [{"doc": "finance.md", "start": 1, "end": 10**12}]}
        s = score(q, p, [], self.corpus)
        self.assertEqual(s["citation_validity"], 0)
        self.assertEqual(s["line_recall"], 0)
        self.assertTrue(s["correct"])

    def test_abstention_is_explicit_not_regex(self):
        q = next(q for q in self.questions if q["unanswerable"])
        p = {"answer": "They do not contain it.", "abstain": True, "values": [], "citations": []}
        self.assertTrue(score(q, p, [], self.corpus)["correct"])

    def test_missing_semantic_grade_stays_unknown(self):
        q = {**self.questions[0], "expected_values": [], "answer_aliases": []}
        p = {"answer": "Some paraphrase", "abstain": False, "values": [], "citations": []}
        self.assertIsNone(score(q, p, [], self.corpus)["correct"])


class StatisticsTests(unittest.TestCase):
    def test_mcnemar_exact_known(self):
        r = mcnemar([True] * 10, [False] * 10)
        self.assertEqual(r["p_raw"], 2 / 1024)
        self.assertEqual(mcnemar([True], [True])["p_raw"], 1)

    def test_mcnemar_requires_bool_pairs(self):
        with self.assertRaises(ValueError):
            mcnemar([.5], [True])

    def test_holm_known(self):
        self.assertEqual(holm({"a": .01, "b": .04, "c": .03}), {"a": .03, "c": .06, "b": .06})

    def test_wilson_boundaries(self):
        r = wilson(0, 5)
        self.assertAlmostEqual(r["low"], 0.)
        self.assertGreater(r["high"], .4)
        self.assertIsNone(wilson(0, 0)["mean"])

    def test_repeats_not_extra_independent_questions(self):
        r = paired_comparison({"a": [True, False, True]}, {"a": [False, False, True]}, 1000)
        self.assertEqual(r["n_questions"], 1)
        self.assertIsNone(r["mcnemar"])
        self.assertAlmostEqual(r["delta"]["mean"], 1/3)

    def test_missing_pairs_reported(self):
        r = paired_comparison({"a": [True], "b": [False]}, {"a": [False]}, 1000)
        self.assertEqual(r["n_questions"], 1)
        self.assertEqual(r["missing_other"], 1)


class LedgerTests(unittest.TestCase):
    def test_crash_reservation_persists_and_limits_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "ledger.jsonl")
            ledger = Ledger(path, 1, 1000)
            key = ledger.reserve(.8, 800, "test")
            resumed = Ledger(path, 1, 1000)
            with self.assertRaises(BudgetExceeded):
                resumed.reserve(.3, 100, "would overspend")
            resumed.settle(key, .2, 200, {})
            self.assertAlmostEqual(Ledger(path, 1, 1000).spent, .2)

    def test_torn_log_fails_loudly(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "broken.jsonl")
            path.write_text('{"ok":true}\n{"unfinished":')
            with self.assertRaises(ValueError):
                load_jsonl(path)


if __name__ == "__main__":
    unittest.main()
