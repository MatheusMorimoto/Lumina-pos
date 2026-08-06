"""Endpoints de produtos, lotes, catálogo e validade."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.database import get_authenticated_client
from app.modules.auth import access_token
from app.modules.estoque.repository import EstoqueRepository
from app.modules.estoque.schemas import (
    BaixaEstoqueCreate,
    LoteCreate,
    LoteResponse,
    ProdutoCreate,
    ProdutoResponse,
)
from app.modules.estoque.services import EstoqueService

router = APIRouter(prefix="/estoque", tags=["Estoque e Catálogo"])


def get_service(token: Annotated[str, Depends(access_token)]) -> EstoqueService:
    return EstoqueService(EstoqueRepository(get_authenticated_client(token)))


Service = Annotated[EstoqueService, Depends(get_service)]


@router.post("/produtos", response_model=ProdutoResponse, status_code=status.HTTP_201_CREATED)
def criar_produto(dados: ProdutoCreate, service: Service) -> dict[str, Any]:
    return service.criar_produto(dados)


@router.get("/catalogo", response_model=list[ProdutoResponse])
def listar_catalogo(service: Service) -> list[dict[str, Any]]:
    return service.listar_catalogo()


@router.post("/lotes", response_model=LoteResponse, status_code=status.HTTP_201_CREATED)
def criar_lote(dados: LoteCreate, service: Service) -> dict[str, Any]:
    return service.criar_lote(dados)


@router.post("/lotes/{lote_id}/baixa", response_model=LoteResponse)
def baixar_lote(
    lote_id: UUID, dados: BaixaEstoqueCreate, service: Service
) -> dict[str, Any]:
    return service.baixar_lote(lote_id, dados)


@router.get("/alertas-validade")
def alertas_validade(
    service: Service, dias: int = Query(default=30, ge=0, le=365)
) -> list[dict[str, Any]]:
    return service.alertas_validade(dias)
