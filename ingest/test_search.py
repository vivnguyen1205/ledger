import os
import sys
import math

import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
query = " ".join(sys.argv[1:]) or "export controls on chip sales to China"

client = genai.Client()
values = client.models.embed_content(
    model="gemini-embedding-001",
    contents=[query],
    config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=768),
).embeddings[0].values
norm = math.sqrt(sum(x * x for x in values))
vector = "[" + ",".join(f"{x / norm:.6f}" for x in values) + "]"

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    rows = conn.execute(
        """SELECT ticker, fiscal_year, section, embedding <=> %s::vector AS distance,
                  left(content, 160)
           FROM chunks ORDER BY distance LIMIT 5""",
        (vector,),
    ).fetchall()

for ticker, year, section, distance, preview in rows:
    print(f"{distance:.3f}  {ticker} FY{year}  {section}\n       {preview}...\n")