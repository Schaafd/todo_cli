"""CLI commands for demo mode — populate with sample data for testing."""

import click
from rich.console import Console

from ..services.demo import DemoDataGenerator

console = Console()


@click.group("demo")
def demo_group():
    """Demo mode -- populate with sample data for testing."""
    pass


@demo_group.command("populate")
@click.option("--count", "-n", type=int, default=30, help="Number of tasks to generate")
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducible data")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def populate(count: int, seed, yes: bool):
    """Populate with realistic demo tasks."""
    gen = DemoDataGenerator()

    existing = gen.get_demo_count()
    if existing > 0 and not yes:
        if not click.confirm(
            f"There are already {existing} demo tasks. Add {count} more?"
        ):
            console.print("[yellow]Aborted.[/yellow]")
            return

    console.print(f"[cyan]Generating {count} demo tasks...[/cyan]")
    created = gen.populate(count=count, seed=seed)
    console.print(f"[green]Created {created} demo tasks.[/green]")


@demo_group.command("clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def clear(yes: bool):
    """Remove all demo tasks."""
    gen = DemoDataGenerator()
    count = gen.get_demo_count()

    if count == 0:
        console.print("[yellow]No demo tasks found.[/yellow]")
        return

    if not yes:
        if not click.confirm(f"Remove {count} demo tasks?"):
            console.print("[yellow]Aborted.[/yellow]")
            return

    removed = gen.clear()
    console.print(f"[green]Removed {removed} demo tasks.[/green]")


@demo_group.command("status")
def status():
    """Show demo data status."""
    gen = DemoDataGenerator()
    count = gen.get_demo_count()

    if count == 0:
        console.print("[dim]No demo tasks currently loaded.[/dim]")
    else:
        console.print(f"[cyan]Demo tasks: {count}[/cyan]")
