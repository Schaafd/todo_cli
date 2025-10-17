"""Enhanced tag management CLI commands."""

import sys
from typing import List, Set, Dict
import click
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from collections import defaultdict

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


def get_all_tags() -> Dict[str, int]:
    """Get all available tags with their usage counts."""
    storage = get_storage()
    config = get_config()
    tag_counts = defaultdict(int)
    
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            for todo in todos:
                for tag in todo.tags:
                    tag_counts[tag] += 1
    
    return dict(tag_counts)


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


def filter_todos_by_tags(todos: List[Todo], tags: List[str], match_all: bool = False) -> List[Todo]:
    """Filter todos by tags. match_all=True requires all tags, False requires any tag."""
    if not tags:
        return todos
    
    filtered = []
    for todo in todos:
        if match_all:
            # Must have all specified tags
            if all(tag in todo.tags for tag in tags):
                filtered.append(todo)
        else:
            # Must have at least one specified tag
            if any(tag in todo.tags for tag in tags):
                filtered.append(todo)
    
    return filtered


@click.group(name="tag")
def tags():
    """Manage todo tags."""
    pass


@tags.command(name="list")
@click.option("--show-counts", is_flag=True, help="Show usage counts per tag")
@click.option("--sort-by-count", is_flag=True, help="Sort by usage count (most used first)")
def list_tags(show_counts: bool, sort_by_count: bool):
    """List all available tags."""
    tag_counts = get_all_tags()
    
    if not tag_counts:
        get_console().print("[yellow]No tags found. Add tags to your todos with 'todo add \"task text #tag\"'[/yellow]")
        return
    
    # Sort tags
    if sort_by_count:
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    else:
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[0])
    
    if show_counts:
        # Create table with counts
        table = Table(title="🏷️ Available Tags", show_header=True, header_style="bold blue")
        table.add_column("Tag", style="cyan", min_width=15)
        table.add_column("Usage Count", style="yellow", min_width=12)
        table.add_column("Visual", style="white", min_width=10)
        
        for tag, count in sorted_tags:
            # Create a visual indicator based on usage
            if count >= 10:
                visual = "🔥 High"
            elif count >= 5:
                visual = "⭐ Medium"
            elif count >= 2:
                visual = "📌 Low"
            else:
                visual = "💫 Rare"
            
            table.add_row(tag, str(count), visual)
        
        get_console().print(table)
    else:
        # Simple list format
        get_console().print("[bold blue]🏷️ Available Tags:[/bold blue]")
        for tag, count in sorted_tags:
            get_console().print(f"  • [cyan]#{tag}[/cyan]")


@tags.command(name="add")
@click.argument("todo_id", type=int)
@click.argument("tag_name")
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def add_tag(todo_id: int, tag_name: str, project: str):
    """Add a tag to an existing todo."""
    # Clean tag name (remove # if present)
    tag_name = tag_name.lstrip('#')
    
    result = find_todo_by_id(todo_id, project)
    if not result:
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    todo, proj_name, todos = result
    
    # Check if tag already exists
    if tag_name in todo.tags:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} already has tag '{tag_name}'[/yellow]")
        return
    
    # Add tag
    todo.tags.append(tag_name)
    
    # Save project
    storage = get_storage()
    proj, _ = storage.load_project(proj_name)
    if storage.save_project(proj, todos):
        get_console().print(f"[green]✅ Added tag '#{tag_name}' to todo {todo_id}: {todo.text}[/green]")
    else:
        get_console().print("[red]❌ Failed to save changes[/red]")
        sys.exit(1)


@tags.command(name="remove")
@click.argument("todo_id", type=int)
@click.argument("tag_name")
@click.option("--project", "-p", help="Project name (searches all if not specified)")
def remove_tag(todo_id: int, tag_name: str, project: str):
    """Remove a tag from an existing todo."""
    # Clean tag name (remove # if present)
    tag_name = tag_name.lstrip('#')
    
    result = find_todo_by_id(todo_id, project)
    if not result:
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    todo, proj_name, todos = result
    
    # Check if tag exists
    if tag_name not in todo.tags:
        get_console().print(f"[yellow]⚠️  Todo {todo_id} does not have tag '{tag_name}'[/yellow]")
        return
    
    # Remove tag
    todo.tags.remove(tag_name)
    
    # Save project
    storage = get_storage()
    proj, _ = storage.load_project(proj_name)
    if storage.save_project(proj, todos):
        get_console().print(f"[green]✅ Removed tag '#{tag_name}' from todo {todo_id}: {todo.text}[/green]")
    else:
        get_console().print("[red]❌ Failed to save changes[/red]")
        sys.exit(1)


@tags.command(name="find")
@click.argument("tag_names", nargs=-1, required=True)
@click.option("--project", "-p", help="Filter by project")
@click.option("--all-tags", is_flag=True, help="Require all specified tags (default: any tag)")
@click.option("--status", type=click.Choice(['pending', 'in_progress', 'completed', 'cancelled', 'blocked']), 
              help="Filter by status")
@click.option("--limit", "-l", type=int, default=50, help="Limit number of results")
def find_by_tags(tag_names: tuple, project: str, all_tags: bool, status: str, limit: int):
    """Find todos by tags. Specify multiple tags to find todos with any or all tags."""
    # Clean tag names (remove # if present)
    clean_tags = [tag.lstrip('#') for tag in tag_names]
    
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
    
    # Filter by tags
    flat_todos = [todo for todo, _ in all_todos]
    filtered_todos = filter_todos_by_tags(flat_todos, clean_tags, match_all=all_tags)
    
    # Rebuild the (todo, project) tuples for filtered results
    filtered_with_projects = [(todo, proj) for todo, proj in all_todos if todo in filtered_todos]
    
    # Filter by status if specified
    if status:
        filtered_with_projects = [(todo, proj) for todo, proj in filtered_with_projects 
                                if todo.status == TodoStatus(status)]
    
    if not filtered_with_projects:
        tag_display = " AND ".join(f"#{tag}" for tag in clean_tags) if all_tags else " OR ".join(f"#{tag}" for tag in clean_tags)
        get_console().print(f"[yellow]No todos found with tags: {tag_display}[/yellow]")
        return
    
    # Sort by priority and due date
    priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
    
    def sort_key(todo_proj_tuple):
        todo, _ = todo_proj_tuple
        from ..utils.datetime import ensure_aware, max_utc
        return (
            not todo.pinned,  # Pinned first
            todo.completed,   # Active todos first
            priority_order.get(todo.priority, 2),
            ensure_aware(todo.due_date) if todo.due_date else max_utc(),
            todo.id
        )
    
    filtered_with_projects.sort(key=sort_key)
    
    # Limit results
    if limit:
        filtered_with_projects = filtered_with_projects[:limit]
    
    # Display header
    tag_display = " AND ".join(f"#{tag}" for tag in clean_tags) if all_tags else " OR ".join(f"#{tag}" for tag in clean_tags)
    match_type = "all" if all_tags else "any"
    
    get_console().print(f"\n[bold blue]🔍 Todos with {match_type} of: {tag_display}[/bold blue]")
    get_console().print(f"[muted]Found {len(filtered_with_projects)} todos[/muted]\n")
    
    # Display todos
    from .tasks import format_todo_for_display
    for todo, proj_name in filtered_with_projects:
        proj_info = f" [dim]({proj_name})[/dim]" if project is None else ""
        get_console().print(f"  {format_todo_for_display(todo)}{proj_info}")


@tags.command(name="rename")
@click.argument("old_tag")
@click.argument("new_tag")
@click.option("--project", "-p", help="Rename only in specific project")
@click.option("--dry-run", is_flag=True, help="Show what would be renamed without making changes")
def rename_tag(old_tag: str, new_tag: str, project: str, dry_run: bool):
    """Rename a tag across all todos."""
    # Clean tag names (remove # if present)
    old_tag = old_tag.lstrip('#')
    new_tag = new_tag.lstrip('#')
    
    storage = get_storage()
    config = get_config()
    
    # Get all todos
    changes = []
    
    if project:
        projects = [project]
    else:
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            for todo in todos:
                if old_tag in todo.tags:
                    changes.append((todo, proj_name, proj, todos))
    
    if not changes:
        get_console().print(f"[yellow]No todos found with tag '#{old_tag}'[/yellow]")
        return
    
    get_console().print(f"[bold blue]Found {len(changes)} todos with tag '#{old_tag}'[/bold blue]")
    
    if dry_run:
        get_console().print(f"[yellow]DRY RUN: Would rename '#{old_tag}' to '#{new_tag}' in:[/yellow]")
        for todo, proj_name, _, _ in changes:
            get_console().print(f"  • {todo.id}: {todo.text} ({proj_name})")
        return
    
    # Perform the rename
    projects_to_save = {}
    
    for todo, proj_name, proj, todos in changes:
        # Replace the tag
        todo.tags = [new_tag if tag == old_tag else tag for tag in todo.tags]
        
        # Group by project for batch saving
        if proj_name not in projects_to_save:
            projects_to_save[proj_name] = (proj, todos)
    
    # Save all affected projects
    success_count = 0
    for proj_name, (proj, todos) in projects_to_save.items():
        if storage.save_project(proj, todos):
            success_count += 1
        else:
            get_console().print(f"[red]❌ Failed to save project '{proj_name}'[/red]")
    
    if success_count == len(projects_to_save):
        get_console().print(f"[green]✅ Successfully renamed tag '#{old_tag}' to '#{new_tag}' in {len(changes)} todos[/green]")
    else:
        get_console().print(f"[yellow]⚠️  Partial success: saved {success_count}/{len(projects_to_save)} projects[/yellow]")


@tags.command(name="clean")
@click.option("--unused-only", is_flag=True, help="Remove only tags that are not used by any todos")
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without making changes")
@click.option("--project", "-p", help="Clean tags only in specific project")
def clean_tags(unused_only: bool, dry_run: bool, project: str):
    """Clean up duplicate or unused tags."""
    storage = get_storage()
    config = get_config()
    
    changes = []
    tag_stats = defaultdict(int)
    
    if project:
        projects = [project]
    else:
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
    
    # Analyze all todos
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            for todo in todos:
                original_tags = todo.tags.copy()
                
                # Remove duplicates while preserving order
                cleaned_tags = []
                seen = set()
                for tag in todo.tags:
                    if tag not in seen:
                        cleaned_tags.append(tag)
                        seen.add(tag)
                        tag_stats[tag] += 1
                    else:
                        get_console().print(f"[yellow]Found duplicate tag '#{tag}' in todo {todo.id}[/yellow]")
                
                # Check if we need to update this todo
                if cleaned_tags != original_tags:
                    changes.append((todo, proj_name, proj, todos, original_tags, cleaned_tags))
    
    if unused_only:
        # For this command, we're only removing duplicates, not unused tags
        # (unused tags would require deleting them from todos, which is covered by duplicate removal)
        pass
    
    if not changes:
        get_console().print("[green]✅ No tag cleanup needed[/green]")
        return
    
    get_console().print(f"[bold blue]Found {len(changes)} todos with tag issues[/bold blue]")
    
    if dry_run:
        get_console().print("[yellow]DRY RUN: Would clean up:[/yellow]")
        for todo, proj_name, _, _, original, cleaned in changes:
            removed = set(original) - set(cleaned)
            get_console().print(f"  • Todo {todo.id}: Remove duplicates of {removed} ({proj_name})")
        return
    
    # Perform cleanup
    projects_to_save = {}
    
    for todo, proj_name, proj, todos, original, cleaned in changes:
        todo.tags = cleaned
        
        # Group by project for batch saving
        if proj_name not in projects_to_save:
            projects_to_save[proj_name] = (proj, todos)
    
    # Save all affected projects
    success_count = 0
    for proj_name, (proj, todos) in projects_to_save.items():
        if storage.save_project(proj, todos):
            success_count += 1
        else:
            get_console().print(f"[red]❌ Failed to save project '{proj_name}'[/red]")
    
    if success_count == len(projects_to_save):
        get_console().print(f"[green]✅ Successfully cleaned up tags in {len(changes)} todos[/green]")
    else:
        get_console().print(f"[yellow]⚠️  Partial success: saved {success_count}/{len(projects_to_save)} projects[/yellow]")


@tags.command(name="stats")
@click.option("--project", "-p", help="Show stats for specific project only")
def tag_stats(project: str):
    """Show tag usage statistics."""
    storage = get_storage()
    config = get_config()
    
    tag_counts = defaultdict(int)
    todo_with_tags = 0
    total_todos = 0
    
    if project:
        projects = [project]
    else:
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            for todo in todos:
                total_todos += 1
                if todo.tags:
                    todo_with_tags += 1
                    for tag in todo.tags:
                        tag_counts[tag] += 1
    
    if not tag_counts:
        get_console().print("[yellow]No tags found.[/yellow]")
        return
    
    # Calculate statistics
    total_tags = len(tag_counts)
    total_tag_usages = sum(tag_counts.values())
    avg_tags_per_todo = total_tag_usages / total_todos if total_todos > 0 else 0
    tagged_percentage = (todo_with_tags / total_todos * 100) if total_todos > 0 else 0
    
    # Create stats panel
    stats_content = f"""[bold cyan]📊 Tag Statistics[/bold cyan]

[bold]Overall:[/bold]
• Total unique tags: [cyan]{total_tags}[/cyan]
• Total tag usages: [yellow]{total_tag_usages}[/yellow]
• Todos with tags: [green]{todo_with_tags}/{total_todos}[/green] ([bold]{tagged_percentage:.1f}%[/bold])
• Average tags per todo: [blue]{avg_tags_per_todo:.1f}[/blue]

[bold]Most Used Tags:[/bold]"""
    
    # Add top 10 most used tags
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    for i, (tag, count) in enumerate(top_tags, 1):
        percentage = (count / total_tag_usages * 100)
        stats_content += f"\n{i:2d}. [cyan]#{tag}[/cyan]: [yellow]{count}[/yellow] uses ([bold]{percentage:.1f}%[/bold])"
    
    panel = Panel(stats_content, title="🏷️ Tag Analytics", border_style="blue")
    get_console().print(panel)


def get_tags_commands():
    """Get the tags command group."""
    return tags