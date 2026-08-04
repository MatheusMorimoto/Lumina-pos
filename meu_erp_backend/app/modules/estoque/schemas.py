"""Contratos do domínio de estoque."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProdutoCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    nome: str = Field(min_length=2, max_length=200)
    preco_venda: Decimal = Field(ge=0)
    estoque_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    ativo: bool = True


class ProdutoResponse(ProdutoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    criado_em: datetime


class LoteCreate(BaseModel):
    produto_id: UUID
    codigo_lote: str = Field(min_length=1, max_length=80)
    quantidade: Decimal = Field(gt=0)
    validade: date | None = None


class LoteResponse(LoteCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    saldo: Decimal


class BaixaEstoqueCreate(BaseModel):
    quantidade: Decimal = Field(gt=0)
    motivo: str = Field(min_length=3, max_length=200)
