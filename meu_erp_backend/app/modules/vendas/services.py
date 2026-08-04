"""Regras de negócio para PDV, caixa cego e trocas."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.vendas.repository import VendasRepository
from app.modules.vendas.schemas import (
    AberturaCaixaCreate,
    FechamentoCaixaCreate,
    FechamentoCaixaResponse,
    TrocaCreate,
    VendaCreate,
)
from app.shared.exceptions import BusinessRuleError, NotFoundError


class VendasService:
    def __init__(self, repository: VendasRepository) -> None:
        self.repository = repository

    def abrir_caixa(self, dados: AberturaCaixaCreate) -> dict:
        if self.repository.buscar_caixa_aberto_por_operador(dados.operador_id):
            raise BusinessRuleError("O operador já possui um caixa aberto.")
        return self.repository.abrir_caixa(dados)

    def registrar_venda(self, dados: VendaCreate) -> dict:
        caixa = self.repository.buscar_caixa(dados.caixa_id)
        if not caixa:
            raise NotFoundError("Caixa não encontrado.")
        if caixa["status"] != "aberto":
            raise BusinessRuleError("Não é possível vender com o caixa fechado.")
        total = sum((item.subtotal for item in dados.itens), Decimal("0"))
        if total < 0:
            raise BusinessRuleError("O desconto não pode superar o valor da venda.")
        return self.repository.criar_venda(dados, total)

    def fechar_caixa(
        self, caixa_id: UUID, dados: FechamentoCaixaCreate
    ) -> FechamentoCaixaResponse:
        caixa = self.repository.buscar_caixa(caixa_id)
        if not caixa:
            raise NotFoundError("Caixa não encontrado.")
        if caixa["status"] != "aberto":
            raise BusinessRuleError("O caixa já está fechado.")
        esperado = Decimal(str(caixa["saldo_inicial"])) + self.repository.total_movimentado(caixa_id)
        quebra = dados.saldo_informado - esperado
        registro = self.repository.fechar_caixa(caixa_id, dados.saldo_informado, quebra)
        return FechamentoCaixaResponse(
            caixa_id=caixa_id,
            saldo_esperado=esperado,
            saldo_informado=dados.saldo_informado,
            quebra_caixa=quebra,
            fechado_em=registro.get("fechado_em", datetime.now(UTC)),
        )

    def registrar_troca(self, dados: TrocaCreate) -> dict:
        return self.repository.registrar_troca(dados)
