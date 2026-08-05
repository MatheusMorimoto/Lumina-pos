"""Configurações tipadas carregadas do ambiente e do arquivo .env."""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração central da aplicação."""

    app_name: str = "Sistema Integrado de Gestão Comercial"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    supabase_url: str = "http://localhost:54321"
    supabase_key: str = "local-development-key"
    supabase_anon_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @property
    def effective_anon_key(self) -> str:
        """Chave pública usada em operações executadas como o usuário."""
        return self.supabase_anon_key or self.supabase_key

    @property
    def effective_secret_key(self) -> str | None:
        """Chave administrativa; nunca deve ser exposta ao cliente."""
        return self.supabase_secret_key or self.supabase_service_role_key

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ERP_",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    """Retorna uma única instância de configurações por processo."""
    return Settings()
