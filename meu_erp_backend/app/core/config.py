"""Configurações tipadas carregadas do ambiente e do arquivo .env."""

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


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
    supabase_anon_key: str = "local-development-key"
    supabase_secret_key: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    supabase_timeout_seconds: float = Field(default=10, gt=0, le=120)
    supabase_expected_project_id: str = "gfqrqlvkqqnhzwbcozzp"

    diagnostic_enabled: bool = False
    diagnostic_username: str | None = None
    diagnostic_password: str | None = None
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_reset_redirect_url: str | None = None
    legacy_password_login_enabled: bool = False

    @property
    def effective_anon_key(self) -> str:
        """Chave pública usada em operações executadas como o usuário."""
        return self.supabase_anon_key

    @property
    def effective_secret_key(self) -> str | None:
        """Chave administrativa; nunca deve ser exposta ao cliente."""
        return self.supabase_secret_key or self.supabase_service_role_key

    @computed_field
    @property
    def supabase_is_configured(self) -> bool:
        """Indica se a aplicacao deixou de usar os valores locais de exemplo."""
        return not (
            self.supabase_url.rstrip("/") == "http://localhost:54321"
            or self.effective_anon_key == "local-development-key"
        )

    model_config = SettingsConfigDict(
        # Nao depender do diretorio usado para iniciar o servidor.
        env_file=ENV_FILE,
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

    @field_validator("supabase_anon_key")
    @classmethod
    def reject_admin_key_as_anon(cls, value: str) -> str:
        """Impede que uma chave administrativa seja usada no cliente com RLS."""
        if value.startswith("sb_secret_"):
            raise ValueError("ERP_SUPABASE_ANON_KEY nao pode receber uma chave secret.")
        try:
            payload = value.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            role = json.loads(base64.urlsafe_b64decode(payload)).get("role")
        except (IndexError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            role = None
        if role == "service_role":
            raise ValueError("ERP_SUPABASE_ANON_KEY nao pode receber uma chave service_role.")
        return value


@lru_cache
def get_settings() -> Settings:
    """Retorna uma única instância de configurações por processo."""
    return Settings()
