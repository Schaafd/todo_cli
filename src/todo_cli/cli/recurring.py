"""Recurring task CLI commands."""

import sys
from datetime import datetime, timedelta

import click
from click.shell_completion import CompletionItem
from rich.console import Console

from ..config import get_config
from ..domain import RecurringTaskManager, create_recurring_task_from_text
from ..storage import Storage
from ..theme import get_themed_console


recurring_manager = RecurringTaskManager()


class RecurringGroup(click.Group):
    """Recurring command group that preserves the old create shorthand."""

    def resolve_command(self, ctx: click.Context, args: list[str]) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] not in self.commands:
            args.insert(0, "create")
        return super().resolve_command(ctx, args)


def get_console() -> Console:
    """Get a themed console that reflects current configuration."""
    return get_themed_console()


def get_storage() -> Storage:
    """Get initialized storage instance."""
    return Storage(get_config())


def _completion_items(values: list[str], incomplete: str) -> list[CompletionItem]:
    """Build Click completion items for values matching the incomplete token."""
    matches = []
    lowered = incomplete.lower()
    for value in values:
        completion = str(value)
        if not incomplete or completion.lower().startswith(lowered):
            matches.append(CompletionItem(completion))
    return matches


def _complete_projects(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:
    try:
        storage = get_storage()
        config = get_config()
        return _completion_items(storage.list_projects() or [config.default_project], incomplete)
    except Exception:
        return []


def _create_recurring_task(
    task_text: str,
    pattern: str,
    project: str | None,
    max_occurrences: int | None,
    end_date: str | None,
    preview: bool,
) -> None:
    """Create or preview a recurring task."""
    try:
        template, recurrence_pattern = create_recurring_task_from_text(task_text, pattern)

        if project:
            template.project = project

        if max_occurrences:
            recurrence_pattern.max_occurrences = max_occurrences

        if end_date:
            try:
                recurrence_pattern.end_date = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                get_console().print("[error]❌ Invalid end date format. Use YYYY-MM-DD[/error]")
                return

        if preview:
            get_console().print("\n[primary]📅 Preview of recurring task:[/primary]")
            get_console().print(f"  [bold]{template.text}[/bold]")
            get_console().print(f"  Pattern: {pattern}")
            get_console().print(f"  Project: {template.project}")

            get_console().print("\n[primary]Next 5 occurrences:[/primary]")
            current_date = datetime.now()

            for i in range(5):
                next_occurrence = recurring_manager.calculate_next_occurrence(current_date, recurrence_pattern)
                if next_occurrence:
                    get_console().print(f"  {i+1}. {next_occurrence.strftime('%Y-%m-%d %H:%M')}")
                    current_date = next_occurrence
                else:
                    break

            get_console().print("\n[muted]Use without --preview to create the recurring task[/muted]")
            return

        recurring_task = recurring_manager.create_recurring_task(template, recurrence_pattern)

        get_console().print("\n[success]✅ Created recurring task:[/success]")
        get_console().print(f"  [bold]{template.text}[/bold]")
        get_console().print(f"  Pattern: {pattern}")
        get_console().print(f"  Next due: {recurring_task.next_due.strftime('%Y-%m-%d %H:%M') if recurring_task.next_due else 'Unknown'}")
        get_console().print(f"  ID: {recurring_task.id}")

        if max_occurrences:
            get_console().print(f"  Max occurrences: {max_occurrences}")
        if end_date:
            get_console().print(f"  Ends: {end_date}")

    except ValueError as e:
        get_console().print(f"[error]❌ {e}[/error]")
        sys.exit(1)


@click.group(cls=RecurringGroup, invoke_without_command=True)
@click.pass_context
def recurring(ctx: click.Context) -> None:
    """Create and manage recurring tasks."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@recurring.command("create")
@click.argument("task_text")
@click.argument("pattern")
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project for the recurring task")
@click.option("--max-occurrences", type=int, help="Maximum number of occurrences")
@click.option("--end-date", help="End date for recurrence (YYYY-MM-DD)")
@click.option("--preview", is_flag=True, help="Preview next few occurrences without creating")
def recurring_create(
    task_text: str,
    pattern: str,
    project: str | None,
    max_occurrences: int | None,
    end_date: str | None,
    preview: bool,
) -> None:
    """Create a recurring task with smart scheduling."""
    _create_recurring_task(task_text, pattern, project, max_occurrences, end_date, preview)


def _list_recurring_tasks() -> None:
    """List all recurring tasks."""
    recurring_tasks = recurring_manager.list_recurring_tasks()

    if not recurring_tasks:
        get_console().print("[muted]No recurring tasks found.[/muted]")
        get_console().print("[muted]Create one with: todo recurring create 'task description' 'pattern'[/muted]")
        return

    get_console().print(f"\n[primary]📋 Recurring Tasks ({len(recurring_tasks)}):[/primary]")

    for task in recurring_tasks:
        status_icon = "✅" if task.active else "⏸️"
        get_console().print(f"\n{status_icon} [bold]{task.template.text}[/bold]")
        get_console().print(f"   ID: {task.id}")
        get_console().print(f"   Pattern: {task.pattern.type.value}")
        get_console().print(f"   Project: {task.template.project}")
        get_console().print(f"   Next due: {task.next_due.strftime('%Y-%m-%d %H:%M') if task.next_due else 'N/A'}")
        get_console().print(f"   Occurrences: {task.occurrence_count}")

        if task.pattern.max_occurrences:
            get_console().print(f"   Max occurrences: {task.pattern.max_occurrences}")
        if task.pattern.end_date:
            get_console().print(f"   End date: {task.pattern.end_date.strftime('%Y-%m-%d')}")


@recurring.command("list")
def recurring_list() -> None:
    """List all recurring tasks."""
    _list_recurring_tasks()


@click.command("recurring-list", hidden=True)
def list_recurring() -> None:
    """List all recurring tasks."""
    _list_recurring_tasks()


def _generate_recurring_tasks(days: int, dry_run: bool) -> None:
    """Generate due recurring tasks."""
    until_date = datetime.now() + timedelta(days=days)

    generated_tasks = recurring_manager.generate_due_tasks(until_date)

    if not generated_tasks:
        get_console().print("[muted]No recurring tasks due for generation.[/muted]")
        return

    if dry_run:
        get_console().print(f"\n[primary]Would generate {len(generated_tasks)} tasks:[/primary]")
        for task in generated_tasks:
            get_console().print(f"  • {task.text} (due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No date'})")
        get_console().print("\n[muted]Run without --dry-run to actually create these tasks[/muted]")
    else:
        storage = get_storage()
        saved_count = 0

        for task in generated_tasks:
            task.id = storage.get_next_todo_id(task.project)
            proj, todos = storage.load_project(task.project)
            assert proj is not None
            todos.append(task)

            if storage.save_project(proj, todos):
                saved_count += 1

        get_console().print(f"\n[success]✅ Generated and saved {saved_count} recurring tasks[/success]")

        if saved_count != len(generated_tasks):
            failed_count = len(generated_tasks) - saved_count
            get_console().print(f"[warning]⚠️  Failed to save {failed_count} tasks[/warning]")

        if saved_count > 0:
            try:
                from ..services import NotificationManager

                notification_manager = NotificationManager()
                notification_manager.send_recurring_notification(saved_count)
            except Exception:
                pass


@recurring.command("generate")
@click.option("--days", "-d", type=int, default=30, help="Generate tasks for next N days")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without creating tasks")
def recurring_generate(days: int, dry_run: bool) -> None:
    """Generate due recurring tasks."""
    _generate_recurring_tasks(days, dry_run)


@click.command("recurring-generate", hidden=True)
@click.option("--days", "-d", type=int, default=30, help="Generate tasks for next N days")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without creating tasks")
def generate_recurring(days: int, dry_run: bool) -> None:
    """Generate due recurring tasks."""
    _generate_recurring_tasks(days, dry_run)


def _pause_recurring_task(task_id: str) -> None:
    """Pause a recurring task."""
    task = recurring_manager.get_recurring_task(task_id)
    if not task:
        get_console().print(f"[error]❌ Recurring task '{task_id}' not found[/error]")
        return

    if not task.active:
        get_console().print(f"[warning]⚠️  Task '{task_id}' is already paused[/warning]")
        return

    recurring_manager.pause_recurring_task(task_id)
    get_console().print(f"[success]✅ Paused recurring task: {task.template.text}[/success]")


@recurring.command("pause")
@click.argument("task_id")
def recurring_pause(task_id: str) -> None:
    """Pause a recurring task."""
    _pause_recurring_task(task_id)


@click.command("recurring-pause", hidden=True)
@click.argument("task_id")
def pause_recurring(task_id: str) -> None:
    """Pause a recurring task."""
    _pause_recurring_task(task_id)


def _resume_recurring_task(task_id: str) -> None:
    """Resume a paused recurring task."""
    task = recurring_manager.get_recurring_task(task_id)
    if not task:
        get_console().print(f"[error]❌ Recurring task '{task_id}' not found[/error]")
        return

    if task.active:
        get_console().print(f"[warning]⚠️  Task '{task_id}' is already active[/warning]")
        return

    recurring_manager.resume_recurring_task(task_id)
    get_console().print(f"[success]✅ Resumed recurring task: {task.template.text}[/success]")


@recurring.command("resume")
@click.argument("task_id")
def recurring_resume(task_id: str) -> None:
    """Resume a paused recurring task."""
    _resume_recurring_task(task_id)


@click.command("recurring-resume", hidden=True)
@click.argument("task_id")
def resume_recurring(task_id: str) -> None:
    """Resume a paused recurring task."""
    _resume_recurring_task(task_id)


def _delete_recurring_task(task_id: str, confirm: bool) -> None:
    """Delete a recurring task."""
    task = recurring_manager.get_recurring_task(task_id)
    if not task:
        get_console().print(f"[error]❌ Recurring task '{task_id}' not found[/error]")
        return

    get_console().print("\n[warning]Will delete recurring task:[/warning]")
    get_console().print(f"  [bold]{task.template.text}[/bold]")
    get_console().print(f"  Pattern: {task.template.recurrence}")
    get_console().print(f"  Occurrences generated: {task.occurrence_count}")

    if not confirm and not click.confirm("\nAre you sure you want to delete this recurring task?"):
        get_console().print("[muted]Deletion cancelled.[/muted]")
        return

    recurring_manager.delete_recurring_task(task_id)
    get_console().print("[success]✅ Deleted recurring task[/success]")


@recurring.command("delete")
@click.argument("task_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def recurring_delete(task_id: str, confirm: bool) -> None:
    """Delete a recurring task."""
    _delete_recurring_task(task_id, confirm)


@click.command("recurring-delete", hidden=True)
@click.argument("task_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_recurring(task_id: str, confirm: bool) -> None:
    """Delete a recurring task."""
    _delete_recurring_task(task_id, confirm)
