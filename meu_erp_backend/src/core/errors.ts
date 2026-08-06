import type { FastifyInstance } from "fastify";
import { ZodError } from "zod";

export class ApplicationError extends Error {
  readonly statusCode: number;
  readonly code: string;

  constructor(
    message: string,
    statusCode = 400,
    code = "application_error",
  ) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.name = new.target.name;
  }
}

export class BusinessRuleError extends ApplicationError {
  constructor(message: string) { super(message, 422, "business_rule_violation"); }
}
export class NotFoundError extends ApplicationError {
  constructor(message: string) { super(message, 404, "not_found"); }
}
export class AuthenticationError extends ApplicationError {
  constructor(message = "Credenciais de autenticação inválidas.") {
    super(message, 401, "authentication_error");
  }
}
export class AuthorizationError extends ApplicationError {
  constructor(message = "Acesso não autorizado.") { super(message, 403, "authorization_error"); }
}
export class ConflictError extends ApplicationError {
  constructor(message: string) { super(message, 409, "conflict"); }
}
export class RateLimitError extends ApplicationError {
  constructor(message: string) { super(message, 429, "rate_limit_exceeded"); }
}
export class UpstreamError extends ApplicationError {
  constructor(message = "Serviço de dados indisponível.") {
    super(message, 503, "supabase_unavailable");
  }
}

export function registerErrorHandler(app: FastifyInstance): void {
  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof ApplicationError) {
      return reply.status(error.statusCode).send({ error: { code: error.code, message: error.message } });
    }
    if (error instanceof ZodError) {
      return reply.status(422).send({
        error: { code: "validation_error", message: "Dados de entrada inválidos.", issues: error.issues },
      });
    }
    const httpError = error as { statusCode?: number; headers?: Record<string, string>; message?: string };
    if (typeof httpError.statusCode === "number" && httpError.statusCode < 500) {
      if (httpError.headers) reply.headers(httpError.headers);
      return reply.status(httpError.statusCode).send({ error: { code: "http_error", message: httpError.message ?? "Erro HTTP." } });
    }
    app.log.error(error);
    return reply.status(500).send({
      error: { code: "internal_error", message: "Erro interno do servidor." },
    });
  });
}
