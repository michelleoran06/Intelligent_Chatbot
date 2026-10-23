"""Pruebas de integración (Sección 15.3): API + motor de IA + SQLite.

Usan un vector store falso (tests/fakes.py) para no depender del modelo de embeddings.
La integración con ChromaDB real está en test_chroma.py.
"""
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

import database as db  # noqa: E402
import main  # noqa: E402
from input_validation import BLANK_MESSAGE, MALFORMED_MESSAGE  # noqa: E402
from tests.conftest import ADMIN_HEADERS, FAKE_STORE  # noqa: E402


def ask(client, query, user_type="estudiante", **extra):
    return client.post("/api/v1/chat", json={"user_id": "tester_1", "user_type": user_type, "query": query, **extra})


# IT-01: pregunta que existe en la base de conocimiento
def test_it01_known_question_is_answered(client):
    res = ask(client, "¿A qué hora abren la cafetería?")
    assert res.status_code == 200
    body = res.json()
    assert body["routed_to"] == "bot"
    assert body["status"] == "answered"
    assert body["confidence_score"] >= 0.70
    assert "7:00" in body["response"]
    assert body["ticket_id"] is not None


# IT-02: pregunta fuera de la base de conocimiento
def test_it02_unknown_question_is_escalated(client):
    res = ask(client, "¿Cuál es la capital de Francia?")
    body = res.json()
    assert res.status_code == 200
    assert body["status"] == "pending_human"
    assert body["routed_to"] == "human"
    queue = client.get("/api/v1/tickets/escalated").json()
    assert body["ticket_id"] in [t["id"] for t in queue]


# IT-03: cada interacción queda registrada
def test_it03_interactions_are_logged(client):
    ask(client, "¿Venden pizza?", user_type="maestro")
    ask(client, "¿Cuándo son los exámenes finales?", user_type="administrativo")
    with db.session_scope() as session:
        rows = session.query(db.ConversationLog).order_by(db.ConversationLog.id).all()
        assert len(rows) == 2
        assert {r.routed_to for r in rows} == {"bot", "human"}
        assert all(r.user_id and r.query and r.response and r.response_time_ms is not None for r in rows)
        assert rows[0].user_type == "maestro"


# IT-04: el operador responde un ticket
def test_it04_operator_resolves_ticket(client):
    ticket_id = ask(client, "¿Puedo reservar mesas para un evento?").json()["ticket_id"]
    res = client.post(f"/api/v1/ticket/{ticket_id}/resolve", json={"manual_response": "Sí, pregunta en caja."})
    assert res.status_code == 200
    assert ticket_id not in [t["id"] for t in client.get("/api/v1/tickets/escalated").json()]
    ticket = client.get(f"/api/v1/ticket/{ticket_id}").json()
    assert ticket["routed_to"] == "human_resolved"
    assert ticket["response"] == "Sí, pregunta en caja."
    # resolverlo otra vez o resolver uno inexistente no debe decir "success"
    assert client.post(f"/api/v1/ticket/{ticket_id}/resolve", json={"manual_response": "x"}).status_code == 409
    assert client.post("/api/v1/ticket/999999/resolve", json={"manual_response": "x"}).status_code == 404


# IT-05: el chat muestra "servicio no disponible" si el backend no responde
def test_it05_frontend_shows_service_unavailable(monkeypatch):
    app_test = pytest.importorskip("streamlit.testing.v1").AppTest
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9")  # puerto sin servidor
    frontend = Path(__file__).resolve().parent.parent / "frontend.py"
    at = app_test.from_file(str(frontend), default_timeout=20)
    at.run()
    at.chat_input[0].set_value("¿A qué hora abren?").run()
    texts = " ".join(m.value for m in at.markdown)
    assert "no está disponible" in texts


# IT-06: reseñas del lugar
def test_it06_place_review(client):
    res = client.post("/api/v1/reviews", json={"user_type": "maestro", "rating": 4, "comment": "Muy rico"})
    assert res.status_code == 200
    reviews = client.get("/api/v1/reviews").json()
    assert reviews[0]["rating"] == 4 and reviews[0]["comment"] == "Muy rico"
    bad = client.post("/api/v1/reviews", json={"user_type": "maestro", "rating": 9})
    assert bad.status_code == 422


# UT-03: mensaje demasiado largo -> 422 y el motor de IA no se llama
def test_ut03_too_long_message(client, monkeypatch):
    def fail_if_called(_query):
        raise AssertionError("El motor de IA no debió ejecutarse")

    monkeypatch.setattr(main.nlp_engine, "retrieve", fail_if_called)
    res = ask(client, "a" * 501)
    assert res.status_code == 422
    assert "muy largo" in res.json()["detail"]


# Fail Fast (400) y petición malformada (422 estructurado)
def test_blank_and_malformed_return_400(client):
    assert ask(client, "     ").json()["detail"] == BLANK_MESSAGE
    res = ask(client, "jaskdhasjkdhasd")
    assert res.status_code == 400
    assert res.json()["detail"] == MALFORMED_MESSAGE


def test_missing_field_returns_structured_422(client):
    res = client.post("/api/v1/chat", json={"query": "hola"})
    assert res.status_code == 422
    fields = [e["field"] for e in res.json()["errors"]]
    assert "user_id" in fields and "user_type" in fields


def test_greeting_does_not_create_ticket(client):
    body = ask(client, "¡Hola!").json()
    assert body["ticket_id"] is None and body["status"] == "answered"


# RF10: el usuario pide un operador
def test_rf10_user_requests_operator(client):
    body = ask(client, "¿Venden pizza?", request_human=True).json()
    assert body["status"] == "pending_human"
    body = ask(client, "Quiero hablar con un operador").json()
    assert body["status"] == "pending_human"


# RF09: calificación de una respuesta
def test_rf09_response_feedback(client):
    ticket_id = ask(client, "¿Tienen postres?").json()["ticket_id"]
    assert client.post(f"/api/v1/ticket/{ticket_id}/feedback", json={"helpful": True}).status_code == 200
    assert client.post("/api/v1/ticket/999999/feedback", json={"helpful": False}).status_code == 404
    overall = client.get("/api/v1/stats").json()["overall"]
    assert overall["positive_feedback"] == 1


# RF08: estadísticas
def test_rf08_stats(client):
    ask(client, "¿Venden pizza?")
    ask(client, "¿Cuál es la capital de Francia?")
    stats = client.get("/api/v1/stats").json()
    assert stats["overall"]["total"] == 2
    assert stats["overall"]["escalation_rate"] == 0.5
    assert stats["by_user_type"][0]["user_type"] == "estudiante"


# Error 500 controlado
def test_internal_error_returns_friendly_500(client):
    FAKE_STORE.fail = True
    res = ask(client, "¿Tienen jugos naturales de naranja?")
    assert res.status_code == 500
    assert "Intenta de nuevo" in res.json()["detail"]
    errors = client.get("/api/v1/errors").json()
    assert any(e["endpoint"] == "/api/v1/chat" for e in errors)


# RF03: gestión de la base de conocimiento
def test_rf03_knowledge_base_crud(client):
    entry = {
        "id": "wifi_cafeteria",
        "category": "Servicios",
        "answer": "La cafetería no cuenta con wifi propio.",
        "questions": ["¿Tienen wifi en la cafetería?"],
        "keywords": ["wifi", "internet"],
    }
    assert client.post("/api/v1/kb", json=entry).status_code == 401  # sin token
    assert client.post("/api/v1/kb", json=entry, headers=ADMIN_HEADERS).status_code == 201
    assert client.post("/api/v1/kb", json=entry, headers=ADMIN_HEADERS).status_code == 409

    body = ask(client, "¿Tienen wifi en la cafetería?").json()
    assert body["status"] == "answered" and "wifi" in body["response"]

    update = {**entry, "answer": "Sí, la red de la facultad llega a la cafetería."}
    update.pop("id")
    assert client.put("/api/v1/kb/wifi_cafeteria", json=update, headers=ADMIN_HEADERS).status_code == 200
    main.nlp_engine.clear_cache()
    assert "red de la facultad" in ask(client, "¿Tienen wifi en la cafetería?").json()["response"]

    assert client.delete("/api/v1/kb/wifi_cafeteria", headers=ADMIN_HEADERS).status_code == 200
    assert client.delete("/api/v1/kb/wifi_cafeteria", headers=ADMIN_HEADERS).status_code == 404
    assert ask(client, "¿Tienen wifi en la cafetería?").json()["status"] == "pending_human"


# Sincronización de la base de conocimiento cuando cambia KB_SEED_VERSION
def test_kb_seed_version_sync(client):
    from knowledge_base import KB_SEED_VERSION

    original = db.get_kb_entry("bebidas")
    db.update_kb_entry("bebidas", {**original, "answer": "Texto viejo de la versión anterior."})
    db.set_metadata("kb_seed_version", "version-anterior")
    db.set_metadata("kb_seed_ids", '["bebidas", "producto_descontinuado"]')
    db.create_kb_entry({"id": "producto_descontinuado", "category": "X", "answer": "x", "questions": ["x"]})
    db.create_kb_entry({"id": "creada_por_admin", "category": "Y", "answer": "y", "questions": ["y"]})

    main.load_knowledge_base()

    assert db.get_kb_entry("bebidas")["answer"] == original["answer"]   # restaurada
    assert db.get_kb_entry("producto_descontinuado") is None            # ya no es predeterminada
    assert db.get_kb_entry("creada_por_admin") is not None              # del administrador: se respeta
    assert db.get_metadata("kb_seed_version") == KB_SEED_VERSION
    db.delete_kb_entry("creada_por_admin")
    main.load_knowledge_base()


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["knowledge_base_entries"] >= 14
    assert body["knowledge_base_version"]
