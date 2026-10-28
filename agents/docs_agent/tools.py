import json
import math
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
SCOPE = json.loads((ROOT / "scope.json").read_text())

EMBED_MODEL = "gemini-embedding-001"
DIMS = 768
TOP_K = 6
_client = None


def _embed_query(text: str) -> str:
    global _client
    if _client is None:
        _client = genai.Client()
    values = _client.models.embed_content(
        model=EMBED_MODEL,
        contents=[text],
        config=types.EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=DIMS),
    ).embeddings[0].values
    norm = math.sqrt(sum(x * x for x in values))
    return "[" + ",".join(f"{x / norm:.6f}" for x in values) + "]"


def search_filings(query: str, ticker: str, fiscal_year: int) -> dict:
    """Search the text of companies' 10-K annual reports for passages relevant to a query.

    Covers three sections: Item 1 Business, Item 1A Risk Factors, and Item 7
    Management's Discussion and Analysis (MD&A).

    Args:
        query: A description of the content you need, e.g.
            "risks from US export controls on chip sales to China".
        ticker: One company ticker to restrict the search to, e.g. "NVDA".
            Use an empty string "" to search all companies.
        fiscal_year: One fiscal year to restrict the search to, e.g. 2024.
            Use 0 to search all years.

    Returns:
        A dict with "results": a list of passages, each with a "source" label to cite,
        plus ticker, fiscal_year, section, and text. Or a dict with "error".
    """
    ticker = ticker.strip().upper()
    if ticker and ticker not in SCOPE["companies"]:
        return {"error": f"{ticker} is not in the dataset. Available: {', '.join(SCOPE['companies'])}"}
    if fiscal_year and fiscal_year not in SCOPE["fiscal_years"]:
        return {"error": f"Fiscal year {fiscal_year} is not in the dataset. Available: {SCOPE['fiscal_years']}"}

    sql = """SELECT ticker, fiscal_year, section, content, source_url,
                    embedding <=> %s::vector AS distance
             FROM chunks"""
    params = [_embed_query(query)]
    conditions = []
    if ticker:
        conditions.append("ticker = %s")
        params.append(ticker)
    if fiscal_year:
        conditions.append("fiscal_year = %s")
        params.append(fiscal_year)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY distance LIMIT %s"
    params.append(TOP_K)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        # Make the index consider more candidates, so filters still return enough results
        conn.execute("SET hnsw.ef_search = 1000")
        rows = conn.execute(sql, params).fetchall()

    return {"results": [
        {
            "source": f"{t} 10-K FY{y}, {section}",
            "ticker": t,
            "fiscal_year": y,
            "section": section,
            "distance": round(float(distance), 3),
            "text": content,
            "url": url,
        }
        for t, y, section, content, url, distance in rows
    ]}