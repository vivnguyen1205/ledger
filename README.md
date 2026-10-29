# ledger

Ledger is a research assistant that answers questions about public companies
using their SEC 10-K filings. It downloads filings from EDGAR, splits the text
into chunks, embeds them with Gemini, and stores them in Neon Postgres
(pgvector). A Google ADK agent searches those chunks and answers with
citations.

## What's covered

Defined in [`scope.json`](scope.json):

- **Companies:** AAPL, MSFT, NVDA, AMD, INTC, GOOGL, AMZN, META, TSLA, NFLX
- **Fiscal years:** 2023, 2024, 2025
- **10-K sections:** Item 1 (Business), Item 1A (Risk Factors), Item 7 (MD&A)
- **Financial metrics:** revenue, net income, operating income, R&D expense,
  cash, total debt

## Setup

You need Python 3, Node.js, a Neon Postgres database with the `vector`
extension, and a Gemini API key.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```sh
DATABASE_URL=postgresql://...        # Neon connection string
GEMINI_API_KEY=...                   # or GOOGLE_API_KEY
GOOGLE_GENAI_USE_VERTEXAI=FALSE
SEC_USER_AGENT="Your Name you@example.com"   # required by SEC EDGAR
```

Quick checks that each service works:

```sh
python hello_db.py       # confirms pgvector is enabled
python hello_edgar.py    # fetches Apple's recent filings from EDGAR
python hello_gemini.py   # one test call to Gemini
```

## Load the data

Run these from the project root. Downloaded files go in `data/` (ignored by
git).

```sh
python ingest/download.py       # 10-K HTML + XBRL company facts -> data/10k, data/facts
python ingest/load_metrics.py   # financial metrics -> `metrics` table
python ingest/chunk_10ks.py     # section text -> data/chunks/*.jsonl
python ingest/embed_chunks.py   # embeddings -> `chunks` table
```

Each step skips work that's already done, so it's safe to re-run.
`embed_chunks.py` handles Gemini free-tier rate limits by waiting and retrying,
so a full load can take a while.

Helper scripts:

```sh
python ingest/check_chunks.py                  # compare chunk files with what's in the database
python ingest/test_search.py "export controls" # run a raw vector search
python ingest/find_tags.py NVDA 2025 revenue   # list XBRL tags matching a keyword
```

## Ask questions

The docs agent lives in [`agents/docs_agent`](agents/docs_agent). It calls the
`search_filings` tool, which embeds the query and runs a filtered vector search
(by ticker and fiscal year) over the `chunks` table. Answers cite their sources,
e.g. `[NVDA 10-K FY2025, Item 1A Risk Factors]`.

```sh
adk web agents          # browser chat UI
adk run agents/docs_agent   # terminal chat
```

## Evals

[`evals/questions.json`](evals/questions.json) holds 20 test questions across
docs, SQL, API, multi-step, and tricky cases. Each has an expected answer, a
source, and a check type (`judge`, `number`, or `refusal`).

## Health check server

A small TypeScript server checks the Neon connection:

```sh
npm install
npm run build
npm start
```

`GET /health` runs a query against Neon and returns the connection status. It
reads `DATABASE_URL` from `.env.local` (or `.env`). Set `PORT` to change the
default port (`3000`).
