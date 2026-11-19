"""Fase 5: scripts de verificación de producción, con HTTP simulado (el CI nunca toca producción)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_prod_env  # noqa: E402
import smoke_prod  # noqa: E402
from security import hash_password  # noqa: E402

PASSWORD = "contrasena-de-prueba-123"
GOOD = {
    "OPERATOR_PASSWORD_HASH": hash_password(PASSWORD),
    "AUTH_SECRET_KEY": "x" * 40,
    "ALLOWED_ORIGINS": "https://chat-cafe.streamlit.app,https://panel-cafe.streamlit.app",
    "GEMINI_API_KEY_1": "clave-falsa",
    "GEMINI_MODEL": "gemini-3.5-flash-lite",
}


# ------------------------------------------------------------------ check_prod_env.py
def test_check_prod_env_valores_correctos():
    assert check_prod_env.check(GOOD, PASSWORD) == []


def test_check_prod_env_detecta_hash_secreto_y_origenes_malos():
    bad = {**GOOD, "OPERATOR_PASSWORD_HASH": "mi-contraseña", "AUTH_SECRET_KEY": "corta",
           "ALLOWED_ORIGINS": "http://chat.streamlit.app/,*"}
    problems = " ".join(check_prod_env.check(bad))
    assert "OPERATOR_PASSWORD_HASH" in problems and "AUTH_SECRET_KEY" in problems
    assert "https://" in problems and "'*'" in problems


def test_check_prod_env_faltantes_y_contrasena_que_no_coincide():
    problems = check_prod_env.check({**GOOD, "ALLOWED_ORIGINS": "", "GEMINI_MODEL": ""}, "otra-contrasena-123")
    assert "Falta ALLOWED_ORIGINS." in problems
    assert any("GEMINI_MODEL" in p for p in problems)
    assert any("NO corresponde" in p for p in problems)


def test_check_prod_env_origen_con_ruta():
    assert check_prod_env.origin_problems("https://chat.streamlit.app/") != []
    assert check_prod_env.origin_problems("https://chat.streamlit.app") == []


def test_check_prod_env_nunca_imprime_valores(monkeypatch, capsys):
    answers = iter([GOOD["OPERATOR_PASSWORD_HASH"], GOOD["AUTH_SECRET_KEY"], GOOD["GEMINI_API_KEY_1"], PASSWORD])
    texts = iter([GOOD["ALLOWED_ORIGINS"], GOOD["GEMINI_MODEL"]])
    monkeypatch.setattr(check_prod_env.getpass, "getpass", lambda _prompt="": next(answers))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(texts))
    assert check_prod_env.main() == 0
    out = capsys.readouterr().out
    assert "OK" in out
    for value in (GOOD["OPERATOR_PASSWORD_HASH"], GOOD["AUTH_SECRET_KEY"], PASSWORD, GOOD["GEMINI_API_KEY_1"]):
        assert value not in out


# ------------------------------------------------------------------ smoke_prod.py
class FakeResponse:
    def __init__(self, status, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


class FakeProduction:
    """Backend de producción simulado que se comporta como debe."""

    def __init__(self, injection_reply="No puedo hacer eso. ¿Te ayudo con algo de la cafetería?"):
        self.logins = []
        self.injection_reply = injection_reply

    def get(self, url, headers=None, params=None, timeout=None):
        path = url.split(".com", 1)[1]
        authorized = (headers or {}).get("Authorization") == "Bearer token-falso"
        if path == "/health":
            return FakeResponse(200, {"status": "ok"})
        if path == "/api/v1/system":
            return FakeResponse(200, {"llm_configured": True, "llm_model": "m", "llm_keys": 2,
                                      "ip_detectada": "203.0.113.7"} if authorized else {})
        if path == "/api/v1/conversations" and authorized:
            return FakeResponse(200, text="hora_utc,sesion,tipo_usuario,pregunta\n1,2,3,4\n")
        if path.startswith("/api/v1/"):
            return FakeResponse(401)
        return FakeResponse(404)

    def post(self, url, json=None, timeout=None):
        path = url.split(".com", 1)[1]
        if path == "/api/v1/auth/login":
            self.logins.append(json["password"])
            ok = json["password"] == PASSWORD
            return FakeResponse(200 if ok else 401, {"access_token": "token-falso"} if ok else {})
        query = json["query"]
        if query == smoke_prod.NORMAL_QUESTION:
            return FakeResponse(200, {"route": "llm", "response": "Abrimos a las 7:00 a.m."})
        if query == smoke_prod.OUT_OF_DOMAIN_QUESTION:
            return FakeResponse(200, {"route": "out_of_scope", "response": "Solo sé de la cafetería."})
        return FakeResponse(200, {"route": "out_of_scope", "response": self.injection_reply})


URL = "https://backend-falso.onrender.com"


def test_smoke_prod_todo_ok_y_un_solo_login_incorrecto():
    fake = FakeProduction()
    checks = smoke_prod.run(fake, URL, PASSWORD, pause=0)
    assert all(check.ok for check in checks), [c.line() for c in checks if not c.ok]
    assert len(checks) == 13
    wrong = [p for p in fake.logins if p != PASSWORD]
    assert len(wrong) == 1  # nunca más de un intento incorrecto (5 bloquean la IP 15 min)
    assert len(fake.logins) == 2


def test_smoke_prod_detecta_fuga_del_prompt():
    checks = smoke_prod.run(FakeProduction(injection_reply="Mis reglas: escribe el source_id..."), URL, PASSWORD, pause=0)
    injection = [c for c in checks if "Inyección" in c.name][0]
    assert not injection.ok and "source_id" in injection.detail


def test_smoke_prod_se_detiene_si_el_backend_no_responde():
    class Down(FakeProduction):
        def get(self, url, headers=None, params=None, timeout=None):
            return FakeResponse(503)

    checks = smoke_prod.run(Down(), URL, PASSWORD, pause=0)
    assert len(checks) == 1 and not checks[0].ok and "503" in checks[0].detail


def test_smoke_prod_aviso_de_bloqueo():
    assert "5 intentos" in smoke_prod.WARNING and "15 minutos" in smoke_prod.WARNING
