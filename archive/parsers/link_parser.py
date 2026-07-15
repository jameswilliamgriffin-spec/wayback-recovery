"""HTML link parsing helpers."""

from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urldefrag, urljoin, urlparse

IGNORED_EXTENSIONS = {
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".pdf",
    ".png",
    ".svg",
    ".webp",
}
HTML_EXTENSIONS = {"", ".asp", ".aspx", ".htm", ".html", ".php"}


class _LinkParser(HTMLParser):
    """Collect href attributes from anchor tags."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attributes = {name.lower(): value for name, value in attrs if value is not None}
        href = attributes.get("href", "").strip()
        if href:
            self.links.append(href)


def extract_internal_links(html: str, base_url: str) -> list[str]:
    """Return same-domain HTML page links found in anchor tags."""
    parser = _LinkParser()
    parser.feed(html)

    base_host = _normalized_host(base_url)
    base_page = _canonical_page_url(base_url)
    links: list[str] = []
    seen: set[str] = set()

    for href in parser.links:
        if _ignored_href(href):
            continue

        url, fragment = urldefrag(urljoin(base_url, href))
        if fragment and not url:
            continue
        if _normalized_host(url) != base_host:
            continue
        if not _is_html_page(url):
            continue
        canonical_url = _canonical_page_url(url)
        if canonical_url == base_page:
            continue
        if canonical_url in seen:
            continue

        links.append(url)
        seen.add(canonical_url)

    return links


def _ignored_href(href: str) -> bool:
    lowered = href.lower()
    return (
        lowered.startswith("#")
        or lowered.startswith("mailto:")
        or lowered.startswith("javascript:")
        or lowered.startswith("tel:")
    )


def _is_html_page(url: str) -> bool:
    path = urlparse(url).path
    suffix = PurePosixPath(path).suffix.lower()
    return suffix in HTML_EXTENSIONS and suffix not in IGNORED_EXTENSIONS


def _normalized_host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _canonical_page_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{_normalized_host(url)}{path}{query}"
