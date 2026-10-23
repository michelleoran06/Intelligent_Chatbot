"""Validación Fail Fast y normalización de texto (capa Edge, Secciones 3.1 y 10).

Es lógica pura, sin dependencias de FastAPI, para poder probarla de forma aislada.
"""
import re
import unicodedata
from typing import Optional

BLANK_MESSAGE = "Tu mensaje está en blanco. Por favor, escribe una pregunta."
MALFORMED_MESSAGE = "¡Ups! Tu mensaje parece estar mal escrito o incompleto. ¿Podrías escribirlo de nuevo?"
GREETING_REPLY = (
    "¡Hola! 👋 Soy el asistente de la cafetería de la Facultad de Ingeniería. "
    "Pregúntame sobre el menú, los precios, los horarios, la ubicación o los métodos de pago."
)
THANKS_REPLY = "¡Con gusto! Si tienes otra duda sobre la cafetería, aquí estoy. ☕"

_MIN_LETTERS = 3
# 5 o más veces la misma letra seguida ("holaaaaa", "aaaaaa")
_REPEATED_LETTER = re.compile(r"([a-z])\1{4,}")
# 5 o más consonantes seguidas. En español el grupo más largo es de 4 ("nstr" en "instrucciones"),
# y la "y" no se cuenta porque funciona como vocal ("hay", "muy").
_CONSONANT_RUN = re.compile(r"[bcdfghjklmnpqrstvwxz]{5,}")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")

_GREETING_CORE = {"hola", "ola", "hey", "saludos", "buenos", "buenas", "buen", "tal"}
_GREETING_WORDS = _GREETING_CORE | {"dias", "dia", "tardes", "noches", "que", "como", "estas", "esta"}
_THANKS_WORDS = {"gracias", "muchas", "mil", "ok", "okay", "vale", "perfecto", "excelente",
                 "muy", "amable", "bien", "listo", "genial"}

_HUMAN_REQUEST = re.compile(
    r"\b(operador|operadora|humano|humana|asesor|asesora|agente)\b"
    r"|persona real|hablar con (alguien|una persona)"
)


def normalize_text(text: str) -> str:
    """Minúsculas, sin acentos, sin puntuación y sin espacios repetidos."""
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = text.encode("ascii", "ignore").decode("ascii")
    text = _NON_ALNUM.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def validate_query_text(raw_query: Optional[str]) -> Optional[str]:
    """Devuelve el mensaje de error para el usuario, o None si la consulta es válida."""
    if raw_query is None or not raw_query.strip():
        return BLANK_MESSAGE
    normalized = normalize_text(raw_query)
    letters = re.sub(r"[^a-z]", "", normalized)
    if len(letters) < _MIN_LETTERS:
        return MALFORMED_MESSAGE
    if _REPEATED_LETTER.search(normalized) or _CONSONANT_RUN.search(normalized):
        return MALFORMED_MESSAGE
    return None


def small_talk_reply(normalized_query: str) -> Optional[str]:
    """Respuesta directa para saludos y agradecimientos cortos; None si no aplica."""
    tokens = normalized_query.split()
    if not tokens or len(tokens) > 4:
        return None
    token_set = set(tokens)
    if token_set <= _GREETING_WORDS and token_set & _GREETING_CORE:
        return GREETING_REPLY
    if token_set <= _THANKS_WORDS and "gracias" in token_set:
        return THANKS_REPLY
    return None


def is_human_request(normalized_query: str) -> bool:
    """RF10: detecta cuando el usuario pide explícitamente hablar con una persona."""
    return bool(_HUMAN_REQUEST.search(normalized_query))
