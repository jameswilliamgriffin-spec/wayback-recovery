"""HTML parsing helpers for recovered pages."""

from html.parser import HTMLParser


class _StylesheetParser(HTMLParser):
    """Collect stylesheet hrefs from link tags."""

    def __init__(self) -> None:
        super().__init__()
        self.stylesheets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return

        attributes = {name.lower(): value for name, value in attrs if value is not None}
        rel_values = attributes.get("rel", "").lower().split()
        href = attributes.get("href")
        if href and "stylesheet" in rel_values:
            self.stylesheets.append(href)


def extract_stylesheets(html: str) -> list[str]:
    """Return stylesheet URLs found in link rel=\"stylesheet\" tags."""
    parser = _StylesheetParser()
    parser.feed(html)
    return parser.stylesheets
