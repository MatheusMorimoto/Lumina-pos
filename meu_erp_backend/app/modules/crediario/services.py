"""Juros, limites de crédito, baixas e gatilhos de cobrança."""

from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol
from uuid import UUID

from app.modules.crediario.repository import CrediarioRepository
from app.modules.crediario.schemas import (
    BaixaParcelaCreate,
    BaixaParcelaResponse,
    LimiteCreditoResponse,
    ParcelaCreate,
)
from app.shared.exceptions import BusinessRuleError, NotFoundError

CENTAVOS = Decimal("0.01")


class WhatsAppGateway(Protocol):
    def enviar_cobranca(self, telefone: str, mensagem: str) -> None: ...


class CrediarioService:
    def __init__(
        self,
        repository: CrediarioRepository,
        whatsapp_gateway: WhatsAppGateway | None = None,
        taxa_juros_diaria: Decimal = Decimal("0.0033"),
    ) -> None:
        self.repository = repository
        self.whatsapp_gateway = whatsapp_gateway
        self.taxa_juros_diaria = taxa_juros_diaria

    def criar_parcela(self, dados: ParcelaCreate) -> dict:
        limite = self.consultar_limite(dados.cliente_id)
        if dados.valor_original > limite.limite_disponivel:
            raise BusinessRuleError("Limite de crédito insuficiente.")
        return self.repository.criar_parcela(dados)

    def calcular_juros(
        self, saldo: Decimal, vencimento: date, pagamento: date
    ) -> Decimal:
        dias_atraso = max((pagamento - vencimento).days, 0)
        return (saldo * self.taxa_juros_diaria * dias_atraso).quantize(
            CENTAVOS, rounding=ROUND_HALF_UP
        )

    def baixar_parcela(
        self, parcela_id: UUID, dados: BaixaParcelaCreate
    ) -> BaixaParcelaResponse:
        parcela = self.repository.buscar_parcela(parcela_id)
        if not parcela:
            raise NotFoundError("Parcela não encontrada.")
        if parcela["status"] == "paga":
            raise BusinessRuleError("A parcela já está paga.")
        principal = Decimal(str(parcela["saldo_devedor"]))
        juros = self.calcular_juros(principal, date.fromisoformat(parcela["vencimento"]), dados.data_pagamento)
        total = principal + juros
        if dados.valor_pago > total:
            raise BusinessRuleError("O valor pago é maior que o saldo atualizado.")
        saldo_restante = total - dados.valor_pago
        self.repository.baixar_parcela(parcela_id, dados.valor_pago, saldo_restante)
        return BaixaParcelaResponse(
            parcela_id=parcela_id,
            valor_principal=principal,
            juros=juros,
            valor_pago=dados.valor_pago,
            saldo_restante=saldo_restante,
            baixada_em=datetime.now(UTC),
        )

    def consultar_limite(self, cliente_id: UUID) -> LimiteCreditoResponse:
        cliente = self.repository.buscar_cliente(cliente_id)
        if not cliente:
            raise NotFoundError("Cliente não encontrado.")
        limite = Decimal(str(cliente.get("limite_credito", 0)))
        saldo = self.repository.saldo_em_aberto(cliente_id)
        return LimiteCreditoResponse(
            cliente_id=cliente_id,
            limite_total=limite,
            saldo_em_aberto=saldo,
            limite_disponivel=max(limite - saldo, Decimal("0")),
        )

    def disparar_cobranca(self, cliente_id: UUID, mensagem: str) -> None:
        cliente = self.repository.buscar_cliente(cliente_id)
        if not cliente:
            raise NotFoundError("Cliente não encontrado.")
        if not self.whatsapp_gateway:
            raise BusinessRuleError("Gateway de WhatsApp não configurado.")
        self.whatsapp_gateway.enviar_cobranca(cliente["telefone"], mensagem)
