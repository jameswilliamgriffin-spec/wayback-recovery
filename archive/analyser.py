"""URL analysis helpers for archived site structures."""

from collections.abc import Callable
from urllib.parse import urlparse

AnalysisRule = Callable[[str], bool]

CATEGORY_ORDER = [
    "pages",
    "posts",
    "images",
    "css",
    "javascript",
    "uploads",
    "feeds",
    "categories",
    "tags",
    "admin",
    "other",
]

IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".tif",
    ".tiff",
    ".webp",
}


def analyse_urls(urls: list[str]) -> dict[str, int]:
    """Classify URLs into simple structure and asset categories."""
    summary = {category: 0 for category in CATEGORY_ORDER}

    for url in urls:
        matched = False
        for category, rule in _rules().items():
            if rule(url):
                summary[category] += 1
                matched = True

        if not matched:
            summary["other"] += 1

    return summary


def _rules() -> dict[str, AnalysisRule]:
    """Return category rules in display order."""
    return {
        "pages": _is_page,
        "posts": _is_post,
        "images": _has_extension(IMAGE_EXTENSIONS),
        "css": _has_extension({".css"}),
        "javascript": _has_extension({".js", ".mjs"}),
        "uploads": _contains_path_part("uploads"),
        "feeds": _is_feed,
        "categories": _contains_path_part("category"),
        "tags": _contains_path_part("tag"),
        "admin": _is_admin,
    }


def _path(url: str) -> str:
    """Return a normalized URL path."""
    return urlparse(url).path.lower()


def _has_extension(extensions: set[str]) -> AnalysisRule:
    """Build a rule that checks for one of the given file extensions."""

    def rule(url: str) -> bool:
        return any(_path(url).endswith(extension) for extension in extensions)

    return rule


def _contains_path_part(part: str) -> AnalysisRule:
    """Build a rule that checks for a path segment."""

    def rule(url: str) -> bool:
        return part in _path(url).strip("/").split("/")

    return rule


def _is_page(url: str) -> bool:
    """Return whether a URL looks like a general website page."""
    path = _path(url)
    if (
        _is_post(url)
        or _is_feed(url)
        or _is_admin(url)
        or _contains_path_part("category")(url)
        or _contains_path_part("tag")(url)
        or _contains_path_part("uploads")(url)
    ):
        return False

    has_page_extension = path.endswith((".html", ".htm", ".php"))
    has_file_extension = "." in path.rsplit("/", maxsplit=1)[-1]
    return (
        path in {"", "/"}
        or path.endswith("/")
        or has_page_extension
        or not has_file_extension
    )


def _is_post(url: str) -> bool:
    """Return whether a URL looks like a dated blog post."""
    parts = _path(url).strip("/").split("/")
    return len(parts) >= 4 and all(part.isdigit() for part in parts[:3])


def _is_feed(url: str) -> bool:
    """Return whether a URL looks like a feed URL."""
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    return path.endswith("/feed") or path.endswith(".rss") or "feed=" in parsed.query


def _is_admin(url: str) -> bool:
    """Return whether a URL looks like an admin URL."""
    path = _path(url)
    return "/wp-admin/" in path or path.endswith("/wp-admin") or "wp-login.php" in path
