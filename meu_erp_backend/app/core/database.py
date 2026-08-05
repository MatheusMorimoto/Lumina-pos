"""Criação e disponibilização do cliente Supabase."""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import get_settings


def _client_options(*, headers: dict[str, str] | None = None) -> SyncClientOptions:
    settings = get_settings()
    return SyncClientOptions(
        headers=headers or {},
        persist_session=False,
        auto_refresh_token=False,
        postgrest_client_timeout=settings.supabase_timeout_seconds,
        storage_client_timeout=int(settings.supabase_timeout_seconds),
        function_client_timeout=int(settings.supabase_timeout_seconds),
    )


@lru_cache
def get_supabase_client() -> Client:
    """Cria o cliente compartilhado do Supabase sob demanda."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key, _client_options())


@lru_cache
def get_supabase_anon_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.effective_anon_key, _client_options())


@lru_cache
def get_supabase_admin_client() -> Client:
    settings = get_settings()
    if not settings.effective_secret_key:
        raise RuntimeError("ERP_SUPABASE_SECRET_KEY não configurada.")
    return create_client(settings.supabase_url, settings.effective_secret_key, _client_options())


def get_authenticated_client(access_token: str) -> Client:
    """Cria cliente PostgREST que preserva o JWT e, portanto, as políticas RLS."""
    settings = get_settings()
    options = _client_options(headers={"Authorization": f"Bearer {access_token}"})
    return create_client(settings.supabase_url, settings.effective_anon_key, options)


def check_database_connection() -> None:
    """Executa uma consulta minima no PostgREST para validar banco e credenciais."""
    if not get_settings().supabase_is_configured:
        raise RuntimeError(
            "ERP_SUPABASE_URL e ERP_SUPABASE_KEY nao foram configuradas no ambiente."
        )
    get_supabase_client().table("stores").select("id").limit(1).execute()


def unwrap_response(response: Any) -> list[dict[str, Any]]:
    """Normaliza o campo `data` retornado pelo SDK do Supabase."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []
