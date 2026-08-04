"""Criação e disponibilização do cliente Supabase."""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Cria o cliente compartilhado do Supabase sob demanda."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def unwrap_response(response: Any) -> list[dict[str, Any]]:
    """Normaliza o campo `data` retornado pelo SDK do Supabase."""
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []
