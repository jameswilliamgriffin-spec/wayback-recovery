"""Download archived snapshot content."""

import requests

from archive.cache import CacheManager
from archive.network import request_with_retry

TIMEOUT = 30


class SnapshotDownloader:
    """Download content from selected Internet Archive snapshots."""

    def download(self, snapshot: dict[str, str]) -> str:
        """Download snapshot HTML and return it as text."""
        timestamp = snapshot["timestamp"]
        original_url = snapshot["original"]
        cache = CacheManager("pages", extension="html")
        cache_key = f"page:{timestamp}:{original_url}"
        print("Checking cache...")
        if cache.exists(cache_key):
            print("✓ Cache hit")
            return cache.get(cache_key)

        print("Cache miss")
        print("Downloading...")
        snapshot_url = f"https://web.archive.org/web/{timestamp}id_/{original_url}"

        try:
            response = request_with_retry(snapshot_url, timeout=TIMEOUT)
            html = response.text
            cache.set(cache_key, html)
            print("Saved to cache")
            return html
        except requests.Timeout as exc:
            raise TimeoutError("Timed out while downloading snapshot HTML.") from exc
        except requests.ConnectionError as exc:
            raise ConnectionError("Could not connect to download snapshot HTML.") from exc
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"Snapshot download failed with HTTP {exc.response.status_code}."
            ) from exc
