"""Exceções de aplicação e handlers HTTP globais."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ApplicationError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "application_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BusinessRuleError(ApplicationError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "business_rule_violation"


class NotFoundError(ApplicationError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class AuthenticationError(ApplicationError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"


class ConflictError(ApplicationError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class RateLimitError(ApplicationError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limit_exceeded"


class UpstreamError(ApplicationError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "supabase_unavailable"


def register_exception_handlers(app: FastAPI) -> None:
    """Registra o formato consistente de erros da aplicação."""

    @app.exception_handler(ApplicationError)
    async def application_error_handler(
        _: Request, exc: ApplicationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
