"""Prepare the Gujarat Volume I comparison using checked source spans."""
import hashlib
import json
import urllib.request
from pathlib import Path

from read_vs_rag.corpus import Corpus
from read_vs_rag.io import load_jsonl

ROOT = Path(__file__).resolve().parents[2]

SOURCE = 'https://cag.gov.in/uploads/state_accounts_report/account-report-FA-VOL-I-2024-25-069c52aa2b34bf9-63690940.pdf'
PDF = ROOT / 'runs/source/gujarat.pdf'
CORPUS = ROOT / 'data/corpora/gujarat-live'
DOCUMENT = 'gujarat-vol-i.md'
OUT = CORPUS.parent / 'gujarat-live-questions.jsonl'
POSITION = [(722, 748)]
RECEIPTS = [(949, 957)]
NATURE = [(2271, 2278), (2293, 2293)]
FUNCTION = [(1923, 1936)]
SPANS = {
    'arith-001': (RECEIPTS + [(1073, 1073), (1297, 1297)], 'crore'),
    'unans-001': ([], None), 'unans-002': ([], None), 'unans-003': ([], None),
    'lookup-010': (POSITION + [(807, 807)], 'crore'),
    'lookup-011': (POSITION + [(751, 751)], 'crore'),
    'lookup-012': (POSITION + [(794, 794)], 'crore'),
    'lookup-013': (POSITION + [(800, 804)], 'crore'),
    'lookup-014': (POSITION + [(781, 781)], 'crore'),
    'lookup-015': (RECEIPTS + [(963, 965)], 'crore'),
    'lookup-016': (RECEIPTS + [(963, 965)], 'crore'),
    'lookup-017': (RECEIPTS + [(982, 982)], 'crore'),
    'lookup-018': (RECEIPTS + [(1024, 1026)], 'crore'),
    'lookup-019': (RECEIPTS + [(982, 982)], 'crore'),
    'arith-010': (RECEIPTS + [(963, 965)], 'crore'),
    'arith-011': (RECEIPTS + [(1024, 1026)], 'crore'),
    'arith-012': (POSITION + [(807, 807)], 'crore'),
    'agg-010': (NATURE + [(2296, 2296)], 'crore'),
    'lookup-020': (NATURE + [(2296, 2296)], 'crore'),
    'agg-011': ([(832, 834)], 'crore'),
    'conv-002': (RECEIPTS + [(1298, 1302)], 'crore'),
    'lookup-030': (NATURE + [(2298, 2298)], 'crore'),
    'lookup-031': (NATURE + [(2300, 2300)], 'crore'),
    'lookup-032': (NATURE + [(2309, 2309)], 'crore'),
    'lookup-033': (NATURE + [(2311, 2311)], 'crore'),
    'lookup-034': (NATURE + [(2299, 2299)], 'crore'),
    'agg-020': (FUNCTION + [(2259, 2265)], 'crore'),
    'arith-020': (NATURE + [(2315, 2315)], 'crore'),
    'arith-021': (NATURE + [(2309, 2309)], 'percent'),
    'arith-022': (NATURE + [(2300, 2300)], 'crore'),
    'lookup-035': (NATURE + [(2305, 2305)], 'crore'),
    'lookup-036': (NATURE + [(2303, 2303)], 'crore'),
}
NEW = [
    ('vol1-transport-01', 'lookup', 'In Statement 4A, what was the capital expenditure on Roads and Bridges in 2024-25?',
     '16,513.22 crore INR in the Capital column.', [16513.22], FUNCTION + [(2203, 2203)]),
    ('vol1-transport-02', 'arithmetic', 'In Statement 4A, by how much did the 2024-25 capital expenditure on Roads and Bridges exceed that on Road Transport?',
     '16,513.22 minus 1,710.36 gives 14,802.86 crore INR.', [14802.86], FUNCTION + [(2203, 2204)]),
    ('vol1-travel-01', 'arithmetic', 'In Statement 4B, by how much did total Domestic Travel Expenses increase from 2023-24 to 2024-25?',
     '198.70 minus 144.23 gives 54.47 crore INR.', [54.47], NATURE + [(2303, 2303)]),
    ('vol1-expenses-01', 'aggregation', 'In Statement 4B, what was the combined 2024-25 total expenditure on Office Expenses and Publication?',
     '1,127.35 plus 18.73 gives 1,146.08 crore INR.', [1146.08], NATURE + [(2304, 2304), (2306, 2306)]),
]


def main():
    import pymupdf4llm

    if not PDF.exists():
        PDF.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE, timeout=45) as response:
            data = response.read(10_000_000)
        PDF.write_bytes(data)
    pdf_hash = hashlib.sha256(PDF.read_bytes()).hexdigest()
    CORPUS.mkdir(parents=True, exist_ok=True)
    markdown = pymupdf4llm.to_markdown(str(PDF))
    (CORPUS / DOCUMENT).write_text(markdown, encoding='utf-8', newline='\n')
    corpus = Corpus(CORPUS)
    print('PDF SHA256', pdf_hash, 'Markdown SHA256', corpus.hashes[DOCUMENT])
    expected_manifest = Path(__file__).with_name('source.json')
    if expected_manifest.exists():
        pinned = json.loads(expected_manifest.read_text(encoding='utf-8'))
        if pdf_hash != pinned['pdf_sha256'] or corpus.hashes[DOCUMENT] != pinned['markdown_sha256']:
            raise ValueError('Source or conversion differs from the pinned evidence coordinates')

    def item(qid, category, question, reference, figures, spans, unit, unanswerable, origin):
        return {
            'id': qid, 'category': category, 'split': 'test', 'verified': True,
            'unanswerable': unanswerable, 'question': question, 'reference_answer': reference,
            'expected_values': [{'value': v, 'unit': unit} for v in figures],
            'gold_spans': [{'doc': DOCUMENT, 'start': start, 'end': end} for start, end in spans],
            'rel_tol': 0, 'abs_tol': .0050001, 'corpus_hashes': corpus.hashes, 'annotation_origin': origin,
        }

    rows = []
    for q in load_jsonl(ROOT / 'data/upstream/questions.jsonl'):
        if q['id'] not in SPANS:
            continue
        spans, unit = SPANS[q['id']]
        figures = q.get('expected_figures') or []
        reference = q['reference_answer']
        if q['id'] == 'lookup-034':
            figures = [0.0]  # Printed as '..'; distinguish zero/nil from an unavailable answer.
        rows.append(item(q['id'], 'lookup' if q['id'] == 'conv-002' else q['category'], q['question'],
                         reference, figures, spans, unit, q['unanswerable'], 'TwoSpoon, remapped to Volume I PDF'))
    for qid, category, question, reference, figures, spans in NEW:
        rows.append(item(qid, category, question, reference, figures, spans, 'crore', False,
                         'New question from checked CAG Volume I lines'))
    OUT.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    print('Prepared', len(rows), 'questions')


if __name__ == '__main__':
    main()
