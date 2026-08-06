import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import type { FastifyInstance } from "fastify";
import { buildApp } from "../src/app.ts";

let app: FastifyInstance;
before(async () => { app = await buildApp(); });
after(async () => { await app.close(); });

test("publica os health checks", async () => {
  const response = await app.inject({ method: "GET", url: "/health" });
  assert.equal(response.statusCode, 200);
  assert.deepEqual(response.json(), { status: "ok", api: "online" });
});

test("protege endpoints operacionais", async () => {
  for (const url of ["/api/products", "/api/customers", "/api/sales"]) {
    const response = await app.inject({ method: "GET", url });
    assert.equal(response.statusCode, 401);
    assert.equal(response.json().error.code, "authentication_error");
  }
});

test("exige chave de idempotência antes de acessar o banco", async () => {
  const response = await app.inject({
    method: "POST", url: "/api/sales/00000000-0000-0000-0000-000000000001/finalize",
    payload: { payments: [{ method: "pix", amount: 10 }] },
  });
  assert.equal(response.statusCode, 422);
  assert.equal(response.json().error.code, "business_rule_violation");
});

test("publica o contrato operacional completo", () => {
  const routes: Array<[string, string]> = [
    ["POST", "/api/auth/register"], ["POST", "/api/auth/login"], ["GET", "/api/auth/me"],
    ["GET", "/api/account"], ["PATCH", "/api/account/fiscal-profile"], ["PUT", "/api/products/:productId/tax-profile"],
    ["GET", "/api/products"], ["POST", "/api/products"], ["GET", "/api/products/:id"], ["PATCH", "/api/products/:id"],
    ["GET", "/api/products/:productId/batches"], ["POST", "/api/products/:productId/batches"], ["POST", "/api/stock/movements"], ["GET", "/api/stock"],
    ["POST", "/api/sales"], ["GET", "/api/sales"], ["GET", "/api/sales/:id"], ["POST", "/api/sales/:saleId/finalize"],
    ["GET", "/api/customers"], ["POST", "/api/customers"], ["GET", "/api/receivables"], ["POST", "/api/receivables/:id/payments"],
    ["POST", "/api/cash-sessions/open"], ["GET", "/api/reports/dashboard"], ["GET", "/api/reports/closures/export"],
    ["GET", "/api/deliveries"], ["POST", "/api/deliveries/:id/status"], ["POST", "/api/reconciliation/imports"],
    ["GET", "/api/reconciliation/issues"], ["GET", "/api/acquirer-fee-rules"], ["DELETE", "/api/acquirer-fee-rules/:id"],
  ];
  for (const [method, url] of routes) assert.equal(app.hasRoute({ method, url }), true, `${method} ${url}`);
});

test("mantém diagnóstico oculto quando desabilitado", async () => {
  const response = await app.inject({ method: "GET", url: "/api/health/supabase" });
  assert.equal(response.statusCode, 404);
});
