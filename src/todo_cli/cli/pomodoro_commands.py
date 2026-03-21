"""CLI commands for the Pomodoro/Focus Timer."""

import sys
import time

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.progress import BarColumn, TextColumn, Progress


def _make_progress_bar(remaining: float, total: float, state_label: str, task_text: str = "") -> Panel:
    """Build a Rich panel showing the countdown progress bar."""
    minutes = int(remaining) // 60
    seconds = int(remaining) % 60
    fraction = remaining / total if total > 0 else 0

    bar_width = 30
    filled = int(bar_width * fraction)
    empty = bar_width - filled
    bar = "[green]" + "#" * filled + "[/green]" + "[dim]" + "-" * empty + "[/dim]"

    time_str = f"{minutes:02d}:{seconds:02d}"
    line = f"  [{bar}] {time_str} remaining"
    if task_text:
        line += f'  --  "{task_text}"'

    return Panel(line, title=f"[bold]{state_label}[/bold]", border_style="cyan", expand=False)


@click.group("focus")
def focus_group():
    """Pomodoro focus timer."""
    pass


@focus_group.command("start")
@click.argument("task_id", required=False)
@click.option("--duration", "-d", type=int, help="Focus duration in minutes (default: 25)")
def start_focus(task_id, duration):
    """Start a focus session, optionally linked to a task.

    Displays a live countdown timer in the terminal using Rich.
    Press Ctrl+C to interrupt the session.
    """
    from ..services.pomodoro import PomodoroTimer, PomodoroConfig

    console = Console()
    timer = PomodoroTimer()

    if duration:
        timer.config.focus_minutes = duration

    task_text = None
    if task_id:
        # Try to look up the task text
        try:
            from ..config import get_config
            from ..storage import Storage
            config = get_config()
            storage = Storage(config)
            for proj_name in storage.list_projects():
                proj, todos = storage.load_project(proj_name)
                for todo in (todos or []):
                    if str(todo.id) == str(task_id):
                        task_text = todo.text
                        break
                if task_text:
                    break
        except Exception:
            pass

    session = timer.start_focus(task_id=task_id, task_text=task_text)
    total_seconds = session.planned_minutes * 60
    state_label = "Focus"

    console.print(f"[bold green]Starting {session.planned_minutes}-minute focus session...[/bold green]")
    if task_text:
        console.print(f"[dim]Task: {task_text}[/dim]")
    console.print("[dim]Press Ctrl+C to interrupt.[/dim]\n")

    try:
        with Live(console=console, refresh_per_second=2) as live:
            while True:
                remaining = timer.get_remaining_seconds()
                if remaining <= 0:
                    break
                live.update(_make_progress_bar(remaining, total_seconds, state_label, task_text or ""))
                time.sleep(0.5)

        completed = timer.complete_session()
        console.print("\n[bold green]Session complete![/bold green]")
        if completed:
            console.print(f"[dim]Focused for {completed.actual_minutes:.1f} minutes.[/dim]")

        # Offer break
        console.print("\n[yellow]Would you like to take a break? (y/n)[/yellow] ", end="")
        try:
            answer = input().strip().lower()
        except EOFError:
            answer = "n"
        if answer in ("y", "yes"):
            _run_break(timer, console)
    except KeyboardInterrupt:
        interrupted = timer.interrupt_session()
        console.print("\n[red]Session interrupted.[/red]")
        if interrupted:
            console.print(f"[dim]Worked for {interrupted.actual_minutes:.1f} minutes before interruption.[/dim]")


def _run_break(timer, console):
    """Run a break session with live countdown."""
    session = timer.start_break()
    total_seconds = session.planned_minutes * 60
    state_label = "Long Break" if session.planned_minutes > 5 else "Short Break"

    console.print(f"\n[bold cyan]Starting {session.planned_minutes}-minute {state_label.lower()}...[/bold cyan]")

    try:
        with Live(console=console, refresh_per_second=2) as live:
            while True:
                remaining = timer.get_remaining_seconds()
                if remaining <= 0:
                    break
                live.update(_make_progress_bar(remaining, total_seconds, state_label))
                time.sleep(0.5)

        timer.complete_session()
        console.print("\n[bold green]Break over! Time to focus.[/bold green]")
    except KeyboardInterrupt:
        timer.interrupt_session()
        console.print("\n[yellow]Break interrupted.[/yellow]")


@focus_group.command("break")
def take_break():
    """Start a break (auto-selects short or long)."""
    from ..services.pomodoro import PomodoroTimer
    console = Console()
    timer = PomodoroTimer()
    _run_break(timer, console)


@focus_group.command("stats")
@click.option("--days", "-d", type=int, default=7, help="Number of days to show stats for")
def show_stats(days):
    """Show pomodoro statistics."""
    from ..services.pomodoro import PomodoroTimer
    console = Console()
    timer = PomodoroTimer()
    stats = timer.get_stats(days=days)

    table = Table(title=f"Pomodoro Stats (last {days} days)", show_header=False, border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Sessions", str(stats.total_sessions))
    table.add_row("Completed", str(stats.completed_sessions))
    table.add_row("Interrupted", str(stats.interrupted_sessions))
    table.add_row("Total Focus (min)", f"{stats.total_focus_minutes:.1f}")
    table.add_row("Avg Focus (min)", f"{stats.average_focus_minutes:.1f}")
    table.add_row("Current Streak", str(stats.current_streak))
    table.add_row("Best Streak", str(stats.best_streak))
    table.add_row("Sessions Today", str(stats.sessions_today))
    table.add_row("Focus Today (min)", f"{stats.focus_minutes_today:.1f}")

    console.print(table)


@focus_group.command("history")
@click.option("--limit", "-n", type=int, default=10, help="Number of sessions to show")
def show_history(limit):
    """Show recent pomodoro session history."""
    from ..services.pomodoro import PomodoroTimer
    console = Console()
    timer = PomodoroTimer()

    if not timer.history:
        console.print("[dim]No pomodoro sessions recorded yet.[/dim]")
        return

    table = Table(title="Recent Pomodoro Sessions", border_style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Type")
    table.add_column("Duration", justify="right")
    table.add_column("Status")
    table.add_column("Task")

    for session in timer.history[-limit:]:
        date_str = session.started_at.strftime("%Y-%m-%d %H:%M") if session.started_at else "?"
        state_str = session.state.value.replace("_", " ").title()
        duration_str = f"{session.actual_minutes:.1f}m"
        if session.completed:
            status_str = "[green]Completed[/green]"
        elif session.interrupted:
            status_str = "[red]Interrupted[/red]"
        else:
            status_str = "[yellow]Unknown[/yellow]"
        task_str = session.task_text or session.task_id or ""

        table.add_row(date_str, state_str, duration_str, status_str, task_str)

    console.print(table)


@focus_group.command("config")
@click.option("--focus-minutes", type=int, help="Focus duration in minutes")
@click.option("--short-break", type=int, help="Short break duration in minutes")
@click.option("--long-break", type=int, help="Long break duration in minutes")
@click.option("--sessions-before-long", type=int, help="Sessions before long break")
def configure(focus_minutes, short_break, long_break, sessions_before_long):
    """Configure pomodoro timer settings."""
    from ..config import get_config, save_config

    console = Console()
    config = get_config()
    changed = False

    if focus_minutes is not None:
        config.pomodoro_focus_minutes = focus_minutes
        changed = True
    if short_break is not None:
        config.pomodoro_short_break_minutes = short_break
        changed = True
    if long_break is not None:
        config.pomodoro_long_break_minutes = long_break
        changed = True
    if sessions_before_long is not None:
        config.pomodoro_sessions_before_long_break = sessions_before_long
        changed = True

    if changed:
        save_config(config)
        console.print("[green]Pomodoro configuration updated.[/green]")
    else:
        console.print(f"Focus: {config.pomodoro_focus_minutes} min")
        console.print(f"Short break: {config.pomodoro_short_break_minutes} min")
        console.print(f"Long break: {config.pomodoro_long_break_minutes} min")
        console.print(f"Sessions before long break: {config.pomodoro_sessions_before_long_break}")
