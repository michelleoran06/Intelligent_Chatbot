"""API del Intelligent Chatbot (capas Edge y Business Logic, Secciones 4.1 y 9).

Flujo de /api/v1/chat:
1. Validación Fail Fast (pydantic + input_validation) -> HTTP 422 / 400.
2. Saludos y agradecimientos cortos se responden directamente.
3. RF10: si el usuario pide un operador, se escala sin consultar al motor de IA.
4. RF02: el motor de IA recupera la respuesta candidata y su confianza S.
5. Strategy: S >= umbral -> BotResponseStrategy; si no -> HumanFallbackStrategy (Observer).
6. RF04: la interacción se registra en la SQL DB y se devuelve la respuesta.
"""
import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import database as db
from input_validation import is_human_request, normalize_text, small_talk_reply, validate_query_text
from knowledge_base import DEFAULT_ENTRIES, KB_SEED_VERSION
from nlp_engine import NLPEngine
from patterns import (
    ROUTED_BOT,
    STATUS_ANSWERED,
    BotResponseStrategy,
    ConversationContext,
    EscalationSubject,
    HumanFallbackStrategy,
    OperatorDashboardNotifier,
    StrategySelector,
)
from vector_store import get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ChatbotAPI")

SERVICE_ERROR_MESSAGE = "Problema técnico interno. Intenta de nuevo en unos minutos."
TOO_LONG_MESSAGE = (
    f"Tu mensaje es muy largo (máximo {config.MAX_QUERY_LENGTH} caracteres). "
    "Por favor, resúmelo un poco e intenta de nuevo."
)
INVALID_REQUEST_MESSAGE = "La petición no es válida: faltan campos obligatorios o tienen un formato incorrecto."

UserType = Literal["estudiante", "maestro", "administrativo"]

# ------------------------------------------------------------------ composición de componentes
escalation_subject = EscalationSubject()
operator_notifier = OperatorDashboardNotifier()
escalation_subject.attach(operator_notifier)

bot_strategy = BotResponseStrategy()
fallback_strategy = HumanFallbackStrategy(escalation_subject)
strategy_selector = StrategySelector(bot_strategy, fallback_strategy, config.CONFIDENCE_THRESHOLD)

nlp_engine = NLPEngine(
    store=get_store(),
    confidence_threshold=config.CONFIDENCE_THRESHOLD,
    divisor=config.CONFIDENCE_DIVISOR,
    keyword_confidence=config.KEYWORD_CONFIDENCE,
    min_keyword_matches=config.MIN_KEYWORD_MATCHES,
    n_results=config.SEMANTIC_RESULTS,
    cache_size=config.NLP_CACHE_SIZE,
)


def _safe_log_error(endpoint: str, message: str) -> None:
    """Registra un error sin dejar que una falla de la base tumbe la respuesta."""
    try:
        db.log_system_error(endpoint, message[:4000])
    except Exception:
        logger.exception("No se pudo registrar el error en la base de datos.")


def load_knowledge_base() -> int:
    summary = db.sync_default_kb(DEFAULT_ENTRIES, KB_SEED_VERSION)
    if summary["previous_version"] != KB_SEED_VERSION:
        logger.info("Base de conocimiento sincronizada a la versión %s (antes: %s). Nuevas: %s | "
                    "actualizadas: %s | eliminadas: %s", KB_SEED_VERSION, summary["previous_version"],
                    summary["inserted"], summary["updated"], summary["removed"])
    entries = db.list_kb_entries()
    nlp_engine.store.rebuild(entries)
    nlp_engine.set_knowledge_base(entries)
    return len(entries)


def refresh_knowledge_base_entry(kb_id: str) -> None:
    """Propagación SQL DB -> Vector DB en segundo plano (consistencia eventual, Sección 4.4)."""
    try:
        entry = db.get_kb_entry(kb_id)
        if entry is None:
            nlp_engine.store.delete_entry(kb_id)
        else:
            nlp_engine.store.upsert_entry(entry)
        nlp_engine.set_knowledge_base(db.list_kb_entries())
        logger.info("Entrada '%s' reindexada.", kb_id)
    except Exception as exc:
        logger.exception("Falló la reindexación de la entrada '%s'.", kb_id)
        _safe_log_error("/api/v1/kb (reindexación)", f"{type(exc).__name__}: {exc}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    total = load_knowledge_base()
    logger.info("Backend listo: %d entradas en la base de conocimiento.", total)
    yield


app = FastAPI(title="Intelligent Chatbot API", version="2.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    too_long = any(
        err.get("type") == "string_too_long" and "query" in tuple(err.get("loc", ()))
        for err in errors
    )
    simplified = [
        {
            "field": ".".join(str(part) for part in err.get("loc", ()) if part != "body"),
            "error": str(err.get("msg", "")),
        }
        for err in errors
    ]
    _safe_log_error(request.url.path, f"Validación: {simplified}")
    return JSONResponse(
        status_code=422,
        content={"detail": TOO_LONG_MESSAGE if too_long else INVALID_REQUEST_MESSAGE, "errors": simplified},
    )


# ------------------------------------------------------------------ modelos de entrada
class QueryPayload(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    user_type: UserType
    query: str = Field(..., min_length=1, max_length=config.MAX_QUERY_LENGTH)
    request_human: bool = False


class ResolvePayload(BaseModel):
    manual_response: str = Field(..., min_length=1, max_length=2000)


class FeedbackPayload(BaseModel):
    helpful: bool


class ReviewPayload(BaseModel):
    user_type: UserType
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=500)


class KnowledgeEntryUpdate(BaseModel):
    category: str = Field(..., min_length=1, max_length=100)
    answer: str = Field(..., min_length=1, max_length=2000)
    questions: List[str] = Field(..., min_length=1)
    keywords: List[str] = Field(default_factory=list)


class KnowledgeEntryCreate(KnowledgeEntryUpdate):
    id: str = Field(..., pattern=r"^[a-z0-9_]{2,50}$")


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Si ADMIN_TOKEN está configurado, exige el encabezado X-Admin-Token."""
    if config.ADMIN_TOKEN and not hmac.compare_digest(x_admin_token or "", config.ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Token de administrador inválido o ausente.")


# ------------------------------------------------------------------ endpoints generales
@app.get("/")
def root():
    return {"service": "Intelligent Chatbot API", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "knowledge_base_entries": len(nlp_engine.entries),
        "confidence_threshold": nlp_engine.confidence_threshold,
        "knowledge_base_version": KB_SEED_VERSION,
        "embedding_model": config.EMBEDDING_MODEL,
        "rejection_examples": config.USE_REJECTION_EXAMPLES,
        "embedding_concurrency": config.EMBEDDING_CONCURRENCY,
        "nlp_cache_size": config.NLP_CACHE_SIZE,
    }


# ------------------------------------------------------------------ chat (RF01, RF02, RF04, RF05, RF10)
@app.post("/api/v1/chat")
def handle_chat(payload: QueryPayload):
    started = time.perf_counter()
    try:
        error_message = validate_query_text(payload.query)
        if error_message:
            raise HTTPException(status_code=400, detail=error_message)

        query = payload.query.strip()
        normalized = normalize_text(query)

        reply = small_talk_reply(normalized)
        if reply:
            return {
                "ticket_id": None,
                "query": query,
                "response": reply,
                "routed_to": ROUTED_BOT,
                "confidence_score": 1.0,
                "status": STATUS_ANSWERED,
                "method": "small_talk",
            }

        requested_human = payload.request_human or is_human_request(normalized)
        if requested_human:
            candidate, confidence, kb_id, method = "", 0.0, None, "user_request"
        else:
            retrieval = nlp_engine.retrieve(query)
            candidate, confidence = retrieval.answer, retrieval.confidence
            kb_id, method = retrieval.kb_id, retrieval.method

        context = ConversationContext(
            user_id=payload.user_id,
            user_type=payload.user_type,
            query=query,
            candidate_answer=candidate,
            confidence=confidence,
            kb_id=kb_id,
            requested_human=requested_human,
        )
        result = strategy_selector.select(confidence, requested_human).resolve(context)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        ticket_id = db.save_log(
            user_id=payload.user_id,
            user_type=payload.user_type,
            query=query,
            response=result.message,
            score=confidence,
            routed_to=result.routed_to,
            method=method,
            kb_id=kb_id,
            response_time_ms=elapsed_ms,
        )
        return {
            "ticket_id": ticket_id,
            "query": query,
            "response": result.message,
            "routed_to": result.routed_to,
            "confidence_score": confidence,
            "status": result.status,
            "method": method,
            "response_time_ms": elapsed_ms,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error crítico en /api/v1/chat")
        _safe_log_error("/api/v1/chat", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=SERVICE_ERROR_MESSAGE)


# ------------------------------------------------------------------ tickets (RF06, RF07, RF09)
@app.get("/api/v1/ticket/{ticket_id}")
def check_ticket(ticket_id: int):
    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="No logramos encontrar tu ticket en el sistema.")
    return ticket


@app.post("/api/v1/ticket/{ticket_id}/resolve")
def resolve_ticket_endpoint(ticket_id: int, payload: ResolvePayload):
    try:
        outcome = db.update_ticket(ticket_id, payload.manual_response.strip())
    except Exception as exc:
        _safe_log_error(f"/api/v1/ticket/{ticket_id}/resolve", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error interno al resolver el ticket.")
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="El ticket no existe.")
    if outcome == "not_pending":
        raise HTTPException(status_code=409, detail="El ticket ya fue atendido o no está escalado.")
    return {"status": "success", "ticket_id": ticket_id}


@app.post("/api/v1/ticket/{ticket_id}/feedback")
def ticket_feedback(ticket_id: int, payload: FeedbackPayload):
    try:
        found = db.save_feedback(ticket_id, payload.helpful)
    except Exception as exc:
        _safe_log_error(f"/api/v1/ticket/{ticket_id}/feedback", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error al guardar la calificación.")
    if not found:
        raise HTTPException(status_code=404, detail="El ticket no existe.")
    return {"status": "success"}


@app.get("/api/v1/tickets/escalated")
def fetch_escalated_tickets():
    return db.get_escalated_tickets()


# ------------------------------------------------------------------ estadísticas y errores (RF08)
@app.get("/api/v1/stats")
def fetch_stats():
    return db.get_user_stats()


@app.get("/api/v1/errors")
def fetch_errors():
    return db.get_system_errors()


# ------------------------------------------------------------------ reseñas del lugar (RF11)
@app.post("/api/v1/reviews")
def add_review(payload: ReviewPayload):
    try:
        review_id = db.save_review(payload.user_type, payload.rating, payload.comment.strip())
    except Exception as exc:
        _safe_log_error("/api/v1/reviews", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error al guardar la reseña.")
    return {"status": "success", "review_id": review_id}


@app.get("/api/v1/reviews")
def fetch_reviews():
    return db.get_reviews()


# ------------------------------------------------------------------ base de conocimiento (RF03)
def _clean_entry_payload(payload: KnowledgeEntryUpdate) -> dict:
    data = payload.model_dump()
    data["questions"] = [q.strip() for q in data["questions"] if q.strip()]
    data["keywords"] = [k.strip() for k in data["keywords"] if k.strip()]
    if not data["questions"]:
        raise HTTPException(status_code=400, detail="La entrada necesita al menos una pregunta de ejemplo.")
    return data


@app.get("/api/v1/kb")
def list_knowledge_base():
    return db.list_kb_entries()


@app.post("/api/v1/kb", status_code=201, dependencies=[Depends(require_admin)])
def create_knowledge_entry(payload: KnowledgeEntryCreate, background_tasks: BackgroundTasks):
    data = _clean_entry_payload(payload)
    try:
        entry = db.create_kb_entry(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background_tasks.add_task(refresh_knowledge_base_entry, entry["id"])
    return entry


@app.put("/api/v1/kb/{kb_id}", dependencies=[Depends(require_admin)])
def update_knowledge_entry(kb_id: str, payload: KnowledgeEntryUpdate, background_tasks: BackgroundTasks):
    entry = db.update_kb_entry(kb_id, _clean_entry_payload(payload))
    if entry is None:
        raise HTTPException(status_code=404, detail="La entrada no existe.")
    background_tasks.add_task(refresh_knowledge_base_entry, kb_id)
    return entry


@app.delete("/api/v1/kb/{kb_id}", dependencies=[Depends(require_admin)])
def delete_knowledge_entry(kb_id: str, background_tasks: BackgroundTasks):
    if not db.delete_kb_entry(kb_id):
        raise HTTPException(status_code=404, detail="La entrada no existe.")
    background_tasks.add_task(refresh_knowledge_base_entry, kb_id)
    return {"status": "success", "id": kb_id}
