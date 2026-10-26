import json
from pathlib import Path

from edgar_client import get

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
scope = json.loads((ROOT / "scope.json").read_text())


def ticker_to_cik() -> dict:
    """Map tickers like AAPL to 10-digit CIK strings."""
    rows = get("https://www.sec.gov/files/company_tickers.json").json()
    return {row["ticker"]: str(row["cik_str"]).zfill(10) for row in rows.values()}


def download_company_facts(ticker: str, cik: str):
    out = DATA / "facts" / f"{ticker}.json"
    if out.exists():
        print(f"  facts: already have {ticker}")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json").content)
    print(f"  facts: saved {ticker}")

def all_filings(cik: str) -> list:
    """Recent filings plus older pages EDGAR splits off for busy filers."""
    sub = get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
    pages = [sub["filings"]["recent"]]
    for older in sub["filings"].get("files", []):
        pages.append(get(f"https://data.sec.gov/submissions/{older['name']}").json())

    rows = []
    for page in pages:
        rows.extend(zip(page["form"], page["accessionNumber"], page["primaryDocument"],
                        page["reportDate"], page["filingDate"]))
    return rows
def download_10ks(ticker: str, cik: str):
    recent = get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()["filings"]["recent"]
    filings = zip(recent["form"], recent["accessionNumber"],
                  recent["primaryDocument"], recent["reportDate"], recent["filingDate"])

    for form, accession, doc, report_date, filing_date in all_filings(cik):
        if form != "10-K":  # skips amendments (10-K/A)
            continue
        fiscal_year = int(report_date[:4])
        if fiscal_year not in scope["fiscal_years"]:
            continue

        out = DATA / "10k" / ticker / f"FY{fiscal_year}.html"
        if out.exists():
            print(f"  10-K: already have {ticker} FY{fiscal_year}")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)

        url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
               f"{accession.replace('-', '')}/{doc}")
        out.write_bytes(get(url).content)

        # Save where it came from, so every chunk can cite its source later
        meta = {"ticker": ticker, "fiscal_year": fiscal_year, "report_date": report_date,
                "filing_date": filing_date, "accession": accession, "url": url}
        out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        print(f"  10-K: saved {ticker} FY{fiscal_year}")


if __name__ == "__main__":
    ciks = ticker_to_cik()
    for ticker in scope["companies"]:
        print(ticker)
        cik = ciks[ticker]
        download_company_facts(ticker, cik)
        download_10ks(ticker, cik)