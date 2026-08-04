"""Autenticação JWT dos operadores."""
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client

from app.core.database import get_supabase_client, unwrap_response
from app.core.security import create_access_token, decode_access_token, verify_password
from app.shared.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["Autenticação"])
bearer = HTTPBearer(auto_error=False)


class LoginIn(BaseModel):
    email: str
    password: str
    store_id: str | None = None


@router.post("/login")
def login(data: LoginIn, db: Annotated[Client, Depends(get_supabase_client)]) -> dict[str, Any]:
    query = db.table("users").select("*").eq("email", data.email).eq("active", True)
    if data.store_id:
        query = query.eq("store_id", data.store_id)
    rows = unwrap_response(query.limit(1).execute())
    if not rows or not verify_password(data.password, rows[0]["password_hash"]):
        raise AuthenticationError("E-mail ou senha inválidos.")
    user = rows[0]
    token = create_access_token(user["id"], {"store_id": user["store_id"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict[str, Any]:
    if not credentials:
        raise AuthenticationError("Token de acesso obrigatório.")
    return decode_access_token(credentials.credentials)


@router.get("/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    return user
