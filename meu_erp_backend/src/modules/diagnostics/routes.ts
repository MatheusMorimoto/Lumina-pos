import { timingSafeEqual } from "node:crypto";
import type { FastifyPluginAsync, FastifyRequest } from "fastify";
import { config } from "../../core/config.ts";
import { checkDatabaseConnection } from "../../core/database.ts";

function equal(left: string, right: string): boolean {
  const a = Buffer.from(left); const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}
function guard(request: FastifyRequest): void {
  if (!config.diagnosticEnabled) throw Object.assign(new Error("Not Found"), { statusCode: 404 });
  if (!config.diagnosticUsername || !config.diagnosticPassword) throw Object.assign(new Error("Diagnóstico sem credenciais."), { statusCode: 503 });
  const raw = request.headers.authorization;
  const decoded = raw?.startsWith("Basic ") ? Buffer.from(raw.slice(6), "base64").toString("utf8") : ":";
  const separator = decoded.indexOf(":"); const username = decoded.slice(0, separator); const password = decoded.slice(separator + 1);
  if (!equal(username, config.diagnosticUsername) || !equal(password, config.diagnosticPassword)) {
    throw Object.assign(new Error("Acesso administrativo obrigatório."), { statusCode: 401, headers: { "WWW-Authenticate": 'Basic realm="Lumina diagnostics"' } });
  }
}
function projectId(): string | null { const host = new URL(config.supabaseUrl).hostname; return host.endsWith(".supabase.co") ? host.slice(0, -12) : null; }

const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Diagnóstico Lumina POS</title><style>body{font:16px system-ui;max-width:760px;margin:40px auto;padding:20px;background:#07111f;color:#edf4ff}section{background:#111c2f;padding:20px;border-radius:14px;margin:16px 0}input,button{padding:10px;margin:5px;width:95%}pre{white-space:pre-wrap}</style></head><body><h1>Diagnóstico Lumina POS</h1><section><pre id="health">Verificando...</pre></section><section><form id="form"><input id="email" type="email" placeholder="E-mail" required><input id="password" type="password" placeholder="Senha" required><button>Testar login</button></form><pre id="result"></pre></section><script>fetch('/api/health/supabase',{cache:'no-store'}).then(r=>r.json()).then(d=>health.textContent=JSON.stringify(d,null,2));form.onsubmit=async e=>{e.preventDefault();const r=await fetch('/api/auth/login',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:email.value,password:password.value})});const d=await r.json();delete d.access_token;delete d.refresh_token;result.textContent=JSON.stringify(d,null,2);password.value=''}</script></body></html>`;

export const registerDiagnosticRoutes: FastifyPluginAsync = async (app) => {
  app.get("/api/health/supabase", async (request, reply) => {
    guard(request); const started = performance.now(); const id = projectId(); let connected = false; let errorStage: string | null = null;
    try { await checkDatabaseConnection(); connected = id === config.expectedProjectId; if (!connected) errorStage = "project_validation"; } catch { errorStage = "supabase_connection"; }
    return reply.status(connected ? 200 : 503).header("Cache-Control", "no-store").send({
      api: "online", supabase: connected ? "connected" : "disconnected", project_id: id,
      configuration: { url_configured: config.supabaseConfigured, publishable_key_configured: Boolean(config.supabaseAnonKey), secret_key_configured: Boolean(config.supabaseSecretKey) },
      response_time_ms: Math.round((performance.now() - started) * 100) / 100, tested_at: new Date().toISOString(), error_stage: errorStage,
    });
  });
  app.get("/teste-conexao", async (request, reply) => {
    guard(request); return reply.type("text/html; charset=utf-8").headers({
      "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
      "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    }).send(html);
  });
};
