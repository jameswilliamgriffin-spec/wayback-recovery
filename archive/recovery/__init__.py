"""Recovery workflows and queue primitives."""

__all__ = ["recover_homepage"]


def __getattr__(name: str):
    if name == "recover_homepage":
        from archive.recovery.recovery import recover_homepage

        return recover_homepage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
