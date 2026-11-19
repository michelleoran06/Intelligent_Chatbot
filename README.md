# Intelligent Chatbot: Cafetería de la Facultad de Ingeniería (UAEMEX)

Chatbot que responde dudas sobre la cafetería: horarios, ubicación, formas de pago y menú con precios. Si no sabe la respuesta, envía la pregunta a un operador humano. Es el proyecto de Ingeniería de Software II.

- **Backend:** FastAPI (`main.py`), desplegado en Render: https://intelligent-chatbot-std8.onrender.com
- **Chat de usuarios:** Streamlit (`frontend.py`).
- **Panel del operador y administrador:** Streamlit (`dashboard.py`), protegido con contraseña.

La documentación completa está en [`Manual_del_Proyecto.md`](Manual_del_Proyecto.md). Ahí se explica la instalación, la configuración, el despliegue y el uso. Los errores encontrados y cómo se corrigieron están en [`BITACORA_ERRORES.md`](BITACORA_ERRORES.md).

## Cómo funciona

1. **Recuperación semántica.** ChromaDB con `all-MiniLM-L6-v2` busca en la base de conocimiento (`knowledge_base.py`) las entradas más parecidas a la pregunta. La confianza es S = 1 − d/2, con umbral de 0.75.
2. **Gemini (`gemini-3.5-flash-lite`).** Recibe la pregunta, las 5 entradas más cercanas y los últimos 3 turnos de la misma sesión. Responde en JSON con uno de cuatro tipos:
   - **responder:** contesta solo con la información de la base y cita la entrada que usó.
   - **aclarar:** pide al usuario que reescriba la pregunta. A la tercera vez seguida ofrece un operador.
   - **fuera de tema:** avisa que solo atiende temas de la cafetería.
   - **escalar:** crea un ticket para el operador. Es el único tipo que crea tickets.
3. **Respaldo sin Gemini.** Si Gemini no está configurado o ninguna de las dos keys responde, se usa la regla calibrada en M3: ejemplos de rechazo para lo que está fuera de tema, S ≥ 0.75 o palabras clave para responder y, si no, operador. El bot nunca se queda sin responder.
4. **Patrones de diseño (`patterns.py`).**
   - **Strategy:** una estrategia por ruta (`BotResponseStrategy`, `LLMResponseStrategy`, `ClarifyStrategy`, `OutOfScopeStrategy`, `HumanFallbackStrategy`).
   - **Observer:** `EscalationSubject` avisa al panel cuando hay un caso nuevo.
5. **Persistencia.** SQLite (`chatbot_audit.db`) guarda conversaciones, tickets, reseñas y la bitácora del operador. ChromaDB guarda el índice vectorial.

## Seguridad

- El operador inicia sesión con una contraseña. En el backend solo está su hash bcrypt (`OPERATOR_PASSWORD_HASH`). Los tokens están firmados y duran 8 h.
- Tras 5 intentos fallidos desde la misma IP, el login se bloquea 15 minutos.
- Hay límite de peticiones por IP en `/chat`, `/auth/login` y `/reviews`.
- CORS solo acepta los orígenes de `ALLOWED_ORIGINS`.
- Se envían encabezados de seguridad. Con `ENV=production` se apagan `/docs`, `/redoc` y `/openapi.json`.
- Con `ENV=production`, el backend no arranca si faltan los secretos o tienen un formato inseguro.
- Contra la inyección de prompt, la pregunta va delimitada y Gemini solo puede citar entradas que recibió.
- Ningún secreto se guarda en el repositorio. Los valores reales van en `.env` (ignorado por git) y en las variables de Render. [`.env.example`](.env.example) solo tiene valores falsos.

## Inicio rápido (local)

Requisitos: Python 3.12 (el mismo del CI y de Docker) y Git.

```bash
python -m venv venv
venv\Scripts\activate            # Windows (PowerShell: venv\Scripts\Activate.ps1)
source venv/bin/activate         # Mac/Linux
pip install -r requirements.txt
cp .env.example .env             # y llena los valores reales en .env, nunca en .env.example
python scripts/hash_password.py  # genera el hash de la contraseña del operador para tu .env

uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # backend
streamlit run frontend.py                              # chat (otra terminal)
streamlit run dashboard.py                             # panel del operador (otra terminal)
```

Con Docker: `docker compose up --build` levanta los 3 servicios.

## Pruebas y calidad

```bash
pip install -r requirements-dev.txt
pytest --cov=. --cov-report=term-missing --cov-fail-under=77
ruff check .
```

- **Pruebas:** 193 automatizadas. Son unitarias, de integración, de seguridad, de Gemini simulado (el CI no gasta cuota), con ChromaDB real y de los scripts de producción. La cobertura es de 78 %.
- **CI en GitHub Actions** (`.github/workflows/ci.yml`):
  - `ruff`;
  - las pruebas, con cobertura mínima de 77 %;
  - `pip-audit` y `bandit`;
  - la validación del modelo;
  - la construcción de Docker y una prueba de humo.
- **Evaluación con Gemini real:** `python evaluate_rag.py` (necesita una key en `.env`). Los resultados quedan en `evaluation/results/m4_fase3/`. En `test_set`, el F1 sube de 87.8 % (solo recuperación) a 96.4 % con Gemini.

## Despliegue

- **Render (backend).** Variables obligatorias con `ENV=production`:
  - `OPERATOR_PASSWORD_HASH`;
  - `AUTH_SECRET_KEY`, de al menos 32 caracteres;
  - `ALLOWED_ORIGINS`, con las URLs de las dos apps de Streamlit.

  Para Gemini: `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2` y `GEMINI_MODEL`. Antes de poner `ENV=production`, revisa el formato con `python scripts/check_prod_env.py`. Después del despliegue, verifica con `python scripts/smoke_prod.py`.
- **Streamlit Community Cloud.** Cada app necesita solo `BACKEND_URL` en *Secrets*.
- **Importante:** en el plan gratuito de Render, el disco es efímero y la base se borra en cada despliegue o reinicio. Exporta antes las conversaciones con `GET /api/v1/conversations` (solo operador).

El detalle está en el manual, secciones 6 y 9.

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `main.py` | API FastAPI: validación, orquestación y endpoints |
| `rag_pipeline.py` | Decide la ruta de cada mensaje (Gemini o respaldo) |
| `llm_client.py` | Cliente de Gemini: prompt, esquema JSON, 2 keys, caché |
| `nlp_engine.py`, `vector_store.py` | Recuperación semántica con ChromaDB |
| `patterns.py` | Patrones Strategy y Observer |
| `security.py`, `config.py` | Login, tokens, IP real detrás del proxy y configuración |
| `database.py` | SQLite con SQLAlchemy |
| `knowledge_base.py` | Base de conocimiento inicial y ejemplos de rechazo |
| `frontend.py`, `dashboard.py` | Interfaces de Streamlit |
| `scripts/` | Hash de contraseña, revisión de variables y prueba de humo en producción |
| `evaluation/` | Conjuntos etiquetados (validación, prueba y conversacional) y resultados |
| `tests/` | Pruebas automatizadas |
