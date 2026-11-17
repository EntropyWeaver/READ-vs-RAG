'use strict';

const sourceUrl = 'https://cag.gov.in/uploads/state_accounts_report/account-report-FA-VOL-I-2024-25-069c52aa2b34bf9-63690940.pdf';
const copy = {
  en: {
    title: 'Retrieval debugger', intro: 'Read the evidence, pick an answer, and see what the models did with it.',
    languages: 'Language', navigation: 'Experiment cases', evidence: 'Source evidence',
    coordinates: 'Line numbers refer to the Markdown conversion. Excerpts are in English.', source: 'Open the source PDF ↗',
    choose: 'Choose an answer', reveal: 'Reveal answers', retry: 'Reset case', results: 'What the systems answered',
    right: 'You got it.', wrong: 'The supported answer is', correct: 'Correct', incorrect: 'Incorrect',
    finding: 'What happened', citations: 'Cited lines', trace: 'Inspect tool trace', steps: 'steps',
    original: 'Original response', arguments: 'Tool arguments', documents: 'Documents', returned: 'lines returned',
    matches: 'total matches', clipped: 'Tool output was truncated.', excerpt: 'Preview of returned lines',
    note: 'Recorded benchmark runs · GPT-5.4 mini', report: 'Study report', repo: 'Code on GitHub',
    cases: {
      total: {
        name: 'Subtotal vs total', question: 'What was total revenue expenditure in 2024–25?',
        choices: ['148,743.95 crore', '199,611.44 crore', '45,112.87 crore'], answer: 1,
        focus: [5845, 5848],
        finding: 'Both systems cited lines 5845–5848. READ picked the amount that represents 74.52% of the total. BM25 picked the total in the same citation.',
      },
      consolidated: {
        name: 'The wrong breakdown', question: 'What was total Consolidated Fund expenditure in 2024–25?',
        choices: ['297,717.24 crore', '4,647.19 crore', '199,611.44 crore'], answer: 0,
        focus: [2265],
        finding: 'READ located the total and its three components. The hybrid added three figures from selected subheads in a different passage and treated the sum as the fund total.',
      },
      scope: {
        name: 'The wrong state', question: 'According to this volume, what was Maharashtra’s revenue surplus in 2024–25?',
        choices: ['33,477.03 crore', '18,942.94 crore', 'The volume does not report it'], answer: 2,
        focus: [3, 953, 1073],
        finding: 'The table covers Gujarat. READ gave Gujarat’s 2023–24 figure as Maharashtra’s 2024–25 surplus. The hybrid checked the document scope and abstained.',
      },
    },
  },
  es: {
    title: 'Depurador de recuperación', intro: 'Lee la evidencia, elige una respuesta y mira qué hicieron los modelos con ella.',
    languages: 'Idioma', navigation: 'Casos del experimento', evidence: 'Evidencia del informe',
    coordinates: 'Los números corresponden a la conversión a Markdown. Los extractos están en inglés.', source: 'Abrir el PDF original ↗',
    choose: 'Elige una respuesta', reveal: 'Revelar respuestas', retry: 'Reiniciar caso', results: 'Qué respondió cada sistema',
    right: 'Has acertado.', wrong: 'La respuesta respaldada es', correct: 'Correcta', incorrect: 'Incorrecta',
    finding: 'Qué pasó', citations: 'Líneas citadas', trace: 'Inspeccionar traza', steps: 'pasos',
    original: 'Respuesta original', arguments: 'Argumentos de la herramienta', documents: 'Documentos', returned: 'líneas devueltas',
    matches: 'coincidencias totales', clipped: 'La salida de la herramienta se truncó.', excerpt: 'Vista parcial de las líneas devueltas',
    note: 'Ejecuciones grabadas del benchmark · GPT-5.4 mini', report: 'Informe del estudio', repo: 'Código en GitHub',
    cases: {
      total: {
        name: 'Subtotal o total', question: '¿Cuál fue el gasto corriente total en 2024–25?',
        choices: ['148.743,95 crore', '199.611,44 crore', '45.112,87 crore'], answer: 1,
        focus: [5845, 5848],
        finding: 'Los dos sistemas citaron las líneas 5845–5848. READ eligió la cifra que representa el 74,52 % del total. BM25 eligió el total que figuraba en la misma cita.',
        answers: {read: 'El gasto corriente total de 2024–25 fue de 148.743,95 crore.',
                  bm25: 'El gasto corriente total de 2024–25 fue de 199.611,44 crore.'},
      },
      consolidated: {
        name: 'El desglose equivocado', question: '¿Cuál fue el gasto total del Fondo Consolidado en 2024–25?',
        choices: ['297.717,24 crore', '4.647,19 crore', '199.611,44 crore'], answer: 0,
        focus: [2265],
        finding: 'READ localizó el total y sus tres componentes. El híbrido sumó tres cifras de partidas seleccionadas en otro pasaje y presentó esa suma como el total del fondo.',
        answers: {read: 'El gasto del Fondo Consolidado fue de 297.717,24 crore: 199.611,44 de gasto corriente, 65.428,32 de capital y 32.677,48 de préstamos.',
                  hybrid_rrf: 'El gasto del Fondo Consolidado fue de 4.647,19 crore: 1.296,32 de gasto corriente, 3.108,05 de capital y 242,82 de préstamos.'},
      },
      scope: {
        name: 'El estado equivocado', question: 'Según este volumen, ¿cuál fue el superávit corriente de Maharashtra en 2024–25?',
        choices: ['33.477,03 crore', '18.942,94 crore', 'El volumen no lo indica'], answer: 2,
        focus: [3, 953, 1073],
        finding: 'La tabla es de Gujarat. READ atribuyó el dato de Gujarat de 2023–24 a Maharashtra en 2024–25. El híbrido comprobó el ámbito del documento y se abstuvo.',
        answers: {read: 'El superávit corriente de Maharashtra en 2024–25 fue de 33.477,03 crore.',
                  hybrid_rrf: 'Me abstengo. La evidencia procede de las cuentas de Gujarat y no respalda una cifra para el superávit de Maharashtra en 2024–25.'},
      },
    },
  },
};

const cases = window.DEBUGGER_CASES;
const systemName = {read: 'READ', bm25: 'BM25', hybrid_rrf: 'BM25 + BGE'};
const states = new Map();
const caseNav = document.getElementById('case-nav');
const panel = document.getElementById('case-panel');
let language = new URLSearchParams(location.search).get('lang') === 'es' ? 'es' : 'en';
let active = cases.find(item => `#${item.id}` === location.hash) || cases[0];

function node(name, className, text) {
  const el = document.createElement(name);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function format(value, digits) {
  return new Intl.NumberFormat(language, {maximumFractionDigits: digits}).format(value);
}

function details(label) {
  const container = node('details');
  container.append(node('summary', '', label));
  return container;
}

function lines(rows, focus = []) {
  const list = node('ul', 'source-lines mono');
  for (const row of rows) {
    const line = node('li', focus.includes(row.line) ? 'source-line emphasis' : 'source-line');
    const text = row.text.replace(/^#+ /, '').replaceAll('**', '').replace(/_([^_]+)_/g, '$1');
    line.append(node('span', 'line-number', row.line), node('span', '', text || '\u00a0'));
    list.append(line);
  }
  return list;
}

function traceFor(output) {
  const t = copy[language];
  const trace = details(`${t.trace} · ${output.steps.length} ${t.steps}`);
  const list = node('ol', 'steps');
  for (const step of output.steps) {
    const query = step.args.query;
    const range = step.args.start ? `${step.args.start}–${step.args.end}` : '';
    const label = [step.tool === 'rag' ? systemName[output.system] : step.tool, query || range].filter(Boolean);
    const fold = details(label.join(' · '));
    const stats = [`${step.returned} ${t.returned}`, `${format(step.seconds, 3)} s`];
    if (step.total_matches !== null) stats.unshift(`${step.total_matches} ${t.matches}`);
    fold.append(node('p', 'step-description', stats.join(' · ')));
    if (step.truncated) fold.append(node('p', 'step-description', t.clipped));
    const args = details(t.arguments);
    args.append(node('pre', 'step-args mono', JSON.stringify(step.args, null, 2)));
    fold.append(args);
    if (step.documents.length) {
      fold.append(node('p', 'step-description', `${t.documents} · ${step.documents.map(doc => doc.doc).join(', ')}`));
    }
    if (step.preview.length) {
      fold.append(node('p', 'step-description', t.excerpt), lines(step.preview));
    }
    const row = node('li');
    row.append(fold);
    list.append(row);
  }
  trace.append(list);
  return trace;
}

function answerCard(output, item) {
  const t = copy[language];
  const card = node('article', 'card answer-card');
  const header = node('div', 'answer-header');
  header.append(node('h3', '', systemName[output.system]),
                node('span', `verdict ${output.correct ? 'good' : 'bad'}`, output.correct ? t.correct : t.incorrect));
  const answer = node('p', 'answer-text', item.answers?.[output.system] || output.answer);
  const meta = node('div', 'answer-meta mono');
  meta.append(node('span', '', `${format(output.seconds, 2)} s`),
              node('span', '', `${format(output.usd, 5)} USD`));
  const spans = output.citations.map(({start, end}) => start === end ? `${start}` : `${start}–${end}`);
  card.append(header, answer, meta, node('p', 'answer-cites', `${t.citations} · ${spans.join(', ')}`));
  if (item.answers) {
    const original = details(t.original);
    const quote = node('p', 'answer-text', output.answer);
    quote.lang = 'en';
    original.append(quote);
    card.append(original);
  }
  card.append(traceFor(output));
  return card;
}

function updateUrl() {
  const url = new URL(location.href);
  if (language === 'es') url.searchParams.set('lang', 'es');
  else url.searchParams.delete('lang');
  url.hash = active.id;
  history.replaceState(null, '', url);
}

function render(focus = '') {
  const t = copy[language];
  const item = t.cases[active.id];
  const state = states.get(active.id) || {selection: null, revealed: false};
  document.documentElement.lang = language;
  document.title = `${t.title} · READ vs RAG`;
  for (const [id, text] of Object.entries({title: t.title, intro: t.intro, 'replay-note': t.note,
                                           'report-link': t.report, 'repo-link': t.repo})) {
    document.getElementById(id).textContent = text;
  }
  document.getElementById('languages').setAttribute('aria-label', t.languages);
  for (const button of document.querySelectorAll('[data-language]')) {
    button.setAttribute('aria-pressed', String(button.dataset.language === language));
  }
  caseNav.setAttribute('aria-label', t.navigation);
  caseNav.replaceChildren(...cases.map(candidate => {
    const button = node('button', '', t.cases[candidate.id].name);
    button.type = 'button';
    button.dataset.case = candidate.id;
    if (candidate.id === active.id) button.setAttribute('aria-current', 'true');
    button.addEventListener('click', () => {
      active = candidate;
      updateUrl();
      render('case');
    });
    return button;
  }));

  const grid = node('div', 'case-grid');
  const questionCard = node('section', 'card question-card');
  const title = node('h2', '', item.question);
  title.id = 'question';
  const form = node('form');
  const options = node('fieldset');
  options.disabled = state.revealed;
  const legend = node('legend', 'sr-only', t.choose);
  options.append(legend);
  const reveal = node('button', 'primary', t.reveal);
  reveal.type = 'submit';
  reveal.disabled = state.selection === null;
  for (const [index, text] of item.choices.entries()) {
    const label = node('label', 'choice');
    const radio = node('input');
    radio.type = 'radio';
    radio.name = 'answer';
    radio.value = String(index);
    radio.checked = index === state.selection;
    if (state.revealed && index === item.answer) label.classList.add('is-correct');
    if (state.revealed && index === state.selection && index !== item.answer) label.classList.add('is-wrong');
    radio.addEventListener('change', () => {
      state.selection = index;
      states.set(active.id, state);
      reveal.disabled = false;
    });
    label.append(radio, node('span', '', text));
    options.append(label);
  }
  const actions = node('div', 'actions');
  if (state.revealed) {
    const retry = node('button', 'secondary', t.retry);
    retry.type = 'button';
    retry.addEventListener('click', () => {
      states.delete(active.id);
      render('choice');
    });
    actions.append(retry);
  } else {
    actions.append(reveal);
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (state.selection === null || state.revealed) return;
    state.revealed = true;
    states.set(active.id, state);
    render('result');
  });
  form.append(options, actions);
  questionCard.append(node('span', 'kicker mono', active.question_id), title, form);
  const evidence = node('section', 'card evidence-card');
  const excerpt = lines(active.evidence, state.revealed ? item.focus : []);
  excerpt.lang = 'en';
  const link = node('a', '', t.source);
  link.href = sourceUrl;
  evidence.append(node('h3', '', t.evidence), node('p', '', t.coordinates), excerpt, link);
  grid.append(questionCard, evidence);
  panel.replaceChildren(grid);

  if (state.revealed) {
    const result = node('section', 'results');
    const heading = node('h2', '', t.results);
    heading.id = 'result-heading';
    heading.tabIndex = -1;
    result.setAttribute('aria-labelledby', heading.id);
    const correct = state.selection === item.answer;
    const feedback = node('p', `feedback ${correct ? 'good' : 'bad'}`,
                          correct ? t.right : `${t.wrong} · ${item.choices[item.answer]}.`);
    const answers = node('div', 'answer-grid');
    answers.append(...active.outputs.map(output => answerCard(output, item)));
    const finding = node('aside', 'card finding');
    finding.append(node('strong', '', t.finding), node('p', '', item.finding));
    result.append(heading, feedback, answers, finding);
    panel.append(result);
    if (focus === 'result') heading.focus();
  }
  if (focus === 'case') caseNav.querySelector('[aria-current="true"]').focus();
  if (focus === 'choice') panel.querySelector('input').focus();
}

for (const button of document.querySelectorAll('[data-language]')) {
  button.addEventListener('click', () => {
    language = button.dataset.language;
    updateUrl();
    render();
  });
}
window.addEventListener('hashchange', () => {
  active = cases.find(item => `#${item.id}` === location.hash) || cases[0];
  render();
});
render();
