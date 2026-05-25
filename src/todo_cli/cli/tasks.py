"""New clean command-line interface for Todo CLI."""

import os
import sys
from difflib import get_close_matches
from typing import Optional
from datetime import datetime, timedelta
import click
from click.shell_completion import CompletionItem
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from ..utils.datetime import ensure_aware, max_utc, now_utc

from ..config import get_config, load_config
from ..core.errors import StorageError, TaskNotFoundError, TodoCliError, ValidationError
from .error_handling import exit_with_error
from ..storage import Storage
from ..application.task_commands import add_task_from_input
from ..services.operation_history import OperationHistory, OperationRecord
from ..validation import (
    validate_name_tokens,
    validate_parsed_task,
    validate_project_name,
    validate_task_text,
    validate_todo_id,
)
from ..domain import (
    Todo,
    TodoStatus,
    Priority,
    parse_task_input,
    TaskBuilder,
)
from ..domain.parser import SmartDateParser
from ..theme import (
    get_themed_console, 
    show_dashboard_banner,
    show_startup_banner, 
    show_quick_help,
    get_priority_style,
    get_status_emoji,
    PRODUCTIVITY_NINJA_THEME
)


# Dynamic console - no longer created at module level
def get_console():
    """Get a themed console that reflects current configuration."""
    return get_themed_console()

def _get_query_engine():
    from ..services import QueryEngine
    return QueryEngine()

def _get_recommend_engine():
    from ..services import TaskRecommendationEngine
    return TaskRecommendationEngine()


DASHBOARD_SECTION_TITLES = {
    "pinned": "[todo_pinned]⭐ Pinned Tasks[/todo_pinned]",
    "overdue": "[critical]🔥 Overdue Tasks[/critical]",
    "today": "[success]📅 Due Today[/success]",
    "upcoming": "[primary]📆 Due This Week[/primary]",
}

DASHBOARD_SECTION_BORDER_STYLES = {
    "pinned": "pinned_border",
    "overdue": "overdue_border",
    "today": "today_border",
    "upcoming": "upcoming_border",
}

DASHBOARD_SECTION_STYLES = {
    "pinned": "pinned_bg",
    "overdue": "overdue_bg",
    "today": "today_bg",
    "upcoming": "upcoming_bg",
}


COMMON_COMMANDS = [
    ("todo", "Show the dashboard"),
    ('todo add "Review PR @work due tomorrow"', "Add a task"),
    ("todo list", "List active tasks"),
    ("todo done <id>", "Complete a task"),
    ("todo edit <id> --text ...", "Edit a task"),
    ("todo delete <id>", "Delete a task"),
    ("todo undo", "Undo last change"),
    ("todo search <query>", "Search tasks"),
    ("todo projects", "List projects"),
]


COMMAND_CATEGORIES = [
    ("Core", ["add", "quick", "list", "done", "edit", "delete", "undo", "pin", "bulk", "projects", "search", "export"]),
    ("Views and Planning", ["dashboard", "board", "recommend", "queries", "recurring"]),
    ("Organization", ["tag", "ctx", "dep"]),
    ("Focus and Notifications", ["focus", "notify"]),
    ("Integrations", ["app-sync", "sync", "calendar", "ai", "voice", "web", "collab"]),
    ("Maintenance", ["backup", "doctor", "theme", "completion"]),
    ("Advanced", ["analytics", "dashboard-mgr", "demo"]),
]


class CategorizedGroup(click.Group):
    """Root Click group that presents commands by workflow instead of alphabetically."""

    def get_command(self, ctx, cmd_name):
        command = super().get_command(ctx, cmd_name)
        if command is not None or ctx.resilient_parsing:
            return command

        visible = [
            name
            for name, cmd in self.commands.items()
            if not getattr(cmd, "hidden", False)
        ]
        matches = get_close_matches(cmd_name, visible, n=1, cutoff=0.72)
        if matches:
            ctx.fail(f"No such command '{cmd_name}'.\n\nDid you mean '{matches[0]}'?")

        return None

    def format_commands(self, ctx, formatter):
        """Render common commands first, then categorized command groups."""
        visible_commands = {
            name: cmd
            for name, cmd in self.commands.items()
            if not getattr(cmd, "hidden", False)
        }

        with formatter.section("Common commands"):
            formatter.write_dl(COMMON_COMMANDS)

        rendered = set()
        for category, names in COMMAND_CATEGORIES:
            rows = []
            for name in names:
                command = visible_commands.get(name)
                if command is None:
                    continue
                rendered.add(name)
                rows.append((name, command.get_short_help_str()))
            if rows:
                with formatter.section(category):
                    formatter.write_dl(rows)

        leftovers = sorted(set(visible_commands) - rendered)
        if leftovers:
            with formatter.section("Other"):
                formatter.write_dl(
                    [
                        (name, visible_commands[name].get_short_help_str())
                        for name in leftovers
                    ]
                )


def _completion_items(values, incomplete, prefix=""):
    """Build Click completion items for values matching the incomplete token."""
    matches = []
    for value in sorted(set(values)):
        completion = f"{prefix}{value}"
        if completion.startswith(incomplete):
            matches.append(CompletionItem(completion))
    return matches


def _load_completion_todos():
    """Load todos for data-backed shell completion, returning an empty list on failure."""
    try:
        storage = get_storage()
        config = get_config()
        projects = storage.list_projects() or [config.default_project]
        todos = []
        for project_name in projects:
            _, project_todos = storage.load_project(project_name)
            todos.extend(project_todos)
        return todos
    except Exception:
        return []


def _complete_projects(ctx, param, incomplete):
    try:
        storage = get_storage()
        config = get_config()
        return _completion_items(storage.list_projects() or [config.default_project], incomplete)
    except Exception:
        return []


def _complete_tags(ctx, param, incomplete):
    tags = []
    for todo in _load_completion_todos():
        tags.extend(todo.tags or [])
    return _completion_items(tags, incomplete)


def _complete_contexts(ctx, param, incomplete):
    contexts = []
    for todo in _load_completion_todos():
        contexts.extend(todo.context or [])
    return _completion_items(contexts, incomplete)


def _saved_query_names():
    try:
        return _get_query_engine().list_saved_queries().keys()
    except Exception:
        return []


def _complete_saved_query_names(ctx, param, incomplete):
    return _completion_items(_saved_query_names(), incomplete)


def _complete_saved_query_refs(ctx, param, incomplete):
    if not incomplete.startswith("@"):
        return []
    return _completion_items(_saved_query_names(), incomplete, prefix="@")


def get_storage() -> Storage:
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


def get_operation_history() -> OperationHistory:
    """Get operation history for the current configuration."""
    return OperationHistory(get_config())


def _snapshot_todo(todo: Todo) -> Todo:
    """Capture a detached todo snapshot for history records."""
    return Todo.from_dict(todo.to_dict())


def _record_operation(record: OperationRecord) -> None:
    get_operation_history().append(record)


def format_todo_for_display(todo: Todo, show_id: bool = True) -> str:
    """Format a todo for display with themed styling."""
    # Get themed status emoji
    status_icon = get_status_emoji(todo.status.value, todo.pinned)
    
    # Get priority style
    priority_style = get_priority_style(todo.priority.value)
    
    # Format text parts
    text_parts = []
    if show_id:
        text_parts.append(f"[muted]{todo.id}[/muted]")
    
    # Main task text with priority styling
    text_parts.append(f"{status_icon} [{priority_style}]{todo.text}[/{priority_style}]")
    
    # Add metadata with themed colors
    if todo.tags:
        tags_str = ' '.join(['@' + tag for tag in todo.tags])
        text_parts.append(f"[tag]{tags_str}[/tag]")
    
    if todo.context:
        context_str = ' '.join(['@' + ctx for ctx in todo.context])
        text_parts.append(f"[tag]{context_str}[/tag]")
    
    if todo.due_date:
        date_str = todo.due_date.strftime('%Y-%m-%d')
        if todo.is_overdue():
            text_parts.append(f"[due_date_overdue]!{date_str}[/due_date_overdue]")
        else:
            text_parts.append(f"[due_date]!{date_str}[/due_date]")
    
    if todo.assignees:
        assignee_str = ' '.join(['+' + assignee for assignee in todo.assignees])
        text_parts.append(f"[assignee]{assignee_str}[/assignee]")
    
    if todo.stakeholders:
        stakeholder_str = ' '.join(['&' + stakeholder for stakeholder in todo.stakeholders])
        text_parts.append(f"[accent]{stakeholder_str}[/accent]")
    
    return " ".join(text_parts)


def _find_todo(storage: Storage, todo_id: int, project: Optional[str] = None):
    """Find a todo and return its project object and containing list."""
    todo_id = validate_todo_id(todo_id)
    project = validate_project_name(project)

    projects = [project] if project else storage.list_projects()
    if not projects:
        projects = [get_config().default_project]

    for project_name in projects:
        project_obj, todos = storage.load_project(project_name)
        for todo in todos:
            if todo.id == todo_id:
                return project_obj, todos, todo

    raise TaskNotFoundError(todo_id, project=project)


def _parse_due_date(value: str):
    """Parse a due-date setter value."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("Due date cannot be empty.")
    if cleaned.lower() in {"none", "clear", "remove"}:
        return None

    due_date = SmartDateParser().parse(cleaned)
    if due_date is None:
        raise ValidationError(
            f"Could not parse due date '{value}'.",
            suggestion="Use a date like tomorrow, Friday, or 2026-05-24.",
        )
    return due_date


@click.group()
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--debug", is_flag=True, help="Show stack traces for expected errors")
@click.pass_context
def cli(ctx, config, verbose, debug):
    """Todo CLI - A powerful command-line todo application."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug
    
    # Load configuration
    try:
        if config:
            from pathlib import Path
            load_config(Path(config))
        else:
            get_config()
    except Exception as e:
        get_console().print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("input_text", required=False)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Default project if not specified in text")
@click.option("--dry-run", is_flag=True, help="Parse without saving to see what would be created")
@click.option("--suggest", is_flag=True, help="Show suggestions for improving the input")
@click.option("--interactive", "interactive_mode", is_flag=True, help="Prompt for task fields")
def add(input_text, project, dry_run, suggest, interactive_mode):
    """Add a new todo item with natural language parsing.
    
    Examples:
      todo add "Review PR #urgent @web due tomorrow"
      todo add "Call doctor @phone ~high est:30m"
      todo add "Deploy app #project1 due friday @work +john"
      todo add "Meeting prep [PIN] energy:high est:1h"
    """
    try:
        storage = get_storage()
        config = get_config()

        if interactive_mode:
            _guided_add(storage, config, project)
            return

        if input_text is None:
            raise ValidationError(
                "Task text is required.",
                suggestion="Use `todo add \"task\"` or `todo add --interactive`.",
            )

        if dry_run or suggest:
            project = validate_project_name(project)
            parsed, errors, suggestions = parse_task_input(
                input_text,
                config,
                project_hint=project or config.default_project,
            )
            blocking_errors = [e for e in errors if e.severity == "error"]
            if blocking_errors:
                joined = "; ".join(e.message for e in blocking_errors)
                raise ValidationError(joined)
            validate_parsed_task(parsed)
            if dry_run:
                preview_todo = TaskBuilder(config).build(parsed, 1)
                get_console().print("[bold yellow]🔍 DRY RUN - Would create:[/bold yellow]")
                get_console().print(f"  {format_todo_for_display(preview_todo, show_id=False)}")
            if suggest and suggestions:
                get_console().print("[bold blue]💡 Suggestions:[/bold blue]")
                for suggestion in suggestions:
                    get_console().print(f"  [blue]{suggestion}[/blue]")
            elif suggest:
                get_console().print("[blue]ℹ️  No suggestions for this input.[/blue]")
            return

        result = add_task_from_input(
            storage=storage,
            config=config,
            input_text=input_text,
            project=project,
        )
        _record_operation(
            OperationRecord.create(
                "add",
                todo_id=result.todo.id,
                after=result.todo,
                after_project=result.todo.project,
            )
        )

        get_console().print(f"[green]✅ Added:[/green] {format_todo_for_display(result.todo)}")

    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not create todo")


def _split_prompt_tokens(value: str) -> list[str]:
    """Split comma or space separated prompt input into tokens."""
    return [token for token in value.replace(",", " ").split() if token]


def _guided_add(storage: Storage, config, project: Optional[str]) -> None:
    """Prompt for task fields and save a todo."""
    text = validate_task_text(click.prompt("Task"))
    target_project = click.prompt(
        "Project",
        default=project or config.default_project,
        show_default=True,
    )
    target_project = validate_project_name(target_project)
    priority = click.prompt(
        "Priority",
        type=click.Choice(["critical", "high", "medium", "low"]),
        default=config.default_priority.value,
        show_default=True,
    )
    due_input = click.prompt("Due date", default="", show_default=False)
    tags_input = click.prompt("Tags", default="", show_default=False)
    context_input = click.prompt("Contexts", default="", show_default=False)

    tags = validate_name_tokens(_split_prompt_tokens(tags_input), field_name="tag")
    contexts = validate_name_tokens(_split_prompt_tokens(context_input), field_name="context")
    due_date = _parse_due_date(due_input) if due_input.strip() else None

    project_obj, existing_todos = storage.load_project(target_project)
    next_id = (max(todo.id for todo in existing_todos) + 1) if existing_todos else 1
    todo = Todo(
        id=next_id,
        text=text,
        project=target_project,
        priority=Priority(priority),
        due_date=due_date,
        tags=tags,
        context=contexts,
    )

    get_console().print("[bold yellow]Preview:[/bold yellow]")
    get_console().print(f"  {format_todo_for_display(todo)}")
    if not click.confirm("Save this task?", default=True):
        get_console().print("[muted]Task not saved.[/muted]")
        return

    existing_todos.append(todo)
    storage.save_project(project_obj, existing_todos)
    _record_operation(
        OperationRecord.create(
            "add",
            todo_id=todo.id,
            after=todo,
            after_project=target_project,
        )
    )
    get_console().print(f"[green]✅ Added:[/green] {format_todo_for_display(todo)}")


@cli.command()
@click.argument("text", required=True)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project to add to (default: inbox)")
@click.option("--priority", type=click.Choice(['critical', 'high', 'medium', 'low']), default='medium', help="Task priority")
@click.option("--tag", "-t", multiple=True, shell_complete=_complete_tags, help="Add tags (can be used multiple times)")
@click.option("--context", "-c", multiple=True, shell_complete=_complete_contexts, help="Add contexts (can be used multiple times)")
def quick(text, project, priority, tag, context):
    """Quick capture - add a todo with minimal processing.
    
    Examples:
      todo quick "Call the client"
      todo quick "Review PR" --tag work --priority high
      todo quick "Buy groceries" --context errands --project personal
    """
    try:
        storage = get_storage()
        config = get_config()

        text = validate_task_text(text)
        target_project = validate_project_name(project or config.default_project)
        tag = tuple(validate_name_tokens(tag, field_name="tag"))
        context = tuple(validate_name_tokens(context, field_name="context"))
        proj, existing_todos = storage.load_project(target_project)
        next_id = (max(todo.id for todo in existing_todos) + 1) if existing_todos else 1

        todo = Todo(
            id=next_id,
            text=text,
            project=target_project,
            priority=Priority(priority),
            tags=list(tag) if tag else [],
            context=list(context) if context else [],
        )

        existing_todos.append(todo)
        storage.save_project(proj, existing_todos)
        _record_operation(
            OperationRecord.create(
                "add",
                todo_id=todo.id,
                after=todo,
                after_project=target_project,
            )
        )

        priority_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
        emoji = priority_emoji.get(priority, "🟡")

        tags_str = f" #{' #'.join(tag)}" if tag else ""
        context_str = f" @{' @'.join(context)}" if context else ""
        proj_str = f" ({target_project})" if target_project != "inbox" else ""

        get_console().print(
            f"[green]✅ Quick added:[/green] {emoji} {text}{tags_str}{context_str}{proj_str}"
        )

    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not create todo")


@cli.command()
@click.option("--project", "-p", shell_complete=_complete_projects, help="Filter by project")
@click.option("--group-by", type=click.Choice(['status', 'priority', 'tag', 'context']), default='status', 
              help="Group todos by field")
@click.option("--tag", "-t", multiple=True, shell_complete=_complete_tags, help="Filter by tags")
@click.option("--context", "-c", multiple=True, shell_complete=_complete_contexts, help="Filter by contexts")
def board(project: str, group_by: str, tag: tuple, context: tuple):
    """Display todos in a kanban-style board view.
    
    Examples:
      todo board                    # Group by status
      todo board --group-by priority # Group by priority
      todo board --tag work --context office  # Filter and group
      todo board -p work_project    # Show specific project
    """
    try:
        storage = get_storage()
        config = get_config()
        
        # Get all todos
        all_todos = []
        
        if project:
            projects = [project]
        else:
            projects = storage.list_projects()
            if not projects:
                projects = [config.default_project]
        
        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            if todos:
                all_todos.extend([(todo, proj_name) for todo in todos])
        
        if not all_todos:
            get_console().print("[yellow]No todos found.[/yellow]")
            return
        
        # Apply filters
        filtered_todos = all_todos
        
        # Filter by tags
        if tag:
            filtered_todos = [(todo, proj) for todo, proj in filtered_todos 
                            if any(t in todo.tags for t in tag)]
        
        # Filter by contexts
        if context:
            filtered_todos = [(todo, proj) for todo, proj in filtered_todos 
                            if any(c in todo.context for c in context)]
        
        if not filtered_todos:
            get_console().print("[yellow]No todos match the specified filters.[/yellow]")
            return
        
        # Group todos by the specified field
        groups = {}
        
        for todo, proj_name in filtered_todos:
            if group_by == 'status':
                key = todo.status.value.title()
            elif group_by == 'priority':
                key = todo.priority.value.title()
            elif group_by == 'tag':
                # Group by primary tag (first tag) or 'No Tag'
                key = todo.tags[0] if todo.tags else 'No Tag'
            elif group_by == 'context':
                # Group by primary context (first context) or 'No Context'
                key = todo.context[0] if todo.context else 'No Context'
            
            if key not in groups:
                groups[key] = []
            groups[key].append((todo, proj_name))
        
        # Display the board
        get_console().print(f"\n[bold blue]📋 Kanban Board - Grouped by {group_by.title()}[/bold blue]")
        
        if project:
            get_console().print(f"[muted]Project: {project}[/muted]")
        
        if tag or context:
            filters = []
            if tag:
                filters.append(f"Tags: {', '.join(tag)}")
            if context:
                filters.append(f"Contexts: {', '.join(context)}")
            get_console().print(f"[muted]Filters: {' | '.join(filters)}[/muted]")
        
        get_console().print()
        
        # Sort groups for consistent display
        if group_by == 'status':
            # Logical order for status
            status_order = ['Pending', 'In Progress', 'Blocked', 'Completed', 'Cancelled']
            sorted_groups = [(key, groups[key]) for key in status_order if key in groups]
            # Add any other groups not in the predefined order
            for key in groups:
                if key not in status_order:
                    sorted_groups.append((key, groups[key]))
        elif group_by == 'priority':
            # High to low priority order
            priority_order = ['Critical', 'High', 'Medium', 'Low']
            sorted_groups = [(key, groups[key]) for key in priority_order if key in groups]
            for key in groups:
                if key not in priority_order:
                    sorted_groups.append((key, groups[key]))
        else:
            # Alphabetical order for tags/contexts
            sorted_groups = sorted(groups.items())
        
        # Calculate column width for display
        max_width = 40
        num_groups = len(sorted_groups)
        
        # Display groups as columns
        for i, (group_name, group_todos) in enumerate(sorted_groups):
            # Group header with count
            count = len(group_todos)
            
            # Choose colors/emojis based on group type
            if group_by == 'status':
                status_colors = {
                    'Pending': ('🗓️', 'yellow'),
                    'In Progress': ('🔄', 'blue'),
                    'Blocked': ('🚫', 'red'),
                    'Completed': ('✅', 'green'),
                    'Cancelled': ('❌', 'red')
                }
                emoji, color = status_colors.get(group_name, ('📋', 'white'))
            elif group_by == 'priority':
                priority_colors = {
                    'Critical': ('🔴', 'red'),
                    'High': ('🟠', 'red'),
                    'Medium': ('🟡', 'yellow'),
                    'Low': ('🔵', 'blue')
                }
                emoji, color = priority_colors.get(group_name, ('📋', 'white'))
            else:
                emoji, color = '🏷️', 'cyan'
            
            # Header
            get_console().print(f"[bold {color}]{emoji} {group_name} ({count})[/bold {color}]")
            get_console().print(f"[{color}]{'─' * min(len(f'{group_name} ({count})') + 3, max_width)}[/{color}]")
            
            # Sort todos within group by priority and due date
            priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
            
            def sort_key(todo_proj_tuple):
                todo, _ = todo_proj_tuple
                from ..utils.datetime import ensure_aware, max_utc
                return (
                    not todo.pinned,  # Pinned first
                    priority_order.get(todo.priority, 2),
                    ensure_aware(todo.due_date) if todo.due_date else max_utc(),
                    todo.id
                )
            
            group_todos.sort(key=sort_key)
            
            # Display todos in the group
            if group_todos:
                for todo, proj_name in group_todos[:10]:  # Limit to 10 per column
                    # Compact todo display for board view
                    status_icon = get_status_emoji(todo.status.value, todo.pinned)
                    
                    # Priority indicator
                    priority_indicator = {
                        Priority.CRITICAL: "[red]⚠[/red]",
                        Priority.HIGH: "[yellow]⬆[/yellow]", 
                        Priority.MEDIUM: "",
                        Priority.LOW: "[blue]⬇[/blue]"
                    }.get(todo.priority, "")
                    
                    # Truncate long text
                    text = todo.text[:35] + "..." if len(todo.text) > 35 else todo.text
                    
                    # Show due date if present
                    due_str = ""
                    if todo.due_date:
                        if todo.is_overdue():
                            due_str = f" [red]![/red]{todo.due_date.strftime('%m/%d')}"
                        else:
                            due_str = f" [muted]!{todo.due_date.strftime('%m/%d')}[/muted]"
                    
                    # Project info if showing multiple projects
                    proj_str = f" [dim]({proj_name})[/dim]" if not project else ""
                    
                    get_console().print(
                        f"  {status_icon} [muted]{todo.id:2d}[/muted] {priority_indicator}{text}{due_str}{proj_str}"
                    )
                
                if len(group_todos) > 10:
                    remaining = len(group_todos) - 10
                    get_console().print(f"  [dim]... and {remaining} more[/dim]")
            else:
                get_console().print("  [dim]No items[/dim]")
            
            get_console().print()  # Space between columns
        
        # Summary
        total_todos = len(filtered_todos)
        get_console().print(f"[bold]Summary:[/bold] {total_todos} todos in {len(sorted_groups)} groups")
        
    except Exception as e:
        get_console().print(f"[red]❌ Error displaying board: {e}[/red]")
        sys.exit(1)


def _dashboard_panel(section_key: str, todos: list[Todo], max_items: int) -> Panel:
    """Build one dashboard section panel."""
    content_lines = [
        format_todo_for_display(todo, show_id=True)
        for todo in todos[:max_items]
    ]
    if len(todos) > max_items:
        content_lines.append(f"[muted]... and {len(todos) - max_items} more[/muted]")

    return Panel(
        "\n".join(content_lines),
        title=DASHBOARD_SECTION_TITLES[section_key],
        border_style=DASHBOARD_SECTION_BORDER_STYLES[section_key],
        style=DASHBOARD_SECTION_STYLES[section_key],
        expand=True,
    )


def _dashboard_grid(sections: list[tuple[str, list[Todo]]], columns: int, max_items: int) -> Table:
    """Render dashboard sections in a responsive grid."""
    grid = Table.grid(expand=True, padding=(0, 1))
    for _ in range(columns):
        grid.add_column(ratio=1)

    panels = [
        _dashboard_panel(section_key, todos, max_items)
        for section_key, todos in sections
        if todos
    ]

    for index in range(0, len(panels), columns):
        row = panels[index:index + columns]
        if len(row) < columns:
            row.extend([""] * (columns - len(row)))
        grid.add_row(*row)
        if index + columns < len(panels):
            grid.add_row(*([""] * columns))

    return grid


def _dashboard_grid_settings(config) -> tuple[int, int, list[str]]:
    """Read dashboard grid settings with safe fallbacks."""
    try:
        columns = int(config.dashboard_grid_columns)
    except (TypeError, ValueError):
        columns = 2

    try:
        max_items = int(config.dashboard_grid_max_items)
    except (TypeError, ValueError):
        max_items = 5

    configured_sections = getattr(config, "dashboard_grid_sections", None)
    if not isinstance(configured_sections, list):
        configured_sections = []

    section_order = [
        section
        for section in configured_sections
        if section in DASHBOARD_SECTION_TITLES
    ]
    for section in DASHBOARD_SECTION_TITLES:
        if section not in section_order:
            section_order.append(section)

    return max(1, min(columns, 3)), max(1, max_items), section_order


@cli.command()
def dashboard():
    """Show dashboard with overview of tasks."""
    storage = get_storage()
    config = get_config()
    
    # Collect all todos
    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    if not all_todos:
        # Create themed welcome panel with background colors
        welcome_panel = Panel(
            "[accent]Welcome to Productivity Ninja CLI![/accent]\n\n"
            "Get started by adding your first task:\n"
            "[primary]todo add[/primary] [muted]\"Review architecture proposal @meetings due friday\"[/muted]\n\n"
            "[muted]💡 Try some examples:[/muted]\n"
            "[primary]todo add[/primary] [muted]\"Call client @phone ~high due tomorrow\"[/muted]\n"
            "[primary]todo add[/primary] [muted]\"Deploy app #project1 @work +john\"[/muted]\n"
            "[primary]todo add[/primary] [muted]\"Meeting prep [PIN] est:1h\"[/muted]",
            title="[header]🚀 Getting Started[/header]",
            border_style="welcome_border",
            style="welcome_bg"
        )
        get_console().print(welcome_panel)
        return
    
    # Categorize todos
    pinned_todos = [t for t in all_todos if t.pinned and not t.completed]
    overdue_todos = [t for t in all_todos if t.is_overdue() and not t.completed]
    today_todos = []
    upcoming_todos = []
    
    today = datetime.now().date()
    week_from_now = today + timedelta(days=7)
    
    for todo in all_todos:
        if todo.completed or not todo.due_date:
            continue
        
        due_date = todo.due_date.date()
        if due_date == today:
            today_todos.append(todo)
        elif due_date <= week_from_now:
            upcoming_todos.append(todo)
    
    # Create dashboard
    show_dashboard_banner(get_console())

    dashboard_sections = {
        "pinned": pinned_todos,
        "overdue": overdue_todos,
        "today": today_todos,
        "upcoming": upcoming_todos,
    }
    grid_columns, grid_max_items, grid_section_order = _dashboard_grid_settings(config)
    grid_sections = [
        (section, dashboard_sections[section])
        for section in grid_section_order
        if dashboard_sections[section]
    ]

    if grid_sections:
        get_console().print()
        get_console().print(_dashboard_grid(grid_sections, grid_columns, grid_max_items))
    
    # Summary stats
    total_todos = len(all_todos)
    completed_todos = sum(1 for t in all_todos if t.completed)
    active_todos = sum(1 for t in all_todos if t.is_active())
    
    # Check and send notifications silently
    try:
        from ..services import NotificationManager
        notification_manager = NotificationManager()
        notification_manager.check_and_send_notifications(all_todos)
    except Exception:
        # Silently ignore notification failures
        pass
    
    if grid_sections:
        get_console().print()  # Extra space before summary
    
    # Create bordered panel for summary stats
    summary_panel = Panel(
        f"[header]Total: {total_todos}[/header] | [primary]Active: {active_todos}[/primary] | [success]Completed: {completed_todos}[/success]",
        title="[panel_title]Summary[/panel_title]",
        border_style="section_border",
        style="container_bg"
    )
    get_console().print(summary_panel)


@cli.command()
@click.option("--project", "-p", shell_complete=_complete_projects, help="Filter by project")
@click.option("--status", type=click.Choice(['pending', 'in_progress', 'completed', 'cancelled', 'blocked']), 
              help="Filter by status")
@click.option("--filter-priority", type=click.Choice(['critical', 'high', 'medium', 'low']), 
              help="Filter by priority")
@click.option("--overdue", is_flag=True, help="Show only overdue tasks")
@click.option("--pinned", is_flag=True, help="Show only pinned tasks")
@click.option("--limit", "-l", type=int, default=50, help="Limit number of results")
@click.option("--priority-sort", is_flag=True, help="Sort tasks by priority (highest to lowest) instead of ID")
def list_todos(project, status, filter_priority, overdue, pinned, limit, priority_sort):
    """List todo items organized by date views."""
    from ..theme import organize_todos_by_date, get_view_header

    try:
        storage = get_storage()
        config = get_config()

        all_todos = []

        if project:
            projects = [validate_project_name(project)]
        else:
            projects = storage.list_projects()
            if not projects:
                projects = [config.default_project]

        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            if todos:
                all_todos.extend(todos)

        if not all_todos:
            get_console().print("[yellow]No todos found.[/yellow]")
            return

        filtered_todos = all_todos

        if status:
            filtered_todos = [t for t in filtered_todos if t.status == TodoStatus(status)]

        if filter_priority:
            filtered_todos = [t for t in filtered_todos if t.priority == Priority(filter_priority)]

        if overdue:
            filtered_todos = [t for t in filtered_todos if t.is_overdue()]

        if pinned:
            filtered_todos = [t for t in filtered_todos if t.pinned]

        if status or filter_priority or overdue or pinned:
            priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}

            def sort_key(todo):
                return (
                    not todo.pinned,
                    priority_order.get(todo.priority, 2),
                    ensure_aware(todo.due_date) if todo.due_date else max_utc(),
                    todo.id,
                )

            filtered_todos.sort(key=sort_key)

            if limit:
                filtered_todos = filtered_todos[:limit]

            if filtered_todos:
                get_console().print(f"[bold]Found {len(filtered_todos)} todos:[/bold]")
                for todo in filtered_todos:
                    get_console().print(format_todo_for_display(todo))
            else:
                get_console().print("[yellow]No todos match the specified filters.[/yellow]")
        else:
            views = organize_todos_by_date(filtered_todos, sort_by_priority=priority_sort)

            for view_name in ['today', 'tomorrow', 'upcoming', 'backlog']:
                view_todos = views[view_name]

                if limit and view_todos:
                    view_todos = view_todos[:limit]

                if view_todos or view_name in ['today', 'tomorrow']:
                    get_console().print(f"\n{get_view_header(view_name, len(view_todos))}")

                    if view_todos:
                        for todo in view_todos:
                            get_console().print(f"  {format_todo_for_display(todo)}")
                    else:
                        get_console().print("  [muted]No tasks[/muted]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not list tasks")


@cli.command()
@click.argument("todo_id", type=int)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project name (if not specified, searches all projects)")
def done(todo_id, project):
    """Mark a todo as completed."""
    _complete_todo(todo_id, project)


def _complete_todo(todo_id, project):
    """Mark a todo as completed."""
    try:
        storage = get_storage()
        todo_id = validate_todo_id(todo_id)
        project = validate_project_name(project)

        found_todo = None
        found_project = None
        found_todos = None

        if project:
            projects = [project]
        else:
            config = get_config()
            projects = storage.list_projects()
            if not projects:
                projects = [config.default_project]

        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            for todo in todos:
                if todo.id == todo_id:
                    found_todo = todo
                    found_project = proj
                    found_todos = todos
                    break
            if found_todo:
                break

        if not found_todo:
            raise TaskNotFoundError(todo_id, project=project)

        before = _snapshot_todo(found_todo)
        found_todo.complete()
        storage.save_project(found_project, found_todos)
        _record_operation(
            OperationRecord.create(
                "done",
                todo_id=found_todo.id,
                before=before,
                after=found_todo,
                before_project=found_project.name,
                after_project=found_project.name,
            )
        )
        get_console().print(f"[green]✅ Completed task {todo_id}: {found_todo.text}[/green]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not complete task")


@cli.command("complete", hidden=True)
@click.argument("todo_id", type=int)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project name (if not specified, searches all projects)")
def complete_alias(todo_id, project):
    """Alias for done."""
    _complete_todo(todo_id, project)


@cli.command()
@click.argument("todo_id", type=int)
@click.option("--from-project", shell_complete=_complete_projects, help="Project to search (defaults to all projects)")
@click.option("--text", help="Replace the task text")
@click.option("--priority", type=click.Choice(['critical', 'high', 'medium', 'low']), help="Set task priority")
@click.option("--due", help="Set due date, or use 'none' to clear it")
@click.option("--project", "-p", "target_project", shell_complete=_complete_projects, help="Move task to another project")
def edit(todo_id, from_project, text, priority, due, target_project):
    """Edit a todo's common fields."""
    try:
        if not any(value is not None for value in (text, priority, due, target_project)):
            raise ValidationError(
                "No edits specified.",
                suggestion="Use --text, --priority, --due, or --project.",
            )

        storage = get_storage()
        project_obj, todos, todo = _find_todo(storage, todo_id, from_project)
        original_project = project_obj.name
        before = _snapshot_todo(todo)

        if text is not None:
            todo.text = validate_task_text(text)
        if priority is not None:
            todo.priority = Priority(priority)
        if due is not None:
            todo.due_date = _parse_due_date(due)

        target_project = validate_project_name(target_project)
        if target_project and target_project != original_project:
            todos.remove(todo)
            storage.save_project(project_obj, todos)

            target_project_obj, target_todos = storage.load_project(target_project)
            todo.project = target_project
            todo.modified = now_utc()
            target_todos.append(todo)
            storage.save_project(target_project_obj, target_todos)
        else:
            todo.modified = now_utc()
            storage.save_project(project_obj, todos)

        _record_operation(
            OperationRecord.create(
                "edit",
                todo_id=todo.id,
                before=before,
                after=todo,
                before_project=original_project,
                after_project=todo.project,
            )
        )
        get_console().print(f"[green]✅ Updated task {todo_id}: {todo.text}[/green]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not edit task")


@cli.command()
@click.argument("todo_id", type=int)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project name (if not specified, searches all projects)")
@click.option("--yes", "-y", is_flag=True, help="Delete without confirmation")
def delete(todo_id, project, yes):
    """Delete a todo after confirmation."""
    try:
        storage = get_storage()
        project_obj, todos, todo = _find_todo(storage, todo_id, project)
        before = _snapshot_todo(todo)

        if not yes:
            get_console().print(f"[warning]Will delete task {todo.id}: {todo.text}[/warning]")
            if not click.confirm("Delete this task?"):
                get_console().print("[muted]Deletion cancelled.[/muted]")
                return

        storage.backup_project(project_obj.name)
        todos.remove(todo)
        storage.save_project(project_obj, todos)
        _record_operation(
            OperationRecord.create(
                "delete",
                todo_id=todo.id,
                before=before,
                before_project=project_obj.name,
            )
        )
        get_console().print(f"[green]✅ Deleted task {todo_id}: {todo.text}[/green]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not delete task")


@cli.command()
def undo():
    """Undo the last reversible task change."""
    try:
        record = get_operation_history().undo_last(get_storage())
        action = {
            "add": "Removed added task",
            "done": "Reopened completed task",
            "edit": "Restored edited task",
            "delete": "Restored deleted task",
        }.get(record.operation, f"Undid {record.operation}")
        get_console().print(f"[green]✅ {action} {record.todo_id}[/green]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not undo")


@cli.command()
@click.argument("todo_id", type=int)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Project name")
def pin(todo_id, project):
    """Pin/unpin a todo."""
    try:
        storage = get_storage()
        todo_id = validate_todo_id(todo_id)
        project = validate_project_name(project)

        found_todo = None
        found_project = None
        found_todos = None

        if project:
            projects = [project]
        else:
            config = get_config()
            projects = storage.list_projects()
            if not projects:
                projects = [config.default_project]

        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            for todo in todos:
                if todo.id == todo_id:
                    found_todo = todo
                    found_project = proj
                    found_todos = todos
                    break
            if found_todo:
                break

        if not found_todo:
            raise TaskNotFoundError(todo_id, project=project)

        if found_todo.pinned:
            found_todo.unpin()
            action = "Unpinned"
        else:
            found_todo.pin()
            action = "Pinned"

        storage.save_project(found_project, found_todos)
        get_console().print(f"[green]✅ {action} task {todo_id}: {found_todo.text}[/green]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not update task")


@cli.command()
@click.argument("query", shell_complete=_complete_saved_query_refs)
@click.option("--project", "-p", shell_complete=_complete_projects, help="Limit search to specific project")
@click.option("--save", "save_name", help="Save this query with a name")
@click.option("--sort", "sort_by", help="Sort results by field (priority, due, created, etc.)")
@click.option("--limit", "-l", type=int, help="Limit number of results")
@click.option("--reverse", "-r", is_flag=True, help="Reverse sort order")
def search(query, project, save_name, sort_by, limit, reverse):
    """Search todos with advanced query syntax.
    
    Examples:
      todo search "priority:high status:pending"
      todo search "tag:urgent OR tag:important"
      todo search "due:this-week assignee:me"
      todo search "is:overdue NOT project:personal"
      todo search "effort:quick,small energy:low"
    """
    storage = get_storage()
    config = get_config()
    
    # Get all todos from specified project or all projects
    all_todos = []
    
    if project:
        projects = [project]
    else:
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    if not all_todos:
        get_console().print("[yellow]No todos found to search.[/yellow]")
        return
    
    try:
        # Execute search query
        results = _get_query_engine().search(all_todos, query)
        
        # Save query if requested
        if save_name:
            _get_query_engine().save_query(save_name, query)
            get_console().print(f"[success]✅ Saved query as '{save_name}'[/success]")
        
        # Sort results if requested
        if sort_by:
            results = _sort_todos(results, sort_by, reverse)
        
        # Limit results if requested
        if limit and len(results) > limit:
            results = results[:limit]
            truncated = True
        else:
            truncated = False
        
        # Display results
        if results:
            get_console().print(f"\n[success]Found {len(results)} todo{'s' if len(results) != 1 else ''}:[/success]")
            if truncated:
                get_console().print(f"[muted](showing first {limit} results)[/muted]")
            
            for todo in results:
                get_console().print(f"  {format_todo_for_display(todo)}")
        else:
            get_console().print("[yellow]No todos match your search.[/yellow]")
        
    except ValueError as e:
        get_console().print(f"[error]Search error: {e}[/error]")
        get_console().print("[muted]Try: todo search --help for syntax examples[/muted]")
        sys.exit(1)


def _sort_todos(todos, sort_field, reverse=False):
    """Sort todos by specified field"""
    sort_keys = {
        'priority': lambda t: ({'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(t.priority.value if t.priority else 'medium', 2), t.id),
        'due': lambda t: ((ensure_aware(t.due_date) if t.due_date else max_utc()), t.id),
        'created': lambda t: (t.created, t.id),
        'project': lambda t: (t.project or '', t.id),
        'status': lambda t: (t.status.value if t.status else 'pending', t.id),
        'text': lambda t: (t.text.lower(), t.id),
        'id': lambda t: t.id,
    }
    
    if sort_field not in sort_keys:
        return todos
    
    return sorted(todos, key=sort_keys[sort_field], reverse=reverse)


@cli.command()
@click.option("--context", "-c", shell_complete=_complete_contexts, help="Current context (e.g., work, home, focus)")
@click.option("--energy", "-e", type=click.Choice(['high', 'medium', 'low']), default='medium', help="Current energy level")
@click.option("--time", "-t", type=int, help="Available time in minutes")
@click.option("--limit", "-l", type=int, default=5, help="Number of recommendations")
@click.option("--explain", is_flag=True, help="Show detailed explanations for recommendations")
def recommend(context, energy, time, limit, explain):
    """Get personalized task recommendations based on context, energy, and patterns.
    
    Examples:
      todo recommend --energy high --time 30
      todo recommend --context work --energy low  
      todo recommend --explain
    """
    storage = get_storage()
    config = get_config()
    
    # Get all todos
    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    if not all_todos:
        get_console().print("[yellow]No todos found to analyze.[/yellow]")
        return
    
    # Get recommendations
    recommendations = _get_recommend_engine().get_recommendations(
        all_todos,
        current_context=context,
        current_energy=energy, 
        available_time=time,
        limit=limit
    )
    
    if not recommendations:
        get_console().print("[yellow]No active tasks to recommend.[/yellow]")
        return
    
    # Display recommendations
    get_console().print(f"\n[success]🎯 Top {len(recommendations)} Recommendations:[/success]")
    
    if context:
        get_console().print(f"[muted]Context: {context}[/muted]")
    get_console().print(f"[muted]Energy Level: {energy}[/muted]")
    if time:
        get_console().print(f"[muted]Available Time: {time} minutes[/muted]")
    
    for i, rec in enumerate(recommendations, 1):
        # Category icon
        category_icons = {
            'urgent': '🔥',
            'contextual': '🎯',
            'energy-match': '⚡',
            'pattern-based': '🧠',
            'general': '📋'
        }
        icon = category_icons.get(rec.category, '📋')
        
        get_console().print(f"\n{i}. {icon} {format_todo_for_display(rec.todo)}")
        
        if explain:
            get_console().print(f"   [muted]Score: {rec.score:.1f} | Category: {rec.category}[/muted]")
            if rec.reasons:
                reasons_text = ", ".join(rec.reasons)
                get_console().print(f"   [muted]Why: {reasons_text}[/muted]")
    
    # Show contextual suggestions
    from ..services import get_context_suggestions, get_energy_suggestions
    if not context:
        suggested_contexts = get_context_suggestions(all_todos)
        if suggested_contexts:
            get_console().print(f"\n[muted]💡 Suggested contexts for this time: {', '.join(suggested_contexts)}[/muted]")
    
    # Show energy-based suggestions
    energy_suggestions = get_energy_suggestions(energy)
    if energy_suggestions:
        get_console().print(f"\n[muted]💪 Good for {energy} energy:[/muted]")
        for suggestion in energy_suggestions['suggestions'][:3]:
            get_console().print(f"[muted]   • {suggestion}[/muted]")


@cli.command()
@click.option("--list", "list_queries", is_flag=True, help="List all saved queries")
@click.option("--delete", "delete_name", shell_complete=_complete_saved_query_names, help="Delete a saved query")
def queries(list_queries, delete_name):
    """Manage saved search queries."""
    if list_queries:
        saved = _get_query_engine().list_saved_queries()
        if saved:
            get_console().print("[bold]Saved Queries:[/bold]")
            for name, query in saved.items():
                get_console().print(f"  [primary]{name}[/primary]: {query}")
                get_console().print(f"    [muted]Usage: todo search @{name}[/muted]")
        else:
            get_console().print("[muted]No saved queries found.[/muted]")
            get_console().print("[muted]Save a query with: todo search 'query' --save name[/muted]")
    elif delete_name:
        if _get_query_engine().delete_query(delete_name):
            get_console().print(f"[success]✅ Deleted saved query '{delete_name}'[/success]")
        else:
            get_console().print(f"[error]❌ Saved query '{delete_name}' not found[/error]")
    else:
        get_console().print("[muted]Use --list to see saved queries or --delete to remove one[/muted]")


@cli.command()
@click.argument("action", type=click.Choice(['complete', 'pin', 'unpin', 'priority', 'project', 'delete']))
@click.argument("ids", nargs=-1, type=int, required=True)
@click.option("--priority", type=click.Choice(['critical', 'high', 'medium', 'low']), help="Priority for priority action")
@click.option("--project", "target_project", shell_complete=_complete_projects, help="Target project for project action")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompts")
def bulk(action, ids, priority, target_project, confirm):
    """Perform bulk operations on multiple todos.
    
    Examples:
      todo bulk complete 1 2 3       # Mark todos 1, 2, 3 as complete
      todo bulk pin 5 7 9            # Pin todos 5, 7, 9
      todo bulk priority 1 2 --priority high  # Set priority to high
      todo bulk project 4 5 --project work    # Move to work project
      todo bulk delete 8 9 10 --confirm       # Delete without prompts
    """
    try:
        storage = get_storage()
        config = get_config()

        ids = tuple(validate_todo_id(todo_id) for todo_id in ids)
        target_project = validate_project_name(target_project)

        if not ids:
            raise ValidationError("No todo IDs specified.")

        if action == 'priority' and not priority:
            raise ValidationError("--priority option required for priority action.")

        if action == 'project' and not target_project:
            raise ValidationError("--project option required for project action.")

        all_projects = storage.list_projects() or [config.default_project]
        found_todos = []
        project_map = {}  # todo_id -> (project, todos_list)
        projects_to_save = {}  # project name -> (project, todos_list)

        for proj_name in all_projects:
            proj, todos = storage.load_project(proj_name)
            for todo in todos:
                if todo.id in ids:
                    found_todos.append(todo)
                    project_map[todo.id] = (proj, todos)

        if not found_todos:
            raise TaskNotFoundError(ids[0])

        missing_ids = set(ids) - {t.id for t in found_todos}
        if missing_ids:
            get_console().print(f"[warning]⚠️  Todo IDs not found: {sorted(missing_ids)}[/warning]")

        get_console().print(f"\n[primary]Found {len(found_todos)} todos to {action}:[/primary]")
        for todo in found_todos:
            get_console().print(f"  {format_todo_for_display(todo)}")

        if not confirm:
            action_descriptions = {
                'complete': 'mark as complete',
                'pin': 'pin',
                'unpin': 'unpin',
                'priority': f'set priority to {priority}',
                'project': f'move to project {target_project}',
                'delete': 'DELETE permanently',
            }
            description = action_descriptions.get(action, action)

            if not click.confirm(f"\nProceed to {description} {len(found_todos)} todos?"):
                get_console().print("[muted]Operation cancelled.[/muted]")
                return

        success_count = 0

        for todo in found_todos:
            proj, todos_list = project_map[todo.id]

            if action == 'complete':
                if not todo.completed:
                    todo.complete()
                    success_count += 1
                    projects_to_save[proj.name] = (proj, todos_list)
            elif action == 'pin':
                if not todo.pinned:
                    todo.pin()
                    success_count += 1
                    projects_to_save[proj.name] = (proj, todos_list)
            elif action == 'unpin':
                if todo.pinned:
                    todo.unpin()
                    success_count += 1
                    projects_to_save[proj.name] = (proj, todos_list)
            elif action == 'priority':
                todo.priority = Priority(priority)
                success_count += 1
                projects_to_save[proj.name] = (proj, todos_list)
            elif action == 'project':
                if todo.project != target_project:
                    todos_list.remove(todo)
                    projects_to_save[proj.name] = (proj, todos_list)

                    target_proj, target_todos = storage.load_project(target_project)
                    todo.project = target_project
                    target_todos.append(todo)
                    projects_to_save[target_proj.name] = (target_proj, target_todos)

                    success_count += 1
            elif action == 'delete':
                storage.backup_project(proj.name)
                todos_list.remove(todo)
                projects_to_save[proj.name] = (proj, todos_list)
                success_count += 1

        for proj, todos in projects_to_save.values():
            storage.save_project(proj, todos)

        if success_count > 0:
            action_past_tense = {
                'complete': 'completed',
                'pin': 'pinned',
                'unpin': 'unpinned',
                'priority': f'set to {priority} priority',
                'project': f'moved to {target_project}',
                'delete': 'deleted',
            }
            past_tense = action_past_tense.get(action, f'{action}d')
            get_console().print(f"\n[success]✅ Successfully {past_tense} {success_count} todos[/success]")
        else:
            get_console().print(f"\n[warning]⚠️  No todos were modified[/warning]")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix=f"could not {action} tasks")


@cli.command()
def projects():
    """List all projects."""
    try:
        storage = get_storage()
        project_names = storage.list_projects()

        if not project_names:
            get_console().print("[yellow]No projects found.[/yellow]")
            return

        get_console().print("[bold]Projects:[/bold]")
        for name in sorted(project_names):
            proj, todos = storage.load_project(name)
            if proj:
                total = len(todos)
                completed = sum(1 for t in todos if t.completed)
                get_console().print(f"  {name} ({completed}/{total} completed)")
    except TodoCliError as e:
        exit_with_error(e, console=get_console(), prefix="could not list projects")


# Create main function that invokes dashboard by default
@click.group(cls=CategorizedGroup, invoke_without_command=True)
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--debug", is_flag=True, help="Show stack traces for expected errors")
@click.option("--no-banner", is_flag=True, help="Skip the startup banner")
@click.pass_context
def main(ctx, config, verbose, debug, no_banner):
    """Productivity Ninja CLI - Master Your Tasks. Unleash Your Potential."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['debug'] = debug
    ctx.obj['no_banner'] = no_banner

    if ctx.invoked_subcommand == "completion":
        return
    
    # Load configuration
    try:
        if config:
            from pathlib import Path
            load_config(Path(config))
        else:
            get_config()
    except Exception as e:
        exit_with_error(ValidationError(f"Configuration error: {e}"), console=get_console())
    
    # If no command provided, show startup experience
    if ctx.invoked_subcommand is None:
        if not no_banner:
            show_startup_banner(get_console())
            show_quick_help(get_console())
        ctx.invoke(dashboard)


@main.command("tui")
def tui():
    """Open the full-screen interactive dashboard."""
    from ..tui import TodoDashboardApp

    TodoDashboardApp().run()


# Add calendar command group
@main.group()
def calendar():
    """Calendar integration commands"""
    pass

@calendar.command(name="list", help="List configured calendars")
def calendar_list():
    """List all configured calendars"""
    from .calendar import calendar_list as cmd_impl
    cmd_impl()

@calendar.command(name="add", help="Add a new calendar")
@click.option("--name", "-n", required=True, help="Calendar name")
@click.option("--type", "-t", "cal_type", required=True, 
              type=click.Choice(["ical", "google_calendar", "apple_calendar", "local_file"]),
              help="Calendar type")
@click.option("--path", "-p", help="File path for file-based calendars")
@click.option("--sync", "-s", default="bidirectional",
              type=click.Choice(["import_only", "export_only", "bidirectional"]),
              help="Sync direction")
@click.option("--conflicts", "-c", default="newest_wins",
              type=click.Choice(["todo_wins", "calendar_wins", "manual", "newest_wins"]),
              help="Conflict resolution strategy")
def calendar_add(name, cal_type, path, sync, conflicts):
    """Add a new calendar configuration"""
    from .calendar import calendar_add as cmd_impl
    cmd_impl(name, cal_type, path, sync, conflicts)

@calendar.command(name="sync", help="Sync with calendars")
@click.option("--name", "-n", help="Sync specific calendar (all calendars if not specified)")
def calendar_sync_cmd(name):
    """Sync todos with calendars"""
    from .calendar import calendar_sync as cmd_impl
    cmd_impl(name)

@calendar.command(name="status", help="Show calendar status")
@click.option("--name", "-n", help="Show status for specific calendar (all calendars if not specified)")
def calendar_status(name):
    """Show calendar sync status"""
    from .calendar import calendar_status as cmd_impl
    cmd_impl(name)

# Add sync command group
@main.group()
def sync():
    """Multi-device synchronization commands"""
    pass

@sync.command(name="setup", help="Set up multi-device synchronization")
@click.option("--provider", "-p", required=True, 
              type=click.Choice(["dropbox", "google_drive", "git", "local_file"]),
              help="Sync provider")
@click.option("--path", required=True, help="Sync directory path or URL")
@click.option("--auto/--manual", default=True, help="Enable/disable automatic sync")
@click.option("--conflicts", "-c", default="newest_wins",
              type=click.Choice(["local_wins", "remote_wins", "manual", "newest_wins", "merge"]),
              help="Conflict resolution strategy")
def sync_setup(provider, path, auto, conflicts):
    """Set up synchronization"""
    from .calendar import sync_setup as cmd_impl
    cmd_impl(provider, path, auto, conflicts)

@sync.command(name="now", help="Perform synchronization now")
@click.option("--direction", "-d", default="full",
              type=click.Choice(["push", "pull", "full"]),
              help="Sync direction")
def sync_now(direction):
    """Perform synchronization now"""
    from .calendar import sync_now as cmd_impl
    cmd_impl(direction)

@sync.command(name="status", help="Show sync status")
def sync_status():
    """Show sync status"""
    from .calendar import sync_status as cmd_impl
    cmd_impl()

@sync.command(name="conflicts", help="List and resolve sync conflicts")
@click.option("--resolve", "-r", help="Resolve conflict with specified todo ID")
@click.option("--using", "-u", type=click.Choice(["local", "remote", "merge"]),
              help="Resolution strategy (required with --resolve)")
def sync_conflicts(resolve, using):
    """List and resolve sync conflicts"""
    from .calendar import sync_conflicts as cmd_impl
    cmd_impl(resolve, using)

@sync.command(name="history", help="Show sync history")
@click.option("--limit", "-l", default=10, help="Limit number of entries")
def sync_history(limit):
    """Show sync history"""
    from .calendar import sync_history as cmd_impl
    cmd_impl(limit)

# Add all commands to the main group
main.add_command(add)
main.add_command(quick)
main.add_command(board)
main.add_command(dashboard)
main.add_command(list_todos, name="list")
main.add_command(search)
main.add_command(recommend)
main.add_command(queries)
main.add_command(bulk)
from .recurring import (
    delete_recurring,
    generate_recurring,
    list_recurring,
    pause_recurring,
    recurring,
    recurring_manager,
    resume_recurring,
)
main.add_command(recurring)
for _legacy_recurring_command in (
    list_recurring,
    generate_recurring,
    pause_recurring,
    resume_recurring,
    delete_recurring,
):
    _legacy_recurring_command.hidden = True
    main.add_command(_legacy_recurring_command)
main.add_command(done)
main.add_command(complete_alias)
main.add_command(edit)
main.add_command(delete)
main.add_command(undo)
main.add_command(pin)
main.add_command(projects)
from .export import export
from .notifications import notify
main.add_command(export)
main.add_command(notify)
from .analytics_commands import get_analytics_commands
main.add_command(get_analytics_commands())

# Add app-sync command group
from .app_sync import app_sync_group
main.add_command(app_sync_group)

# Add doctor command group
from .doctor import doctor
main.add_command(doctor)

# Add completion command group
from .completion import create_completion_group
main.add_command(create_completion_group(main))

# Add theme command group
from .theme_cmds import get_theme_commands
main.add_command(get_theme_commands())

# Add dependencies command group
from .dependencies import get_dependencies_commands
main.add_command(get_dependencies_commands())

# Add context command group
from .context import get_context_commands
main.add_command(get_context_commands())

# Add tags command group
from .tags import get_tags_commands
main.add_command(get_tags_commands())

# Add backup command group
from .backup import get_backup_commands
main.add_command(get_backup_commands())

# Add web command group
from .web import web
main.add_command(web)

# Add dashboard management command group
from .dashboard_commands import dashboard_group
main.add_command(dashboard_group)

# Add voice command group
from .voice_commands import voice_group
main.add_command(voice_group)

# Add AI command group
from .ai_commands import ai_group
main.add_command(ai_group)

# Add pomodoro/focus command group
from .pomodoro_commands import focus_group
main.add_command(focus_group)


# Add collaboration command group
from .collab_commands import collab_group
main.add_command(collab_group)

# Add demo command group
from .demo_commands import demo_group
main.add_command(demo_group)


if __name__ == "__main__":
    main()
