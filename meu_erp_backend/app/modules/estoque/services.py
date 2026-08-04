"""Baixa de estoque por lote e alertas de validade."""

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from app.modules.estoque.repository import EstoqueRepository
from app.modules.estoque.schemas import BaixaEstoqueCreate, LoteCreate, ProdutoCreate
from app.shared.exceptions import BusinessRuleError, NotFoundError


class EstoqueService:
    def __init__(self, repository: EstoqueRepository) -> None:
        self.repository = repository

    def criar_produto(self, dados: ProdutoCreate) -> dict:
        return self.repository.criar_produto(dados)

    def listar_catalogo(self) -> list[dict]:
        return self.repository.listar_catalogo()

    def criar_lote(self, dados: LoteCreate) -> dict:
        return self.repository.criar_lote(dados)

    def baixar_lote(self, lote_id: UUID, dados: BaixaEstoqueCreate) -> dict:
        lote = self.repository.buscar_lote(lote_id)
        if not lote:
            raise NotFoundError("Lote não encontrado.")
        saldo_atual = Decimal(str(lote["saldo"]))
        if dados.quantidade > saldo_atual:
            raise BusinessRuleError("Saldo insuficiente no lote.")
        return self.repository.atualizar_saldo_lote(lote_id, saldo_atual - dados.quantidade)

    def alertas_validade(self, dias: int = 30) -> list[dict]:
        if dias < 0 or dias > 365:
            raise BusinessRuleError("O período deve estar entre 0 e 365 dias.")
        return self.repository.lotes_vencendo_ate(date.today() + timedelta(days=dias))
