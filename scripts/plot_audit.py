"""Publication-style charts from measured published rows, never generated imagery."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / "reports/paper_audit"
data = json.loads((out / "audit.json").read_text(encoding="utf-8"))
rows = data["main"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False, "svg.hashsalt": "READ-vs-RAG",
                     "svg.fonttype": "none"})
fig, (ax, cost) = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
colors = ["#127c70" if r["system"] == "read" else "#e49a3c" if r["system"] == "bm25" else "#64748b" for r in rows]
means = [100*r["accuracy"]["mean"] for r in rows]
lo = [100*(r["accuracy"]["mean"]-r["accuracy"]["low"]) for r in rows]
hi = [100*(r["accuracy"]["high"]-r["accuracy"]["mean"]) for r in rows]
ax.barh([r["system"] for r in rows], means, color=colors, height=.62)
ax.errorbar(means, range(len(rows)), xerr=[lo, hi], fmt="none", ecolor="#111827", capsize=3)
ax.invert_yaxis()
ax.set(xlim=(0, 100), xlabel="Original accuracy (%) · 95% Wilson interval", title="Published outcome labels")
for i, r in enumerate(rows):
    ax.text(92, i, f"{r['n_correct']}/51", va="center", ha="right", fontsize=9)
for r, color in zip(rows, colors):
    x, y = r["recorded_cost_usd"]["mean"], 100*r["accuracy"]["mean"]
    cost.scatter(x, y, s=70, color=color)
    offset = (-7, 11) if r["system"] == "read_no_outline" else (-7, -15) if r["system"] == "read_naive_grep" else (5, 6)
    cost.annotate(r["system"], (x, y), xytext=offset, textcoords="offset points", fontsize=8)
cost.set(xlabel="Author-recorded generation cost ($ / question)", ylabel="Original accuracy (%)",
         title="Quality / recorded cost", xlim=(.01, .075), ylim=(0, 86))
cost.grid(alpha=.15)
fig.suptitle("READ vs chunked RAG · independent arithmetic audit", fontsize=15, weight="bold")
fig.text(.5, .02, "663 published executions · 51 questions · one financial report · Gemini 2.5 Pro\n"
         "These are author runs, not new model executions. READ vs BM25: Holm p = 1.00.",
         ha="center", fontsize=9, color="#374151")
fig.tight_layout(rect=(0, .10, 1, .93))
fig.savefig(out / "comparison.png", dpi=170)
fig.savefig(out / "comparison.svg", metadata={"Date": None})
svg = out / "comparison.svg"
svg.write_text("\n".join(line.rstrip() for line in svg.read_text(encoding="utf-8").splitlines()) + "\n", encoding="utf-8")
print(out / "comparison.png")
