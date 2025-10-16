"""New clean command-line interface for Todo CLI."""

import sys
from typing import Optional
from datetime import datetime, timedelta
import click
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from ..utils.datetime import ensure_aware, max_utc

from ..config import get_config, load_config
from ..storage import Storage
from ..domain import (
    Todo,
    TodoStatus,
    Priority,
    Project,
    parse_task_input,
    TaskBuilder,
    ParseError,
    RecurringTaskManager,
    RecurrenceParser,
    create_recurring_task_from_text,
)
from ..theme import (
    get_themed_console, 
    show_startup_banner, 
    show_quick_help,
    get_priority_style,
    get_status_emoji,
    PRODUCTIVITY_NINJA_THEME
)
from ..services import (
    QueryEngine,
    TaskRecommendationEngine,
    get_context_suggestions,
    get_energy_suggestions,
    ExportManager,
    ExportFormat,
    NotificationManager,
    NotificationType,
    NotificationPreferences,
)
from ..sync.calendar_integration import CalendarSync, CalendarConfig, CalendarType, SyncDirection, ConflictResolution
from ..sync import SyncManager, SyncConfig, SyncProvider, ConflictStrategy, SyncStatus
from .analytics_commands import get_analytics_commands


# Dynamic console - no longer created at module level
def get_console():
    """Get a themed console that reflects current configuration."""
    return get_themed_console()

query_engine = QueryEngine()
recommend_engine = TaskRecommendationEngine()
recurring_manager = RecurringTaskManager()


def get_storage() -> Storage:
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


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


@click.group()
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.pass_context
def cli(ctx, config, verbose):
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
        get_console().print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


@cli.command()
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
    try:
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
            get_console().print("[bold yellow]⚠️  Parsing Issues:[/bold yellow]")
            for error in errors:
                if error.severity == "error":
                    get_console().print(f"  [red]❌ {error.message}[/red]")
                    for suggestion in error.suggestions:
                        get_console().print(f"     [blue]💡 {suggestion}[/blue]")
                elif error.severity == "warning":
                    get_console().print(f"  [yellow]⚠️  {error.message}[/yellow]")
            
            # Don't proceed if there are blocking errors
            if any(e.severity == "error" for e in errors):
                sys.exit(1)
        
        # Show suggestions if requested
        if suggest or suggestions:
            if suggestions:
                get_console().print("[bold blue]💡 Suggestions:[/bold blue]")
                for suggestion in suggestions:
                    get_console().print(f"  [blue]{suggestion}[/blue]")
            
            if suggest:
                return
        
        # Get next todo ID for the project
        target_project = parsed.project or project or config.default_project
        todo_id = storage.get_next_todo_id(target_project)
        
        # Build todo with our enhanced data
        builder = TaskBuilder(config)
        todo = builder.build(parsed, todo_id)
        
        # Show preview
        get_console().print("[bold green]📋 Task Preview:[/bold green]")
        preview_text = format_todo_for_display(todo, show_id=True)
        get_console().print(f"  {preview_text}")
        
        # Show additional details that aren't in the standard format
        if todo.context:
            get_console().print(f"  [dim]Context: {', '.join('@' + ctx for ctx in todo.context)}[/dim]")
        if todo.effort:
            get_console().print(f"  [dim]Effort: *{todo.effort}[/dim]")
        if todo.energy_level != "medium":
            get_console().print(f"  [dim]Energy: {todo.energy_level}[/dim]")
        if todo.time_estimate:
            hours = todo.time_estimate // 60
            minutes = todo.time_estimate % 60
            if hours > 0:
                get_console().print(f"  [dim]Estimate: {hours}h {minutes}m[/dim]")
            else:
                get_console().print(f"  [dim]Estimate: {minutes}m[/dim]")
        if todo.waiting_for:
            get_console().print(f"  [dim]Waiting for: {', '.join(todo.waiting_for)}[/dim]")
        if todo.url:
            get_console().print(f"  [dim]URL: {todo.url}[/dim]")
        
        if dry_run:
            get_console().print("[yellow]🔍 Dry run - not saved[/yellow]")
            return
        
        # Load project and todos
        proj, todos = storage.load_project(target_project)
        if not proj:
            proj = Project(name=target_project)
        
        todos.append(todo)
        
        # Save project
        if storage.save_project(proj, todos):
            get_console().print(f"[success]✅ Added task {todo_id} to {target_project}[/success]")
        else:
            get_console().print(f"[error]❌ Failed to add task[/error]")
            sys.exit(1)
        
    except Exception as e:
        get_console().print(f"[red]Error: {e}[/red]")
        sys.exit(1)


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
    get_console().print(Panel.fit("[header]📋 Todo Dashboard[/header]", border_style="border"))
    
    # Track if we've printed any sections for spacing
    sections_printed = 0
    
    if pinned_todos:
        if sections_printed > 0:
            get_console().print()  # Extra space between sections
        
        # Create bordered panel for pinned tasks
        content_lines = []
        for todo in pinned_todos[:5]:
            content_lines.append(format_todo_for_display(todo, show_id=True))
        if len(pinned_todos) > 5:
            content_lines.append(f"[muted]... and {len(pinned_todos) - 5} more[/muted]")
        
        panel = Panel(
            "\n".join(content_lines),
            title="[todo_pinned]⭐ Pinned Tasks[/todo_pinned]",
            border_style="pinned_border",
            style="pinned_bg"
        )
        get_console().print(panel)
        sections_printed += 1
    
    if overdue_todos:
        if sections_printed > 0:
            get_console().print()  # Extra space between sections
        
        # Create bordered panel for overdue tasks
        content_lines = []
        for todo in overdue_todos[:5]:
            content_lines.append(format_todo_for_display(todo, show_id=True))
        if len(overdue_todos) > 5:
            content_lines.append(f"[muted]... and {len(overdue_todos) - 5} more[/muted]")
        
        panel = Panel(
            "\n".join(content_lines),
            title="[critical]🔥 Overdue Tasks[/critical]",
            border_style="overdue_border",
            style="overdue_bg"
        )
        get_console().print(panel)
        sections_printed += 1
    
    if today_todos:
        if sections_printed > 0:
            get_console().print()  # Extra space between sections
        
        # Create bordered panel for today's tasks
        content_lines = []
        for todo in today_todos[:5]:
            content_lines.append(format_todo_for_display(todo, show_id=True))
        
        panel = Panel(
            "\n".join(content_lines),
            title="[success]📅 Due Today[/success]",
            border_style="today_border",
            style="today_bg"
        )
        get_console().print(panel)
        sections_printed += 1
    
    if upcoming_todos:
        if sections_printed > 0:
            get_console().print()  # Extra space between sections
        
        # Create bordered panel for upcoming tasks
        content_lines = []
        for todo in upcoming_todos[:5]:
            content_lines.append(format_todo_for_display(todo, show_id=True))
        
        panel = Panel(
            "\n".join(content_lines),
            title="[primary]📆 Due This Week[/primary]",
            border_style="upcoming_border",
            style="upcoming_bg"
        )
        get_console().print(panel)
        sections_printed += 1
    
    # Summary stats
    total_todos = len(all_todos)
    completed_todos = sum(1 for t in all_todos if t.completed)
    active_todos = sum(1 for t in all_todos if t.is_active())
    
    # Check and send notifications silently
    try:
        notification_manager = NotificationManager()
        notification_manager.check_and_send_notifications(all_todos)
    except Exception:
        # Silently ignore notification failures
        pass
    
    if sections_printed > 0:
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
@click.option("--project", "-p", help="Filter by project")
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
        get_console().print("[yellow]No todos found.[/yellow]")
        return
    
    # Apply filters
    filtered_todos = all_todos
    
    if status:
        filtered_todos = [t for t in filtered_todos if t.status == TodoStatus(status)]
    
    if filter_priority:
        filtered_todos = [t for t in filtered_todos if t.priority == Priority(filter_priority)]
    
    if overdue:
        filtered_todos = [t for t in filtered_todos if t.is_overdue()]
    
    if pinned:
        filtered_todos = [t for t in filtered_todos if t.pinned]
    
    # If any filters are applied, use the old display format
    if status or filter_priority or overdue or pinned:
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
            get_console().print(f"[bold]Found {len(filtered_todos)} todos:[/bold]")
            for todo in filtered_todos:
                get_console().print(format_todo_for_display(todo))
        else:
            get_console().print("[yellow]No todos match the specified filters.[/yellow]")
    else:
        # Use organized date view when no filters are applied
        views = organize_todos_by_date(filtered_todos, sort_by_priority=priority_sort)
        
        # Display each view
        for view_name in ['today', 'tomorrow', 'upcoming', 'backlog']:
            view_todos = views[view_name]
            
            # Apply limit across all views if specified
            if limit and view_todos:
                view_todos = view_todos[:limit]
            
            if view_todos or view_name in ['today', 'tomorrow']:  # Always show today/tomorrow even if empty
                get_console().print(f"\n{get_view_header(view_name, len(view_todos))}")
                
                if view_todos:
                    for todo in view_todos:
                        get_console().print(f"  {format_todo_for_display(todo)}")
                else:
                    get_console().print("  [muted]No tasks[/muted]")


@cli.command()
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
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
        sys.exit(1)
    
    # Mark as completed
    found_todo.complete()
    
    # Save project
    if storage.save_project(found_project, found_todos):
        get_console().print(f"[green]✅ Completed task {todo_id}: {found_todo.text}[/green]")
    else:
        get_console().print(f"[red]❌ Failed to update task[/red]")
        sys.exit(1)


@cli.command()
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
        get_console().print(f"[red]❌ Todo with ID {todo_id} not found[/red]")
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
        get_console().print(f"[green]✅ {action} task {todo_id}: {found_todo.text}[/green]")
    else:
        get_console().print(f"[red]❌ Failed to update task[/red]")
        sys.exit(1)


@cli.command()
@click.argument("query")
@click.option("--project", "-p", help="Limit search to specific project")
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
        results = query_engine.search(all_todos, query)
        
        # Save query if requested
        if save_name:
            query_engine.save_query(save_name, query)
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
@click.option("--context", "-c", help="Current context (e.g., work, home, focus)")
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
    recommendations = recommend_engine.get_recommendations(
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
@click.option("--delete", "delete_name", help="Delete a saved query")
def queries(list_queries, delete_name):
    """Manage saved search queries."""
    if list_queries:
        saved = query_engine.list_saved_queries()
        if saved:
            get_console().print("[bold]Saved Queries:[/bold]")
            for name, query in saved.items():
                get_console().print(f"  [primary]{name}[/primary]: {query}")
                get_console().print(f"    [muted]Usage: todo search @{name}[/muted]")
        else:
            get_console().print("[muted]No saved queries found.[/muted]")
            get_console().print("[muted]Save a query with: todo search 'query' --save name[/muted]")
    elif delete_name:
        if query_engine.delete_query(delete_name):
            get_console().print(f"[success]✅ Deleted saved query '{delete_name}'[/success]")
        else:
            get_console().print(f"[error]❌ Saved query '{delete_name}' not found[/error]")
    else:
        get_console().print("[muted]Use --list to see saved queries or --delete to remove one[/muted]")


@cli.command()
@click.argument("action", type=click.Choice(['complete', 'pin', 'unpin', 'priority', 'project', 'delete']))
@click.argument("ids", nargs=-1, type=int, required=True)
@click.option("--priority", type=click.Choice(['critical', 'high', 'medium', 'low']), help="Priority for priority action")
@click.option("--project", "target_project", help="Target project for project action")
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
    storage = get_storage()
    config = get_config()
    
    if not ids:
        get_console().print("[error]❌ No todo IDs specified[/error]")
        return
    
    # Validate required options for certain actions
    if action == 'priority' and not priority:
        get_console().print("[error]❌ --priority option required for priority action[/error]")
        return
    
    if action == 'project' and not target_project:
        get_console().print("[error]❌ --project option required for project action[/error]")
        return
    
    # Find all todos across all projects
    all_projects = storage.list_projects() or [config.default_project]
    found_todos = []
    project_map = {}  # todo_id -> (project, todos_list)
    
    for proj_name in all_projects:
        proj, todos = storage.load_project(proj_name)
        for todo in todos:
            if todo.id in ids:
                found_todos.append(todo)
                project_map[todo.id] = (proj, todos)
    
    if not found_todos:
        get_console().print(f"[error]❌ None of the specified todos found: {list(ids)}[/error]")
        return
    
    # Show what will be affected
    missing_ids = set(ids) - {t.id for t in found_todos}
    if missing_ids:
        get_console().print(f"[warning]⚠️  Todo IDs not found: {sorted(missing_ids)}[/warning]")
    
    get_console().print(f"\n[primary]Found {len(found_todos)} todos to {action}:[/primary]")
    for todo in found_todos:
        get_console().print(f"  {format_todo_for_display(todo)}")
    
    # Confirm action unless --confirm flag is set
    if not confirm:
        action_descriptions = {
            'complete': 'mark as complete',
            'pin': 'pin',
            'unpin': 'unpin', 
            'priority': f'set priority to {priority}',
            'project': f'move to project {target_project}',
            'delete': 'DELETE permanently'
        }
        description = action_descriptions.get(action, action)
        
        if not click.confirm(f"\nProceed to {description} {len(found_todos)} todos?"):
            get_console().print("[muted]Operation cancelled.[/muted]")
            return
    
    # Perform the bulk action
    success_count = 0
    projects_to_save = set()
    
    for todo in found_todos:
        proj, todos_list = project_map[todo.id]
        
        try:
            if action == 'complete':
                if not todo.completed:
                    todo.complete()
                    success_count += 1
            elif action == 'pin':
                if not todo.pinned:
                    todo.pin()
                    success_count += 1
            elif action == 'unpin':
                if todo.pinned:
                    todo.unpin()
                    success_count += 1
            elif action == 'priority':
                from ..domain import Priority
                todo.priority = Priority(priority)
                success_count += 1
            elif action == 'project':
                # Move to different project
                if todo.project != target_project:
                    # Remove from current project
                    todos_list.remove(todo)
                    projects_to_save.add(proj.name)
                    
                    # Add to target project
                    target_proj, target_todos = storage.load_project(target_project)
                    if not target_proj:
                        from .project import Project
                        target_proj = Project(target_project, target_project)
                        target_todos = []
                    
                    todo.project = target_project
                    target_todos.append(todo)
                    projects_to_save.add(target_project)
                    
                    success_count += 1
            elif action == 'delete':
                todos_list.remove(todo)
                success_count += 1
            
            if action not in ['project', 'delete']:
                projects_to_save.add(proj.name)
                
        except Exception as e:
            get_console().print(f"[error]❌ Failed to {action} todo {todo.id}: {e}[/error]")
    
    # Save all affected projects
    for proj_name in projects_to_save:
        proj, todos = storage.load_project(proj_name)
        if not storage.save_project(proj, todos):
            get_console().print(f"[error]❌ Failed to save project {proj_name}[/error]")
    
    # Show results
    if success_count > 0:
        action_past_tense = {
            'complete': 'completed',
            'pin': 'pinned',
            'unpin': 'unpinned',
            'priority': f'set to {priority} priority',
            'project': f'moved to {target_project}',
            'delete': 'deleted'
        }
        past_tense = action_past_tense.get(action, f'{action}d')
        get_console().print(f"\n[success]✅ Successfully {past_tense} {success_count} todos[/success]")
    else:
        get_console().print(f"\n[warning]⚠️  No todos were modified[/warning]")


@cli.command()
@click.argument("task_text")
@click.argument("pattern")
@click.option("--project", "-p", help="Project for the recurring task")
@click.option("--max-occurrences", type=int, help="Maximum number of occurrences")
@click.option("--end-date", help="End date for recurrence (YYYY-MM-DD)")
@click.option("--preview", is_flag=True, help="Preview next few occurrences without creating")
def recurring(task_text, pattern, project, max_occurrences, end_date, preview):
    """Create a recurring task with smart scheduling.
    
    Examples:
      todo recurring "Team standup @meetings" "daily"
      todo recurring "Review monthly reports ~high" "monthly"
      todo recurring "Backup database @maintenance" "weekly"
      todo recurring "Pay rent +landlord" "monthly" --max-occurrences 12
      todo recurring "Doctor appointment @health" "every 6 months" --preview
    """
    try:
        # Create template and pattern
        template, recurrence_pattern = create_recurring_task_from_text(task_text, pattern)
        
        # Apply command line options
        if project:
            template.project = project
        
        if max_occurrences:
            recurrence_pattern.max_occurrences = max_occurrences
        
        if end_date:
            try:
                recurrence_pattern.end_date = datetime.strptime(end_date, '%Y-%m-%d')
            except ValueError:
                get_console().print(f"[error]❌ Invalid end date format. Use YYYY-MM-DD[/error]")
                return
        
        if preview:
            # Show preview of next few occurrences
            get_console().print(f"\n[primary]📅 Preview of recurring task:[/primary]")
            get_console().print(f"  [bold]{template.text}[/bold]")
            get_console().print(f"  Pattern: {pattern}")
            get_console().print(f"  Project: {template.project}")
            
            # Calculate next few occurrences
            get_console().print(f"\n[primary]Next 5 occurrences:[/primary]")
            current_date = datetime.now()
            
            for i in range(5):
                next_occurrence = recurring_manager.calculate_next_occurrence(current_date, recurrence_pattern)
                if next_occurrence:
                    get_console().print(f"  {i+1}. {next_occurrence.strftime('%Y-%m-%d %H:%M')}")
                    current_date = next_occurrence
                else:
                    break
            
            get_console().print(f"\n[muted]Use without --preview to create the recurring task[/muted]")
            return
        
        # Create the recurring task
        recurring_task = recurring_manager.create_recurring_task(template, recurrence_pattern)
        
        get_console().print(f"\n[success]✅ Created recurring task:[/success]")
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


@cli.command("recurring-list")
def list_recurring():
    """List all recurring tasks."""
    recurring_tasks = recurring_manager.list_recurring_tasks()
    
    if not recurring_tasks:
        get_console().print("[muted]No recurring tasks found.[/muted]")
        get_console().print("[muted]Create one with: todo recurring 'task description' 'pattern'[/muted]")
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


@cli.command("recurring-generate")
@click.option("--days", "-d", type=int, default=30, help="Generate tasks for next N days")
@click.option("--dry-run", is_flag=True, help="Show what would be generated without creating tasks")
def generate_recurring(days, dry_run):
    """Generate due recurring tasks.
    
    Examples:
      todo recurring-generate              # Generate for next 30 days
      todo recurring-generate --days 7    # Generate for next week
      todo recurring-generate --dry-run   # Preview without creating
    """
    until_date = datetime.now() + timedelta(days=days)
    
    generated_tasks = recurring_manager.generate_due_tasks(until_date)
    
    if not generated_tasks:
        get_console().print("[muted]No recurring tasks due for generation.[/muted]")
        return
    
    if dry_run:
        get_console().print(f"\n[primary]Would generate {len(generated_tasks)} tasks:[/primary]")
        for task in generated_tasks:
            get_console().print(f"  • {task.text} (due: {task.due_date.strftime('%Y-%m-%d') if task.due_date else 'No date'})")
        get_console().print(f"\n[muted]Run without --dry-run to actually create these tasks[/muted]")
    else:
        # Actually save the generated tasks
        storage = get_storage()
        saved_count = 0
        
        for task in generated_tasks:
            # Get next ID for the project
            task.id = storage.get_next_todo_id(task.project)
            
            # Load project and add task
            proj, todos = storage.load_project(task.project)
            if not proj:
                from .project import Project
                proj = Project(task.project, task.project)
                todos = []
            
            todos.append(task)
            
            if storage.save_project(proj, todos):
                saved_count += 1
        
        get_console().print(f"\n[success]✅ Generated and saved {saved_count} recurring tasks[/success]")
        
        if saved_count != len(generated_tasks):
            failed_count = len(generated_tasks) - saved_count
            get_console().print(f"[warning]⚠️  Failed to save {failed_count} tasks[/warning]")
        
        # Send notification about generated tasks
        if saved_count > 0:
            try:
                from .notifications import NotificationManager
                notification_manager = NotificationManager()
                notification_manager.send_recurring_notification(saved_count)
            except Exception:
                # Silently ignore notification failures
                pass


@cli.command("recurring-pause")
@click.argument("task_id")
def pause_recurring(task_id):
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


@cli.command("recurring-resume")
@click.argument("task_id")
def resume_recurring(task_id):
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


@cli.command("recurring-delete")
@click.argument("task_id")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete_recurring(task_id, confirm):
    """Delete a recurring task."""
    task = recurring_manager.get_recurring_task(task_id)
    if not task:
        get_console().print(f"[error]❌ Recurring task '{task_id}' not found[/error]")
        return
    
    get_console().print(f"\n[warning]Will delete recurring task:[/warning]")
    get_console().print(f"  [bold]{task.template.text}[/bold]")
    get_console().print(f"  Pattern: {task.template.recurrence}")
    get_console().print(f"  Occurrences generated: {task.occurrence_count}")
    
    if not confirm and not click.confirm("\nAre you sure you want to delete this recurring task?"):
        get_console().print("[muted]Deletion cancelled.[/muted]")
        return
    
    recurring_manager.delete_recurring_task(task_id)
    get_console().print(f"[success]✅ Deleted recurring task[/success]")


@cli.command()
def projects():
    """List all projects."""
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


@cli.command()
@click.argument("format_type", type=click.Choice(['json', 'csv', 'markdown', 'md', 'html', 'pdf', 'ical', 'yaml', 'tsv']))
@click.option("--output", "-o", help="Output file path (auto-generated if not specified)")
@click.option("--project", "-p", help="Export specific project only")
@click.option("--include-completed", is_flag=True, default=True, help="Include completed tasks")
@click.option("--no-completed", "exclude_completed", is_flag=True, help="Exclude completed tasks")
@click.option("--include-metadata", is_flag=True, default=True, help="Include extended metadata")
@click.option("--group-by-project", is_flag=True, help="Group tasks by project (Markdown only)")
@click.option("--open-after", is_flag=True, help="Open the exported file after creation")
def export(format_type, output, project, include_completed, exclude_completed, include_metadata, group_by_project, open_after):
    """Export tasks to various formats.
    
    Supported formats:
      json       - Structured JSON data
      csv        - Comma-separated values for spreadsheets
      tsv        - Tab-separated values
      markdown   - Human-readable Markdown format
      html       - Web-friendly HTML format
      pdf        - Professional PDF report (lightweight, optional: fpdf2)
      ical       - iCalendar format for calendar apps
      yaml       - YAML format
    
    Examples:
      todo export json --project work
      todo export csv --no-completed -o ~/exports/tasks.csv
      todo export html --open-after
      todo export pdf --project personal -o report.pdf
    """
    storage = get_storage()
    config = get_config()
    export_manager = ExportManager()
    
    # Handle completed tasks flags
    if exclude_completed:
        include_completed = False
    
    # Convert format string to enum
    format_map = {
        'json': ExportFormat.JSON,
        'csv': ExportFormat.CSV,
        'tsv': ExportFormat.TSV,
        'markdown': ExportFormat.MARKDOWN,
        'md': ExportFormat.MARKDOWN,
        'html': ExportFormat.HTML,
        'pdf': ExportFormat.PDF,
        'ical': ExportFormat.ICAL,
        'yaml': ExportFormat.YAML,
    }
    
    export_format = format_map[format_type]
    
    # Get all todos from specified project or all projects
    all_todos = []
    project_info = None
    
    if project:
        projects = [project]
        proj, todos = storage.load_project(project)
        project_info = proj
    else:
        projects = storage.list_projects()
        if not projects:
            projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    if not all_todos:
        get_console().print("[yellow]No tasks found to export.[/yellow]")
        return
    
    # Generate output filename if not specified
    if not output:
        from pathlib import Path
        project_name = project or "all_projects"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = export_manager.get_file_extension(export_format)
        output = f"todo_export_{project_name}_{timestamp}.{extension}"
    
    # Prepare export options
    export_kwargs = {
        'include_completed': include_completed,
        'include_metadata': include_metadata,
        'project_name': project_info.display_name if project_info and hasattr(project_info, 'display_name') else (project or "Todo Export")
    }
    
    # Markdown-specific options
    if export_format == ExportFormat.MARKDOWN:
        export_kwargs['group_by_project'] = group_by_project
    
    try:
        # Perform the export
        get_console().print(f"[primary]🔄 Exporting {len(all_todos)} tasks to {format_type.upper()}...[/primary]")
        
        
        result = export_manager.export_todos(
            all_todos,
            export_format,
            output_path=output,
            **export_kwargs
        )
        
        # Show success message with stats
        exported_todos = all_todos if include_completed else [t for t in all_todos if not t.completed]
        stats = {
            'total': len(exported_todos),
            'completed': sum(1 for t in exported_todos if t.completed),
            'pending': sum(1 for t in exported_todos if not t.completed),
            'overdue': sum(1 for t in exported_todos if t.is_overdue() and not t.completed)
        }
        
        get_console().print(f"\n[success]✅ Successfully exported to {output}[/success]")
        get_console().print(f"[muted]📊 Stats: {stats['total']} total, {stats['completed']} completed, {stats['pending']} pending, {stats['overdue']} overdue[/muted]")
        
        # Show file size
        from pathlib import Path
        file_size = Path(output).stat().st_size
        if file_size > 1024 * 1024:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        elif file_size > 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size} bytes"
        
        get_console().print(f"[muted]📁 File size: {size_str}[/muted]")
        
        # Open file if requested
        if open_after:
            try:
                import subprocess
                if sys.platform == "darwin":  # macOS
                    subprocess.run(["open", output])
                elif sys.platform == "win32":  # Windows
                    subprocess.run(["start", output], shell=True)
                else:  # Linux and others
                    subprocess.run(["xdg-open", output])
                get_console().print(f"[success]🚀 Opened {output}[/success]")
            except Exception as e:
                get_console().print(f"[warning]⚠️  Could not open file: {e}[/warning]")
        
    except ImportError as e:
        get_console().print(f"[error]❌ Export failed: {e}[/error]")
        if "fpdf2" in str(e):
            get_console().print("[muted]Install lightweight PDF support with: pip install fpdf2[/muted]")
            get_console().print("[muted]Or use 'html' or 'markdown' formats for visual reports.[/muted]")
    except Exception as e:
        get_console().print(f"[error]❌ Export failed: {e}[/error]")
        sys.exit(1)


@cli.group()
def notify():
    """Manage notifications and notification settings.
    
    Configure desktop and email notifications for due tasks, overdue reminders,
    and daily summaries. Test notification delivery and view notification history.
    """
    pass


@notify.command()
@click.option('--test', is_flag=True, help='Test notification delivery')
def status(test):
    """Show notification system status and availability."""
    notification_manager = NotificationManager()
    
    get_console().print("[header]🔔 Notification System Status[/header]\n")
    
    # Show preferences status
    prefs = notification_manager.preferences
    enabled_icon = "✅" if prefs.enabled else "❌"
    get_console().print(f"{enabled_icon} [bold]Notifications:[/bold] {'Enabled' if prefs.enabled else 'Disabled'}")
    
    # Check availability
    availability = notification_manager.is_available()
    
    desktop_icon = "✅" if availability['desktop'] else "❌"
    desktop_enabled = "✅" if prefs.desktop_enabled else "❌"
    get_console().print(f"{desktop_icon} [bold]Desktop:[/bold] {'Available' if availability['desktop'] else 'Not Available'} | {desktop_enabled} {'Enabled' if prefs.desktop_enabled else 'Disabled'}")
    
    email_icon = "✅" if availability['email'] else "❌"
    email_enabled = "✅" if prefs.email_enabled else "❌"
    get_console().print(f"{email_icon} [bold]Email:[/bold] {'Available' if availability['email'] else 'Not Available'} | {email_enabled} {'Enabled' if prefs.email_enabled else 'Disabled'}")
    
    # Show notification types
    get_console().print("\n[subheader]Notification Types:[/subheader]")
    type_status = [
        ("Due Soon", prefs.notify_due_soon, f"{prefs.due_soon_hours}h before"),
        ("Overdue", prefs.notify_overdue, f"Every {prefs.overdue_reminder_hours}h"),
        ("Recurring Tasks", prefs.notify_recurring, "When generated"),
        ("Daily Summary", prefs.notify_daily_summary, "Once per day"),
        ("Weekly Summary", prefs.notify_weekly_summary, "Once per week")
    ]
    
    for name, enabled, timing in type_status:
        icon = "✅" if enabled else "❌"
        get_console().print(f"  {icon} {name}: {timing if enabled else 'Disabled'}")
    
    # Show quiet hours
    if prefs.quiet_enabled:
        get_console().print(f"\n[muted]😴 Quiet hours: {prefs.quiet_start:02d}:00 - {prefs.quiet_end:02d}:00[/muted]")
    
    # Test notifications if requested
    if test:
        get_console().print("\n[primary]📨 Testing notifications...[/primary]")
        test_results = notification_manager.test_notifications()
        
        for method, success in test_results.items():
            icon = "✅" if success else "❌"
            status_text = "Success" if success else "Failed"
            get_console().print(f"  {icon} {method.title()}: {status_text}")


@notify.command()
@click.option('--enabled/--disabled', default=None, help='Enable or disable notifications')
@click.option('--desktop/--no-desktop', default=None, help='Enable or disable desktop notifications')
@click.option('--email/--no-email', default=None, help='Enable or disable email notifications')
@click.option('--due-soon-hours', type=int, help='Hours before due date to notify')
@click.option('--overdue-hours', type=int, help='Hours between overdue reminders')
@click.option('--quiet-start', type=int, help='Quiet hours start (24-hour format)')
@click.option('--quiet-end', type=int, help='Quiet hours end (24-hour format)')
@click.option('--quiet/--no-quiet', default=None, help='Enable or disable quiet hours')
@click.option('--email-address', help='Email address for notifications')
@click.option('--smtp-server', help='SMTP server hostname')
@click.option('--smtp-port', type=int, help='SMTP server port')
@click.option('--smtp-username', help='SMTP username')
@click.option('--smtp-password', help='SMTP password (use with caution)')
def config(enabled, desktop, email, due_soon_hours, overdue_hours, quiet_start, 
          quiet_end, quiet, email_address, smtp_server, smtp_port, smtp_username, smtp_password):
    """Configure notification preferences.
    
    Examples:
      todo notify config --enabled --desktop
      todo notify config --due-soon-hours 12 --overdue-hours 6
      todo notify config --quiet-start 22 --quiet-end 8
      todo notify config --email --email-address user@example.com --smtp-server smtp.gmail.com
    """
    notification_manager = NotificationManager()
    prefs = notification_manager.preferences
    changes_made = False
    
    # Update preferences based on options
    if enabled is not None:
        prefs.enabled = enabled
        changes_made = True
    
    if desktop is not None:
        prefs.desktop_enabled = desktop
        changes_made = True
    
    if email is not None:
        prefs.email_enabled = email
        changes_made = True
    
    if due_soon_hours is not None:
        prefs.due_soon_hours = due_soon_hours
        changes_made = True
    
    if overdue_hours is not None:
        prefs.overdue_reminder_hours = overdue_hours
        changes_made = True
    
    if quiet_start is not None:
        prefs.quiet_start = quiet_start
        changes_made = True
    
    if quiet_end is not None:
        prefs.quiet_end = quiet_end
        changes_made = True
    
    if quiet is not None:
        prefs.quiet_enabled = quiet
        changes_made = True
    
    if email_address:
        prefs.email_address = email_address
        changes_made = True
    
    if smtp_server:
        prefs.smtp_server = smtp_server
        changes_made = True
    
    if smtp_port is not None:
        prefs.smtp_port = smtp_port
        changes_made = True
    
    if smtp_username:
        prefs.smtp_username = smtp_username
        changes_made = True
    
    if smtp_password:
        get_console().print("[warning]⚠️  Warning: Passwords are stored in plain text. Consider using app-specific passwords.[/warning]")
        prefs.smtp_password = smtp_password
        changes_made = True
    
    if changes_made:
        notification_manager.save_preferences()
        get_console().print("[success]✅ Notification preferences updated[/success]")
    else:
        get_console().print("[yellow]No changes specified. Use --help to see available options.[/yellow]")


@notify.command()
@click.option('--limit', '-l', type=int, default=20, help='Number of notifications to show')
@click.option('--type', 'notification_type', 
              type=click.Choice(['due_soon', 'overdue', 'recurring_generated', 'daily_summary']),
              help='Filter by notification type')
def history(limit, notification_type):
    """Show notification history.
    
    Examples:
      todo notify history
      todo notify history --limit 50
      todo notify history --type overdue
    """
    notification_manager = NotificationManager()
    
    # Convert string to enum if provided
    filter_type = None
    if notification_type:
        filter_type = NotificationType(notification_type)
    
    notifications = notification_manager.get_notification_history(
        limit=limit, 
        notification_type=filter_type
    )
    
    if not notifications:
        get_console().print("[yellow]No notifications found in history.[/yellow]")
        return
    
    get_console().print(f"[header]📜 Notification History ({len(notifications)} recent)[/header]\n")
    
    for notification in notifications:
        # Format timestamp
        time_str = notification.created_at.strftime('%m-%d %H:%M')
        
        # Get type icon
        type_icons = {
            NotificationType.DUE_SOON: '⏰',
            NotificationType.OVERDUE: '🔥',
            NotificationType.RECURRING_GENERATED: '🔄',
            NotificationType.DAILY_SUMMARY: '📈',
            NotificationType.WEEKLY_SUMMARY: '📈',
            NotificationType.MILESTONE: '🎆'
        }
        icon = type_icons.get(notification.type, '🔔')
        
        # Status indicator
        status = "✅" if notification.sent_at else "⏸️"
        
        get_console().print(f"{icon} {status} [{time_str}] [bold]{notification.title}[/bold]")
        get_console().print(f"    [muted]{notification.message}[/muted]")
        
        if notification.todo_id:
            get_console().print(f"    [muted]Task ID: {notification.todo_id}[/muted]")
        
        get_console().print()


@notify.command()
@click.option('--title', '-t', default='Test Notification', help='Test notification title')
@click.option('--message', '-m', default='This is a test from Todo CLI', help='Test notification message')
def test(title, message):
    """Send a test notification.
    
    Examples:
      todo notify test
      todo notify test --title "Custom Test" --message "Testing notifications"
    """
    notification_manager = NotificationManager()
    
    if not notification_manager.preferences.enabled:
        get_console().print("[error]❌ Notifications are disabled. Enable with: todo notify config --enabled[/error]")
        return
    
    get_console().print("[primary]📨 Sending test notification...[/primary]")
    
    results = {}
    if notification_manager.preferences.desktop_enabled:
        results['desktop'] = notification_manager.scheduler.test_notification(title, message)
    
    if notification_manager.preferences.email_enabled:
        # For email test, we'd need to create a proper notification with email delivery method
        # For now, just check if email is configured
        results['email'] = notification_manager.scheduler.email_delivery.is_available()
    
    # Show results
    success_count = 0
    for method, success in results.items():
        icon = "✅" if success else "❌"
        status_text = "Success" if success else "Failed"
        get_console().print(f"  {icon} {method.title()}: {status_text}")
        if success:
            success_count += 1
    
    if success_count > 0:
        get_console().print(f"\n[success]✅ Sent test notification via {success_count} method(s)[/success]")
    else:
        get_console().print("\n[error]❌ No test notifications could be sent[/error]")
        get_console().print("[muted]Check your notification settings with: todo notify status[/muted]")


@notify.command()
def check():
    """Check for due and overdue tasks and send notifications.
    
    This command manually triggers the notification check that would normally
    run automatically. Useful for testing or immediate notification delivery.
    """
    storage = get_storage()
    config = get_config()
    notification_manager = NotificationManager()
    
    if not notification_manager.preferences.enabled:
        get_console().print("[yellow]Notifications are disabled. Enable with: todo notify config --enabled[/yellow]")
        return
    
    # Get all todos
    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    get_console().print("[primary]🔍 Checking for due and overdue tasks...[/primary]")
    
    notifications_sent = notification_manager.check_and_send_notifications(all_todos)
    
    if notifications_sent > 0:
        get_console().print(f"[success]✅ Sent {notifications_sent} notification(s)[/success]")
    else:
        get_console().print("[muted]😴 No notifications needed at this time[/muted]")


# Create main function that invokes dashboard by default
@click.group(invoke_without_command=True)
@click.option("--config", type=click.Path(), help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--no-banner", is_flag=True, help="Skip the startup banner")
@click.pass_context
def main(ctx, config, verbose, no_banner):
    """Productivity Ninja CLI - Master Your Tasks. Unleash Your Potential."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['no_banner'] = no_banner
    
    # Load configuration
    try:
        if config:
            from pathlib import Path
            load_config(Path(config))
        else:
            get_config()
    except Exception as e:
        get_console().print(f"[error]Configuration error: {e}[/error]")
        sys.exit(1)
    
    # If no command provided, show startup experience
    if ctx.invoked_subcommand is None:
        if not no_banner:
            show_startup_banner(get_console())
            show_quick_help(get_console())
        ctx.invoke(dashboard)


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
main.add_command(dashboard)
main.add_command(list_todos, name="list")
main.add_command(search)
main.add_command(recommend)
main.add_command(queries)
main.add_command(bulk)
main.add_command(recurring)
main.add_command(list_recurring)
main.add_command(generate_recurring)
main.add_command(pause_recurring)
main.add_command(resume_recurring)
main.add_command(delete_recurring)
main.add_command(done)
main.add_command(pin)
main.add_command(projects)
main.add_command(export)
main.add_command(notify)
main.add_command(get_analytics_commands())

# Add app-sync command group
from .app_sync import app_sync_group
main.add_command(app_sync_group)

# Add doctor command group
from .doctor import doctor
main.add_command(doctor)

# Add theme command group
from .theme_cmds import get_theme_commands
main.add_command(get_theme_commands())


if __name__ == "__main__":
    main()
