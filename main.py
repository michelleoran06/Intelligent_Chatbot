import logging
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from database import save_log, update_ticket, get_ticket
from vector_store import seed_knowledge_base
from patterns import EscalationSubject, OperatorDashboardNotifier, BotResponseStrategy, HumanFallbackStrategy
from nlp_engine import NLPEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ChatbotAPI")

app = FastAPI(title="Intelligent Chatbot API", version="1.0.0")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Parece que tu mensaje es muy largo o tiene caracteres no válidos. Por favor, resúmelo un poco e intenta de nuevo."}
    )

escalation_subject = EscalationSubject()
escalation_subject.attach(OperatorDashboardNotifier())

bot_strategy = BotResponseStrategy()
fallback_strategy = HumanFallbackStrategy(escalation_subject)
nlp_engine = NLPEngine(confidence_threshold=0.70)

class QueryPayload(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    query: str = Field(..., min_length=2, max_length=500)

class ResolvePayload(BaseModel):
    manual_response: str = Field(..., min_length=1)

@app.on_event("startup")
def startup_event():
    seed_knowledge_base()

@app.post("/api/v1/chat", status_code=status.HTTP_200_OK)
def handle_chat(payload: QueryPayload):
    try:
        user_query = payload.query.strip()
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tu mensaje está en blanco. Por favor, escribe una pregunta."
            )

        context, confidence = nlp_engine.retrieve_and_score(user_query)

        if confidence < 0.25:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tu consulta no parece estar relacionada con los servicios de la cafetería de la facultad. Intenta preguntarlo de otra forma."
            )

        if confidence >= nlp_engine.confidence_threshold:
            strategy = bot_strategy
        else:
            strategy = fallback_strategy

        result = strategy.generate_response(user_query, context)

        ticket_id = save_log(
            user_id=payload.user_id,
            query=user_query,
            response=result["message"],
            score=confidence,
            routed_to=result["routed_to"]
        )

        return {
            "ticket_id": ticket_id,
            "query": user_query,
            "response": result["message"],
            "routed_to": result["routed_to"],
            "confidence_score": confidence,
            "status": result["status"]
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error critico: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tuvimos un pequeño problema técnico de nuestro lado. Por favor, intenta de nuevo en unos minutos."
        )

@app.get("/api/v1/ticket/{ticket_id}")
def check_ticket(ticket_id: int):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=404, 
            detail="No logramos encontrar tu ticket en el sistema."
        )
    return ticket

@app.post("/api/v1/ticket/{ticket_id}/resolve")
def resolve_ticket_endpoint(ticket_id: int, payload: ResolvePayload):
    update_ticket(ticket_id, payload.manual_response)
    return {"status": "success"}