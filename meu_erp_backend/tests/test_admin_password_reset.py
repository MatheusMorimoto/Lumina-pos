from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.modules import auth


USER_ID = "00000000-0000-0000-0000-000000000003"
STORE_ID = "00000000-0000-0000-0000-000000000002"
ACTOR_ID = "00000000-0000-0000-0000-000000000001"


class Query:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args): return self
    def eq(self, *_args): return self
    def limit(self, *_args): return self
    def execute(self): return SimpleNamespace(data=self.rows)


class AuthenticatedClient:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return Query(self.rows)


class AdminClient:
    def __init__(self):
        self.auth = self
        self.admin = self
        self.password_updates = []
        self.audit_rows = []

    def update_user_by_id(self, user_id, attributes):
        self.password_updates.append((user_id, attributes))

    def table(self, name):
        assert name == "audit_logs"
        return self

    def insert(self, row):
        self.audit_rows.append(row)
        return self

    def execute(self):
        return SimpleNamespace(data=self.audit_rows)


def actor(role="owner"):
    return {"id": ACTOR_ID, "role": role, "store_id": STORE_ID}


def request_payload():
    return {"password": "NovaSenha123", "password_confirmation": "NovaSenha123"}


def test_admin_resets_password_and_audits_without_storing_credential(monkeypatch):
    admin = AdminClient()
    app.dependency_overrides[auth.access_token] = lambda: "actor-token"
    app.dependency_overrides[auth.current_user] = actor
    monkeypatch.setattr(
        auth, "get_authenticated_client", lambda _token: AuthenticatedClient([{"id": USER_ID}])
    )
    monkeypatch.setattr(auth, "get_supabase_admin_client", lambda: admin)
    try:
        response = TestClient(app).post(
            f"/api/auth/admin/users/{USER_ID}/password", json=request_payload()
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert admin.password_updates == [(USER_ID, {"password": "NovaSenha123"})]
    assert admin.audit_rows[0]["action"] == "password_reset_by_admin"
    assert "NovaSenha123" not in str(admin.audit_rows[0])
    assert "password" not in admin.audit_rows[0]["data"]
    assert "NovaSenha123" not in response.text


def test_non_admin_cannot_reset_password(monkeypatch):
    app.dependency_overrides[auth.access_token] = lambda: "actor-token"
    app.dependency_overrides[auth.current_user] = lambda: actor("cashier")
    monkeypatch.setattr(
        auth, "get_supabase_admin_client", lambda: (_ for _ in ()).throw(AssertionError())
    )
    try:
        response = TestClient(app).post(
            f"/api/auth/admin/users/{USER_ID}/password", json=request_payload()
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "authorization_error"


def test_admin_cannot_reset_user_outside_own_store(monkeypatch):
    app.dependency_overrides[auth.access_token] = lambda: "actor-token"
    app.dependency_overrides[auth.current_user] = actor
    monkeypatch.setattr(auth, "get_authenticated_client", lambda _token: AuthenticatedClient([]))
    try:
        response = TestClient(app).post(
            f"/api/auth/admin/users/{USER_ID}/password", json=request_payload()
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
