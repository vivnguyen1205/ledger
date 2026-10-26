import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

HEADERS = {"User-Agent": os.environ["SEC_USER_AGENT"]}
MIN_INTERVAL = 0.15  # seconds between requests, keeps us under 10/sec
_last_request = 0.0


def get(url: str) -> requests.Response:
    """GET a SEC URL with the required header and rate limiting."""
    global _last_request
    wait = MIN_INTERVAL - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    response = requests.get(url, headers=HEADERS, timeout=30)
    _last_request = time.time()
    response.raise_for_status()  # stop loudly on 403/404 instead of saving junk
    return response