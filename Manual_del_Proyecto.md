# ☕ Intelligent Chatbot - Manual del Proyecto

Instrucciones para instalar, ejecutar, probar y desplegar el sistema, y manual de uso para usuarios, operadores y administradores.

---

## 🛠️ Parte 1: Manual técnico

### 1. Requisitos previos
- **Python 3.10 o superior** (la imagen de Docker usa 3.11).
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

Por defecto, las interfaces se conectan a `http://127.0.0.1:8000`. Para usar el backend de Render **ya no hay que editar el código**: basta con definir la variable de entorno `BACKEND_URL`.

```bash
# Windows (cmd)
set BACKEND_URL=https://intelligent-chatbot-std8.onrender.com
# Mac/Linux
export BACKEND_URL=https://intelligent-chatbot-std8.onrender.com
```

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
| `CONFIDENCE_THRESHOLD` | 0.70 | Umbral S para responder automáticamente |
| `CONFIDENCE_DIVISOR` | 2.5 | Divisor de la fórmula S = 1 − d / divisor |
| `KEYWORD_CONFIDENCE` | 0.75 | Confianza asignada al respaldo por palabras clave |
| `MAX_QUERY_LENGTH` | 500 | Máximo de caracteres por pregunta |
| `DATA_DIR` | ./data | Carpeta de SQLite y ChromaDB |
| `ADMIN_TOKEN` | (vacío) | Si se define, exige el token para modificar la base de conocimiento |
| `BACKEND_URL` | http://127.0.0.1:8000 | Dirección del backend (solo en las interfaces) |
| `MAX_MESSAGES` | 15 | Límite de mensajes por sesión de chat |
| `EMBEDDING_MODEL` | default | `default` = all-MiniLM-L6-v2; otro valor = modelo de sentence-transformers |
| `USE_REJECTION_EXAMPLES` | false | Indexa ejemplos de preguntas de otros temas para escalarlas |

Copia `.env.example` como `.env` para tenerlas a mano. El archivo `.env` **nunca** se sube a GitHub.

### 7. Pruebas y validación

```bash
pytest tests/test_unit.py -v           # pruebas unitarias (Sección 15.2)
pytest tests/test_integration.py -v    # pruebas de integración (Sección 15.3)
pytest -m chroma -v                    # integración con ChromaDB real
python calibrate_confidence.py         # validación del modelo (Sección 16)
python memory_test.py                  # perfilado de memoria (Sección 15.4)
locust -f locustfile.py --host http://127.0.0.1:8000    # carga (Sección 19.5)

pip install -r requirements-experiment.txt
python experiment_quality.py           # compara 4 configuraciones del modelo (Sección 16.4)
```

Los resultados (CSV y gráficas) se guardan en `evaluation/results/`.

> **Sobre la prueba de carga:** cada pregunta escalada crea un ticket. Córrela contra los contenedores locales y no contra producción.

### 8. Actualizar la información de la cafetería
- **Cambios puntuales:** se hacen desde el panel, en la pestaña "📚 Base de conocimiento".
- **Cambios grandes:**
  1. Editar `knowledge_base.py`.
  2. Cambiar `KB_SEED_VERSION`.
  3. Reiniciar el backend: actualiza las entradas predeterminadas y respeta las que creó el Administrador.

### 9. Despliegue
- **Render (backend).** Comando de inicio: `uvicorn main:app --host 0.0.0.0 --port $PORT`. Variables: las de la sección 6.
- **Streamlit Community Cloud (chat y panel).** En *Settings → Secrets* de cada app agrega `BACKEND_URL = "https://intelligent-chatbot-std8.onrender.com"`. En el panel agrega también `ADMIN_TOKEN` si lo usas.
- **GitHub Actions (`.github/workflows/ci.yml`).** En cada pull request y en cada push a `main` ejecuta lint, pruebas, la validación del modelo, la construcción de Docker y una prueba de humo. Para que el despliegue dependa de las pruebas:
  1. Desactiva el *auto-deploy* de Render.
  2. Guarda el *deploy hook* de Render como el secreto `RENDER_DEPLOY_HOOK_URL` del repositorio.
  3. Opcionalmente, guarda la URL pública del backend como `BACKEND_PUBLIC_URL`.

---

## 👥 Parte 2: Manual de uso

### 🙋 Usuario (estudiante, maestro o personal administrativo)

No necesitas registrarte ni iniciar sesión.

1. **Perfil.** En la barra lateral elige si eres estudiante, maestro o personal administrativo.
2. **Pregunta.** Escribe tu duda con tus propias palabras o usa los botones de *Consultas rápidas*. El bot conoce:
   - los horarios;
   - la ubicación;
   - los métodos de pago;
   - el menú con precios: desayunos (hasta las 12:00), chilaquiles, antojitos y molletes, sándwiches, paquetes, pizzas, carnitas (viernes y sábado), bebidas, panadería y menú del día.
3. **Califica la respuesta** con 👍 o 👎.
4. **Hablar con una persona.** Si el bot no sabe la respuesta, envía tu pregunta a un operador automáticamente. También puedes pedirlo tú: escribe "quiero hablar con un operador" o pulsa **🙋 Hablar con un operador**.
5. **Espera en línea.** Mantén la ventana abierta mientras el operador responde. Si tarda, su respuesta aparecerá en el chat la próxima vez que interactúes.
6. **Reseña.** Evalúa la cafetería con estrellas y un comentario desde la barra lateral.
7. **Límite de la conversación.** Después de 15 mensajes verás "Memoria llena". Recarga la página para empezar otra conversación. Lo que ya preguntaste queda registrado.

### 🎧 Operador

1. Abre el panel, pestaña **🚨 Casos pendientes**.
2. La cola se actualiza sola cada 10 segundos. Cuando llega un caso nuevo verás un aviso y escucharás un sonido.
3. Pulsa **🔄 Actualizar lista de casos** para que el caso nuevo aparezca en el selector.
4. Elige el ticket, escribe la respuesta y pulsa **Enviar respuesta y cerrar caso**. La respuesta llega al chat del usuario y el ticket sale de la cola. Si otro operador ya lo atendió, el panel te avisa.

### 🛠️ Administrador

- **📊 Estadísticas:** número de conversaciones, cuántas resolvió el bot, tasa de escalamiento, tiempo medio y percentil 95 de respuesta, y calificaciones 👍/👎, por tipo de usuario.
- **⭐ Reseñas:** reseñas del lugar y calificación promedio.
- **📚 Base de conocimiento:** crear, editar y eliminar entradas. Cada entrada tiene:
  - una respuesta;
  - preguntas de ejemplo (una por línea), que son las que usa la búsqueda semántica;
  - palabras clave de respaldo.
  
  Los cambios se reindexan en segundo plano en unos segundos.
- **⚠️ Errores:** los últimos errores del sistema.
