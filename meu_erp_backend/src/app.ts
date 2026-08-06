import cors from "@fastify/cors";
import multipart from "@fastify/multipart";
import Fastify, { type FastifyInstance } from "fastify";
import { config } from "./core/config.ts";
import { checkDatabaseConnection } from "./core/database.ts";
import { registerErrorHandler } from "./core/errors.ts";
import { registerAuthRoutes } from "./modules/auth/routes.ts";
import { registerCatalogRoutes } from "./modules/catalog/routes.ts";
import { registerSalesRoutes } from "./modules/sales/routes.ts";
import { registerCustomerRoutes } from "./modules/customers/routes.ts";
import { registerAccountRoutes } from "./modules/account/routes.ts";
import { registerDeliveryRoutes } from "./modules/deliveries/routes.ts";
import { registerReportRoutes } from "./modules/reports/routes.ts";
import { registerReconciliationRoutes } from "./modules/reconciliation/routes.ts";
import { registerDiagnosticRoutes } from "./modules/diagnostics/routes.ts";

export async function buildApp(): Promise<FastifyInstance> {
  const app = Fastify({ logger: config.environment !== "test" });
  await app.register(cors, {
    origin: config.corsOrigins.includes("*") ? true : config.corsOrigins,
    credentials: !config.corsOrigins.includes("*"),
  });
  await app.register(multipart, { limits: { fileSize: 10 * 1024 * 1024, files: 1 } });
  registerErrorHandler(app);

  app.get("/", async () => ({
    name: config.appName, status: "online", docs: "/docs", health: "/health/ready",
  }));
  app.get("/health", async () => ({ status: "ok", api: "online" }));
  app.get("/health/ready", async (_request, reply) => {
    try {
      await checkDatabaseConnection();
      return { status: "ok", api: "online", database: "online" };
    } catch (error) {
      return reply.status(503).send({
        status: "unavailable", api: "online", database: "offline",
        detail: config.supabaseConfigured ? (error as Error).constructor.name : "supabase_not_configured",
      });
    }
  });

  await app.register(registerAuthRoutes, { prefix: "/api/auth" });
  await app.register(registerCatalogRoutes, { prefix: "/api" });
  await app.register(registerSalesRoutes, { prefix: "/api" });
  await app.register(registerCustomerRoutes, { prefix: "/api" });
  await app.register(registerAccountRoutes, { prefix: "/api" });
  await app.register(registerDeliveryRoutes, { prefix: "/api" });
  await app.register(registerReportRoutes, { prefix: "/api" });
  await app.register(registerReconciliationRoutes, { prefix: "/api" });
  await app.register(registerDiagnosticRoutes);
  return app;
}
