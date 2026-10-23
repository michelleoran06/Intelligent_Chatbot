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

**Resultados:** pendientes de ejecución → `evaluation/results/experimento_calidad/RESULTADOS_EXPERIMENTO.md`.

---

## Pendiente

- [ ] Ejecutar el experimento en el equipo (Claude Code) y registrar aquí los resultados.
- [ ] El equipo escribe `evaluation/validation_set.csv` (~40 consultas) para la medición final.
- [ ] Decidir la configuración de producción y, si cambia, actualizar `config.py`, el `Dockerfile` (precarga del modelo), los requisitos y el reporte.
- [ ] Fase 3: optimizaciones de desempeño (límite de embeddings simultáneos, precarga del modelo) y nueva prueba de carga por escalones.
- [ ] Docker: instalar Docker Desktop o usar como evidencia el job `docker` de GitHub Actions.
