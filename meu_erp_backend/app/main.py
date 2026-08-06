"""Ponto de entrada da API FastAPI."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.modules.api import router as public_api_router
from app.modules.auth import router as auth_router
from app.modules.account import router as account_router
from app.modules.diagnostics import api_router as diagnostics_api_router
from app.modules.diagnostics import page_router as diagnostics_page_router
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
        # O wildcard nao pode ser combinado com credenciais CORS em navegadores.
        # A API usa Authorization: Bearer, portanto cookies nao sao necessarios.
        allow_credentials="*" not in settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Os antigos endpoints /api/v1 usavam um cliente compartilhado sem o JWT
    # da requisicao. Eles permanecem fora da aplicacao ate serem migrados para
    # o mesmo modelo autenticado e protegido por RLS usado em /api.
    app.include_router(public_api_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(account_router, prefix="/api")
    app.include_router(diagnostics_api_router, prefix="/api")
    app.include_router(diagnostics_page_router)
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
