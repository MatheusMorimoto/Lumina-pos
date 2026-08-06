import type { FastifyPluginAsync } from "fastify";
import { BusinessRuleError } from "../../core/errors.ts";
import { requestDatabase, requestRepository } from "../../shared/http.ts";
import { batchCreate, movementCreate, productCreate, productPatch, promotionCreate } from "./schemas.ts";

type Id = { id: string };
type ProductId = { productId: string };

export const registerCatalogRoutes: FastifyPluginAsync = async (app) => {
  app.get<{ Querystring: { search?: string; barcode?: string } }>("/products", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    let query = db.from("products").select("*");
    if (request.query.barcode) query = query.eq("barcode", request.query.barcode);
    if (request.query.search) {
      const safe = request.query.search.replaceAll(",", "");
      query = query.or(`name.ilike.%${safe}%,sku.ilike.%${safe}%,barcode.ilike.%${safe}%`);
    }
    return repo.rows(query.order("name"));
  });

  app.post("/products", async (request, reply) => {
    const row = await requestRepository(request).insert("products", productCreate.parse(request.body));
    return reply.status(201).send(row);
  });
  app.get<{ Params: Id }>("/products/:id", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.one(db.from("products").select("*").eq("id", request.params.id).limit(1), "Produto não encontrado.");
  });
  app.patch<{ Params: Id }>("/products/:id", async (request) => {
    const payload = productPatch.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    if (Object.keys(payload).length === 0) return repo.one(db.from("products").select("*").eq("id", request.params.id).limit(1), "Produto não encontrado.");
    return repo.one(db.from("products").update({ ...payload, updated_at: new Date().toISOString() }).eq("id", request.params.id).select(), "Produto não encontrado.");
  });
  app.get<{ Params: ProductId }>("/products/:productId/batches", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    return repo.rows(db.from("inventory_batches").select("*").eq("product_id", request.params.productId).order("expires_at"));
  });
  app.post<{ Params: ProductId }>("/products/:productId/batches", async (request, reply) => {
    const data = batchCreate.parse(request.body); const repo = requestRepository(request);
    const row = await repo.insert("inventory_batches", { ...data, product_id: request.params.productId });
    if (Number(data.quantity) > 0) await repo.insert("stock_movements", {
      product_id: request.params.productId, batch_id: row.id, type: "in", quantity: data.quantity,
      unit_cost: data.purchase_price, reference_type: "batch",
    });
    return reply.status(201).send(row);
  });
  app.post("/stock/movements", async (request, reply) => {
    const data = movementCreate.parse(request.body); const repo = requestRepository(request); const db = requestDatabase(request);
    if (data.batch_id) {
      const batch = await repo.one(db.from("inventory_batches").select("quantity").eq("id", data.batch_id).limit(1), "Lote não encontrado.");
      const delta = ["in", "return"].includes(data.type) ? Number(data.quantity) : -Number(data.quantity);
      const quantity = Number(batch.quantity) + delta;
      if (quantity < 0) throw new BusinessRuleError("Saldo insuficiente no lote.");
      await repo.one(db.from("inventory_batches").update({ quantity: String(quantity) }).eq("id", data.batch_id).select(), "Lote não encontrado.");
    }
    return reply.status(201).send(await repo.insert("stock_movements", data));
  });
  app.get<{ Querystring: { validity?: "expired" | "soon" | "ok" } }>("/stock", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request);
    const today = new Date(); const soon = new Date(today); soon.setUTCDate(soon.getUTCDate() + 30);
    const iso = today.toISOString().slice(0, 10); const soonIso = soon.toISOString().slice(0, 10);
    let query = db.from("inventory_batches").select("*,products(*)").gt("quantity", 0);
    if (request.query.validity === "expired") query = query.lt("expires_at", iso);
    if (request.query.validity === "soon") query = query.gte("expires_at", iso).lte("expires_at", soonIso);
    if (request.query.validity === "ok") query = query.or(`expires_at.is.null,expires_at.gt.${soonIso}`);
    return repo.rows(query.order("expires_at"));
  });
  app.post<{ Params: ProductId }>("/products/:productId/promotions", async (request, reply) => {
    const data = promotionCreate.parse(request.body);
    return reply.status(201).send(await requestRepository(request).insert("promotions", { ...data, product_id: request.params.productId }));
  });
  app.patch<{ Params: Id }>("/promotions/:id", async (request) => {
    const repo = requestRepository(request); const db = requestDatabase(request); const data = promotionCreate.parse(request.body);
    return repo.one(db.from("promotions").update(data).eq("id", request.params.id).select(), "Promoção não encontrada.");
  });
};
