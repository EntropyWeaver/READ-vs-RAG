# Añadir un corpus real

El runner trabaja sobre Markdown UTF-8, con IDs de documento relativos a una carpeta.
La extracción de PDF/OCR es una etapa previa. No redistribuimos el informe de CAG.

```text
data/corpora/my-study/
  finance.md
  policy.md
data/my-study-questions.jsonl
```

No poner gold, preguntas o metadatos de evaluación en `data/corpora/my-study/`: todos
los Markdown de esa carpeta son visibles para el agente. El texto de los documentos
se envía al proveedor elegido durante una ejecución; usar datos que puedas procesar así.

## Fila de pregunta

```json
{
  "id": "report-a-001",
  "question": "What was the closing cash balance in 2025?",
  "category": "lookup",
  "split": "dev",
  "verified": true,
  "unanswerable": false,
  "reference_answer": "125 crore INR, closing balance in 2025.",
  "expected_values": [{"value": 125, "unit": "crore"}],
  "answer_aliases": [],
  "gold_spans": [
    {"doc": "finance.md", "start": 80, "end": 82},
    {"doc": "finance.md", "start": 91, "end": 91}
  ],
  "rel_tol": 0.0001,
  "abs_tol": 0.000001,
  "corpus_hashes": {"finance.md": "SHA256_REAL", "policy.md": "SHA256_REAL"},
  "annotation_origin": "reviewer and date"
}
```

Es un ejemplo de formato, no una pregunta ya verificada. No copiar los hashes ficticios.

| Campo | Regla |
|---|---|
| `id` | Único, estable, texto no vacío |
| `split` | `dev` o `test`; el runner no decide la partición por ti |
| `verified` | Solo `true` entra en el run; significa revisado por el responsable del dataset |
| `unanswerable` | Ausencia de información según corpus, no según lo recuperado |
| `expected_values` | Todos los resultados finales pedidos, con unidad explícita |
| `answer_aliases` | Respuestas textuales exactas equivalentes; para paráfrasis amplias usar judge/revisión |
| `gold_spans` | Rangos 1-based inclusivos: datos, unidades, años, columnas y todos los operandos necesarios |
| `rel_tol` / `abs_tol` | Tolerancia relativa / tolerancia absoluta en la unidad del valor esperado |
| `corpus_hashes` | Hash exacto de todos los Markdown del corpus, no solo del documento gold |

Para calcular hashes y explorar coordenadas sin modelo:

```python
from read_vs_rag.corpus import Corpus, ReadTools
corpus = Corpus("data/corpora/my-study")
print(corpus.hashes)
tools = ReadTools(corpus)
print(tools.call("memory_outline", {}))
print(tools.call("memory_grep", {"query": "cash balance"}))
print(tools.call("memory_read", {"doc": "finance.md", "start": 75, "end": 95}))
```

## Unidades y aritmética

Se aceptan INR (`inr`, `rupee`, `rupees`), `lakh`, `crore`, `thousand_inr`, `eur`,
`usd`, `percent`/`%`, `ratio`, `count`. Un crore son 10 millones de INR y un lakh
100.000 INR. Monedas distintas nunca se convierten entre sí. Si necesitas otras
dimensiones, ampliar el registro de unidades y añadir pruebas.

En una resta, `expected_values` contiene la diferencia; los operandos van en las
referencias y en `gold_spans`. Una cifra derivada no tiene por qué aparecer en el
documento. Los valores sin unidad no aprueban por asumir una escala favorable.
Para una pregunta narrativa sin aliases, el score determinista es `null`; ejecutar
el juez para tener una señal semántica separada o adjudicarla fuera del runner.

Si existen varias localizaciones equivalentes del mismo hecho, elegir apoyos
mínimos y documentar alternativas. El esquema actual trata todos los spans como
requeridos y **no modela conjuntos alternativos OR**: puede subestimar la cobertura
cuando el sistema encuentra otro apoyo igualmente válido. No usar esa cobertura
como verdad semántica absoluta.

## Procedencia y separación

Anotar inicialmente sin ver las respuestas de los sistemas. Revisar con el documento
original, particularmente las unidades/columnas destruidas por OCR. Congelar test.
No marcar como «humano verificado» respuestas que solo ha propuesto un LLM.

Las 16 preguntas en `examples/` son datos artificiales conocidos por construcción.
Su `verified=true` solo permite ejecutar un test de integración; `dataset_kind` y
`annotation_origin` hacen explícita esa diferencia. Ninguna tabla de ese fixture
se debe presentar como validación externa.

El JSONL upstream tiene otro esquema y convenciones de unidad. No cambiar la ruta
del config directamente a `data/upstream/questions.jsonl`: no es una importación
válida. Para una reproducción exacta usar el harness de TwoSpoon. Una adaptación
a nuestro esquema exige revisar coordenadas, tipos de magnitud y valores narrativos.

Duplicar `configs/pilot.json`, cambiar `corpus`, `questions`, `dataset_kind` y sus
límites, y ejecutar `plan`. Las rutas se resuelven contra `project_root`, relativo
al directorio del config. Cambiar una entrada exige un directorio de run nuevo.
