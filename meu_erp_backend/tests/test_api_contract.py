"""Garante que o contrato solicitado pelo PDV não regrida."""
from app.main import app


def test_rotas_essenciais_publicadas() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/products", "/api/products/{product_id}/batches", "/api/stock/movements",
        "/api/sales", "/api/sales/{sale_id}/finalize", "/api/customers",
        "/api/receivables/{receivable_id}/payments", "/api/cash-sessions/open",
        "/api/reports/dashboard", "/api/reconciliation/imports", "/api/deliveries",
        "/api/acquirer-fee-rules", "/api/auth/login",
    }
    assert expected <= paths.keys()


def test_finalizacao_exige_idempotency_key() -> None:
    operation = app.openapi()["paths"]["/api/sales/{sale_id}/finalize"]["post"]
    header = next(p for p in operation["parameters"] if p["in"] == "header")
    assert header["name"] == "Idempotency-Key"
