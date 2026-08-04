"""Endpoints de parcelas, baixas e limites."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.database import get_supabase_client
from app.modules.crediario.repository import CrediarioRepository
from app.modules.crediario.schemas import (
    BaixaParcelaCreate,
    BaixaParcelaResponse,
    LimiteCreditoResponse,
    ParcelaCreate,
    ParcelaResponse,
)
from app.modules.crediario.services import CrediarioService

router = APIRouter(prefix="/crediario", tags=["Crediário"])


def get_service() -> CrediarioService:
    return CrediarioService(CrediarioRepository(get_supabase_client()))


Service = Annotated[CrediarioService, Depends(get_service)]


@router.post("/parcelas", response_model=ParcelaResponse, status_code=status.HTTP_201_CREATED)
def criar_parcela(dados: ParcelaCreate, service: Service) -> dict[str, Any]:
    return service.criar_parcela(dados)


@router.post("/parcelas/{parcela_id}/baixa", response_model=BaixaParcelaResponse)
def baixar_parcela(
    parcela_id: UUID, dados: BaixaParcelaCreate, service: Service
) -> BaixaParcelaResponse:
    return service.baixar_parcela(parcela_id, dados)


@router.get("/clientes/{cliente_id}/limite", response_model=LimiteCreditoResponse)
def consultar_limite(cliente_id: UUID, service: Service) -> LimiteCreditoResponse:
    return service.consultar_limite(cliente_id)
