import { existsSync } from "node:fs";
import { createServer, type ServerResponse } from "node:http";
import { config } from "dotenv";
import { Pool } from "pg";

if (existsSync(".env.local")) {
  config({ path: ".env.local" });
} else if (existsSync(".env")) {
  config();
}

const connectionString = process.env.DATABASE_URL;

if (!connectionString) {
  throw new Error("DATABASE_URL must be set in the environment or .env.local/.env");
}

const pool = new Pool({ connectionString });
const port = Number(process.env.PORT ?? 3000);

if (!Number.isInteger(port) || port < 0 || port > 65535) {
  throw new Error("PORT must be an integer between 0 and 65535");
}

async function respondWithDatabaseHealth(response: ServerResponse): Promise<void> {
  try {
    const result = await pool.query<{ ok: number }>("SELECT 1 AS ok");
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "ok", database: "connected", result: result.rows[0]?.ok }));
  } catch (error) {
    console.error("Neon database health check failed:", error);
    response.writeHead(503, { "content-type": "application/json" });
    response.end(JSON.stringify({ status: "error", database: "unavailable" }));
  }
}

const server = createServer((request, response) => {
  if (request.method !== "GET" || request.url?.split("?")[0] !== "/health") {
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: "Not found" }));
    return;
  }

  void respondWithDatabaseHealth(response);
});

server.listen(port, () => {
  console.log(`Ledger server listening on port ${port}`);
});

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    server.close(() => {
      void pool.end().catch((error: unknown) => {
        console.error("Failed to close the Neon database pool:", error);
        process.exitCode = 1;
      });
    });
  });
}
