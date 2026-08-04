"""Persistência de parcelas e limites de clientes."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from supabase import Client

from app.core.database import unwrap_response
from app.modules.crediario.schemas import ParcelaCreate


class CrediarioRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def criar_parcela(self, dados: ParcelaCreate) -> dict[str, Any]:
        payload = dados.model_dump(mode="json")
        payload["saldo_devedor"] = str(dados.valor_original)
        payload["status"] = "aberta"
        return unwrap_response(
            self.client.table("parcelas_crediario").insert(payload).execute()
        )[0]

    def buscar_parcela(self, parcela_id: UUID) -> dict[str, Any] | None:
        response = (
            self.client.table("parcelas_crediario")
            .select("*")
            .eq("id", str(parcela_id))
            .limit(1)
            .execute()
        )
        rows = unwrap_response(response)
        return rows[0] if rows else None

    def baixar_parcela(
        self, parcela_id: UUID, valor_pago: Decimal, saldo_restante: Decimal
    ) -> dict[str, Any]:
        payload = {
            "saldo_devedor": str(saldo_restante),
            "status": "paga" if saldo_restante == 0 else "parcial",
        }
        response = (
            self.client.table("parcelas_crediario")
            .update(payload)
            .eq("id", str(parcela_id))
            .execute()
        )
        return unwrap_response(response)[0]

    def buscar_cliente(self, cliente_id: UUID) -> dict[str, Any] | None:
        response = (
            self.client.table("clientes").select("*").eq("id", str(cliente_id)).limit(1).execute()
        )
        rows = unwrap_response(response)
        return rows[0] if rows else None

    def saldo_em_aberto(self, cliente_id: UUID) -> Decimal:
        response = (
            self.client.table("parcelas_crediario")
            .select("saldo_devedor")
            .eq("cliente_id", str(cliente_id))
            .in_("status", ["aberta", "parcial"])
            .execute()
        )
        return sum(
            (Decimal(str(row["saldo_devedor"])) for row in unwrap_response(response)),
            Decimal("0"),
        )
