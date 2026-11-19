"""Pruebas de seguridad de la Fase 2 (M4): login, tokens, bloqueo, rate limit, IDOR y endurecimiento.

Cada prueba corresponde a un hallazgo de BITACORA_ERRORES.md (E-003, E-004, E-010 a E-013, E-017 a E-020).
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import config  # noqa: E402
import database as db  # noqa: E402
import main  # noqa: E402
import security  # noqa: E402
from tests.conftest import TEST_PASSWORD, operator_headers  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGIN = "/api/v1/auth/login"

PROTECTED = [
    ("get", "/api/v1/tickets/escalated"),
    ("get", "/api/v1/stats"),
    ("get", "/api/v1/errors"),
    ("get", "/api/v1/reviews"),
    ("get", "/api/v1/kb"),
    ("get", "/api/v1/system"),
    ("get", "/api/v1/operator-actions"),
    ("get", "/api/v1/auth/check"),
    ("post", "/api/v1/ticket/1/resolve"),
    ("post", "/api/v1/kb"),
    ("put", "/api/v1/kb/horarios"),
    ("delete", "/api/v1/kb/horarios"),
]


def login(client, password=TEST_PASSWORD):
    return client.post(LOGIN, json={"password": password})


def chat(client, query, user_id="duenia_1"):
    return client.post("/api/v1/chat", json={"user_id": user_id, "user_type": "estudiante", "query": query})


# ------------------------------------------------------------------ login (2.1)
def test_login_correcto_devuelve_token_de_8_horas(client):
    res = login(client)
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 8 * 3600
    payload = jwt.decode(body["access_token"], config.AUTH_SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == "operator"
    assert payload["exp"] - payload["iat"] == 8 * 3600
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    assert client.get("/api/v1/stats", headers=headers).status_code == 200


def test_login_incorrecto_mensaje_generico(client):
    wrong = login(client, "otra-contrasena-larga-999")
    short = login(client, "corta")
    assert wrong.status_code == short.status_code == 401
    assert wrong.json() == short.json() == {"detail": "Credenciales inválidas."}


def test_contrasena_de_11_caracteres_no_entra_aunque_coincida_el_hash(client, monkeypatch):
    once = "abcdefghijk"  # 11 caracteres
    monkeypatch.setattr(config, "OPERATOR_PASSWORD_HASH",
                        __import__("bcrypt").hashpw(once.encode(), __import__("bcrypt").gensalt(4)).decode())
    assert login(client, once).status_code == 401


@pytest.mark.parametrize("missing", ["OPERATOR_PASSWORD_HASH", "AUTH_SECRET_KEY"])
def test_login_fail_closed_sin_configuracion(client, monkeypatch, missing):
    monkeypatch.setattr(config, missing, "")
    assert login(client).status_code == 401


def test_bloqueo_tras_5_intentos_fallidos(client):
    for _ in range(4):
        assert login(client, "contrasena-equivocada").status_code == 401
    blocked = login(client, "contrasena-equivocada")
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == main.LOGIN_LOCKED_MESSAGE
    main.limiter.reset()  # descarta el rate limit para comprobar que el bloqueo es del servidor
    still = login(client)  # ni con la contraseña correcta
    assert still.status_code == 429 and still.json()["detail"] == main.LOGIN_LOCKED_MESSAGE
    with db.session_scope() as session:  # el bloqueo vive en la base, no en session_state
        assert session.get(db.LoginAttempt, "testclient").locked_until is not None


def test_bloqueo_vence_a_los_15_minutos(client):
    for _ in range(5):
        login(client, "contrasena-equivocada")
    main.limiter.reset()
    with db.session_scope() as session:
        attempt = session.get(db.LoginAttempt, "testclient")
        assert attempt.locked_until - attempt.last_failure == timedelta(minutes=15)
        attempt.locked_until = db.utcnow() - timedelta(seconds=1)
    assert login(client).status_code == 200


def test_fallos_viejos_no_cuentan():
    ip = "203.0.113.7"
    start = db.utcnow()
    for _ in range(4):
        assert db.register_login_failure(ip, 5, 15, now=start) is False
    # 20 minutos después, el contador empieza de nuevo
    assert db.register_login_failure(ip, 5, 15, now=start + timedelta(minutes=20)) is False
    db.clear_login_failures(ip)


# ------------------------------------------------------------------ require_operator (2.2, E-003, E-004, E-012)
@pytest.mark.parametrize("method,path", PROTECTED)
def test_endpoints_del_operador_sin_token_401(client, method, path):
    res = client.request(method.upper(), path, json={})
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_token_expirado_401(client):
    old = security.create_token(now=datetime.now(timezone.utc) - timedelta(hours=9))
    assert client.get("/api/v1/stats", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_token_alterado_401(client):
    token = security.create_token()
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}{'AA' if signature[-2:] != 'AA' else 'BB'}"
    assert client.get("/api/v1/stats", headers={"Authorization": f"Bearer {tampered}"}).status_code == 401


def test_token_firmado_con_otra_clave_401(client):
    now = datetime.now(timezone.utc)
    forged = jwt.encode({"sub": "operator", "iat": now, "exp": now + timedelta(hours=1)},
                        "otra-clave-que-no-es-la-del-servidor-0000", algorithm="HS256")
    assert client.get("/api/v1/stats", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_sin_firma_alg_none_401(client):
    now = datetime.now(timezone.utc)
    unsigned = jwt.encode({"sub": "operator", "iat": now, "exp": now + timedelta(hours=1)}, None, algorithm="none")
    assert client.get("/api/v1/stats", headers={"Authorization": f"Bearer {unsigned}"}).status_code == 401


def test_admin_token_viejo_ya_no_sirve(client):
    # E-004: el encabezado X-Admin-Token (fail-open si estaba vacío) ya no da acceso
    assert client.get("/api/v1/kb", headers={"X-Admin-Token": ""}).status_code == 401


def test_publico_sigue_abierto(client):
    assert client.post("/api/v1/reviews", json={"user_type": "maestro", "rating": 5}).status_code == 200
    assert chat(client, "¿A qué hora abren la cafetería?").status_code == 200
    assert client.get("/health").status_code == 200


# ------------------------------------------------------------------ IDOR y E-010 (2.4)
def test_public_id_es_uuid_y_no_el_id_interno(client):
    public_id = chat(client, "¿Cuál es la capital de Francia?").json()["ticket_id"]
    assert main._valid_public_id(public_id)


def test_ids_secuenciales_ya_no_funcionan(client):
    chat(client, "¿Cuál es la capital de Francia?")
    with db.session_scope() as session:
        internal = session.query(db.ConversationLog).one().id
    assert client.get(f"/api/v1/ticket/{internal}", params={"user_id": "duenia_1"}).status_code == 404
    res = client.post(f"/api/v1/ticket/{internal}/feedback", json={"user_id": "duenia_1", "helpful": False})
    assert res.status_code == 404


def test_ticket_ajeno_no_se_consulta_ni_se_califica(client):
    public_id = chat(client, "¿Venden pizza?", user_id="duenia_1").json()["ticket_id"]
    assert client.get(f"/api/v1/ticket/{public_id}", params={"user_id": "otra_persona"}).status_code == 404
    assert client.get(f"/api/v1/ticket/{public_id}").status_code == 404  # sin user_id
    res = client.post(f"/api/v1/ticket/{public_id}/feedback", json={"user_id": "otra_persona", "helpful": False})
    assert res.status_code == 404
    with db.session_scope() as session:
        assert session.query(db.ConversationLog).one().feedback is None
    # la dueña sí puede
    assert client.get(f"/api/v1/ticket/{public_id}", params={"user_id": "duenia_1"}).status_code == 200
    ok = client.post(f"/api/v1/ticket/{public_id}/feedback", json={"user_id": "duenia_1", "helpful": True})
    assert ok.status_code == 200


def test_migracion_asigna_public_id_a_tickets_viejos():
    with db.engine.begin() as connection:
        connection.execute(text("DROP INDEX IF EXISTS ix_conversation_logs_public_id"))
        for i in range(3):
            connection.execute(text(
                "INSERT INTO conversation_logs (user_id, user_type, query, response, confidence_score, routed_to,"
                " public_id) VALUES (:u, 'estudiante', 'q', 'r', 0.1, 'human', NULL)"), {"u": f"viejo_{i}"})
    db._backfill_public_ids()
    with db.session_scope() as session:
        ids = [row.public_id for row in session.query(db.ConversationLog).all()]
    assert len(ids) == 3 and len(set(ids)) == 3 and all(main._valid_public_id(i) for i in ids)
    with db.engine.begin() as connection:
        indexes = connection.execute(text("PRAGMA index_list('conversation_logs')")).fetchall()
    assert any(row[1] == "ix_conversation_logs_public_id" and row[2] == 1 for row in indexes)  # único


# ------------------------------------------------------------------ rate limiting y validaciones (2.5)
def test_rate_limit_chat_20_por_minuto(client):
    for _ in range(20):
        assert chat(client, "Hola").status_code == 200
    res = chat(client, "Hola")
    assert res.status_code == 429
    assert res.json()["detail"] == main.RATE_LIMIT_MESSAGE


def test_rate_limit_resenias_5_por_minuto(client):
    review = {"user_type": "estudiante", "rating": 3, "comment": "spam"}
    codes = [client.post("/api/v1/reviews", json=review).status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]


def test_rate_limit_login_5_por_minuto(client, monkeypatch):
    monkeypatch.setattr(config, "LOGIN_MAX_FAILURES", 100)  # aísla el rate limit del bloqueo
    codes = [login(client, "contrasena-equivocada").status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]


@pytest.mark.parametrize("payload", [
    {"user_type": "estudiante", "rating": 0},
    {"user_type": "estudiante", "rating": 6},
    {"user_type": "hacker", "rating": 3},
    {"user_type": "estudiante", "rating": 3, "comment": "x" * 501},
])
def test_resenia_invalida_422(client, payload):
    assert client.post("/api/v1/reviews", json=payload).status_code == 422


@pytest.mark.parametrize("user_id", ["<script>alert(1)</script>", "a b", "x" * 51, ""])
def test_user_id_invalido_422(client, user_id):
    res = client.post("/api/v1/chat", json={"user_id": user_id, "user_type": "estudiante", "query": "Hola"})
    assert res.status_code == 422


def test_respuesta_manual_demasiado_larga_422(client):
    res = client.post("/api/v1/ticket/1/resolve", json={"manual_response": "x" * 2001}, headers=operator_headers())
    assert res.status_code == 422


# ------------------------------------------------------------------ endurecimiento (2.6, E-011, E-013)
def test_health_no_expone_configuracion(client):
    body = client.get("/health").json()
    assert body == {"status": "ok"}


def test_encabezados_de_seguridad(client):
    headers = client.get("/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert "default-src 'none'" in headers["content-security-policy"]


def test_html_inyectado_viaja_como_json_no_como_html(client):
    res = chat(client, "<script>alert('xss')</script> ¿venden pizza?")
    assert res.headers["content-type"].startswith("application/json")
    assert res.headers["x-content-type-options"] == "nosniff"


def test_cors_rechaza_origen_no_permitido(client):
    res = client.options("/api/v1/chat", headers={"Origin": "https://sitio-malicioso.example",
                                                 "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in res.headers


def test_error_500_sin_detalles_internos(client, monkeypatch):
    def boom():
        raise RuntimeError("detalle interno: /ruta/secreta.db")

    monkeypatch.setattr(db, "get_user_stats", boom)
    with TestClient(main.app, raise_server_exceptions=False) as raw_client:
        res = raw_client.get("/api/v1/stats", headers=operator_headers())
    assert res.status_code == 500
    assert res.json() == {"detail": main.SERVICE_ERROR_MESSAGE}
    assert "secreta" not in res.text and "Traceback" not in res.text


def test_docs_disponible_en_desarrollo(client):
    assert client.get("/docs").status_code == 200


def _run_in_production(code: str):
    env = dict(os.environ)
    env.update({
        "ENV": "production",
        "OPERATOR_PASSWORD_HASH": "$2b$12$" + "x" * 53,
        "AUTH_SECRET_KEY": "clave-falsa-pero-suficientemente-larga-0123",
        "ALLOWED_ORIGINS": "https://chat-permitido.example",
    })
    return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_docs_y_openapi_no_existen_en_produccion():
    code = (
        "from fastapi.testclient import TestClient\n"
        "import main\n"
        "c = TestClient(main.app)\n"
        "print([c.get(p).status_code for p in ('/docs', '/redoc', '/openapi.json')])\n"
        "print(c.get('/health').headers.get('strict-transport-security'))\n"
        "r = c.options('/api/v1/chat', headers={'Origin': 'https://chat-permitido.example',"
        " 'Access-Control-Request-Method': 'POST'})\n"
        "print(r.headers.get('access-control-allow-origin'))\n"
    )
    result = _run_in_production(code)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert lines[-3] == "[404, 404, 404]"
    assert lines[-2].startswith("max-age=")
    assert lines[-1] == "https://chat-permitido.example"


# ------------------------------------------------------------------ bitácora del operador (2.6)
def test_bitacora_de_acciones_del_operador(client):
    login(client, "contrasena-equivocada")
    login(client)
    public_id = chat(client, "¿Cuál es la capital de Francia?").json()["ticket_id"]
    with db.session_scope() as session:
        internal = session.query(db.ConversationLog).filter_by(public_id=public_id).one().id
    headers = operator_headers()
    client.post(f"/api/v1/ticket/{internal}/resolve", json={"manual_response": "No es tema de la cafetería."},
                headers=headers)
    actions = client.get("/api/v1/operator-actions", headers=headers).json()
    assert [a["action"] for a in actions] == ["resolver_ticket", "login_ok", "login_fallido"]
    assert actions[0]["target"] == str(internal)
    assert all(a["ip"] == "testclient" and a["timestamp"] and a["actor"] == "operador" for a in actions)


# ------------------------------------------------------------------ IP real detrás del proxy de Render
class _FakeRequest:
    def __init__(self, forwarded=None, host="10.0.0.1"):
        self.headers = {"x-forwarded-for": forwarded} if forwarded else {}
        self.client = type("C", (), {"host": host})()


def test_client_ip_sin_proxy_ignora_x_forwarded_for(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 0)
    assert security.client_ip(_FakeRequest("1.2.3.4")) == "10.0.0.1"


def test_client_ip_con_proxies_ignora_valores_inventados(monkeypatch):
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 2)
    # Render/Cloudflare: "<cliente>, <borde de Cloudflare>". El cliente intenta anteponer una IP falsa.
    assert security.client_ip(_FakeRequest("198.51.100.20, 104.22.17.40")) == "198.51.100.20"
    assert security.client_ip(_FakeRequest("6.6.6.6, 198.51.100.20, 104.22.17.40")) == "198.51.100.20"
    assert security.client_ip(_FakeRequest()) == "10.0.0.1"
    monkeypatch.setattr(config, "TRUSTED_PROXY_HOPS", 1)
    assert security.client_ip(_FakeRequest("6.6.6.6, 198.51.100.20")) == "198.51.100.20"


def test_system_muestra_ip_detectada_para_verificar_el_proxy(client):
    body = client.get("/api/v1/system", headers=operator_headers()).json()
    assert body["ip_detectada"] == "testclient"


# ------------------------------------------------------------------ política de contraseña y script
def test_politica_de_contrasena():
    assert security.password_problem("a" * 11)
    assert security.password_problem(" " * 12)
    assert security.password_problem("ñ" * 37)  # 74 bytes > 72
    assert security.password_problem("a" * 12) is None
    with pytest.raises(ValueError):
        security.hash_password("corta")


def test_hash_y_verificacion():
    hashed = security.hash_password("una-contrasena-de-prueba")
    assert hashed.startswith("$2b$12$") and len(hashed) == 60
    assert security.verify_password("una-contrasena-de-prueba", hashed)
    assert not security.verify_password("otra-contrasena-de-prueba", hashed)
    assert not security.verify_password("una-contrasena-de-prueba", "no-es-un-hash")


def _load_script():
    import importlib.util

    spec = importlib.util.spec_from_file_location("hash_password", REPO_ROOT / "scripts" / "hash_password.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_hash_password(monkeypatch, capsys):
    script = _load_script()
    answers = iter(["contrasena-segura-de-prueba", "contrasena-segura-de-prueba"])
    monkeypatch.setattr(script.getpass, "getpass", lambda _prompt: next(answers))
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "contrasena-segura-de-prueba" not in out  # la contraseña nunca se imprime
    hashed = out.strip().splitlines()[-1]
    assert security.verify_password("contrasena-segura-de-prueba", hashed)


@pytest.mark.parametrize("answers", [["corta"], ["contrasena-segura-1", "contrasena-segura-2"]])
def test_script_rechaza_contrasena_corta_o_distinta(monkeypatch, capsys, answers):
    script = _load_script()
    it = iter(answers)
    monkeypatch.setattr(script.getpass, "getpass", lambda _prompt: next(it))
    assert script.main() == 1
    assert "$2b$" not in capsys.readouterr().out


# ------------------------------------------------------------------ exportación de conversaciones
def test_exportar_conversaciones_requiere_operador(client):
    assert client.get("/api/v1/conversations").status_code == 401


def test_exportar_conversaciones_csv_desde_una_hora(client):
    from datetime import timedelta
    import database as db
    db.save_log(user_id="estudiante_viejo000000", user_type="estudiante", query="vieja", response="r",
                score=0.9, routed_to="bot", route="llm")
    with db.session_scope() as session:
        row = session.query(db.ConversationLog).filter(db.ConversationLog.query == "vieja").one()
        row.timestamp = db.utcnow() - timedelta(hours=3)
    db.save_log(user_id="estudiante_nuevo000000", user_type="estudiante", query="¿A qué hora abren?",
                response="A las 7:00", score=0.9, routed_to="bot", route="llm")
    since = (db.utcnow() - timedelta(hours=1)).isoformat() + "+00:00"
    res = client.get("/api/v1/conversations", params={"since": since}, headers=operator_headers())
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    text = res.text
    assert "pregunta" in text and "¿A qué hora abren?" in text and "vieja" not in text
    assert client.get("/api/v1/conversations", params={"since": "ayer"},
                      headers=operator_headers()).status_code == 422
