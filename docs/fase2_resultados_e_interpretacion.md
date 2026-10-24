# Fase 2 — Resultados e interpretación del experimento de calidad

Fuente: `evaluation/results/experimento_calidad/RESULTADOS_EXPERIMENTO.md` (base de conocimiento v2, conjunto de prueba v2, 120 consultas). Este documento complementa `docs/BITACORA_DE_CAMBIOS.md` y sirve de base para las Secciones 16.3–16.5 y 19 del reporte.

## 1. Resumen

| Config. | Precisión (0.70 / 2.5) | Recall | Mejor ajuste con precisión ≥ 0.90 | RSS | ¿Viable en Render? |
|---|---|---|---|---|---|
| A: modelo actual | 0.755 | 0.949 | 0.75 / 2.0 → P 0.900 · R 0.847 | 160 MB | Sí |
| B: multilingüe | 0.658 | 1.000 | 0.85 / 1.5 → P 0.942 · R 0.756 | 1,321 MB | **No** |
| C: actual + rechazo | 0.779 | 0.949 | **0.75 / 2.0 → P 0.911 · R 0.847 · F1 0.878** | 138 MB | **Sí** |
| D: multilingüe + rechazo | 0.774 | 1.000 | 0.85 / 1.5 → P 0.942 · R 0.756 | 1,309 MB | **No** |

## 2. Interpretación

**1. El problema principal era la calibración, no el modelo.** Con el umbral y el divisor iniciales (0.70 / 2.5), las cuatro configuraciones tienen precisión de 0.66–0.78, muy lejos del objetivo de 0.90.
- Con la calibración que el reporte ya preveía en la Sección 16.4 (umbral 0.75, divisor 2.0), el mismo modelo actual llega a precisión 0.900 con recall 0.847.
- Esto equivale a aceptar solo distancias d ≤ 0.5, es decir, una similitud coseno ≥ 0.75, en lugar de d ≤ 0.75 (coseno ≥ 0.625).
- El divisor 2.5 era un valor analítico inicial; ahora tiene un reemplazo empírico.

**2. El modelo multilingüe no es viable en este despliegue.**
- **Ordena un poco mejor:** Hit@1 de 0.908 contra 0.885.
- **Pero discrimina peor:** comprime todas las similitudes hacia arriba. Por ejemplo, "¿Cuál es la capital de Francia?" obtiene S = 0.813. Por eso necesita un umbral de 0.85 y aun así su recall (0.756) es menor que el de C.
- **Y no cabe en memoria:** usa unos 1.3 GB, porque requiere PyTorch, contra 512 MB del plan de Render.
- **Conclusión para el reporte:** la hipótesis de "Language mismatch" se confirmó, pero la mitigación probada no cumple las restricciones de recursos. Es un *trade-off* documentado (criterio 6).

**3. Los ejemplos de rechazo ayudan poco, pero ayudan.** Con la configuración vigente, C tiene 3 FP menos que A:
- eliminó el falso positivo por palabras clave de "¿A qué hora abre la biblioteca?";
- y dos más: "¿En qué edificio está la dirección de la facultad?" y "La comida me cayó mal...".

Efecto secundario: rechazó la consulta "precios", que era un FN aceptable porque es una pregunta ambigua. Con la calibración elegida, C supera a A en precisión (0.911 contra 0.900) con el mismo recall.

**4. Advertencia sobre la latencia.** A y C usan el mismo modelo, pero A midió 539 ms y C 267 ms por consulta; también la construcción del índice tardó 16.9 s contra 4.6 s.
- La diferencia se debe a que A corrió primero y absorbió el calentamiento (carga del modelo ONNX y caché de disco). No se debe a los ejemplos de rechazo.
- Para el reporte, usar las cifras de C como representativas del modelo actual, o repetir la medición.
- El tiempo del embedding con ONNX (~270 ms por consulta) es el costo principal de cada pregunta nueva. Es la base de la Fase 3 (desempeño).

## 3. Análisis de errores (Tabla 23, con datos reales de la configuración C)

| Categoría | Ejemplos reales | Causa | Mitigación |
|---|---|---|---|
| Fuera de alcance con vocabulario compartido | "¿Cuánto cuesta la colegiatura?" → antojitos; "¿Puedo pagar la inscripción con tarjeta?" → pagos; "Perdí mi cartera en la cafetería" → ubicación | Palabras como "cuesta", "pagar", "tarjeta" o "cafetería" dominan el embedding | Calibración 0.75 / 2.0 y ejemplos de rechazo; no se elimina por completo |
| Productos o servicios que no se venden | "¿Venden cigarros?" → carnitas; "¿Tienen opciones veganas?"; "¿Café de grano?"; "¿Calorías de la pizza?" | El modelo reconoce que el tema es comida, pero no puede saber qué *no* está en el menú | Escalar es lo correcto; queda como limitación de un sistema que solo recupera respuestas |
| La estructura pesa más que el contenido | "¿Qué antojitos tienen?" → desayunos; "¿Tienen molletes o tostadas?" → desayunos | Un modelo orientado al inglés da más peso al patrón "¿Qué X tienen?" que al producto | Modelo multilingüe (no viable aquí) o más preguntas de ejemplo por entrada |
| Preguntas con varios temas | "horario y formas de pago" → pagos | Solo se devuelve una entrada | Responder la más cercana y ofrecer escalamiento |
| Preguntas muy cortas o genéricas | "precios", "comida", "pizza", "¿cuánto cuesta?" | Poca información en la consulta | Escalar o pedir que aclare |
| Errores de escritura | "chilakiles con cesina" (S = 0.560), "kesadillas cuanto" | El embedding pierde la palabra clave mal escrita | Respaldo léxico difuso; efecto limitado |

**Nota de rigor:** no se agregaron a la base de conocimiento las consultas que fallaron. Hacerlo mejoraría las métricas de forma artificial ("estudiar con el examen"). Cualquier ajuste de contenido debe evaluarse con el conjunto de validación independiente.

## 4. Decisión propuesta (pendiente de confirmar con el conjunto de validación)

| Parámetro | Antes | Propuesto |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.70 | **0.75** |
| `CONFIDENCE_DIVISOR` | 2.5 | **2.0** |
| `USE_REJECTION_EXAMPLES` | false | **true** |
| `EMBEDDING_MODEL` | default | default (sin cambio) |
| `KEYWORD_CONFIDENCE` | 0.75 | 0.75 (sigue siendo ≥ umbral; el respaldo léxico sigue activo) |

**Criterio para confirmarla:** en el conjunto de validación independiente, la configuración C (0.75 / 2.0) debe superar a la línea base A (0.70 / 2.5) en precisión sin perder demasiado recall. Si no la supera, se reporta el resultado tal cual y se discute.

**Impacto en el reporte si se adopta:** el valor 0.70 cambia a 0.75 en RF05, la Sección 2.3, las Figuras 1 y 3, las Secciones 4.3, 8, 9 y 16 y la Tabla 33. El divisor 2.5 cambia a 2.0 en las Secciones 8 y 16.4. Así lo anticipaba la propia Sección 16.4: "si los valores seleccionados difieren de los iniciales, se cambian en todos los artefactos a la vez".
