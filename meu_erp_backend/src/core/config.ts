import "dotenv/config";
import { z } from "zod";

const boolean = z.string().default("false").transform((value) => value.toLowerCase() === "true");
const optional = z.string().optional().transform((value) => value?.trim() || undefined);

const schema = z.object({
  ERP_APP_NAME: z.string().default("Sistema Integrado de Gestão Comercial"),
  ERP_APP_VERSION: z.string().default("0.2.0"),
  ERP_ENVIRONMENT: z.string().default("development"),
  ERP_DEBUG: boolean,
  ERP_PORT: z.coerce.number().int().min(1).max(65535).default(8000),
  PORT: z.coerce.number().int().min(1).max(65535).optional(),
  ERP_CORS_ORIGINS: z.string().default("http://localhost:3000"),
  ERP_SUPABASE_URL: z.url().default("http://localhost:54321"),
  ERP_SUPABASE_ANON_KEY: z.string().default("local-development-key"),
  ERP_SUPABASE_SECRET_KEY: optional,
  ERP_SUPABASE_SERVICE_ROLE_KEY: optional,
  ERP_SUPABASE_TIMEOUT_SECONDS: z.coerce.number().positive().max(120).default(10),
  ERP_SUPABASE_EXPECTED_PROJECT_ID: z.string().default("gfqrqlvkqqnhzwbcozzp"),
  ERP_DIAGNOSTIC_ENABLED: boolean,
  ERP_DIAGNOSTIC_USERNAME: optional,
  ERP_DIAGNOSTIC_PASSWORD: optional,
  ERP_LOGIN_RATE_LIMIT_ATTEMPTS: z.coerce.number().int().min(1).max(100).default(5),
  ERP_LOGIN_RATE_LIMIT_WINDOW_SECONDS: z.coerce.number().int().min(10).max(3600).default(300),
  ERP_PASSWORD_RESET_REDIRECT_URL: optional,
});

const env = schema.parse(process.env);

function jwtRole(key: string): string | undefined {
  const payload = key.split(".")[1];
  if (!payload) return undefined;
  try { return JSON.parse(Buffer.from(payload, "base64url").toString("utf8")).role; }
  catch { return undefined; }
}

if (env.ERP_SUPABASE_ANON_KEY.startsWith("sb_secret_") || jwtRole(env.ERP_SUPABASE_ANON_KEY) === "service_role") {
  throw new Error("ERP_SUPABASE_ANON_KEY não pode conter uma chave administrativa.");
}

export const config = Object.freeze({
  appName: env.ERP_APP_NAME,
  appVersion: env.ERP_APP_VERSION,
  environment: env.ERP_ENVIRONMENT,
  debug: env.ERP_DEBUG,
  port: env.PORT ?? env.ERP_PORT,
  corsOrigins: env.ERP_CORS_ORIGINS.split(",").map((item) => item.trim()).filter(Boolean),
  supabaseUrl: env.ERP_SUPABASE_URL.replace(/\/$/, ""),
  supabaseAnonKey: env.ERP_SUPABASE_ANON_KEY,
  supabaseSecretKey: env.ERP_SUPABASE_SECRET_KEY ?? env.ERP_SUPABASE_SERVICE_ROLE_KEY,
  supabaseTimeoutMs: env.ERP_SUPABASE_TIMEOUT_SECONDS * 1_000,
  expectedProjectId: env.ERP_SUPABASE_EXPECTED_PROJECT_ID,
  diagnosticEnabled: env.ERP_DIAGNOSTIC_ENABLED,
  diagnosticUsername: env.ERP_DIAGNOSTIC_USERNAME,
  diagnosticPassword: env.ERP_DIAGNOSTIC_PASSWORD,
  rateLimitAttempts: env.ERP_LOGIN_RATE_LIMIT_ATTEMPTS,
  rateLimitWindowMs: env.ERP_LOGIN_RATE_LIMIT_WINDOW_SECONDS * 1_000,
  passwordResetRedirectUrl: env.ERP_PASSWORD_RESET_REDIRECT_URL,
  supabaseConfigured: env.ERP_SUPABASE_URL !== "http://localhost:54321" && env.ERP_SUPABASE_ANON_KEY !== "local-development-key",
});
