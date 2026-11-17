"""Recalculate published outcomes. This never generates answers or re-runs the authors' judge."""

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from .io import load_jsonl, sha256_file, utcnow, write_json
from .stats import bootstrap_mean, distribution, holm, paired_comparison, wilson

UPSTREAM_COMMIT = "c3c368d4a78b0a152f0dfe7f9f74110347f02397"
UPSTREAM_URL = "https://github.com/twospoon/READ"


def rate(values):
    xs = [v for v in values if v is not None]
    return wilson(sum(xs), len(xs))


def flatten(row, question):
    scores = row.get("scores") or {}
    judge = scores.get("judge") or {}
    exact = scores.get("exact_figure") or {}
    grounded = scores.get("grounded") or {}
    gold, exposed = set(question.get("gold_lines") or []), set(row.get("exposed_lines") or [])
    summary = row.get("tool_summary") or {}
    return {
        "system": row["system"], "question_id": row["question_id"], "category": row["category"],
        "difficulty": row["difficulty"], "source_unit": question.get("source_unit"),
        "correct": row.get("correct"), "judge_correct": judge.get("correct"),
        "exact_correct": exact.get("correct") if exact.get("applicable") else None,
        "numeric_grounded_proxy": grounded.get("grounded") if grounded.get("applicable") else None,
        "unanswerable": row["unanswerable"], "abstained": scores.get("abstained"),
        "annotated_line_recall": len(gold & exposed) / len(gold) if gold else None,
        "all_annotated_lines_seen": gold <= exposed if gold else None,
        "any_annotated_line_seen": bool(gold & exposed) if gold else None,
        "unique_lines_seen": len(exposed), "latency_s": row.get("latency_s"),
        "recorded_cost_usd": row.get("cost_usd"), "input_tokens": row.get("input_tokens"),
        "output_tokens": row.get("output_tokens"), "thinking_tokens": row.get("thinking_tokens"),
        "cache_read_tokens": row.get("cache_read_tokens"), "api_calls": row.get("api_calls"),
        "tool_calls": summary.get("n_tool_calls"), "error": bool(row.get("error")),
        "judge_error": bool(judge.get("error")),
        "empty_grep_rate": summary.get("empty_grep_rate"),
        "judge_input_tokens": (judge.get("usage") or {}).get("input_tokens"),
        "judge_output_tokens": (judge.get("usage") or {}).get("output_tokens"),
        "judge_thinking_tokens": (judge.get("usage") or {}).get("thinking_tokens"),
        "judge_primary_disagree": judge.get("correct") is not None and judge["correct"] != row["correct"],
    }


def summarize(rows, bootstrap_samples=10000):
    by_system = defaultdict(list)
    for row in rows:
        by_system[row["system"]].append(row)
    result = []
    for name, rs in sorted(by_system.items()):
        answerable = [r for r in rs if not r["unanswerable"]]
        unanswerable = [r for r in rs if r["unanswerable"]]
        acc = rate([r["correct"] for r in rs])
        cost = distribution([r["recorded_cost_usd"] for r in rs])
        right = sum(r["correct"] is True for r in rs)
        s = {"system": name, "n": len(rs), "n_correct": right, "accuracy": acc,
             "missing_verdicts": sum(r["correct"] is None for r in rs),
             "accuracy_answerable": rate([r["correct"] for r in answerable]),
             "abstention_on_unanswerable": rate([r["abstained"] for r in unanswerable]),
             "abstention_on_answerable": rate([r["abstained"] for r in answerable]),
             "judge_only_sensitivity": rate([r["judge_correct"] for r in rs]),
             "exact_numeric": rate([r["exact_correct"] for r in rs]),
             "numeric_grounded_proxy": rate([r["numeric_grounded_proxy"] for r in rs]),
             "all_annotated_lines_seen": rate([r["all_annotated_lines_seen"] for r in rs]),
             "any_annotated_line_seen": rate([r["any_annotated_line_seen"] for r in rs]),
             "annotated_line_recall": distribution([r["annotated_line_recall"] for r in rs]),
             "latency_s": distribution([r["latency_s"] for r in rs]), "recorded_cost_usd": cost,
             "cost_mean_ci": bootstrap_mean([r["recorded_cost_usd"] for r in rs
                                              if r["recorded_cost_usd"] is not None], bootstrap_samples),
             "recorded_cost_per_correct": cost["total"] / right if right else None,
             "judge_primary_disagreements": sum(r["judge_primary_disagree"] for r in rs),
             "error_rate": rate([r["error"] for r in rs]),
             "judge_error_rate": rate([r["judge_error"] for r in rs])}
        for field in ("input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens",
                      "api_calls", "tool_calls", "unique_lines_seen", "empty_grep_rate",
                      "judge_input_tokens", "judge_output_tokens", "judge_thinking_tokens"):
            s[field] = distribution([r[field] for r in rs])
        result.append(s)
    return sorted(result, key=lambda x: -(x["accuracy"]["mean"] or 0))


def comparisons(rows, family, samples):
    systems = defaultdict(dict)
    for r in rows:
        if r["correct"] is not None:
            systems[r["system"]][r["question_id"]] = [r["correct"]]
    if "read" not in systems:
        return []
    out = []
    for name in sorted(systems):
        if name == "read":
            continue
        c = paired_comparison(systems["read"], systems[name], samples)
        c.update({"reference": "read", "system": name, "family": family})
        out.append(c)
    adjusted = holm({c["system"]: c["mcnemar"]["p_raw"] for c in out if c["mcnemar"]})
    for c in out:
        c["p_holm"] = adjusted.get(c["system"])
    return out


def csv_write(path, rows):
    if not rows:
        return
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pct(value):
    return "N/A" if value is None else f"{100 * value:.1f}%"


def report_markdown(report):
    main = report["main"]
    s = ["# READ vs RAG — auditoría de los resultados publicados", "",
         "**Reanálisis de ejecuciones de terceros. No son nuevas llamadas a modelos nuestras.**", "",
         f"Fuente: [{UPSTREAM_URL}]({UPSTREAM_URL}), commit `{UPSTREAM_COMMIT}`.", "",
         f"Se validaron {report['n_rows']} registros: 357 principales y 306 del barrido. "
         "Los 51 IDs de preguntas coinciden en todas las condiciones. Un documento, "
         "un modelo (Gemini 2.5 Pro), una repetición. Se conservan las etiquetas originales.", "",
         "## Resultados principales", "",
         "| Sistema | Aciertos | Accuracy · IC 95% Wilson | Coste registrado/pregunta | Latencia p50 / p95 |",
         "|---|---:|---:|---:|---:|"]
    for x in main:
        a, c, t = x["accuracy"], x["recorded_cost_usd"], x["latency_s"]
        s.append(f"| {x['system']} | {x['n_correct']}/{x['n']} | {pct(a['mean'])} "
                 f"[{pct(a['low'])}, {pct(a['high'])}] | ${c['mean']:.4f} | "
                 f"{t['p50']:.1f}s / {t['p95']:.1f}s |")
    s += ["", "El coste y la latencia son los registrados por los autores para generación; "
          "no miden nuestra máquina y no son una factura completa de evaluación, conversión e indexación. "
          "Los tokens del juez se muestran por separado en `audit.json`.", "",
          "## Comparaciones pareadas", "",
          "Δ = READ − otro sistema. Bootstrap por pregunta (10.000 remuestreos, semilla fija). "
          "McNemar exacto, corrección de Holm sobre seis comparaciones de la familia principal.", "",
          "| Comparador | Δ puntos · IC bootstrap 95% | Gana READ / pierde | p Holm |",
          "|---|---:|---:|---:|"]
    for c in report["main_comparisons"]:
        d, m = c["delta"], c["mcnemar"]
        s.append(f"| {c['system']} | {100*d['mean']:+.1f} [{100*d['low']:+.1f}, "
                 f"{100*d['high']:+.1f}] | {m['wins']} / {m['losses']} | {c['p_holm']:.6g} |")
    s += ["", "**No se demuestra superioridad frente a BM25.** No significación tampoco demuestra "
          "equivalencia. El resultado se refiere a este informe financiero, no a todos los RAG.", "",
          "## Barrido denso publicado", "",
          "| Variante | Accuracy | Coste registrado/pregunta |",
          "|---|---:|---:|"]
    for x in report["sweep"]:
        s.append(f"| {x['system']} | {pct(x['accuracy']['mean'])} | "
                 f"${x['recorded_cost_usd']['mean']:.4f} |")
    s += ["", "El mejor ajuste se escogió sobre estas mismas preguntas. No es una estimación sobre "
          "un test independiente. `audit.json` incluye otra familia de seis comparaciones para el barrido.",
          "", "## Auditoría de medición", ""]
    s += [f"- {f}" for f in report["findings"]]
    s += ["", "## Alcance de las métricas", "",
          "`per_question.csv` conserva los denominadores y permite revisar cada caso. "
          "`slices.csv` desglosa categoría, dificultad y unidad. `review_queue.jsonl` contiene los "
          "desacuerdos entre juez y puntuación principal, con respuestas completas.", "",
          "La cobertura recalculada usa líneas anotadas y líneas expuestas. Es cobertura de esas "
          "anotaciones, que pueden ser incompletas; no demuestra fidelidad semántica ni citas correctas. "
          "El groundedness publicado es un proxy numérico heredado, no una validación independiente "
          "del documento. No hemos reconvertido ni auditado manualmente el PDF.", "",
          "## Reproducir", "", "```bash", "python -m read_vs_rag audit", "```", "",
          "Sin API ni dependencias externas. Primero ejecutar `python -m read_vs_rag fetch-upstream` "
          "para descargar los logs una vez; después funciona sin red. Los hashes de entrada se verifican "
          "contra `data/upstream/manifest.json`. El bootstrap es determinista.", ""]
    return "\n".join(s)


def report_html(report, reviews):
    # Self-contained interactive table; text escaped, no external scripts or CDNs.
    rows = "".join(
        f"<tr><td>{html.escape(x['system'])}</td><td>{x['n_correct']}/{x['n']}</td>"
        f"<td>{pct(x['accuracy']['mean'])}</td><td>{pct(x['accuracy']['low'])} – "
        f"{pct(x['accuracy']['high'])}</td><td>${x['recorded_cost_usd']['mean']:.4f}</td>"
        f"<td>{x['latency_s']['p50']:.1f}s</td><td>{x['latency_s']['p95']:.1f}s</td></tr>"
        for x in report["main"])
    cases = "".join(f"<details data-search='{html.escape(r['system']+' '+r['question_id'], quote=True)}'>"
                    f"<summary>{html.escape(r['system']+' · '+r['question_id'])} · "
                    f"original={r['correct']} / juez={r['judge_correct']}</summary>"
                    f"<p>{html.escape(r['question'])}</p><pre>{html.escape(r['answer'])}</pre>"
                    f"<p>Juez: {html.escape(r['judge_reason'])}</p></details>" for r in reviews)
    findings = "".join(f"<li>{html.escape(f)}</li>" for f in report["findings"])
    return """<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>READ / RAG · Evidence lab</title>
<style>:root{color-scheme:dark}body{margin:0;background:#10151d;color:#e7edf7;font:16px/1.6 system-ui}
main{max-width:1100px;margin:60px auto;padding:0 28px}small{color:#83dbba;letter-spacing:.16em}
h1{font-size:clamp(32px,6vw,64px);line-height:1.05}h2{margin-top:48px}p,li{max-width:90ch}
.tag{border-left:4px solid #efbd6b;padding:14px 22px;background:#25252a}.scroll{overflow:auto}
table{border-collapse:collapse;min-width:780px;width:100%}th,td{padding:12px;text-align:left;border-bottom:1px solid #334052}
th{color:#83dbba}a{color:#83dbba}details{padding:14px;border:1px solid #334052;margin:10px 0;border-radius:8px}
summary{cursor:pointer}pre{white-space:pre-wrap;word-break:break-word;background:#19222f;padding:16px}
input{padding:12px;background:#19222f;border:1px solid #526178;color:inherit;border-radius:6px;width:min(90%,480px)}
</style><main><small>ENTROPYWEAVER / EXPERIMENT 001</small><h1>READ vs RAG<br>Del titular a los datos.</h1>
<p class="tag">Reanálisis de 663 ejecuciones publicadas por TwoSpoon. No son llamadas nuevas nuestras.
51 preguntas · un informe financiero · Gemini 2.5 Pro.</p><h2>Calidad, coste y latencia</h2>
<p>Accuracy original, intervalo Wilson al 95%. Costes y tiempos registrados por los autores para generación.</p>
<div class="scroll"><table><thead><tr><th>Sistema</th><th>Aciertos</th><th>Accuracy</th><th>IC 95%</th>
<th>$/pregunta</th><th>p50</th><th>p95</th></tr></thead><tbody>""" + rows + """</tbody></table></div>
<p>READ no demuestra superioridad estadística frente a BM25 en este conjunto.</p><h2>Qué exige revisión</h2><ul>""" + findings + """</ul>
<h2>Inspeccionar desacuerdos</h2><label for="filter">Filtrar por sistema o ID</label><br>
<input id="filter" placeholder="dense, unans-001…"><section id="cases">""" + cases + """</section>
<p><a href="report.md">Informe completo</a> · <a href="audit.json">Estadísticas JSON</a> ·
<a href="per_question.csv">Resultados CSV</a> · <a href="https://arxiv.org/abs/2608.06305">Paper original</a></p>
<script>document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();
document.querySelectorAll('[data-search]').forEach(x=>x.hidden=!x.dataset.search.toLowerCase().includes(q))});</script></main></html>"""


def audit(source="data/upstream", output="reports/paper_audit", bootstrap_samples=10000):
    source, output = Path(source), Path(output)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        if not (source / name).exists():
            raise ValueError(f"Missing {name}. First run: python -m read_vs_rag fetch-upstream --destination {source}")
        if sha256_file(source / name) != meta["sha256"]:
            raise ValueError(f"Source hash mismatch: {name}")
    questions = {q["id"]: q for q in load_jsonl(source / "questions.jsonl") if q["verified"]}
    main_raw = load_jsonl(source / "results.jsonl")
    sweep_raw = load_jsonl(source / "results_sweep.jsonl")
    raw = main_raw + sweep_raw
    if len(raw) != 663:
        raise ValueError("Expected the pinned 663 source rows")
    keys = [(r["system"], r["question_id"], r["model"], r["seed"]) for r in raw]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate source cells; do not silently deduplicate")
    for name in {r["system"] for r in raw}:
        rs = [r for r in raw if r["system"] == name]
        if {r["question_id"] for r in rs} != questions.keys() or len(rs) != len(questions):
            raise ValueError(f"Incomplete paired matrix: {name}")
    main = [flatten(r, questions[r["question_id"]]) for r in main_raw]
    sweep = [flatten(r, questions[r["question_id"]]) for r in sweep_raw]
    reviews = []
    for r, f in zip(raw, main + sweep):
        if f["judge_primary_disagree"]:
            reviews.append({**f, "question": r["question"], "answer": r["answer"],
                            "judge_reason": r["scores"]["judge"].get("reason", "")})
    flagged = sum("awaiting human audit" in q.get("drafted_by", "") for q in questions.values())
    regex_cases = sum(r["unanswerable"] and r["judge_correct"] is True and r["correct"] is False
                      for r in main)
    findings = [
        f"En la matriz principal hay {regex_cases} respuestas a preguntas sin respuesta que el juez "
        "considera correctas y el detector de abstención puntúa como incorrectas. Incluyen «do not contain» "
        "y «do not specify». Se conservan ambas señales: no se sustituyen etiquetas sin revisión humana.",
        f"{flagged} preguntas marcadas verified=true conservan metadatos «awaiting human audit». "
        "Esto no prueba que falte la revisión, pero la procedencia requiere aclaración antes de "
        "llamarlas verificadas por nosotros.",
        "Solo hay 5 preguntas sin respuesta: cualquier tasa de alucinación derivada tiene gran incertidumbre. "
        "El detector publicado solo evalúa ese subconjunto; no mide todas las afirmaciones falsas.",
        "La puntuación numérica upstream permite tolerancia relativa del 0,5%, absoluta de 0,01 crore "
        "y dos interpretaciones de algunas cifras sin unidad. Puede aceptar errores pequeños y "
        "confundir unidades; el nuevo runner exige unidades explícitas y tolerancias por pregunta.",
        "El judge-only es un análisis de sensibilidad con las etiquetas LLM existentes, no una nueva "
        "verdad de referencia. Los intervalos y tests no corrigen sesgos del juez ni del corpus.",
    ]
    report = {"source": "published_author_runs_reanalysis", "generated_at": utcnow(),
              "upstream_commit": UPSTREAM_COMMIT, "n_rows": len(raw), "n_questions": len(questions),
              "bootstrap_samples": bootstrap_samples, "bootstrap_seed": 20261117,
              "main": summarize(main, bootstrap_samples), "sweep": summarize(sweep, bootstrap_samples),
              "main_comparisons": comparisons(main, "main_6", bootstrap_samples),
              "sweep_comparisons": comparisons([r for r in main if r["system"] == "read"] + sweep,
                                               "sweep_6_exploratory", bootstrap_samples),
              "findings": findings, "category_counts": dict(Counter(q["category"] for q in questions.values()))}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "audit.json", report)
    csv_write(output / "per_question.csv", main + sweep)
    slices = []
    for dim in ("category", "difficulty", "source_unit"):
        groups = defaultdict(list)
        for r in main + sweep:
            groups[(r["system"], str(r[dim]))].append(r)
        for (system, value), rs in sorted(groups.items()):
            a = rate([r["correct"] for r in rs])
            slices.append({"system": system, "dimension": dim, "value": value,
                           "n": a["n"], "accuracy": a["mean"], "ci_low": a["low"], "ci_high": a["high"]})
    csv_write(output / "slices.csv", slices)
    (output / "review_queue.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                                      for r in reviews), encoding="utf-8")
    (output / "report.md").write_text(report_markdown(report), encoding="utf-8")
    (output / "index.html").write_text(report_html(report, reviews), encoding="utf-8")
    return report
