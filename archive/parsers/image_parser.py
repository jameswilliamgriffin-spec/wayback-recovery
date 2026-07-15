"""HTML image parsing helpers."""

from html.parser import HTMLParser


class _ImageParser(HTMLParser):
    """Collect image src attributes from img tags."""

    def __init__(self) -> None:
        super().__init__()
        self.images: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return

        attributes = {name.lower(): value for name, value in attrs if value is not None}
        src = attributes.get("src", "").strip()
        if src and not src.lower().startswith("data:"):
            self.images.append(src)


def extract_images(html: str) -> list[str]:
    """Return image URLs found in img src attributes."""
    parser = _ImageParser()
    parser.feed(html)
    return parser.images
