import os

import requests
from dotenv import load_dotenv

load_dotenv()
headers = {"User-Agent": os.environ["SEC_USER_AGENT"]}
r = requests.get(
    "https://data.sec.gov/submissions/CIK0000320193.json",
    headers=headers,
    timeout=30,
)
r.raise_for_status()
data = r.json()
print(data["name"])
print(data["filings"]["recent"]["form"][:5])
