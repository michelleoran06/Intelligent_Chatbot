"""Genera el hash bcrypt de la contraseña del operador (Fase 2 M4).

Uso, en tu computadora y desde la raíz del repositorio:

    python scripts/hash_password.py

La contraseña se pide dos veces sin mostrarse en pantalla (getpass), no queda en el historial de la
terminal y nunca se guarda ni se imprime. Solo se imprime el hash, que se pega en la variable
OPERATOR_PASSWORD_HASH de Render (o en tu .env local). Requisitos: mínimo 12 caracteres y máximo
72 bytes (límite de bcrypt).
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security import hash_password, password_problem  # noqa: E402


def main() -> int:
    password = getpass.getpass("Contraseña del operador (no se muestra): ")
    problem = password_problem(password)
    if problem:
        print(f"Error: {problem}", file=sys.stderr)
        return 1
    if getpass.getpass("Repítela: ") != password:
        print("Error: las contraseñas no coinciden.", file=sys.stderr)
        return 1
    print("\nHash bcrypt (cópialo completo en OPERATOR_PASSWORD_HASH):\n")
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    sys.exit(main())
