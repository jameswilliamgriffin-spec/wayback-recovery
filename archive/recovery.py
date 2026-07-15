"""Homepage recovery workflow for selected website versions."""

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from archive.cache import CacheManager
from archive.cdx import CDXClient
from archive.downloader import SnapshotDownloader
from archive.network import request_with_retry
from archive.version_detector import detect_versions

CDX_API_URL = "https://web.archive.org/cdx"
OUTPUT_PATH = Path("output/pages/index.html")
TIMEOUT = 30


def recover_homepage(domain: str, version: int) -> Path:
    """Recover the homepage HTML for a selected website version."""
    records = CDXClient().get_records(domain, collapse=True)
    homepage_url = _find_homepage_url(records, domain)
    version_range = _version_range(records, domain, version)
    snapshots = _get_homepage_snapshots(homepage_url)
    snapshot = _select_snapshot(snapshots, version_range)
    html = SnapshotDownloader().download(snapshot)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    return OUTPUT_PATH


def _find_homepage_url(records: list[Any], domain: str) -> str:
    """Find the archived homepage URL from collapsed CDX records."""
    clean_domain = _clean_domain(domain)
    urls = [
        record["original"]
        for record in _records_to_dicts(records)
        if _is_homepage(record.get("original", ""), clean_domain)
    ]
    if not urls:
        raise LookupError(f"No archived homepage URL found for {domain}.")

    return _preferred_homepage_url(urls)


def _version_range(records: list[Any], domain: str, version: int) -> dict[str, Any]:
    """Return the requested detected version range for a domain."""
    versions = detect_versions(records)
    if version < 1 or version > len(versions):
        raise ValueError(f"Version {version} was not detected for {domain}.")

    return versions[version - 1]


def _is_homepage(url: str, domain: str) -> bool:
    """Return whether a URL is the homepage for a domain."""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path or "/"
    return host == domain and path == "/"


def _preferred_homepage_url(urls: list[str]) -> str:
    """Return the preferred homepage URL from discovered candidates."""
    for url in sorted(urls):
        if url.startswith("https://"):
            return url
    return sorted(urls)[0]


def _clean_domain(domain: str) -> str:
    """Normalize a domain for hostname comparison."""
    return domain.removeprefix("https://").removeprefix("http://").strip("/").lower()


def _get_homepage_snapshots(homepage_url: str) -> list[dict[str, str]]:
    """Return every CDX snapshot for the homepage URL."""
    cache = CacheManager("snapshots")
    cache_key = f"homepage-snapshots:{homepage_url}"
    print("Checking cache...")
    if cache.exists(cache_key):
        print("✓ Cache hit")
        records = cache.get(cache_key)
        return _records_to_dicts(records)

    print("Cache miss")
    print("Downloading...")
    params = {
        "url": homepage_url,
        "output": "json",
    }

    try:
        response = request_with_retry(CDX_API_URL, params=params, timeout=TIMEOUT)
        records = response.json()
        cache.set(cache_key, records)
        print("Saved to cache")
    except requests.Timeout as exc:
        raise TimeoutError("Timed out while retrieving homepage snapshots.") from exc
    except requests.ConnectionError as exc:
        raise ConnectionError("Could not connect to the CDX API.") from exc
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Homepage snapshot lookup failed with HTTP {exc.response.status_code}."
        ) from exc
    except requests.JSONDecodeError as exc:
        raise ValueError("CDX API returned invalid JSON for homepage snapshots.") from exc

    return _records_to_dicts(records)


def _select_snapshot(
    snapshots: list[dict[str, str]],
    version_range: dict[str, Any],
) -> dict[str, str]:
    """Select the newest HTTP 200 snapshot inside a version range."""
    start_year = str(version_range["start_year"])
    end_year = str(version_range["end_year"])
    candidates = [
        snapshot
        for snapshot in snapshots
        if snapshot.get("statuscode") == "200"
        and start_year <= snapshot.get("timestamp", "")[:4] <= end_year
    ]
    if not candidates:
        raise LookupError(
            f"No HTTP 200 homepage snapshots found for version "
            f"{start_year}-{end_year}."
        )

    return max(candidates, key=lambda snapshot: snapshot["timestamp"])


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
