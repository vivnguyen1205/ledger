import os

import psycopg
from dotenv import load_dotenv

load_dotenv()
with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    row = conn.execute(
        "SELECT extname FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()
    print("pgvector enabled!" if row else "pgvector NOT found")
