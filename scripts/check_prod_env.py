"""Revisa el formato de las variables de producción ANTES de poner ENV=production en Render (Fase 5 M4).

Con ENV=production el backend no arranca si falta OPERATOR_PASSWORD_HASH, AUTH_SECRET_KEY o
ALLOWED_ORIGINS, o si tienen un formato inseguro (config.validate_config). Este script aplica esas mismas
reglas a los valores que vas a pegar en Render, en tu computadora y sin red.

Uso, desde la raíz del repositorio y con el venv activado:

    python scripts/check_prod_env.py

Pega cada valor tal como está en Render. Los secretos se piden con getpass (no se muestran ni quedan en el
historial) y el script nunca imprime ningún valor: solo dice OK o qué hay que corregir.
"""
import getpass
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def origin_problems(raw: str) -> list:
    """Problemas de formato en ALLOWED_ORIGINS (lista separada por comas de https://host, sin ruta)."""
    problems = []
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        return ["ALLOWED_ORIGINS está vacío."]
    for number, origin in enumerate(origins, start=1):
        parsed = urlparse(origin)
        if origin == "*":
            problems.append(f"Origen {number}: '*' permite cualquier sitio; pon las URLs de tus apps de Streamlit.")
        elif parsed.scheme != "https" or not parsed.netloc:
            problems.append(f"Origen {number}: debe empezar con https:// y tener un dominio.")
        elif parsed.path not in ("",) or parsed.query or parsed.fragment:
            problems.append(f"Origen {number}: sin ruta ni '/' al final (solo https://dominio).")
        if origin != origin.strip("'\""):
            problems.append(f"Origen {number}: quita las comillas.")
    return problems


def check(values: dict, password=None) -> list:
    """Lista de problemas (vacía = todo bien). `values` usa los nombres de las variables de Render."""
    environ = {"ENV": "production", **values}
    problems = [f"Falta {name}." for name in config.missing_required_vars(environ)]
    problems += [f"Formato inseguro: {item}" for item in config.invalid_secret_vars(environ)]
    for name in ("OPERATOR_PASSWORD_HASH", "AUTH_SECRET_KEY"):
        value = values.get(name) or ""
        if value != value.strip() or value[:1] in ("'", '"'):
            problems.append(f"{name}: quita los espacios o comillas de los extremos.")
    if values.get("ALLOWED_ORIGINS"):
        problems += origin_problems(values["ALLOWED_ORIGINS"])
    if not (values.get("GEMINI_API_KEY_1") or "").strip():
        problems.append("Falta GEMINI_API_KEY_1 (el backend arranca, pero sin Gemini).")
    if not (values.get("GEMINI_MODEL") or "").strip():
        problems.append("Falta GEMINI_MODEL (el backend arranca, pero sin Gemini).")
    password_hash = (values.get("OPERATOR_PASSWORD_HASH") or "").strip()
    if password and password_hash and not config.invalid_secret_vars(environ):
        from security import verify_password
        if not verify_password(password, password_hash):
            problems.append("La contraseña que escribiste NO corresponde a OPERATOR_PASSWORD_HASH.")
    return problems


def main() -> int:
    print("Pega cada valor exactamente como está (o estará) en Render. Nada de esto se imprime.\n")
    values = {
        "OPERATOR_PASSWORD_HASH": getpass.getpass("OPERATOR_PASSWORD_HASH (no se muestra): "),
        "AUTH_SECRET_KEY": getpass.getpass("AUTH_SECRET_KEY (no se muestra): "),
        "ALLOWED_ORIGINS": input("ALLOWED_ORIGINS (URLs de Streamlit separadas por coma): "),
        "GEMINI_API_KEY_1": getpass.getpass("GEMINI_API_KEY_1 (no se muestra; Enter para omitir): "),
        "GEMINI_MODEL": input("GEMINI_MODEL: "),
    }
    password = getpass.getpass("Contraseña del operador, para comprobar que coincide con el hash "
                               "(no se muestra; Enter para omitir): ")
    problems = check(values, password)
    print()
    if problems:
        print("Corrige esto antes de poner ENV=production:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK: con estos valores el backend arranca con ENV=production"
          + (" y la contraseña coincide con el hash." if password else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
