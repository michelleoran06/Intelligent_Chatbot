# Contexto del proyecto para Claude Code

Proyecto escolar **Intelligent Chatbot** (Software Engineering II, UAEMéx, Equipo 1): chatbot de la cafetería de la Facultad de Ingeniería. El reporte de la Entrega 3 se evalúa con una rúbrica centrada en **pruebas, validación del modelo, CI/CD, Docker, desempeño y evidencia técnica**, no en funcionalidades nuevas.

## Arquitectura (ver Manual_del_Proyecto.md)
- `main.py`: API FastAPI. Validación Fail Fast → saludos → solicitud de operador (RF10) → motor de IA → Strategy → registro en SQLite.
- `nlp_engine.py`: recuperación semántica en ChromaDB primero (S = 1 − d / 2.0), con ejemplos de rechazo. Si S < 0.75, respaldo por palabras clave con ≥ 2 coincidencias y confianza fija de 0.75.
- `patterns.py`: patrones Strategy (`resolve()`, estados `answered` / `pending_human`) y Observer.
- `database.py`: SQLite. La tabla `knowledge_entries` es la fuente de verdad y se propaga a ChromaDB en segundo plano.
- `frontend.py` y `dashboard.py`: Streamlit. Leen la dirección del backend de `BACKEND_URL`.
- Configuración centralizada en `config.py` (variables de entorno).

## Decisiones fijas (NO cambiar sin autorización explícita del equipo)
- **Sin LLM:** el bot solo devuelve respuestas almacenadas o escala a un humano.
- **Umbral 0.75, divisor 2.0 y ejemplos de rechazo activos** (`USE_REJECTION_EXAMPLES=true`), calibrados en la Fase 2 (configuración C, confirmada con el conjunto de validación independiente). Solo se cambian si una nueva calibración lo justifica y el equipo lo aprueba.
- **Límites:** 500 caracteres por pregunta y 15 mensajes por sesión.
- **Mensajes al usuario:** en español, iguales a la Tabla 5 del reporte.
- **Estructura del repositorio:** plana, sin carpetas por capa.
- **Base de conocimiento v2** (`knowledge_base.py`, fuente: `docs/fuentes/base_de_conocimiento_cafeteria.txt`). No inventar productos, precios ni horarios.
- **Modelo de embeddings en producción:** `EMBEDDING_MODEL=default` (all-MiniLM-L6-v2). El modelo multilingüe se descartó en la Fase 2 porque no cabe en la memoria de Render.
- **Conjunto de validación independiente:** `evaluation/validation_set.csv` lo escribe el equipo. No usarlo para ajustar nada; solo para la medición final.

## Reglas de trabajo
1. **No agregar funcionalidades** ni cambiar el comportamiento del sistema. Solo verificar, corregir errores y generar evidencia.
2. **Si una prueba falla, primero diagnosticar y reportar la causa.** Nunca modificar los valores esperados de una prueba para que pase sin explicarlo y pedir permiso.
3. **Cada corrección se registra** en `evaluation/results/REPORTE_VERIFICACION.md` con:
   - el archivo y la línea;
   - el error original;
   - la causa;
   - el cambio hecho.
4. **No leer, imprimir ni subir `.env`.** Tampoco subir `data/`, archivos `*.db` ni `chroma_data/` (ya están en `.gitignore`).
5. **Trabajar en la rama `correcciones-entrega3`** con commits pequeños, con mensajes del tipo `fix: ...`, `test: ...` o `docs: ...`.
6. **Guardar toda salida de comandos útil como evidencia** en `evaluation/results/`.
7. **Ante cualquier duda de diseño, preguntar** antes de cambiar.
8. **Registrar en `docs/BITACORA_DE_CAMBIOS.md`** cada resultado y cada corrección.

## Comandos
```bash
pip install -r requirements-dev.txt
ruff check .
pytest tests/test_unit.py tests/test_integration.py -v
pytest -m chroma -v
uvicorn main:app --port 8000
python calibrate_confidence.py
python memory_test.py
docker compose up --build -d
pip install -r requirements-experiment.txt && python experiment_quality.py
```
