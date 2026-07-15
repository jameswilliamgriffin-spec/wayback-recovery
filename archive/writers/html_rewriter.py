"""Rewrite recovered HTML references to local recovered files."""

import re
from urllib.parse import urlparse

LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(
    r"""(?P<name>[\w:-]+)\s*=\s*(?:(?P<quote>["'])(?P<quoted>.*?)(?P=quote)|(?P<unquoted>[^\s"'=<>`]+))""",
    re.IGNORECASE,
)


def rewrite_html(
    html: str,
    css_map: dict[str, str],
    image_map: dict[str, str] | None = None,
) -> str:
    """Rewrite recovered asset references in HTML to local paths."""

    def replace_link(match: re.Match[str]) -> str:
        tag = match.group(0)
        attributes = _attributes(tag)
        rel = attributes.get("rel", "").lower().split()
        href = attributes.get("href")
        if "stylesheet" not in rel or not href:
            return tag

        replacement = _find_css_replacement(href, css_map)
        if replacement is None:
            return tag

        filename = replacement.rsplit("/", 1)[-1]
        print(f"✓ {filename}")
        return _replace_href(tag, replacement)

    def replace_image(match: re.Match[str]) -> str:
        tag = match.group(0)
        attributes = _attributes(tag)
        src = attributes.get("src")
        if not src:
            return tag

        replacement = _find_asset_replacement(src, image_map or {})
        if replacement is None:
            return tag

        return _replace_src(tag, replacement)

    html = LINK_TAG_RE.sub(replace_link, html)
    return IMG_TAG_RE.sub(replace_image, html)


def _attributes(tag: str) -> dict[str, str]:
    """Return attributes from a start tag keyed by lowercase name."""
    attributes: dict[str, str] = {}
    for match in ATTR_RE.finditer(tag):
        value = match.group("quoted")
        if value is None:
            value = match.group("unquoted") or ""
        attributes[match.group("name").lower()] = value
    return attributes


def _find_css_replacement(href: str, css_map: dict[str, str]) -> str | None:
    """Find a local CSS path for an href or equivalent archive URL."""
    return _find_asset_replacement(href, css_map)


def _find_asset_replacement(url: str, asset_map: dict[str, str]) -> str | None:
    """Find a local path for an asset URL or equivalent archive URL."""
    stripped = _strip_wayback_prefix(url)
    candidates = [url, stripped, _swap_scheme(url), _swap_scheme(stripped)]
    for candidate in candidates:
        if candidate and candidate in asset_map:
            return asset_map[candidate]
    return None


def _replace_href(tag: str, replacement: str) -> str:
    """Replace only the href attribute value inside a link tag."""

    def replace_attr(match: re.Match[str]) -> str:
        name = match.group("name")
        if name.lower() != "href":
            return match.group(0)

        quote = match.group("quote")
        if quote:
            return f"{name}={quote}{replacement}{quote}"
        return f"{name}={replacement}"

    return ATTR_RE.sub(replace_attr, tag)


def _replace_src(tag: str, replacement: str) -> str:
    """Replace only the src attribute value inside an img tag."""

    def replace_attr(match: re.Match[str]) -> str:
        name = match.group("name")
        if name.lower() != "src":
            return match.group(0)

        quote = match.group("quote")
        if quote:
            return f"{name}={quote}{replacement}{quote}"
        return f"{name}={replacement}"

    return ATTR_RE.sub(replace_attr, tag)


def _strip_wayback_prefix(url: str) -> str:
    """Return the original URL embedded in a Wayback URL, when present."""
    parsed = urlparse(url)
    if parsed.netloc not in {"web.archive.org", "www.web.archive.org"}:
        return ""

    parts = parsed.path.split("/", 3)
    if len(parts) < 4 or parts[1] != "web":
        return ""
    return parts[3]


def _swap_scheme(url: str) -> str:
    """Return the HTTP/HTTPS equivalent of a URL."""
    if url.startswith("http://"):
        return f"https://{url.removeprefix('http://')}"
    if url.startswith("https://"):
        return f"http://{url.removeprefix('https://')}"
    return ""
