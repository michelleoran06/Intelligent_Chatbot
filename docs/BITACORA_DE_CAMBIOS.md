# Bitácora de cambios — Intelligent Chatbot (Entrega 3)

Registro cronológico de qué se cambió, por qué y con qué evidencia. Sirve para escribir la Sección 14 (correcciones), la Sección 20 (evidencia) y las partes del reporte que cita cada entrada. La guía sección por sección está en `CAMBIOS_PARA_EL_DOCUMENTO.md`.

**Criterios de la rúbrica:** C1 Correcciones · C2 Pruebas · C3 Validación del modelo · C4 CI/CD · C5 Docker · C6 Desempeño · C7 Evidencia y consistencia.

---

## Versión 2.0 — Corrección general del código

**Objetivo:** que el sistema corra sin errores y coincida con el reporte.

| # | Cambio | Motivo | Criterio | Archivos |
|---|---|---|---|---|
| 1 | Se creó el `Dockerfile` | `docker-compose.yml` lo usaba, pero no existía | C5 | `Dockerfile`, `.dockerignore` |
| 2 | El volumen de datos se monta en una carpeta (`/app/data`) | Montarlo sobre la ruta de un archivo hacía que SQLite no pudiera abrir la base | C5 | `docker-compose.yml`, `config.py` |
| 3 | La dirección del backend se lee de `BACKEND_URL` | Estaba escrita en el código; en Docker los contenedores no se encontraban | C5, C7 | `frontend.py`, `dashboard.py` |
| 4 | Se completó `requirements.txt` y se creó `requirements-dev.txt` | Faltaba `fuzzywuzzy` (se cambió por `rapidfuzz`) y las herramientas de prueba | C2 | `requirements*.txt` |
| 5 | Migración automática de columnas en SQLite | Una base de la versión anterior fallaba con "no such column: user_type" | C1 | `database.py` |
| 6 | El filtro anti-spam normaliza el texto y exige 5 consonantes seguidas (antes 4) | Bloqueaba palabras válidas: "sándwich", "instrucciones" | C1 | `input_validation.py` |
| 7 | Se eliminó la banda S < 0.25 → HTTP 400; todo lo que tenga S < 0.70 se escala | Contradecía RF05 y el "umbral único" de la Tabla 33 | C1, C7 | `main.py` |
| 8 | La búsqueda semántica decide primero; las palabras clave son respaldo y exigen 2 coincidencias | Con una sola palabra clave, el bot respondía el menú a "¿venden refacciones para una laptop?" | C3 | `nlp_engine.py` |
| 9 | Los errores del motor de IA ya no quedan guardados en la caché | Un fallo pasajero quedaba "cacheado" para siempre | C1 | `nlp_engine.py` |
| 10 | Nombres alineados con el documento: `resolve()`, `answered`, `pending_human`; se agregó `StrategySelector` | El código y el reporte usaban nombres distintos | C1, C7 | `patterns.py` |
| 11 | El Observer ahora registra eventos de escalamiento reales (`EscalationEvent`) | `OperatorDashboardNotifier.update()` estaba vacío | C1 | `patterns.py` |
| 12 | RF03: CRUD de la base de conocimiento con reindexación en segundo plano | Requisito de prioridad alta que no estaba implementado | C1 | `main.py`, `database.py`, `dashboard.py` |
| 13 | RF08 completo: tasa de escalamiento, tiempo medio y p95, calificaciones | Solo había un conteo por tipo de usuario | C1, C6 | `database.py`, `dashboard.py` |
| 14 | RF09 (👍/👎) y RF10 (botón para pedir un operador) | No estaban implementados | C1 | `frontend.py`, `main.py` |
| 15 | Errores 422 diferenciados ("muy largo" o "falta un campo") y 404/409 al resolver tickets | Siempre decía "muy largo" y resolver un ticket inexistente devolvía "success" | C1 | `main.py` |
| 16 | Pruebas unitarias e integración (UT-01 a UT-10, IT-01 a IT-06) | No existían | C2 | `tests/` |
| 17 | Conjunto de 120 consultas etiquetadas y script de validación | Hacían falta para la Sección 16 | C3 | `evaluation/test_set.csv`, `calibrate_confidence.py` |
| 18 | Perfilado de memoria (RSS y tracemalloc) y prueba de carga con consultas variadas | Antes repetían una sola frase, que siempre salía de la caché | C2, C6 | `memory_test.py`, `locustfile.py` |
| 19 | Pipeline de CI/CD en GitHub Actions con 7 etapas | Hacía falta para la Sección 17 | C4 | `.github/workflows/ci.yml` |
| 20 | Se eliminó la llave de API de `.env` y se agregó `.gitignore` | La llave de Gemini estaba en texto plano y no se usaba | C7 | `.gitignore`, `.env.example` |

**Decisión:** no se reintegró el LLM (Gemini). El código no lo usaba, el reporte ya describe una arquitectura sin LLM, y reintroducirlo reabría el comentario 3 de la Entrega 2.

---

## Fase 1 — Verificación en el equipo del proyecto (21-oct-2026)

Ejecutada por Claude Code en Windows 11 con Python 3.12. Detalle completo: `evaluation/results/REPORTE_VERIFICACION.md`.

| Verificación | Resultado | Evidencia (figura) |
|---|---|---|
| Pruebas unitarias e integración | 50/50 pasaron | `pytest_salida.txt` (Fig. 7) |
| Integración con ChromaDB real | 1/1 | `pytest_chroma_salida.txt` |
| Prueba de humo de la API | 6/6 casos correctos | `api_smoke.txt` |
| Memoria | RSS estable en ~198 MB entre 100 y 500 consultas; cabe en 512 MB | `memoria_salida.txt`, `memory_profile.png` (Fig. 8) |
| Validación del modelo (base v1) | Exactitud 0.783 · Precisión 0.773 · Recall 0.949 · F1 0.852 · Hit@1 0.897 | `calibracion_salida.txt` (Fig. 11, 12) |
| Carga con 50 usuarios (90 s) | 602 peticiones · 0.17 % de error · mediana 16 ms · p95 26 s | `carga_50_*.csv` |

**Hallazgos (para interpretar en el reporte):**

- **H1, calidad (C3).** El orden de los resultados es bueno (Hit@1 = 0.897), pero el sistema no sabe cuándo *no* hay respuesta: 22 FP, 12 de ellos preguntas fuera de alcance. Con el modelo actual, entrenado sobre todo en inglés, las frases en español quedan muy juntas en el espacio vectorial. Por ejemplo, "¿Cuál es la capital de Francia?" obtuvo S = 0.692, apenas debajo del umbral. Esto confirma con datos la hipótesis de "Language mismatch" de la Tabla 23.
- **H1b.** Subir el umbral a 0.80 con divisor 2.0 da precisión 0.962 pero recall 0.575: esconde el problema en vez de resolverlo. Por eso no se aplicó.
- **H2, desempeño (C6).** En frío, muchos hilos calculan embeddings a la vez y se saturan la CPU: la latencia llega a decenas de segundos. Con la caché llena, la mediana baja a 31 ms, pero solo porque el conjunto tiene 120 preguntas distintas.
- **H3, entorno.** Git y Docker no estaban instalados (D0, D3).

**Corrección aplicada en la Fase 1:**

- **C1, ruff.** A partir de la versión 0.16, ruff cambió las reglas que aplica por defecto (98 avisos sin errores reales). Se limitó la versión (`ruff>=0.4,<0.16`) y se agregó `ruff.toml` con las reglas clásicas (E4, E7, E9, F).

---

## Paso A — Preparación del repositorio

| Cambio | Motivo | Criterio |
|---|---|---|
| `ruff.toml` con reglas fijas | Las reglas no deben depender de la versión de ruff | C4 |
| Python 3.12 en el `Dockerfile` y en la CI | Es la versión con la que se verificó todo | C5, C7 |
| `evaluation/results/` deja de ignorarse en git | La evidencia del reporte debe estar en el repositorio | C7 |

**Ejecución (23-oct-2026, Claude Code):**

- Se instaló Git 2.55 con `winget`, porque no estaba instalado (hallazgo H3).
- No existía un clon del repositorio. Se inicializó un repositorio **local** en `intelligent_chatbot_corregido/intelligent_chatbot`, en la rama `correcciones-entrega3`, sin remoto. Por decisión del equipo, se sube a GitHub al final.
- `ruff.toml` **no estaba** en la carpeta del proyecto, aunque la Fase 1 lo registra; se tomó la versión de `fase2`.
- Se reemplazaron `ruff.toml`, `.gitignore`, `Dockerfile` y `ci.yml` con sus versiones de `fase2`. `requirements-dev.txt` era idéntico.
- Se verificó que el commit no incluye `.env`, `data/`, `*.db`, `chroma_data/` ni `.venv/`.

---

## Fase 2 — Base de conocimiento v2 y experimento de calidad

### Base de conocimiento v2 (`KB_SEED_VERSION = "2026-10-cafeteria-v2"`)

**Fuente:** `docs/fuentes/base_de_conocimiento_cafeteria.txt`, el texto actualizado por el equipo. Regla aplicada: cuando el texto y el `.docx` no coinciden, manda el texto.

| Cambio en el contenido | Entradas afectadas |
|---|---|
| Lunes a viernes de 7:00 a 17:00; **sábados solo medio día** | `horarios` |
| Los desayunos y chilaquiles se sirven **hasta las 12:00** | `horarios`, `desayunos`, `chilaquiles` |
| **Nueva entrada: carnitas** (viernes y sábado): taco $15, torta $30, combo $50, por kilo | `carnitas` |
| Los molletes se integran en antojitos | `antojitos` |
| El menú del día para llevar cuesta $100 en total ($20 por recipientes) | `menu_del_dia` |
| **Se quitaron** los productos que el texto nuevo no menciona (ver la lista de confirmación) | `sandwiches`, `paquetes`, `pizzas`, `bebidas`, `desayunos`, `menu_general` |

**Productos que el texto nuevo no menciona y se quitaron** (el equipo debe confirmarlo):
- hamburguesa doble y hamburguesa hawaiana;
- licuados;
- pizzas de pastor, queso y champiñón;
- Paquete 6 (carne asada de cerdo) y Paquete 7 (cecina adobada);
- chilaquiles rojos o verdes de $55 dentro de los desayunos.

**Datos que siguen sin fuente** (conservados de la versión anterior): los métodos de pago y la ubicación.

**Dato ambiguo:** "los sábados solo se abre medio día". El bot lo dice así, sin inventar una hora de cierre. Si saben la hora exacta, conviene agregarla.

### Sincronización por versión

- **Problema:** antes, la base de conocimiento solo se llenaba si estaba vacía, así que una base ya existente (Render o local) nunca recibiría el contenido nuevo.
- **Solución:** la tabla `app_metadata` guarda la versión cargada. Si `KB_SEED_VERSION` cambia, el backend:
  1. actualiza las entradas predeterminadas;
  2. borra las que dejaron de ser predeterminadas;
  3. **no toca** las entradas que creó el Administrador desde el panel.
- **Matiz que el reporte debe mencionar:** si el Administrador editó una entrada predeterminada, esa edición se reemplaza cuando cambia la versión.
- **Archivos:** `database.py` (`sync_default_kb`), `main.py`.
- **Prueba:** `test_kb_seed_version_sync`.

### Conjunto de prueba v2

Se reemplazaron 3 consultas sobre productos que ya no existen por consultas sobre carnitas:

| Antes | Ahora |
|---|---|
| ¿Tienen hamburguesas? | ¿Venden carnitas? |
| ¿Venden licuados? | ¿Los viernes hay tacos de carnitas? |
| hay hamburgesas | tacos de karnitas cuanto |

**Consecuencia:** las métricas de la Fase 1 (base v1) no son directamente comparables con las de la Fase 2. En el reporte, la línea base es la **configuración A** del experimento.

### Experimento de calidad (`experiment_quality.py`)

| Config. | Modelo de embeddings | Ejemplos de rechazo |
|---|---|---|
| A (línea base) | all-MiniLM-L6-v2 (actual) | No |
| B | paraphrase-multilingual-MiniLM-L12-v2 | No |
| C | all-MiniLM-L6-v2 | Sí (40) |
| D | paraphrase-multilingual-MiniLM-L12-v2 | Sí (40) |

- **Modelo multilingüe:** se usa con `normalize_embeddings=True`, para que la distancia siga en el rango 0–4 y la fórmula S = 1 − d / divisor conserve su significado (Sección 8).
- **Ejemplos de rechazo:** 40 preguntas de otros temas (trámites, servicios universitarios, temas generales), indexadas con el id `__fuera_de_alcance__`. Si la consulta queda más cerca de ellas, el sistema escala con `method = "rejected"`. Se redactaron sin copiar consultas del conjunto de prueba.
- **Criterio de elección:** el mayor recall con precisión ≥ 0.90, siempre que la memoria quepa en Render (≤ 450 MB, dejando margen sobre los 512 MB).
- **Rigor:** el umbral y el divisor se buscan sobre el mismo conjunto de 120 consultas, así que esos resultados son optimistas. La decisión final se confirma con un **conjunto de validación independiente** escrito por el equipo (`evaluation/validation_set.csv`).
- **Producción no cambia** hasta decidir: `EMBEDDING_MODEL=default` y `USE_REJECTION_EXAMPLES=false` por defecto.
- **Archivos:** `knowledge_base.py`, `vector_store.py`, `nlp_engine.py`, `config.py`, `calibrate_confidence.py`, `experiment_quality.py`, `requirements-experiment.txt`, `tests/`.
- **Pruebas nuevas:** rechazo explícito, que el rechazo no bloquee preguntas de la cafetería, palabras clave de carnitas y unicidad de los ids.

### Resultados del experimento (23-oct-2026)

Ejecutado por Claude Code en Windows 11 con Python 3.12.0, torch 2.14.1 y sentence-transformers 6.2.0.

**Pruebas previas:** `ruff check .` sin avisos; `pytest tests/test_unit.py tests/test_integration.py -v` → **56/56 pasaron** (`pytest_fase2.txt`).

**Evidencia:**
- `evaluation/results/experimento_calidad/RESULTADOS_EXPERIMENTO.md` (reporte completo, con los casos fallidos)
- `consola.txt`
- `config_A.json` … `config_D.json`
- `grid_completo.csv`

**Con la configuración vigente (umbral 0.70, divisor 2.5), 120 consultas:**

| Config. | Modelo | Rechazo | TP | FP | FN | TN | Exactitud | Precisión | Recall | F1 | Escalamiento | Hit@1 | Hit@3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | default | no | 74 | 24 | 4 | 18 | 0.767 | 0.755 | 0.949 | 0.841 | 0.183 | 0.885 | 0.954 |
| B | paraphrase-multilingual-MiniLM-L12-v2 | no | 79 | 41 | 0 | 0 | 0.658 | 0.658 | 1.000 | 0.794 | 0.000 | 0.908 | 0.943 |
| C | default | sí | 74 | 21 | 4 | 21 | 0.792 | 0.779 | 0.949 | 0.856 | 0.208 | 0.885 | 0.954 |
| D | paraphrase-multilingual-MiniLM-L12-v2 | sí | 79 | 23 | 0 | 18 | 0.808 | 0.774 | 1.000 | 0.873 | 0.150 | 0.908 | 0.943 |

**Mejor combinación con precisión ≥ 0.90** (optimista: se ajustó sobre el mismo conjunto):

| Config. | Umbral | Divisor | Precisión | Recall | F1 | Escalamiento |
|---|---|---|---|---|---|---|
| A | 0.75 | 2.0 | 0.900 | 0.847 | 0.873 | 0.333 |
| B | 0.85 | 1.5 | 0.942 | 0.756 | 0.839 | 0.425 |
| C | 0.75 | 2.0 | 0.911 | 0.847 | 0.878 | 0.342 |
| D | 0.85 | 1.5 | 0.942 | 0.756 | 0.839 | 0.425 |

**Recursos:**

| Config. | Documentos | Construcción del índice (s) | RSS final (MB) | Latencia media (ms) | Latencia p95 (ms) | ¿Cabe en Render? |
|---|---|---|---|---|---|---|
| A | 101 | 16.9 | 160.3 | 538.8 | 1369.5 | sí |
| B | 101 | 87.7 | 1321.0 | 16.0 | 18.7 | no |
| C | 141 | 4.6 | 137.5 | 267.3 | 322.4 | sí |
| D | 141 | 19.1 | 1308.9 | 15.9 | 17.4 | no |

**Recomendación automática del script:** configuración **C** con umbral 0.75 y divisor 2.0. Da precisión 0.911, recall 0.847, F1 0.878 y RSS 137.5 MB. **No se aplicó.**
- Cambia el umbral y el divisor, que son decisiones fijas: requieren aprobación del equipo.
- Hay que confirmarla con `evaluation/validation_set.csv`.

**Observaciones para interpretar en el reporte:**

- **O1, modelo multilingüe y divisor.** Con el divisor 2.5, el modelo multilingüe (B) pone todas las consultas por encima de 0.70 y nunca escala (escalamiento 0.000, TN = 0). Su escala de distancias es distinta, así que el divisor 2.5 no le sirve. Por eso su mejor punto exige umbral 0.85 y divisor 1.5.
- **O2, los ejemplos de rechazo ayudan poco con el modelo actual.** De A a C, los FP bajan de 24 a 21. Con el modelo multilingüe, de B a D, bajan de 41 a 23. Efecto secundario en C: la consulta "precios" (esperado `menu_general`) pasó a `rejected` (FN).
- **O3, memoria.** B y D usan unos 1.3 GB de RSS, porque cargan torch y sentence-transformers. No caben en Render (límite seguro de 450 MB). A y C usan el modelo ONNX de ChromaDB (~140–160 MB).
- **O4, la latencia de A no es comparable.** A corrió primero y su tiempo incluye el arranque en frío del modelo ONNX (construcción del índice 16.9 s contra 4.6 s en C). La diferencia de latencia entre A y C se debe sobre todo al calentamiento, no al rechazo. Las latencias de B y D (~16 ms) se midieron con torch en CPU, después de cargar el modelo.
- **O5, las fallas son de calidad, no de la herramienta.** Las preguntas fuera de alcance que mencionan pagos o precios ("¿Aceptan tarjeta en la papelería?", "¿Cuánto cuesta la colegiatura?") siguen obteniendo S > 0.80 en todas las configuraciones.

**Advertencias de la ejecución (no afectan los resultados):**
- `huggingface_hub` avisó que las peticiones a HF Hub no están autenticadas (sin `HF_TOKEN`).
- Windows no permite symlinks en la caché de Hugging Face, así que la caché ocupa más espacio en disco.
- La ruta del conjunto aparece como `evaluation\test_set.csv` (separador de Windows) en el reporte. Es solo estético.
- **No hubo errores.** Las cuatro configuraciones terminaron con código 0.

---

## Decisión final de la Fase 2 (23-oct-2026)

**Decisión:** se adopta la **configuración C**, aprobada por el equipo con base en la validación independiente.

**Conjunto de validación:** `evaluation/validation_set.csv`, escrito por el equipo. Tiene 40 consultas, 26 de la cafetería y 14 fuera de alcance, y ninguna se repite en `test_set.csv`.
- No se usó para ajustar nada.
- Al archivo original le faltaba la línea de encabezado; en el repositorio solo se le agregó `query,expected,category`.

**Evidencia:**
- `experimento_calidad/validacion_final_consola.txt`
- `validacion_final_A.json`
- `validacion_final_C.json`

| Métrica | A: línea base (0.70 / 2.5, sin rechazo) | C: adoptada (0.75 / 2.0, con rechazo) |
|---|---|---|
| TP / FP / FN / TN | 22 / 4 / 2 / 12 | 21 / 1 / 4 / 14 |
| Exactitud | 0.850 | 0.875 |
| Precisión | 0.846 | **0.955** |
| Recall | 0.917 | 0.840 |
| F1 | 0.880 | 0.894 |
| Escalamiento | 0.350 | 0.450 |
| Hit@1 / Hit@3 | 0.885 / 0.962 | 0.885 / 0.962 |

**Lectura:** C supera el objetivo de precisión (≥ 0.90) y mejora la exactitud y el F1. A cambio, el recall baja 0.077.
- **Ganancia:** deja de dar 3 respuestas incorrectas.
- **Costo:** escala 2 preguntas que sí sabía responder: "¿Qué tienen para desayunar ahorita?" (S = 0.746) y "¿De qué especialidad es la pizza?" (S = 0.707). En ambas, la entrada correcta quedó en primer lugar.
- **Limitación:** con 40 consultas, cada caso vale unos 2.5 puntos de exactitud, así que la diferencia es indicativa.

**Valores adoptados:**

| Parámetro | Antes | Ahora |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.70 | **0.75** |
| `CONFIDENCE_DIVISOR` | 2.5 | **2.0** |
| `USE_REJECTION_EXAMPLES` | false | **true** |
| `EMBEDDING_MODEL` | default | default (sin cambio) |
| `KEYWORD_CONFIDENCE` | 0.75 | 0.75 (sin cambio) |

**Archivos:**
- `config.py` (valores por defecto)
- `docker-compose.yml`
- `.env.example`
- `Manual_del_Proyecto.md` (tabla de variables)
- `CLAUDE.md` (decisiones fijas y arquitectura)

**Pruebas nuevas** en `tests/test_unit.py`; no se borró ninguna prueba existente:
- `test_calibrated_score_boundary`: con divisor 2.0, d = 0.5 da S = 0.75.
- `test_calibrated_threshold_decision`: con umbral 0.75, `StrategySelector` manda 0.75 al bot y 0.7499 al operador.

**Verificación** (`evaluation/results/pytest_config_final.txt`):
- `ruff check .`: sin avisos.
- Unitarias e integración: **58/58** pasaron.
- `pytest -m chroma`: **1/1**.

**Prueba de humo de la API** (`evaluation/results/api_smoke_config_final.txt`, 3/4):
- El backend arrancó con los valores por defecto nuevos (sin variables de entorno) y con un `DATA_DIR` temporal, para no modificar `data/`.
- El índice tiene 141 documentos, 40 de ellos de rechazo.
- `/health` muestra `confidence_threshold: 0.75` y `rejection_examples: true`.
- "¿A qué hora abren la cafetería?" se respondió (bot, S = 1.0).
- **Hallazgo:** "¿Cuánto cuesta la colegiatura?" **no se escaló**. El bot respondió `antojitos` con S = 0.7881.
  - **Causa:** no es un error del código. Es el falso positivo ya medido en el experimento: S = 0.831 con divisor 2.5 equivale a d ≈ 0.42, que con divisor 2.0 da S ≈ 0.79, por encima de 0.75.
  - Aparece en el análisis de errores de `docs/fase2_resultados_e_interpretacion.md` (fuera de alcance con vocabulario compartido: "cuesta").
  - Con los valores vigentes (0.70 / 2.5), fue FP en las cuatro configuraciones (A–D). Los ejemplos de rechazo no lo cubren, porque se redactaron sin copiar consultas del conjunto de prueba.
  - **No se modificó nada para que pase.** Queda como limitación documentada para el reporte.

---

## Interfaces conectadas por defecto al backend de Render (23-oct-2026)

**Origen:** se reemplazaron `frontend.py` y `dashboard.py` con las versiones de la carpeta `urls_render`. El equipo revisó y aprobó las diferencias antes del reemplazo.

| Cambio | Antes | Ahora | Motivo | Criterio | Archivo |
|---|---|---|---|---|---|
| Dirección por defecto del backend | `http://127.0.0.1:8000` | `https://intelligent-chatbot-std8.onrender.com` (constante `DEFAULT_BACKEND_URL`) | Las interfaces publicadas deben usar el backend desplegado sin configuración extra. Sigue pudiéndose cambiar con `BACKEND_URL` | C5, C7 | `frontend.py`, `dashboard.py` |
| Tiempo de espera de 👍/👎 (RF09) y de las reseñas | 5 s | 30 s | En el plan gratuito, Render "duerme" el backend y la primera petición tarda | C6 | `frontend.py` |
| Tiempo de espera del panel | 10 s (GET) y 15 s (envíos) | 60 s | El mismo motivo | C6 | `dashboard.py` |
| Aviso de conexión del panel del operador | "…Revisa que el backend esté en ejecución." | "…Si el backend estaba dormido (plan gratuito de Render), espera un minuto y actualiza la página." | Orienta al operador ante el arranque en frío | C7 | `dashboard.py` |

**Documentación:** en `Manual_del_Proyecto.md`, la sección 4 ("Ejecución local") ahora explica que las interfaces usan Render por defecto y que, para el backend local, se define `BACKEND_URL=http://127.0.0.1:8000`. También se actualizó la fila de `BACKEND_URL` en la tabla de variables (sección 6).

**Sin cambio:**
- `docker-compose.yml` sigue definiendo `BACKEND_URL=http://backend:8000`.
- `.env.example` conserva `BACKEND_URL=http://127.0.0.1:8000`, para trabajar en local.

**Verificación** (`evaluation/results/pytest_urls_render.txt`):
- `ruff check .`: sin avisos.
- Unitarias e integración: **58/58** pasaron.

**Para el reporte:** si el aviso de conexión del panel aparece en la Tabla 5, hay que actualizar su texto.

---

## Fase 3 — Desempeño: límite de embeddings simultáneos (23-oct-2026)

**Objetivo:** medir si limitar cuántas consultas calculan su embedding a la vez reduce la saturación de CPU (hallazgo H2 de la Fase 1). **Solo se midió.** El límite queda desactivado por defecto (`EMBEDDING_CONCURRENCY=0`) hasta que el equipo decida.

### Cambios en el código

| Cambio | Archivo |
|---|---|
| Límite opcional de embeddings simultáneos (`threading.BoundedSemaphore`); con 0 no hay límite | `vector_store.py` |
| Nueva variable `EMBEDDING_CONCURRENCY = _get_int("EMBEDDING_CONCURRENCY", 0)` | `config.py` |
| `/health` muestra `embedding_concurrency` y `nlp_cache_size` | `main.py` |
| Escalones configurables con `STEP_USERS` y `STEP_SECONDS` (por defecto 10, 25, 50 y 100 usuarios, 60 s) | `locustfile.py` |
| Script de resumen por escalón (tabla y gráfica) | `evaluation/analyze_load.py` |
| Pruebas del límite: se respeta, sin límite hay concurrencia completa y el resultado no cambia | `tests/test_performance.py` |

Se revisaron las diferencias de `vector_store.py`, `main.py` y `locustfile.py`: solo agregan cosas y no deshacen la configuración C ni otros cambios previos.

**Corrección C2** (detalle en `REPORTE_VERIFICACION.md`): el `locustfile.py` recibido tenía `NameError: _seconds` en `StepLoadShape`, así que la prueba por escalones no arrancaba. Ruff lo detectó como F821. Se corrigió calculando los escalones fuera del cuerpo de la clase.

**Verificación** (`evaluation/results/fase3/pytest_fase3.txt`):
- `ruff check .`: sin avisos.
- `pytest -v`: **62/62** pasaron (unitarias, integración, ChromaDB y las 3 nuevas de desempeño).

### Pruebas de carga

**Condiciones:**
- Backend **local** (Windows 11, Python 3.12, un proceso uvicorn), con un `DATA_DIR` temporal nuevo en cada corrida y la configuración C.
- Locust con escalones de 10, 25, 50 y 100 usuarios, 60 s cada uno, y una mezcla de las 120 consultas de `test_set.csv` (4 respondibles por cada 1 que se escala).
- Las variables de cada corrida se comprobaron con `/health` (`<corrida>_health.json`).

**Evidencia:** `evaluation/results/fase3/`
- `<corrida>_stats*.csv`
- `<corrida>_failures.csv`
- logs de locust y del backend
- `corridas_log.txt`
- `carga_resumen.md` y `carga_resumen.png`
- `tiempos_servidor.txt`

**Resumen** (de `carga_resumen.md`; latencias del cliente en segundos; RNF01: p95 < 2.5 s):

| Usuarios | Sin límite, sin caché | Límite 2, sin caché | Sin límite, con caché | Límite 2, con caché |
|---|---|---|---|---|
| 10 | 1.71 req/s · p50 3.8 · p95 7.6 · 0 % | 2.43 req/s · p50 1.9 · p95 3.2 · 0 % | 2.30 req/s · p50 3.6 · p95 8.1 · 0 % | 1.03 req/s · p50 9.0 · p95 11 · 0 % |
| 25 | 1.24 · 4.2 · 19 · 0 % | 1.79 · 2.4 · 13 · 0 % | 11.79 · 0.017 · 6.4 · 0 % | 1.75 · 8.7 · 25 · 0 % |
| 50 | 1.78 · 12 · 28 · **7.89 %** | 1.83 · 5.9 · 25 · 0 % | 24.88 · 0.015 · 2.9 · 0 % | 4.98 · 0.18 · 27 · 0 % |
| 100 | 0.32 · 15 · 45 · **3.80 %** | 1.82 · 12 · 29 · 0 % | 49.34 · 0.013 · **0.115** · 0 % ✔ | 24.85 · 0.18 · 27 · 0 % |

Cada celda muestra throughput · p50 · p95 · errores. La única celda que cumple RNF01 en un escalón completo es "Sin límite, con caché" con 100 usuarios.

**Interpretación (para el reporte; la decisión es del equipo):**

1. **Sin caché, la capacidad real es de unas 2 consultas nuevas por segundo**, con o sin límite. El cuello de botella es el cálculo del embedding con ONNX en CPU. Ninguna variante sin caché cumple RNF01.
2. **El límite de 2 mejora la carga baja y elimina los errores.**
   - Con 10 usuarios, el p50 baja de 3.8 a 1.9 s y el p95 de 7.6 a 3.2 s.
   - Con 50 y 100 usuarios ya no hay errores `HTTP 0`.
   - No aumenta el throughput: la espera pasa de competir por la CPU a hacer cola en el semáforo. Por eso el tiempo *dentro* del servidor sube con el límite: 22 s de mediana con 50 y 100 usuarios (`tiempos_servidor.txt`).
3. **Con caché, la prueba mide sobre todo el calentamiento.** Solo hay 120 consultas distintas, y la caché tiene 256 entradas.
   - Sin límite, la caché se llena en el primer minuto. Desde los 25 usuarios, la mediana del servidor es de 0.2 ms y con 100 usuarios el p95 es de 0.115 s.
   - Con el límite de 2, la caché se llena más despacio y las peticiones encoladas en el semáforo ocupan los hilos del servidor. El p95 se queda en ~27 s hasta 100 usuarios, aunque la mediana ya es baja (0.18 s).
4. **Conclusión provisional:** con preguntas repetidas, el límite de 2 retrasa el calentamiento de la caché y empeora la cola de latencias. Sin caché, ayuda a la latencia con poca carga y evita errores, pero no aumenta la capacidad.

### Incidencias

- **I1. Errores `HTTP 0` (9 en total)** solo en "Sin límite, sin caché": 5 en preguntas respondibles y 4 en las que se escalan. Ocurrieron entre los escalones de 50 y 100 usuarios (00:21:10–00:22:43 UTC). Son errores de conexión del lado del cliente durante la saturación, igual que en la Fase 1.
- **I2. Anomalía sin explicar en "Límite 2, con caché" con 10 usuarios.** La mediana del servidor fue de 8.7 s, contra 1.9 s en "Límite 2, sin caché" en el mismo escalón. Con la caché todavía vacía deberían comportarse igual, y el código no tiene contención de candados entre la caché y la consulta. Puede ser ruido del equipo (otros procesos, antivirus sobre el `DATA_DIR` nuevo). **Conviene repetir esa corrida antes de decidir.**
- **I3. Escalones intermedios en `carga_resumen.md`.** `analyze_load.py` agrupa por número de usuarios, así que los instantes de la rampa (20, 35, 45, 60, 70, 80, 90 usuarios) aparecen como filas. Cada uno tiene **una sola muestra** y no es un escalón real: los válidos son 10, 25, 50 y 100, con unas 55 muestras cada uno. No se modificó el script.
- **I4. Código de salida de locust vacío** en `corridas_log.txt`. Es una limitación de `Start-Process` en PowerShell 5.1. Las 4 corridas terminaron solas en unos 245 s, sin congelarse.
- **I5. Entorno.** Se midió en Windows y no en el contenedor Linux ni en Render (512 MB, CPU compartida), así que las cifras absolutas pueden diferir. El orden relativo entre configuraciones es lo comparable.

---

## Pendiente

- [x] Ejecutar el experimento en el equipo (Claude Code) y registrar aquí los resultados (23-oct-2026).
- [ ] Subir el repositorio local (rama `correcciones-entrega3`) a GitHub.
- [x] El equipo escribe `evaluation/validation_set.csv` (40 consultas) para la medición final.
- [x] Decidir la configuración de producción: configuración C (23-oct-2026). Con el modelo `default` no hace falta cambiar el `Dockerfile` ni los requisitos.
- [ ] Actualizar el reporte: 0.70 → 0.75 y 2.5 → 2.0 en RF05, la Sección 2.3, las Figuras 1 y 3, las Secciones 4.3, 8, 9 y 16 y la Tabla 33.
- [x] Fase 3: límite de embeddings simultáneos implementado (desactivado por defecto) y medido con prueba de carga por escalones (23-oct-2026).
- [ ] Fase 3: el equipo decide el valor de `EMBEDDING_CONCURRENCY` (conviene repetir antes la corrida "Límite 2, con caché", ver I2).
- [ ] Docker: instalar Docker Desktop o usar como evidencia el job `docker` de GitHub Actions.
