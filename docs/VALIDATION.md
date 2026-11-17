# Verificación de la entrega inicial

Fecha: 17-11-2026. Python 3.12, Linux.

## Ejecutado

- Instalación editable del paquete en un venv nuevo.
- Lint con Ruff.
- Tests de primitivas READ, normalización/ablaciones, límites y paginación, rechazo
  de escapes del corpus, conservación de líneas y contexto, BM25.
- Grading de escalas, signos, valores próximos a cero, múltiples resultados,
  abstención tipada, citas inventadas y ausencia de grados semánticos.
- Wilson, McNemar exacto, Holm, bootstrap pareado sin pseudorreplicación.
- Hashes y recálculo de conteos de los 663 registros publicados; reproducción
  del resultado nulo READ vs BM25; retención de desacuerdos de scoring.
- Contratos Gemini **con transporte simulado**: countTokens, reservas antes de gasto,
  costes de razonamiento/caché, drift de modelo, propagación de IDs/firmas de llamadas.
- Integración del runner **con proveedor simulado**: herramientas→respuesta,
  no filtración de gold, reanudación, cambios de fingerprint, pendientes, informes,
  separación de juez ciego y gasto.
- Smoke de recuperación sobre corpus artificial, cero llamadas LLM.
- Generación e inspección visual de figuras desde las mediciones upstream.

El comando completo es `python -m unittest discover -s tests -v`. No requiere claves.
La CI reproduce los checks offline en Linux y Windows; ver el estado real en Actions.

## Pendiente de integración real

- Autenticación y llamadas Gemini contra la API real: no había una clave disponible.
- Descarga/inferencia real de BGE y cross-encoder; no se descargaron pesos en esta entrega.
- Conversión y verificación del documento CAG; no se distribuye con los resultados.
- Corpus propio real, anotación y revisión humana; prueba final separada del ajuste.
- Nuevas respuestas READ/RAG, judge real y conclusiones entre documentos/modelos.

Una prueba con mocks verifica el contrato que esperamos, no garantiza que el servicio
acepte exactamente ese request. La primera ejecución pagada debe ser el piloto corto.
Las cifras de acierto publicadas en README son **reanálisis**, nunca resultados de mocks.
