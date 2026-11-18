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

# ------------------------------------------------------------------ entorno y secretos (Fase 1 M4)
# "development" (por defecto) o "production". En producción el backend no arranca si faltan secretos.
ENV = os.getenv("ENV", "development").strip().lower() or "development"
IS_PRODUCTION = ENV == "production"

# Gemini (Fase 3). La segunda key es opcional: se usa como respaldo cuando exista.
GEMINI_API_KEY_1 = os.getenv("GEMINI_API_KEY_1", "").strip()
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()
# Fase 3: timeout por llamada (s), respuestas guardadas en memoria y presupuesto de "thinking"
# (vacío = el valor por defecto del modelo; 0 lo apaga en los modelos Flash que lo permiten)
# La API de Gemini rechaza (400) cualquier timeout menor a 10 s (E-026)
GEMINI_TIMEOUT_SECONDS = _get_float("GEMINI_TIMEOUT_SECONDS", 15.0)
LLM_CACHE_SIZE = _get_int("LLM_CACHE_SIZE", 256)
_thinking = os.getenv("GEMINI_THINKING_BUDGET", "").strip()
GEMINI_THINKING_BUDGET = int(_thinking) if _thinking.lstrip("-").isdigit() else None
# Entradas de la base de conocimiento que recibe Gemini como contexto (top-k de ChromaDB)
LLM_CONTEXT_ENTRIES = _get_int("LLM_CONTEXT_ENTRIES", 3)
# Fuera de dominio claro: si la mejor confianza S es menor que este valor, se responde que solo se
# atienden temas de la cafetería (sin Gemini y sin escalar). 0 = solo se usan los ejemplos de rechazo.
OUT_OF_SCOPE_CONFIDENCE = _get_float("OUT_OF_SCOPE_CONFIDENCE", 0.0)

# Autenticación del operador (Fase 2): hash bcrypt de la contraseña y clave para firmar tokens
OPERATOR_PASSWORD_HASH = os.getenv("OPERATOR_PASSWORD_HASH", "").strip()
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "").strip()

# Orígenes permitidos para CORS, separados por comas (Fase 2)
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]

# Sesión del operador (Fase 2): duración del token, bloqueo por IP y largo mínimo de la contraseña
TOKEN_TTL_HOURS = _get_float("TOKEN_TTL_HOURS", 8.0)
LOGIN_MAX_FAILURES = _get_int("LOGIN_MAX_FAILURES", 5)
LOGIN_LOCK_MINUTES = _get_int("LOGIN_LOCK_MINUTES", 15)
MIN_PASSWORD_LENGTH = 12
MIN_SECRET_KEY_LENGTH = 32

# Límites de peticiones por IP (formato de slowapi/limits). Para pruebas de carga locales se pueden subir.
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20/minute")
RATE_LIMIT_LOGIN = os.getenv("RATE_LIMIT_LOGIN", "5/minute")
RATE_LIMIT_REVIEWS = os.getenv("RATE_LIMIT_REVIEWS", "5/minute")

# Detrás del proxy de Render todas las peticiones llegan desde la misma IP interna. TRUSTED_PROXY_HOPS dice
# cuántos proxies de confianza agregan su entrada al final de X-Forwarded-For; la IP del cliente es la que
# queda justo antes de ellos. Los valores de la izquierda los puede inventar el cliente, así que no se usan.
# 0 (por defecto) = no se confía en X-Forwarded-For y se usa la IP de la conexión.
TRUSTED_PROXY_HOPS = max(0, _get_int("TRUSTED_PROXY_HOPS", 0))

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


def invalid_secret_vars(environ=None) -> list:
    """Secretos presentes pero con formato inseguro (solo en producción). Nunca devuelve valores."""
    environ = os.environ if environ is None else environ
    if (environ.get("ENV") or "development").strip().lower() != "production":
        return []
    invalid = []
    password_hash = (environ.get("OPERATOR_PASSWORD_HASH") or "").strip()
    if password_hash and not (password_hash.startswith("$2") and len(password_hash) == 60):
        invalid.append("OPERATOR_PASSWORD_HASH (no parece un hash bcrypt; genéralo con scripts/hash_password.py)")
    secret_key = (environ.get("AUTH_SECRET_KEY") or "").strip()
    if secret_key and len(secret_key) < MIN_SECRET_KEY_LENGTH:
        invalid.append(f"AUTH_SECRET_KEY (debe tener al menos {MIN_SECRET_KEY_LENGTH} caracteres)")
    return invalid


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
    invalid = invalid_secret_vars(environ)
    if invalid:
        raise ConfigError("ENV=production y hay secretos con formato inseguro: " + "; ".join(invalid) + ".")
