import type { FastifyPluginAsync } from "fastify";
import { config } from "../../core/config.ts";
import { anonClient, authenticatedClient, bearerToken } from "../../core/database.ts";
import { AuthenticationError } from "../../core/errors.ts";
import { currentUser, login, resetPasswordByAdmin } from "./service.ts";
import { emailSchema, loginSchema, passwordSchema } from "./schemas.ts";
import { registrationSchema } from "../registration/schema.ts";
import { register } from "../registration/service.ts";

export const registerAuthRoutes: FastifyPluginAsync = async (app) => {
  app.post("/register", async (request, reply) => {
    const result = await register(registrationSchema.parse(request.body));
    return reply.status(result.statusCode).send(result.body);
  });
  app.post("/login", async (request) => {
    const data = loginSchema.parse(request.body);
    return login(request, data.email, data.password);
  });

  app.post("/password/recover", async (request, reply) => {
    const { email } = emailSchema.parse(request.body);
    const options = config.passwordResetRedirectUrl ? { redirectTo: config.passwordResetRedirectUrl } : undefined;
    try { await anonClient.auth.resetPasswordForEmail(email, options); } catch { /* impede enumeração */ }
    return reply.status(202).send({ message: "Se o e-mail estiver cadastrado, enviaremos as instruções." });
  });

  app.post("/password/update", async (request) => {
    const data = passwordSchema.parse(request.body);
    const token = bearerToken(request.headers.authorization);
    const { error } = await authenticatedClient(token).auth.updateUser({ password: data.password });
    if (error) throw new AuthenticationError("Sessão inválida ou expirada para redefinir a senha.");
    return { message: "Senha atualizada com sucesso." };
  });

  app.get("/me", async (request) => {
    const { access_token: _, ...user } = await currentUser(request);
    return user;
  });

  app.post<{ Params: { userId: string } }>("/admin/users/:userId/password", async (request) => {
    const data = passwordSchema.parse(request.body);
    await resetPasswordByAdmin(request, request.params.userId, data.password);
    return { message: "Senha redefinida com sucesso." };
  });
};
