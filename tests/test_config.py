"""Fase 1 (M4): configuración centralizada y arranque fail-closed en producción."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import config

REPO_ROOT = Path(__file__).resolve().parent.parent
# Valores falsos con el formato correcto (un "hash" bcrypt de 60 caracteres que no corresponde a nada)
SECRETOS_FALSOS = {
    "OPERATOR_PASSWORD_HASH": "$2b$12$" + "x" * 53,
    "AUTH_SECRET_KEY": "clave-falsa-pero-suficientemente-larga-0123",
    "ALLOWED_ORIGINS": "http://localhost:8501",
}


def test_desarrollo_no_exige_secretos():
    assert config.missing_required_vars({}) == []
    assert config.missing_required_vars({"ENV": "development"}) == []
    config.validate_config({"ENV": "development"})


def test_produccion_sin_secretos_falla():
    with pytest.raises(config.ConfigError) as exc:
        config.validate_config({"ENV": "production"})
    for name in config.PRODUCTION_REQUIRED_VARS:
        assert name in str(exc.value)


@pytest.mark.parametrize("faltante", sorted(SECRETOS_FALSOS))
def test_produccion_detecta_cada_variable_faltante(faltante):
    env = {"ENV": "Production", **SECRETOS_FALSOS, faltante: "   "}
    assert config.missing_required_vars(env) == [faltante]


def test_produccion_con_secretos_arranca():
    config.validate_config({"ENV": "production", **SECRETOS_FALSOS})


def test_error_no_muestra_valores_de_secretos():
    env = {"ENV": "production", "AUTH_SECRET_KEY": "valor-super-secreto"}
    with pytest.raises(config.ConfigError) as exc:
        config.validate_config(env)
    assert "valor-super-secreto" not in str(exc.value)


def test_produccion_rechaza_hash_que_no_es_bcrypt():
    env = {"ENV": "production", **SECRETOS_FALSOS, "OPERATOR_PASSWORD_HASH": "mi-contrasena-en-texto-plano"}
    with pytest.raises(config.ConfigError) as exc:
        config.validate_config(env)
    assert "OPERATOR_PASSWORD_HASH" in str(exc.value)
    assert "mi-contrasena-en-texto-plano" not in str(exc.value)


def test_produccion_rechaza_clave_corta():
    env = {"ENV": "production", **SECRETOS_FALSOS, "AUTH_SECRET_KEY": "abc123xyz"}
    with pytest.raises(config.ConfigError) as exc:
        config.validate_config(env)
    assert "AUTH_SECRET_KEY" in str(exc.value) and "abc123xyz" not in str(exc.value)


def test_gemini_no_es_obligatorio():
    assert not any(name.startswith("GEMINI") for name in config.PRODUCTION_REQUIRED_VARS)


def _importar_main(env_extra):
    env = {k: v for k, v in os.environ.items() if k not in SECRETOS_FALSOS and k != "ENV"}
    env.update(env_extra)
    return subprocess.run([sys.executable, "-c", "import main"], cwd=REPO_ROOT, env=env,
                          capture_output=True, text=True, timeout=120)


def test_backend_no_arranca_en_produccion_sin_secretos():
    result = _importar_main({"ENV": "production"})
    assert result.returncode != 0
    assert "ConfigError" in result.stderr
    assert "AUTH_SECRET_KEY" in result.stderr


def test_backend_arranca_en_produccion_con_secretos():
    result = _importar_main({"ENV": "production", **SECRETOS_FALSOS})
    assert result.returncode == 0, result.stderr


# E-025: ninguna key de Google (formatos "AIza…" y "AQ.…") puede quedar en un archivo versionado
GOOGLE_KEY = __import__("re").compile(r"AIza[0-9A-Za-z_\-]{30,}|AQ\.[0-9A-Za-z_\-]{30,}")


def test_ningun_archivo_versionado_tiene_keys_de_google():
    files = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    encontrados = []
    for name in files.splitlines():
        path = REPO_ROOT / name
        if not path.is_file() or path.suffix in {".db", ".png", ".jpg", ".sqlite3", ".bin"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if GOOGLE_KEY.search(text):
            encontrados.append(name)  # solo el nombre del archivo, nunca la key
    assert encontrados == []
