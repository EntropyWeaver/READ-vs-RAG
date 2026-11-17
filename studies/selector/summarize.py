"""Aggregate the registered holdout runs and audit the selector's stage decisions."""

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from read_vs_rag.audit import csv_write
from read_vs_rag.io import load_jsonl, sha256_file, stable_hash, write_json
from read_vs_rag.metrics import numeric_match
from read_vs_rag.stats import distribution, holm, paired_comparison, wilson

SYSTEMS = ("hybrid_rrf", "read", "selector")


def load_run(path):
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    experiment = manifest["experiment"]
    config = experiment["config"]
    if stable_hash(experiment) != manifest["fingerprint"]:
        raise ValueError(f"{path}: invalid manifest fingerprint")
    if (experiment["limit"] is not None or experiment["split"] != "test" or config["repeats"] != [0]
            or tuple(system["name"] for system in config["systems"]) != SYSTEMS):
        raise ValueError(f"{path}: expected a complete test run of the registered matrix")
    questions = {row["id"]: row for row in experiment["questions"]}
    file = path / "results.jsonl"
    rows = {}
    for row in load_jsonl(file):
        key = row["question_id"], row["system"]
        if (row["fingerprint"] != manifest["fingerprint"] or row["repeat"] != 0
                or key[0] not in questions or key[1] not in SYSTEMS
                or key in rows and row["attempt"] <= rows[key]["attempt"]):
            raise ValueError(f"{path}: invalid attempt for {key}")
        rows[key] = row
    if set(rows) != {(qid, system) for qid in questions for system in SYSTEMS}:
        raise ValueError(f"{path}: missing comparison cells")
    for row in rows.values():
        if type(row["scores"]["correct"]) is not bool:
            raise ValueError(f"{path}: ungraded cell")
        if not math.isclose(row["cost_usd"], sum(c["cost_usd"] for c in row["calls"]), abs_tol=1e-10):
            raise ValueError(f"{path}: cell cost does not match its calls")
    settled, reservations = {}, {}
    for entry in load_jsonl(path / "budget.jsonl"):
        if entry["event"] == "reserve":
            reservations[entry["id"]] = entry["cost_usd"]
        elif entry["event"] == "settle" and entry["id"] in reservations:
            reservations.pop(entry["id"])
            settled[entry["id"]] = entry["cost_usd"]
        else:
            raise ValueError(f"{path}: malformed budget ledger")
    recorded_spend = sum(row["cost_usd"] for row in rows.values())
    if recorded_spend > sum(settled.values()) + 1e-9:
        raise ValueError(f"{path}: recorded usage exceeds settled reservations")
    return questions, rows, config, {
        "fingerprint": manifest["fingerprint"], "source_corpus": experiment["corpus"],
        "code_hash": experiment["code_hash"], "dependencies": experiment["dependencies"],
        "results_sha256": sha256_file(file),
        "actual_spend_usd_all_attempts": sum(settled.values()),
        "unsettled_reservations_usd": sum(reservations.values()),
        "unsettled_requests": len(reservations),
        "recorded_attempts": sum(row["attempt"] for row in rows.values()),
        "max_run_cost_usd": config["max_run_cost_usd"],
        "workers": config["workers"],
        "index_builds": [{key: index[key] for key in ("system", "build_s", "chunks", "truncated_chunks")}
                         for index in load_jsonl(path / "index_builds.jsonl")],
    }


def summarize(rows):
    correct = sum(row["scores"]["correct"] for row in rows)
    unanswerable = [row for row in rows if row["scores"]["unanswerable"]]
    answerable = [row for row in rows if not row["scores"]["unanswerable"]]
    answered = [row for row in rows if row["status"] == "ok" and row["scores"]["abstained"] is False]
    return {
        "n": len(rows), "correct": correct, "accuracy_wilson_95": wilson(correct, len(rows)),
        "correct_abstentions": sum(row["scores"]["abstained"] is True for row in unanswerable),
        "unanswerable": len(unanswerable),
        "false_abstentions": sum(row["scores"]["abstained"] is True for row in answerable),
        "answerable": len(answerable), "answered": len(answered),
        "correct_when_answered": sum(row["scores"]["correct"] for row in answered),
        "operational_errors": dict(Counter(row["status"] for row in rows if row["status"] != "ok")),
        "cost_usd": distribution([row["cost_usd"] for row in rows]),
        "latency_s": distribution([row["latency_s"] for row in rows]),
        "tokens": {field: sum(row[field] for row in rows)
                   for field in ("input_tokens", "output_tokens", "thinking_tokens")},
        "recorded_model_calls": sum(len(row["calls"]) for row in rows),
        "tool_calls": sum(sum(bool(step.get("model_tool")) for step in row["trace"]) for row in rows),
        "annotated_line_recall": distribution([row["scores"].get("line_recall")
                                               for row in answerable]),
        "citation_seen_fraction": distribution([row["scores"].get("citation_seen_fraction")
                                                for row in answered]),
    }


def grade_candidate(question, prediction):
    if prediction is None:
        return None
    if question["unanswerable"] or prediction["abstain"]:
        return question["unanswerable"] and prediction["abstain"]
    return numeric_match(question["expected_values"], prediction["values"], question["rel_tol"], question["abs_tol"])


def selector_audit(rows, questions):
    routes, checks, flow, reviews, cost_by_stage = (Counter() for _ in range(5))
    read_delta_by_q, results = {}, {}
    initial_grade = Counter()
    stop_on_abstain = Counter()
    for row in rows:
        qid = row["question_id"]
        route = row["routing"]
        routes[route["decision"]] += 1
        stages = route["stages"]
        if len(stages) == 2:
            routes["read_started"] += 1
        initial_correct = grade_candidate(questions[qid], stages[0]["prediction"])
        initial_grade[str(initial_correct).lower()] += 1
        final_correct = row["scores"]["correct"]
        for call in row["calls"]:
            _, stage, kind, *_ = call["tag"].split("/")
            cost_by_stage[f"{stage}_review" if kind == "review" else stage] += call["cost_usd"]
        if stages[0]["reason"] == "candidate_abstained" and len(stages) == 2:
            stop_on_abstain["candidates"] += 1
            stop_on_abstain["fallback_cost_usd"] += sum(
                call["cost_usd"] for call in row["calls"] if call["tag"].startswith("selector/read/"))
            stop_on_abstain["accuracy_wins_of_read"] += final_correct and not initial_correct
            stop_on_abstain["accuracy_losses_of_read"] += initial_correct and not final_correct
        if initial_correct is True and not final_correct:
            flow["lost_correct_hybrid_candidate"] += 1
        elif initial_correct is False and final_correct:
            flow["corrected_incorrect_hybrid_candidate"] += 1
        else:
            flow["no_measured_change" if initial_correct is not None else "hybrid_candidate_unavailable"] += 1
        for stage in stages:
            check = stage["reason"]
            checks[stage["stage"], check] += 1
            stage["candidate_correct_offline"] = grade_candidate(questions[qid], stage["prediction"])
            if "review" in stage:
                verdict = stage["review"]
                reviews["requested"] += 1
                reviews["recorded_model_calls"] += verdict["model_calls"]
                if verdict["model_calls"] and stage["status"] == "ok":
                    key = ("accepted" if verdict["accepted"] else "rejected") + (
                        "_correct" if stage["candidate_correct_offline"] else "_incorrect")
                    reviews[key] += 1
        if len(stages) == 2:
            read_delta_by_q[qid] = stages[1]["candidate_correct_offline"]
        results[qid] = {"decision": route["decision"], "stages": stages}
    return {"routes": dict(routes), "flow": dict(flow), "initial_hybrid_candidate_correctness": dict(initial_grade),
            "reviews": dict(reviews), "cost_usd_by_stage": dict(cost_by_stage),
            "exploratory_stop_on_hybrid_abstention": dict(stop_on_abstain),
            "checks": {f"{stage}:{reason}": n for (stage, reason), n in sorted(checks.items())},
            "read_candidates_correct": sum(value is True for value in read_delta_by_q.values())}, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs=2, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    questions, observations, manifests, docs = {}, {}, {}, {}
    common = None
    for path in args.runs:
        case_questions, rows, cfg, provenance = load_run(path)
        if len(case_questions) != 12 or any(qid in questions for qid in case_questions):
            raise ValueError(f"{path}: expected 12 distinct questions per document")
        state = next(iter(case_questions)).split("-", 1)[0]
        if state in docs or any(not qid.startswith(state + "-") for qid in case_questions):
            raise ValueError(f"{path}: unexpected document labels")
        spec = ({k: cfg[k] for k in ("systems", "provider", "budgets", "workers")}, provenance["code_hash"])
        if common is not None and spec != common:
            raise ValueError("Runs have different model settings, system settings, or runner code")
        common = spec
        questions.update(case_questions)
        observations.update(rows)
        manifests[state] = provenance
        docs[state] = {system: summarize([r for (_, name), r in rows.items() if name == system])
                       for system in SYSTEMS}
    group = {system: [row for (_, name), row in observations.items() if name == system] for system in SYSTEMS}
    paired = {system: {row["question_id"]: [row["scores"]["correct"]] for row in rows}
              for system, rows in group.items()}
    comparisons = {baseline: paired_comparison(paired["selector"], paired[baseline])
                   for baseline in SYSTEMS if baseline != "selector"}
    corrected = holm({name: comp["mcnemar"]["p_raw"] for name, comp in comparisons.items()})
    for name, comp in comparisons.items():
        comp["p_holm"] = corrected[name]
        for field in ("cost_usd", "latency_s"):
            comp[f"paired_delta_{field}"] = distribution([
                observations[qid, "selector"][field] - observations[qid, name][field]
                for qid in questions])
    audit, by_q = selector_audit(group["selector"], questions)
    flat = []
    for qid, question in sorted(questions.items()):
        for system in SYSTEMS:
            row = observations[qid, system]
            route = by_q[qid] if system == "selector" else {}
            prediction = row["prediction"] or {}
            flat.append({"question_id": qid, "category": question["category"],
                         "unanswerable": question["unanswerable"], "system": system, "status": row["status"],
                         "correct": row["scores"]["correct"], "abstained": row["scores"]["abstained"],
                         "latency_s": round(row["latency_s"], 6), "cost_usd": round(row["cost_usd"], 8),
                         "reference": question["reference_answer"], "answer": prediction.get("answer", ""),
                         "values": json.dumps(prediction.get("values", []), ensure_ascii=False),
                         "citations": json.dumps(prediction.get("citations", []), ensure_ascii=False),
                         "selector_decision": route.get("decision", ""),
                         "selector_checks": " / ".join(f"{s['stage']}={s['reason']}" for s in route.get("stages", []))})
    slices = {category: {system: summarize([r for r in rows if r["category"] == category])
                         for system, rows in group.items()}
              for category in sorted({q["category"] for q in questions.values()})}
    sensitivity = {}
    for tolerance in (.0100001, .0500001):
        by_system = {}
        for name, rows in group.items():
            newly_correct = []
            for row in rows:
                q = questions[row["question_id"]]
                proposed = row["prediction"]
                if (row["status"] == "ok" and not row["scores"]["correct"] and not q["unanswerable"]
                        and not proposed["abstain"]
                        and numeric_match(q["expected_values"], proposed["values"], q["rel_tol"], tolerance)):
                    newly_correct.append(row["question_id"])
            by_system[name] = {"correct": sum(row["scores"]["correct"] for row in rows) + len(newly_correct),
                               "added_question_ids": sorted(newly_correct)}
        sensitivity[str(round(tolerance, 2))] = by_system
    args.output.mkdir(parents=True, exist_ok=True)
    write_json(args.output / "metrics.json", {
        "mode": "new_model_runs", "model": common[0]["provider"]["model"],
        "systems": {name: summarize(rows) for name, rows in group.items()},
        "by_document": docs, "by_category": slices, "comparisons": comparisons, "selector": audit,
        "provenance": manifests, "exploratory_absolute_tolerance_crore": sensitivity,
        "latency_note": "End-to-end cell wall time including count calls, retrieval and semantic reviews. "
                        "Four workers shared each document run. Pooled p95 is descriptive.",
        "inference_note": "Pairs are questions. Each system was executed once per question. "
                          "Intervals omit between-document variation and within-table dependence.",
    })
    write_json(args.output / "selector_decisions.json", by_q)
    csv_write(args.output / "per_question.csv", flat)


if __name__ == "__main__":
    main()
