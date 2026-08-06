"""Autenticacao dos operadores e diagnostico seguro do resultado do login."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator
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


class PasswordRecoveryIn(BaseModel):
    email: str


class PasswordUpdateIn(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self) -> "PasswordUpdateIn":
        if self.password != self.password_confirmation:
            raise ValueError("As senhas nao coincidem.")
        if not any(char.isalpha() for char in self.password) or not any(
            char.isdigit() for char in self.password
        ):
            raise ValueError("A senha deve conter letras e numeros.")
        return self


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


def _mask_cnpj(value: str | None) -> str | None:
    digits = "".join(char for char in (value or "") if char.isdigit())
    if len(digits) != 14:
        return None
    return f"{digits[:2]}.***.***/{digits[8:12]}-{digits[-2:]}"


def _profile_for_token(token: str, user_id: str) -> dict[str, Any]:
    """Consulta o perfil operacional aplicando as RLS do usuario autenticado."""
    try:
        client = get_authenticated_client(token)
        users = unwrap_response(
            client.table("users")
            .select("id,name,email,active,store_id,role,stores(person_type)")
            .eq("id", user_id).limit(1).execute()
        )
        if not users:
            return {"found": False, "user_id": user_id, "lookup_status": "not_found"}
        user = users[0]
        person_type = (user.get("stores") or {}).get("person_type")
        table = "company_registrations" if person_type == "company" else "individual_registrations"
        fields = "legal_name,trade_name,cnpj" if person_type == "company" else "full_name,cpf"
        registrations = unwrap_response(
            client.table(table).select(fields)
            .eq("store_id", user["store_id"]).limit(1).execute()
        )
        registration = registrations[0] if registrations else {}
        return {
            "found": True,
            "user_id": user_id,
            "name": registration.get("trade_name") or registration.get("full_name")
            or registration.get("legal_name") or user.get("name"),
            "cpf_masked": _mask_cpf(registration.get("cpf")),
            "cnpj_masked": _mask_cnpj(registration.get("cnpj")),
            "person_type": person_type,
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


def _raise_safe_auth_error(exc: Exception | None) -> None:
    """Traduz erros conhecidos do GoTrue sem devolver detalhes internos."""
    message = str(exc or "").lower()
    if "email not confirmed" in message or "email_not_confirmed" in message:
        raise AuthenticationError("E-mail ainda nao confirmado.")
    if any(term in message for term in ("banned", "blocked", "user_banned")):
        raise AuthenticationError("Conta temporariamente bloqueada.")
    if any(term in message for term in ("invalid api key", "invalid api-key", "api key")):
        raise UpstreamError("A autenticacao do Supabase nao esta configurada corretamente.")
    raise AuthenticationError("E-mail ou senha invalidos.")


def _complete_pending_profile(auth_user: Any, token: str) -> None:
    metadata = getattr(auth_user, "user_metadata", None) or {}
    pending = metadata.get("pending_registration")
    if not isinstance(pending, dict):
        return
    try:
        RegistrationService.complete_with_token(token, pending)
    except Exception:
        # A autenticacao ja foi concluida. Uma falha temporaria ao criar o perfil
        # nao deve invalidar a sessao; o cliente recebe registration_complete=false.
        return


def access_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if not credentials:
        raise AuthenticationError("Token de acesso obrigatorio.")
    return credentials.credentials


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegistrationIn, response: Response) -> dict[str, Any]:
    response_status, payload = RegistrationService().register(data)
    response.status_code = response_status
    return payload


@router.post("/login")
def login(
    data: LoginIn,
    request: Request,
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
            _complete_pending_profile(auth_user, auth_response.session.access_token)
            profile = _profile_for_token(auth_response.session.access_token, user_id)
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
                "profile": profile,
                "user": {
                    "id": user_id,
                    "email": getattr(auth_user, "email", email),
                    "person_type": profile.get("person_type"),
                    "display_name": profile.get("name"),
                    "account_id": profile.get("store_id"),
                    "role": profile.get("role"),
                    "registration_complete": profile.get("found", False),
                },
            }
    except Exception as exc:
        auth_error = exc

    if not get_settings().legacy_password_login_enabled:
        _record_failure(key)
        if auth_error and _looks_like_upstream_failure(auth_error):
            raise UpstreamError(
                "O servico de autenticacao esta temporariamente indisponivel."
            ) from None
        _raise_safe_auth_error(auth_error)

    try:
        # Compatibilidade temporaria com usuarios que ainda possuem hash local.
        db = get_supabase_client()
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
        _raise_safe_auth_error(auth_error)
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
        "user": {
            "id": user["id"], "email": user["email"],
            "person_type": None, "display_name": user.get("name"),
            "account_id": user.get("store_id"), "role": user.get("role"),
            "registration_complete": True,
        },
    }


@router.post("/password/recover", status_code=status.HTTP_202_ACCEPTED)
def recover_password(data: PasswordRecoveryIn) -> dict[str, str]:
    """Envia recuperacao sem revelar se o e-mail esta cadastrado."""
    email = data.email.strip().lower()
    options: dict[str, str] = {}
    redirect = get_settings().password_reset_redirect_url
    if redirect:
        options["redirect_to"] = redirect
    try:
        auth_api = get_supabase_anon_client().auth
        if options:
            auth_api.reset_password_for_email(email, options)
        else:
            auth_api.reset_password_for_email(email)
    except Exception:
        # Resposta uniforme evita enumeracao de contas.
        pass
    return {"message": "Se o e-mail estiver cadastrado, enviaremos as instrucoes."}


@router.post("/password/update")
def update_password(data: PasswordUpdateIn, token: Annotated[str, Depends(access_token)]) -> dict[str, str]:
    try:
        get_authenticated_client(token).auth.update_user({"password": data.password})
    except Exception as exc:
        raise AuthenticationError("Sessao invalida ou expirada para redefinir a senha.") from exc
    return {"message": "Senha atualizada com sucesso."}


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
            if not rows:
                return {
                    "id": str(auth_user.id),
                    "email": getattr(auth_user, "email", None),
                    "name": None,
                    "phone": None,
                    "role": None,
                    "store": None,
                    "store_id": None,
                    "registration_complete": False,
                    "profile_found": False,
                    "access_token": token,
                }
            if not rows[0].get("active", True):
                raise AuthenticationError("Cadastro de usuario nao esta ativo.")
            row = rows[0]
            return {
                "id": row["id"], "email": row["email"], "name": row["name"],
                "phone": row.get("phone"), "role": row["role"],
                "store": row.get("stores"), "store_id": row["store_id"],
                "registration_complete": bool(row.get("stores")),
                "profile_found": True, "access_token": token,
            }
    except AuthenticationError:
        raise
    except Exception:
        pass
    return decode_access_token(token)


@router.get("/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return {key: value for key, value in user.items() if key != "access_token"}
