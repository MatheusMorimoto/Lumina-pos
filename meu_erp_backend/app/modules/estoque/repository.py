"""Persistência de produtos e lotes no Supabase."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.database import unwrap_response
from app.modules.estoque.schemas import LoteCreate, ProdutoCreate


class EstoqueRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def criar_produto(self, dados: ProdutoCreate) -> dict[str, Any]:
        return unwrap_response(
            self.client.table("produtos").insert(dados.model_dump(mode="json")).execute()
        )[0]

    def listar_catalogo(self) -> list[dict[str, Any]]:
        return unwrap_response(
            self.client.table("produtos").select("*").eq("ativo", True).order("nome").execute()
        )

    def criar_lote(self, dados: LoteCreate) -> dict[str, Any]:
        payload = dados.model_dump(mode="json")
        payload["saldo"] = str(dados.quantidade)
        return unwrap_response(self.client.table("lotes_produto").insert(payload).execute())[0]

    def buscar_lote(self, lote_id: UUID) -> dict[str, Any] | None:
        rows = unwrap_response(
            self.client.table("lotes_produto").select("*").eq("id", str(lote_id)).limit(1).execute()
        )
        return rows[0] if rows else None

    def atualizar_saldo_lote(self, lote_id: UUID, saldo: Decimal) -> dict[str, Any]:
        rows = unwrap_response(
            self.client.table("lotes_produto")
            .update({"saldo": str(saldo)})
            .eq("id", str(lote_id))
            .execute()
        )
        return rows[0]

    def lotes_vencendo_ate(self, data_limite: date) -> list[dict[str, Any]]:
        return unwrap_response(
            self.client.table("lotes_produto")
            .select("*, produtos(nome, sku)")
            .gt("saldo", 0)
            .not_.is_("validade", "null")
            .lte("validade", data_limite.isoformat())
            .order("validade")
            .execute()
        )
