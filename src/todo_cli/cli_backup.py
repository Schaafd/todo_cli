"""Command-line interface for Todo CLI."""

import sys
from typing import Optional
from datetime import datetime, timedelta
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from .utils.datetime import ensure_aware, max_utc
from rich.panel import Panel

from .config import get_config, load_config
from .storage import Storage
from .todo import Todo, TodoStatus, Priority
from .project import Project
from .parser import parse_task_input, TaskBuilder, ParseError


console = Console()


def get_storage() -> Storage:
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


def format_todo_for_display(todo: Todo, show_id: bool = True) -> str:
    """Format a todo for display."""
    # Status emoji
    status_emoji = {
        TodoStatus.PENDING: "⏳",
        TodoStatus.IN_PROGRESS: "🔄",
        TodoStatus.COMPLETED: "✅",
        TodoStatus.CANCELLED: "❌",
        TodoStatus.BLOCKED: "🚫"
    }
    
    # Priority color
    priority_colors = {
        Priority.CRITICAL: "red",
        Priority.HIGH: "yellow",
        Priority.MEDIUM: "white",
        Priority.LOW: "dim"
    }
    
    status_icon = status_emoji.get(todo.status, "⏳")
    priority_color = priority_colors.get(todo.priority, "white")
    
    # Format text
    text_parts = []
    if show_id:
        text_parts.append(f"[dim]{todo.id}[/dim]")
    
    if todo.pinned:
        text_parts.append("⭐")
    
    text_parts.append(f"{status_icon} [{priority_color}]{todo.text}[/{priority_color}]")
    
    # Add metadata
    if todo.tags:
        text_parts.append(f"[cyan]{''.join(['@' + tag for tag in todo.tags])}[/cyan]")
    
    if todo.due_date:
        if todo.is_overdue():
            text_parts.append(f"[red]!{todo.due_date.strftime('%Y-%m-%d')}[/red]")
        else:
            text_parts.append(f"[blue]!{todo.due_date.strftime('%Y-%m-%d')}[/blue]")
    
    if todo.assignees:
        text_parts.append(f"[green]{' '.join(['+' + assignee for assignee in todo.assignees])}[/green]")
    
    return " ".join(text_parts)


@click.group(invoke_without_command=True)
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def main(ctx, config, verbose):
    """Todo CLI - A powerful command-line todo application."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    
    # Load configuration
    try:
        if config:
            from pathlib import Path
            load_config(Path(config))
        else:
            get_config()
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)
    
    # If no command provided, show dashboard
    if ctx.invoked_subcommand is None:
        console.print("No command provided - would show dashboard")
        # try:
        #     ctx.invoke(dashboard)
        # except Exception as e:
        #     console.print(f"[red]Dashboard error: {e}[/red]")
        #     sys.exit(1)


@main.command()
@click.argument("input_text", required=True)
@click.option("--project", "-p", help="Default project if not specified in text")
@click.option("--dry-run", is_flag=True, help="Parse without saving to see what would be created")
@click.option("--suggest", is_flag=True, help="Show suggestions for improving the input")
def add(input_text, project, dry_run, suggest):
    """Add a new todo item with natural language parsing.
    
    Examples:
      todo add "Review PR #urgent @web due tomorrow"
      todo add "Call doctor @phone ~high est:30m"
      todo add "Deploy app #project1 due friday @work +john"
      todo add "Meeting prep [PIN] energy:high est:1h"
    """
    storage = get_storage()
    config = get_config()
    
    # Get available data for suggestions
    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    available_projects = list(set(t.project for t in all_todos if t.project))
    available_tags = list(set(tag for t in all_todos for tag in t.tags))
    available_people = list(set(person for t in all_todos for person in t.assignees))
    
    # Parse the input
    parsed, errors, suggestions = parse_task_input(
        input_text, 
        config, 
        project_hint=project or config.default_project,
        available_projects=available_projects, 
        available_tags=available_tags, 
        available_people=available_people
    )
    
    # Show parsing errors
    if errors:
        console.print("[bold yellow]⚠️  Parsing Issues:[/bold yellow]")
        for error in errors:
            if error.severity == "error":
                console.print(f"  [red]❌ {error.message}[/red]")
                for suggestion in error.suggestions:
                    console.print(f"     [blue]💡 {suggestion}[/blue]")
            elif error.severity == "warning":
                console.print(f"  [yellow]⚠️  {error.message}[/yellow]")
        
        # Don't proceed if there are blocking errors
        if any(e.severity == "error" for e in errors):
            sys.exit(1)
    
    # Show suggestions if requested
    if suggest or suggestions:
        if suggestions:
            console.print("[bold blue]💡 Suggestions:[/bold blue]")
            for suggestion in suggestions:
                console.print(f"  [blue]{suggestion}[/blue]")
        
        if suggest:
            return
    
    # Get next todo ID for the project
    target_project = parsed.project or project or config.default_project
    todo_id = storage.get_next_todo_id(target_project)
    
    # Build todo with our enhanced data
    builder = TaskBuilder(config)
    todo = builder.build(parsed, todo_id)
    
    # Show preview
    console.print("[bold green]📋 Task Preview:[/bold green]")
    preview_text = format_todo_for_display(todo, show_id=True)
    console.print(f"  {preview_text}")
    
    # Show additional details that aren't in the standard format
    if todo.context:
        console.print(f"  [dim]Context: {', '.join('@' + ctx for ctx in todo.context)}[/dim]")
    if todo.effort:
        console.print(f"  [dim]Effort: *{todo.effort}[/dim]")
    if todo.energy_level != "medium":
        console.print(f"  [dim]Energy: {todo.energy_level}[/dim]")
    if todo.time_estimate:
        hours = todo.time_estimate // 60
        minutes = todo.time_estimate % 60
        if hours > 0:
            console.print(f"  [dim]Estimate: {hours}h {minutes}m[/dim]")
        else:
            console.print(f"  [dim]Estimate: {minutes}m[/dim]")
    if todo.waiting_for:
        console.print(f"  [dim]Waiting for: {', '.join(todo.waiting_for)}[/dim]")
    if todo.url:
        console.print(f"  [dim]URL: {todo.url}[/dim]")
    
    if dry_run:
        console.print("[yellow]🔍 Dry run - not saved[/yellow]")
        return
    
    # Load project and todos
    proj, todos = storage.load_project(target_project)
    if not proj:
        proj = Project(name=target_project)
    
    todos.append(todo)
    
    # Save project
    if storage.save_project(proj, todos):
        console.print(f"[green]✅ Added task {todo_id} to {target_project}[/green]")
    else:
        console.print(f"[red]❌ Failed to add task[/red]")
        sys.exit(1)


@main.command()
@click.option("--project", "-p", help="Filter by project")
@click.option("--status", type=click.Choice(['pending', 'in_progress', 'completed', 'cancelled', 'blocked']), 
              help="Filter by status")
@click.option("--priority", type=click.Choice(['critical', 'high', 'medium', 'low']), 
              help="Filter by priority")
@click.option("--overdue", is_flag=True, help="Show only overdue tasks")
@click.option("--pinned", is_flag=True, help="Show only pinned tasks")
@click.option("--limit", "-l", type=int, default=50, help="Limit number of results")
def list(project, status, priority, overdue, pinned, limit):
    """List todo items."""
    storage = get_storage()
    config = get_config()
    
    # Get all todos from all projects or specific project
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
        console.print("[yellow]No todos found.[/yellow]")
        return
    
    # Apply filters
    filtered_todos = all_todos
    
    if status:
        filtered_todos = [t for t in filtered_todos if t.status == TodoStatus(status)]
    
    if priority:
        filtered_todos = [t for t in filtered_todos if t.priority == Priority(priority)]
    
    if overdue:
        filtered_todos = [t for t in filtered_todos if t.is_overdue()]
    
    if pinned:
        filtered_todos = [t for t in filtered_todos if t.pinned]
    
    # Sort: pinned first, then by priority, then by due date
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    
    def sort_key(todo):
        return (
            not todo.pinned,  # Pinned tasks first
            priority_order.get(todo.priority, 2),
            ensure_aware(todo.due_date) if todo.due_date else max_utc(),
            todo.id
        )
    
    filtered_todos.sort(key=sort_key)
    
    # Limit results
    if limit:
        filtered_todos = filtered_todos[:limit]
    
    # Display todos
    if filtered_todos:
        console.print(f"[bold]Found {len(filtered_todos)} todos:[/bold]")
        for todo in filtered_todos:
            console.print(format_todo_for_display(todo))
    else:
        console.print("[yellow]No todos match the specified filters.[/yellow]")


@main.command()
@click.argument("todo_id", type=int)
@click.option("--project", "-p", help="Project name (if not specified, searches all projects)")
def done(todo_id, project):
    """Mark a todo as completed."""
    storage = get_storage()
    
    # Find the todo
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
        console.print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    # Mark as completed
    found_todo.complete()
    
    # Save project
    if storage.save_project(found_project, found_todos):
        console.print(f"[green]✅ Completed task {todo_id}: {found_todo.text}[/green]")
    else:
        console.print(f"[red]❌ Failed to update task[/red]")
        sys.exit(1)


@main.command()
@click.argument("todo_id", type=int)
@click.option("--project", "-p", help="Project name")
def pin(todo_id, project):
    """Pin/unpin a todo."""
    storage = get_storage()
    
    # Find the todo (similar to done command)
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
        console.print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    # Toggle pin status
    if found_todo.pinned:
        found_todo.unpin()
        action = "Unpinned"
    else:
        found_todo.pin()
        action = "Pinned"
    
    # Save project
    if storage.save_project(found_project, found_todos):
        console.print(f"[green]✅ {action} task {todo_id}: {found_todo.text}[/green]")
    else:
        console.print(f"[red]❌ Failed to update task[/red]")
        sys.exit(1)


@main.command()
def projects():
    """List all projects."""
    storage = get_storage()
    project_names = storage.list_projects()
    
    if not project_names:
        console.print("[yellow]No projects found.[/yellow]")
        return
    
    console.print("[bold]Projects:[/bold]")
    for name in sorted(project_names):
        proj, todos = storage.load_project(name)
        if proj:
            total = len(todos)
            completed = sum(1 for t in todos if t.completed)
            console.print(f"  {name} ({completed}/{total} completed)")


@main.command()
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
        console.print(Panel.fit(
            "[yellow]Welcome to Todo CLI![/yellow]\\n\\n"
            "Get started by adding your first task:\\n"
            "[cyan]todo add \"Your first task\"[/cyan]",
            title="📋 Todo Dashboard"
        ))
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
    console.print(Panel.fit("📋 Todo Dashboard", style="bold blue"))
    
    if pinned_todos:
        console.print("\\n[bold yellow]⭐ Pinned Tasks[/bold yellow]")
        for todo in pinned_todos[:5]:
            console.print(f"  {format_todo_for_display(todo)}")
        if len(pinned_todos) > 5:
            console.print(f"  [dim]... and {len(pinned_todos) - 5} more[/dim]")
    
    if overdue_todos:
        console.print("\\n[bold red]🔥 Overdue Tasks[/bold red]")
        for todo in overdue_todos[:5]:
            console.print(f"  {format_todo_for_display(todo)}")
        if len(overdue_todos) > 5:
            console.print(f"  [dim]... and {len(overdue_todos) - 5} more[/dim]")
    
    if today_todos:
        console.print("\\n[bold green]📅 Due Today[/bold green]")
        for todo in today_todos[:5]:
            console.print(f"  {format_todo_for_display(todo)}")
    
    if upcoming_todos:
        console.print("\\n[bold cyan]📆 Due This Week[/bold cyan]")
        for todo in upcoming_todos[:5]:
            console.print(f"  {format_todo_for_display(todo)}")
    
    # Summary stats
    total_todos = len(all_todos)
    completed_todos = sum(1 for t in all_todos if t.completed)
    active_todos = sum(1 for t in all_todos if t.is_active())
    
    console.print(f"\\n[dim]Total: {total_todos} | Active: {active_todos} | Completed: {completed_todos}[/dim]")


@main.command()
@click.option("--version", is_flag=True, help="Show version")
def info(version):
    """Show application information."""
    if version:
        from . import __version__
        console.print(f"Todo CLI version {__version__}")
    else:
        config = get_config()
        console.print(f"Data directory: {config.data_dir}")
        console.print(f"Configuration: {config.get_config_path()}")
        
        storage = get_storage()
        projects = storage.list_projects()
        console.print(f"Projects: {len(projects)}")


if __name__ == "__main__":
    main()