# CLAUDE.md — Intelligent Chatbot (Cafetería, Facultad de Ingeniería UAEM)

## Qué es este proyecto
Chatbot de la cafetería de la Facultad de Ingeniería. Proyecto escolar de Ingeniería de Software II.
- **Backend:** FastAPI (`main.py`) desplegado en Render.
- **Chat de usuario:** Streamlit (`frontend.py`).
- **Panel de operador/admin:** Streamlit (`dashboard.py`).
- **IA:** recuperación semántica con ChromaDB + `all-MiniLM-L6-v2` (`vector_store.py`, `nlp_engine.py`).
  Confianza `S = 1 - d/2`, umbral 0.75, ejemplos de rechazo para fuera de dominio.
- **Persistencia:** SQLite (`database.py`, `chatbot_audit.db`) + ChromaDB (`chroma_data/`).
- **Patrones:** Strategy (`BotResponseStrategy`, `HumanFallbackStrategy`) y Observer (`EscalationSubject`) en `patterns.py`.
- **Calidad:** 64 pruebas (pytest), CI en GitHub Actions, Docker Compose con 3 servicios, Locust para carga.

> Si algo de lo anterior no coincide con el código real del repo, **el código manda**: avísale a la usuaria qué difiere antes de cambiar nada.

## Reglas de trabajo (OBLIGATORIAS)
1. **No hagas nada sin consultar.** Antes de cada fase de `PLAN_CORRECCIONES.md`, muestra qué archivos vas a tocar y qué vas a cambiar, y espera un "sí". Si surge algo fuera del plan, pregunta.
2. **Una rama por fase** (`fase-1-secretos`, `fase-2-seguridad`, …). Commits pequeños con mensajes claros en español. **Nunca** hagas push a `main` ni merge sin permiso.
3. **Después de cada fase:** corre `pytest` completo (con cobertura) y reporta resultados. Si algo falla, no avances.
4. **Bitácora de errores:** TODO error, bug, fallo de prueba o vulnerabilidad que encuentres o corrijas se registra en `BITACORA_ERRORES.md` con el formato que ya tiene. Esto es un entregable del proyecto; no lo omitas.
5. **Secretos:** nunca escribas una API key, contraseña o token en código, commits, logs o archivos versionados. Solo en `.env` (ignorado por git), en los Environment Variables de Render y en los Secrets de Streamlit Cloud. Siempre proporciona un `.env.example` con valores falsos.
6. **No cambies el comportamiento funcional fuera del plan**, ni los parámetros calibrados (umbral, divisor, modelo de embeddings) sin preguntar.
7. Comunícate con la usuaria en **español**. Código, docstrings y nombres pueden seguir el estilo existente del repo.
8. Cada cambio debe dejar evidencia que se pueda poner en el reporte: prueba automatizada, captura o salida de comando.

## Comandos
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload   # backend
streamlit run frontend.py                              # chat
streamlit run dashboard.py                             # panel operador
pytest --cov=. --cov-report=term-missing               # pruebas + cobertura
docker compose up --build                              # todo en contenedores
```

## Contexto académico
- Evaluación del Milestone 4: se verifica que las observaciones del Milestone 3 estén corregidas, que el software funcione y que la documentación coincida con el sistema.
- La profesora **intentará romper el sistema** (accesos sin contraseña, endpoints abiertos, inyección, spam). Diseña pensando en eso.
- El reporte escrito del M4 se redacta en **inglés** más adelante; por ahora solo se recopila evidencia.
