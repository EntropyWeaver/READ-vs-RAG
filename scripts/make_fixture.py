"""Generate controlled fixtures. Synthetic tests are never evidence of general performance."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from read_vs_rag.corpus import Corpus

ROOT = Path(__file__).resolve().parents[1]
corpus = Corpus(ROOT / "examples/corpus")


def span(doc, marker):
    matches = [i for i, line in enumerate(corpus.docs[doc], 1) if marker == line]
    if not matches:
        matches = [i for i, line in enumerate(corpus.docs[doc], 1) if marker in line]
    if len(matches) != 1:
        raise ValueError(f"Ambiguous marker: {marker}")
    return {"doc": doc, "start": matches[0], "end": matches[0]}


questions = []
def add(qid, category, question, reference, value=None, unit=None, markers=(), aliases=(),
        split="dev", unanswerable=False):
    questions.append({"id": qid, "category": category, "question": question,
                      "reference_answer": reference, "expected_values":
                      [{"value": value, "unit": unit}] if value is not None else [],
                      "answer_aliases": list(aliases), "gold_spans": [span(*m) for m in markers],
                      "unanswerable": unanswerable, "verified": True,
                      "annotation_origin": "synthetic_programmatic_fixture", "split": split,
                      "rel_tol": 1e-5, "abs_tol": 1e-6, "corpus_hashes": corpus.hashes})


F, OPS = "finance.md", "operations.md"
add("dev-lookup", "lookup", "What was Aruna's revenue surplus in 2024–25?", "18,942.94 crore INR.",
    18942.94, "crore", [(F, "Amounts are in crore INR. The right"), (F, "| Revenue surplus")])
add("dev-arithmetic", "arithmetic", "What is the difference between the fiscal deficit and revenue surplus in 2024–25?",
    "48,964.89 minus 18,942.94 = 30,021.95 crore INR.", 30021.95, "crore",
    [(F, "Amounts are in crore INR. The right"), (F, "| Fiscal deficit"), (F, "| Revenue surplus")])
add("dev-units", "units", "How much was added to medical education loans? Express the amount in crore INR.",
    "70,000 lakh INR = 700 crore INR.", 700., "crore", [(F, "Amounts are in lakh"), (F, "| Medical education")])
add("dev-owner", "navigation", "Who owns onboarding?", "Service Desk", markers=[(OPS, "onboarding owner")],
    aliases=["Service Desk", "The Service Desk"])
add("dev-negative", "sign", "What was the cumulative expenditure adjustment?", "-67,278.26 crore INR.",
    -67278.26, "crore", [(F, "| Cumulative expenditure adjustment"), (F, "Amounts are in crore INR.")])
add("dev-unans-year", "unanswerable", "What was Aruna's fiscal deficit in 2027–28?", "Not reported.", unanswerable=True)
add("dev-nearzero", "units", "What was the closing small residual bank loan, in rupees?", "2,000 INR.",
    2000., "inr", [(F, "Amounts are in lakh"), (F, "| Small residual bank loan")])
add("dev-injection", "instruction_in_document", "How many approvals does a release need?", "2 approvals.",
    2, "count", [(OPS, "A release needs")])
add("test-prioryear", "temporal", "What were revenue receipts in 2023–24?", "222,762.73 crore INR.",
    222762.73, "crore", [(F, "Amounts are in crore INR. The right"), (F, "| Revenue receipts")], split="test")
add("test-ratio", "arithmetic", "What percentage of current revenue receipts was spent on revenue expenditure?",
    "199611.44 / 218554.38 × 100 = 91.3321627 percent.", 199611.44 / 218554.38 * 100, "percent",
    [(F, "| Revenue receipts"), (F, "| Revenue expenditure")], split="test")
add("test-retention", "lookup", "How many days are archived audit logs retained?", "90 days.",
    90, "count", [(OPS, "Archived audit logs")], split="test")
add("test-escalation", "navigation", "Who receives escalations for lost source data?", "Data Steward",
    markers=[(OPS, "must be escalated")], aliases=["Data Steward", "The Data Steward"], split="test")
add("test-unans-state", "unanswerable", "What was Maharashtra's revenue surplus?", "Not reported.",
    unanswerable=True, split="test")
add("test-unans-rate", "unanswerable", "What interest rate did medical education borrowers pay?", "Not reported.",
    unanswerable=True, split="test")
add("test-water", "lookup", "What was the closing balance of water supply loans in crore INR?", "323.7282 crore INR.",
    323.7282, "crore", [(F, "Amounts are in lakh"), (F, "| Water supply")], split="test")
add("test-growth", "arithmetic", "By how much did revenue expenditure grow between the two years?",
    "10,325.74 crore INR.", 10325.74, "crore", [(F, "| Revenue expenditure"),
    (F, "Amounts are in crore INR. The right")], split="test")

(ROOT / "examples/questions.jsonl").write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8")
print(f"Wrote {len(questions)} synthetic fixture questions; do not use for a general superiority claim.")
