import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { extname, join } from "node:path";
import type { FastifyPluginAsync } from "fastify";
import { z } from "zod";
import { BusinessRuleError, ConflictError } from "../../core/errors.ts";
import { requestDatabase, requestRepository } from "../../shared/http.ts";

type Id = { id: string };
const payloadSchema = z.record(z.string(), z.unknown());

export const registerReconciliationRoutes: FastifyPluginAsync = async (app) => {
  app.post<{ Querystring: { store_id?: string } }>("/reconciliation/imports", async (request, reply) => {
    const part = await request.file();
    const storeId = request.query.store_id;
    if (!part || !storeId) throw new BusinessRuleError("Arquivo e store_id são obrigatórios.");
    const extension = extname(part.filename).toLowerCase();
    if (![".csv", ".ofx", ".xlsx"].includes(extension)) throw new BusinessRuleError("Formato não permitido. Use CSV, OFX ou XLSX.");
    const content = await part.toBuffer();
    const digest = createHash("sha256").update(content).digest("hex");
    const db = requestDatabase(request); const repo = requestRepository(request);
    const existing = await repo.rows(db.from("reconciliation_imports").select("id").eq("file_hash", digest).limit(1));
    if (existing.length) throw new ConflictError("Este arquivo já foi importado.");
    const directory = join(process.cwd(), "data", "reconciliation");
    await mkdir(directory, { recursive: true });
    const path = join(directory, `${digest}${extension}`);
    await writeFile(path, content, { flag: "wx" }).catch((error: NodeJS.ErrnoException) => {
      if (error.code !== "EEXIST") throw error;
    });
    return reply.status(202).send(await repo.insert("reconciliation_imports", {
      store_id: storeId, file_path: path, format: extension.slice(1), file_hash: digest,
      file_size: content.length, status: "pending",
    }));
  });
  app.get<{ Params: Id }>("/reconciliation/imports/:id", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request);
    return repo.one(db.from("reconciliation_imports").select("*").eq("id", request.params.id).limit(1), "Importação não encontrada.");
  });
  app.get("/reconciliation/transactions", async (request) => {
    const db = requestDatabase(request); return requestRepository(request).rows(db.from("acquirer_transactions").select("*"));
  });
  app.post("/reconciliation/run", async (_request, reply) => reply.status(202).send({ status: "queued" }));
  app.get<{ Querystring: { status?: string } }>("/reconciliation/issues", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request); let query = db.from("reconciliation_issues").select("*");
    if (request.query.status) query = query.eq("status", request.query.status); return repo.rows(query);
  });
  app.patch<{ Params: Id }>("/reconciliation/issues/:id", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request);
    return repo.one(db.from("reconciliation_issues").update(payloadSchema.parse(request.body)).eq("id", request.params.id).select(), "Pendência não encontrada.");
  });
  app.get("/acquirer-fee-rules", async (request) => {
    const db = requestDatabase(request); return requestRepository(request).rows(db.from("acquirer_fee_rules").select("*"));
  });
  app.post("/acquirer-fee-rules", async (request, reply) => reply.status(201).send(
    await requestRepository(request).insert("acquirer_fee_rules", payloadSchema.parse(request.body)),
  ));
  app.get<{ Params: Id }>("/acquirer-fee-rules/:id", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request);
    return repo.one(db.from("acquirer_fee_rules").select("*").eq("id", request.params.id).limit(1), "Regra não encontrada.");
  });
  app.patch<{ Params: Id }>("/acquirer-fee-rules/:id", async (request) => {
    const db = requestDatabase(request); const repo = requestRepository(request);
    return repo.one(db.from("acquirer_fee_rules").update(payloadSchema.parse(request.body)).eq("id", request.params.id).select(), "Regra não encontrada.");
  });
  app.delete<{ Params: Id }>("/acquirer-fee-rules/:id", async (request, reply) => {
    const db = requestDatabase(request); const { error } = await db.from("acquirer_fee_rules").delete().eq("id", request.params.id);
    if (error) throw new ConflictError("Não foi possível remover a regra."); return reply.status(204).send();
  });
};
