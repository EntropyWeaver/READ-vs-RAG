"""Explicit-unit grading and evidence coordinates. No lexical proxy is called faithfulness."""

import json
import math
import re
from collections import Counter

from .corpus import normalize

UNITS = {
    "inr": ("inr", 1.), "rupee": ("inr", 1.), "rupees": ("inr", 1.),
    "crore": ("inr", 1e7), "lakh": ("inr", 1e5), "thousand_inr": ("inr", 1e3),
    "eur": ("eur", 1.), "usd": ("usd", 1.), "percent": ("percent", 1.),
    "%": ("percent", 1.), "count": ("count", 1.), "ratio": ("ratio", 1.),
}


def parse_prediction(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)[:-3].strip()
    result = json.loads(text)
    if not isinstance(result, dict) or set(result) != {"answer", "abstain", "values", "citations"}:
        raise ValueError("Final answer must have exactly answer, abstain, values, citations")
    if not isinstance(result["answer"], str) or type(result["abstain"]) is not bool:
        raise ValueError("answer must be text; abstain must be boolean")
    if not isinstance(result["values"], list) or not isinstance(result["citations"], list):
        raise ValueError("values and citations must be lists")
    for v in result["values"]:
        if set(v) != {"value", "unit"} or type(v["value"]) not in (int, float) or not math.isfinite(v["value"]):
            raise ValueError("Each value must have a finite numeric value and an explicit unit")
        if not isinstance(v["unit"], str) or v["unit"].casefold() not in UNITS:
            raise ValueError("Unknown unit; use a unit documented in the answer schema")
    for c in result["citations"]:
        if set(c) != {"doc", "start", "end"} or not isinstance(c["doc"], str):
            raise ValueError("Invalid citation schema")
        if type(c["start"]) is not int or type(c["end"]) is not int or not 1 <= c["start"] <= c["end"]:
            raise ValueError("Invalid citation coordinates")
    if result["abstain"] and result["values"]:
        raise ValueError("An abstention must not contain a proposed numeric answer")
    return result


def validate_questions(questions, corpus):
    seen = set()
    for q in questions:
        if not isinstance(q.get("id"), str) or not q["id"].strip():
            raise ValueError("Question ID must be nonempty text")
        if q["id"] in seen:
            raise ValueError(f"Duplicate question ID: {q['id']}")
        seen.add(q["id"])
        for field in ("question", "category", "split", "reference_answer"):
            if not isinstance(q.get(field), str) or not q[field].strip():
                raise ValueError(f"Question {q['id']}: missing {field}")
        if q["split"] not in {"dev", "test"}:
            raise ValueError("split must be dev or test")
        if type(q.get("verified")) is not bool or type(q.get("unanswerable")) is not bool:
            raise ValueError("verified and unanswerable must be booleans")
        if not q.get("corpus_hashes") or q["corpus_hashes"] != corpus.hashes:
            raise ValueError(f"Question {q['id']}: corpus hashes differ; revalidate evidence after conversion")
        for span in q.get("gold_spans", []):
            corpus.lines(span["doc"], span["start"], span["end"])
        if not q["unanswerable"] and not q.get("gold_spans"):
            raise ValueError(f"Answerable question {q['id']} needs evidence annotations")
        for v in q.get("expected_values", []):
            if type(v.get("value")) not in (int, float) or not math.isfinite(v["value"]) or v.get("unit") not in UNITS:
                raise ValueError("Expected values need a known explicit unit and finite number")
        if q["unanswerable"] and (q.get("expected_values") or q.get("answer_aliases")):
            raise ValueError("Unanswerable question cannot have expected answers")
        if q.get("rel_tol", 1e-4) < 0 or q.get("abs_tol", 1e-6) < 0:
            raise ValueError("Numeric tolerances cannot be negative")
    if not questions:
        raise ValueError("Empty question set")


def span_lines(spans):
    return {(s["doc"], n) for s in spans for n in range(s["start"], s["end"] + 1)}


def numeric_match(expected, predicted, rel_tol=1e-4, abs_tol=1e-6):
    # abs_tol is expressed in EACH expected value's unit, not an implicit crore.
    if len(expected) != len(predicted):
        return False  # prevents shotgun answers and reusing one prediction for two gold values
    edges = []
    for e in expected:
        dim, scale = UNITS[e["unit"].casefold()]
        choices = []
        for i, p in enumerate(predicted):
            pdim, pscale = UNITS[p["unit"].casefold()]
            if dim == pdim and math.isclose(e["value"], p["value"] * pscale / scale,
                                            rel_tol=rel_tol, abs_tol=abs_tol):
                choices.append(i)
        edges.append(choices)
    # Small bipartite matching; robust with repeated or nearby expected values.
    assigned = {}
    def visit(i, visited):
        for j in edges[i]:
            if j in visited:
                continue
            visited.add(j)
            if j not in assigned or visit(assigned[j], visited):
                assigned[j] = i
                return True
        return False
    return all(visit(i, set()) for i in range(len(expected)))


def token_f1(answer, references):
    a = Counter(normalize(answer)[0].split())
    best = 0.
    for ref in references:
        b = Counter(normalize(ref)[0].split())
        overlap = sum((a & b).values())
        best = max(best, 2 * overlap / (sum(a.values()) + sum(b.values())) if a or b else 1.)
    return best


def score(question, prediction, exposed, corpus, retrieved_chunks=(), total_relevant_chunks=None):
    gold = span_lines(question.get("gold_spans", []))
    seen = {(e["doc"], e["line"]) for e in exposed}
    abstain = prediction["abstain"]
    expected = question.get("expected_values", [])
    aliases = question.get("answer_aliases", [])
    numeric = numeric_match(expected, prediction["values"], question.get("rel_tol", 1e-4),
                            question.get("abs_tol", 1e-6)) if expected else None
    exact = normalize(prediction["answer"])[0] in {normalize(s)[0] for s in aliases} if aliases else None
    if question["unanswerable"]:
        correct = abstain
    elif abstain:
        correct = False
    elif numeric is not None:
        correct = numeric
    else:
        correct = exact  # None => requires semantic/human review, never silently counted as false
    citations = prediction["citations"]
    valid, supported, relevant, cited = 0, 0, 0, set()
    for c in citations:
        # Validate BEFORE materialising a potentially enormous model-supplied range.
        try:
            corpus.lines(c["doc"], c["start"], c["end"])
        except ValueError:
            continue
        points = span_lines([c])
        valid += 1
        supported += points <= seen
        relevant += bool(points & gold)
        cited |= points
    binary_relevance = [bool({(e["doc"], e["line"]) for e in c["entries"]} & gold)
                        for c in retrieved_chunks]
    first = next((i for i, v in enumerate(binary_relevance, 1) if v), None)
    dcg = sum(v / math.log2(i + 1) for i, v in enumerate(binary_relevance, 1))
    ideal_n = min(total_relevant_chunks or 0, len(binary_relevance))
    idcg = sum(1 / math.log2(i + 1) for i in range(1, ideal_n + 1))
    precision = relevant / len(citations) if citations else None
    recall = len(cited & gold) / len(gold) if gold else None
    return {
        "correct": correct, "numeric_correct": numeric, "text_exact": exact,
        "token_f1_diagnostic": token_f1(prediction["answer"], aliases or [question["reference_answer"]]),
        "abstained": abstain, "unanswerable": question["unanswerable"],
        "line_recall": len(seen & gold) / len(gold) if gold else None,
        "all_gold_lines_seen": gold <= seen if gold else None,
        "reciprocal_rank": 1 / first if first else (0. if gold and total_relevant_chunks is not None else None),
        "hit_at_k": bool(first) if total_relevant_chunks is not None and gold else None,
        "chunk_recall_at_k": sum(binary_relevance) / total_relevant_chunks if total_relevant_chunks else None,
        "ndcg_at_k": dcg / idcg if idcg else (0. if total_relevant_chunks else None),
        "retrieved_chunk_annotation_precision": sum(binary_relevance) / len(binary_relevance)
        if binary_relevance and gold else None,
        "citation_validity": valid / len(citations) if citations else None,
        "citation_seen_fraction": supported / len(citations) if citations else None,
        "citation_gold_overlap_precision": precision, "citation_gold_line_recall": recall,
        "has_citation": bool(citations), "unique_lines_seen": len(seen),
        "grading_signal": "abstention" if question["unanswerable"] else
        ("numeric" if numeric is not None else "text_exact" if exact is not None else "needs_review"),
    }
