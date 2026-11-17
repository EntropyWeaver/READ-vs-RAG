"""Compare paired live runs and export metrics without source-document excerpts."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from read_vs_rag.io import load_jsonl, write_json
from read_vs_rag.stats import distribution, holm, paired_comparison, wilson


def cell_cost(path):
    records = {row['id']: row for row in load_jsonl(path / 'budget.jsonl')}
    settled = [r for r in records.values() if r['event'] == 'settle']
    pending = [r for r in records.values() if r['event'] == 'reserve']
    return {'cost_from_provider_usage_usd': sum(r['cost_usd'] for r in settled),
            'unresolved_budget_reserve_usd': sum(r['cost_usd'] for r in pending),
            'settled_calls': len(settled), 'unresolved_calls': len(pending)}


def summarize(paths, output):
    questions = None
    rows = defaultdict(dict)
    design = None
    budgets = {}
    attempts = defaultdict(Counter)
    indexes = {}
    for path in paths:
        m = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
        exp = m['experiment']
        config = exp['config']
        this_design = {k: exp[k] for k in ('corpus', 'questions', 'code_hash', 'dependencies')}
        this_design['provider'] = config['provider']
        this_design['budgets'] = config['budgets']
        this_design['workers'] = config.get('workers', 1)
        if design is None:
            design = this_design
        elif this_design != design:
            raise ValueError('Runs differ in corpus, questions, model, code, limits, dependencies or workers')
        questions = {q['id']: q for q in exp['questions']}
        if config['repeats'] != [0]:
            raise ValueError('This study uses one repeat')
        for system in config['systems']:
            rows[system['name']]
        for row in load_jsonl(path / 'results.jsonl'):
            if row['fingerprint'] != m['fingerprint']:
                raise ValueError('Unexpected result fingerprint')
            system, question = row['system'], row['question_id']
            attempts[system][row['status']] += 1
            if question in rows[system] and rows[system][question]['attempt'] >= row['attempt']:
                raise ValueError(f'Duplicate or reordered attempt for {system}/{question}')
            rows[system][question] = row
        if (path / 'budget.jsonl').exists():
            budgets[path.name] = cell_cost(path)
        if (path / 'index_builds.jsonl').exists():
            indexes[path.name] = load_jsonl(path / 'index_builds.jsonl')

    systems, pairs, flat = {}, {}, []
    groups = defaultdict(list)
    for q in questions.values():
        groups[q['category']].append(q['id'])
    for name, cells in rows.items():
        graded = {qid: [r['scores']['correct']] for qid, r in cells.items()
                  if r['scores']['correct'] is not None}
        ok = [r for r in cells.values() if r['status'] == 'ok']
        correct = sum(v[0] for v in graded.values())
        systems[name] = s = {
            'expected': len(questions), 'completed': len(cells), 'statuses': dict(Counter(r['status'] for r in cells.values())),
            'attempt_statuses': dict(attempts[name]), 'accuracy': wilson(correct, len(graded)), 'correct': correct,
            'accuracy_bounds_including_missing': [correct / len(questions), (correct + len(questions) - len(graded)) / len(questions)],
            'latency_s_successful_cells': distribution([r['latency_s'] for r in ok]),
            'cost_usd_latest_cells': distribution([r['cost_usd'] for r in cells.values()]),
            'model_calls': distribution([len(r['calls']) for r in cells.values()]),
            'input_tokens': distribution([r['input_tokens'] for r in cells.values()]),
            'output_tokens': distribution([r['output_tokens'] for r in cells.values()]),
            'reasoning_tokens': distribution([r['thinking_tokens'] for r in cells.values()]),
            'category_accuracy': {cat: wilson(sum(graded[q][0] for q in ids if q in graded),
                                            sum(q in graded for q in ids)) for cat, ids in sorted(groups.items())},
        }
        for metric in ('line_recall', 'all_gold_lines_seen', 'has_citation', 'citation_validity',
                       'citation_seen_fraction', 'citation_gold_overlap_precision', 'ndcg_at_k', 'reciprocal_rank'):
            s[metric] = distribution([r['scores'].get(metric) for r in ok])
        s['abstention_answerable'] = distribution([r['scores']['abstained'] for r in ok if not r['scores']['unanswerable']])
        s['abstention_unanswerable'] = distribution([r['scores']['abstained'] for r in ok if r['scores']['unanswerable']])
        pairs[name] = graded
        for qid, q in questions.items():
            r = cells.get(qid, {})
            score, prediction = r.get('scores', {}), r.get('prediction') or {}
            flat.append({'system': name, 'question_id': qid, 'category': q['category'],
                         'status': r.get('status', 'pending'), 'correct': score.get('correct'),
                         'expected_values': json.dumps(q['expected_values']), 'values': json.dumps(prediction.get('values')),
                         'abstained': prediction.get('abstain'), 'line_recall': score.get('line_recall'),
                         'citation_seen_fraction': score.get('citation_seen_fraction'),
                         'cost_usd': r.get('cost_usd'), 'latency_s': r.get('latency_s'), 'attempt': r.get('attempt')})
    comparisons = {name: paired_comparison(pairs['read'], values) for name, values in pairs.items() if name != 'read'}
    adjusted = holm({name: comp['mcnemar']['p_raw'] for name, comp in comparisons.items() if comp['mcnemar']})
    for name, comp in comparisons.items():
        comp['p_holm'] = adjusted.get(name)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'metrics.json', {'model': design['provider']['model'], 'workers_per_run': design['workers'],
               'code_hash': design['code_hash'], 'dependencies': design['dependencies'], 'corpus': design['corpus'],
               'n_questions': len(questions), 'systems': systems, 'comparisons_vs_read': comparisons,
               'budgets': budgets, 'indexes': indexes})
    with (output / 'per_question.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(flat)
    print(json.dumps({name: [s['correct'], s['accuracy']['n'], s['completed']] for name, s in systems.items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    summarize(args.runs, args.output)
