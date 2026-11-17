"""Export a small, deterministic replay of the three published debugger cases."""

import argparse
import json
from pathlib import Path


CASES = {
    'lookup-016': (('bm25',), (5845, 5846, 5847, 5848), 'total'),
    'agg-020': (('hybrid_rrf',), (2109, 2259, 2261, 2265), 'consolidated'),
    'unans-002': (('hybrid_rrf',), (1, 3, 949, 953, 1073), 'scope'),
}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def trace_step(step, spans):
    result = step['result']
    entries = result.get('entries', [])
    # Show cited lines that were actually returned in this step, or a short preview.
    cited = [row for row in entries if row['text'].strip() and any(
        span['doc'] == row['doc'] and span['start'] <= row['line'] <= span['end'] for span in spans)]
    preview = cited or [row for row in entries if row['text'].strip()][:1]
    return {
        'tool': step['tool'], 'args': step['arguments'], 'seconds': round(step['latency_s'], 3),
        'returned': len(entries), 'total_matches': result.get('total_matches'),
        'truncated': bool(result.get('truncated')), 'documents': result.get('documents', []),
        'preview': [{'line': row['line'], 'text': row['text'][:280]} for row in preview[:3]],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path, help='Converted gujarat-vol-i.md')
    parser.add_argument('runs', type=Path, nargs='+', help='Original READ/BM25 and control results.jsonl files')
    parser.add_argument('--output', type=Path, default=Path('docs/debugger/cases.js'))
    args = parser.parse_args()
    lines = args.corpus.read_text(encoding='utf-8').splitlines()
    cells = {}
    for path in args.runs:
        for row in read_jsonl(path):
            key = row['question_id'], row['system']
            if key[0] not in CASES or key[1] not in ('read', *CASES[key[0]][0]):
                continue
            if key in cells or row['status'] != 'ok':
                raise ValueError(f'Expected one successful original result for {key}')
            cells[key] = row

    cases = []
    for question, (comparators, excerpt, case_id) in CASES.items():
        outputs = []
        for name in ('read', *comparators):
            row = cells[(question, name)]
            prediction = row['prediction']
            spans = prediction['citations']
            outputs.append({
                'system': name, 'answer': prediction['answer'], 'abstained': prediction['abstain'],
                'correct': row['scores']['correct'], 'citations': spans,
                'seconds': round(row['latency_s'], 2), 'usd': round(row['cost_usd'], 6),
                'steps': [trace_step(step, spans) for step in row['trace']],
            })
        cases.append({'id': case_id, 'question_id': question, 'outputs': outputs,
                      'evidence': [{'line': index, 'text': lines[index - 1]} for index in excerpt]})
    args.output.write_text('window.DEBUGGER_CASES = ' + json.dumps(cases, ensure_ascii=False, indent=2) + ';\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
