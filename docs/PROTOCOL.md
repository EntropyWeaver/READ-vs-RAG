# Protocolo experimental

## Pregunta y alcance

Evaluar si la navegación léxica y estructural de READ mejora la calidad frente a RAG
por chunks, a qué coste, y en qué documentos. La afirmación del artículo procede de
un informe financiero, 51 preguntas y un backbone. No supone una mejora universal.

Tres evidencias distintas permanecen identificadas:

1. **Reanálisis publicado:** 663 filas de TwoSpoon, pin y hashes; usamos sus respuestas
   y juicios existentes. No hemos vuelto a ejecutar ni auditado manualmente esos juicios.
2. **Pruebas de implementación:** fixtures y transportes simulados. Validan código y
   contratos; no se reportan como experimentos de calidad con un LLM real.
3. **Nuevas ejecuciones:** requieren modelo, corpus y preguntas reales, y se guardan
   en `runs/`. En la entrega inicial no existen filas de este tipo.

## Hipótesis antes del test

- H1: READ mejora la exactitud cuando evidencia, unidades y años quedan separados.
- H2: la diferencia se reduce frente a BM25 y recuperación híbrida reforzada.
- H3: el beneficio depende del tipo de pregunta y compensa solo parte del coste adicional.
- H4: la conversión PDF→Markdown puede imponer un techo común a todos los métodos.

Primaria: diferencia pareada de corrección en test entre READ y el mejor baseline
elegido **solo en dev**. El campo numérico es una señal determinista, no corrección
semántica de toda la respuesta. En respuestas narrativas, utilizar un adjudicador
humano o el juez LLM y reportar su señal separadamente. Nunca sustituir silenciosamente
un criterio por otro porque mejore el resultado de un sistema.

## Corpus y muestreo

Empezar por tres familias: informes/tablas, manuales técnicos narrativos y documentos
con referencias cruzadas. Añadir español e inglés con un encoder apropiado por idioma:
BGE-base-en del ejemplo es **inglés**, no un baseline multilingüe adecuado.

Diseñar preguntas de lookup, agregación, aritmética, año/columna, navegación,
unidades/signos, varios documentos, falsas premisas y ausencia de información.
Las categorías no tienen que tener el mismo tamaño, pero sus tamaños se publican.
La ausencia de respuesta necesita revisión humana: no equivale a que un retriever falle.

Hacer un piloto pequeño (p. ej. 20 preguntas) para detectar errores y estimar coste.
Preparar dev y test separados, preferentemente por documentos. Una propuesta inicial
de trabajo es 80 dev / 200 test en varios documentos, **no una garantía de potencia**.
Dimensionar el test definitivo según el efecto mínimo útil y la proporción de pares
discordantes del piloto. El fixture dev/test compartido no valida generalización.

No meter preguntas ni respuestas gold en la carpeta del corpus. Congelar extracción,
hashes, anotaciones, prompts, precios y revisión de los modelos antes del test.
Un PDF reconvertido exige revisar coordenadas y hashes. El hash solo detecta cambios:
no certifica que las etiquetas sean correctas.

## Controles

Mismo generador, temperatura, semilla de repetición, instrucciones de respuesta y
límites máximos en todos los sistemas. Orden de celdas aleatorizado con semilla fija.
Registrar la versión que devuelve el proveedor; un alias puede cambiar.

Los límites son comunes; **el consumo real no será idéntico**. READ y RAG agéntico
pueden realizar más llamadas que RAG de una pasada. Comparar tanto el techo de recursos
como el coste/latencia observados. Publicar una curva de calidad por presupuesto en
ejecuciones separadas, no solo una configuración favorable.

Usar `configs/sweep.dev.example.json` para variar chunk size y k en **dev**. Fijar la
selección antes de ejecutar test. La herramienta permite seleccionar `--split test`;
la separación metodológica exige no usarlo para ajustar parámetros. La matriz incluye
normalización, outline, contexto en chunks, RRF, reranking, bucle agéntico y controles.

El índice denso es un encoder real fijado a commit. La instrucción de consulta BGE se
aplica solo a queries. No truncar textos sin saberlo: la implementación rechaza por
defecto chunks demasiado largos para el encoder y entradas que truncarían el reranker.
`allow_embedding_truncation=true` es una decisión explícita, debe reportarse con el
número de chunks afectados. La construcción y descarga del índice no se esconden
dentro de la latencia de una sola pregunta. No se ha implementado caché persistente
de embeddings: una nueva sesión reconstruye el índice y lo registra.

Oracle utiliza gold y es solo diagnóstico. Full context se rechaza si no cabe entero;
no se rotula un prefijo truncado como contexto completo. Herramientas y documentos son
texto no confiable; no hay shell, red, escritura ni eval expuestos al agente.

## Grading y revisión

La salida exige `abstain: bool`, unidades explícitas y rangos de líneas. Cero no debe
aprobar una magnitud pequeña por una tolerancia absoluta enorme. Predicciones numéricas
de más no aprueban por contener casualmente la cifra gold. La tolerancia es por pregunta
y la tolerancia absoluta se interpreta en la unidad de cada valor esperado.

`judge` es un paso opcional después de generar respuestas. No recibe el nombre del
sistema, sus scores ni su gold retrieval; recibe pregunta, respuesta de referencia,
respuesta candidata y evidencia realmente expuesta. Usa inicialmente el mismo modelo
con instrucciones distintas: esto tiene riesgo de sesgo correlacionado. Sus juicios
de corrección y soporte se muestran separados; no sobreescriben el score mecánico.
Revisar manualmente una muestra estratificada, todos los desacuerdos y todos los
casos sin respuesta. No hemos ejecutado esta revisión sobre datos nuevos.

Los fallos operacionales cuentan como fallos, se mantienen en las tablas. Los grados
semánticos ausentes quedan desconocidos y se muestran límites de accuracy que incluyen
pendientes; nunca se elimina una fila para mejorar el porcentaje. Para precisión y
recall de citas, la cobertura de anotaciones incompletas no equivale a soporte semántico.

## Inferencia estadística

- Wilson al 95% para una sola observación binaria por pregunta.
- Bootstrap percentil por pregunta, 10.000 muestras y semilla `20261117` para diferencias.
- McNemar exacto sobre los pares discordantes, corrección de Holm sobre la familia
  declarada. Auditoría: seis comparaciones principales y seis exploratorias del barrido,
  separadas. No combinar familias después de mirar resultados.
- Con varias repeticiones, promediar dentro de cada pregunta y remuestrear preguntas.
  No se aplica McNemar a repeticiones tratadas como observaciones independientes.
- El runner exige todas las repeticiones para los pares; informa preguntas/celdas
  faltantes. El CI repetido se refiere solo a preguntas completas. No significación
  no significa equivalencia ni ausencia de efecto.

Estos intervalos suponen preguntas independientes. Varias preguntas sobre el mismo
documento pueden estar correlacionadas: para generalizar entre documentos se necesita
bootstrap jerárquico/por documento, **todavía no implementado**. Publicar también
resultados por documento/categoría, sin vender los intervalos de este runner como
inferencia a una población de documentos.

## Gasto y reproducibilidad

Un ledger persistente reserva el coste máximo estimado antes de cada petición. Un
timeout ambiguo conserva la reserva. No hay reintentos automáticos de red. Las
reservas de generación y de judge son independientes. Cambiar carpetas inicia un
nuevo presupuesto: un límite por carpeta no es un límite de cuenta del proveedor.

Costes basados en tarifas introducidas por el usuario, uso real reportado y caché
observada; no es una factura. No incluye impuestos ni electricidad/GPU local. Los
ejemplos no crean cachés explícitas con coste de almacenamiento. El preflight de
tokens también tarda y está incluido en la latencia de la llamada del nuevo runner.
Un cambio de tarifa, modelo o versión exige una nueva campaña.

## Reproducción exacta

Para repetir el paper sin mezclar cambios del nuevo harness:

```bash
git clone https://github.com/twospoon/READ.git upstream-read
cd upstream-read
git checkout c3c368d4a78b0a152f0dfe7f9f74110347f02397
python -m venv .venv
# Activar el entorno según sistema operativo
python -m pip install -e ".[eval,convert,dev]"
```

Seguir el README de ese commit: descargar el PDF de CAG, convertir con pymupdf4llm,
verificar líneas con `python scripts/02_annotate_benchmark.py --verify`, construir el
índice y ejecutar `python scripts/03_run_experiment.py --dry-run` antes de las APIs.
La conversión original no viene en el repo y las dependencias no están completamente
fijadas; coincidir en número de líneas no basta para garantizar la misma extracción.
Guardar un lock del entorno real. Revisar también la disponibilidad del modelo.

Fuentes: [paper v2](https://arxiv.org/html/2608.06305v2),
[implementación y datos](https://github.com/twospoon/READ),
[BGE y query instruction](https://huggingface.co/BAAI/bge-base-en-v1.5),
[API Gemini](https://ai.google.dev/api/generate-content),
[tarifas Gemini](https://ai.google.dev/gemini-api/docs/pricing).
