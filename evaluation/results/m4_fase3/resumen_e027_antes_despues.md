# E-027: tasas antes y después de la respuesta tipada (Gemini gemini-3.5-flash-lite)

Corridas hechas por la usuaria en su computadora el 2026-11-18 (plan gratuito, 0 respaldos sin Gemini en ambas).
- **Antes:** commit `6335600` (pipeline de la Fase 3, sin tipos ni historial), solo `conversational_set`.
- **Después:** rama `fase-3b-clasificacion` (`aebfa8c`), los tres sets. El `.env` local tenía `LLM_CONTEXT_ENTRIES=3`,
  así que la corrida usó 3 entradas de contexto (el nuevo valor por defecto es 5).

## Escalamiento (tickets al operador)

| Set | Antes | Después |
|---|---|---|
| conversational_set (40) | **42.5 %** | **22.5 %** |
| test_set (120) | 17.5 % (corrida de la Fase 3) | 11.7 % |
| validation_set (40) | 17.5 % (corrida de la Fase 3) | 5.0 % |

## Tasas por tipo de respuesta

| Set | Respondidas | Pidió aclarar | Fuera de tema | Escaladas | Tipo correcto |
|---|---|---|---|---|---|
| conversational_set, antes | 35.0 % | 0.0 % | 22.5 % | 42.5 % | 45.0 % |
| conversational_set, después | 45.0 % | 27.5 % | 5.0 % | 22.5 % | 82.5 % |
| test_set, después | 69.2 % | 4.2 % | 15.0 % | 11.7 % | n/d |
| validation_set, después | 60.0 % | 0.0 % | 35.0 % | 5.0 % | n/d |

"Pidió aclarar" no cuenta como respuesta resuelta.

## Métricas de clasificación (responde = clase positiva)

| Set | Accuracy | Precision | Recall | F1 | Matriz |
|---|---|---|---|---|---|
| conversational_set, antes | 72.5 % | 100.0 % | 56.0 % | 71.8 % | TP 14, FP 0, FN 11, TN 15 |
| conversational_set, después | 82.5 % | 100.0 % | 72.0 % | 83.7 % | TP 18, FP 0, FN 7, TN 15 |
| test_set, Fase 3 | 95.0 % | 100.0 % | 93.1 % | 96.4 % | TP 81, FP 0, FN 6, TN 33 |
| test_set, después | 95.0 % | 97.6 % | 95.3 % | 96.4 % | TP 81, FP 2, FN 4, TN 33 |
| validation_set, Fase 3 | 90.0 % | 100.0 % | 84.6 % | 91.7 % | TP 22, FP 0, FN 4, TN 14 |
| validation_set, después | 95.0 % | 100.0 % | 92.3 % | 96.0 % | TP 24, FP 0, FN 2, TN 14 |

Latencia promedio de Gemini en la corrida "después": 0.9 a 1.1 s (p95 de 1.4 a 1.7 s).

## Observaciones
- El escalamiento del set conversacional baja a casi la mitad, y el tipo correcto sube de 45 % a 82.5 %.
- En `test_set` aparecen 2 falsos positivos (antes 0): precisión 97.6 %. El F1 se mantiene en 96.4 %.
- Las preguntas incompletas ya no se escalan: se pide aclararlas (27.5 % del set conversacional).
