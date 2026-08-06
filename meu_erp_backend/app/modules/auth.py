"""Autenticacao dos operadores e diagnostico seguro do resultado do login."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client

from app.core.config import get_settings
from app.core.database import (
    get_authenticated_client,
    get_supabase_anon_client,
    get_supabase_client,
    unwrap_response,
)
from app.core.security import create_access_token, decode_access_token, verify_password
from app.modules.registration import RegistrationIn, RegistrationService
from app.shared.exceptions import AuthenticationError, RateLimitError, UpstreamError

router = APIRouter(prefix="/auth", tags=["Autenticação"])
bearer = HTTPBearer(auto_error=False)
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = Lock()


class LoginIn(BaseModel):
    email: str
    password: str
    store_id: str | None = None


def _request_key(request: Request, email: str) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return f"{host}:{email.strip().lower()}"


def _check_rate_limit(key: str) -> None:
    settings = get_settings()
    cutoff = monotonic() - settings.login_rate_limit_window_seconds
    with _attempts_lock:
        attempts = _attempts[key]
        while attempts and attempts[0] < cutoff:
            attempts.popleft()
        if len(attempts) >= settings.login_rate_limit_attempts:
            raise RateLimitError("Muitas tentativas de login. Aguarde alguns minutos.")


def _record_failure(key: str) -> None:
    with _attempts_lock:
        _attempts[key].append(monotonic())


def _clear_attempts(key: str) -> None:
    with _attempts_lock:
        _attempts.pop(key, None)


def _mask_cpf(value: str | None) -> str | None:
    digits = "".join(char for char in (value or "") if char.isdigit())
    if len(digits) != 11:
        return None
    return f"{digits[:3]}.***.***-{digits[-2:]}"


def _profile_for_token(token: str, user_id: str) -> dict[str, Any]:
    """Consulta o perfil operacional aplicando as RLS do usuario autenticado."""
    try:
        client = get_authenticated_client(token)
        users = unwrap_response(
            client.table("users")
            .select("id,name,email,active,store_id,role")
            .eq("id", user_id).limit(1).execute()
        )
        if not users:
            return {"found": False, "user_id": user_id, "lookup_status": "not_found"}
        user = users[0]
        registrations = unwrap_response(
            client.table("individual_registrations")
            .select("full_name,cpf")
            .eq("store_id", user["store_id"]).limit(1).execute()
        )
        registration = registrations[0] if registrations else {}
        return {
            "found": True,
            "user_id": user_id,
            "name": registration.get("full_name") or user.get("name"),
            "cpf_masked": _mask_cpf(registration.get("cpf")),
            "store_id": user.get("store_id"),
            "role": user.get("role"),
            "active": user.get("active", True),
            "lookup_status": "found",
        }
    except Exception:
        # Perfil e secundario: uma falha de consulta nunca invalida o Supabase Auth.
        return {"found": False, "user_id": user_id, "lookup_status": "unavailable"}


def _looks_like_upstream_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(term in message for term in (
        "timed out", "timeout", "connect", "network", "dns", "service unavailable",
        "bad gateway", "connection refused",
    ))


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegistrationIn, response: Response) -> dict[str, Any]:
    response_status, payload = RegistrationService().register(data)
    response.status_code = response_status
    return payload


@router.post("/login")
def login(
    data: LoginIn,
    request: Request,
    db: Annotated[Client, Depends(get_supabase_client)],
) -> dict[str, Any]:
    email = data.email.strip().lower()
    key = _request_key(request, email)
    _check_rate_limit(key)
    auth_error: Exception | None = None
    try:
        auth_response = get_supabase_anon_client().auth.sign_in_with_password(
            {"email": email, "password": data.password}
        )
        if auth_response.session:
            _clear_attempts(key)
            auth_user = auth_response.user or auth_response.session.user
            user_id = str(auth_user.id)
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "token_type": "bearer",
                "expires_in": auth_response.session.expires_in,
                "expires_at": getattr(auth_response.session, "expires_at", None),
                "authentication": {
                    "success": True,
                    "user_id": user_id,
                    "email": getattr(auth_user, "email", email),
                    "email_confirmed": bool(
                        getattr(auth_user, "email_confirmed_at", None)
                        or getattr(auth_user, "confirmed_at", None)
                    ),
                    "token_received": True,
                },
                "profile": _profile_for_token(auth_response.session.access_token, user_id),
            }
    except Exception as exc:
        auth_error = exc

    try:
        # Compatibilidade temporaria com usuarios que ainda possuem hash local.
        query = db.table("users").select("*").eq("email", email).eq("active", True)
        if data.store_id:
            query = query.eq("store_id", data.store_id)
        rows = unwrap_response(query.limit(1).execute())
    except Exception as exc:
        _record_failure(key)
        if _looks_like_upstream_failure(auth_error or exc):
            raise UpstreamError(
                "O servico de autenticacao esta temporariamente indisponivel."
            ) from None
        raise UpstreamError("Nao foi possivel consultar o cadastro de acesso.") from None

    if not rows or not rows[0].get("password_hash") or not verify_password(
        data.password, rows[0]["password_hash"]
    ):
        _record_failure(key)
        if auth_error and _looks_like_upstream_failure(auth_error):
            raise UpstreamError(
                "O servico de autenticacao esta temporariamente indisponivel."
            ) from None
        raise AuthenticationError("E-mail ou senha invalidos.")
    user = rows[0]
    token = create_access_token(user["id"], {"store_id": user["store_id"], "role": user["role"]})
    _clear_attempts(key)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
        "authentication": {
            "success": True, "user_id": user["id"], "email": user["email"],
            "email_confirmed": None, "token_received": True,
        },
        "profile": {
            "found": True, "user_id": user["id"], "name": user.get("name"),
            "cpf_masked": None, "store_id": user.get("store_id"),
            "role": user.get("role"), "active": user.get("active", True),
            "lookup_status": "legacy",
        },
    }


def access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if not credentials:
        raise AuthenticationError("Token de acesso obrigatório.")
    return credentials.credentials


def current_user(token: Annotated[str, Depends(access_token)]) -> dict[str, Any]:
    """Aceita tokens do Supabase Auth e mantém compatibilidade com JWTs legados."""
    try:
        client = get_authenticated_client(token)
        auth_response = client.auth.get_user(token)
        auth_user = auth_response.user if auth_response else None
        if auth_user:
            rows = unwrap_response(
                client.table("users")
                .select("id,email,name,phone,role,active,store_id,stores(id,name,person_type)")
                .eq("id", str(auth_user.id))
                .limit(1)
                .execute()
            )
            if not rows or not rows[0].get("active", True):
                raise AuthenticationError("Cadastro de usuário não está ativo.")
            row = rows[0]
            return {
                "id": row["id"], "email": row["email"], "name": row["name"],
                "phone": row.get("phone"), "role": row["role"],
                "store": row.get("stores"), "store_id": row["store_id"],
                "registration_complete": bool(row.get("stores")), "access_token": token,
            }
    except AuthenticationError:
        raise
    except Exception:
        pass
    return decode_access_token(token)


@router.get("/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return {key: value for key, value in user.items() if key != "access_token"}
