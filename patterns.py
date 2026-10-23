"""Patrones de diseño del sistema (Business Logic Layer, Secciones 3.2 y 3.3).

- Strategy: ResponseStrategy.resolve(context) -> ResponseResult, con BotResponseStrategy y
  HumanFallbackStrategy. StrategySelector aplica la regla única S >= umbral.
- Observer: EscalationSubject notifica a los observadores (OperatorDashboardNotifier) cada vez
  que una conversación se escala. El panel de operador además consulta la cola de tickets por
  HTTP, así un operador desconectado nunca bloquea una notificación (Sección 6).
"""
import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Deque, List, Optional

logger = logging.getLogger("Patterns")

ROUTED_BOT = "bot"
ROUTED_HUMAN = "human"
ROUTED_HUMAN_RESOLVED = "human_resolved"

STATUS_ANSWERED = "answered"
STATUS_PENDING_HUMAN = "pending_human"
STATUS_RESOLVED_BY_HUMAN = "resolved_by_human"

ESCALATION_MESSAGE = "Tu pregunta fue enviada a un operador. Por favor espera la respuesta."
LOW_CONFIDENCE_PREFIX = "No encontré una respuesta segura a tu pregunta. "


@dataclass(frozen=True)
class ConversationContext:
    user_id: str
    user_type: str
    query: str
    candidate_answer: str = ""
    confidence: float = 0.0
    kb_id: Optional[str] = None
    requested_human: bool = False


@dataclass(frozen=True)
class ResponseResult:
    routed_to: str
    message: str
    status: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EscalationEvent:
    session_id: str
    query: str
    reason: str
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ------------------------------------------------------------------------------ Observer
class Observer(ABC):
    @abstractmethod
    def update(self, event: EscalationEvent) -> None:
        pass


class OperatorDashboardNotifier(Observer):
    """Registra cada escalamiento y conserva los más recientes para el panel de operador."""

    def __init__(self, max_events: int = 100):
        self.recent_events: Deque[EscalationEvent] = deque(maxlen=max_events)
        self.total_notifications = 0

    def update(self, event: EscalationEvent) -> None:
        self.recent_events.append(event)
        self.total_notifications += 1
        logger.info("Caso escalado para operadores (%s) | usuario=%s | S=%.4f",
                    event.reason, event.session_id, event.confidence)


class EscalationSubject:
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: EscalationEvent) -> None:
        for observer in list(self._observers):
            try:
                observer.update(event)
            except Exception:  # un observador con fallas no debe tumbar el chat
                logger.exception("Un observador falló al recibir la notificación.")


# ------------------------------------------------------------------------------ Strategy
class ResponseStrategy(ABC):
    @abstractmethod
    def resolve(self, context: ConversationContext) -> ResponseResult:
        pass


class BotResponseStrategy(ResponseStrategy):
    """Devuelve la respuesta guardada en la entrada más cercana de la base de conocimiento."""

    def resolve(self, context: ConversationContext) -> ResponseResult:
        return ResponseResult(routed_to=ROUTED_BOT, message=context.candidate_answer, status=STATUS_ANSWERED)


class HumanFallbackStrategy(ResponseStrategy):
    """Escala la conversación a un operador mediante el mecanismo Observer."""

    def __init__(self, escalation_subject: EscalationSubject):
        self.escalation_subject = escalation_subject

    def resolve(self, context: ConversationContext) -> ResponseResult:
        if context.requested_human:
            reason = "Solicitud del usuario (RF10)"
            message = ESCALATION_MESSAGE
        else:
            reason = "Confianza baja (RF05)"
            message = LOW_CONFIDENCE_PREFIX + ESCALATION_MESSAGE
        self.escalation_subject.notify(EscalationEvent(
            session_id=context.user_id,
            query=context.query,
            reason=reason,
            confidence=context.confidence,
        ))
        return ResponseResult(routed_to=ROUTED_HUMAN, message=message, status=STATUS_PENDING_HUMAN)


class StrategySelector:
    """Regla única de decisión: bot si S >= umbral y el usuario no pidió un operador."""

    def __init__(self, bot: ResponseStrategy, fallback: ResponseStrategy, threshold: float):
        self.bot = bot
        self.fallback = fallback
        self.threshold = threshold

    def select(self, confidence: float, requested_human: bool = False) -> ResponseStrategy:
        if requested_human or confidence < self.threshold:
            return self.fallback
        return self.bot
