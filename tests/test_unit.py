"""Pruebas unitarias (Sección 15.2). No necesitan FastAPI, la base de datos ni ChromaDB.

UT-03 (mensaje demasiado largo) necesita la API y está en test_integration.py.
"""
import pytest

from input_validation import (
    BLANK_MESSAGE,
    GREETING_REPLY,
    MALFORMED_MESSAGE,
    is_human_request,
    normalize_text,
    small_talk_reply,
    validate_query_text,
)
from knowledge_base import DEFAULT_ENTRIES, REJECTION_EXAMPLES
from nlp_engine import NLPEngine
from patterns import (
    STATUS_ANSWERED,
    STATUS_PENDING_HUMAN,
    BotResponseStrategy,
    ConversationContext,
    EscalationEvent,
    EscalationSubject,
    HumanFallbackStrategy,
    Observer,
    StrategySelector,
)
from tests.fakes import FakeVectorStore


def make_engine(rejection_examples=None, **kwargs):
    store = FakeVectorStore(rejection_examples=rejection_examples)
    store.rebuild(DEFAULT_ENTRIES)
    engine = NLPEngine(store=store, **kwargs)
    engine.set_knowledge_base(DEFAULT_ENTRIES)
    return engine, store


class RecordingObserver(Observer):
    def __init__(self):
        self.events = []

    def update(self, event):
        self.events.append(event)


# UT-01: mensaje en blanco
@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
def test_ut01_blank_message(text):
    assert validate_query_text(text) == BLANK_MESSAGE


# UT-02: mensaje repetitivo o sin sentido
@pytest.mark.parametrize("text", ["aaaaaa", "holaaaaaa", "jaskdhasjkdhasd", "?!", "ok"])
def test_ut02_malformed_message(text):
    assert validate_query_text(text) == MALFORMED_MESSAGE


@pytest.mark.parametrize("text", [
    "¿tienen sándwich de pierna?",
    "instrucciones para pagar",
    "construcción",
    "¿Cuánto cuesta?",
    "hola!!!!",
    "¿Hay licuados?",
])
def test_valid_spanish_is_not_blocked(text):
    assert validate_query_text(text) is None


# UT-04: normalización
def test_ut04_normalization():
    assert normalize_text("¿Qué HORARIO tienen?") == "que horario tienen"
    assert normalize_text("  ¡Sándwich,   club!  ") == "sandwich club"


# UT-05, UT-06 y UT-07: puntuación de confianza
@pytest.mark.parametrize("distance, expected", [(0.0, 1.0), (0.75, 0.70), (2.5, 0.0), (4.0, 0.0)])
def test_ut05_07_confidence_score(distance, expected):
    engine, _ = make_engine(divisor=2.5)
    assert engine.score_from_distance(distance) == pytest.approx(expected)


# UT-08: ambas estrategias cumplen el mismo contrato
def test_ut08_strategies_share_contract():
    subject = EscalationSubject()
    context = ConversationContext(user_id="u1", user_type="estudiante", query="q",
                                  candidate_answer="respuesta", confidence=0.9)
    bot = BotResponseStrategy().resolve(context).to_dict()
    human = HumanFallbackStrategy(subject).resolve(context).to_dict()
    assert set(bot) == set(human) == {"routed_to", "message", "status"}
    assert bot["status"] == STATUS_ANSWERED
    assert human["status"] == STATUS_PENDING_HUMAN


# UT-09: Observer
def test_ut09_observer_attach_detach_notify():
    subject = EscalationSubject()
    first, second = RecordingObserver(), RecordingObserver()
    subject.attach(first)
    subject.attach(second)
    subject.attach(first)  # adjuntar dos veces no duplica
    subject.detach(second)
    subject.notify(EscalationEvent(session_id="u1", query="q", reason="prueba", confidence=0.1))
    assert len(first.events) == 1
    assert second.events == []


def test_observer_failure_does_not_break_notify():
    class BrokenObserver(Observer):
        def update(self, event):
            raise RuntimeError("falla")

    subject = EscalationSubject()
    ok_observer = RecordingObserver()
    subject.attach(BrokenObserver())
    subject.attach(ok_observer)
    subject.notify(EscalationEvent(session_id="u1", query="q", reason="prueba", confidence=0.1))
    assert len(ok_observer.events) == 1


# UT-10: decisión con el umbral
def test_ut10_threshold_decision():
    bot, fallback = BotResponseStrategy(), HumanFallbackStrategy(EscalationSubject())
    selector = StrategySelector(bot, fallback, threshold=0.70)
    assert selector.select(0.70) is bot
    assert selector.select(0.69) is fallback
    assert selector.select(0.99, requested_human=True) is fallback


# Motor de IA
def test_semantic_exact_question_is_answered():
    engine, _ = make_engine()
    result = engine.retrieve("¿A qué hora abren la cafetería?")
    assert result.kb_id == "horarios"
    assert result.method == "semantic"
    assert result.confidence >= 0.70


def test_keyword_fallback_needs_two_matches():
    engine, _ = make_engine()
    assert engine.keyword_match(normalize_text("la API de pagos no me responde"))[0] is None
    assert engine.keyword_match(normalize_text("donde tramito mi credencial"))[0] is None
    assert engine.keyword_match(normalize_text("a que hora abren"))[0] == "horarios"
    assert engine.keyword_match(normalize_text("que trae el menu del dia"))[0] == "menu_del_dia"


def test_out_of_scope_is_not_answered():
    engine, _ = make_engine()
    result = engine.retrieve("¿Cuál es la capital de Francia?")
    assert result.confidence < 0.70


def test_cache_avoids_repeated_queries():
    engine, store = make_engine()
    engine.retrieve("¿Venden pizza?")
    calls = store.calls
    engine.retrieve("venden PIZZA")  # misma consulta una vez normalizada
    assert store.calls == calls


def test_errors_are_raised_and_not_cached():
    engine, store = make_engine()
    store.fail = True
    with pytest.raises(RuntimeError):
        engine.retrieve("¿Tienen postres?")
    store.fail = False
    assert engine.retrieve("¿Tienen postres?").kb_id == "postres"


def test_knowledge_base_reload_clears_cache():
    engine, store = make_engine()
    engine.retrieve("¿Venden pizza?")
    reduced = [e for e in DEFAULT_ENTRIES if e["id"] != "pizzas"]
    store.rebuild(reduced)
    engine.set_knowledge_base(reduced)
    assert engine.retrieve("¿Venden pizza?").kb_id != "pizzas"


# Mensajes cortos y RF10
def test_small_talk():
    assert small_talk_reply(normalize_text("¡Hola!")) == GREETING_REPLY
    assert small_talk_reply(normalize_text("buenas tardes")) == GREETING_REPLY
    assert small_talk_reply(normalize_text("hola, ¿a qué hora abren?")) is None
    assert small_talk_reply(normalize_text("muchas gracias")) is not None


@pytest.mark.parametrize("text, expected", [
    ("Quiero hablar con un operador", True),
    ("¿me pasas con un humano?", True),
    ("necesito hablar con una persona", True),
    ("¿a qué hora abren?", False),
])
def test_human_request_detection(text, expected):
    assert is_human_request(normalize_text(text)) is expected


# Ejemplos de rechazo
def test_rejection_examples_force_escalation():
    engine, _ = make_engine(rejection_examples=REJECTION_EXAMPLES)
    result = engine.retrieve("¿Cómo hago mi servicio social?")
    assert result.method == "rejected"
    assert result.confidence == 0.0
    assert result.kb_id is None


def test_rejection_does_not_block_cafeteria_questions():
    engine, _ = make_engine(rejection_examples=REJECTION_EXAMPLES)
    result = engine.retrieve("¿Cuánto cuesta la torta de carnitas?")
    assert result.kb_id == "carnitas"
    assert result.confidence >= 0.70


def test_rejection_examples_do_not_count_as_candidates():
    engine, _ = make_engine(rejection_examples=REJECTION_EXAMPLES)
    result = engine.retrieve("¿Cuánto cuesta la pizza?")
    assert "__fuera_de_alcance__" not in result.candidates


# Base de conocimiento v2
def test_knowledge_base_ids_are_unique_and_complete():
    ids = [entry["id"] for entry in DEFAULT_ENTRIES]
    assert len(ids) == len(set(ids))
    for entry in DEFAULT_ENTRIES:
        assert entry["answer"].strip() and entry["questions"] and entry["category"].strip()


def test_carnitas_keywords_do_not_steal_antojitos():
    engine, _ = make_engine()
    assert engine.keyword_match(normalize_text("tacos de carnitas"))[0] == "carnitas"
    assert engine.keyword_match(normalize_text("tacos dorados"))[0] == "antojitos"
