# Revalidación Fase 3 (Gemini gemini-3.5-flash-lite)

Corrida hecha por la usuaria en su computadora el 2026-11-18 (Windows, Python 3.12, plan gratuito, una key),
con `python evaluate_rag.py` en la rama `fase-3-gemini` después de corregir E-026. Los CSV por pregunta
quedaron en su equipo (`evaluation/results/m4_fase3/*_con_llm.csv`).

Umbral 0.75, divisor 2.0, OUT_OF_SCOPE_CONFIDENCE 0.0, contexto top-3.

### validation_set (Gemini gemini-3.5-flash-lite, N = 40)

| Métrica | M3 | Fase 3 |
|---|---|---|
| Accuracy | 87.5 % | 90.0 % |
| Precision | 95.5 % | 100.0 % |
| Recall | 84.0 % | 84.6 % |
| F1 | 89.4 % | 91.7 % |
| Escaladas al operador | | 17.5 % |
| Avisadas como fuera de tema | | 27.5 % |
| Latencia promedio de Gemini | | 4,591 ms |
| Latencia p95 de Gemini | | 7,376 ms |

Matriz de confusión: TP = 22, FP = 0, FN = 4, TN = 14. Rutas: {'llm': 22, 'human': 7, 'out_of_scope': 11}. Respaldos sin Gemini: 0. S mínima de una pregunta respondible: 0.5867.

### test_set (Gemini gemini-3.5-flash-lite, N = 120)

| Métrica | M3 | Fase 3 |
|---|---|---|
| Accuracy | n/d | 95.0 % |
| Precision | n/d | 100.0 % |
| Recall | n/d | 93.1 % |
| F1 | n/d | 96.4 % |
| Escaladas al operador | | 17.5 % |
| Avisadas como fuera de tema | | 15.0 % |
| Latencia promedio de Gemini | | 6,066 ms |
| Latencia p95 de Gemini | | 8,405 ms |

Matriz de confusión: TP = 81, FP = 0, FN = 6, TN = 33. Rutas: {'llm': 81, 'human': 21, 'out_of_scope': 18}. Respaldos sin Gemini: 0. S mínima de una pregunta respondible: 0.4499.

### Comparación con la misma corrida sin Gemini (`resumen_sin_llm.md`, test_set)

| Métrica | Sin Gemini | Con Gemini |
|---|---|---|
| Accuracy | 83.3 % | 95.0 % |
| Precision | 91.1 % | 100.0 % |
| Recall | 84.7 % | 93.1 % |
| F1 | 87.8 % | 96.4 % |
| Falsos positivos (respuestas equivocadas) | 7 | 0 |
| Escaladas al operador | 19.2 % | 17.5 % |
