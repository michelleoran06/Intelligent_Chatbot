"""Configuración central del Intelligent Chatbot.

Todos los valores se pueden sobrescribir con variables de entorno, así el mismo código
corre en local, en Docker y en Render sin editar archivos (Sección 18.2).
"""
import os


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Decisión bot / humano (Secciones 8 y 16): S = 1 - d / CONFIDENCE_DIVISOR; responde si S >= umbral
# Calibrados en la Fase 2 (configuración C, confirmada con evaluation/validation_set.csv)
CONFIDENCE_THRESHOLD = _get_float("CONFIDENCE_THRESHOLD", 0.75)
CONFIDENCE_DIVISOR = _get_float("CONFIDENCE_DIVISOR", 2.0)

# Respaldo por palabras clave: solo se usa si la búsqueda semántica no alcanza el umbral
KEYWORD_CONFIDENCE = _get_float("KEYWORD_CONFIDENCE", 0.75)
MIN_KEYWORD_MATCHES = _get_int("MIN_KEYWORD_MATCHES", 2)

SEMANTIC_RESULTS = _get_int("SEMANTIC_RESULTS", 20)
# Calibrados en la Fase 3 (Plan B): 2 embeddings a la vez y 200 hilos para que las respuestas en caché no esperen turno
EMBEDDING_CONCURRENCY = _get_int("EMBEDDING_CONCURRENCY", 2)
SERVER_THREADS = _get_int("SERVER_THREADS", 200)
NLP_CACHE_SIZE = _get_int("NLP_CACHE_SIZE", 256)

MAX_QUERY_LENGTH = _get_int("MAX_QUERY_LENGTH", 500)

DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DATA_DIR}/chatbot_audit.db"
CHROMA_PATH = os.getenv("CHROMA_PATH") or f"{DATA_DIR}/chroma_data"
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "knowledge_base_cafe")

# Modelo de embeddings: "default" = all-MiniLM-L6-v2 (ONNX, incluido en chromadb).
# Cualquier otro valor es un modelo de sentence-transformers (requirements-experiment.txt).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "default").strip() or "default"
# Ejemplos de rechazo (knowledge_base.REJECTION_EXAMPLES): escalan preguntas de otros temas
USE_REJECTION_EXAMPLES = os.getenv("USE_REJECTION_EXAMPLES", "true").strip().lower() in ("1", "true", "yes", "si", "sí")

# Si se define, los endpoints que modifican la base de conocimiento exigen el encabezado X-Admin-Token
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
