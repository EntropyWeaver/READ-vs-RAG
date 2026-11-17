"""Render the measured accuracy and API cost with Matplotlib."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
LABELS = {'read': 'READ', 'bm25': 'BM25', 'dense': 'BGE largo', 'dense_short': 'BGE corto',
          'hybrid_rrf': 'Híbrido RRF', 'agentic_bm25': 'BM25 iterativo'}


def main():
    results = HERE / 'results'
    data = json.loads((results / 'metrics.json').read_text(encoding='utf-8'))
    systems = data['systems']
    names = sorted(systems, key=lambda s: -systems[s]['accuracy']['mean'])
    labels = [LABELS[s] for s in names]
    scores = [100 * systems[s]['accuracy']['mean'] for s in names]
    error_bars = [[100 * abs(systems[s]['accuracy']['mean'] - systems[s]['accuracy'][side]) for s in names]
                  for side in ('low', 'high')]
    costs = [100 * systems[s]['cost_usd_latest_cells']['mean'] for s in names]
    matplotlib.rcParams.update({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none',
                                'svg.hashsalt': 'gujarat-v1', 'axes.spines.top': False, 'axes.spines.right': False})
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.3, 4.1), sharey=True, width_ratios=[1.35, 1])
    colors = ['#11766b' if name == 'read' else '#486282' for name in names]
    positions = range(len(names))
    left.errorbar(scores, positions, xerr=error_bars, fmt='none', capsize=4, ecolor='#748098', zorder=1)
    left.scatter(scores, positions, color=colors, s=75, zorder=2)
    left.set(yticks=list(positions), yticklabels=labels, xlim=(0, 103), xlabel='Aciertos (%) · IC 95% Wilson')
    left.invert_yaxis()
    right.barh(positions, costs, color=colors, height=.55)
    right.set(xlabel='Centavos de USD / pregunta')
    for axis in (left, right):
        axis.grid(axis='x', alpha=.18)
        axis.set_axisbelow(True)
    fig.suptitle('READ y cinco variantes RAG en las cuentas de Gujarat', fontsize=15, weight='bold')
    fig.text(.5, .015, f"GPT-5.4 mini · {data['n_questions']} preguntas por sistema · Un informe de 94 páginas",
             ha='center', fontsize=9, color='#4b5563')
    fig.tight_layout(rect=(0, .07, 1, .93))
    svg = results / 'comparison.svg'
    fig.savefig(svg, metadata={'Date': None})
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
