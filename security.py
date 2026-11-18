"""Autenticación del operador y utilidades de seguridad (Fase 2 M4).

- Contraseña: solo se guarda su hash bcrypt (OPERATOR_PASSWORD_HASH). Nunca se registra en logs.
- Sesión: token JWT HS256 firmado con AUTH_SECRET_KEY que expira en TOKEN_TTL_HOURS.
- Fail-closed: si falta el hash o la clave, ningún login ni token es válido.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config

TOKEN_ALGORITHM = "HS256"
TOKEN_SUBJECT = "operator"
BCRYPT_MAX_BYTES = 72
INVALID_CREDENTIALS = "Credenciales inválidas."
UNAUTHORIZED = "Sesión inválida o expirada. Inicia sesión de nuevo."

_bearer = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------ contraseñas
def password_problem(password: str) -> Optional[str]:
    """Motivo por el que la contraseña no se acepta, o None si cumple la política."""
    if len(password) < config.MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {config.MIN_PASSWORD_LENGTH} caracteres."
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return f"La contraseña no puede pasar de {BCRYPT_MAX_BYTES} bytes (límite de bcrypt)."
    if not password.strip():
        return "La contraseña no puede ser solo espacios."
    return None


def hash_password(password: str) -> str:
    problem = password_problem(password)
    if problem:
        raise ValueError(problem)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """Compara en tiempo constante (bcrypt.checkpw). Fail-closed ante cualquier dato inválido."""
    if not password_hash or password_problem(password):
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, TypeError, UnicodeError):
        return False


def auth_configured() -> bool:
    return bool(config.OPERATOR_PASSWORD_HASH and config.AUTH_SECRET_KEY)


# ------------------------------------------------------------------ tokens
def create_token(now: Optional[datetime] = None) -> str:
    if not config.AUTH_SECRET_KEY:
        raise RuntimeError("AUTH_SECRET_KEY no está configurada.")
    now = now or datetime.now(timezone.utc)
    payload = {
        "sub": TOKEN_SUBJECT,
        "iat": now,
        "exp": now + timedelta(hours=config.TOKEN_TTL_HOURS),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, config.AUTH_SECRET_KEY, algorithm=TOKEN_ALGORITHM)


def token_is_valid(token: str) -> bool:
    if not token or not config.AUTH_SECRET_KEY:
        return False
    try:
        payload = jwt.decode(
            token,
            config.AUTH_SECRET_KEY,
            algorithms=[TOKEN_ALGORITHM],  # lista cerrada: evita el ataque de "alg": "none"
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return False
    return payload.get("sub") == TOKEN_SUBJECT


def require_operator(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> None:
    """Dependencia de FastAPI: exige Authorization: Bearer <token> válido (firma y expiración)."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not token_is_valid(credentials.credentials):
        raise HTTPException(status_code=401, detail=UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})


# ------------------------------------------------------------------ IP del cliente
def client_ip(request: Request) -> str:
    """IP del cliente para rate limiting, bloqueo de login y bitácora del operador.

    Con TRUSTED_PROXY_HOPS = N > 0 se toma la entrada N-ésima contando desde la derecha de X-Forwarded-For:
    los proxies de confianza (Render/Cloudflare) agregan sus entradas al final y el cliente no las puede
    quitar; lo que el cliente mande por su cuenta queda a la izquierda y se ignora.
    """
    hops_trusted = config.TRUSTED_PROXY_HOPS
    if hops_trusted > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-hops_trusted if len(hops) >= hops_trusted else 0][:64]
    return (request.client.host if request.client else "desconocida")[:64]
