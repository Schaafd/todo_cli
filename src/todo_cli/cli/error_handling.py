"""Shared CLI error rendering."""

import traceback
from typing import Optional

import click
from rich.console import Console

from ..core.errors import TodoCliError


def debug_enabled() -> bool:
    """Return whether the current Click invocation requested debug output."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return False

    while ctx is not None:
        if ctx.obj and ctx.obj.get("debug"):
            return True
        ctx = ctx.parent

    return False


def render_expected_error(
    error: Exception,
    *,
    console: Console,
    prefix: Optional[str] = None,
) -> None:
    """Render an expected CLI failure with optional debug detail."""
    message = getattr(error, "message", str(error))
    if prefix:
        console.print(f"[error]Error: {prefix}: {message}[/error]")
    else:
        console.print(f"[error]Error: {message}[/error]")

    suggestion = getattr(error, "suggestion", None)
    if suggestion:
        console.print(f"[muted]Try: {suggestion}[/muted]")

    if debug_enabled():
        console.print("[dim]Stack trace:[/dim]")
        console.print("".join(traceback.format_exception(error)))


def exit_with_error(
    error: Exception,
    *,
    console: Console,
    prefix: Optional[str] = None,
) -> None:
    """Render an expected error and terminate the Click command."""
    render_expected_error(error, console=console, prefix=prefix)
    raise click.exceptions.Exit(1)


def as_todo_cli_error(error: Exception, *, message: Optional[str] = None) -> TodoCliError:
    """Wrap an unexpected exception in the shared error type."""
    return TodoCliError(message or str(error))
