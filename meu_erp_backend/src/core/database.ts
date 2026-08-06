import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { config } from "./config.ts";
import { AuthenticationError, NotFoundError, UpstreamError } from "./errors.ts";

export type Row = Record<string, unknown>;
export type DatabaseClient = SupabaseClient;

const options = {
  auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  global: { fetch: timedFetch },
};

async function timedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const signal = AbortSignal.timeout(config.supabaseTimeoutMs);
  return fetch(input, { ...init, signal });
}

export const anonClient = createClient(config.supabaseUrl, config.supabaseAnonKey, options);

export function adminClient(): DatabaseClient {
  if (!config.supabaseSecretKey) throw new UpstreamError("Chave administrativa não configurada.");
  return createClient(config.supabaseUrl, config.supabaseSecretKey, options);
}

export function authenticatedClient(token: string): DatabaseClient {
  return createClient(config.supabaseUrl, config.supabaseAnonKey, {
    ...options,
    global: { ...options.global, headers: { Authorization: `Bearer ${token}` } },
  });
}

export function bearerToken(authorization: string | undefined): string {
  const match = authorization?.match(/^Bearer\s+(.+)$/i);
  if (!match?.[1]) throw new AuthenticationError("Token Bearer obrigatório.");
  return match[1];
}

export async function checkDatabaseConnection(): Promise<void> {
  if (!config.supabaseConfigured) throw new Error("Supabase não configurado.");
  const { error } = await anonClient.from("stores").select("id").limit(1);
  if (error) throw new UpstreamError();
}

export class Repository {
  protected readonly db: DatabaseClient;

  constructor(db: DatabaseClient) { this.db = db; }

  async one<T extends Row>(promise: PromiseLike<{ data: T[] | null; error: { message: string } | null }>, message: string): Promise<T> {
    const { data, error } = await promise;
    if (error) throw new UpstreamError(error.message);
    if (!data?.[0]) throw new NotFoundError(message);
    return data[0];
  }

  async rows<T extends Row>(promise: PromiseLike<{ data: T[] | null; error: { message: string } | null }>): Promise<T[]> {
    const { data, error } = await promise;
    if (error) throw new UpstreamError(error.message);
    return data ?? [];
  }

  insert<T extends Row>(table: string, payload: Row, message = `Falha ao criar registro em ${table}.`): Promise<T> {
    return this.one<T>(this.db.from(table).insert(payload).select(), message);
  }
}
