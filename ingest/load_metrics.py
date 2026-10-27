import json
import os
from datetime import date
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
scope = json.loads((ROOT / "scope.json").read_text())

# Possible XBRL tags for each metric, tried in order. Expect to edit this.
TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss"],
    "operating_income": ["OperatingIncomeLoss"],
    "rd_expense": ["ResearchAndDevelopmentExpense","ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "total_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
}
# Metrics measured over a year (income statement), not at a single date (balance sheet)
FLOW_METRICS = {"revenue", "net_income", "operating_income", "rd_expense"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    ticker       TEXT    NOT NULL,
    metric       TEXT    NOT NULL,
    fiscal_year  INTEGER NOT NULL,
    value        NUMERIC NOT NULL,
    unit         TEXT    NOT NULL,
    xbrl_tag     TEXT    NOT NULL,
    period_end   DATE    NOT NULL,
    accession    TEXT    NOT NULL,
    PRIMARY KEY (ticker, metric, fiscal_year)
);
"""


def is_full_year(fact: dict) -> bool:
    if "start" not in fact:
        return False
    days = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
    return 350 <= days <= 380


def find_value(us_gaap: dict, metric: str, report_date: str, accession: str):
    for tag in TAGS[metric]:
        for fact in us_gaap.get(tag, {}).get("units", {}).get("USD", []):
            if fact.get("accn") != accession or fact["end"] != report_date:
                continue
            if metric in FLOW_METRICS and not is_full_year(fact):
                continue
            return fact["val"], tag
    return None, None


def main():
    rows, missing = [], []
    for ticker in scope["companies"]:
        us_gaap = json.loads((DATA / "facts" / f"{ticker}.json").read_text())["facts"]["us-gaap"]
        for meta_path in sorted((DATA / "10k" / ticker).glob("FY*.json")):
            meta = json.loads(meta_path.read_text())
            for metric in scope["metrics"]:
                value, tag = find_value(us_gaap, metric, meta["report_date"], meta["accession"])
                if value is None:
                    missing.append(f"{ticker} FY{meta['fiscal_year']} {metric}")
                    continue
                rows.append((ticker, metric, meta["fiscal_year"], value, "USD",
                             tag, meta["report_date"], meta["accession"]))

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(SCHEMA)
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO metrics VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (ticker, metric, fiscal_year) DO UPDATE SET
                     value = EXCLUDED.value, xbrl_tag = EXCLUDED.xbrl_tag,
                     period_end = EXCLUDED.period_end, accession = EXCLUDED.accession""",
                rows,
            )

    print(f"Loaded {len(rows)} values.")
    print(f"Missing {len(missing)}:")
    for item in missing:
        print("  ", item)


if __name__ == "__main__":
    main()