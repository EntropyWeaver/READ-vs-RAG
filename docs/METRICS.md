# Métricas y denominadores

Los registros crudos son la fuente. No hay una puntuación mágica que mezcle calidad,
coste y latencia con pesos ocultos. Las métricas que no aplican quedan `null` y
exponen el número de observaciones que sí las sustentan.

| Señal | Definición / denominador | Límite |
|---|---|---|
| Corrección mecánica | Abstención explícita en preguntas sin respuesta; matching de valores/unidades o aliases exactos en las demás | No valida toda la prosa; desconocida sin señal textual/numérica |
| Accuracy sobre scored | Correctas / filas con un grado disponible | Siempre junto a pendientes y sin grado |
| Límites de accuracy | Correctas / todas las celdas previstas; (correctas + desconocidas) / todas | No son intervalos estadísticos |
| Exactitud numérica | Matching uno a uno de todos los valores finales, sin valores extra | Tolerancia declarada por pregunta |
| Text exact / token F1 | Igualdad normalizada / solapamiento de tokens con referencias | F1 es diagnóstico léxico, no semántica ni faithfulness |
| Corrección del judge | Media de veredictos válidos del juez ciego al sistema | Sesgo LLM; denominador y discrepancias visibles |
| Soporte del judge | Afirmaciones sustentadas por evidencia expuesta según juez | No una certificación humana |
| Line recall | Líneas gold vistas / líneas gold anotadas | Unidades/años deben estar anotados; puede faltar evidencia alternativa |
| All gold seen | Todas las líneas gold vistas | Más estricto para multi-hop; anotación incompleta afecta su significado |
| Hit@k | Al menos un chunk expuesto intersecta gold | Solo RAG de una pasada |
| Chunk recall@k | Chunks recuperados con solapamiento / todos los chunks del índice con solapamiento | Depende del chunker y de encabezados repetidos |
| MRR | 1 / posición del primer chunk relevante (0 si ninguno) | Solo una pasada; no se mezcla el orden de varias queries agénticas |
| nDCG@k | DCG binario por solapamiento, normalizado contra el ideal del índice | Mismo límite; no mide relevancia no anotada |
| Citation validity | Citas cuyos documentos y coordenadas existen / citas emitidas | No implica que respalden una afirmación |
| Citation seen fraction | Citas con todas sus líneas realmente expuestas / citas emitidas | Detecta referencias inventadas a contenido no visto |
| Citation gold overlap precision | Citas que intersectan gold / citas emitidas | Solapamiento, no entailment |
| Citation gold line recall | Líneas gold citadas / líneas gold | Citas extensas pueden inflar esta métrica; revisar tamaños |
| Abstención sobre unanswerable | Abstenciones / respuestas a preguntas sin respuesta | Mostrar n; muy inestable con cinco preguntas |
| Abstención sobre answerable | Abstenciones / preguntas con respuesta | Detecta un sistema que evita fallos absteniéndose siempre |
| Error operacional | Filas fallidas / celdas ejecutadas | Se conserva el tipo de error y se cuenta como fallo |
| Latencia | `perf_counter`, por intento; medias y p50/p95/p99 | Nuevo runner incluye countTokens; audit hereda medición upstream |
| Index build | Tiempo de crear chunks/modelo/embeddings por sesión | Separado de queries; no incluye coste monetario de GPU local |
| Tokens | Uso que devuelve el proveedor, pensamiento y caché separados | Nunca sustituirlo por len(text)/4 |
| Coste | Tokens × tarifas configuradas, juez separado | Estimación; no incluye impuestos/electricidad |
| Reservado o facturado estimado | Ledger de todas las llamadas e intentos, incluidas respuestas perdidas | Puede sobreestimar tras fallos ambiguos |

En RAG, las métricas se calculan sobre los chunks cuyo texto realmente llegó al
modelo después de limitar evidencia. En agentes, cobertura se calcula sobre la
unión de todas las líneas expuestas, deduplicadas. Una línea truncada no se cuenta
como vista. Grep y outline exponen texto y sí cuentan como evidencia, no solo read.

Unidades de la API: `input_tokens` es `promptTokenCount`, `thinking_tokens` es
`thoughtsTokenCount`, `output_tokens` es `candidatesTokenCount`. La adaptación también
registra `tool_use_prompt_tokens` y los incluye en coste si el proveedor los reporta.
Se conserva la respuesta de uso en el ledger para auditar discrepancias.

## Auditoría upstream

`reports/paper_audit/audit.json` conserva el score original, el score del juez,
el exact numérico y groundedness como señales separadas. El groundedness original
es una comprobación mecánica de números, se rotula **numeric_grounded_proxy**.
No se ha reevaluado contra la conversión completa. Las líneas gold y las líneas
expuestas permiten recalcular cobertura, pero no verificar por sí solas la fidelidad.

Los desgloses incluyen categoría, dificultad y unidad de origen, con denominadores.
Los costes/latencias de las tablas principales no incluyen nuevas llamadas ni el
coste global del experimento. Los tokens de judge upstream se exponen por separado.
La familia de comparaciones principales incluye las dos ablaciones READ: no se
escogen solo las comparaciones significativas.

## Estadística del nuevo runner

Las repeticiones mantienen su ID para el emparejamiento. El bootstrap de múltiples
repeticiones remuestrea medias por pregunta solo cuando están todas sus repeticiones.
McNemar se omite en ese caso. La fracción de preguntas completas y los límites con
pendientes son obligatorios para interpretar un run interrumpido. Los tests se
aplican al criterio mecánico, no a una mezcla posterior de judge y numérico.

No se han implementado todavía bootstrap por documento, adjudicación humana dentro
de la CLI ni intervalos específicos para todas las métricas secundarias del nuevo
runner. No presentar p95/p99 de un piloto de tres preguntas como estimaciones estables.
