"""Command-line interface for Todo CLI."""

import sys
from typing import Optional
from datetime import datetime, timedelta
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel

from .config import get_config, load_config
from .storage import Storage
from .todo import Todo, TodoStatus, Priority
from .project import Project


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
    if config:
        from pathlib import Path
        load_config(Path(config))
    else:
        get_config()
    
    # If no command provided, show dashboard
    if ctx.invoked_subcommand is None:
        ctx.invoke(dashboard)


@main.command()
@click.argument("text", required=True)
@click.option("--project", "-p", default="inbox", help="Project name")
@click.option("--priority", "-pr", type=click.Choice(['critical', 'high', 'medium', 'low']), 
              default="medium", help="Task priority")
@click.option("--due", "-d", help="Due date (YYYY-MM-DD)")
@click.option("--tags", "-t", multiple=True, help="Tags (can be used multiple times)")
@click.option("--assignee", "-a", multiple=True, help="Assignees (can be used multiple times)")
@click.option("--pin", is_flag=True, help="Pin the task")
def add(text, project, priority, due, tags, assignee, pin):
    """Add a new todo item."""
    storage = get_storage()
    
    # Parse due date
    due_date = None
    if due:
        try:
            due_date = datetime.strptime(due, '%Y-%m-%d')
        except ValueError:
            console.print(f"[red]Error: Invalid due date format. Use YYYY-MM-DD[/red]")
            sys.exit(1)
    
    # Get next todo ID
    todo_id = storage.get_next_todo_id(project)
    
    # Create todo
    todo = Todo(
        id=todo_id,
        text=text,
        project=project,
        priority=Priority(priority),
        due_date=due_date,
        tags=list(tags),
        assignees=list(assignee),
        pinned=pin
    )
    
    # Load project and todos
    proj, todos = storage.load_project(project)
    if not proj:
        proj = Project(name=project)
    
    todos.append(todo)
    
    # Save project
    if storage.save_project(proj, todos):
        console.print(f"[green]✅ Added task {todo_id}: {text}[/green]")
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
            todo.due_date or datetime.max,
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