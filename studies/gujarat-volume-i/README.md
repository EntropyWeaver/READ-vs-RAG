# READ vs RAG con un informe financiero real

La prueba usa las 94 páginas del Volumen I de las cuentas de Gujarat 2024–25.
`prepare.py` convierte el PDF oficial con versiones fijadas y comprueba el hash
del PDF y del Markdown. El PDF y la conversión se descargan y preparan en local.
Las coordenadas de evidencia se revisaron en esta conversión. El conjunto incluye
32 preguntas adaptadas del benchmark de TwoSpoon y cuatro nuevas sobre el mismo
informe. Únicamente tres preguntas piden abstenerse. La muestra concentra varias
preguntas en las mismas tablas y los intervalos por pregunta no recogen variación
entre documentos. El alcance corresponde a esta conversión del Volumen I.

Todas las variantes usan el mismo snapshot de GPT-5.4 mini con razonamiento bajo,
el mismo formato de salida y los mismos límites por pregunta. Cada pregunta se
ejecuta una vez por sistema. El orden de inicio se mezcla por ejecución y las
configuraciones permiten hasta ocho celdas simultáneas. Las latencias incluyen el
conteo de tokens previo y reflejan concurrencia y red compartida. Los tiempos de
indexación se registran aparte.

| Sistema | Acceso a la evidencia |
|---|---|
| READ | Búsqueda normalizada, navegación por encabezados y lectura de rangos |
| BM25 | Una búsqueda léxica, chunks contextuales de 1.500 caracteres, k=12 |
| BGE | Una búsqueda densa, mismos chunks y k=12 |
| BGE corto | Chunk de 850 caracteres y k=16 para medir sensibilidad al truncado del encoder |
| Híbrido | Fusión RRF de BM25 y BGE, chunks de 1.500 caracteres y k=12 |
| BM25 iterativo | BM25 como herramienta en el mismo bucle que usa READ |

El score principal compara valores finales con unidades, con tolerancia absoluta
de medio centésimo en la unidad esperada, o la decisión de abstenerse. Un valor
correcto puede coexistir con una explicación equivocada. La cobertura cuenta las
líneas de referencia anotadas y solo una de las posibles localizaciones de cada
hecho. La validez de una cita verifica sus coordenadas y el acceso a sus líneas.
Los contrastes pareados usan McNemar exacto y corrección de Holm, y los intervalos
de diferencia usan bootstrap por pregunta.

## Reproducir

Desde la raíz del repo con Python 3.12 y el entorno activado, instalar
`.[dense]` y las versiones del conversor. Para reproducir el entorno de embeddings
exacto, consultar las versiones capturadas en `metrics.json`.

```bash
python -m pip install -e ".[dense]" "pymupdf==1.28.2" "pymupdf4llm==0.2.2"
python studies/gujarat-volume-i/prepare.py
python -m read_vs_rag plan --config studies/gujarat-volume-i/read-bm25.json --split test
python -m read_vs_rag run --config studies/gujarat-volume-i/read-bm25.json --split test --output runs/gujarat-read-bm25
python -m read_vs_rag run --config studies/gujarat-volume-i/dense.json --split test --output runs/gujarat-dense
python -m read_vs_rag run --config studies/gujarat-volume-i/dense-short.json --split test --output runs/gujarat-dense-short
python -m read_vs_rag run --config studies/gujarat-volume-i/controls.json --split test --output runs/gujarat-controls
python studies/gujarat-volume-i/summarize.py runs/gujarat-read-bm25 runs/gujarat-dense runs/gujarat-dense-short runs/gujarat-controls --output runs/gujarat-analysis
```

Las llamadas necesitan `OPENAI_API_KEY`. La ejecución se puede reanudar con la
misma ruta y los mismos ajustes. Un fallo registrado se puede volver a intentar
con `--retry-errors`; las reservas pendientes se conservan en el libro de gasto.
