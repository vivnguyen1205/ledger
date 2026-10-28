import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()
CHUNKS = Path(__file__).resolve().parent.parent / "data" / "chunks"

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    in_db = dict(conn.execute(
        "SELECT ticker || '_FY' || fiscal_year, COUNT(*) FROM chunks GROUP BY 1"
    ).fetchall())

ok = stale = missing = 0
for path in sorted(CHUNKS.glob("*.jsonl")):
    name = path.stem                                   # e.g. "AMD_FY2024"
    in_file = len(path.read_text().splitlines())
    db_count = in_db.get(name, 0)
    if db_count == 0:
        status, missing = "not loaded yet", missing + 1
    elif db_count == in_file:
        status, ok = "OK", ok + 1
    else:
        status, stale = "STALE, needs reload", stale + 1
    print(f"{name:<12} file: {in_file:>4}  database: {db_count:>4}  {status}")

print(f"\n{ok} OK, {stale} stale, {missing} not loaded yet")