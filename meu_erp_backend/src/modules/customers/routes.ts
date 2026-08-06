import type { FastifyPluginAsync } from "fastify";
import { z } from "zod";
import { NotFoundError } from "../../core/errors.ts";
import { requestDatabase, requestRepository } from "../../shared/http.ts";

const decimal = z.union([z.number(), z.string()]).transform(String);
const customerSchema = z.object({
  store_id: z.uuid(), name: z.string().min(1), document: z.string().nullable().optional(),
  phone: z.string().nullable().optional(), email: z.email().nullable().optional(),
  credit_limit: decimal.default("0"), active: z.boolean().default(true),
});
const paymentSchema = z.object({
  amount: decimal.refine((value) => Number(value) > 0), payment_method: z.string().min(1),
  user_id: z.uuid(), paid_at: z.iso.datetime({ offset: true }).nullable().optional(),
});

type Id = { id: string };

export const registerCustomerRoutes: FastifyPluginAsync = async (app) => {
  app.get<{ Querystring: { search?: string; credit_status?: string } }>("/customers", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request); let query = db.from("customers").select("*");
    if (request.query.search) {
      const safe = request.query.search.replaceAll(",", "");
      query = query.or(`name.ilike.%${safe}%,document.ilike.%${safe}%`);
    }
    const rows = await repo.rows(query.order("name"));
    if (!request.query.credit_status) return rows;
    const today = new Date().toISOString().slice(0, 10);
    const classified = await Promise.all(rows.map(async (row) => {
      const open = await repo.rows(db.from("receivables").select("open_amount,due_date").eq("customer_id", String(row.id)).gt("open_amount", 0));
      const credit_status = open.some((item) => String(item.due_date) < today) ? "overdue" : open.length ? "open" : "clear";
      return { ...row, credit_status };
    }));
    return classified.filter((row) => row.credit_status === request.query.credit_status);
  });
  app.post("/customers", async (request, reply) => reply.status(201).send(
    await requestRepository(request).insert("customers", customerSchema.parse(request.body)),
  ));
  app.get<{ Params: Id }>("/customers/:id", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.one(db.from("customers").select("*").eq("id", request.params.id).limit(1), "Cliente não encontrado.");
  });
  app.patch<{ Params: Id }>("/customers/:id", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.one(db.from("customers").update(customerSchema.partial().parse(request.body)).eq("id", request.params.id).select(), "Cliente não encontrado.");
  });
  app.get<{ Params: Id }>("/customers/:id/receivables", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.rows(db.from("receivables").select("*,receivable_payments(*)").eq("customer_id", request.params.id));
  });
  app.get<{ Querystring: { status?: string } }>("/receivables", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request); let query = db.from("receivables").select("*,customers(*)");
    if (request.query.status === "overdue") query = query.gt("open_amount", 0).lt("due_date", new Date().toISOString().slice(0, 10));
    else if (request.query.status) query = query.eq("status", request.query.status);
    return repo.rows(query.order("due_date"));
  });
  app.post<{ Params: Id }>("/receivables/:id/payments", async (request, reply) => {
    const data = paymentSchema.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    const rows = await repo.rows(db.rpc("pay_receivable", {
      p_receivable_id: request.params.id, p_amount: data.amount, p_method: data.payment_method,
      p_user_id: data.user_id, p_paid_at: data.paid_at ?? new Date().toISOString(),
    }));
    if (!rows[0]) throw new NotFoundError("Conta a receber não encontrada.");
    return reply.status(201).send(rows[0]);
  });
};
