#  Intelligent Chatbot - Manual del Proyecto (borrador base)

Instrucciones para instalar, ejecutar, probar y desplegar el sistema, y manual de uso para usuarios, operadores y administradores.

## Parte 1: Manual técnico

### 1. Requisitos previos
- **Python 3.12** (el mismo del CI y de la imagen de Docker).
- **Git**.
- **Docker Desktop** (opcional, para correr todo en contenedores).
- Conexión a internet la primera vez: ChromaDB descarga su modelo de embeddings (all-MiniLM-L6-v2, unos 80 MB).

### 2. Estructura del código

| Archivo | Capa | Responsabilidad |
|---|---|---|
| `frontend.py` | Presentación | Chat de estudiantes, maestros y personal administrativo |
| `dashboard.py` | Presentación | Panel de operador y administrador |
| `main.py` | Edge y lógica de negocio | API FastAPI: validación, orquestación y endpoints |
| `input_validation.py` | Edge | Validación Fail Fast y normalización de texto |
| `patterns.py` | Lógica de negocio | Patrones Strategy y Observer |
| `nlp_engine.py` | IA / predicción | Recuperación semántica, respaldo léxico y confianza |
| `vector_store.py` | Persistencia | ChromaDB (Vector DB) |
| `database.py` | Persistencia | SQLite con SQLAlchemy (SQL DB) |
| `knowledge_base.py` | Datos | Base de conocimiento predeterminada (v2) y ejemplos de rechazo |
| `config.py` | Configuración | Umbral, divisor, límites y rutas (variables de entorno) |
| `tests/` | Pruebas | Unitarias, de integración y con ChromaDB real |
| `calibrate_confidence.py` | Validación del modelo | Matriz de confusión, métricas y calibración |
| `memory_test.py` | Pruebas | Perfilado de memoria |
| `locustfile.py` | Pruebas | Prueba de carga |
| `evaluation/test_set.csv` | Datos | 120 consultas etiquetadas para la validación |

### 3. Instalación

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt        # para ejecutar el sistema
pip install -r requirements-dev.txt    # además: pruebas, validación, memoria y carga
```

### 4. Ejecución local (3 terminales)

**Terminal 1: backend**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Al arrancar se crea `data/chatbot_audit.db`, se carga la base de conocimiento y se construye el índice en `data/chroma_data`. Documentación interactiva: http://localhost:8000/docs

**Terminal 2: chat del usuario**
```bash
streamlit run frontend.py
```

**Terminal 3: panel del operador**
```bash
streamlit run dashboard.py
```

Por defecto, las interfaces se conectan al backend desplegado en Render: `https://intelligent-chatbot-std8.onrender.com`. Para trabajar con el backend local de la Terminal 1, define la variable de entorno `BACKEND_URL` antes de abrir las interfaces; **no hay que editar el código**.

```bash
# Windows (cmd)
set BACKEND_URL=http://127.0.0.1:8000
# Windows (PowerShell)
$env:BACKEND_URL = "http://127.0.0.1:8000"
# Mac/Linux
export BACKEND_URL=http://127.0.0.1:8000
```

En el plan gratuito, Render "duerme" el backend cuando no se usa. La primera petición puede tardar alrededor de un minuto; por eso las interfaces esperan hasta 30 s (chat) o 60 s (panel) antes de mostrar un error. Docker Compose ya define `BACKEND_URL` por su cuenta.

### 5. Ejecución con Docker

```bash
docker compose up --build
```

| Servicio | Dirección |
|---|---|
| API | http://localhost:8000/docs |
| Chat | http://localhost:8501 |
| Panel | http://localhost:8502 |

Los datos se guardan en el volumen `chatbot_data`, así que sobreviven al reemplazo de los contenedores. Con `docker compose down -v` se borran.

### 6. Configuración (variables de entorno)

| Variable | Valor por defecto | Uso |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | 0.75 | Umbral S para responder automáticamente |
| `CONFIDENCE_DIVISOR` | 2.0 | Divisor de la fórmula S = 1 − d / divisor |
| `KEYWORD_CONFIDENCE` | 0.75 | Confianza asignada al respaldo por palabras clave |
| `MAX_QUERY_LENGTH` | 500 | Máximo de caracteres por pregunta |
| `DATA_DIR` | ./data | Carpeta de SQLite y ChromaDB |
| `ENV` | development | `production` apaga `/docs`, `/redoc` y `/openapi.json`, activa HSTS y exige los secretos de abajo para arrancar |
| `OPERATOR_PASSWORD_HASH` | (vacío) | Hash bcrypt de la contraseña del operador (mínimo 12 caracteres), generado con `python scripts/hash_password.py`. Vacío = nadie puede iniciar sesión |
| `AUTH_SECRET_KEY` | (vacío) | Clave aleatoria de al menos 32 caracteres para firmar los tokens de sesión. Vacío = nadie puede iniciar sesión |
| `ALLOWED_ORIGINS` | (vacío) | Orígenes permitidos por CORS, separados por comas (las URLs de las apps de Streamlit) |
| `TOKEN_TTL_HOURS` | 8 | Duración de la sesión del operador |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | 5 / 15 | Intentos fallidos de login por IP antes de bloquearla, y minutos de bloqueo |
| `RATE_LIMIT_CHAT` / `RATE_LIMIT_LOGIN` / `RATE_LIMIT_REVIEWS` | 20/minute, 5/minute, 5/minute | Peticiones máximas por IP a `/chat`, `/auth/login` y `POST /reviews` (respuesta 429) |
| `TRUSTED_PROXY_HOPS` | 0 | Proxies de confianza al final de `X-Forwarded-For` para obtener la IP real del cliente. 0 en local y Docker; en Render, ver la sección 9 |
| `GEMINI_API_KEY_1` / `GEMINI_API_KEY_2` | (vacío) | Keys de Gemini (Google AI Studio). La segunda es de respaldo: si la primera agota su cuota o falla, se usa la otra. Vacías = el bot responde solo con la recuperación (regla de M3). Nunca se escriben en el código ni en los logs |
| `GEMINI_MODEL` | (vacío) | Modelo de Gemini. Se validó `gemini-3.5-flash-lite` (plan gratuito). Vacío = Gemini desactivado |
| `GEMINI_TIMEOUT_SECONDS` | 15 | Tiempo máximo por llamada a Gemini (mínimo 10: la API rechaza valores menores) |
| `GEMINI_THINKING_BUDGET` | (vacío) | Presupuesto de razonamiento del modelo; 0 lo apaga en los Flash que lo permiten (más rápido) |
| `LLM_CACHE_SIZE` | 256 | Respuestas de Gemini guardadas en memoria (misma pregunta y mismas entradas = sin gastar cuota) |
| `LLM_CONTEXT_ENTRIES` | 5 | Entradas de la base de conocimiento que recibe Gemini (top-k de ChromaDB) |
| `LLM_HISTORY_TURNS` / `LLM_HISTORY_MINUTES` | 3 / 30 | Turnos previos de la misma sesión que recibe Gemini, solo de los últimos N minutos (E-027) |
| `CLARIFY_MAX_IN_A_ROW` | 2 | Veces seguidas que el bot pide aclarar antes de ofrecer un operador |
| `OUT_OF_SCOPE_CONFIDENCE` | 0 | Si la confianza S es menor, se avisa que solo se atienden temas de la cafetería, sin Gemini ni operador. 0 = desactivado (solo ejemplos de rechazo) |
| `BACKEND_URL` | https://intelligent-chatbot-std8.onrender.com | Dirección del backend (solo en las interfaces); en local, `http://127.0.0.1:8000` |
| `MAX_MESSAGES` | 15 | Límite de mensajes por sesión de chat |
| `EMBEDDING_MODEL` | default | `default` = all-MiniLM-L6-v2; otro valor = modelo de sentence-transformers |
| `USE_REJECTION_EXAMPLES` | true | Indexa ejemplos de preguntas de otros temas para escalarlas |
| `EMBEDDING_CONCURRENCY` | 2 | Máximo de consultas que calculan su embedding a la vez (0 = sin límite) |
| `SERVER_THREADS` | 200 | Hilos del servidor para los endpoints; las respuestas en caché no esperan a los cálculos de embeddings |
| `EMBEDDING_BATCH_SIZE` | 16 | Documentos por lote al construir el índice vectorial; limita la memoria pico al arrancar |
| `MALLOC_ARENA_MAX` | 2 (en Docker/Render) | Variable de glibc (solo Linux): limita las arenas de memoria por hilo y reduce la memoria del proceso. No la lee `config.py` |

Copia `.env.example` como `.env` para tenerlas a mano. El archivo `.env` **nunca** se sube a GitHub.

#### 6.1 Generar el hash de la contraseña del operador
La contraseña nunca se guarda ni se escribe en ningún archivo: solo su hash bcrypt, y solo en `OPERATOR_PASSWORD_HASH` (Render o tu `.env` local).

```bash
pip install -r requirements.txt
python scripts/hash_password.py                                   # pide la contraseña dos veces, sin mostrarla
python -c "import secrets; print(secrets.token_urlsafe(48))"      # valor para AUTH_SECRET_KEY
```
El script rechaza contraseñas de menos de 12 caracteres o de más de 72 bytes y solo imprime el hash (`$2b$12$…`). Cópialo completo a la variable; si lo pones en un `.env` que use Docker Compose, enciérralo entre comillas simples por los signos `$`.

> **Windows:** si el script falla con `ImportError: DLL load failed while importing _bcrypt`, tu entorno tiene una versión de bcrypt distinta a la del proyecto. Reinstálala con la versión fijada (E-021):
> ```bash
> venv\Scripts\activate
> pip uninstall -y bcrypt
> pip install -r requirements.txt
> python scripts/hash_password.py
> ```

### 7. Pruebas y validación

```bash
pytest tests/test_unit.py -v           # pruebas unitarias (Sección 15.2)
pytest tests/test_integration.py -v    # pruebas de integración (Sección 15.3)
pytest tests/test_security.py -v       # pruebas de seguridad (login, tokens, IDOR, rate limit)
pytest --cov=. --cov-report=term-missing   # toda la suite con cobertura
pytest -m chroma -v                    # integración con ChromaDB real
python calibrate_confidence.py         # validación del modelo (Sección 16)
python memory_test.py                  # perfilado de memoria (Sección 15.4)
locust -f locustfile.py --host http://127.0.0.1:8000    # carga (Sección 19.5)

pip install -r requirements-experiment.txt
python experiment_quality.py           # compara 4 configuraciones del modelo (Sección 16.4)
```

Los resultados (CSV y gráficas) se guardan en `evaluation/results/`.

**Compuertas del CI (Fase 4).** Además de ruff y las pruebas por etapa, el CI corre toda la suite con `--cov-fail-under=77` (falla si la cobertura baja de 77 %) y sube `coverage.xml` como artefacto. También corre `pip-audit -r requirements.txt` (dependencias con vulnerabilidades conocidas; las 4 de chromadb sin versión corregida se ignoran por ID, ver E-029) y `bandit -r . -x ./tests --severity-level medium` (falla con hallazgos de severidad media o alta; los de severidad baja están revisados en E-030). Para correrlas en local:

```bash
pip install pip-audit bandit
pytest --cov=. --cov-report=term-missing --cov-fail-under=77
pip-audit -r requirements.txt
bandit -r . -x ./tests
```

> **Sobre la prueba de carga:** cada pregunta escalada crea un ticket. Córrela contra los contenedores locales y no contra producción. Como `/chat` acepta 20 peticiones por minuto por IP, para la prueba de carga local sube el límite (por ejemplo, `RATE_LIMIT_CHAT=100000/minute`).

### 7.2 Respuestas con Gemini (Fase 3)
Cada pregunta del dominio pasa por este orden (`rag_pipeline.decide`, usado igual por `/api/v1/chat` y por `evaluate_rag.py`):
1. Si Gemini está configurado, se hace **una sola llamada** por mensaje. Gemini recibe las `LLM_CONTEXT_ENTRIES` entradas más cercanas (buscadas con el mensaje y con la pregunta anterior de la sesión) y los últimos `LLM_HISTORY_TURNS` turnos de la misma sesión de los últimos `LLM_HISTORY_MINUTES` minutos, leídos de `conversation_logs` por `user_id` (nunca del navegador). Responde en JSON (`tipo`, `source_id`, `answer`), con `tipo` = `responder` (ruta `llm`), `aclarar` (`clarify`, `ClarifyStrategy`), `fuera_de_tema` (`out_of_scope`) o `escalar` (`human`). **Solo `escalar` crea ticket.** Un `responder` que cita una entrada que no recibió, o un tipo desconocido, se descarta (E-027).
2. Anti-bucle: si el bot ya pidió aclarar `CLARIFY_MAX_IN_A_ROW` veces seguidas en la sesión, la siguiente aclaración ofrece hablar con un operador (sin crear ticket).
3. Si Gemini no está configurado o ninguna key responde, se usa la regla de M3: ejemplos de rechazo (o S < `OUT_OF_SCOPE_CONFIDENCE`) = fuera de tema; S ≥ 0.75 o palabras clave = respuesta; si no, operador. El bot nunca se queda sin responder.

La pregunta va delimitada en `<pregunta>` y el historial en `<conversacion>`, y el prompt le indica ignorar instrucciones dentro de ella (inyección de prompt). Las pruebas (`tests/test_llm.py`) simulan Gemini, así que CI no gasta cuota. Para medir con Gemini real:

```bash
python evaluate_rag.py --no-llm   # solo recuperación (sin cuota)
python evaluate_rag.py            # con Gemini; lee las keys de .env sin imprimirlas
```

Los resultados quedan en `evaluation/results/m4_fase3/`. Con Python 3.9 se instala `google-genai` 1.47 (la última que lo soporta); con Python 3.11 o más reciente, la versión actual.

### 7.1 Seguridad de la API
| Endpoint | Acceso |
|---|---|
| `GET /health` | Público; solo responde `{"status": "ok"}` |
| `POST /api/v1/chat`, `POST /api/v1/reviews` | Públicos, con límite de peticiones por IP |
| `GET /api/v1/ticket/{public_id}?user_id=…`, `POST /api/v1/ticket/{public_id}/feedback` | Públicos, pero solo para el dueño del ticket: `public_id` es un UUID y el `user_id` debe coincidir |
| `POST /api/v1/auth/login` | Público; 5 por minuto y bloqueo de 15 min por IP tras 5 fallos |
| `/resolve`, `/tickets/escalated`, `/stats`, `/errors`, `GET /reviews`, todo `/kb`, `/system`, `/operator-actions`, `/auth/check` | Solo con `Authorization: Bearer <token>` del operador |

Cada respuesta lleva `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy` y `Cache-Control: no-store` (más HSTS en producción). Un error 500 nunca devuelve detalles internos. Los inicios de sesión, resoluciones de tickets y cambios a la base de conocimiento quedan en la tabla `operator_actions` con la IP y la hora.

### 8. Actualizar la información de la cafetería
- **Cambios puntuales:** se hacen desde el panel, en la pestaña "📚 Base de conocimiento".
- **Cambios grandes:**
  1. Editar `knowledge_base.py`.
  2. Cambiar `KB_SEED_VERSION`.
  3. Reiniciar el backend: actualiza las entradas predeterminadas y respeta las que creó el Administrador.

### 9. Despliegue
- **Render (backend).** Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`. Variables: las de la sección 6. Obligatorias para el login: `OPERATOR_PASSWORD_HASH`, `AUTH_SECRET_KEY` y `ALLOWED_ORIGINS`. Con `TRUSTED_PROXY_HOPS=2` se toma la IP real del cliente detrás de Render y Cloudflare; después de desplegar, compara `ip_detectada` de `GET /api/v1/system` con tu IP pública para confirmarlo.
- **Streamlit Community Cloud (chat y panel).** En *Settings → Secrets* de cada app agrega `BACKEND_URL = "https://intelligent-chatbot-std8.onrender.com"`. Es la única variable de las dos apps: la contraseña del operador **no** se configura en Streamlit, solo su hash en Render (`OPERATOR_PASSWORD_HASH`).
- **GitHub Actions (`.github/workflows/ci.yml`).** En cada pull request y en cada push a `main` ejecuta lint, pruebas, la validación del modelo, la construcción de Docker y una prueba de humo. Para que el despliegue dependa de las pruebas:
  1. Desactiva el *auto-deploy* de Render.
  2. Guarda el *deploy hook* de Render como el secreto `RENDER_DEPLOY_HOOK_URL` del repositorio.
  3. Opcionalmente, guarda la URL pública del backend como `BACKEND_PUBLIC_URL`.

#### 9.1 Paso a producción y verificación (Fase 5)
Variables del backend en Render:
- **Obligatorias con `ENV=production`:** `OPERATOR_PASSWORD_HASH`, `AUTH_SECRET_KEY` y `ALLOWED_ORIGINS`. Si falta una o tiene un formato inseguro, el backend **no arranca**.
- **Gemini:** `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2` (respaldo) y `GEMINI_MODEL=gemini-3.5-flash-lite`.
- **Otras:** `TRUSTED_PROXY_HOPS` (ver E-017).

Orden:
1. **Revisar el formato de las variables, sin red:** `python scripts/check_prod_env.py`. Pide los valores con `getpass` y nunca los imprime. Aplica las mismas reglas que `config.validate_config` y, si escribes la contraseña, comprueba que coincide con el hash. Solo sigue si dice OK.
2. **Fusionar la PR en `main`.**
3. **En Render, *Environment*:** agregar `ENV=production` y guardar. Render vuelve a desplegar, y el plan gratuito borra la base (E-031): exporta antes lo que necesites.
4. **Esperar a que Render diga *Live*.** Si el despliegue falla, el log dice qué variable falta. Para volver a la versión anterior, quita `ENV` y el backend arranca como antes.
5. **Correr la prueba de humo:** `python scripts/smoke_prod.py`. Verifica:
   - `/health`;
   - que `/docs`, `/redoc` y `/openapi.json` den 404;
   - que un endpoint del operador sin token dé 401;
   - 1 login incorrecto (401) y el login correcto (200);
   - que Gemini esté configurado;
   - una pregunta normal (ruta `llm`);
   - la pregunta de la colegiatura (fuera de tema u operador);
   - un intento de inyección de prompt (no revela el prompt);
   - la exportación en CSV.

   Muestra al final la IP con la que te ve el backend, para comprobar E-017. **No lo corras 5 veces seguidas sin un login correcto:** 5 intentos fallidos bloquean tu IP 15 minutos.

---

## Parte 2: Manual de uso

### Usuario (estudiante, maestro o personal administrativo)

No necesitas registrarte ni iniciar sesión.

1. **Perfil.** En la barra lateral elige si eres estudiante, maestro o personal administrativo.
2. **Pregunta.** Escribe tu duda con tus propias palabras o usa los botones de *Consultas rápidas*. El bot conoce:
   - los horarios;
   - la ubicación;
   - los métodos de pago;
   - el menú con precios: desayunos (hasta las 12:00), chilaquiles, antojitos y molletes, sándwiches, paquetes, pizzas, carnitas (viernes y sábado), bebidas, panadería y menú del día.
3. **Califica la respuesta** con 👍 o 👎.
4. **Cómo responde el bot.** Entiende faltas de ortografía y preguntas de seguimiento ("¿aceptan tarjeta?" y luego "y si no"), porque recuerda los últimos 3 mensajes de los últimos 30 minutos de tu conversación. Según tu mensaje, hace una de cuatro cosas:
   - **Responde** si tiene la información. Si solo tiene una parte, te dice lo que sabe y te sugiere hablar con un operador.
   - **Te pide que lo reescribas** si no entendió o falta información (por ejemplo, solo "cuánto"). No se envía a un operador. Si te lo pide 2 veces seguidas, a la tercera te sugiere hablar con un operador.
   - **Te avisa que solo atiende la cafetería** si preguntas por otro tema (trámites, clima, tareas). No se envía a un operador.
   - **Envía tu pregunta a un operador** si es de la cafetería, se entiende y no tiene la información (por ejemplo, apartar un pedido).
5. **Hablar con una persona.** También puedes pedirlo tú en cualquier momento: escribe "quiero hablar con un operador" o pulsa **🙋 Hablar con un operador**.
6. **Espera en línea.** Mantén la ventana abierta mientras el operador responde. Si tarda, su respuesta aparecerá en el chat la próxima vez que interactúes.
7. **Reseña.** Evalúa la cafetería con estrellas y un comentario desde la barra lateral.
8. **Límite de la conversación.** Después de 15 mensajes verás "Memoria llena". Recarga la página para empezar otra conversación. Lo que ya preguntaste queda registrado.

### 🎧 Operador

0. Al abrir el panel, escribe la contraseña del operador y pulsa **Entrar**. La sesión dura 8 horas; cuando vence (o si el token deja de ser válido) el panel vuelve solo a la pantalla de inicio de sesión. Usa **🚪 Cerrar sesión** en la barra lateral al terminar. Tras 5 contraseñas incorrectas desde la misma red, el inicio de sesión se bloquea 15 minutos.
1. Abre la pestaña **🚨 Casos pendientes**.
2. La cola se actualiza sola cada 10 segundos. Cuando llega un caso nuevo verás un aviso y escucharás un sonido.
3. Pulsa **🔄 Actualizar lista de casos** para que el caso nuevo aparezca en el selector.
4. Elige el ticket, escribe la respuesta y pulsa **Enviar respuesta y cerrar caso**. La respuesta llega al chat del usuario y el ticket sale de la cola. Si otro operador ya lo atendió, el panel te avisa.
5. **Exportar conversaciones.** Con el token de la sesión, `GET /api/v1/conversations?since=<fecha ISO>` devuelve un CSV con hora, sesión, pregunta, respuesta, ruta y ticket. La base del plan gratuito de Render se borra en cada despliegue o reinicio: exporta antes de desplegar (E-031).

### 🛠️ Administrador

- **🔐 Bitácora:** quién hizo qué y cuándo: inicios de sesión (correctos, fallidos y bloqueados), tickets resueltos y cambios a la base de conocimiento, con la IP.
- **📊 Estadísticas:** número de conversaciones, cuántas resolvió el bot, tasa de escalamiento, tiempo medio y percentil 95 de respuesta, y calificaciones 👍/👎, por tipo de usuario.
- **⭐ Reseñas:** reseñas del lugar y calificación promedio.
- **📚 Base de conocimiento:** crear, editar y eliminar entradas. Cada entrada tiene:
  - una respuesta;
  - preguntas de ejemplo (una por línea), que son las que usa la búsqueda semántica;
  - palabras clave de respaldo.
  
  Los cambios se reindexan en segundo plano en unos segundos.
- **⚠️ Errores:** los últimos errores del sistema.
