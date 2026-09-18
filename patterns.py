from abc import ABC, abstractmethod
from typing import List

class Observer(ABC):
    @abstractmethod
    def update(self, session_id: str, query: str, reason: str):
        pass

class OperatorDashboardNotifier(Observer):
    def update(self, session_id: str, query: str, reason: str):
        pass

class EscalationSubject:
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer):
        self._observers.remove(observer)

    def notify(self, session_id: str, query: str, reason: str):
        for observer in self._observers:
            observer.update(session_id, query, reason)

class ResponseStrategy(ABC):
    @abstractmethod
    def generate_response(self, query: str, context: str) -> dict:
        pass

class BotResponseStrategy(ResponseStrategy):
    def generate_response(self, query: str, context: str) -> dict:
        return {
            "routed_to": "bot",
            "message": context,
            "status": "resolved"
        }

class HumanFallbackStrategy(ResponseStrategy):
    def __init__(self, escalation_subject: EscalationSubject):
        self.escalation_subject = escalation_subject

    def generate_response(self, query: str, context: str) -> dict:
        self.escalation_subject.notify(
            session_id="session_active",
            query=query,
            reason="Low confidence score"
        )
        return {
            "routed_to": "human",
            "message": "Hmm, parece que no tengo la respuesta exacta a eso. 😅 No te preocupes, te estoy transfiriendo con un humano para que te ayude mejor.",
            "status": "escalated"
        }