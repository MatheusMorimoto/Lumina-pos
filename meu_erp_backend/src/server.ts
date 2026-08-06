import { buildApp } from "./app.ts";
import { config } from "./core/config.ts";

const app = await buildApp();

try {
  await app.listen({ host: "0.0.0.0", port: config.port });
} catch (error) {
  app.log.error(error);
  process.exitCode = 1;
}
