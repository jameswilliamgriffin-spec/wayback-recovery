"""Build historical timelines from CDX archive records."""

from typing import Any


def build_timeline(records: list[Any]) -> list[dict[str, str | int]]:
    """Group collapsed CDX records by snapshot year."""
    if not records:
        return []

    headers = records[0]
    timestamp_index = _column_index(headers, "timestamp")
    years: dict[str, list[str]] = {}

    for record in records[1:]:
        if len(record) <= timestamp_index:
            continue

        timestamp = record[timestamp_index]
        if not isinstance(timestamp, str) or len(timestamp) < 8:
            continue

        year = timestamp[:4]
        years.setdefault(year, []).append(timestamp)

    return [
        {
            "year": year,
            "archived_urls": len(timestamps),
            "first_snapshot": _format_date(min(timestamps)),
            "last_snapshot": _format_date(max(timestamps)),
        }
        for year, timestamps in sorted(years.items())
    ]


def _column_index(headers: list[str], column: str) -> int:
    """Return the index for a CDX column name."""
    try:
        return headers.index(column)
    except ValueError as exc:
        raise ValueError(f"CDX records are missing the {column!r} column.") from exc


def _format_date(timestamp: str) -> str:
    """Format a CDX timestamp as YYYY-MM-DD."""
    return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
