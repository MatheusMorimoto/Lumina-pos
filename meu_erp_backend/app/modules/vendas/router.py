"""Endpoints HTTP do domínio de vendas."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.database import get_authenticated_client
from app.modules.auth import access_token
from app.modules.vendas.repository import VendasRepository
from app.modules.vendas.schemas import (
    AberturaCaixaCreate,
    CaixaResponse,
    FechamentoCaixaCreate,
    FechamentoCaixaResponse,
    TrocaCreate,
    VendaCreate,
    VendaResponse,
)
from app.modules.vendas.services import VendasService

router = APIRouter(prefix="/vendas", tags=["Vendas e PDV"])


def get_service(token: Annotated[str, Depends(access_token)]) -> VendasService:
    return VendasService(VendasRepository(get_authenticated_client(token)))


Service = Annotated[VendasService, Depends(get_service)]


@router.post("/caixas", response_model=CaixaResponse, status_code=status.HTTP_201_CREATED)
def abrir_caixa(dados: AberturaCaixaCreate, service: Service) -> dict[str, Any]:
    return service.abrir_caixa(dados)


@router.post("/", response_model=VendaResponse, status_code=status.HTTP_201_CREATED)
def registrar_venda(dados: VendaCreate, service: Service) -> dict[str, Any]:
    return service.registrar_venda(dados)


@router.post("/caixas/{caixa_id}/fechamento", response_model=FechamentoCaixaResponse)
def fechar_caixa(
    caixa_id: UUID, dados: FechamentoCaixaCreate, service: Service
) -> FechamentoCaixaResponse:
    return service.fechar_caixa(caixa_id, dados)


@router.post("/trocas", status_code=status.HTTP_201_CREATED)
def registrar_troca(dados: TrocaCreate, service: Service) -> dict[str, Any]:
    return service.registrar_troca(dados)
