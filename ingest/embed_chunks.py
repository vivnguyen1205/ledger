import json
import math
import os
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
CHUNKS = ROOT / "data" / "chunks"

MODEL = "gemini-embedding-001"
DIMS = 768
# Free tier allows 30,000 embedding tokens per minute. A 600-word chunk is ~800
# tokens, so 50 chunks (~40k) could never fit in one request; 20 (~16k) does.
BATCH = 20

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    ticker       TEXT    NOT NULL,
    fiscal_year  INTEGER NOT NULL,
    section      TEXT    NOT NULL,
    chunk_index  INTEGER NOT NULL,
    content      TEXT    NOT NULL,
    source_url   TEXT    NOT NULL,
    embedding    vector({DIMS}) NOT NULL,
    UNIQUE (ticker, fiscal_year, section, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def normalize(vector):
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector]


def to_pgvector(vector) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vector) + "]"


def embed(client, texts):
    for attempt in range(6):
        try:
            result = client.models.embed_content(
                model=MODEL,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT", output_dimensionality=DIMS),
            )
            return [normalize(e.values) for e in result.embeddings]
        except Exception as error:
            if "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error):
                wait = 10 * 2 ** attempt
                print(f"  rate limited, waiting {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gave up after repeated rate limits")


def main():
    client = genai.Client()
    # Short-lived connections: embedding a filing can take minutes of rate-limit
    # waits, and Neon closes connections that sit idle that long.
    db_url = os.environ["DATABASE_URL"]
    with psycopg.connect(db_url) as conn:
        conn.execute(SCHEMA)
        conn.commit()
    for path in sorted(CHUNKS.glob("*.jsonl")):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if not rows:
            continue
        with psycopg.connect(db_url) as conn:
            already = conn.execute(
                "SELECT 1 FROM chunks WHERE ticker = %s AND fiscal_year = %s LIMIT 1",
                (rows[0]["ticker"], rows[0]["fiscal_year"]),
            ).fetchone()
        if already:
            print(f"{path.name}: already loaded")
            continue

        print(f"{path.name}: embedding {len(rows)} chunks")
        records = []
        for start in range(0, len(rows), BATCH):
            batch = rows[start:start + BATCH]
            # A short header gives each chunk context about where it came from
            texts = [f"{r['ticker']} 10-K FY{r['fiscal_year']}, {r['section']}\n\n{r['content']}"
                     for r in batch]
            for row, vector in zip(batch, embed(client, texts)):
                records.append((row["ticker"], row["fiscal_year"], row["section"],
                                row["chunk_index"], row["content"], row["source_url"],
                                to_pgvector(vector)))
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO chunks (ticker, fiscal_year, section, chunk_index,
                                           content, source_url, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""",
                    records,
                )
            conn.commit()  # one filing at a time, so a crash keeps earlier progress


if __name__ == "__main__":
    main()