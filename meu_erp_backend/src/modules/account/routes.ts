import type { FastifyPluginAsync, FastifyRequest } from "fastify";
import { z } from "zod";
import { authenticatedClient, Repository } from "../../core/database.ts";
import { AuthorizationError, NotFoundError } from "../../core/errors.ts";
import { currentUser } from "../auth/service.ts";

const accountPatch = z.object({
  name: z.string().min(2).max(200).optional(), phone: z.string().optional(), postal_code: z.string().optional(),
  street: z.string().optional(), address_number: z.string().optional(), complement: z.string().nullable().optional(),
  neighborhood: z.string().optional(), city: z.string().optional(), state: z.string().length(2).optional(),
});
const fiscalPatch = z.object({
  tax_regime: z.enum(["mei", "simples_nacional", "lucro_presumido", "lucro_real", "pessoa_fisica", "nao_informado"]),
  regime_source: z.string().nullable().optional(), manually_reviewed: z.boolean().default(true),
});
const taxProfile = z.object({
  ncm: z.string().length(8), cest: z.string().max(7).nullable().optional(), merchandise_origin: z.string().min(1).max(2),
  cfop: z.string().length(4), cst_csosn: z.string().max(4).nullable().optional(), pis_cst: z.string().max(3).nullable().optional(),
  cofins_cst: z.string().max(3).nullable().optional(), icms_rate: z.number().min(0).max(100).default(0),
  pis_rate: z.number().min(0).max(100).default(0), cofins_rate: z.number().min(0).max(100).default(0),
  ipi_rate: z.number().min(0).max(100).default(0), fcp_rate: z.number().min(0).max(100).default(0),
  destination_state: z.string().length(2).nullable().optional(), operation_type: z.enum(["sale", "purchase", "return", "transfer"]).default("sale"),
  valid_from: z.iso.date().default(() => new Date().toISOString().slice(0, 10)), valid_until: z.iso.date().nullable().optional(),
  manually_reviewed: z.boolean().default(false),
});

async function context(request: FastifyRequest) {
  const user = await currentUser(request);
  return { user, db: authenticatedClient(user.access_token), repo: new Repository(authenticatedClient(user.access_token)) };
}
function requireAdmin(role: string | null): void {
  if (!role || !["owner", "admin"].includes(role)) throw new AuthorizationError("Apenas proprietário ou administrador pode alterar dados fiscais.");
}

export const registerAccountRoutes: FastifyPluginAsync = async (app) => {
  app.get("/account", async (request) => {
    const { user, db, repo } = await context(request);
    return repo.one(db.from("stores").select("*,company_registrations(*),individual_registrations(*),store_addresses(*)").eq("id", user.store_id).limit(1), "Cadastro da loja não encontrado.");
  });
  app.patch("/account", async (request) => {
    const data = accountPatch.parse(request.body); const { user, db } = await context(request); requireAdmin(user.role);
    const { name, phone, ...address } = data;
    if (name) await db.from("stores").update({ name }).eq("id", user.store_id);
    if (phone) await db.from("users").update({ phone }).eq("id", user.id);
    if (Object.keys(address).length) await db.from("store_addresses").update(address).eq("store_id", user.store_id).eq("is_primary", true);
    const repo = new Repository(db);
    return repo.one(db.from("stores").select("*,company_registrations(*),individual_registrations(*),store_addresses(*)").eq("id", user.store_id).limit(1), "Cadastro da loja não encontrado.");
  });
  app.get("/account/fiscal-profile", async (request) => {
    const { user, db, repo } = await context(request);
    return repo.one(db.from("fiscal_profiles").select("*").eq("store_id", user.store_id).limit(1), "Perfil fiscal não encontrado.");
  });
  app.patch("/account/fiscal-profile", async (request) => {
    const data = fiscalPatch.parse(request.body); const { user, db, repo } = await context(request); requireAdmin(user.role);
    return repo.one(db.rpc("review_fiscal_profile", { p_tax_regime: data.tax_regime, p_regime_source: data.regime_source }), "Perfil fiscal não encontrado.");
  });
  app.get<{ Params: { productId: string } }>("/products/:productId/tax-profile", async (request) => {
    const { db, repo } = await context(request);
    return repo.one(db.from("product_tax_profiles").select("*").eq("product_id", request.params.productId).limit(1), "Perfil fiscal do produto não encontrado.");
  });
  app.put<{ Params: { productId: string } }>("/products/:productId/tax-profile", async (request) => {
    const data = taxProfile.parse(request.body); const { user, db, repo } = await context(request); requireAdmin(user.role);
    const { data: products } = await db.from("products").select("id").eq("id", request.params.productId).eq("store_id", user.store_id).limit(1);
    if (!products?.[0]) throw new NotFoundError("Produto não encontrado nesta loja.");
    return repo.one(db.from("product_tax_profiles").upsert({ ...data, product_id: request.params.productId, store_id: user.store_id, reviewed_by: data.manually_reviewed ? user.id : null }, { onConflict: "product_id" }).select(), "Não foi possível salvar o perfil fiscal.");
  });
};
