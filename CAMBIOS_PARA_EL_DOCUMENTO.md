# Cambios que hay que reflejar en el reporte (tercera entrega)
Este documento lista lo que cambió en el código y qué secciones del reporte hay que actualizar para que digan lo mismo. Sigue la regla de la Sección 20.2: una decisión que cambia debe cambiar en todos los artefactos que la mencionan.

## Antes de editar: decisión sobre el LLM (Gemini)

Las notas del equipo dicen que Gemini se reintegró en `patterns.py`. **En los archivos de esta versión no existe**: ningún archivo de código menciona Gemini ni `google-generativeai`, y `.env` solo tiene la llave. Tampoco existían el `Dockerfile`, el `ci.yml` ni las pruebas que mencionan las notas; esta versión los agrega.

**Recomendación: mantener la arquitectura sin LLM**, que es lo que el código implementa y lo que el reporte ya dice (Tabla 33). Las razones:

- **La profesora ya marcó esta inconsistencia.** El comentario 3 de la Entrega 2 fue justamente que el LLM aparecía en unos artefactos y en otros no. Volver a meterlo reabre ese problema y obliga a rehacer las Secciones 3, 4, 8, 10, 12, 16 y las Figuras 3 y 6.
- **Las métricas de la Sección 16 dejarían de tener sentido.** Si un LLM redacta la respuesta, ya no basta con medir si se recuperó la entrada correcta.
- **Pone en riesgo los requisitos de desempeño.** Agrega una llamada de red en cada respuesta, lo que complica cumplir RNF01 (< 2.5 s), y además tiene costo y depende de una llave de API.
- **La llave quedó expuesta.** El archivo `.env` contiene la llave en texto plano. Si se subió a GitHub hay que revocarla en Google AI Studio aunque no se use.

Si el equipo decide usar Gemini de todos modos, el patrón Strategy permite agregarlo como una tercera estrategia sin tocar las demás (principio Open/Closed). Pero hay que implementarlo de verdad, con pruebas, y reescribir las secciones mencionadas. No se puede declarar "implementado" algo que no está en el código. Un dato adicional: según tengo entendido, la librería `google-generativeai` fue reemplazada por `google-genai`; conviene confirmarlo, junto con el nombre exacto del modelo, en la documentación oficial antes de usarlos.

**Sobre "RF09 de login" en las notas:** la numeración cambió en este reporte. Hoy RF09 es "calificar una respuesta" y la autenticación está fuera de alcance (Sección 14, "Scope changes"). No hay ningún requisito de login.

## 1. Requisitos y mensajes (Secciones 2.1 y 2.4)

| Requisito | Estado | Dónde está |
|---|---|---|
| RF03 Gestionar la base de conocimiento | Implementado | `/api/v1/kb` (GET, POST, PUT, DELETE); pestaña "Base de conocimiento" del panel |
| RF08 Estadísticas | Implementado | `/api/v1/stats`: volumen, resueltas por el bot, tasa de escalamiento, tiempo medio y p95 de respuesta, calificaciones |
| RF09 Calificar una respuesta | Implementado | 👍/👎 en el chat; `/api/v1/ticket/{id}/feedback` |
| RF10 Pedir un operador | Implementado | Botón "Hablar con un operador" y detección de frases como "quiero hablar con un operador" |
| RF11 Reseña del lugar | Implementado | Formulario de estrellas; `/api/v1/reviews`; pestaña "Reseñas" |

En la **Tabla 5**, los cuatro mensajes que estaban como "Specified" pasan a "Implemented". El límite de sesión es de **15 mensajes** (variable `MAX_MESSAGES`).

## 2. Patrones de diseño (Secciones 3.2 y 3.3)

- **Strategy.** El código ahora coincide con el texto: `ResponseStrategy.resolve(context: ConversationContext) -> ResponseResult`, con los estados `"answered"` y `"pending_human"`.
  - Conviene agregar `StrategySelector`, que aplica la regla única "bot si S ≥ 0.70 y el usuario no pidió un operador".
- **Observer.** `EscalationSubject.notify(EscalationEvent)` notifica a `OperatorDashboardNotifier`.
  - Cada evento lleva el usuario, la consulta, el motivo (confianza baja o solicitud del usuario) y la confianza.
  - El notificador registra el evento en el log y guarda los más recientes.
  - El panel sigue leyendo la cola por HTTP (polling), como dice la Sección 6.

## 3. Persistencia (Sección 4.4)

Lo que el reporte describía ahora es cierto en el código:

- La SQL DB (tabla `knowledge_entries`) es la fuente de verdad del catálogo.
- Cada cambio se propaga a ChromaDB en segundo plano (`BackgroundTasks` de FastAPI), es decir, con consistencia eventual.
- Al arrancar, el índice vectorial se reconstruye a partir de la SQL DB.

## 4. Estructura del código (Sección 7)

El repositorio se mantuvo **plano**, sin carpetas por capa. El árbol de la Sección 7 debe reemplazarse por la tabla de la sección 2 del `Manual_del_Proyecto.md`, que muestra la capa de cada archivo.

Hay archivos nuevos que deben mencionarse:

- en la Tabla 9: `config.py`, `input_validation.py` y `knowledge_base.py`;
- en la Sección 15: `tests/`.

## 5. Módulo de IA (Secciones 8 y 16.1)

El orden del flujo híbrido cambió. El texto actual dice "primero palabras clave, luego semántica"; ahora es:

1. **Normalización.** Se aplica también a los documentos indexados, no solo a la consulta.
2. **Recuperación semántica primero.** Cada pregunta de ejemplo y el texto de cada respuesta (sin precios) se indexan como documentos separados. Se toma la distancia mínima por entrada y se calcula S = 1 − d / 2.5.
3. **Respaldo léxico, solo si S < 0.70.** Exige al menos 2 palabras clave de una misma entrada, sin empate. Le asigna una confianza fija de 0.75 y lo registra como `method = "keyword"`.
   - Antes bastaba una sola palabra, y eso producía errores como responder el menú a "¿venden refacciones para una laptop?".
4. **Decisión única con S ≥ 0.70.**

La caché de respuestas se limpia cuando cambia la base de conocimiento, y ya no guarda resultados de errores.

## 6. Manejo de errores (Secciones 9 y 10)

- **La validación Fail Fast se corrigió:**
  - normaliza el texto antes de revisarlo;
  - bloquea 5 o más consonantes seguidas (antes eran 4, y se bloqueaban "sándwich", "instrucciones" y "construcción");
  - bloquea 5 o más letras repetidas.
  
  Actualizar el regex citado en la Sección 10.
- **Las preguntas con S bajo siempre se escalan.** Ya no existe la respuesta 400 "fuera de mi conocimiento" para S < 0.25.
- **Mensaje demasiado largo (> 500 caracteres):** HTTP 422 con un mensaje específico.
- **Petición malformada:** HTTP 422 con la lista de campos que fallaron.
- **Errores internos:** HTTP 500 con un mensaje amigable. El error se registra en la tabla `system_errors` y se ve en el panel.

## 7. Pruebas (Sección 15)

- **Unitarias:** UT-01 a UT-10 están en `tests/test_unit.py`, salvo UT-03, que está en `tests/test_integration.py` porque necesita la API.
- **Integración:** IT-01 a IT-06 están en `tests/test_integration.py`. IT-05 usa `streamlit.testing.v1.AppTest`.
- **ChromaDB real:** `tests/test_chroma.py`.
- **Perfilado de memoria:** `memory_test.py` mide la memoria del proceso (RSS) y la de Python (tracemalloc) en 0, 50, 100 y 500 consultas, estima el tamaño de la sesión con 10, 25 y 50 mensajes, y genera la Figura 8.
- Las columnas "Result" se llenan con la salida real de `pytest` (Figura 7).

## 8. Validación del modelo (Sección 16)

- `evaluation/test_set.csv` tiene **120 consultas**: 30 directas, 30 parafraseadas, 20 informales o con errores, 30 fuera de alcance y 10 ambiguas. Son los mínimos de la Tabla 16.
- `calibrate_confidence.py` imprime y guarda en CSV:
  - la Tabla 19 (matriz de confusión) y la Tabla 20 (métricas);
  - la Tabla 21 (barrido del umbral) y la Tabla 22 (barrido del divisor);
  - la lista de fallas por categoría, para la Tabla 23;
  - la gráfica de la Figura 12.
- **Hay que correrlo con ChromaDB real.** Los números de prueba que salieron con el vector store falso no sirven para el reporte.

## 9. CI/CD (Sección 17)

- `.github/workflows/ci.yml` implementa las etapas de la Tabla 24:
  1. lint (ruff);
  2. pruebas unitarias;
  3. pruebas de integración;
  4. integración con ChromaDB y validación del modelo;
  5. construcción de Docker con prueba de humo;
  6. despliegue con el *deploy hook* de Render;
  7. prueba de humo en producción.
- **Matiz que el reporte debe decir:** el despliegue solo queda condicionado a las pruebas si se desactiva el *auto-deploy* de Render y se configura el secreto `RENDER_DEPLOY_HOOK_URL`. Streamlit Community Cloud sigue desplegando cada push a `main` por su cuenta.
- La redacción de las Secciones 17.1 y 17.2 pasa de "propuesto" a "implementado". La Figura 14 es la captura de una ejecución real en la pestaña Actions de GitHub.

## 10. Docker (Sección 18)

- `Dockerfile` y `docker-compose.yml` implementan la Tabla 25:
  - el modelo de embeddings se descarga al construir la imagen;
  - `BACKEND_URL` se pasa por variable de entorno;
  - los datos viven en el volumen `/app/data`;
  - las interfaces esperan a que el backend pase su revisión de salud.
- **Corrección:** el backend ahora expone `/health`. En la Tabla 26, las *readiness* y *liveness probes* deben apuntar a `/health`, no a `/docs`.
- Kubernetes sigue siendo diseño objetivo, no implementación.

## 11. Desempeño (Sección 19)

- Cada interacción guarda su tiempo de respuesta (`response_time_ms`). El panel muestra el promedio y el percentil 95, lo que sirve para RNF01.
- `locustfile.py` usa preguntas variadas del conjunto de prueba (4 respondibles por cada escalada). Con `STEP_LOAD=1` aplica los escalones de la Tabla 31 (10, 50, 100, 250 y 500 usuarios).
- Antes, todas las consultas de las pruebas de carga y de memoria eran la misma frase. Eso solo medía la caché y nunca tocaba ChromaDB.

## 12. Consistencia (Tabla 33)

Agregar estas filas:

| Decisión | Valor | Dónde vive en el código |
|---|---|---|
| Respaldo léxico | Mínimo 2 coincidencias, confianza 0.75 | `config.py` |
| Límite de mensajes por sesión | 15 | `MAX_MESSAGES` |
| Longitud máxima de la pregunta | 500 caracteres | `MAX_QUERY_LENGTH` |
| Fuente de verdad del catálogo | SQL DB → Vector DB | `refresh_knowledge_base_entry` |

## 13. Datos de la cafetería (base de conocimiento v2)

- Los productos sin precio en `informacion_de_cafeteria.docx` ahora dicen "precio a consultar en caja": cecina adobada, carne asada de cerdo, pizzas de pastor, queso y champiñón, hamburguesas y licuados.
- Se agregaron el paquete de carne asada de cerdo y el filete empanizado, que faltaban.
- Ese documento **no menciona** los métodos de pago ni la ubicación. Se conservaron los de la versión anterior (efectivo, tarjeta y transferencia; planta baja del edificio principal). **Confírmenlos** antes de entregar.
- **Actualización (v2):** la fuente ahora es `docs/fuentes/base_de_conocimiento_cafeteria.txt`, y la lista de cambios está en `docs/BITACORA_DE_CAMBIOS.md`.
  - Nuevos: carnitas, desayunos hasta las 12:00 y sábados de medio día.
  - Retirados: hamburguesas, licuados, sabores de pizza sin precio y paquetes 6 y 7.

## 14. Fase 2: experimento de calidad (Secciones 8, 16.4, 16.5 y Tabla 23)

- **Sección 8:** agregar que el modelo de embeddings es configurable (`EMBEDDING_MODEL`). Con sentence-transformers se normalizan los vectores para que d siga en el rango 0–4.
- **Sección 16.1:** si se adopta el rechazo explícito, agregar el paso "si la entrada más cercana es el grupo de ejemplos de otros temas, se escala (`method = rejected`)".
- **Sección 16.3:** la línea base es la configuración A del experimento, con la base v2 y el conjunto v2. Las cifras de la Fase 1 (base v1) se citan como medición inicial.
- **Sección 16.4:** presentar la comparación A/B/C/D (`RESULTADOS_EXPERIMENTO.md`) y la medición final con el conjunto de validación independiente.
- **Sección 16.5 / Tabla 23:** la fila "Language mismatch" deja de ser hipótesis. Tiene evidencia (S = 0.692 en "capital de Francia") y una mitigación medida (configuración B o D). Lo mismo aplica a "Out-of-scope with shared words" (configuración C o D).
- **Sección 19 y Tabla 30:** si el modelo multilingüe usa más memoria o más latencia, se reporta como *trade-off* con los números del experimento.
- **Sección 15.3:** la Tabla 13 suma la prueba de sincronización de la base de conocimiento (`test_kb_seed_version_sync`).
