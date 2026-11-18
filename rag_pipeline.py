"""Decisión de la Fase 3 (RAG con Gemini), sin dependencias de FastAPI.

La usan main.py (/api/v1/chat) y evaluate_rag.py (revalidación), así lo que se mide es exactamente lo
que corre en producción.

Orden:
1. Pregunta claramente de otro tema (ejemplos de rechazo o S < OUT_OF_SCOPE_CONFIDENCE): "out_of_scope".
2. Gemini disponible: responde con las entradas recuperadas ("llm") o NO_SE ("human").
3. Gemini no configurado o sin respuesta de ninguna key: regla anterior S >= umbral ("retrieval"/"human").
"""
import logging
from dataclasses import dataclass
from typing import Optional

from llm_client import LLMAnswer, LLMUnavailable
from nlp_engine import NLPEngine, RetrievalResult

logger = logging.getLogger("RAG")

ROUTE_LLM = "llm"
ROUTE_RETRIEVAL = "retrieval"
ROUTE_OUT_OF_SCOPE = "out_of_scope"
ROUTE_HUMAN = "human"


@dataclass(frozen=True)
class Decision:
    route: str
    answered: bool                 # True si el bot responde la pregunta (llm o retrieval con S >= umbral)
    kb_id: Optional[str]           # entrada usada para responder
    llm_answer: Optional[LLMAnswer] = None


def decide(query: str, normalized: str, retrieval: RetrievalResult, engine: NLPEngine, llm,
           out_of_scope_confidence: float, context_k: int) -> Decision:
    if retrieval.method == "rejected" or (
        retrieval.method != "none" and retrieval.confidence < out_of_scope_confidence
    ):
        return Decision(ROUTE_OUT_OF_SCOPE, False, None)

    entries = engine.entries
    context_entries = [entries[i] for i in engine.context_ids(retrieval, context_k) if i in entries]
    if llm is not None and llm.available and context_entries:
        try:
            answer = llm.answer(query, normalized, context_entries)
        except LLMUnavailable:
            logger.warning("Gemini no respondió; se usa la recuperación sin Gemini.")
        else:
            if answer.is_no_se:
                return Decision(ROUTE_HUMAN, False, None, answer)
            return Decision(ROUTE_LLM, True, answer.source_id, answer)

    if retrieval.confidence >= engine.confidence_threshold:
        return Decision(ROUTE_RETRIEVAL, True, retrieval.kb_id)
    return Decision(ROUTE_HUMAN, False, None)
