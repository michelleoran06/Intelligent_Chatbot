"""API del Intelligent Chatbot (capas Edge y Business Logic, Secciones 4.1 y 9).

Flujo de /api/v1/chat:
1. Validación Fail Fast (pydantic + input_validation) -> HTTP 422 / 400.
2. Saludos y agradecimientos cortos se responden directamente.
3. RF10: si el usuario pide un operador, se escala sin consultar al motor de IA.
4. RF02: el motor de IA recupera la respuesta candidata y su confianza S.
5. Strategy: S >= umbral -> BotResponseStrategy; si no -> HumanFallbackStrategy (Observer).
6. RF04: la interacción se registra en la SQL DB y se devuelve la respuesta.

Seguridad (Fase 2 M4): los endpoints del operador exigen un token (security.require_operator), el usuario
solo ve el public_id (UUID) de sus tickets, hay límite de peticiones por IP (slowapi), CORS restringido,
encabezados de seguridad y /docs apagado en producción.
"""
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
import time
from contextlib import asynccontextmanager
import uuid
from typing import List, Literal

from anyio import to_thread
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

import config
import database as db
from input_validation import is_human_request, normalize_text, small_talk_reply, validate_query_text
from knowledge_base import DEFAULT_ENTRIES, KB_SEED_VERSION
from nlp_engine import NLPEngine
import security
import llm_client
import rag_pipeline
from patterns import (
    ROUTED_BOT,
    STATUS_ANSWERED,
    BotResponseStrategy,
    ClarifyStrategy,
    ConversationContext,
    EscalationSubject,
    HumanFallbackStrategy,
    LLMResponseStrategy,
    OperatorDashboardNotifier,
    OutOfScopeStrategy,
    StrategySelector,
)
from vector_store import get_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Fail-closed (Fase 1): en producción no se arranca sin los secretos obligatorios
config.validate_config()
logger = logging.getLogger("ChatbotAPI")

SERVICE_ERROR_MESSAGE = "Problema técnico interno. Intenta de nuevo en unos minutos."
TOO_LONG_MESSAGE = (
    f"Tu mensaje es muy largo (máximo {config.MAX_QUERY_LENGTH} caracteres). "
    "Por favor, resúmelo un poco e intenta de nuevo."
)
INVALID_REQUEST_MESSAGE = "La petición no es válida: faltan campos obligatorios o tienen un formato incorrecto."
RATE_LIMIT_MESSAGE = "Estás enviando demasiadas solicitudes. Espera un minuto y vuelve a intentarlo, por favor."
LOGIN_LOCKED_MESSAGE = "Demasiados intentos fallidos. Espera unos minutos antes de volver a intentarlo."
TICKET_NOT_FOUND_MESSAGE = "No logramos encontrar tu ticket en el sistema."

UserType = Literal["estudiante", "maestro", "administrativo"]

# ------------------------------------------------------------------ composición de componentes
escalation_subject = EscalationSubject()
operator_notifier = OperatorDashboardNotifier()
escalation_subject.attach(operator_notifier)

bot_strategy = BotResponseStrategy()
fallback_strategy = HumanFallbackStrategy(escalation_subject)
strategy_selector = StrategySelector(bot_strategy, fallback_strategy, config.CONFIDENCE_THRESHOLD)
llm_strategy = LLMResponseStrategy()
out_of_scope_strategy = OutOfScopeStrategy()
clarify_strategy = ClarifyStrategy(max_in_a_row=config.CLARIFY_MAX_IN_A_ROW)

# Fase 3: Gemini con dos keys y failover. Sin keys o sin modelo, el chat usa solo la recuperación.
llm = llm_client.from_config()

nlp_engine = NLPEngine(
    store=get_store(),
    confidence_threshold=config.CONFIDENCE_THRESHOLD,
    divisor=config.CONFIDENCE_DIVISOR,
    keyword_confidence=config.KEYWORD_CONFIDENCE,
    min_keyword_matches=config.MIN_KEYWORD_MATCHES,
    n_results=config.SEMANTIC_RESULTS,
    cache_size=config.NLP_CACHE_SIZE,
)


def peak_memory_mb():
    """Memoria máxima usada por el proceso (MB), o None si el sistema no lo informa (Windows)."""
    try:
        import resource
        import sys

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024, 1)
    except (ImportError, AttributeError, ValueError):
        return None


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
    # Fase 3 (Plan B): tamaño del grupo de hilos que atiende los endpoints síncronos
    to_thread.current_default_thread_limiter().total_tokens = max(1, config.SERVER_THREADS)
    total = load_knowledge_base()
    logger.info("Backend listo: %d entradas en la base de conocimiento. Memoria pico del arranque: %s MB.",
                total, peak_memory_mb())
    yield


# E-013: en producción no se publica la documentación interactiva ni el esquema OpenAPI
app = FastAPI(
    title="Intelligent Chatbot API",
    version="2.1.0",
    lifespan=lifespan,
    docs_url=None if config.IS_PRODUCTION else "/docs",
    redoc_url=None if config.IS_PRODUCTION else "/redoc",
    openapi_url=None if config.IS_PRODUCTION else "/openapi.json",
)

# Rate limiting por IP (slowapi). La IP sale de security.client_ip (respeta TRUSTED_PROXY_HOPS en Render).
limiter = Limiter(key_func=security.client_ip)
app.state.limiter = limiter

# E-013: CORS solo para los orígenes de ALLOWED_ORIGINS (vacío = ningún origen externo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """E-013: encabezados de seguridad en todas las respuestas."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    if not request.url.path.startswith(_DOCS_PATHS):  # Swagger (solo en desarrollo) necesita cargar su JS
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if config.IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, _exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": RATE_LIMIT_MESSAGE})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Un 500 nunca devuelve el stack trace ni detalles internos; el detalle queda en el log del servidor."""
    logger.exception("Error no controlado en %s", request.url.path)
    _safe_log_error(request.url.path, f"{type(exc).__name__}: {exc}")
    return JSONResponse(status_code=500, content={"detail": SERVICE_ERROR_MESSAGE})


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
# user_id de la sesión del chat: solo letras, números, guion y guion bajo
USER_ID_PATTERN = r"^[A-Za-z0-9_-]{1,50}$"


class QueryPayload(BaseModel):
    user_id: str = Field(..., pattern=USER_ID_PATTERN)
    user_type: UserType
    query: str = Field(..., min_length=1, max_length=config.MAX_QUERY_LENGTH)
    request_human: bool = False


class ResolvePayload(BaseModel):
    manual_response: str = Field(..., min_length=1, max_length=2000)


class FeedbackPayload(BaseModel):
    user_id: str = Field(..., pattern=USER_ID_PATTERN)
    helpful: bool


class LoginPayload(BaseModel):
    password: str = Field(..., max_length=256)


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


OPERATOR = [Depends(security.require_operator)]


def _audit(action: str, target, request: Request) -> None:
    """Bitácora de acciones del operador. Si falla, no tumba la operación."""
    try:
        db.log_operator_action(action, None if target is None else str(target), security.client_ip(request))
    except Exception:
        logger.exception("No se pudo registrar la acción del operador.")


def _valid_public_id(public_id: str) -> bool:
    try:
        return str(uuid.UUID(public_id)) == public_id.lower()
    except (ValueError, AttributeError):
        return False


# ------------------------------------------------------------------ endpoints generales
@app.get("/")
def root():
    return {"service": "Intelligent Chatbot API", "health": "/health"}


@app.get("/health")
def health():
    """E-011: público y mínimo; el detalle de configuración está en /api/v1/system (operador)."""
    return {"status": "ok"}


@app.get("/api/v1/system", dependencies=OPERATOR)
def system_details(request: Request):
    return {
        "status": "ok",
        # Para verificar TRUSTED_PROXY_HOPS en Render: debe coincidir con la IP pública de quien consulta
        "ip_detectada": security.client_ip(request),
        "x_forwarded_for_entradas": len([h for h in request.headers.get("x-forwarded-for", "").split(",")
                                         if h.strip()]),
        "knowledge_base_entries": len(nlp_engine.entries),
        "confidence_threshold": nlp_engine.confidence_threshold,
        "knowledge_base_version": KB_SEED_VERSION,
        "embedding_model": config.EMBEDDING_MODEL,
        "llm_configured": llm.available,
        "llm_model": config.GEMINI_MODEL or None,
        "llm_keys": llm.key_count,
        "rejection_examples": config.USE_REJECTION_EXAMPLES,
        "embedding_concurrency": config.EMBEDDING_CONCURRENCY,
        "nlp_cache_size": config.NLP_CACHE_SIZE,
        "server_threads": max(1, config.SERVER_THREADS),
        "peak_memory_mb": peak_memory_mb(),
    }


# ------------------------------------------------------------------ chat (RF01, RF02, RF04, RF05, RF10)
# ------------------------------------------------------------------ login del operador (Fase 2)
@app.post("/api/v1/auth/login")
@limiter.limit(lambda: config.RATE_LIMIT_LOGIN)
def login(request: Request, payload: LoginPayload):
    ip = security.client_ip(request)
    if db.login_locked_until(ip):
        _audit("login_bloqueado", None, request)
        raise HTTPException(status_code=429, detail=LOGIN_LOCKED_MESSAGE)
    # Fail-closed: sin hash o sin clave configurados, ningún login es válido
    if security.auth_configured() and security.verify_password(payload.password, config.OPERATOR_PASSWORD_HASH):
        db.clear_login_failures(ip)
        _audit("login_ok", None, request)
        return {"access_token": security.create_token(), "token_type": "bearer",
                "expires_in": int(config.TOKEN_TTL_HOURS * 3600)}
    locked = db.register_login_failure(ip, config.LOGIN_MAX_FAILURES, config.LOGIN_LOCK_MINUTES)
    _audit("login_fallido", None, request)
    if locked:
        raise HTTPException(status_code=429, detail=LOGIN_LOCKED_MESSAGE)
    raise HTTPException(status_code=401, detail=security.INVALID_CREDENTIALS)


@app.get("/api/v1/auth/check", dependencies=OPERATOR)
def check_session():
    return {"status": "ok"}


def _decide(query: str, normalized: str, retrieval, history=()):
    """Fase 3 (rag_pipeline.decide): devuelve (estrategia, ruta, respuesta de Gemini o None)."""
    decision = rag_pipeline.decide(query, normalized, retrieval, nlp_engine, llm,
                                   config.OUT_OF_SCOPE_CONFIDENCE, config.LLM_CONTEXT_ENTRIES, history)
    strategy = {
        rag_pipeline.ROUTE_OUT_OF_SCOPE: out_of_scope_strategy,
        rag_pipeline.ROUTE_CLARIFY: clarify_strategy,
        rag_pipeline.ROUTE_LLM: llm_strategy,
        rag_pipeline.ROUTE_RETRIEVAL: bot_strategy,
        rag_pipeline.ROUTE_HUMAN: fallback_strategy,
    }[decision.route]
    return strategy, decision.route, decision.llm_answer


@app.post("/api/v1/chat")
@limiter.limit(lambda: config.RATE_LIMIT_CHAT)
def handle_chat(request: Request, payload: QueryPayload):
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
        llm_answer = None
        streak = 0
        if requested_human:
            candidate, confidence, kb_id, method = "", 0.0, None, "user_request"
            strategy, route = fallback_strategy, "human"
        else:
            # E-027: últimos turnos de esta sesión (de la base, no del navegador) para entender seguimientos
            history = db.get_recent_turns(payload.user_id, config.LLM_HISTORY_TURNS, config.LLM_HISTORY_MINUTES)
            streak = db.clarify_streak(history)
            retrieval = nlp_engine.retrieve(query, previous=history[-1]["user"] if history else None)
            candidate, confidence = retrieval.answer, retrieval.confidence
            kb_id, method = retrieval.kb_id, retrieval.method
            strategy, route, llm_answer = _decide(query, normalized, retrieval, history)
            if llm_answer is not None:
                method = {"responder": "llm", "aclarar": "llm_clarify", "fuera_de_tema": "llm_out_of_scope",
                          "escalar": "llm_no_se"}.get(llm_answer.tipo, "llm")
                candidate = llm_answer.text
                kb_id = llm_answer.source_id

        context = ConversationContext(
            user_id=payload.user_id,
            user_type=payload.user_type,
            query=query,
            candidate_answer=candidate,
            confidence=confidence,
            kb_id=kb_id,
            requested_human=requested_human,
            clarify_streak=streak,
        )
        result = strategy.resolve(context)
        if result.routed_to != ROUTED_BOT:
            route = "human"

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        public_id = db.new_public_id()
        db.save_log(
            public_id=public_id,
            user_id=payload.user_id,
            user_type=payload.user_type,
            query=query,
            response=result.message,
            score=confidence,
            routed_to=result.routed_to,
            method=method,
            kb_id=kb_id,
            response_time_ms=elapsed_ms,
            route=route,
            llm_key=llm_answer.key_label if llm_answer else None,
            llm_latency_ms=llm_answer.latency_ms if llm_answer and not llm_answer.cached else None,
        )
        return {
            "ticket_id": public_id,  # el usuario solo conoce el public_id, nunca el id interno
            "query": query,
            "response": result.message,
            "routed_to": result.routed_to,
            "confidence_score": confidence,
            "status": result.status,
            "method": method,
            "route": route,
            "response_time_ms": elapsed_ms,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error crítico en /api/v1/chat")
        _safe_log_error("/api/v1/chat", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail=SERVICE_ERROR_MESSAGE)


# ------------------------------------------------------------------ tickets (RF06, RF07, RF09)
@app.get("/api/v1/ticket/{public_id}")
def check_ticket(public_id: str, user_id: str = ""):
    """IDOR: se consulta por public_id (UUID) y solo si el user_id de la sesión es el dueño."""
    ticket = db.get_ticket(public_id, user_id) if _valid_public_id(public_id) and user_id else None
    if not ticket:
        raise HTTPException(status_code=404, detail=TICKET_NOT_FOUND_MESSAGE)
    return ticket


@app.post("/api/v1/ticket/{ticket_id}/resolve", dependencies=OPERATOR)
def resolve_ticket_endpoint(ticket_id: int, payload: ResolvePayload, request: Request):
    try:
        outcome = db.update_ticket(ticket_id, payload.manual_response.strip())
    except Exception as exc:
        _safe_log_error(f"/api/v1/ticket/{ticket_id}/resolve", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error interno al resolver el ticket.")
    if outcome == "not_found":
        raise HTTPException(status_code=404, detail="El ticket no existe.")
    if outcome == "not_pending":
        raise HTTPException(status_code=409, detail="El ticket ya fue atendido o no está escalado.")
    _audit("resolver_ticket", ticket_id, request)
    return {"status": "success", "ticket_id": ticket_id}


@app.post("/api/v1/ticket/{public_id}/feedback")
def ticket_feedback(public_id: str, payload: FeedbackPayload):
    """E-010: solo el dueño del ticket (mismo user_id) puede calificarlo."""
    if not _valid_public_id(public_id):
        raise HTTPException(status_code=404, detail="El ticket no existe.")
    try:
        found = db.save_feedback(public_id, payload.user_id, payload.helpful)
    except Exception as exc:
        _safe_log_error("/api/v1/ticket/{public_id}/feedback", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error al guardar la calificación.")
    if not found:
        raise HTTPException(status_code=404, detail="El ticket no existe.")
    return {"status": "success"}


@app.get("/api/v1/tickets/escalated", dependencies=OPERATOR)
def fetch_escalated_tickets():
    return db.get_escalated_tickets()


# ------------------------------------------------------------------ estadísticas y errores (RF08)
@app.get("/api/v1/stats", dependencies=OPERATOR)
def fetch_stats():
    return db.get_user_stats()


@app.get("/api/v1/errors", dependencies=OPERATOR)
def fetch_errors():
    return db.get_system_errors()


@app.get("/api/v1/operator-actions", dependencies=OPERATOR)
def fetch_operator_actions():
    return db.get_operator_actions()


# ------------------------------------------------------------------ reseñas del lugar (RF11)
@app.post("/api/v1/reviews")
@limiter.limit(lambda: config.RATE_LIMIT_REVIEWS)
def add_review(request: Request, payload: ReviewPayload):
    try:
        review_id = db.save_review(payload.user_type, payload.rating, payload.comment.strip())
    except Exception as exc:
        _safe_log_error("/api/v1/reviews", f"{type(exc).__name__}: {exc}")
        raise HTTPException(status_code=500, detail="Error al guardar la reseña.")
    return {"status": "success", "review_id": review_id}


@app.get("/api/v1/conversations", dependencies=OPERATOR)
def export_conversations(request: Request, since: str = ""):
    """Exporta en CSV las conversaciones desde `since` (ISO 8601; con zona, p. ej. 2026-11-18T18:30-06:00).

    Solo para el operador. Sin `since`, las de las últimas 24 horas."""
    try:
        start = datetime.fromisoformat(since) if since else datetime.now(timezone.utc) - timedelta(hours=24)
    except ValueError:
        raise HTTPException(status_code=422, detail="since debe ser una fecha ISO, p. ej. 2026-11-18T18:30-06:00")
    if start.tzinfo is not None:
        start = start.astimezone(timezone.utc).replace(tzinfo=None)
    rows = db.export_conversations(start)
    _audit("export_conversations", since or "24h", request)
    buffer = io.StringIO()
    fields = ["hora_utc", "sesion", "tipo_usuario", "pregunta", "respuesta", "ruta", "metodo", "enviado_a", "ticket"]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return Response(content="\ufeff" + buffer.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="conversaciones.csv"'})


@app.get("/api/v1/reviews", dependencies=OPERATOR)
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


@app.get("/api/v1/kb", dependencies=OPERATOR)
def list_knowledge_base():
    return db.list_kb_entries()


@app.post("/api/v1/kb", status_code=201, dependencies=OPERATOR)
def create_knowledge_entry(payload: KnowledgeEntryCreate, background_tasks: BackgroundTasks, request: Request):
    data = _clean_entry_payload(payload)
    try:
        entry = db.create_kb_entry(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background_tasks.add_task(refresh_knowledge_base_entry, entry["id"])
    _audit("kb_crear", entry["id"], request)
    return entry


@app.put("/api/v1/kb/{kb_id}", dependencies=OPERATOR)
def update_knowledge_entry(kb_id: str, payload: KnowledgeEntryUpdate, background_tasks: BackgroundTasks,
                           request: Request):
    entry = db.update_kb_entry(kb_id, _clean_entry_payload(payload))
    if entry is None:
        raise HTTPException(status_code=404, detail="La entrada no existe.")
    background_tasks.add_task(refresh_knowledge_base_entry, kb_id)
    _audit("kb_editar", kb_id, request)
    return entry


@app.delete("/api/v1/kb/{kb_id}", dependencies=OPERATOR)
def delete_knowledge_entry(kb_id: str, background_tasks: BackgroundTasks, request: Request):
    if not db.delete_kb_entry(kb_id):
        raise HTTPException(status_code=404, detail="La entrada no existe.")
    background_tasks.add_task(refresh_knowledge_base_entry, kb_id)
    _audit("kb_borrar", kb_id, request)
    return {"status": "success", "id": kb_id}
