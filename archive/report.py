"""Text report generation for Wayback Recovery."""

REPORT_FIELDS = [
    ("Total unique URLs", "total_unique_urls"),
    ("Pages", "pages"),
    ("Blog posts", "posts"),
    ("Images", "images"),
    ("Uploads", "uploads"),
    ("CSS", "css"),
    ("JavaScript", "javascript"),
    ("Feeds", "feeds"),
    ("Categories", "categories"),
    ("Tags", "tags"),
]

RECOVER_RECOMMENDATIONS = [
    "pages",
    "posts",
    "uploads",
]

IGNORE_RECOMMENDATIONS = [
    "feeds",
    "admin",
    "search pages",
]


def generate_report(url_analysis: dict[str, int]) -> str:
    """Generate a text recovery report from URL analysis counts."""
    lines = ["Recovery Report", "", "Discovered URLs"]

    for label, key in REPORT_FIELDS:
        lines.append(f"{label}: {url_analysis.get(key, 0)}")

    lines.extend(["", "Recommendations", "", "Recover:"])
    lines.extend(_format_recommendations(RECOVER_RECOMMENDATIONS))

    lines.extend(["", "Ignore:"])
    lines.extend(_format_recommendations(IGNORE_RECOMMENDATIONS))

    return "\n".join(lines)


def _format_recommendations(recommendations: list[str]) -> list[str]:
    """Format recommendation labels as bullet lines."""
    return [f"- {recommendation}" for recommendation in recommendations]
