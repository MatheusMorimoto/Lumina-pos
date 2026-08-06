import type { FastifyPluginAsync } from "fastify";
import { BusinessRuleError, ConflictError } from "../../core/errors.ts";
import { requestDatabase, requestRepository } from "../../shared/http.ts";
import { cashCloseSchema, cashOpenSchema, finalizeSchema, itemSchema, saleCreate } from "./schemas.ts";

type Id = { id: string };
type SaleId = { saleId: string };
type ItemId = SaleId & { itemId: string };

export const registerSalesRoutes: FastifyPluginAsync = async (app) => {
  app.post("/sales", async (request, reply) => reply.status(201).send(
    await requestRepository(request).insert("sales", saleCreate.parse(request.body)),
  ));
  app.get<{ Querystring: { start?: string; end?: string; payment_method?: string; status?: string } }>("/sales", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request); const queryParams = request.query;
    let query = db.from("sales").select("*,sale_payments(*)");
    if (queryParams.start) query = query.gte("created_at", queryParams.start);
    if (queryParams.end) {
      const exclusive = new Date(`${queryParams.end}T00:00:00Z`); exclusive.setUTCDate(exclusive.getUTCDate() + 1);
      query = query.lt("created_at", exclusive.toISOString().slice(0, 10));
    }
    if (queryParams.status) query = query.eq("status", queryParams.status);
    const rows = await repo.rows(query.order("created_at", { ascending: false }));
    if (!queryParams.payment_method) return rows;
    return rows.filter((row) => (row.sale_payments as Array<{ method?: string }> | undefined)?.some((p) => p.method === queryParams.payment_method));
  });
  app.get<{ Params: Id }>("/sales/:id", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.one(db.from("sales").select("*,sale_items(*,products(*)),sale_payments(*)").eq("id", request.params.id).limit(1), "Venda não encontrada.");
  });
  app.post<{ Params: SaleId }>("/sales/:saleId/items", async (request, reply) => {
    const data = itemSchema.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    const sale = await repo.one(db.from("sales").select("status").eq("id", request.params.saleId).limit(1), "Venda não encontrada.");
    if (sale.status !== "open") throw new BusinessRuleError("A venda não está aberta.");
    return reply.status(201).send(await repo.insert("sale_items", { ...data, sale_id: request.params.saleId }));
  });
  app.patch<{ Params: ItemId }>("/sales/:saleId/items/:itemId", async (request) => {
    const data = itemSchema.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.one(db.from("sale_items").update(data).eq("id", request.params.itemId).eq("sale_id", request.params.saleId).select(), "Item não encontrado.");
  });
  app.delete<{ Params: ItemId }>("/sales/:saleId/items/:itemId", async (request, reply) => {
    const db = requestDatabase(request); const { error } = await db.from("sale_items").delete().eq("id", request.params.itemId).eq("sale_id", request.params.saleId);
    if (error) throw new ConflictError("Não foi possível remover o item.");
    return reply.status(204).send();
  });
  app.post<{ Params: SaleId }>("/sales/:saleId/finalize", async (request) => {
    const key = request.headers["idempotency-key"];
    if (typeof key !== "string" || !key) throw new BusinessRuleError("O cabeçalho Idempotency-Key é obrigatório.");
    const data = finalizeSchema.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    const rows = await repo.rows(db.rpc("finalize_sale", {
      p_sale_id: request.params.saleId, p_payments: data.payments, p_idempotency_key: key,
    }));
    if (!rows[0]) throw new ConflictError("Não foi possível finalizar a venda.");
    return rows[0];
  });
  app.post<{ Params: SaleId }>("/sales/:saleId/cancel", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    const sale = await repo.one(db.from("sales").select("*").eq("id", request.params.saleId).limit(1), "Venda não encontrada.");
    if (sale.status === "cancelled") return sale;
    if (sale.status === "completed") throw new BusinessRuleError("Cancelamento de venda concluída exige estorno de estoque.");
    return repo.one(db.from("sales").update({ status: "cancelled", cancelled_at: new Date().toISOString() }).eq("id", request.params.saleId).select(), "Venda não encontrada.");
  });
  app.post("/cash-sessions/open", async (request, reply) => reply.status(201).send(
    await requestRepository(request).insert("cash_sessions", cashOpenSchema.parse(request.body)),
  ));
  app.get<{ Querystring: { cash_register_id?: string; user_id?: string } }>("/cash-sessions/current", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request); let query = db.from("cash_sessions").select("*").eq("status", "open");
    if (request.query.cash_register_id) query = query.eq("cash_register_id", request.query.cash_register_id);
    if (request.query.user_id) query = query.eq("user_id", request.query.user_id);
    return repo.one(query.limit(1), "Não há sessão de caixa aberta.");
  });
  app.post<{ Params: Id }>("/cash-sessions/:id/close", async (request) => {
    const { declared_amount } = cashCloseSchema.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    const session = await repo.one(db.from("cash_sessions").select("*").eq("id", request.params.id).limit(1), "Sessão não encontrada.");
    if (session.status !== "open") throw new BusinessRuleError("O caixa já está fechado.");
    const payments = await repo.rows(db.from("sale_payments").select("amount,sales!inner(cash_session_id,status)").eq("sales.cash_session_id", request.params.id).eq("sales.status", "completed"));
    const expected = Number(session.opening_amount) + payments.reduce((total, payment) => total + Number(payment.amount), 0);
    const declared = Number(declared_amount);
    return repo.one(db.from("cash_sessions").update({
      status: "closed", closed_at: new Date().toISOString(), declared_amount,
      expected_amount: String(expected), difference: String(declared - expected),
    }).eq("id", request.params.id).select(), "Sessão não encontrada.");
  });
};
