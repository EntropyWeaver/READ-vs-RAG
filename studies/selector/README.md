# Selector híbrido → READ

[Resultados de las 72 evaluaciones en Haryana y Tripura](holdout/report.md).

## Política

El selector empieza con BM25 + BGE y comprueba que las citas se hayan mostrado al modelo.
Para valores directos, comprueba cifra, etiqueta, periodo y unidad en el pasaje citado y en
los encabezados cercanos. Cuando la regla no puede resolver una cita válida, una llamada
acotada revisa la propuesta y sus fuentes. Una señal explícita de subtotal en una pregunta
por el total abre directamente el segundo intento con READ.

READ recupera su propia evidencia con el mismo presupuesto que su baseline. Su propuesta
pasa por las mismas comprobaciones. El selector se abstiene si termina sin una respuesta
respaldada. Los fallos operativos quedan visibles como errores. La revisión recibe la
pregunta, la respuesta candidata y los extractos de fuente, incluido contexto cercano.
Las respuestas de referencia y los nombres de los sistemas quedan fuera de la revisión.
El veredicto semántico puede equivocarse y su coste y latencia se incluyen en la celda.

## Reproducción retrospectiva en Gujarat

Se reaplicaron las comprobaciones deterministas a 36 pares de respuestas registradas
del [estudio de Gujarat](../gujarat-volume-i/README.md), sin llamadas nuevas. El selector
de solo reglas abrió READ 35 veces. Se abstuvo incorrectamente en 30 de las 33 preguntas
respondibles. Las citas comprimidas por la conversión, las unidades heredadas de otras
páginas y las respuestas derivadas requieren más comprobaciones de las que cubre la regla.

| Sistema | Aciertos | Abstenciones correctas | Abstenciones erróneas | USD/pregunta | p95 |
|---|---:|---:|---:|---:|---:|
| Híbrido | 24/36 | 3/3 | 6/33 | 0,00918 | 26,1 s |
| READ | 27/36 | 1/3 | 0/33 | 0,00723 | 102,7 s |
| Selector de solo reglas | 3/36 | 2/3 | 30/33 | 0,01633 | 118,3 s |

El coste del selector de solo reglas suma el uso real de los pasos que habría tomado.
Su p95 suma latencias grabadas como aproximación secuencial. Las ejecuciones originales
se hicieron por separado y de forma concurrente. Este replay diagnóstico no mide la
variante con revisión semántica. [Métricas](replay-gujarat/metrics.json) ·
[Decisiones por pregunta](replay-gujarat/per_question.csv).

Para recalcularlo con las grabaciones originales del estudio.

```sh
python studies/selector/replay.py data/corpora/gujarat-live runs/gujarat-controls-001 runs/gujarat-read-bm25-002 studies/selector/replay-gujarat
```

## Comparación prospectiva en Haryana y Tripura

Las [24 preguntas anotadas](questions.tsv) usan el Volumen I de las cuentas 2024–25 de
[Haryana](https://cag.gov.in/uploads/state_accounts_report/account-report-Finance-Accounts-Volume-I-2024-25-1-06949342f0c1bd1-60544781.pdf)
y [Tripura](https://cag.gov.in/uploads/state_accounts_report/account-report-Finance-Accounts-Vol-I-2024-25-PRINT-069c11f2a724454-49441218.pdf).
Hay 12 preguntas por documento, incluidas dos sin respuesta, una de cálculo y una
de desglose. Los PDF, las conversiones y las coordenadas están fijados con hashes.
Cada documento se evalúa por separado con los tres sistemas, 72 celdas en total.
Gujarat se usó para desarrollar la política. Las 24 preguntas nuevas constituyen una
muestra pequeña de informes financieros del mismo tipo, con preguntas relacionadas
entre sí. Los intervalos pareados reflejan variación por pregunta dentro de cada informe.

La evaluación registra aciertos con unidades, abstenciones correctas y erróneas,
errores, coste, p50 y p95, además de activaciones de READ y decisiones de revisión.
Para el desglose, el evaluador existente comprueba el conjunto de valores numéricos.
La traza y la respuesta permiten auditar la asignación a cada componente.

Desde la raíz del repositorio con Python 3.12.

```sh
python -m pip install -e ".[dense]" "pymupdf==1.28.2" "pymupdf4llm==0.2.2"
python studies/selector/prepare.py
python -m read_vs_rag plan --config runs/selector-haryana.json --split test
python -m read_vs_rag plan --config runs/selector-tripura.json --split test
```

Las llamadas requieren configurar `OPENAI_API_KEY` en el entorno local. El runner
lleva una reserva de 1,25 USD por documento. Comprueba los resultados pendientes,
el coste y las reservas sin liquidar en los informes de cada ejecución.

```sh
python -m read_vs_rag run --config runs/selector-haryana.json --split test --output runs/selector-haryana-001
python -m read_vs_rag run --config runs/selector-tripura.json --split test --output runs/selector-tripura-001
```

Los resultados y veredictos de revisión quedan en `results.jsonl`. La carpeta
`report/` contiene `summary.json`, el CSV por pregunta y el informe navegable.
La demo pública de GitHub Pages reproduce los casos guardados de Gujarat.

Para agregar ambas ejecuciones y repetir el diagnóstico acotado del verificador.

```sh
python studies/selector/summarize.py runs/selector-haryana-001 runs/selector-tripura-001 --output runs/selector-analysis
python studies/selector/diagnose_review.py runs/selector-haryana-001 runs/selector-tripura-001 --output runs/selector-review-diagnostic/results.json
```

El agregador usa los resultados registrados. El diagnóstico requiere una llamada de modelo.
