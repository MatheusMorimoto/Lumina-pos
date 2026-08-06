import { adminClient, anonClient, authenticatedClient } from "../../core/database.ts";
import { ConflictError, UpstreamError } from "../../core/errors.ts";
import { publicRegistration, type Registration } from "./schema.ts";

export async function completeRegistration(token: string, payload: Record<string, unknown>) {
  const client = authenticatedClient(token);
  const { data, error } = await client.rpc("complete_registration", { payload });
  if (error) throw new UpstreamError("Não foi possível concluir o cadastro.");
  if (data) await client.auth.updateUser({ data: { pending_registration: null } });
  return (data ?? []) as Array<Record<string, unknown>>;
}

export async function register(data: Registration) {
  let userId: string | undefined;
  try {
    const payload = publicRegistration(data);
    const { data: auth, error } = await anonClient.auth.signUp({
      email: data.email, password: data.password, options: { data: { pending_registration: payload } },
    });
    if (error) throw error;
    if (!auth.user) throw new UpstreamError("O Supabase não criou o usuário.");
    userId = auth.user.id;
    if (!auth.session) return { statusCode: 202, body: {
      user_id: userId, email_confirmation_required: true, registration_complete: false,
      message: "Confirme o e-mail para concluir o cadastro.",
    } };
    const rows = await completeRegistration(auth.session.access_token, payload);
    if (!rows[0]) throw new UpstreamError("Não foi possível concluir o cadastro.");
    return { statusCode: 201, body: {
      access_token: auth.session.access_token, token_type: "bearer", ...rows[0], registration_complete: true,
    } };
  } catch (error) {
    if (userId) { try { await adminClient().auth.admin.deleteUser(userId); } catch { /* compensação best effort */ } }
    const message = String((error as Error).message).toLowerCase();
    if (["already", "duplicate", "registered"].some((term) => message.includes(term))) throw new ConflictError("E-mail ou documento já cadastrado.");
    if (error instanceof UpstreamError) throw error;
    throw new UpstreamError("O Supabase recusou o cadastro. Consulte os logs da API.");
  }
}
