import type { FastifyRequest } from "fastify";
import { config } from "../../core/config.ts";
import { adminClient, anonClient, authenticatedClient, bearerToken } from "../../core/database.ts";
import { AuthenticationError, AuthorizationError, NotFoundError, RateLimitError, UpstreamError } from "../../core/errors.ts";
import type { CurrentUser } from "./schemas.ts";
import { completeRegistration } from "../registration/service.ts";

const attempts = new Map<string, number[]>();

function requestKey(request: FastifyRequest, email: string): string {
  const forwarded = request.headers["x-forwarded-for"];
  const ip = (Array.isArray(forwarded) ? forwarded[0] : forwarded)?.split(",")[0]?.trim() || request.ip;
  return `${ip}:${email}`;
}

function checkRateLimit(key: string): void {
  const cutoff = Date.now() - config.rateLimitWindowMs;
  const active = (attempts.get(key) ?? []).filter((time) => time >= cutoff);
  attempts.set(key, active);
  if (active.length >= config.rateLimitAttempts) {
    throw new RateLimitError("Muitas tentativas de login. Aguarde alguns minutos.");
  }
}

export async function login(request: FastifyRequest, email: string, password: string) {
  const key = requestKey(request, email);
  checkRateLimit(key);
  const { data, error } = await anonClient.auth.signInWithPassword({ email, password });
  if (error || !data.session || !data.user) {
    attempts.set(key, [...(attempts.get(key) ?? []), Date.now()]);
    const message = error?.message.toLowerCase() ?? "";
    if (message.includes("email not confirmed")) throw new AuthenticationError("E-mail ainda não confirmado.");
    if (["timed out", "timeout", "connect", "network", "dns", "service unavailable", "bad gateway"].some((term) => message.includes(term))) {
      throw new UpstreamError("O serviço de autenticação está temporariamente indisponível.");
    }
    throw new AuthenticationError("E-mail ou senha inválidos.");
  }
  attempts.delete(key);
  const pending = data.user.user_metadata.pending_registration;
  if (pending && typeof pending === "object" && !Array.isArray(pending)) {
    try { await completeRegistration(data.session.access_token, pending as Record<string, unknown>); } catch { /* a sessão continua válida */ }
  }
  const profile = await profileFor(data.session.access_token, data.user.id);
  return {
    access_token: data.session.access_token,
    refresh_token: data.session.refresh_token,
    token_type: "bearer",
    expires_in: data.session.expires_in,
    expires_at: data.session.expires_at,
    authentication: {
      success: true, user_id: data.user.id, email: data.user.email ?? email,
      email_confirmed: Boolean(data.user.email_confirmed_at), token_received: true,
    },
    profile,
    user: {
      id: data.user.id, email: data.user.email ?? email, person_type: profile.person_type,
      display_name: profile.name, account_id: profile.store_id, role: profile.role,
      registration_complete: profile.found,
    },
  };
}

async function profileFor(token: string, userId: string): Promise<Record<string, unknown>> {
  try {
    const db = authenticatedClient(token);
    const { data: users, error } = await db.from("users")
      .select("id,name,email,active,store_id,role,stores(person_type)").eq("id", userId).limit(1);
    if (error || !users?.[0]) return { found: false, user_id: userId, lookup_status: "not_found" };
    const user = users[0] as Record<string, unknown>;
    const stores = user.stores as { person_type?: string } | null;
    const personType = stores?.person_type;
    const table = personType === "company" ? "company_registrations" : "individual_registrations";
    const fields = personType === "company" ? "legal_name,trade_name,cnpj" : "full_name,cpf";
    const { data: registrations } = await db.from(table).select(fields).eq("store_id", user.store_id).limit(1);
    const registration = registrations?.[0] as Record<string, unknown> | undefined;
    const cpf = String(registration?.cpf ?? "").replace(/\D/g, "");
    const cnpj = String(registration?.cnpj ?? "").replace(/\D/g, "");
    return {
      found: true, user_id: userId, name: registration?.trade_name ?? registration?.full_name ?? registration?.legal_name ?? user.name,
      cpf_masked: cpf.length === 11 ? `${cpf.slice(0, 3)}.***.***-${cpf.slice(-2)}` : null,
      cnpj_masked: cnpj.length === 14 ? `${cnpj.slice(0, 2)}.***.***/${cnpj.slice(8, 12)}-${cnpj.slice(-2)}` : null,
      person_type: personType,
      store_id: user.store_id, role: user.role, active: user.active ?? true, lookup_status: "found",
    };
  } catch {
    return { found: false, user_id: userId, lookup_status: "unavailable" };
  }
}

export async function currentUser(request: FastifyRequest): Promise<CurrentUser & { access_token: string }> {
  const token = bearerToken(request.headers.authorization);
  const db = authenticatedClient(token);
  const { data: auth, error: authError } = await db.auth.getUser(token);
  if (authError || !auth.user) throw new AuthenticationError("Sessão inválida ou expirada.");
  const { data, error } = await db.from("users")
    .select("id,email,name,phone,role,active,store_id,stores(id,name,person_type)")
    .eq("id", auth.user.id).limit(1);
  if (error) throw new AuthenticationError("Sessão inválida ou expirada.");
  const row = data?.[0] as Record<string, unknown> | undefined;
  if (!row) return {
    id: auth.user.id, email: auth.user.email ?? null, name: null, phone: null, role: null,
    store: null, store_id: null, registration_complete: false, profile_found: false, access_token: token,
  };
  if (row.active === false) throw new AuthenticationError("Cadastro de usuário não está ativo.");
  return {
    id: String(row.id), email: String(row.email), name: row.name ? String(row.name) : null,
    phone: row.phone ? String(row.phone) : null, role: row.role ? String(row.role) : null,
    store: row.stores ?? null, store_id: row.store_id ? String(row.store_id) : null,
    registration_complete: Boolean(row.stores), profile_found: true, access_token: token,
  };
}

export async function resetPasswordByAdmin(request: FastifyRequest, userId: string, password: string): Promise<void> {
  const actor = await currentUser(request);
  if (!actor.role || !["owner", "admin"].includes(actor.role)) {
    throw new AuthorizationError("Somente administradores podem redefinir senhas.");
  }
  if (!actor.store_id) throw new AuthorizationError("Administrador sem loja operacional associada.");
  const db = authenticatedClient(actor.access_token);
  const { data, error } = await db.from("users").select("id").eq("id", userId).eq("store_id", actor.store_id).limit(1);
  if (error) throw new UpstreamError("Não foi possível validar o usuário no Supabase.");
  if (!data?.[0]) throw new NotFoundError("Usuário não encontrado nesta loja.");
  const admin = adminClient();
  const { error: updateError } = await admin.auth.admin.updateUserById(userId, { password });
  if (updateError) throw new UpstreamError("Não foi possível redefinir a senha no Supabase.");
  const { error: auditError } = await admin.from("audit_logs").insert({
    store_id: actor.store_id, user_id: actor.id, action: "password_reset_by_admin",
    entity_type: "user", entity_id: userId, data: { credential_exposed: false },
  });
  if (auditError) request.log.error({ err: auditError }, "Falha ao auditar redefinição de senha");
}
