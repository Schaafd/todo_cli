"""Task dependency management CLI commands."""

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


def find_todo_by_id(todo_id: int, project: str = None) -> tuple[Todo, str, List[Todo]] | None:
    """Find a todo by ID across projects. Returns (todo, project_name, all_project_todos) or None."""
    storage = get_storage()
    config = get_config()
    
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
                return todo, proj_name, todos
    
    return None


def validate_dependencies(todo: Todo, all_todos: List[Todo]) -> tuple[bool, List[str]]:
    """Validate a todo's dependencies. Returns (is_valid, error_messages)."""
    errors = []
    
    # Check if dependencies exist
    todo_ids = {t.id for t in all_todos}
    for dep_id in todo.depends_on:
        if dep_id not in todo_ids:
            errors.append(f"Dependency todo ID {dep_id} does not exist")
    
    # Check for circular dependencies
    def has_circular_dependency(current_id: int, target_id: int, visited: Set[int]) -> bool:
        if current_id in visited:
            return True
        if current_id == target_id:
            return True
        
        visited.add(current_id)
        current_todo = next((t for t in all_todos if t.id == current_id), None)
        if not current_todo:
            return False
        
        for dep_id in current_todo.depends_on:
            if has_circular_dependency(dep_id, target_id, visited.copy()):
                return True
        
        return False
    
    for dep_id in todo.depends_on:
        if has_circular_dependency(dep_id, todo.id, set()):
            errors.append(f"Circular dependency detected with todo ID {dep_id}")
    
    return len(errors) == 0, errors


def is_blocked(todo: Todo, all_todos: List[Todo]) -> bool:
    """Check if a todo is blocked by incomplete dependencies."""
    if not todo.depends_on:
        return False
    
    for dep_id in todo.depends_on:
        dep_todo = next((t for t in all_todos if t.id == dep_id), None)
        if dep_todo and not dep_todo.completed:
            return True
    
    return False


@click.group(name="dep")
def dependencies():
    """Manage task dependencies."""
    pass


@dependencies.command(name="add")
@click.argument("todo_id", type=int)
@click.argument("depends_on_id", type=int)
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def add_dependency(todo_id: int, depends_on_id: int, project: str):
    """Add a dependency relationship. TODO_ID depends on DEPENDS_ON_ID."""
    
    if todo_id == depends_on_id:
        get_console().print("[red]❌ A todo cannot depend on itself[/red]")
        sys.exit(1)
    
    # Find the main todo
    result = find_todo_by_id(todo_id, project)
    if not result:
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    todo, proj_name, todos = result
    
    # Check if dependency todo exists
    dep_result = find_todo_by_id(depends_on_id)
    if not dep_result:
        get_console().print(f"[red]❌ Dependency todo with ID {depends_on_id} not found[/red]")
        sys.exit(1)
    
    dep_todo, dep_proj_name, dep_todos = dep_result
    
    # Check if dependency already exists
    if depends_on_id in todo.depends_on:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} already depends on {depends_on_id}[/yellow]")
        return
    
    # Add dependency
    todo.depends_on.append(depends_on_id)
    
    # Add reverse relationship (blocks)
    if todo_id not in dep_todo.blocks:
        dep_todo.blocks.append(todo_id)
    
    # Validate dependencies
    all_todos = []
    storage = get_storage()
    config = get_config()
    
    for proj in storage.list_projects() or [config.default_project]:
        _, project_todos = storage.load_project(proj)
        all_todos.extend(project_todos)
    
    is_valid, errors = validate_dependencies(todo, all_todos)
    if not is_valid:
        # Rollback changes
        todo.depends_on.remove(depends_on_id)
        if todo_id in dep_todo.blocks:
            dep_todo.blocks.remove(todo_id)
        
        get_console().print("[red]❌ Cannot add dependency:[/red]")
        for error in errors:
            get_console().print(f"  [red]• {error}[/red]")
        sys.exit(1)
    
    # Save both projects
    storage = get_storage()
    
    # Save main todo's project
    main_proj, _ = storage.load_project(proj_name)
    if not storage.save_project(main_proj, todos):
        get_console().print("[red]❌ Failed to save main todo's project[/red]")
        sys.exit(1)
    
    # Save dependency todo's project if different
    if dep_proj_name != proj_name:
        dep_proj, _ = storage.load_project(dep_proj_name)
        if not storage.save_project(dep_proj, dep_todos):
            get_console().print("[red]❌ Failed to save dependency todo's project[/red]")
            sys.exit(1)
    
    get_console().print(
        f"[green]✅ Added dependency: Todo {todo_id} '{todo.text}' now depends on {depends_on_id} '{dep_todo.text}'[/green]"
    )


@dependencies.command(name="remove")
@click.argument("todo_id", type=int)
@click.argument("depends_on_id", type=int)
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def remove_dependency(todo_id: int, depends_on_id: int, project: str):
    """Remove a dependency relationship."""
    
    # Find the main todo
    result = find_todo_by_id(todo_id, project)
    if not result:
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    todo, proj_name, todos = result
    
    # Check if dependency exists
    if depends_on_id not in todo.depends_on:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} does not depend on {depends_on_id}[/yellow]")
        return
    
    # Find the dependency todo to update its blocks
    dep_result = find_todo_by_id(depends_on_id)
    if dep_result:
        dep_todo, dep_proj_name, dep_todos = dep_result
        if todo_id in dep_todo.blocks:
            dep_todo.blocks.remove(todo_id)
        
        # Save dependency todo's project if different
        if dep_proj_name != proj_name:
            storage = get_storage()
            dep_proj, _ = storage.load_project(dep_proj_name)
            storage.save_project(dep_proj, dep_todos)
    
    # Remove dependency
    todo.depends_on.remove(depends_on_id)
    
    # Save main todo's project
    storage = get_storage()
    main_proj, _ = storage.load_project(proj_name)
    if storage.save_project(main_proj, todos):
        get_console().print(f"[green]✅ Removed dependency: Todo {todo_id} no longer depends on {depends_on_id}[/green]")
    else:
        get_console().print("[red]❌ Failed to save changes[/red]")
        sys.exit(1)


@dependencies.command(name="list")
@click.option("--project", "-p", help="Filter by project")
@click.option("--todo-id", "-t", type=int, help="Show dependencies for specific todo")
@click.option("--blocked-only", is_flag=True, help="Show only blocked todos")
def list_dependencies(project: str, todo_id: int, blocked_only: bool):
    """List task dependencies."""
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
    
    # Filter by specific todo if requested
    if todo_id:
        all_todos = [(todo, proj) for todo, proj in all_todos if todo.id == todo_id]
        if not all_todos:
            get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
            sys.exit(1)
    
    # Filter todos with dependencies or blocks
    todos_with_deps = []
    for todo, proj_name in all_todos:
        if todo.depends_on or todo.blocks:
            if blocked_only and not is_blocked(todo, [t for t, _ in all_todos]):
                continue
            todos_with_deps.append((todo, proj_name))
    
    if not todos_with_deps:
        if blocked_only:
            get_console().print("[green]✅ No blocked todos found.[/green]")
        else:
            get_console().print("[muted]No todos have dependencies.[/muted]")
        return
    
    # Create dependency table
    table = Table(title="📋 Task Dependencies", show_header=True, header_style="bold blue")
    table.add_column("ID", style="cyan", min_width=4)
    table.add_column("Task", style="white", min_width=25)
    table.add_column("Status", min_width=8)
    table.add_column("Depends On", style="yellow", min_width=12)
    table.add_column("Blocks", style="red", min_width=12)
    table.add_column("Blocked", style="magenta", min_width=8)
    table.add_column("Project", style="blue", min_width=8)
    
    flat_todos = [t for t, _ in all_todos]
    
    for todo, proj_name in todos_with_deps:
        # Status with emoji
        status_emoji = {
            TodoStatus.PENDING: "⏳",
            TodoStatus.IN_PROGRESS: "🔄",
            TodoStatus.COMPLETED: "✅",
            TodoStatus.CANCELLED: "❌",
            TodoStatus.BLOCKED: "🚫"
        }.get(todo.status, "❓")
        
        # Dependencies
        deps_str = ", ".join(str(dep_id) for dep_id in todo.depends_on) if todo.depends_on else "-"
        
        # What this blocks
        blocks_str = ", ".join(str(block_id) for block_id in todo.blocks) if todo.blocks else "-"
        
        # Is blocked?
        blocked = "🚫 YES" if is_blocked(todo, flat_todos) else "✅ No"
        
        # Truncate long text
        text = todo.text[:30] + "..." if len(todo.text) > 30 else todo.text
        
        table.add_row(
            str(todo.id),
            text,
            f"{status_emoji} {todo.status.value.title()}",
            deps_str,
            blocks_str,
            blocked,
            proj_name
        )
    
    get_console().print(table)


@dependencies.command(name="check")
@click.option("--project", "-p", help="Check specific project only")
def check_dependencies(project: str):
    """Check for dependency issues across all todos."""
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
            all_todos.extend(todos)
    
    if not all_todos:
        get_console().print("[yellow]No todos found.[/yellow]")
        return
    
    # Check for issues
    issues = []
    todo_ids = {todo.id for todo in all_todos}
    
    for todo in all_todos:
        # Check for non-existent dependencies
        for dep_id in todo.depends_on:
            if dep_id not in todo_ids:
                issues.append(f"Todo {todo.id} '{todo.text}' depends on non-existent todo {dep_id}")
        
        # Check for inconsistent reverse relationships
        for dep_id in todo.depends_on:
            dep_todo = next((t for t in all_todos if t.id == dep_id), None)
            if dep_todo and todo.id not in dep_todo.blocks:
                issues.append(f"Inconsistent relationship: Todo {todo.id} depends on {dep_id}, but {dep_id} doesn't list {todo.id} in its blocks")
        
        # Validate dependencies
        is_valid, errors = validate_dependencies(todo, all_todos)
        if not is_valid:
            for error in errors:
                issues.append(f"Todo {todo.id} '{todo.text}': {error}")
    
    # Display results
    if not issues:
        get_console().print("[green]✅ All dependencies are valid![/green]")
    else:
        get_console().print(f"[red]❌ Found {len(issues)} dependency issues:[/red]")
        for i, issue in enumerate(issues, 1):
            get_console().print(f"  {i}. [red]{issue}[/red]")


@dependencies.command(name="unblock")
@click.argument("todo_id", type=int)
@click.option("--project", "-p", help="Project name (searches all if not specified)")
@click.option("--force", is_flag=True, help="Force unblock by completing dependencies")
def unblock_todo(todo_id: int, project: str, force: bool):
    """Show what's blocking a todo or forcefully unblock it."""
    
    result = find_todo_by_id(todo_id, project)
    if not result:
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    todo, proj_name, todos = result
    
    if not todo.depends_on:
        get_console().print(f"[green]✅ Todo {todo_id} has no dependencies[/green]")
        return
    
    storage = get_storage()
    config = get_config()
    
    # Get all todos for checking
    all_todos = []
    for proj in storage.list_projects() or [config.default_project]:
        _, project_todos = storage.load_project(proj)
        all_todos.extend(project_todos)
    
    blocking_deps = []
    for dep_id in todo.depends_on:
        dep_todo = next((t for t in all_todos if t.id == dep_id), None)
        if dep_todo and not dep_todo.completed:
            blocking_deps.append(dep_todo)
    
    if not blocking_deps:
        get_console().print(f"[green]✅ Todo {todo_id} is not blocked (all dependencies completed)[/green]")
        return
    
    # Show blocking dependencies
    get_console().print(f"[yellow]⚠️  Todo {todo_id} '{todo.text}' is blocked by {len(blocking_deps)} incomplete dependencies:[/yellow]")
    
    for dep in blocking_deps:
        status_emoji = {
            TodoStatus.PENDING: "⏳",
            TodoStatus.IN_PROGRESS: "🔄",
            TodoStatus.BLOCKED: "🚫"
        }.get(dep.status, "❓")
        
        get_console().print(f"  • {dep.id}: {status_emoji} '{dep.text}' ({dep.status.value})")
    
    if force:
        get_console().print("\n[bold red]⚠️  Force completing blocking dependencies...[/bold red]")
        
        # Mark all blocking dependencies as completed
        changes_made = []
        for dep in blocking_deps:
            dep.complete()
            changes_made.append((dep, dep.project))
        
        # Save all affected projects
        projects_to_save = set()
        for dep, dep_proj in changes_made:
            projects_to_save.add(dep_proj)
        
        for proj_name in projects_to_save:
            proj, project_todos = storage.load_project(proj_name)
            storage.save_project(proj, project_todos)
        
        get_console().print(f"[green]✅ Force completed {len(blocking_deps)} dependencies. Todo {todo_id} is now unblocked.[/green]")
    else:
        get_console().print("\n[muted]Use --force to automatically complete blocking dependencies[/muted]")


def get_dependencies_commands():
    """Get the dependencies command group."""
    return dependencies