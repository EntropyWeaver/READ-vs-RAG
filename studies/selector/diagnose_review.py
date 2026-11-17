"""Replay a capped verifier input with a smaller context packet and the original candidate."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from read_vs_rag.corpus import Corpus
from read_vs_rag.io import load_jsonl, write_json
from read_vs_rag.provider import Ledger, make_provider
from read_vs_rag.selector import review_candidate


def compact_context(corpus, prediction):
    """Keep every cited line and the 12 closest short, nonblank lines before each citation."""
    keep = {}
    for span in prediction["citations"]:
        doc, start, end = span["doc"], span["start"], span["end"]
        lines = corpus.docs[doc]
        retained = keep.setdefault(doc, set())
        retained.update(range(start - 1, end))
        preceding = [n for n in range(start - 2, max(-1, start - 82), -1)
                     if lines[n].strip() and len(lines[n]) <= 800]
        retained.update(preceding[:12])
    # The reviewer continues to see the original document IDs and line coordinates.
    return SimpleNamespace(docs={
        doc: [line if n in keep[doc] else "" for n, line in enumerate(corpus.docs[doc])]
        for doc in keep
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs=2, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    jobs = []
    allowance = 0.0
    for run in args.runs:
        experiment = json.loads((run / "manifest.json").read_text(encoding="utf-8"))["experiment"]
        config = experiment["config"]
        ledger = Ledger(run / "budget.jsonl", config["max_run_cost_usd"], config["max_run_tokens"])
        allowance += config["max_run_cost_usd"] - ledger.spent
        corpus = Corpus(config["corpus"])
        if experiment["corpus"] != corpus.hashes:
            raise ValueError("Diagnostic evidence differs from the recorded corpus")
        questions = {q["id"]: q["question"] for q in experiment["questions"]}
        latest = {r["question_id"]: r for r in load_jsonl(run / "results.jsonl") if r["system"] == "selector"}
        for qid, row in latest.items():
            if row["status"] != "budget_exhausted" or row["error_scope"] != "question" or "6000" not in row["error"]:
                continue
            stage = next((s for s in row["routing"]["stages"]
                          if s.get("review", {}).get("reason") == "budget_exhausted"
                          and s["review"]["model_calls"] == 0), None)
            if stage is not None:
                jobs.append((qid, questions[qid], stage, corpus, config))
    if not jobs:
        raise ValueError("No completed selector cells failed the verifier's 6000-token input cap")
    output = args.output
    ledger = Ledger(output.with_name("budget.jsonl"), min(.08, allowance), 16000)
    results = []
    for qid, question, stage, corpus, config in sorted(jobs):
        original = stage["prediction"]
        provider = make_provider(config["provider"], ledger)
        row = {"prediction": original, "status": "ok", "error": None, "error_scope": None,
               "calls": [], "reserved_or_billed_usd": 0, "cost_usd": 0, "input_tokens": 0,
               "output_tokens": 0, "thinking_tokens": 0, "scores": {"unanswerable": False}}
        audited, accepted, reason = review_candidate(
            question, row, compact_context(corpus, original), provider,
            f"compact-proof/{qid}", config["budgets"], 0)
        results.append({"question_id": qid, "replayed_stage": stage["stage"],
                        "accepted": accepted, "reason": reason, "status": audited["status"],
                        "input_tokens": audited["input_tokens"], "cost_usd": audited["cost_usd"]})
    write_json(output, {"mode": "exploratory_compact_context_diagnostic", "cases": results,
                        "actual_or_reserved_usd": ledger.spent,
                        "note": "Preserves the original cited text and model. It changes the nearby context only. "
                                "The registered benchmark results are untouched."})


if __name__ == "__main__":
    main()
