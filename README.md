# ledger

Ledger is a RAG assistant backed by Neon Postgres.

## Run locally

Neon CLI setup stores the database connection in `.env.local` (or `.env` when
that file already exists). Install dependencies, build, and start the service:

```sh
npm install
npm run build
npm start
```

The `GET /health` endpoint runs a query against Neon and returns the database
connection status. Set `PORT` to change the default port (`3000`).
