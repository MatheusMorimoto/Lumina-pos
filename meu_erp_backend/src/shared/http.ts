import type { FastifyRequest } from "fastify";
import { authenticatedClient, bearerToken, Repository } from "../core/database.ts";

export function requestRepository(request: FastifyRequest): Repository {
  return new Repository(authenticatedClient(bearerToken(request.headers.authorization)));
}

export function requestDatabase(request: FastifyRequest) {
  return authenticatedClient(bearerToken(request.headers.authorization));
}

export const uuidParams = { type: "object", properties: { id: { type: "string", format: "uuid" } } } as const;
