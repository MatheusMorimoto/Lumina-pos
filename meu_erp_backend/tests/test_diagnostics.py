"""Contrato do diagnostico temporario sem depender do Supabase remoto."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.modules import auth, diagnostics


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args, **_kwargs): return self
    def eq(self, *_args, **_kwargs): return self
    def limit(self, *_args, **_kwargs): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class AuthClient:
    def __init__(self, profile=True):
        self.profile = profile
        self.auth = self

    def sign_in_with_password(self, _credentials):
        user = SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001",
            email="user@example.com",
            email_confirmed_at="2026-01-01T00:00:00Z",
        )
        session = SimpleNamespace(
            access_token="test-access-token", refresh_token="test-refresh-token",
            expires_in=3600, expires_at=123456789, user=user,
        )
        return SimpleNamespace(session=session, user=user)

    def table(self, name):
        if name == "users" and self.profile:
            return Query([{
                "id": "00000000-0000-0000-0000-000000000001",
                "name": "Pessoa Teste", "email": "user@example.com", "active": True,
                "store_id": "00000000-0000-0000-0000-000000000002", "role": "owner",
            }])
        if name == "individual_registrations" and self.profile:
            return Query([{"full_name": "Pessoa Teste", "cpf": "52998224725"}])
        return Query([])


def enable_diagnostics():
    settings = get_settings()
    settings.diagnostic_enabled = True
    settings.diagnostic_username = "admin"
    settings.diagnostic_password = "temporary-test-secret"
    return settings


def test_diagnostic_is_disabled_by_default():
    settings = get_settings()
    old = settings.diagnostic_enabled
    settings.diagnostic_enabled = False
    try:
        assert TestClient(app).get("/teste-conexao").status_code == 404
    finally:
        settings.diagnostic_enabled = old


def test_supabase_health_never_returns_keys(monkeypatch):
    settings = enable_diagnostics()
    monkeypatch.setattr(diagnostics, "check_database_connection", lambda: None)
    monkeypatch.setattr(diagnostics, "supabase_project_id", lambda: settings.supabase_expected_project_id)
    response = TestClient(app).get(
        "/api/health/supabase", auth=("admin", "temporary-test-secret")
    )
    assert response.status_code == 200
    assert response.json()["supabase"] == "connected"
    body = response.text.lower()
    assert "publishable_key_configured" in body
    assert "secret_key_configured" in body
    assert "sb_publishable_" not in body
    assert "sb_secret_" not in body


def test_login_reports_profile_without_exposing_token_in_metadata(monkeypatch):
    fake = AuthClient(profile=True)
    monkeypatch.setattr(auth, "get_supabase_anon_client", lambda: fake)
    monkeypatch.setattr(auth, "get_authenticated_client", lambda _token: fake)
    response = TestClient(app).post(
        "/api/auth/login", json={"email": "USER@example.com", "password": "not-logged"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["authentication"]["token_received"] is True
    assert "token" not in data["authentication"]
    assert data["profile"]["found"] is True
    assert data["profile"]["cpf_masked"] == "529.***.***-25"


def test_login_succeeds_when_operational_profile_is_missing(monkeypatch):
    fake = AuthClient(profile=False)
    monkeypatch.setattr(auth, "get_supabase_anon_client", lambda: fake)
    monkeypatch.setattr(auth, "get_authenticated_client", lambda _token: fake)
    response = TestClient(app).post(
        "/api/auth/login", json={"email": "user@example.com", "password": "not-logged"}
    )
    assert response.status_code == 200
    assert response.json()["authentication"]["success"] is True
    assert response.json()["profile"]["found"] is False
