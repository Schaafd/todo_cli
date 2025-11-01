"""Command-line interface package for Todo CLI."""

__all__ = ["main"]


def main(*args, **kwargs):
    """Entry point that defers heavy imports until needed."""
    from .tasks import main as tasks_main

    return tasks_main(*args, **kwargs)
