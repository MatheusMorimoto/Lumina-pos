"""Testes unitários das regras de vendas e fechamento de caixa."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.vendas.schemas import (
    FechamentoCaixaCreate,
    FormaPagamento,
    ItemVendaCreate,
    VendaCreate,
)
from app.modules.vendas.services import VendasService
from app.shared.exceptions import BusinessRuleError


class FakeVendasRepository:
    def __init__(self, status: str = "aberto") -> None:
        self.caixa = {"status": status, "saldo_inicial": "100.00"}
        self.total_recebido: Decimal | None = None

    def buscar_caixa(self, _caixa_id):
        return self.caixa

    def criar_venda(self, _dados, total):
        self.total_recebido = total
        return {"total": total}

    def total_movimentado(self, _caixa_id):
        return Decimal("250.00")

    def fechar_caixa(self, caixa_id, saldo_informado, quebra_caixa):
        return {"fechado_em": datetime.now(UTC)}


def test_calcula_total_da_venda() -> None:
    repository = FakeVendasRepository()
    service = VendasService(repository)  # type: ignore[arg-type]
    venda = VendaCreate(
        caixa_id=uuid4(),
        itens=[
            ItemVendaCreate(
                produto_id=uuid4(),
                quantidade=Decimal("2"),
                preco_unitario=Decimal("10"),
                desconto=Decimal("1"),
            )
        ],
        forma_pagamento=FormaPagamento.PIX,
    )

    service.registrar_venda(venda)

    assert repository.total_recebido == Decimal("19")


def test_impede_venda_com_caixa_fechado() -> None:
    service = VendasService(FakeVendasRepository(status="fechado"))  # type: ignore[arg-type]
    venda = VendaCreate(
        caixa_id=uuid4(),
        itens=[
            ItemVendaCreate(
                produto_id=uuid4(), quantidade=1, preco_unitario=10
            )
        ],
        forma_pagamento=FormaPagamento.DINHEIRO,
    )

    with pytest.raises(BusinessRuleError, match="caixa fechado"):
        service.registrar_venda(venda)


def test_calcula_quebra_de_caixa() -> None:
    service = VendasService(FakeVendasRepository())  # type: ignore[arg-type]
    resultado = service.fechar_caixa(
        uuid4(), FechamentoCaixaCreate(saldo_informado=Decimal("345.00"))
    )

    assert resultado.saldo_esperado == Decimal("350.00")
    assert resultado.quebra_caixa == Decimal("-5.00")
