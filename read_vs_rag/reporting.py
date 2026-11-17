"""Reports keep missing evaluations visible and bootstrap repeated calls by question."""

import html
import json
from collections import defaultdict
from pathlib import Path

from .audit import csv_write, pct
from .io import load_jsonl, stable_hash, write_json
from .provider import Ledger
from .stats import bootstrap_mean, distribution, holm, paired_comparison, wilson


def report_run(run_dir, output=None):
    run_dir = Path(run_dir)
    output = Path(output) if output else run_dir / "report"
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    experiment = manifest["experiment"]
    cfg, questions = experiment["config"], experiment["questions"]
    repeats = cfg["repeats"]
    rows = load_jsonl(run_dir / "results.jsonl") if (run_dir / "results.jsonl").exists() else []
    latest = {}
    allowed = {(q["id"], s["name"], r) for q in questions for s in cfg["systems"] for r in repeats}
    for r in rows:
        key = (r["question_id"], r["system"], r["repeat"])
        if key not in allowed or r["fingerprint"] != manifest["fingerprint"]:
            raise ValueError("Result row does not belong to this manifest")
        if key in latest and r["attempt"] <= latest[key]["attempt"]:
            raise ValueError("Duplicate/out-of-order attempt")
        latest[key] = r
    systems, paired, slices = [], {}, []
    judgments = {}
    if (run_dir / "judgments.jsonl").exists():
        for j in load_jsonl(run_dir / "judgments.jsonl"):
            if j["fingerprint"] != manifest["fingerprint"]:
                raise ValueError("Judgment fingerprint mismatch")
            judgments[j["candidate_hash"]] = j.get("judgment")
    for spec in cfg["systems"]:
        name = spec["name"]
        rs = [r for r in latest.values() if r["system"] == name]
        scored = [r for r in rs if r["scores"].get("correct") is not None]
        expected = len(questions) * len(repeats)
        correct = sum(r["scores"]["correct"] for r in scored)
        by_question = defaultdict(dict)
        for r in scored:
            by_question[r["question_id"]][r["repeat"]] = bool(r["scores"]["correct"])
        # Paired analyses need every repeat in BOTH systems; partial repeats are explicitly excluded.
        complete = {q: [vals[rep] for rep in repeats] for q, vals in by_question.items() if set(vals) == set(repeats)}
        paired[name] = complete
        means = [sum(v) / len(v) for v in complete.values()]
        acc_ci = wilson(correct, len(scored)) if len(repeats) == 1 else bootstrap_mean(means)
        summary = {"system": name, "expected_cells": expected, "completed_cells": len(rs),
                   "scored_cells": len(scored), "pending_cells": expected - len(rs),
                   "ungraded_completed_cells": len(rs) - len(scored), "complete_questions": len(complete),
                   "correct": correct, "accuracy_on_scored": correct / len(scored) if scored else None,
                   "accuracy_ci": acc_ci, "accuracy_lower_bound": correct / expected,
                   "accuracy_upper_bound": (correct + expected - len(scored)) / expected,
                   "operational_errors": sum(r["status"] != "ok" for r in rs),
                   "latency_s": distribution([r["latency_s"] for r in rs]),
                   "cost_usd_latest_attempts": distribution([r["cost_usd"] for r in rs])}
        js = [judgments.get(stable_hash(r)) for r in rs]
        summary["llm_judge_correct"] = distribution([j["correct"] for j in js if j])
        summary["llm_judge_supported"] = distribution([j["supported"] for j in js if j])
        summary["judge_scoring_disagreements"] = sum(
            j is not None and r["scores"].get("correct") is not None and j["correct"] != r["scores"]["correct"]
            for r, j in zip(rs, js))
        for metric in ("line_recall", "all_gold_lines_seen", "reciprocal_rank", "hit_at_k", "chunk_recall_at_k", "ndcg_at_k", "citation_validity",
                       "citation_seen_fraction", "citation_gold_overlap_precision", "citation_gold_line_recall",
                       "numeric_correct", "token_f1_diagnostic", "unique_lines_seen", "has_citation"):
            summary[metric] = distribution([r["scores"].get(metric) for r in rs])
        for metric in ("input_tokens", "output_tokens", "thinking_tokens", "evidence_chars"):
            summary[metric] = distribution([r.get(metric) for r in rs])
        unans = [r for r in rs if r["scores"].get("unanswerable")]
        ans = [r for r in rs if not r["scores"].get("unanswerable")]
        summary["abstention_on_unanswerable"] = distribution([r["scores"].get("abstained") for r in unans])
        summary["abstention_on_answerable"] = distribution([r["scores"].get("abstained") for r in ans])
        systems.append(summary)
        for category in sorted({q["category"] for q in questions}):
            crs = [r for r in scored if r["category"] == category]
            slices.append({"system": name, "category": category, "n_scored": len(crs),
                           "accuracy": sum(r["scores"]["correct"] for r in crs) / len(crs) if crs else None})
    comparisons = []
    if "read" in paired:
        for name, values in paired.items():
            if name == "read":
                continue
            c = paired_comparison(paired["read"], values)
            c["system"] = name
            comparisons.append(c)
        corrected = holm({c["system"]: c["mcnemar"]["p_raw"] for c in comparisons if c["mcnemar"]})
        for c in comparisons:
            c["p_holm"] = corrected.get(c["system"])
    ledger = Ledger(run_dir / "budget.jsonl", cfg["max_run_cost_usd"], cfg["max_run_tokens"])
    result = {"source": "new_model_run", "fingerprint": manifest["fingerprint"],
              "provider": cfg["provider"].get("name", "gemini"), "model": cfg["provider"]["model"],
              "dataset_kind": cfg.get("dataset_kind"), "systems": systems, "comparisons": comparisons,
              "budget_reserved_or_billed_usd_all_attempts": ledger.spent,
              "unsettled_requests": sum(e["event"] == "reserve" for e in ledger.entries.values()),
              "notes": ["Missing cells remain visible. Bounds include pending/ungraded cells.",
                        "Operational failures count as incorrect. Missing semantic grades are unknown.",
                        "For repeats, confidence intervals resample complete questions, not independent repeats.",
                        "McNemar/Holm only available with one run per question; no pseudoreplication.",
                        "Citation/line metrics measure annotated overlap, not semantic faithfulness.",
                        "Cost uses configured rates and provider usage. Index build cost is separate."]}
    if (run_dir / "judge_budget.jsonl").exists():
        judge_spec = json.loads((run_dir / "judge_manifest.json").read_text(encoding="utf-8"))
        jl = Ledger(run_dir / "judge_budget.jsonl", judge_spec["max_cost_usd"], 500000)
        result["judge_reserved_or_billed_usd"] = jl.spent
    write_json(output / "summary.json", result)
    csv_write(output / "slices.csv", slices)
    flat = [{"system": r["system"], "question_id": r["question_id"], "repeat": r["repeat"],
             "status": r["status"], "correct": r["scores"].get("correct"), "cost_usd": r["cost_usd"],
             "latency_s": r["latency_s"], "error": r["error"]} for r in latest.values()]
    csv_write(output / "per_question.csv", flat)
    table = ["| Sistema | Ejecutadas/previstas | Scored | Accuracy scored | Límites con pendientes | p95 |",
             "|---|---:|---:|---:|---:|---:|"]
    for s in systems:
        latency = s["latency_s"]["p95"]
        table.append(f"| {s['system']} | {s['completed_cells']}/{s['expected_cells']} | "
                     f"{s['scored_cells']} | {pct(s['accuracy_on_scored'])} | "
                     f"{pct(s['accuracy_lower_bound'])} – {pct(s['accuracy_upper_bound'])} | "
                     f"{latency if latency is not None else 'N/A'} |")
    md = ("# Ejecución READ vs RAG\n\n"
          f"Se evaluó **{cfg.get('dataset_kind')}** con `{result['model']}` ({result['provider']}).\n\n"
          + "\n".join(table))
    md += "\n\n" + "\n".join("- " + n for n in result["notes"]) + "\n"
    (output / "report.md").write_text(md, encoding="utf-8")
    cases = "".join(f"<details><summary>{html.escape(r['system']+' / '+r['question_id'])} · {r['status']}</summary>"
                    f"<pre>{html.escape(json.dumps(r, indent=2, ensure_ascii=False))}</pre></details>"
                    for r in latest.values())
    page = "<!doctype html><html lang='es'><meta charset='utf-8'><title>Run explorer</title>"
    page += "<style>body{max-width:1100px;margin:40px auto;padding:20px;font:16px/1.6 system-ui}"
    page += "pre{white-space:pre-wrap;overflow-wrap:anywhere}details{border:1px solid #aaa;padding:16px;margin:10px 0}</style>"
    page += "<h1>READ vs RAG · Run explorer</h1><pre>" + html.escape(md) + "</pre>" + cases + "</html>"
    (output / "index.html").write_text(page, encoding="utf-8")
    return result
