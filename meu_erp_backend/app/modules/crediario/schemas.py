"""Contratos do domínio de crediário."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParcelaCreate(BaseModel):
    cliente_id: UUID
    venda_id: UUID
    numero: int = Field(gt=0)
    valor_original: Decimal = Field(gt=0)
    vencimento: date


class ParcelaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cliente_id: UUID
    venda_id: UUID
    numero: int
    valor_original: Decimal
    saldo_devedor: Decimal
    vencimento: date
    status: str


class BaixaParcelaCreate(BaseModel):
    valor_pago: Decimal = Field(gt=0)
    data_pagamento: date = Field(default_factory=date.today)


class BaixaParcelaResponse(BaseModel):
    parcela_id: UUID
    valor_principal: Decimal
    juros: Decimal
    valor_pago: Decimal
    saldo_restante: Decimal
    baixada_em: datetime


class LimiteCreditoResponse(BaseModel):
    cliente_id: UUID
    limite_total: Decimal
    saldo_em_aberto: Decimal
    limite_disponivel: Decimal
