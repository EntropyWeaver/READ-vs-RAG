# Resultados de Haryana y Tripura

Se ejecutaron las **72 celdas planificadas**, 24 preguntas por sistema, con GPT-5.4 mini
(`gpt-5.4-mini-2026-03-17`) y cuatro workers por documento. Haryana y Tripura se
evaluaron por separado. Cada celda recibió un intento y el presupuesto operativo
forma parte de la evaluación.

| Sistema | Aciertos | Abstenciones correctas | Abstenciones erróneas | Fallos operativos | USD/pregunta | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Híbrido BM25 + BGE | 19/24 | 4/4 | 1/20 | 0 | 0,00553 | 11,2 s | 17,3 s |
| READ | 15/24 | 3/4 | 0/20 | 0 | 0,00651 | 45,8 s | 72,5 s |
| Selector | 19/24 | 4/4 | 0/20 | 1 | 0,01013 | 22,3 s | 80,4 s |

El selector costó **1,83 veces** lo que costó el híbrido por pregunta y su p95 fue
**4,64 veces** mayor. Los dos acertaron 15 de las 19 preguntas en las que entregaron
una respuesta numérica. El híbrido se abstuvo en una pregunta respondible y el
selector registró un fallo operativo en otra.

| Documento | Híbrido | READ | Selector |
|---|---:|---:|---:|
| Haryana | 11/12 | 5/12 | 10/12 |
| Tripura | 8/12 | 10/12 | 9/12 |

Cada sistema acertó uno de los dos desgloses. El híbrido y el selector acertaron
14 de las 16 consultas directas, frente a 11 de READ. Las dos preguntas de cálculo
fallaron con los tres sistemas bajo el criterio de corrección registrado.

Frente al híbrido independiente, el selector ganó una pregunta y perdió otra.
La diferencia fue de 0 puntos porcentuales, con un intervalo bootstrap pareado
del 95 % de −12,5 a +12,5 puntos. Frente a READ, ganó cinco y perdió una,
una diferencia de +16,7 puntos (IC del 95 % de 0 a +37,5, McNemar exacto con
Holm, p = 0,4375). Los intervalos remuestrean preguntas de estos dos informes.
Varias preguntas comparten tablas, y el estudio tiene una sola ejecución por sistema
y pregunta. El p95 de 24 observaciones es descriptivo.

## Qué hizo el selector

- Entregó la primera propuesta del híbrido en 16 preguntas, una propuesta de READ en
  tres y una abstención en cuatro. La celda restante terminó en un fallo operativo.
- Abrió READ en ocho preguntas. Dentro de la misma ejecución del selector,
  dos propuestas iniciales incorrectas acabaron en respuestas correctas y una
  propuesta inicial correcta se perdió. El híbrido independiente genera su propia
  propuesta y se compara por pregunta.
- Solicitó 20 revisiones y consiguió 18 veredictos. El revisor aprobó 13
  propuestas correctas y cuatro incorrectas según las respuestas de referencia.
  Rechazó una propuesta incorrecta. Dos paquetes excedieron el límite de entrada
  durante el recuento de tokens.
- La revisión aportó 0,05324 USD en conjunto. Las llamadas de generación
  registradas fueron 24 para el híbrido, 105 para READ y 80 para el selector.
  Estas cifras cuentan las generaciones y separan el recuento previo de tokens.

## Qué pasó al volver a leer

- **Haryana, ingresos de 2023–24.** La primera propuesta del selector tomó 101.274,31 crore de las notas de conciliación. El control de subtotal activó READ, que encontró los 101.314,84 crore del Estado 3. El híbrido independiente también acertó esta pregunta. [`haryana-total-prior`](selector_decisions.json)
- **Tripura, desglose del Fondo Consolidado.** El híbrido no encontró el desglose y se abstuvo. READ localizó la fila del Estado 4A y el selector entregó los 24.761,18 crore con los tres componentes correctos. [`tripura-consolidated`](selector_decisions.json)
- **Haryana, desglose del Fondo Consolidado.** Las dos etapas del selector produjeron el resultado correcto. El paquete de revisión superó el límite de 6.000 tokens incluso tras acudir a READ, y la celda terminó con un fallo operativo. [`haryana-consolidated`](selector_decisions.json)

## Qué dejó pasar el revisor

- **Déficit confundido con ingresos en Haryana.** El revisor aprobó 7.539,02 crore como aumento de ingresos. El cálculo resta 11.880,86 de 19.419,88, los dos déficits que se ven en el PDF. El aumento de ingresos del Estado 3 es 5.114,62 crore. La conversión a Markdown junta varias filas de ambos lados de la tabla. [`haryana-receipts-change`](selector_decisions.json)
- **Estado contable equivocado en Tripura.** La propuesta usó 21.103,62 crore del Estado 2. La pregunta pedía los 21.103,59 crore del Estado 3. El revisor atribuyó la cifra al estado contable incorrecto y la aprobó. [`tripura-total-current`](selector_decisions.json)
- **Aritmética con otro estado contable en Tripura.** Los tres sistemas usaron
  las dos cifras del Estado 2 y llegaron a 565,60 crore. El Estado 3 da 565,59.
  El revisor aprobó 565,60 y atribuyó sus operandos al Estado 3.
  [`tripura-receipts-change`](selector_decisions.json)
- **Otra definición de intereses en Tripura.** La propuesta tomó 737,73 crore
  de las deducciones de la tabla de intereses sobre préstamos y saldos de caja.
  El Estado 3 daba 759,43 crore de ingresos por intereses. El revisor comprobó
  que los 737,73 estaban en la línea citada y aceptó la cifra.
  [`tripura-interest-current`](selector_decisions.json)

**Texto y valor estructurado en Haryana.** Una respuesta de READ mostraba
1.638,37 crore en prosa y registró `1.63837` en el campo numérico. La calificación
usa el valor estructurado, por lo que el caso cuenta como incorrecto.
[`haryana-other-transfers`](per_question.csv)

## Comprobaciones exploratorias

**Contexto más corto para el revisor.** La última revisión del desglose de Haryana
recibió un recuento de 7.378 tokens para un límite de 6.000. Repetimos únicamente
la revisión de la primera propuesta, con el mismo modelo, la misma pregunta y
las mismas citas. Acotamos el contexto adicional a las 12 líneas cortas más
cercanas antes de cada cita. El verificador aceptó el desglose con 1.384 tokens
de entrada y 0,001704 USD. Esta intervención mide la recuperación de un solo
caso y queda fuera de la tabla principal. [Resultado de la repetición](review_context_diagnostic.json)

**Sensibilidad al redondeo.** Al repetir la calificación con tolerancias absolutas
de 0,01 y 0,05 crore, el híbrido y el selector pasaron a 20 y 21 aciertos, y READ a
16 y 17. Todos ganaron las mismas preguntas de Tripura. El criterio principal de
medio centésimo mantiene el requisito de usar la cifra del estado contable pedido.

**Abstenciones iniciales.** En cinco preguntas, el híbrido del selector se abstuvo.
Continuar con READ corrigió una de ellas, el desglose de Tripura. Las llamadas
posteriores de esas cinco preguntas, incluidas las revisiones de READ, costaron
0,04345 USD.

## Uso y alcance

Las dos ejecuciones sumaron **0,532227 USD** a las tarifas configuradas y cerraron
sin reservas pendientes. La repetición del verificador añadió **0,001704 USD**.
Las latencias incluyen las llamadas de recuento, recuperación y revisión de
cada celda. Los índices se construyeron antes de medir las celdas. BGE truncó
59 de los 155 chunks de Haryana y 69 de 146 en Tripura para calcular sus
embeddings. Esas cifras caracterizan el baseline compartido por el híbrido y
el selector.

Con estos resultados, el híbrido es la opción con el menor coste y menor latencia
para 19 aciertos. Los casos rescatados permiten concretar dónde aportó
READ y los errores muestran dos límites distintos del verificador. El formato
de la prueba y las cotas de inferencia corresponden a dos informes financieros con
estructura parecida.

[Métricas completas](metrics.json) · [Respuestas por pregunta](per_question.csv) ·
[Decisiones y veredictos](selector_decisions.json) · [Preparación y reproducción](../README.md)
