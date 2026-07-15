"""Snapshot selection for archived URLs."""

from typing import Any

import requests

from archive.cache import CacheManager
from archive.services.network import request_with_retry

CDX_API_URL = "https://web.archive.org/cdx"
TIMEOUT = 30


def find_best_snapshot(url: str) -> dict[str, str]:
    """Return the newest HTTP 200 snapshot for a single URL."""
    records = _get_snapshot_records(url)
    snapshots = _records_to_dicts(records)
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.get("statuscode") == "200"
    ]
    if not candidates:
        raise LookupError(f"No HTTP 200 snapshots found for {url}.")

    return max(candidates, key=lambda snapshot: snapshot["timestamp"])


def _get_snapshot_records(url: str) -> list[Any]:
    """Return raw CDX snapshot records for one URL."""
    cache = CacheManager("snapshots")
    cache_key = f"snapshots:{url}"
    print("Checking cache...")
    if cache.exists(cache_key):
        print("✓ Cache hit")
        return cache.get(cache_key)

    print("Cache miss")
    print("Downloading...")
    params = {
        "url": url,
        "output": "json",
    }

    try:
        response = request_with_retry(CDX_API_URL, params=params, timeout=TIMEOUT)
        records = response.json()
        cache.set(cache_key, records)
        print("Saved to cache")
        return records
    except requests.Timeout as exc:
        raise TimeoutError("Timed out while retrieving URL snapshots.") from exc
    except requests.ConnectionError as exc:
        raise ConnectionError("Could not connect to the CDX API.") from exc
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Snapshot lookup failed with HTTP {exc.response.status_code}."
        ) from exc
    except requests.JSONDecodeError as exc:
        raise ValueError("CDX API returned invalid JSON for snapshots.") from exc


def _records_to_dicts(records: list[Any]) -> list[dict[str, str]]:
    """Convert raw CDX JSON rows into dictionaries."""
    if not records:
        return []

    headers = records[0]
    return [
        dict(zip(headers, record))
        for record in records[1:]
        if len(record) == len(headers)
    ]
