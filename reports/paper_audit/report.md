# READ vs RAG — auditoría de los resultados publicados

**Reanálisis de ejecuciones de terceros. No son nuevas llamadas a modelos nuestras.**

Fuente: [https://github.com/twospoon/READ](https://github.com/twospoon/READ), commit `c3c368d4a78b0a152f0dfe7f9f74110347f02397`.

Se validaron 663 registros: 357 principales y 306 del barrido. Los 51 IDs de preguntas coinciden en todas las condiciones. Un documento, un modelo (Gemini 2.5 Pro), una repetición. Se conservan las etiquetas originales.

## Resultados principales

| Sistema | Aciertos | Accuracy · IC 95% Wilson | Coste registrado/pregunta | Latencia p50 / p95 |
|---|---:|---:|---:|---:|
| read_naive_grep | 34/51 | 66.7% [53.0%, 78.0%] | $0.0431 | 19.6s / 51.5s |
| read_no_outline | 34/51 | 66.7% [53.0%, 78.0%] | $0.0397 | 19.3s / 55.1s |
| read | 30/51 | 58.8% [45.2%, 71.2%] | $0.0580 | 23.2s / 58.5s |
| bm25 | 26/51 | 51.0% [37.7%, 64.1%] | $0.0202 | 10.5s / 16.9s |
| hybrid | 15/51 | 29.4% [18.7%, 43.0%] | $0.0224 | 16.4s / 24.5s |
| agentic_rag | 14/51 | 27.5% [17.1%, 40.9%] | $0.0505 | 19.8s / 47.7s |
| dense | 8/51 | 15.7% [8.2%, 28.0%] | $0.0228 | 10.7s / 23.5s |

El coste y la latencia son los registrados por los autores para generación; no miden nuestra máquina y no son una factura completa de evaluación, conversión e indexación. Los tokens del juez se muestran por separado en `audit.json`.

## Comparaciones pareadas

Δ = READ − otro sistema. Bootstrap por pregunta (10.000 remuestreos, semilla fija). McNemar exacto, corrección de Holm sobre seis comparaciones de la familia principal.

| Comparador | Δ puntos · IC bootstrap 95% | Gana READ / pierde | p Holm |
|---|---:|---:|---:|
| agentic_rag | +31.4 [+13.7, +49.0] | 21 / 5 | 0.0124696 |
| bm25 | +7.8 [-9.8, +25.5] | 13 / 9 | 1 |
| dense | +43.1 [+29.4, +56.9] | 23 / 1 | 1.78814e-05 |
| hybrid | +29.4 [+11.8, +47.1] | 20 / 5 | 0.0163093 |
| read_naive_grep | -7.8 [-23.5, +7.8] | 7 / 11 | 1 |
| read_no_outline | -7.8 [-21.6, +5.9] | 5 / 9 | 1 |

**No se demuestra superioridad frente a BM25.** No significación tampoco demuestra equivalencia. El resultado se refiere a este informe financiero, no a todos los RAG.

## Barrido denso publicado

| Variante | Accuracy | Coste registrado/pregunta |
|---|---:|---:|
| dense_c2000_k16 | 35.3% | $0.0294 |
| dense_c4000_k16 | 29.4% | $0.0419 |
| dense_c4000_k8 | 21.6% | $0.0283 |
| dense_c4000_k4 | 19.6% | $0.0215 |
| dense_c2000_k4 | 17.6% | $0.0163 |
| dense_c2000_k8 | 17.6% | $0.0208 |

El mejor ajuste se escogió sobre estas mismas preguntas. No es una estimación sobre un test independiente. `audit.json` incluye otra familia de seis comparaciones para el barrido.

## Auditoría de medición

- En la matriz principal hay 9 respuestas a preguntas sin respuesta que el juez considera correctas y el detector de abstención puntúa como incorrectas. Incluyen «do not contain» y «do not specify». Se conservan ambas señales: no se sustituyen etiquetas sin revisión humana.
- 15 preguntas marcadas verified=true conservan metadatos «awaiting human audit». Esto no prueba que falte la revisión, pero la procedencia requiere aclaración antes de llamarlas verificadas por nosotros.
- Solo hay 5 preguntas sin respuesta: cualquier tasa de alucinación derivada tiene gran incertidumbre. El detector publicado solo evalúa ese subconjunto; no mide todas las afirmaciones falsas.
- La puntuación numérica upstream permite tolerancia relativa del 0,5%, absoluta de 0,01 crore y dos interpretaciones de algunas cifras sin unidad. Puede aceptar errores pequeños y confundir unidades; el nuevo runner exige unidades explícitas y tolerancias por pregunta.
- El judge-only es un análisis de sensibilidad con las etiquetas LLM existentes, no una nueva verdad de referencia. Los intervalos y tests no corrigen sesgos del juez ni del corpus.

## Alcance de las métricas

`per_question.csv` conserva los denominadores y permite revisar cada caso. `slices.csv` desglosa categoría, dificultad y unidad. `review_queue.jsonl` contiene los desacuerdos entre juez y puntuación principal, con respuestas completas.

La cobertura recalculada usa líneas anotadas y líneas expuestas. Es cobertura de esas anotaciones, que pueden ser incompletas; no demuestra fidelidad semántica ni citas correctas. El groundedness publicado es un proxy numérico heredado, no una validación independiente del documento. No hemos reconvertido ni auditado manualmente el PDF.

## Reproducir

```bash
python -m read_vs_rag audit
```

Sin API ni dependencias externas. Primero ejecutar `python -m read_vs_rag fetch-upstream` para descargar los logs una vez; después funciona sin red. Los hashes de entrada se verifican contra `data/upstream/manifest.json`. El bootstrap es determinista.
