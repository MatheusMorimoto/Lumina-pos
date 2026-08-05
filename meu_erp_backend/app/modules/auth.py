"""Autenticação JWT dos operadores."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
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
from app.shared.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["Autenticação"])
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    email: str
    password: str
    store_id: str | None = None


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegistrationIn, response: Response) -> dict[str, Any]:
    response_status, payload = RegistrationService().register(data)
    response.status_code = response_status
    return payload


@router.post("/login")
def login(data: LoginIn, db: Annotated[Client, Depends(get_supabase_client)]) -> dict[str, Any]:
    try:
        auth_response = get_supabase_anon_client().auth.sign_in_with_password(
            {"email": data.email.strip().lower(), "password": data.password}
        )
        if auth_response.session:
            return {
                "access_token": auth_response.session.access_token,
                "refresh_token": auth_response.session.refresh_token,
                "token_type": "bearer",
                "expires_in": auth_response.session.expires_in,
            }
    except Exception:
        # Compatibilidade temporária com usuários que ainda possuem hash local.
        pass
    query = db.table("users").select("*").eq("email", data.email).eq("active", True)
    if data.store_id:
        query = query.eq("store_id", data.store_id)
    rows = unwrap_response(query.limit(1).execute())
    if not rows or not rows[0].get("password_hash") or not verify_password(
        data.password, rows[0]["password_hash"]
    ):
        raise AuthenticationError("E-mail ou senha inválidos.")
    user = rows[0]
    token = create_access_token(user["id"], {"store_id": user["store_id"], "role": user["role"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": get_settings().access_token_expire_minutes * 60,
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
