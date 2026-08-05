"""Ponto de entrada da API FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.modules.crediario.router import router as crediario_router
from app.modules.estoque.router import router as estoque_router
from app.modules.vendas.router import router as vendas_router
from app.modules.api import router as public_api_router
from app.modules.auth import router as auth_router
from app.modules.account import router as account_router
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
    app.include_router(account_router, prefix="/api")
    register_exception_handlers(app)

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "status": "online",
            "docs": "/docs",
            "health": "/health/ready",
        }

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        """Liveness: confirma que o processo da API esta respondendo."""
        return {"status": "ok", "api": "online"}

    @app.get("/health/ready", tags=["health"])
    def readiness_check(response: Response) -> dict[str, str]:
        """Readiness: confirma comunicacao real com o Supabase/PostgREST."""
        try:
            check_database_connection()
        except Exception as exc:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "unavailable",
                "api": "online",
                "database": "offline",
                "detail": (
                    "supabase_not_configured"
                    if not settings.supabase_is_configured
                    else type(exc).__name__
                ),
            }
        return {"status": "ok", "api": "online", "database": "online"}

    return app


app = create_app()
