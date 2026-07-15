"""Recovery task domain model."""

from dataclasses import dataclass


@dataclass
class RecoveryTask:
    """A queued resource recovery task."""

    task_type: str
    url: str
    snapshot: str | None = None
    priority: int = 0
    source: str | None = None
    status: str = "queued"
