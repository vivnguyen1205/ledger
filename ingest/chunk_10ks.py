import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
scope = json.loads((ROOT / "scope.json").read_text())

SECTION_NAMES = {"1": "Item 1 Business", "1A": "Item 1A Risk Factors", "7": "Item 7 MD&A"}
WANTED = [s.split()[1].upper() for s in scope["sections"]]  # "Item 1A" -> "1A"
HEADER = re.compile(r"^\s*item\s+(\d{1,2}[a-c]?)\b", re.IGNORECASE | re.MULTILINE)
# Intel's 10-K skips "Item" headings; each page is labelled with its own section names instead
ALT_HEADERS = [
    ("1", re.compile(r"^\s*(fundamentals of our business|our business)\s*$", re.I | re.M)),
    ("1A", re.compile(r"^\s*risk factors( and other key information)?\s*$", re.I | re.M)),
    ("7", re.compile(r"^\s*management.s discussion and analysis\s*$", re.I | re.M)),
    ("8", re.compile(r"^\s*financial statements and supplemental details\s*$", re.I | re.M)),
]
SMALL_TABLE_WORDS = 15  # tables this short are headings laid out as tables, not data
CHUNK_WORDS = 600
OVERLAP = 100


def html_to_text(path: Path) -> str:
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    # Tables are mostly financial statements; the numbers already live in SQL
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    for table in soup.find_all("table"):
        # Big tables are mostly financial statements (already in SQL), but some
        # filings (e.g. AMZN, INTC) put section headings in tiny tables, so keep those
        if table.decomposed:
            continue
        if len(table.get_text(" ").split()) > SMALL_TABLE_WORDS:
            table.decompose()
    # Inline XBRL files hide a block of machine-readable metadata
    for tag in soup.find_all(style=re.compile(r"display:\s*none", re.IGNORECASE)):
        tag.decompose()
    text = soup.get_text("\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text)


def split_sections(text: str) -> dict:
    """Map item codes ("1A") to section text.

    Each item heading appears in the table of contents and at the real section,
    and some filings (e.g. MSFT) repeat it as a running header on every page.
    So a section runs from a heading until the next heading with a *different*
    code, and when a code has several such spans we keep the longest.
    """
    matches = [(m.start(), m.group(1).upper()) for m in HEADER.finditer(text)]
    if not any(code in WANTED for _, code in matches):
        matches = sorted((m.start(), code) for code, pattern in ALT_HEADERS
                         for m in pattern.finditer(text))
    best = {}
    i = 0
    while i < len(matches):
        start, code = matches[i]
        j = i + 1
        while j < len(matches) and matches[j][1] == code:
            j += 1  # skip repeats of the same heading (running page headers)
        end = matches[j][0] if j < len(matches) else len(text)
        body = text[start:end]
        if len(body) > len(best.get(code, "")):
            best[code] = body
        i = j
    return best


def chunk_words(text: str):
    words = text.split()
    step = CHUNK_WORDS - OVERLAP
    for start in range(0, max(len(words) - OVERLAP, 1), step):
        yield " ".join(words[start:start + CHUNK_WORDS])


def main():
    out_dir = DATA / "chunks"
    out_dir.mkdir(exist_ok=True)
    for ticker in scope["companies"]:
        for html_path in sorted((DATA / "10k" / ticker).glob("FY*.html")):
            meta = json.loads(html_path.with_suffix(".json").read_text())
            sections = split_sections(html_to_text(html_path))
            report, rows = [], []
            for code in WANTED:
                body = sections.get(code, "")
                report.append(f"{code}: {len(body.split()):>6} words")
                for i, chunk in enumerate(chunk_words(body) if body else []):
                    rows.append({
                        "ticker": ticker,
                        "fiscal_year": meta["fiscal_year"],
                        "section": SECTION_NAMES[code],
                        "chunk_index": i,
                        "content": chunk,
                        "source_url": meta["url"],
                    })
            out = out_dir / f"{ticker}_FY{meta['fiscal_year']}.jsonl"
            out.write_text("".join(json.dumps(r) + "\n" for r in rows))
            print(f"{ticker} FY{meta['fiscal_year']}  " + "  ".join(report) + f"  -> {len(rows)} chunks")


if __name__ == "__main__":
    main()