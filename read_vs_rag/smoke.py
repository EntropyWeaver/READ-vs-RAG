"""Offline diagnostic only. Scripted tool use must never be reported as READ accuracy."""

import time

from .corpus import ReadTools
from .io import provenance, write_json
from .metrics import span_lines
from .retrieval import Retriever
from .runner import load_experiment


def smoke(output):
    _, _, corpus, questions = load_experiment("configs/pilot.json")
    tools = ReadTools(corpus)
    normalized = tools.call("memory_grep", {"query": "48964.89"})
    naive = ReadTools(corpus, normalized=False).call("memory_grep", {"query": "48964.89"})
    if not normalized["entries"] or naive["entries"]:
        raise AssertionError("Normalization fixture failed")
    r = Retriever(corpus, {"retriever": "bm25", "chunk_chars": 1000, "overlap_lines": 2,
                           "contextual": True, "k": 8})
    rows = []
    for q in questions:
        started = time.perf_counter()
        hits = r.search(q["question"])
        elapsed = time.perf_counter() - started
        seen = {(line.doc, line.line) for c, _ in hits for line in c.lines}
        gold = span_lines(q["gold_spans"])
        rows.append({"question_id": q["id"], "retrieval_s": elapsed, "retrieved_chunks": len(hits),
                     "annotated_line_recall": len(seen & gold) / len(gold) if gold else None})
    result = {"source": "local_offline_synthetic_fixture", "llm_calls": 0,
              "claim": "Tool and retrieval plumbing only; no READ-vs-RAG generative conclusion.",
              "normalized_search_hits": len(normalized["entries"]), "naive_search_hits": len(naive["entries"]),
              "bm25_build_s": r.build_s, "rows": rows, "provenance": provenance()}
    write_json(output, result)
    return result
