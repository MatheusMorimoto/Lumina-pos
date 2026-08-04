"""Persistência do domínio de vendas no Supabase."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.database import unwrap_response
from app.modules.vendas.schemas import AberturaCaixaCreate, TrocaCreate, VendaCreate


class VendasRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def buscar_caixa(self, caixa_id: UUID) -> dict[str, Any] | None:
        response = self.client.table("caixas").select("*").eq("id", str(caixa_id)).limit(1).execute()
        rows = unwrap_response(response)
        return rows[0] if rows else None

    def buscar_caixa_aberto_por_operador(self, operador_id: UUID) -> dict[str, Any] | None:
        response = (
            self.client.table("caixas")
            .select("*")
            .eq("operador_id", str(operador_id))
            .eq("status", "aberto")
            .limit(1)
            .execute()
        )
        rows = unwrap_response(response)
        return rows[0] if rows else None

    def abrir_caixa(self, dados: AberturaCaixaCreate) -> dict[str, Any]:
        payload = {
            "operador_id": str(dados.operador_id),
            "saldo_inicial": str(dados.saldo_inicial),
            "status": "aberto",
        }
        return unwrap_response(self.client.table("caixas").insert(payload).execute())[0]

    def criar_venda(self, dados: VendaCreate, total: Decimal) -> dict[str, Any]:
        payload = {
            "caixa_id": str(dados.caixa_id),
            "cliente_id": str(dados.cliente_id) if dados.cliente_id else None,
            "total": str(total),
            "forma_pagamento": dados.forma_pagamento.value,
            "status": "concluida",
        }
        venda = unwrap_response(self.client.table("vendas").insert(payload).execute())[0]
        itens = [
            {
                "venda_id": venda["id"],
                "produto_id": str(item.produto_id),
                "quantidade": str(item.quantidade),
                "preco_unitario": str(item.preco_unitario),
                "desconto": str(item.desconto),
                "subtotal": str(item.subtotal),
            }
            for item in dados.itens
        ]
        self.client.table("itens_venda").insert(itens).execute()
        return venda

    def total_movimentado(self, caixa_id: UUID) -> Decimal:
        response = (
            self.client.table("vendas")
            .select("total")
            .eq("caixa_id", str(caixa_id))
            .eq("status", "concluida")
            .execute()
        )
        return sum((Decimal(str(row["total"])) for row in unwrap_response(response)), Decimal("0"))

    def fechar_caixa(
        self, caixa_id: UUID, saldo_informado: Decimal, quebra_caixa: Decimal
    ) -> dict[str, Any]:
        payload = {
            "status": "fechado",
            "saldo_informado": str(saldo_informado),
            "quebra_caixa": str(quebra_caixa),
            "fechado_em": datetime.now(UTC).isoformat(),
        }
        response = self.client.table("caixas").update(payload).eq("id", str(caixa_id)).execute()
        return unwrap_response(response)[0]

    def registrar_troca(self, dados: TrocaCreate) -> dict[str, Any]:
        return unwrap_response(
            self.client.table("trocas").insert(dados.model_dump(mode="json")).execute()
        )[0]
