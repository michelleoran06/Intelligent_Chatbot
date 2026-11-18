# Revalidación Fase 3 (solo recuperación)

Umbral 0.75, divisor 2.0, OUT_OF_SCOPE_CONFIDENCE 0.0, contexto top-3.

### validation_set (solo recuperación, N = 40)

| Métrica | M3 | Fase 3 |
|---|---|---|
| Accuracy | 87.5 % | 87.5 % |
| Precision | 95.5 % | 95.5 % |
| Recall | 84.0 % | 84.0 % |
| F1 | 89.4 % | 89.4 % |
| Escaladas al operador | | 17.5 % |
| Avisadas como fuera de tema | | 27.5 % |
| Latencia promedio de Gemini | | n/d |
| Latencia p95 de Gemini | | n/d |

Matriz de confusión: TP = 21, FP = 1, FN = 4, TN = 14. Rutas: {'retrieval': 22, 'human': 7, 'out_of_scope': 11}. S mínima de una pregunta respondible: 0.5867.

### test_set (solo recuperación, N = 120)

| Métrica | M3 | Fase 3 |
|---|---|---|
| Accuracy | n/d | 83.3 % |
| Precision | n/d | 91.1 % |
| Recall | n/d | 84.7 % |
| F1 | n/d | 87.8 % |
| Escaladas al operador | | 19.2 % |
| Avisadas como fuera de tema | | 15.0 % |
| Latencia promedio de Gemini | | n/d |
| Latencia p95 de Gemini | | n/d |

Matriz de confusión: TP = 72, FP = 7, FN = 13, TN = 28. Rutas: {'retrieval': 79, 'human': 23, 'out_of_scope': 18}. S mínima de una pregunta respondible: 0.4499.
