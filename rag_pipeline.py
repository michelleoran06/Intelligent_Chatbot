"""Decisión de la Fase 3 (RAG con Gemini), sin dependencias de FastAPI.

La usan main.py (/api/v1/chat) y evaluate_rag.py (revalidación), así lo que se mide es exactamente lo
que corre en producción.

Orden (E-027):
1. Gemini disponible: una sola llamada con las entradas recuperadas y los últimos turnos de la sesión.
   Gemini clasifica el mensaje: "responder" ("llm"), "aclarar" ("clarify"), "fuera_de_tema"
   ("out_of_scope") o "escalar" ("human"). Solo "human" crea ticket.
2. Gemini no configurado o sin respuesta de ninguna key: regla anterior. Ejemplos de rechazo o
   S < OUT_OF_SCOPE_CONFIDENCE = "out_of_scope"; S >= umbral = "retrieval"; si no, "human".
"""
import logging
from dataclasses import dataclass
from typing import Optional, Sequence

from llm_client import TIPO_ACLARAR, TIPO_ESCALAR, TIPO_FUERA_DE_TEMA, LLMAnswer, LLMUnavailable
from nlp_engine import NLPEngine, RetrievalResult

logger = logging.getLogger("RAG")

ROUTE_LLM = "llm"
ROUTE_RETRIEVAL = "retrieval"
ROUTE_OUT_OF_SCOPE = "out_of_scope"
ROUTE_CLARIFY = "clarify"
ROUTE_HUMAN = "human"

_ROUTE_BY_TIPO = {TIPO_ACLARAR: ROUTE_CLARIFY, TIPO_FUERA_DE_TEMA: ROUTE_OUT_OF_SCOPE, TIPO_ESCALAR: ROUTE_HUMAN}


@dataclass(frozen=True)
class Decision:
    route: str
    answered: bool                 # True si el bot resolvió la pregunta (llm o retrieval con S >= umbral)
    kb_id: Optional[str]           # entrada usada para responder
    llm_answer: Optional[LLMAnswer] = None


def decide(query: str, normalized: str, retrieval: RetrievalResult, engine: NLPEngine, llm,
           out_of_scope_confidence: float, context_k: int, history: Sequence[dict] = ()) -> Decision:
    entries = engine.entries
    context_entries = [entries[i] for i in engine.context_ids(retrieval, context_k) if i in entries]
    if llm is not None and llm.available and context_entries:
        try:
            answer = llm.answer(query, normalized, context_entries, history)
        except LLMUnavailable:
            logger.warning("Gemini no respondió; se usa la recuperación sin Gemini.")
        else:
            route = _ROUTE_BY_TIPO.get(answer.tipo)
            if route is not None:
                return Decision(route, False, None, answer)
            return Decision(ROUTE_LLM, True, answer.source_id, answer)

    # Respaldo sin Gemini (regla de M3)
    if retrieval.method == "rejected" or (
        retrieval.method != "none" and retrieval.confidence < out_of_scope_confidence
    ):
        return Decision(ROUTE_OUT_OF_SCOPE, False, None)
    if retrieval.confidence >= engine.confidence_threshold:
        return Decision(ROUTE_RETRIEVAL, True, retrieval.kb_id)
    return Decision(ROUTE_HUMAN, False, None)
