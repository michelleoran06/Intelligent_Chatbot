# Reporte de verificación — Fase 1 (Entrega 3)

Fecha de ejecución: 2026-10-21. Todas las salidas citadas están en `evaluation/results/`.

## 1. Entorno y versiones

| Elemento | Valor |
|---|---|
| Sistema operativo | Windows 11 Home Single Language (NT 10.0.26200) |
| Terminal | Windows PowerShell 5.1.26100 |
| CPU / RAM | Intel Core Ultra 7 155H (16 núcleos, 22 hilos) / 15.5 GB |
| Python del entorno virtual | 3.12.0 (`.venv`) — ver nota A |
| fastapi | 0.159.1 |
| pydantic | 2.14.1 |
| sqlalchemy | 2.1.6 |
| chromadb | 1.5.9 |
| streamlit | 1.66.1 |
| rapidfuzz | 3.14.6 |
| uvicorn / onnxruntime | 0.54.0 / 1.31.0 |
| pytest / locust / ruff | 9.1.1 / 2.47.0 / 0.15.22 (tras la corrección C1) |
| git | **No instalado** |
| Docker | **No instalado** |

Evidencia: `entorno_versiones.txt`.

**Nota A.** El Dockerfile y la CI usan Python 3.11, pero en este equipo solo hay 3.9, 3.12 y 3.14. Se usó 3.12, la versión más cercana con soporte para todas las dependencias.

## 2. Resultado por paso

| Paso | Resultado | Evidencia |
|---|---|---|
| 0. SO, rama git, `.env` no rastreado | **No realizable**: git no está instalado y la carpeta no es un repositorio (no hay `.git`). Tampoco existe `.env` en la carpeta. `.gitignore` sí excluye `.env`. | — |
| 1. Entorno virtual y dependencias | Pasó | `entorno_versiones.txt` |
| 2. `ruff check .` | Falló al inicio con 98 avisos; **pasó** tras la corrección C1 | `ruff_salida.txt` |
| 3. Pruebas unitarias y de integración | **Pasó: 50/50** en 7.3 s, sin advertencias | `pytest_salida.txt` (Figura 7) |
| 4. `pytest -m chroma` | **Pasó: 1/1** (`test_real_retrieval_and_reindex`) | `pytest_chroma_salida.txt` |
| 5. Prueba de humo de la API (local) | **Pasó**: los 6 casos devolvieron lo esperado (ver tabla abajo) | `api_smoke.txt`, `uvicorn_local_*.txt` |
| 6. Calibración | Se ejecutó sin errores; métricas en la sección 4 | `calibracion_salida.txt`, `threshold_sweep.csv`, `divisor_sweep.csv`, `baseline_details.csv`, `precision_recall_threshold.png` (Figuras 11 y 12, Tablas 19 a 22) |
| 7. Prueba de memoria | Pasó; métricas en la sección 5 | `memoria_salida.txt` (Figura 8), `memory_profile.png`, `memory_profile.csv`, `session_size.csv`, `memoria_logs.txt` |
| 8. Docker | **Omitido**: Docker no está instalado | — |
| 9. Carga con 50 usuarios (90 s, backend local) | Se ejecutó; **1 fallo de 602 (0.17 %)** y latencia alta durante el calentamiento (sección 6) | `carga_50_salida.txt`, `carga_50_stats.csv`, `carga_50_stats_history.csv`, `carga_50_failures.csv`, `carga_50_exceptions.csv` |
| 10. Este reporte | Hecho | — |
| 11. Commit | **No realizable**: no hay git ni repositorio | — |

### Prueba de humo (paso 5)

| Caso | HTTP | Resultado |
|---|---|---|
| `GET /health` | 200 | `status: ok`, 13 entradas, umbral 0.7 |
| "¿A qué hora abren la cafetería?" | 200 | `answered`, semántico, S = 1.0, 298 ms |
| "¿Cuál es la capital de Francia?" | 200 | `pending_human`, S = **0.692** (ver advertencia W2) |
| Mensaje en blanco | 400 | "Tu mensaje está en blanco. Por favor, escribe una pregunta." |
| 501 caracteres | 422 | "Tu mensaje es muy largo (máximo 500 caracteres)…" |
| Sin `user_id` | 422 | "La petición no es válida: faltan campos obligatorios…", campo `user_id` |

## 3. Correcciones realizadas

### C1. Incompatibilidad de versión de ruff

- **Archivo y línea:** `requirements-dev.txt`, línea 8.
- **Error original:** `ruff check .` reportó 98 avisos (UP006, UP045, UP035, RUF100, BLE001, I001, SIM102, RUF012, S110, …) en `calibrate_confidence.py`, `main.py`, `nlp_engine.py`, `memory_test.py` y otros.
- **Causa:** la dependencia era `ruff>=0.4`, sin límite superior, así que se instaló ruff 0.17.1. El proyecto no tiene archivo de configuración de ruff. A partir de ruff **0.16.0** cambió el conjunto de reglas que aplica por defecto, y esas reglas nuevas generan los avisos. Se comprobó con varias versiones:
  - 0.8.6, 0.12.12, 0.14.14 y 0.15.22: "All checks passed!"
  - 0.16.10: 96 avisos.
  - 0.17.0: 98 avisos.
  - 0.17.1 limitado a las reglas clásicas (`--select E4,E7,E9,F`): "All checks passed!"

  El código no tenía errores; cambió la herramienta. La CI (`ci.yml`) habría fallado por la misma razón.
- **Cambio hecho:** `ruff>=0.4` pasó a `ruff>=0.4,<0.16`. No se modificó ningún archivo `.py`.
- **Alternativa (para que decida el equipo):** agregar un `ruff.toml` con `[lint] select = ["E4","E7","E9","F"]`, que fija las reglas en cualquier versión de ruff.

No hubo correcciones de lógica de negocio ni de valores esperados de pruebas.

## 4. Métricas de validación del modelo (paso 6)

Conjunto de prueba: 120 consultas. Configuración actual: umbral 0.70, divisor 2.5.

**Matriz de confusión (Tabla 19)**

| | Esperado: respondible | Esperado: ESCALATE |
|---|---|---|
| Sistema responde (S ≥ 0.70) | TP = 75 | FP = 22 |
| Sistema escala (S < 0.70) | FN = 4 | TN = 19 |

**Métricas (Tabla 20)**

| Métrica | Valor |
|---|---|
| Exactitud | 0.783 |
| Precisión | 0.773 |
| Recall | 0.949 |
| F1 | 0.852 |
| Tasa de escalamiento | 0.192 |
| Hit rate @1 | 0.897 |
| Hit rate @3 | 0.977 |

**Barrido del umbral, divisor 2.5 (Tabla 21)**

| Umbral | Precisión | Recall | F1 | Escalamiento |
|---|---|---|---|---|
| 0.60 | 0.658 | 0.975 | 0.786 | 0.025 |
| 0.65 | 0.706 | 0.975 | 0.819 | 0.092 |
| **0.70** | **0.773** | **0.949** | **0.852** | **0.192** |
| 0.75 | 0.824 | 0.854 | 0.838 | 0.292 |
| 0.80 | 0.894 | 0.694 | 0.781 | 0.450 |

**Barrido del divisor, umbral 0.70 (Tabla 22)**

| Divisor | d aceptada ≤ | Precisión | Recall | F1 |
|---|---|---|---|---|
| 2.0 | 0.60 | 0.833 | 0.854 | 0.843 |
| **2.5** | **0.75** | **0.773** | **0.949** | **0.852** |
| 3.0 | 0.90 | 0.700 | 0.975 | 0.815 |

Hay 26 casos fallidos: 22 FP y 4 FN. De los FP, 12 son preguntas fuera de alcance que el bot respondió, por ejemplo "¿Cuánto cuesta la colegiatura?" → antojitos o "¿Puedo pagar la inscripción con tarjeta?" → pagos. El detalle está en `calibracion_salida.txt` y `baseline_details.csv`.

El script sugiere usar umbral 0.80 y divisor 2.0 (precisión 0.962, recall 0.575). **No se aplicó**, porque es una decisión fija del equipo. Ver la duda D1.

## 5. Memoria (paso 7)

| Consultas | RSS | Python actual | Pico Python |
|---|---|---|---|
| 0 | 162.7 MB | 0.00 MB | 0.00 MB |
| 50 | 175.0 MB | 0.16 MB | 1.24 MB |
| 100 | 197.8 MB | 0.22 MB | 1.30 MB |
| 500 | 197.7 MB | 0.30 MB | 1.32 MB |

El RSS se estabiliza en unos 198 MB después de 100 consultas, sin crecimiento entre 100 y 500. El historial de la sesión ocupa 1.9 KB con 10 mensajes, 4.5 KB con 25 y 9.2 KB con 50.

## 6. Carga con 50 usuarios (paso 9)

Configuración: `-u 50 -r 10 -t 90s`, backend local (`uvicorn` con 1 proceso, Windows) con un `DATA_DIR` temporal para no llenar `data/` de tickets de prueba.

| Métrica | Valor |
|---|---|
| Peticiones | 602 (490 respondibles, 112 escaladas) |
| Fallos | 1 (0.17 %), `HTTP 0` en una pregunta respondible |
| Throughput promedio | 6.8 peticiones/s |
| Latencia mediana / promedio | 16 ms / 5,224 ms |
| p90 / p95 / p99 / máximo | 19 s / 26 s / 39 s / 54 s |

**Comportamiento en el tiempo** (`carga_50_stats_history.csv`):

| Momento | Throughput | Mediana | p95 |
|---|---|---|---|
| Primeros ~60 s | 0.1–4.7 peticiones/s | 10–19 s | hasta 39 s |
| Últimos ~10 s | ~23 peticiones/s | 31 ms | — |

**Diagnóstico (sin cambios aplicados):**

1. Las respuestas en caché tardan ~0.13 ms en el servidor. Las nuevas requieren calcular el embedding con ONNX en CPU: ~300 ms sin carga.
2. Al arrancar, la caché está vacía. Los 40 hilos del pool de FastAPI calculan embeddings al mismo tiempo, compiten por la CPU, y el tiempo *dentro* del servidor llega a 15.8 s (dato de `response_time_ms` en SQLite: p90 de 5.6 s).
3. El resto de la latencia del cliente (hasta 54 s) es espera en cola antes de que la petición tome un hilo.
4. El conjunto de prueba solo tiene 120 consultas distintas. En cuanto se cachean, el sistema atiende la demanda (~23 de ~25 peticiones/s posibles). Por eso **la prueba mide sobre todo el arranque en frío**, y el estado estable se ve mucho mejor de lo que sería con preguntas variadas.
5. No se pudo determinar la causa del `HTTP 0` (error de conexión del lado del cliente, 22:52:50, a mitad de la prueba). Coincide con la ventana de mayor saturación.

**Recomendación:** no correr el escalón de 500 usuarios en estas condiciones sin decidir antes las dudas D3 y D4. Con 50 usuarios ya hay latencias de decenas de segundos en frío.

## 7. Advertencias y dudas pendientes

- **D0 — git:** no hay git instalado ni repositorio (`.git`). No se pudo crear la rama `correcciones-entrega3`, verificar el rastreo de `.env` en el historial ni hacer commit. Hay que instalar git o trabajar en la copia clonada del repositorio.
- **D0b — `.gitignore` contra el paso 11:** `.gitignore` ignora `evaluation/results/`. Para hacer commit de la evidencia se necesita `git add -f` o cambiar `.gitignore`. Cualquiera de las dos es decisión del equipo.
- **D1 — calidad del modelo:** precisión de 0.773 con 22 FP. El bot responde preguntas fuera de alcance (colegiatura, inscripción, biblioteca) con datos de la cafetería. Cambiar el umbral o el divisor está fuera de mi autorización.
- **W2 — margen del umbral:** "¿Cuál es la capital de Francia?" obtuvo S = 0.692, solo 0.008 por debajo de 0.70. Variaciones mínimas de versión del modelo o de redacción podrían hacer que se responda.
- **D3 — Docker:** no se ejecutó (Figura 16 pendiente). Además, la carga se midió en Windows con Python 3.12 y no en el contenedor Linux con 3.11, así que las cifras pueden diferir.
- **D4 — desempeño con concurrencia:** las causas probables son la saturación de CPU por inferencias ONNX concurrentes (cada sesión usa varios hilos internos) y un solo proceso uvicorn. Opciones posibles, todas cambios de configuración o diseño que requieren aprobación:
  - limitar los hilos de onnxruntime;
  - limitar la concurrencia del cálculo de embeddings;
  - usar varios *workers*;
  - precalentar la caché.
- **Ruido en la captura en PowerShell 5.1:** al redirigir stderr con `*>`, PowerShell envuelve los logs en `NativeCommandError`. Por eso `memory_test.py` y `locust` se ejecutaron con `cmd /c` para separar stdout (figura) de stderr (logs).
