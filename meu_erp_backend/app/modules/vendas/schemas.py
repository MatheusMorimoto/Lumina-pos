"""Contratos de entrada e saída do domínio de vendas."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FormaPagamento(StrEnum):
    DINHEIRO = "dinheiro"
    PIX = "pix"
    CARTAO_CREDITO = "cartao_credito"
    CARTAO_DEBITO = "cartao_debito"
    CREDIARIO = "crediario"


class ItemVendaCreate(BaseModel):
    produto_id: UUID
    quantidade: Decimal = Field(gt=0)
    preco_unitario: Decimal = Field(ge=0)
    desconto: Decimal = Field(default=Decimal("0"), ge=0)

    @property
    def subtotal(self) -> Decimal:
        return self.quantidade * self.preco_unitario - self.desconto


class VendaCreate(BaseModel):
    caixa_id: UUID
    cliente_id: UUID | None = None
    itens: list[ItemVendaCreate] = Field(min_length=1)
    forma_pagamento: FormaPagamento


class VendaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    caixa_id: UUID
    cliente_id: UUID | None = None
    total: Decimal
    forma_pagamento: FormaPagamento
    status: str
    criada_em: datetime


class AberturaCaixaCreate(BaseModel):
    operador_id: UUID
    saldo_inicial: Decimal = Field(ge=0)


class FechamentoCaixaCreate(BaseModel):
    saldo_informado: Decimal = Field(ge=0)


class FechamentoCaixaResponse(BaseModel):
    caixa_id: UUID
    saldo_esperado: Decimal
    saldo_informado: Decimal
    quebra_caixa: Decimal
    fechado_em: datetime


class TrocaCreate(BaseModel):
    venda_id: UUID
    item_venda_id: UUID
    quantidade: Decimal = Field(gt=0)
    motivo: str = Field(min_length=3, max_length=300)


class CaixaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    operador_id: UUID
    saldo_inicial: Decimal
    status: str
    aberto_em: datetime

    @model_validator(mode="after")
    def validar_status(self) -> "CaixaResponse":
        if self.status not in {"aberto", "fechado"}:
            raise ValueError("Status de caixa desconhecido.")
        return self
