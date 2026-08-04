"""Ponto de entrada da API FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.crediario.router import router as crediario_router
from app.modules.estoque.router import router as estoque_router
from app.modules.vendas.router import router as vendas_router
from app.modules.api import router as public_api_router
from app.modules.auth import router as auth_router
from app.shared.exceptions import register_exception_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Executa tarefas de inicialização e encerramento da aplicação."""
    yield


def create_app() -> FastAPI:
    """Application factory, útil tanto em produção quanto nos testes."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(vendas_router, prefix=settings.api_v1_prefix)
    app.include_router(crediario_router, prefix=settings.api_v1_prefix)
    app.include_router(estoque_router, prefix=settings.api_v1_prefix)
    app.include_router(public_api_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    register_exception_handlers(app)

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
