"""Hashing de senhas e emissão/validação de tokens JWT."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import get_settings
from app.shared.exceptions import AuthenticationError


def hash_password(password: str) -> str:
    """Gera hash bcrypt de uma senha em texto puro."""
    if len(password.encode("utf-8")) > 72:
        raise ValueError("A senha deve ter no máximo 72 bytes.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Compara uma senha em texto puro com seu hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        return False


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """Cria token de acesso JWT com expiração configurável."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    payload.update(extra_claims or {})
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Valida e decodifica um token JWT."""
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise AuthenticationError("Token inválido ou expirado.") from exc
