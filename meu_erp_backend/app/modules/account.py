"""Cadastro da loja e configurações fiscais protegidas por usuário e RLS."""
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.core.database import get_authenticated_client, unwrap_response
from app.modules.auth import current_user
from app.modules.registration import AccountPatch, FiscalProfilePatch, ProductTaxProfileIn
from app.shared.exceptions import AuthenticationError, NotFoundError

router = APIRouter(tags=["Conta e Fiscal"])
User = Annotated[dict[str, Any], Depends(current_user)]


def client_for(user: dict[str, Any]) -> Client:
    token = user.get("access_token")
    if not token:
        raise AuthenticationError("Esta operação exige uma sessão do Supabase Auth.")
    return get_authenticated_client(token)


def require_admin(user: dict[str, Any]) -> None:
    if user.get("role") not in {"owner", "admin"}:
        raise AuthenticationError("Apenas proprietário ou administrador pode alterar dados fiscais.")


def first(rows: list[dict[str, Any]], message: str) -> dict[str, Any]:
    if not rows:
        raise NotFoundError(message)
    return rows[0]


@router.get("/account")
def account(user: User) -> dict[str, Any]:
    rows = unwrap_response(
        client_for(user).table("stores")
        .select("*,company_registrations(*),individual_registrations(*),store_addresses(*)")
        .eq("id", user["store_id"]).limit(1).execute()
    )
    return first(rows, "Cadastro da loja não encontrado.")


@router.patch("/account")
def patch_account(data: AccountPatch, user: User) -> dict[str, Any]:
    require_admin(user)
    db = client_for(user)
    payload = data.model_dump(mode="json", exclude_none=True)
    if "name" in payload:
        db.table("stores").update({"name": payload.pop("name")}).eq(
            "id", user["store_id"]
        ).execute()
    if "phone" in payload:
        db.table("users").update({"phone": payload.pop("phone")}).eq(
            "id", user["id"]
        ).execute()
    if payload:
        db.table("store_addresses").update(payload).eq("store_id", user["store_id"]).eq(
            "is_primary", True
        ).execute()
    return account(user)


@router.get("/account/fiscal-profile")
def fiscal_profile(user: User) -> dict[str, Any]:
    rows = unwrap_response(
        client_for(user).table("fiscal_profiles").select("*").eq(
            "store_id", user["store_id"]
        ).limit(1).execute()
    )
    return first(rows, "Perfil fiscal não encontrado.")


@router.patch("/account/fiscal-profile")
def patch_fiscal_profile(data: FiscalProfilePatch, user: User) -> dict[str, Any]:
    require_admin(user)
    rows = unwrap_response(
        client_for(user).rpc(
            "review_fiscal_profile",
            {"p_tax_regime": data.tax_regime.value, "p_regime_source": data.regime_source},
        ).execute()
    )
    return first(rows, "Perfil fiscal não encontrado.")


@router.get("/products/{product_id}/tax-profile")
def product_tax_profile(product_id: UUID, user: User) -> dict[str, Any]:
    rows = unwrap_response(
        client_for(user).table("product_tax_profiles").select("*").eq(
            "product_id", str(product_id)
        ).limit(1).execute()
    )
    return first(rows, "Perfil fiscal do produto não encontrado.")


@router.put("/products/{product_id}/tax-profile")
def put_product_tax_profile(
    product_id: UUID, data: ProductTaxProfileIn, user: User
) -> dict[str, Any]:
    require_admin(user)
    db = client_for(user)
    products = unwrap_response(
        db.table("products").select("id").eq("id", str(product_id)).eq(
            "store_id", user["store_id"]
        ).limit(1).execute()
    )
    if not products:
        raise NotFoundError("Produto não encontrado nesta loja.")
    payload = data.model_dump(mode="json")
    payload.update({
        "product_id": str(product_id), "store_id": user["store_id"],
        "reviewed_by": user["id"] if data.manually_reviewed else None,
    })
    rows = unwrap_response(
        db.table("product_tax_profiles").upsert(payload, on_conflict="product_id").execute()
    )
    return first(rows, "Não foi possível salvar o perfil fiscal.")
