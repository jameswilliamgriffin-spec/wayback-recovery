"""Recovery task queue primitives."""

from collections import deque
from collections.abc import Hashable

from archive.models.task import RecoveryTask


class RecoveryQueue:
    """FIFO queue that avoids duplicate recovery tasks."""

    def __init__(self) -> None:
        self._items: deque[RecoveryTask] = deque()
        self._seen: set[Hashable] = set()

    def enqueue(self, task: RecoveryTask) -> bool:
        """Add a task to the queue if it has not already been queued."""
        key = self._key(task)
        if key in self._seen:
            return False

        self._items.append(task)
        self._seen.add(key)
        return True

    def dequeue(self) -> RecoveryTask:
        """Remove and return the next queued task."""
        return self._items.popleft()

    def peek(self) -> RecoveryTask:
        """Return the next queued task without removing it."""
        return self._items[0]

    def empty(self) -> bool:
        """Return whether the queue has no pending items."""
        return not self._items

    def size(self) -> int:
        """Return the number of pending items."""
        return len(self._items)

    def __iter__(self):
        """Iterate over pending queue tasks."""
        return iter(self._items)

    def _key(self, task: RecoveryTask) -> Hashable:
        return (task.task_type, task.url)
