"""Testes unitários de juros, limites e baixas de parcelas."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.crediario.schemas import BaixaParcelaCreate
from app.modules.crediario.services import CrediarioService
from app.shared.exceptions import BusinessRuleError


class FakeCrediarioRepository:
    def __init__(self) -> None:
        self.parcela = {
            "saldo_devedor": "100.00",
            "vencimento": "2026-07-01",
            "status": "aberta",
        }

    def buscar_parcela(self, _parcela_id):
        return self.parcela

    def baixar_parcela(self, parcela_id, valor_pago, saldo_restante):
        return {"id": parcela_id, "saldo_devedor": saldo_restante}


def test_calcula_juros_simples_por_dia() -> None:
    service = CrediarioService(FakeCrediarioRepository())  # type: ignore[arg-type]

    juros = service.calcular_juros(
        Decimal("100.00"), date(2026, 7, 1), date(2026, 7, 11)
    )

    assert juros == Decimal("3.30")


def test_nao_aplica_juros_antes_do_vencimento() -> None:
    service = CrediarioService(FakeCrediarioRepository())  # type: ignore[arg-type]
    assert service.calcular_juros(
        Decimal("100.00"), date(2026, 7, 10), date(2026, 7, 1)
    ) == Decimal("0.00")


def test_rejeita_pagamento_superior_ao_saldo_atualizado() -> None:
    service = CrediarioService(FakeCrediarioRepository())  # type: ignore[arg-type]

    with pytest.raises(BusinessRuleError, match="maior"):
        service.baixar_parcela(
            uuid4(),
            BaixaParcelaCreate(
                valor_pago=Decimal("200.00"), data_pagamento=date(2026, 7, 2)
            ),
        )
