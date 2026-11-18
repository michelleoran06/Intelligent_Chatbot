"""Fase 1 (M4): configuración centralizada y arranque fail-closed en producción."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

import config

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETOS_FALSOS = {
    "OPERATOR_PASSWORD_HASH": "hash-falso",
    "AUTH_SECRET_KEY": "clave-falsa",
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
