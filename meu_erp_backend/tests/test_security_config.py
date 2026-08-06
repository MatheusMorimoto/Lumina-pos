import base64
import json

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def fake_jwt(role: str) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{encoded}.signature"


def test_anon_key_rejects_service_role_jwt() -> None:
    with pytest.raises(ValidationError, match="service_role"):
        Settings(_env_file=None, supabase_anon_key=fake_jwt("service_role"))


def test_anon_key_rejects_modern_secret_key() -> None:
    with pytest.raises(ValidationError, match="chave secret"):
        Settings(_env_file=None, supabase_anon_key="sb_secret_example")


def test_anon_key_accepts_publishable_key() -> None:
    settings = Settings(_env_file=None, supabase_anon_key="sb_publishable_example")
    assert settings.effective_anon_key == "sb_publishable_example"
