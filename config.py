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
EMBEDDING_BATCH_SIZE = _get_int("EMBEDDING_BATCH_SIZE", 16)
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

# ------------------------------------------------------------------ entorno y secretos (Fase 1 M4)
# "development" (por defecto) o "production". En producción el backend no arranca si faltan secretos.
ENV = os.getenv("ENV", "development").strip().lower() or "development"

# Gemini (Fase 3). La segunda key es opcional: se usa como respaldo cuando exista.
GEMINI_API_KEY_1 = os.getenv("GEMINI_API_KEY_1", "").strip()
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()

# Autenticación del operador (Fase 2): hash bcrypt de la contraseña y clave para firmar tokens
OPERATOR_PASSWORD_HASH = os.getenv("OPERATOR_PASSWORD_HASH", "").strip()
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "").strip()

# Orígenes permitidos para CORS, separados por comas (Fase 2)
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]

# Variables sin las cuales el backend no debe arrancar en producción (fail-closed).
# Gemini no está aquí: si falla o no está configurado, el bot sigue respondiendo con el flujo actual.
PRODUCTION_REQUIRED_VARS = ("OPERATOR_PASSWORD_HASH", "AUTH_SECRET_KEY", "ALLOWED_ORIGINS")


class ConfigError(RuntimeError):
    """La configuración no permite arrancar el backend de forma segura."""


def missing_required_vars(environ=None) -> list:
    """Nombres de las variables obligatorias que faltan. Solo aplica cuando ENV=production."""
    environ = os.environ if environ is None else environ
    if (environ.get("ENV") or "development").strip().lower() != "production":
        return []
    return [name for name in PRODUCTION_REQUIRED_VARS if not (environ.get(name) or "").strip()]


def validate_config(environ=None) -> None:
    """Fail-closed: en producción, si falta un secreto obligatorio se detiene el arranque.

    El mensaje solo nombra las variables faltantes; nunca muestra valores.
    """
    missing = missing_required_vars(environ)
    if missing:
        raise ConfigError(
            "ENV=production y faltan variables obligatorias: " + ", ".join(missing)
            + ". Configúralas en el entorno (Render) antes de arrancar el backend."
        )
