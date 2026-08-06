import type { FastifyPluginAsync } from "fastify";
import { z } from "zod";
import { requestDatabase, requestRepository } from "../../shared/http.ts";

const delivery = z.object({
  sale_id: z.uuid(), customer_id: z.uuid().nullable().optional(), courier_id: z.uuid().nullable().optional(),
  address: z.record(z.string(), z.unknown()), scheduled_at: z.iso.datetime({ offset: true }).nullable().optional(),
});
const statusSchema = z.object({ status: z.string().min(1), user_id: z.uuid() });
type Id = { id: string };

export const registerDeliveryRoutes: FastifyPluginAsync = async (app) => {
  app.get<{ Querystring: { status?: string } }>("/deliveries", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request); let query = db.from("deliveries").select("*,customers(*),couriers(*)");
    if (request.query.status) query = query.eq("status", request.query.status); return repo.rows(query);
  });
  app.post("/deliveries", async (request, reply) => reply.status(201).send(await requestRepository(request).insert("deliveries", delivery.parse(request.body))));
  app.get<{ Params: Id }>("/deliveries/:id", async (request) => { const db = requestDatabase(request); const repo = requestRepository(request); return repo.one(db.from("deliveries").select("*,delivery_status_history(*)").eq("id", request.params.id).limit(1), "Entrega não encontrada."); });
  app.patch<{ Params: Id }>("/deliveries/:id", async (request) => { const db = requestDatabase(request); const repo = requestRepository(request); return repo.one(db.from("deliveries").update(delivery.partial().parse(request.body)).eq("id", request.params.id).select(), "Entrega não encontrada."); });
  app.post<{ Params: Id }>("/deliveries/:id/status", async (request) => {
    const data = statusSchema.parse(request.body); const db = requestDatabase(request); const repo = requestRepository(request);
    const old = await repo.one(db.from("deliveries").select("status").eq("id", request.params.id).limit(1), "Entrega não encontrada.");
    const row = await repo.one(db.from("deliveries").update({ status: data.status, delivered_at: data.status === "delivered" ? new Date().toISOString() : null }).eq("id", request.params.id).select(), "Entrega não encontrada.");
    await repo.insert("delivery_status_history", { delivery_id: request.params.id, old_status: old.status, new_status: data.status, user_id: data.user_id }); return row;
  });
  app.post<{ Params: Id }>("/deliveries/:id/assign-courier", async (request) => {
    const { courier_id } = z.object({ courier_id: z.uuid() }).parse(request.body); const db = requestDatabase(request); const repo = requestRepository(request);
    return repo.one(db.from("deliveries").update({ courier_id }).eq("id", request.params.id).select(), "Entrega não encontrada.");
  });
};
