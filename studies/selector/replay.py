"""Measure the deterministic checks on the original paired Gujarat recordings."""

import argparse
import json
from collections import Counter
from pathlib import Path

from read_vs_rag.audit import csv_write
from read_vs_rag.corpus import Corpus
from read_vs_rag.io import load_jsonl, sha256_file, write_json
from read_vs_rag.selector import run_cascade
from read_vs_rag.stats import distribution, holm, paired_comparison


def load_stage(run, system):
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    file = run / "results.jsonl"
    rows = {}
    for row in load_jsonl(file):
        if row["system"] == system:
            key = row["question_id"], row["repeat"]
            if row["fingerprint"] != manifest["fingerprint"] or key in rows:
                raise ValueError(f"Ambiguous recording for {key} in {run}")
            rows[key] = row
    return manifest["experiment"], rows, sha256_file(file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corpus", "hybrid", "read", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    corpus = Corpus(args.corpus)
    hybrid, read = (load_stage(path, name) for path, name in ((args.hybrid, "hybrid_rrf"), (args.read, "read")))
    exp, hy, hy_hash = hybrid
    read_exp, rd, rd_hash = read
    questions = {q["id"]: q for q in exp["questions"]}
    if (exp["corpus"] != corpus.hashes or read_exp["corpus"] != corpus.hashes
            or exp["questions"] != read_exp["questions"] or exp["config"]["repeats"] != [0]
            or read_exp["config"]["repeats"] != [0]
            or exp["config"]["provider"] != read_exp["config"]["provider"]):
        raise ValueError("Replay requires matching corpus, provider, questions and a single repeat")
    if not questions or set(hy) != set(rd) or set(hy) != {(qid, 0) for qid in questions}:
        raise ValueError("Replay requires the full set of paired responses")
    args.output.mkdir(parents=True, exist_ok=True)
    rows, by_system = [], {"hybrid": {}, "read": {}, "rules_only": {}}
    for key in sorted(hy):
        qid, _ = key
        staged = {"hybrid": hy[key], "read": rd[key]}
        result = run_cascade(questions[qid], corpus, "rules_only", staged.__getitem__)
        for name, row in {**staged, "rules_only": result}.items():
            by_system[name][qid] = row
        routing = result["routing"]
        rows.append({"question_id": qid, "category": questions[qid]["category"],
                     "unanswerable": questions[qid]["unanswerable"],
                     "hybrid_correct": hy[key]["scores"]["correct"], "read_correct": rd[key]["scores"]["correct"],
                     "rules_only_correct": result["scores"]["correct"], "decision": routing["decision"],
                     "hybrid_check": routing["stages"][0]["reason"],
                     "read_check": routing["stages"][1]["reason"] if len(routing["stages"]) > 1 else "",
                     "rules_only_cost_usd": result["cost_usd"], "sequential_latency_proxy_s": result["latency_s"]})
    metrics = {}
    for name, observations in by_system.items():
        items = list(observations.values())
        correct = [item["scores"]["correct"] for item in items]
        if any(type(item) is not bool for item in correct):
            raise ValueError("Replay requires binary grades on all cells")
        metrics[name] = {
            "correct": sum(correct), "n": len(items),
            "correct_abstentions": sum(row["scores"]["unanswerable"] and row["scores"]["abstained"] is True
                                       for row in items),
            "false_abstentions": sum(not row["scores"]["unanswerable"] and row["scores"]["abstained"] is True
                                     for row in items),
            "errors": sum(row["status"] != "ok" for row in items),
            "cost_usd": distribution([row["cost_usd"] for row in items]),
            "latency_s": distribution([row["latency_s"] for row in items]),
        }
    correct_by_q = {name: {q: [row["scores"]["correct"]] for q, row in observations.items()}
                    for name, observations in by_system.items()}
    comparisons = {name: paired_comparison(correct_by_q["rules_only"], correct_by_q[name])
                   for name in ("hybrid", "read")}
    adjustment = holm({name: result["mcnemar"]["p_raw"] for name, result in comparisons.items()})
    for name, comparison in comparisons.items():
        comparison["p_holm"] = adjustment[name]
    write_json(args.output / "metrics.json", {
        "mode": "counterfactual_rules_only_replay",
        "model": exp["config"]["provider"]["model"],
        "source_sha256": {"hybrid_results": hy_hash, "read_results": rd_hash, "corpus": corpus.hashes},
        "n_unanswerable": sum(q["unanswerable"] for q in questions.values()),
        "rules_only_routes": dict(Counter(row["decision"] for row in rows)),
        "rules_only_read_calls": sum(bool(row["read_check"]) for row in rows),
        "systems": metrics, "paired_vs_rules_only": comparisons,
        "latency_note": "Cascade latency sums the original hybrid and READ durations on escalated questions. "
                        "Original cells ran independently with concurrency, so the result is a sequential proxy.",
        "scope_note": "Retrospective development data. Semantic review was not run and is not represented.",
    })
    csv_write(args.output / "per_question.csv", rows)


if __name__ == "__main__":
    main()
