"""Homepage recovery workflow for selected website versions."""

from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests

from archive.cache import CacheManager
from archive.downloader import SnapshotDownloader
from archive.models.task import RecoveryTask
from archive.parsers.html_parser import extract_stylesheets
from archive.parsers.image_parser import extract_images
from archive.parsers.link_parser import extract_internal_links
from archive.recovery.queue import RecoveryQueue
from archive.services.cdx import CDXClient
from archive.services.network import request_with_retry
from archive.version_detector import detect_versions
from archive.writers.html_rewriter import rewrite_html

CDX_API_URL = "https://web.archive.org/cdx"
OUTPUT_DIR = Path("output")
TIMEOUT = 30


def recover_homepage(domain: str, version: int) -> Path:
    """Recover the homepage HTML for a selected website version."""
    current_step = ""

    try:
        current_step = "Step 1/9: Loading collapsed CDX records"
        print()
        print("Step 1/9")
        print("Loading collapsed CDX records...")
        records = CDXClient().get_records(domain, collapse=True)
        print(f"✓ Loaded {len(_records_to_dicts(records))} records")

        current_step = "Step 2/9: Finding homepage URL"
        print()
        print("Step 2/9")
        print("Finding homepage URL...")
        homepage_url = _find_homepage_url(records, domain)
        print("✓ Homepage found")

        current_step = "Step 3/9: Resolving version range"
        print()
        print("Step 3/9")
        print("Resolving version range...")
        version_range = _version_range(records, domain, version)
        print(
            "✓ Version range "
            f"{version_range['start_year']}-{version_range['end_year']} selected"
        )

        current_step = "Step 4/9: Loading homepage snapshots"
        print()
        print("Step 4/9")
        print("Loading homepage snapshots...")
        snapshots = _get_homepage_snapshots(homepage_url, version_range)
        print(f"✓ {len(snapshots)} snapshots found")

        current_step = "Step 5/9: Selecting best snapshot"
        print()
        print("Step 5/9")
        print("Selecting best snapshot...")
        snapshot = _select_snapshot(snapshots, version_range)
        print(f"✓ Selected {_format_snapshot_date(snapshot)}")

        current_step = "Step 6/9: Initializing recovery queue"
        print()
        print("Step 6/9")
        print("Initializing recovery queue...")
        site_output_dir = _site_output_dir(domain)
        _ensure_site_output_dirs(site_output_dir)
        queue = RecoveryQueue()
        _enqueue_task(
            queue,
            RecoveryTask(
                task_type="html",
                url=homepage_url,
                snapshot=snapshot["timestamp"],
                source="Homepage",
            ),
        )

        current_step = "Step 7/9: Processing recovery queue"
        print()
        print("Step 7/9")
        print("Processing recovery queue...")
        recovered = _process_recovery_queue(
            queue,
            homepage_url,
            snapshot["timestamp"],
            site_output_dir,
        )
        html = recovered["html"]
        css_map = recovered["css_map"]
        image_map = recovered["image_map"]

        current_step = "Step 8/9: Rewriting HTML"
        print()
        print("Step 8/9")
        print("Rewriting HTML...")
        html = rewrite_html(html, css_map, image_map)

        current_step = "Step 9/9: Saving HTML"
        print()
        print("Step 9/9")
        print("Saving HTML...")
        output_path = site_output_dir / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print("✓ Saved:")
        print(output_path)

        return output_path
    except Exception:
        print()
        print(f"Failed during {current_step}")
        raise


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


def _get_homepage_snapshots(
    homepage_url: str,
    version_range: dict[str, Any],
) -> list[dict[str, str]]:
    """Return CDX snapshots for the homepage URL within a version range."""
    start_year = str(version_range["start_year"])
    end_year = str(version_range["end_year"])
    cache = CacheManager("snapshots")
    cache_key = f"homepage-snapshots:{homepage_url}:{start_year}-{end_year}"
    print("Checking cache...")
    if cache.exists(cache_key):
        print("✓ Cache hit")
        records = cache.get(cache_key)
        return _records_to_dicts(records)

    print("Cache miss")
    print("Requesting homepage snapshots for:")
    print(f"{start_year}–{end_year}")
    print("Downloading...")
    params = {
        "url": homepage_url,
        "output": "json",
        "from": start_year,
        "to": end_year,
    }

    try:
        _print_cdx_request(CDX_API_URL, params)
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


def _print_cdx_request(url: str, params: dict[str, str]) -> None:
    """Print the exact CDX request parameters for diagnostics."""
    print()
    print("CDX Request")
    print()
    print("URL:")
    print(url)
    print()
    print("Parameters:")
    for key, value in params.items():
        print(f"{key}={value}")


def _site_output_dir(domain: str) -> Path:
    """Return the self-contained output folder for a recovered site."""
    host = _clean_domain(domain).removeprefix("www.").split("/", 1)[0]
    site_name = host.split(".", 1)[0]
    return OUTPUT_DIR / site_name


def _ensure_site_output_dirs(site_output_dir: Path) -> None:
    """Create the standard output folders for a recovered site."""
    for folder in ("css", "images", "js", "assets"):
        (site_output_dir / folder).mkdir(parents=True, exist_ok=True)


def _enqueue_task(
    queue: RecoveryQueue,
    task: RecoveryTask,
    print_progress: bool = True,
) -> bool:
    """Enqueue a recovery task and print queue progress."""
    queued = queue.enqueue(task)
    if queued and print_progress:
        _print_queue(queue)
    return queued


def _print_queue(queue: RecoveryQueue) -> None:
    """Print pending queue tasks in order."""
    print()
    print("Queue")
    for index, task in enumerate(queue):
        if index:
            print("↓")
        print(_task_label(task))


def _task_label(task: RecoveryTask) -> str:
    """Return a human-readable task label."""
    task_type = task.task_type.upper()
    label = task.source if task.task_type == "html" else _asset_filename(task.url)
    if task.task_type == "page":
        label = task.source or _page_label(task.url)
    return f"[{task_type}]\n{label}"


def _process_recovery_queue(
    queue: RecoveryQueue,
    homepage_url: str,
    timestamp: str,
    site_output_dir: Path,
) -> dict[str, Any]:
    """Process queued recovery tasks."""
    html = ""
    css_map: dict[str, str] = {}
    image_map: dict[str, str] = {}
    css_filenames: dict[str, str] = {}
    image_filenames: dict[str, str] = {}
    image_stats = {"recovered": 0, "failed": 0, "skipped": 0}

    while not queue.empty():
        task = queue.peek()
        task_type = task.task_type

        if task_type == "page":
            break

        task = queue.dequeue()

        if task_type == "html":
            snapshot = {
                "timestamp": task.snapshot or timestamp,
                "original": task.url,
            }
            html = SnapshotDownloader().download(snapshot)
            print("✓ HTML downloaded")
            _enqueue_stylesheet_tasks(queue, html, homepage_url, timestamp, css_filenames)
            skipped = _enqueue_image_tasks(
                queue,
                html,
                homepage_url,
                timestamp,
                image_filenames,
            )
            image_stats["skipped"] += skipped
            _enqueue_page_tasks(queue, html, homepage_url, timestamp)
            continue

        if task_type == "css":
            _recover_stylesheet_task(task, site_output_dir, css_map, css_filenames)
            continue

        if task_type == "image":
            _recover_image_task(
                task,
                site_output_dir,
                image_map,
                image_stats,
                image_filenames,
            )
            continue

        raise ValueError(f"Unknown recovery task type: {task_type}")

    _print_image_recovery_summary(
        image_stats["recovered"],
        image_stats["failed"],
        image_stats["skipped"],
    )
    return {
        "html": html,
        "css_map": css_map,
        "image_map": image_map,
    }


def _enqueue_stylesheet_tasks(
    queue: RecoveryQueue,
    html: str,
    homepage_url: str,
    timestamp: str,
    filenames: dict[str, str],
) -> None:
    """Enqueue stylesheets referenced by recovered homepage HTML."""
    stylesheet_urls = extract_stylesheets(html)
    print(f"Found {len(stylesheet_urls)} stylesheets")
    if not stylesheet_urls:
        return

    print("Downloading...")
    used_filenames: set[str] = set()

    for stylesheet_url in stylesheet_urls:
        resolved_url = _resolve_asset_url(homepage_url, stylesheet_url)
        filename = _stylesheet_filename(resolved_url, used_filenames)
        filenames[resolved_url] = filename
        _enqueue_task(
            queue,
            RecoveryTask(
                task_type="css",
                url=resolved_url,
                snapshot=timestamp,
                source=stylesheet_url,
            ),
        )


def _enqueue_image_tasks(
    queue: RecoveryQueue,
    html: str,
    homepage_url: str,
    timestamp: str,
    filenames: dict[str, str],
) -> int:
    """Enqueue images referenced directly by recovered homepage HTML."""
    image_urls = extract_images(html)
    images, skipped = _internal_images(image_urls, homepage_url)

    print(f"Found {len(images)} images")
    if not images:
        return skipped

    print("Downloading...")
    used_filenames: set[str] = set()

    for image_url, resolved_url in images:
        filename = _image_filename(resolved_url, used_filenames)
        filenames[resolved_url] = filename
        _enqueue_task(
            queue,
            RecoveryTask(
                task_type="image",
                url=resolved_url,
                snapshot=timestamp,
                source=image_url,
            ),
        )

    return skipped


def _enqueue_page_tasks(
    queue: RecoveryQueue,
    html: str,
    homepage_url: str,
    timestamp: str,
) -> None:
    """Discover and enqueue internal HTML pages without processing them."""
    links = extract_internal_links(html, homepage_url)
    print(f"Found {len(links)} internal pages")
    if not links:
        return

    print()
    print("Queued:")
    queued_labels: list[str] = []
    for link in links:
        label = _page_label(link)
        queued = _enqueue_task(
            queue,
            RecoveryTask(
                task_type="page",
                url=link,
                snapshot=timestamp,
                source=label,
            ),
            print_progress=False,
        )
        if queued:
            queued_labels.append(label)

    for label in queued_labels:
        print(label)
    if queued_labels:
        _print_queue(queue)


def _recover_stylesheet_task(
    task: RecoveryTask,
    site_output_dir: Path,
    css_map: dict[str, str],
    filenames: dict[str, str],
) -> None:
    """Download one queued stylesheet task."""
    css_output_dir = site_output_dir / "css"
    filename = filenames[task.url]
    archived_url = _archived_asset_url(task.url, task.snapshot or "")
    response = request_with_retry(archived_url, timeout=TIMEOUT)
    (css_output_dir / filename).write_text(response.text, encoding="utf-8")
    css_map.update(
        _asset_map_entries(
            task.source or task.url,
            task.url,
            archived_url,
            f"css/{filename}",
        )
    )
    print(f"✓ {filename}")


def _recover_image_task(
    task: RecoveryTask,
    site_output_dir: Path,
    image_map: dict[str, str],
    stats: dict[str, int],
    filenames: dict[str, str],
) -> None:
    """Download one queued image task, tolerating failures."""
    image_output_dir = site_output_dir / "images"
    filename = filenames[task.url]
    archived_url = _archived_asset_url(task.url, task.snapshot or "")
    try:
        response = request_with_retry(archived_url, timeout=TIMEOUT)
        (image_output_dir / filename).write_bytes(response.content)
        image_map.update(
            _asset_map_entries(
                task.source or task.url,
                task.url,
                archived_url,
                f"images/{filename}",
            )
        )
        stats["recovered"] += 1
        print(f"✓ {filename}")
    except Exception as exc:
        stats["failed"] += 1
        print(f"✗ {filename}")
        print(f"Reason: {exc}")


def _print_image_recovery_summary(recovered: int, failed: int, skipped: int) -> None:
    """Print a summary of image recovery outcomes."""
    print()
    print("Recovery Summary")
    print()
    print("Images")
    print(f"Recovered: {recovered}")
    print(f"Failed: {failed}")
    print(f"Skipped: {skipped}")


def _internal_images(
    image_urls: list[str],
    homepage_url: str,
) -> tuple[list[tuple[str, str]], int]:
    """Return resolved same-site image URLs and external skip count."""
    images: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0

    for image_url in image_urls:
        resolved_url = _resolve_asset_url(homepage_url, image_url)
        if not _is_internal_asset_url(resolved_url, homepage_url):
            skipped += 1
            continue

        image = (image_url, resolved_url)
        if image not in seen:
            images.append(image)
            seen.add(image)

    return images, skipped


def _asset_map_entries(
    asset_url: str,
    resolved_url: str,
    archived_url: str,
    local_path: str,
) -> dict[str, str]:
    """Return URL variants that should rewrite to a local asset path."""
    entries = {
        asset_url: local_path,
        resolved_url: local_path,
        archived_url: local_path,
    }
    entries.update({_swap_url_scheme(url): local_path for url in list(entries)})
    return {url: path for url, path in entries.items() if url}


def _swap_url_scheme(url: str) -> str:
    """Return the HTTP/HTTPS equivalent of a URL."""
    if url.startswith("http://"):
        return f"https://{url.removeprefix('http://')}"
    if url.startswith("https://"):
        return f"http://{url.removeprefix('https://')}"
    return ""


def _resolve_asset_url(homepage_url: str, asset_url: str) -> str:
    """Resolve an asset URL against the homepage URL."""
    if asset_url.startswith("https://web.archive.org/"):
        return asset_url
    if asset_url.startswith("http://web.archive.org/"):
        return asset_url
    if asset_url.startswith("/web/"):
        return f"https://web.archive.org{asset_url}"
    return urljoin(homepage_url, asset_url)


def _is_internal_asset_url(asset_url: str, homepage_url: str) -> bool:
    """Return whether an asset URL belongs to the homepage domain."""
    original_url = _original_url_from_wayback(asset_url) or asset_url
    asset_host = urlparse(original_url).netloc.lower().removeprefix("www.")
    homepage_host = urlparse(homepage_url).netloc.lower().removeprefix("www.")
    return asset_host == homepage_host


def _original_url_from_wayback(url: str) -> str:
    """Return the original URL embedded in a Wayback asset URL."""
    parsed = urlparse(url)
    if parsed.netloc not in {"web.archive.org", "www.web.archive.org"}:
        return ""

    parts = parsed.path.split("/", 3)
    if len(parts) < 4 or parts[1] != "web":
        return ""
    return parts[3]


def _archived_asset_url(url: str, timestamp: str) -> str:
    """Return the Internet Archive URL for an asset at a snapshot timestamp."""
    if url.startswith("https://web.archive.org/") or url.startswith(
        "http://web.archive.org/"
    ):
        return url
    return f"https://web.archive.org/web/{timestamp}id_/{url}"


def _stylesheet_filename(url: str, used_filenames: set[str]) -> str:
    """Return a filesystem filename for a stylesheet URL."""
    filename = _asset_filename(url) or "stylesheet.css"
    if not filename.endswith(".css"):
        filename = f"{filename}.css"

    candidate = filename
    counter = 2
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    while candidate in used_filenames:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1

    used_filenames.add(candidate)
    return candidate


def _image_filename(url: str, used_filenames: set[str]) -> str:
    """Return a filesystem filename for an image URL."""
    filename = _asset_filename(url) or "image"

    candidate = filename
    counter = 2
    stem = Path(filename).stem or "image"
    suffix = Path(filename).suffix
    while candidate in used_filenames:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1

    used_filenames.add(candidate)
    return candidate


def _asset_filename(url: str) -> str:
    """Return the filename component for an asset URL."""
    original_url = _original_url_from_wayback(url) or url
    path = urlparse(original_url).path
    return Path(unquote(path)).name


def _page_label(url: str) -> str:
    """Return a readable label for a discovered page URL."""
    path = urlparse(url).path.strip("/")
    if not path:
        return "Home"

    name = path.rsplit("/", 1)[-1]
    stem = Path(name).stem or name
    label = stem.replace("-", " ").replace("_", " ").strip()
    return label.title() if label else "Page"


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


def _format_snapshot_date(snapshot: dict[str, str]) -> str:
    """Return a human-readable snapshot date for progress logging."""
    timestamp = snapshot.get("timestamp", "")
    if len(timestamp) >= 8:
        return f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
    return timestamp


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
