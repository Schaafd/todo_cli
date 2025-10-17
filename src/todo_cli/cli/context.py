"""Context switching CLI commands for managing work/personal/project contexts."""

import sys
from typing import List, Set
import click
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from ..config import get_config
from ..storage import Storage
from ..domain import Todo, TodoStatus, Priority
from ..theme import get_themed_console


def get_storage() -> Storage:
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


def get_console():
    """Get themed console."""
    return get_themed_console()


def get_current_context() -> str:
    """Get the current active context from config."""
    config = get_config()
    return getattr(config, 'current_context', 'all')


def set_current_context(context: str):
    """Set the current active context in config."""
    # Note: This is a simplified implementation
    # In a real implementation, we'd update the config file
    config = get_config()
    setattr(config, 'current_context', context)


def get_all_contexts() -> Set[str]:
    """Get all available contexts from existing todos."""
    storage = get_storage()
    config = get_config()
    contexts = set()
    
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            for todo in todos:
                contexts.update(todo.context)
    
    return contexts


def filter_todos_by_context(todos: List[Todo], context: str) -> List[Todo]:
    """Filter todos by context. 'all' returns all todos."""
    if context == 'all':
        return todos
    
    return [todo for todo in todos if context in todo.context or not todo.context]


@click.group(name="ctx")
def context():
    """Manage and switch between contexts (work, personal, projects)."""
    pass


@context.command(name="list")
@click.option("--show-counts", is_flag=True, help="Show todo counts per context")
def list_contexts(show_counts: bool):
    """List all available contexts."""
    contexts = get_all_contexts()
    current = get_current_context()
    
    if not contexts:
        get_console().print("[yellow]No contexts found. Add some todos with @context to get started.[/yellow]")
        return
    
    # Always include 'all' context
    all_contexts = ['all'] + sorted(contexts)
    
    if show_counts:
        # Get all todos for counting
        storage = get_storage()
        config = get_config()
        all_todos = []
        
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
        
        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            if todos:
                all_todos.extend(todos)
        
        # Create table with counts
        table = Table(title="🏷️ Available Contexts", show_header=True, header_style="bold blue")
        table.add_column("Context", style="cyan", min_width=12)
        table.add_column("Status", style="white", min_width=8)
        table.add_column("Active Todos", style="green", min_width=12)
        table.add_column("Total Todos", style="yellow", min_width=12)
        
        for ctx in all_contexts:
            filtered_todos = filter_todos_by_context(all_todos, ctx)
            active_count = len([t for t in filtered_todos if not t.completed])
            total_count = len(filtered_todos)
            
            status = "🎯 CURRENT" if ctx == current else ""
            
            table.add_row(
                ctx,
                status,
                str(active_count),
                str(total_count)
            )
        
        get_console().print(table)
    else:
        # Simple list format
        get_console().print("[bold blue]📋 Available Contexts:[/bold blue]")
        for ctx in all_contexts:
            if ctx == current:
                get_console().print(f"  🎯 [bold green]{ctx}[/bold green] [italic](current)[/italic]")
            else:
                get_console().print(f"  • [cyan]{ctx}[/cyan]")


@context.command(name="set")
@click.argument("context_name")
def set_context(context_name: str):
    """Set the active context."""
    # Validate context exists (except for 'all')
    if context_name != 'all':
        contexts = get_all_contexts()
        if context_name not in contexts:
            get_console().print(f"[yellow]⚠️  Context '{context_name}' not found in existing todos.[/yellow]")
            get_console().print(f"[muted]Creating new context '{context_name}'. Add todos with @{context_name} to populate it.[/muted]")
    
    set_current_context(context_name)
    get_console().print(f"[green]✅ Switched to context: [bold]{context_name}[/bold][/green]")
    
    # Show some stats about this context
    if context_name != 'all':
        storage = get_storage()
        config = get_config()
        all_todos = []
        
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
        
        for proj_name in projects:
            proj, todos = storage.load_project(proj_name)
            if todos:
                all_todos.extend(todos)
        
        filtered_todos = filter_todos_by_context(all_todos, context_name)
        active_count = len([t for t in filtered_todos if not t.completed])
        
        if filtered_todos:
            get_console().print(f"[muted]Found {len(filtered_todos)} todos ({active_count} active) in this context[/muted]")


@context.command(name="current")
def show_current_context():
    """Show the current active context."""
    current = get_current_context()
    get_console().print(f"[bold blue]Current context:[/bold blue] [green]{current}[/green]")


@context.command(name="add")
@click.argument("todo_id", type=int)
@click.argument("context_name")
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def add_context_to_todo(todo_id: int, context_name: str, project: str):
    """Add a context to an existing todo."""
    storage = get_storage()
    config = get_config()
    
    # Find the todo
    found_todo = None
    found_project = None
    found_todos = None
    
    if project:
        projects = [project]
    else:
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
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    # Add context if not already present
    if context_name in found_todo.context:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} already has context '{context_name}'[/yellow]")
        return
    
    found_todo.context.append(context_name)
    
    # Save project
    if storage.save_project(found_project, found_todos):
        get_console().print(f"[green]✅ Added context '{context_name}' to todo {todo_id}: {found_todo.text}[/green]")
    else:
        get_console().print("[red]❌ Failed to save changes[/red]")
        sys.exit(1)


@context.command(name="remove")
@click.argument("todo_id", type=int)
@click.argument("context_name")
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def remove_context_from_todo(todo_id: int, context_name: str, project: str):
    """Remove a context from an existing todo."""
    storage = get_storage()
    config = get_config()
    
    # Find the todo
    found_todo = None
    found_project = None
    found_todos = None
    
    if project:
        projects = [project]
    else:
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
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    # Remove context if present
    if context_name not in found_todo.context:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} does not have context '{context_name}'[/yellow]")
        return
    
    found_todo.context.remove(context_name)
    
    # Save project
    if storage.save_project(found_project, found_todos):
        get_console().print(f"[green]✅ Removed context '{context_name}' from todo {todo_id}: {found_todo.text}[/green]")
    else:
        get_console().print("[red]❌ Failed to save changes[/red]")
        sys.exit(1)


@context.command(name="view")
@click.argument("context_name", required=False)
@click.option("--limit", "-l", type=int, default=20, help="Limit number of results")
@click.option("--status", type=click.Choice(['pending', 'in_progress', 'completed', 'cancelled', 'blocked']), 
              help="Filter by status")
def view_context(context_name: str, limit: int, status: str):
    """View todos in a specific context (or current context if not specified)."""
    if not context_name:
        context_name = get_current_context()
    
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
        get_console().print("[yellow]No todos found.[/yellow]")
        return
    
    # Filter by context
    filtered_todos = filter_todos_by_context(all_todos, context_name)
    
    # Filter by status if specified
    if status:
        from ..domain import TodoStatus
        filtered_todos = [t for t in filtered_todos if t.status == TodoStatus(status)]
    
    if not filtered_todos:
        get_console().print(f"[yellow]No todos found in context '{context_name}'[/yellow]")
        return
    
    # Sort by priority and due date
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    
    def sort_key(todo):
        from ..utils.datetime import ensure_aware, max_utc
        return (
            not todo.pinned,  # Pinned first
            todo.completed,   # Active todos first
            priority_order.get(todo.priority, 2),
            ensure_aware(todo.due_date) if todo.due_date else max_utc(),
            todo.id
        )
    
    filtered_todos.sort(key=sort_key)
    
    # Limit results
    if limit:
        filtered_todos = filtered_todos[:limit]
    
    # Display header
    context_display = f"[bold blue]📋 Context: {context_name}[/bold blue]"
    if context_name == get_current_context():
        context_display += " [italic green](current)[/italic green]"
    
    get_console().print(f"\n{context_display}")
    get_console().print(f"[muted]Showing {len(filtered_todos)} todos[/muted]\n")
    
    # Display todos
    from .tasks import format_todo_for_display
    for todo in filtered_todos:
        get_console().print(f"  {format_todo_for_display(todo)}")


def get_context_commands():
    """Get the context command group."""
    return context