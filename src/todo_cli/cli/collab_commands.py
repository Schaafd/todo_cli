"""Collaboration CLI commands for shared projects and team features."""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..services.collaboration import (
    CollaborationDB,
    CollaborationManager,
    ProjectRole,
)


def _get_manager() -> CollaborationManager:
    return CollaborationManager()


def _get_console() -> Console:
    return Console()


def _get_user_id() -> str:
    """Get current user ID from config or default."""
    try:
        from ..config import get_config
        cfg = get_config()
        uid = getattr(cfg, "collab_user_id", None)
        if uid:
            return uid
    except Exception:
        pass
    return "local-user"


def _get_username() -> str:
    """Get current username from config or default."""
    try:
        from ..config import get_config
        cfg = get_config()
        uname = getattr(cfg, "collab_username", None)
        if uname:
            return uname
    except Exception:
        pass
    return "local-user"


@click.group("collab")
def collab_group():
    """Collaboration and shared project management."""
    pass


@collab_group.command("share")
@click.argument("project")
@click.option("--description", "-d", default="", help="Project description")
def share_project(project, description):
    """Share a project for collaboration."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()

    shared = manager.share_project(project, user_id, description)
    console.print(Panel(
        f"[bold green]Project shared successfully![/bold green]\n\n"
        f"Project ID: [cyan]{shared.id}[/cyan]\n"
        f"Name: {shared.name}\n"
        f"Owner: {user_id}",
        title="Shared Project",
    ))


@collab_group.command("invite")
@click.argument("project_id")
@click.argument("username")
@click.option("--role", type=click.Choice(["admin", "editor", "viewer"]), default="editor",
              help="Role for the invited member")
def invite_member(project_id, username, role):
    """Invite a user to a shared project."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()

    role_enum = ProjectRole(role)
    member = manager.invite_member(project_id, user_id, username, username, role_enum)
    if member:
        console.print(f"[green]Invited {username} as {role} to project.[/green]")
    else:
        console.print("[red]Permission denied. You need admin or owner role to invite members.[/red]")


@collab_group.command("members")
@click.argument("project_id")
def list_members(project_id):
    """List members of a shared project."""
    console = _get_console()
    manager = _get_manager()

    members = manager.db.get_project_members(project_id)
    if not members:
        console.print("[yellow]No members found or project does not exist.[/yellow]")
        return

    table = Table(title="Project Members")
    table.add_column("Username", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Joined", style="dim")
    table.add_column("Invited By", style="dim")

    for m in members:
        table.add_row(
            m.username,
            m.role.value,
            m.joined_at.strftime("%Y-%m-%d %H:%M"),
            m.invited_by or "-",
        )
    console.print(table)


@collab_group.command("activity")
@click.argument("project_id", required=False)
@click.option("--limit", "-n", type=int, default=20, help="Number of entries to show")
def show_activity(project_id, limit):
    """Show activity feed for a project or for current user."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()

    if project_id:
        entries = manager.db.get_activity_feed(project_id, limit)
    else:
        entries = manager.db.get_user_activity(user_id, limit)

    if not entries:
        console.print("[yellow]No activity found.[/yellow]")
        return

    table = Table(title="Activity Feed")
    table.add_column("Time", style="dim")
    table.add_column("User", style="cyan")
    table.add_column("Action", style="green")
    table.add_column("Description")

    for e in entries:
        table.add_row(
            e.created_at.strftime("%Y-%m-%d %H:%M"),
            e.username,
            e.activity_type.value,
            e.description,
        )
    console.print(table)


@collab_group.command("comment")
@click.argument("task_id")
@click.argument("content")
def add_comment(task_id, content):
    """Add a comment to a task."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()
    username = _get_username()

    comment = manager.db.add_comment(task_id, user_id, username, content)
    console.print(f"[green]Comment added (ID: {comment.id})[/green]")


@collab_group.command("comments")
@click.argument("task_id")
def show_comments(task_id):
    """Show comments for a task."""
    console = _get_console()
    manager = _get_manager()

    comments = manager.db.get_comments(task_id)
    if not comments:
        console.print("[yellow]No comments found for this task.[/yellow]")
        return

    for c in comments:
        console.print(Panel(
            f"{c.content}",
            title=f"{c.username} - {c.created_at.strftime('%Y-%m-%d %H:%M')}",
            border_style="dim",
        ))


@collab_group.command("assign")
@click.argument("task_id")
@click.argument("username")
def assign_task(task_id, username):
    """Assign a task to a user."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()

    success = manager.db.assign_task(task_id, username, user_id)
    if success:
        console.print(f"[green]Task {task_id} assigned to {username}.[/green]")
    else:
        console.print("[red]Failed to assign task.[/red]")


@collab_group.command("projects")
def list_shared_projects():
    """List all shared projects you are a member of."""
    console = _get_console()
    manager = _get_manager()
    user_id = _get_user_id()

    projects = manager.db.list_user_projects(user_id)
    if not projects:
        console.print("[yellow]No shared projects found.[/yellow]")
        return

    table = Table(title="Shared Projects")
    table.add_column("ID", style="cyan", max_width=36)
    table.add_column("Name", style="bold")
    table.add_column("Owner", style="green")
    table.add_column("Members", justify="right")
    table.add_column("Description", style="dim")

    for p in projects:
        table.add_row(
            p.id,
            p.name,
            p.owner_id,
            str(len(p.members)),
            p.description or "-",
        )
    console.print(table)
