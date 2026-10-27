import json
import sys
from pathlib import Path

ticker, year, keyword = sys.argv[1], sys.argv[2], sys.argv[3].lower()
ROOT = Path(__file__).resolve().parent.parent
meta = json.loads((ROOT / "data" / "10k" / ticker / f"FY{year}.json").read_text())
facts = json.loads((ROOT / "data" / "facts" / f"{ticker}.json").read_text())["facts"]["us-gaap"]

for tag, info in facts.items():
    if keyword not in tag.lower():
        continue
    for fact in info.get("units", {}).get("USD", []):
        if fact.get("accn") == meta["accession"] and fact["end"] == meta["report_date"]:
            print(f"{tag}: {fact['val']:,}")