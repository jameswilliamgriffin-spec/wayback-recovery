"""Utilities for deduplicating archived CDX URLs."""

from typing import Any


def get_unique_urls(records: list[Any]) -> list[str]:
    """Extract and sort unique original URLs from raw CDX records."""
    if not records:
        return []

    headers = records[0]
    original_index = headers.index("original")

    urls = {
        record[original_index]
        for record in records[1:]
        if len(record) > original_index
    }

    return sorted(urls)
