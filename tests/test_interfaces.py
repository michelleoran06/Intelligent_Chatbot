"""Pruebas de las interfaces de Streamlit contra el backend real (Fase 2 M4, PR B).

Las llamadas de `requests` de dashboard.py y frontend.py se redirigen al TestClient de FastAPI, así
que se prueba el flujo completo: login del panel, token en cada petición, regreso al login ante un
401 y tickets del chat por public_id + user_id.
"""
import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
app_test = pytest.importorskip("streamlit.testing.v1").AppTest

import requests  # noqa: E402

import database as db  # noqa: E402
import security  # noqa: E402
from tests.conftest import TEST_PASSWORD  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FAKE_BACKEND = "http://backend.prueba"


@pytest.fixture
def backend(client, monkeypatch):
    """Redirige requests.get/post/request al backend en memoria y registra cada llamada."""
    calls = []

    def route(method, url, json=None, params=None, headers=None, timeout=None):
        assert url.startswith(FAKE_BACKEND), url
        path = url[len(FAKE_BACKEND):]
        calls.append({"method": method.upper(), "path": path, "headers": dict(headers or {}), "json": json})
        return client.request(method.upper(), path, json=json, params=params, headers=headers or {})

    monkeypatch.setenv("BACKEND_URL", FAKE_BACKEND)
    monkeypatch.setattr(requests, "request", route)
    monkeypatch.setattr(requests, "get", lambda url, **kw: route("GET", url, **kw))
    monkeypatch.setattr(requests, "post", lambda url, **kw: route("POST", url, **kw))
    return calls


def dashboard():
    at = app_test.from_file(str(ROOT / "dashboard.py"), default_timeout=30)
    at.run()
    return at


def login(at, password):
    at.text_input[0].input(password)
    at.button[0].click().run()  # botón "Entrar" del formulario
    return at


def page_text(at) -> str:
    return " ".join(str(e.value) for e in list(at.markdown) + list(at.error) + list(at.warning)
                    + list(at.success) + list(at.info))


# ------------------------------------------------------------------ dashboard.py (E-003)
def test_panel_sin_sesion_solo_muestra_login(backend):
    at = dashboard()
    assert len(at.tabs) == 0
    assert at.text_input[0].label == "Contraseña del operador"
    assert at.text_input[0].proto.type == 1  # TextInput.Type.PASSWORD: no se ve al escribir
    assert all(call["path"] == "/api/v1/auth/login" for call in backend)  # ningún dato del operador


def test_panel_contrasena_incorrecta(backend):
    at = login(dashboard(), "contrasena-equivocada")
    assert "Credenciales inválidas." in [e.value for e in at.error]
    assert len(at.tabs) == 0
    assert "auth_token" not in at.session_state


def test_panel_login_correcto_manda_el_token(backend):
    at = login(dashboard(), TEST_PASSWORD)
    assert not at.exception
    assert len(at.tabs) == 6
    assert security.token_is_valid(at.session_state["auth_token"])
    protected = [c for c in backend if c["path"] != "/api/v1/auth/login"]
    assert protected, "el panel debió consultar la cola"
    assert all(c["headers"].get("Authorization") == f"Bearer {at.session_state['auth_token']}" for c in protected)
    # el formulario de login desaparece y ningún campo conserva la contraseña
    assert all(w.value != TEST_PASSWORD for w in at.text_input)


def test_panel_token_invalido_regresa_al_login(backend):
    at = app_test.from_file(str(ROOT / "dashboard.py"), default_timeout=30)
    at.session_state["auth_token"] = "token.alterado.invalido"
    at.run()
    assert len(at.tabs) == 0
    assert "auth_token" not in at.session_state
    assert any("sesión expiró" in w.value for w in at.warning)


def test_panel_cerrar_sesion(backend):
    at = login(dashboard(), TEST_PASSWORD)
    next(b for b in at.button if b.label == "🚪 Cerrar sesión").click().run()
    assert len(at.tabs) == 0 and "auth_token" not in at.session_state


def test_panel_resuelve_ticket_con_token(backend, client, monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    public_id = client.post("/api/v1/chat", json={"user_id": "estudiante_abc123def456", "user_type": "estudiante",
                                                  "query": "¿Cuál es la capital de Francia?"}).json()["ticket_id"]
    at = login(dashboard(), TEST_PASSWORD)
    at.text_area[0].input("No es un tema de la cafetería.")
    next(b for b in at.button if b.label == "Enviar respuesta y cerrar caso").click().run()
    assert not at.exception
    resolve = next(c for c in backend if c["path"].endswith("/resolve"))
    assert resolve["headers"]["Authorization"].startswith("Bearer ")
    ticket = client.get(f"/api/v1/ticket/{public_id}", params={"user_id": "estudiante_abc123def456"}).json()
    assert ticket["routed_to"] == "human_resolved"


# ------------------------------------------------------------------ frontend.py (E-005, E-010, E-018)
def chat_app():
    at = app_test.from_file(str(ROOT / "frontend.py"), default_timeout=30)
    at.run()
    return at


def test_chat_user_id_aleatorio_de_12_caracteres(backend):
    at = chat_app()
    at.chat_input[0].set_value("¿A qué hora abren la cafetería?").run()
    sent = next(c for c in backend if c["path"] == "/api/v1/chat")
    assert re.fullmatch(r"estudiante_[0-9a-f]{12}", sent["json"]["user_id"])


def test_chat_ticket_escalado_queda_pendiente_con_su_dueno(backend, monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)  # la espera del operador no detiene la prueba
    at = chat_app()
    at.chat_input[0].set_value("¿Cuál es la capital de Francia?").run()
    pending = at.session_state["pending_tickets"]
    assert len(pending) == 1
    ticket_id, user_id = pending[0]["ticket_id"], pending[0]["user_id"]
    assert re.fullmatch(r"[0-9a-f-]{36}", ticket_id)  # UUID, no el id numérico
    polls = [c for c in backend if c["path"].startswith("/api/v1/ticket/")]
    assert polls and all(c["path"] == f"/api/v1/ticket/{ticket_id}" for c in polls)
    # el operador responde y el chat lo muestra al revisar
    with db.session_scope() as session:
        internal = session.query(db.ConversationLog).filter_by(public_id=ticket_id).one().id
    db.update_ticket(internal, "París, pero aquí solo vemos temas de la cafetería.")
    at.run()  # la barra lateral ya muestra el aviso de respuesta pendiente
    next(b for b in at.button if b.label == "🔄 Revisar respuesta del operador").click().run()
    assert at.session_state["pending_tickets"] == []
    assert any("París" in m.value for m in at.markdown)
    assert user_id.startswith("estudiante_")


def test_chat_feedback_usa_public_id_y_user_id_de_la_sesion(backend, client):
    at = chat_app()
    at.chat_input[0].set_value("¿A qué hora abren la cafetería?").run()
    message = next(m for m in at.session_state["messages"] if m.get("allow_feedback"))
    assert re.fullmatch(r"[0-9a-f-]{36}", message["ticket_id"])
    # lo mismo que manda send_feedback al pulsar 👍: el backend lo acepta solo con el user_id de la sesión
    vote = {"user_id": message["user_id"], "helpful": True}
    assert client.post(f"/api/v1/ticket/{message['ticket_id']}/feedback", json=vote).status_code == 200
    vote["user_id"] = "estudiante_otrapersona1"
    assert client.post(f"/api/v1/ticket/{message['ticket_id']}/feedback", json=vote).status_code == 404
