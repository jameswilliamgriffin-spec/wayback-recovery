"""Persistent local cache management for Wayback Recovery."""

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

CACHE_ROOT = Path("cache")
CACHE_FOLDERS = ("cdx", "snapshots", "pages", "assets")


class CacheManager:
    """Manage cached values for one cache folder."""

    def __init__(self, folder: str, extension: str = "json") -> None:
        """Initialize a cache manager for a cache folder."""
        if folder not in CACHE_FOLDERS:
            raise ValueError(f"Unknown cache folder: {folder}")

        self.folder = CACHE_ROOT / folder
        self.extension = extension.lstrip(".")
        self.folder.mkdir(parents=True, exist_ok=True)

    def get(self, key: str) -> Any:
        """Load a cached value by key."""
        path = self._path(key)
        if self.extension == "json":
            return json.loads(path.read_text(encoding="utf-8"))

        return path.read_text(encoding="utf-8")

    def set(self, key: str, value: Any) -> None:
        """Save a value to the cache by key."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        if self.extension == "json":
            path.write_text(json.dumps(value, indent=2), encoding="utf-8")
            return

        path.write_text(str(value), encoding="utf-8")

    def exists(self, key: str) -> bool:
        """Return whether a cache entry exists for a key."""
        return self._path(key).exists()

    def clear(self) -> None:
        """Clear all entries in this cache folder."""
        if self.folder.exists():
            shutil.rmtree(self.folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Return the filesystem path for a cache key."""
        return self.folder / f"{_safe_filename(key)}.{self.extension}"


def ensure_cache_folders() -> None:
    """Create all cache folders."""
    for folder in CACHE_FOLDERS:
        (CACHE_ROOT / folder).mkdir(parents=True, exist_ok=True)


def _safe_filename(key: str) -> str:
    """Convert a cache key into a readable filename."""
    readable = re.sub(r"[^a-zA-Z0-9]+", "-", key).strip("-").lower()
    readable = readable[:80] or "cache-entry"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{readable}-{digest}"
