"""Download pinned CAG reports, reproduce their text and generate holdout configurations."""

import csv
import json
import urllib.request
from pathlib import Path

from read_vs_rag.corpus import Corpus
from read_vs_rag.io import sha256_file, write_json
from read_vs_rag.metrics import validate_questions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))


def canonical_markdown(raw):
    # Keep one blank line between text blocks. The converter can vary blank
    # counts around diagrams while preserving rendered content.
    lines = []
    for line in raw.splitlines():
        if line.strip():
            lines.append(line)
        elif not lines or lines[-1]:
            lines.append("")
    return "\n".join(lines) + "\n"


def prepare_source(state, source):
    import pymupdf
    import pymupdf4llm

    pdf = ROOT / "runs" / "source" / f"{state}.pdf"
    root = ROOT / "data" / "corpora" / f"selector-{state}"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    if not pdf.exists():
        with urllib.request.urlopen(source["url"], timeout=60) as response:
            data = response.read(25_000_001)
        if len(data) > 25_000_000:
            raise ValueError(f"{state}: source exceeds expected size")
        pdf.write_bytes(data)
    if sha256_file(pdf) != source["pdf_sha256"]:
        raise ValueError(f"{state}: PDF differs from the pinned source")
    with pymupdf.open(pdf) as document:
        if len(document) != source["pages"]:
            raise ValueError(f"{state}: PDF page count differs")
    markdown = root / f"{state}-vol-i.md"
    # Convert with pinned versions before using these coordinates.
    text = canonical_markdown(pymupdf4llm.to_markdown(str(pdf)))
    markdown.write_text(text, encoding="utf-8", newline="\n")
    if sha256_file(markdown) != source["markdown_sha256"]:
        raise ValueError(f"{state}: Markdown conversion differs from annotations")
    return root, markdown.name


def prepare_questions(state, annotations, root, doc):
    corpus = Corpus(root)
    questions = []
    for row in annotations:
        if row["state"] != state:
            continue
        amounts = [] if row["expected_crore"] == "-" else row["expected_crore"].split(",")
        spans = []
        for span in [] if row["spans"] == "-" else row["spans"].split(","):
            first, _, last = span.partition("-")
            spans.append({"doc": doc, "start": int(first), "end": int(last or first)})
        questions.append({
            "id": f"{state}-{row['id']}", "question": row["question"], "category": row["category"],
            "split": "test", "verified": True, "reference_answer": row["reference_answer"],
            "unanswerable": row["category"] == "abstention", "gold_spans": spans,
            "corpus_hashes": corpus.hashes, "rel_tol": 0, "abs_tol": .0050001,
            "expected_values": [{"value": float(amount), "unit": "crore"} for amount in amounts],
        })
    validate_questions(questions, corpus)
    path = root.with_suffix(".jsonl")
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in questions), encoding="utf-8")
    return path


def main():
    baseline = HERE.parent / "gujarat-volume-i"
    read_bm25 = json.loads((baseline / "read-bm25.json").read_text(encoding="utf-8"))
    cfg = json.loads((baseline / "controls.json").read_text(encoding="utf-8"))
    read = next(system for system in read_bm25["systems"] if system["name"] == "read")
    hybrid = next(system for system in cfg["systems"] if system["name"] == "hybrid_rrf")
    with (HERE / "questions.tsv").open(encoding="utf-8", newline="") as file:
        annotations = list(csv.DictReader(file, delimiter="\t"))
    for state, spec in SOURCES.items():
        root, doc = prepare_source(state, spec)
        questions = prepare_questions(state, annotations, root, doc)
        config = {
            **cfg, "project_root": "..", "dataset_kind": f"CAG {state.title()} 2024-25 Finance Accounts Volume I",
            "corpus": root.relative_to(ROOT).as_posix(), "questions": questions.relative_to(ROOT).as_posix(),
            "workers": 4, "max_run_cost_usd": 1.25, "max_run_tokens": 900000,
            "systems": [hybrid, read, {"name": "selector", "kind": "selector",
                                       "hybrid": hybrid["name"], "read": read["name"]}],
        }
        dest = ROOT / "runs" / f"selector-{state}.json"
        write_json(dest, config)
        print(f"{state}: {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
