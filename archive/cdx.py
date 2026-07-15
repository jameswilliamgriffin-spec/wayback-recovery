"""CDX API client interface for Wayback Recovery."""

from typing import Any

import requests

from archive.cache import CacheManager
from archive.network import request_with_retry


class CDXClient:
    """Represent communication with the Internet Archive CDX API."""

    def __init__(self) -> None:
        """Initialize a CDX client."""
        self.api_url = "https://web.archive.org/cdx"
        self.timeout = 30

    def get_records(self, domain: str, collapse: bool = False) -> list[Any]:
        """Return archive records for a domain."""
        cache = CacheManager("cdx")
        cache_key = f"records:{domain}:collapse={collapse}"
        print("Checking cache...")
        if cache.exists(cache_key):
            print("✓ Cache hit")
            return cache.get(cache_key)

        print("Cache miss")
        print("Downloading...")
        params = {
            "url": f"{domain}/*",
            "output": "json",
        }
        if collapse:
            params["collapse"] = "urlkey"

        try:
            response = request_with_retry(
                self.api_url,
                params=params,
                timeout=self.timeout,
            )
            records = response.json()
            cache.set(cache_key, records)
            print("Saved to cache")
            return records
        except requests.Timeout as exc:
            raise TimeoutError("Timed out while contacting the CDX API.") from exc
        except requests.ConnectionError as exc:
            raise ConnectionError("Could not connect to the CDX API.") from exc
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"CDX API request failed with HTTP {exc.response.status_code}."
            ) from exc
        except requests.JSONDecodeError as exc:
            raise ValueError("CDX API returned invalid JSON.") from exc

    def get_unique_urls(self, domain: str) -> list[str]:
        """Return unique archived URLs for a domain."""
        raise NotImplementedError

    def get_snapshots(self, url: str) -> list[dict[str, str]]:
        """Return archived snapshots for a URL."""
        raise NotImplementedError

    def find_best_snapshot(self, url: str) -> dict[str, str] | None:
        """Return the best available snapshot for a URL."""
        raise NotImplementedError
