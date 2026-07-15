"""Network helpers with retry support for Internet Archive requests."""

import time
from typing import Any

import requests

RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


def request_with_retry(url: str, max_retries: int = 5, **kwargs: Any) -> requests.Response:
    """Send a GET request and retry temporary HTTP failures."""
    attempt = 1

    while True:
        print(f"Attempt {attempt}...")
        response = requests.get(url, **kwargs)

        if response.status_code not in RETRY_STATUS_CODES:
            response.raise_for_status()
            print("Success")
            return response

        if attempt > max_retries:
            response.raise_for_status()

        delay = 2 ** (attempt - 1)
        unit = "second" if delay == 1 else "seconds"
        print(f"Retrying in {delay} {unit}...")
        time.sleep(delay)
        attempt += 1
