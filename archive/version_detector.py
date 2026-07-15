"""Detect candidate website versions from CDX metadata."""

from collections import Counter
from typing import Any
from urllib.parse import urlparse


def detect_versions(records: list[Any]) -> list[dict[str, Any]]:
    """Detect likely website versions from collapsed CDX records."""
    profiles = _build_year_profiles(records)
    if not profiles:
        return []

    boundaries = _detect_boundaries(profiles)
    return _build_versions(profiles, boundaries)


def _build_year_profiles(records: list[Any]) -> list[dict[str, Any]]:
    """Build per-year URL and path profiles."""
    if not records:
        return []

    headers = records[0]
    timestamp_index = _column_index(headers, "timestamp")
    original_index = _column_index(headers, "original")
    profiles: dict[str, dict[str, Any]] = {}

    for record in records[1:]:
        if len(record) <= max(timestamp_index, original_index):
            continue

        timestamp = record[timestamp_index]
        url = record[original_index]
        if (
            not isinstance(timestamp, str)
            or len(timestamp) < 4
            or not isinstance(url, str)
        ):
            continue

        year = timestamp[:4]
        profile = profiles.setdefault(year, _empty_profile(year))
        profile["urls"].append(url)
        profile["prefixes"].update(_url_prefixes(url))
        profile["themes"].update(_theme_folders(url))
        profile["asset_paths"].update(_asset_paths(url))

    return [
        _finalize_profile(profile)
        for _, profile in sorted(profiles.items())
    ]


def _empty_profile(year: str) -> dict[str, Any]:
    """Create an empty yearly profile."""
    return {
        "year": year,
        "urls": [],
        "prefixes": set(),
        "themes": set(),
        "asset_paths": set(),
    }


def _finalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Add derived counts and common prefixes to a yearly profile."""
    prefix_counts = Counter(
        prefix
        for url in profile["urls"]
        for prefix in _url_prefixes(url)
    )
    profile["url_count"] = len(profile["urls"])
    profile["common_prefixes"] = {
        prefix
        for prefix, _ in prefix_counts.most_common(10)
    }
    return profile


def _detect_boundaries(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect likely version boundaries between yearly profiles."""
    boundaries = []

    for previous, current in zip(profiles, profiles[1:]):
        reasons = _boundary_reasons(previous, current)
        if reasons:
            boundaries.append(
                {
                    "year": current["year"],
                    "reasons": reasons,
                    "confidence": _confidence(reasons),
                }
            )

    return boundaries


def _boundary_reasons(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Return signals that indicate a version boundary."""
    reasons = []

    if _large_activity_change(previous["url_count"], current["url_count"]):
        reasons.append("Large change in archived URL activity.")

    if previous["themes"] != current["themes"]:
        if previous["themes"] and current["themes"]:
            reasons.append("Theme assets changed.")
        elif current["themes"]:
            reasons.append("Theme folder appeared.")
        else:
            reasons.append("Theme folder disappeared.")

    if _jaccard(previous["common_prefixes"], current["common_prefixes"]) < 0.5:
        reasons.append("Common URL prefixes changed.")

    if _asset_paths_changed(previous["asset_paths"], current["asset_paths"]):
        reasons.append("Asset paths changed.")

    return reasons


def _build_versions(
    profiles: list[dict[str, Any]],
    boundaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build version ranges from detected boundaries."""
    versions = []
    boundary_by_year = {boundary["year"]: boundary for boundary in boundaries}
    starts = [profiles[0]["year"], *[boundary["year"] for boundary in boundaries]]

    for index, start_year in enumerate(starts):
        end_year = _version_end_year(profiles, starts, index)
        boundary = boundary_by_year.get(start_year)

        if boundary is None:
            confidence = "Medium"
            reasons = _stable_reasons(profiles, start_year, end_year)
        else:
            confidence = boundary["confidence"]
            reasons = boundary["reasons"]

        versions.append(_version(start_year, end_year, confidence, reasons))

    return versions


def _version_end_year(
    profiles: list[dict[str, Any]],
    starts: list[str],
    index: int,
) -> str:
    """Return the ending year for a version range."""
    if index + 1 >= len(starts):
        return profiles[-1]["year"]

    next_start_index = _profile_index(profiles, starts[index + 1])
    return profiles[next_start_index - 1]["year"]


def _profile_index(profiles: list[dict[str, Any]], year: str) -> int:
    """Return the index of a yearly profile."""
    for index, profile in enumerate(profiles):
        if profile["year"] == year:
            return index
    raise ValueError(f"Missing profile for year {year}.")


def _version(
    start_year: str,
    end_year: str,
    confidence: str,
    reasons: list[str],
) -> dict[str, Any]:
    """Create a structured version candidate."""
    return {
        "start_year": start_year,
        "end_year": end_year,
        "confidence": confidence,
        "reasons": reasons,
    }


def _stable_reasons(
    profiles: list[dict[str, Any]],
    start_year: str,
    end_year: str,
) -> list[str]:
    """Describe why a range belongs together."""
    range_profiles = [
        profile
        for profile in profiles
        if start_year <= profile["year"] <= end_year
    ]
    theme_sets = {tuple(sorted(profile["themes"])) for profile in range_profiles}
    if len(theme_sets) == 1 and next(iter(theme_sets), ()):
        return ["Theme folder remained consistent."]

    return ["No later version boundary detected."]


def _url_prefixes(url: str) -> set[str]:
    """Return simple path prefixes for URL structure comparison."""
    parts = _path_parts(url)
    if not parts:
        return {"/"}

    prefixes = {f"/{parts[0]}"}
    if len(parts) > 1:
        prefixes.add(f"/{parts[0]}/{parts[1]}")
    return prefixes


def _theme_folders(url: str) -> set[str]:
    """Return detected theme folder names from a URL."""
    parts = _path_parts(url)
    themes = set()

    for index, part in enumerate(parts[:-1]):
        if part == "themes" and index + 1 < len(parts):
            themes.add(parts[index + 1])

    return themes


def _asset_paths(url: str) -> set[str]:
    """Return broad asset path prefixes from a URL."""
    parts = _path_parts(url)
    asset_roots = {"assets", "css", "images", "img", "js", "scripts", "static"}
    paths = set()

    for index, part in enumerate(parts):
        if part in asset_roots:
            paths.add("/" + "/".join(parts[: index + 1]))
        if part == "wp-content" and index + 1 < len(parts):
            paths.add("/" + "/".join(parts[: index + 2]))

    return paths


def _path_parts(url: str) -> list[str]:
    """Return normalized URL path parts."""
    return [
        part
        for part in urlparse(url).path.lower().split("/")
        if part
    ]


def _large_activity_change(previous_count: int, current_count: int) -> bool:
    """Return whether yearly archive activity changed significantly."""
    if previous_count == 0 or current_count == 0:
        return previous_count != current_count

    ratio = current_count / previous_count
    return (
        abs(current_count - previous_count) >= 25
        and (ratio >= 2.0 or ratio <= 0.5)
    )


def _asset_paths_changed(previous: set[str], current: set[str]) -> bool:
    """Return whether asset path sets changed significantly."""
    if not previous and not current:
        return False
    if previous != current and (not previous or not current):
        return True
    return _jaccard(previous, current) < 0.5


def _jaccard(left: set[str], right: set[str]) -> float:
    """Return Jaccard similarity for two sets."""
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _confidence(reasons: list[str]) -> str:
    """Return confidence from the number of boundary signals."""
    if len(reasons) >= 3:
        return "High"
    if len(reasons) == 2:
        return "Medium"
    return "Low"


def _column_index(headers: list[str], column: str) -> int:
    """Return the index for a CDX column name."""
    try:
        return headers.index(column)
    except ValueError as exc:
        raise ValueError(f"CDX records are missing the {column!r} column.") from exc
