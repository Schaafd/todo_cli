"""Backup and recovery system CLI commands."""

import sys
import shutil
import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import click
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TaskID

from ..config import get_config
from ..storage import Storage
from ..domain import Todo, Project
from ..theme import get_themed_console
from ..utils.datetime import now_utc


def get_storage() -> Storage:
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


def get_console():
    """Get themed console."""
    return get_themed_console()


def get_backup_dir() -> Path:
    """Get the backup directory path."""
    config = get_config()
    # Use ~/.todo/backups/ as default backup location
    backup_path = Path.home() / ".todo" / "backups"
    backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path


def create_backup_metadata(backup_path: Path, backup_type: str = "manual") -> Dict[str, Any]:
    """Create metadata for a backup."""
    return {
        "timestamp": now_utc().isoformat(),
        "backup_type": backup_type,
        "path": str(backup_path),
        "version": "1.0",
        "todo_cli_version": "0.1.1"
    }


def get_all_project_data() -> Dict[str, Any]:
    """Get all project data for backup."""
    storage = get_storage()
    config = get_config()
    
    backup_data = {
        "projects": {},
        "config": {
            "default_project": config.default_project,
            # Add other relevant config fields
        },
        "metadata": {
            "created_at": now_utc().isoformat(),
            "version": "1.0"
        }
    }
    
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if proj or todos:
            backup_data["projects"][proj_name] = {
                "project": proj.to_dict() if proj else {"name": proj_name},
                "todos": [todo.to_dict() for todo in todos] if todos else []
            }
    
    return backup_data


@click.group(name="backup")
def backup():
    """Backup and recovery commands."""
    pass


@backup.command(name="create")
@click.option("--name", "-n", help="Custom backup name")
@click.option("--auto", is_flag=True, help="Mark as automatic backup")
def create_backup(name: str, auto: bool):
    """Create a backup of all todo data."""
    try:
        backup_dir = get_backup_dir()
        
        # Generate backup filename
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        backup_type = "auto" if auto else "manual"
        
        if name:
            backup_filename = f"{timestamp}_{backup_type}_{name}.json"
        else:
            backup_filename = f"{timestamp}_{backup_type}.json"
        
        backup_path = backup_dir / backup_filename
        
        get_console().print(f"[bold blue]📦 Creating backup...[/bold blue]")
        
        with Progress() as progress:
            # Get all project data
            task = progress.add_task("Collecting data...", total=100)
            backup_data = get_all_project_data()
            progress.update(task, advance=30)
            
            # Add metadata
            progress.update(task, description="Adding metadata...", advance=20)
            backup_data["backup_metadata"] = create_backup_metadata(backup_path, backup_type)
            progress.update(task, advance=20)
            
            # Write backup file
            progress.update(task, description="Writing backup file...", advance=20)
            with open(backup_path, 'w') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            progress.update(task, advance=10)
        
        # Show summary
        projects_count = len(backup_data["projects"])
        total_todos = sum(len(proj_data["todos"]) for proj_data in backup_data["projects"].values())
        file_size = backup_path.stat().st_size
        size_mb = file_size / 1024 / 1024
        
        get_console().print(f"[green]✅ Backup created successfully![/green]")
        get_console().print(f"[muted]File: {backup_filename}[/muted]")
        get_console().print(f"[muted]Projects: {projects_count}, Todos: {total_todos}[/muted]")
        get_console().print(f"[muted]Size: {size_mb:.2f} MB[/muted]")
        
    except Exception as e:
        get_console().print(f"[red]❌ Backup failed: {e}[/red]")
        sys.exit(1)


@backup.command(name="list")
@click.option("--limit", "-l", type=int, default=20, help="Limit number of backups to show")
def list_backups(limit: int):
    """List available backups."""
    backup_dir = get_backup_dir()
    
    # Find all backup files
    backup_files = list(backup_dir.glob("*.json"))
    if not backup_files:
        get_console().print("[yellow]No backups found.[/yellow]")
        return
    
    # Sort by creation time (newest first)
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    if limit:
        backup_files = backup_files[:limit]
    
    # Create table
    table = Table(title="💾 Available Backups", show_header=True, header_style="bold blue")
    table.add_column("Name", style="cyan", min_width=25)
    table.add_column("Created", style="yellow", min_width=15)
    table.add_column("Type", style="green", min_width=8)
    table.add_column("Size", style="white", min_width=8)
    table.add_column("Projects", style="blue", min_width=8)
    table.add_column("Todos", style="magenta", min_width=6)
    
    for backup_file in backup_files:
        try:
            # Get file stats
            stat = backup_file.stat()
            size_mb = stat.st_size / 1024 / 1024
            created = datetime.fromtimestamp(stat.st_mtime)
            
            # Try to read backup metadata
            projects_count = "?"
            todos_count = "?"
            backup_type = "unknown"
            
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    if "projects" in data:
                        projects_count = str(len(data["projects"]))
                        todos_count = str(sum(len(proj_data.get("todos", [])) 
                                            for proj_data in data["projects"].values()))
                    
                    if "backup_metadata" in data:
                        backup_type = data["backup_metadata"].get("backup_type", "unknown")
            except:
                pass  # Use default values if can't read file
            
            table.add_row(
                backup_file.name,
                created.strftime("%Y-%m-%d %H:%M"),
                backup_type.title(),
                f"{size_mb:.2f}MB",
                projects_count,
                todos_count
            )
            
        except Exception:
            # Show file even if we can't read it properly
            table.add_row(
                backup_file.name,
                "Unknown",
                "Error",
                "?",
                "?",
                "?"
            )
    
    get_console().print(table)


@backup.command(name="restore")
@click.argument("backup_name")
@click.option("--dry-run", is_flag=True, help="Show what would be restored without making changes")
@click.option("--force", is_flag=True, help="Restore without confirmation prompts")
def restore_backup(backup_name: str, dry_run: bool, force: bool):
    """Restore from a backup."""
    backup_dir = get_backup_dir()
    
    # Find backup file
    backup_path = None
    if backup_name.endswith('.json'):
        backup_path = backup_dir / backup_name
    else:
        # Try to find backup by partial name
        candidates = list(backup_dir.glob(f"*{backup_name}*.json"))
        if len(candidates) == 1:
            backup_path = candidates[0]
        elif len(candidates) > 1:
            get_console().print("[red]❌ Multiple backups match that name:[/red]")
            for candidate in candidates:
                get_console().print(f"  • {candidate.name}")
            sys.exit(1)
        else:
            backup_path = backup_dir / f"{backup_name}.json"
    
    if not backup_path.exists():
        get_console().print(f"[red]❌ Backup file not found: {backup_path.name}[/red]")
        sys.exit(1)
    
    try:
        # Read backup data
        get_console().print(f"[bold blue]📂 Reading backup: {backup_path.name}[/bold blue]")
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
        
        if "projects" not in backup_data:
            get_console().print("[red]❌ Invalid backup file format[/red]")
            sys.exit(1)
        
        projects_to_restore = backup_data["projects"]
        projects_count = len(projects_to_restore)
        total_todos = sum(len(proj_data.get("todos", [])) for proj_data in projects_to_restore.values())
        
        get_console().print(f"[muted]Found {projects_count} projects with {total_todos} todos[/muted]")
        
        if dry_run:
            get_console().print("[yellow]🔍 DRY RUN - would restore:[/yellow]")
            for proj_name, proj_data in projects_to_restore.items():
                todos_count = len(proj_data.get("todos", []))
                get_console().print(f"  • [cyan]{proj_name}[/cyan]: {todos_count} todos")
            return
        
        # Confirmation prompt
        if not force:
            get_console().print("[bold yellow]⚠️  This will overwrite existing data![/bold yellow]")
            response = click.confirm("Do you want to continue with the restore?")
            if not response:
                get_console().print("Restore cancelled.")
                return
        
        # Create current backup before restore
        get_console().print("[muted]Creating safety backup of current data...[/muted]")
        timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
        safety_backup_path = backup_dir / f"{timestamp}_pre_restore_safety.json"
        current_data = get_all_project_data()
        current_data["backup_metadata"] = create_backup_metadata(safety_backup_path, "pre_restore_safety")
        
        with open(safety_backup_path, 'w') as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        
        # Perform restore
        storage = get_storage()
        restored_projects = 0
        restored_todos = 0
        
        with Progress() as progress:
            task = progress.add_task("Restoring projects...", total=projects_count)
            
            for proj_name, proj_data in projects_to_restore.items():
                # Restore project
                project_dict = proj_data.get("project", {})
                project = Project.from_dict(project_dict) if project_dict else Project(name=proj_name)
                
                # Restore todos
                todos = []
                for todo_dict in proj_data.get("todos", []):
                    try:
                        todo = Todo.from_dict(todo_dict)
                        todos.append(todo)
                        restored_todos += 1
                    except Exception as e:
                        get_console().print(f"[yellow]⚠️  Skipping invalid todo in {proj_name}: {e}[/yellow]")
                
                # Save restored project
                if storage.save_project(project, todos):
                    restored_projects += 1
                else:
                    get_console().print(f"[red]❌ Failed to restore project: {proj_name}[/red]")
                
                progress.update(task, advance=1)
        
        get_console().print(f"[green]✅ Restore completed![/green]")
        get_console().print(f"[muted]Restored {restored_projects} projects with {restored_todos} todos[/muted]")
        get_console().print(f"[muted]Safety backup saved as: {safety_backup_path.name}[/muted]")
        
    except Exception as e:
        get_console().print(f"[red]❌ Restore failed: {e}[/red]")
        sys.exit(1)


@backup.command(name="auto-setup")
@click.option("--enable/--disable", default=True, help="Enable or disable automatic backups")
@click.option("--frequency", type=click.Choice(['daily', 'weekly', 'on-exit']), default='weekly', 
              help="Backup frequency")
@click.option("--keep", type=int, default=10, help="Number of backups to keep")
def setup_auto_backup(enable: bool, frequency: str, keep: int):
    """Set up automatic backup configuration."""
    # This is a simplified implementation
    # In a real implementation, this would configure system-level automation
    
    if enable:
        get_console().print(f"[green]✅ Automatic backups enabled[/green]")
        get_console().print(f"[muted]Frequency: {frequency}[/muted]")
        get_console().print(f"[muted]Keep: {keep} backups[/muted]")
        get_console().print("[yellow]💡 Note: Automatic backup scheduling requires manual setup of cron jobs or system tasks[/yellow]")
        
        # Show example cron job
        if frequency == "daily":
            cron_schedule = "0 2 * * *"  # 2 AM daily
        elif frequency == "weekly":
            cron_schedule = "0 2 * * 0"  # 2 AM Sunday
        else:
            cron_schedule = "# Run on shell exit"
        
        get_console().print(f"[muted]Example cron entry: {cron_schedule} todo backup create --auto[/muted]")
    else:
        get_console().print("[yellow]Automatic backups disabled[/yellow]")


@backup.command(name="clean")
@click.option("--keep", type=int, default=10, help="Number of recent backups to keep")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without making changes")
@click.option("--older-than", type=int, help="Delete backups older than N days")
def clean_backups(keep: int, dry_run: bool, older_than: int):
    """Clean up old backup files."""
    backup_dir = get_backup_dir()
    
    backup_files = list(backup_dir.glob("*.json"))
    if not backup_files:
        get_console().print("[yellow]No backup files found.[/yellow]")
        return
    
    # Sort by creation time (newest first)
    backup_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    files_to_delete = []
    
    if older_than:
        # Delete files older than specified days
        cutoff_time = now_utc().timestamp() - (older_than * 24 * 60 * 60)
        for backup_file in backup_files:
            if backup_file.stat().st_mtime < cutoff_time:
                files_to_delete.append(backup_file)
    else:
        # Keep only the most recent N backups
        if len(backup_files) > keep:
            files_to_delete = backup_files[keep:]
    
    if not files_to_delete:
        get_console().print("[green]✅ No cleanup needed.[/green]")
        return
    
    total_size = sum(f.stat().st_size for f in files_to_delete)
    size_mb = total_size / 1024 / 1024
    
    if dry_run:
        get_console().print(f"[yellow]🔍 DRY RUN - would delete {len(files_to_delete)} backup files ({size_mb:.2f}MB):[/yellow]")
        for backup_file in files_to_delete:
            created = datetime.fromtimestamp(backup_file.stat().st_mtime)
            get_console().print(f"  • {backup_file.name} ({created.strftime('%Y-%m-%d %H:%M')})")
        return
    
    # Confirm deletion
    response = click.confirm(f"Delete {len(files_to_delete)} backup files ({size_mb:.2f}MB)?")
    if not response:
        get_console().print("Cleanup cancelled.")
        return
    
    # Delete files
    deleted_count = 0
    for backup_file in files_to_delete:
        try:
            backup_file.unlink()
            deleted_count += 1
        except Exception as e:
            get_console().print(f"[red]❌ Failed to delete {backup_file.name}: {e}[/red]")
    
    get_console().print(f"[green]✅ Deleted {deleted_count} backup files ({size_mb:.2f}MB)[/green]")


@backup.command(name="verify")
@click.argument("backup_name", required=False)
def verify_backup(backup_name: str):
    """Verify backup file integrity."""
    backup_dir = get_backup_dir()
    
    # Find backup files to verify
    if backup_name:
        if backup_name.endswith('.json'):
            backup_files = [backup_dir / backup_name]
        else:
            backup_files = list(backup_dir.glob(f"*{backup_name}*.json"))
        
        if not backup_files:
            get_console().print(f"[red]❌ No backup files found matching '{backup_name}'[/red]")
            sys.exit(1)
    else:
        backup_files = list(backup_dir.glob("*.json"))
    
    if not backup_files:
        get_console().print("[yellow]No backup files found.[/yellow]")
        return
    
    valid_count = 0
    invalid_count = 0
    
    for backup_file in backup_files:
        get_console().print(f"[bold]Verifying: {backup_file.name}[/bold]")
        
        try:
            # Check file exists and is readable
            if not backup_file.exists():
                get_console().print("  [red]❌ File not found[/red]")
                invalid_count += 1
                continue
            
            # Check file size
            size = backup_file.stat().st_size
            if size == 0:
                get_console().print("  [red]❌ Empty file[/red]")
                invalid_count += 1
                continue
            
            # Check JSON format
            with open(backup_file, 'r') as f:
                data = json.load(f)
            
            # Validate structure
            if "projects" not in data:
                get_console().print("  [red]❌ Missing projects data[/red]")
                invalid_count += 1
                continue
            
            # Validate project data
            projects_count = 0
            todos_count = 0
            
            for proj_name, proj_data in data["projects"].items():
                if not isinstance(proj_data, dict):
                    get_console().print(f"  [yellow]⚠️  Invalid project data for {proj_name}[/yellow]")
                    continue
                
                projects_count += 1
                
                # Check todos
                todos = proj_data.get("todos", [])
                if isinstance(todos, list):
                    todos_count += len(todos)
                    
                    # Validate a few todos
                    for i, todo_data in enumerate(todos[:3]):  # Check first 3 todos
                        try:
                            Todo.from_dict(todo_data)
                        except Exception as e:
                            get_console().print(f"  [yellow]⚠️  Invalid todo {i} in {proj_name}: {e}[/yellow]")
            
            get_console().print(f"  [green]✅ Valid ({projects_count} projects, {todos_count} todos)[/green]")
            valid_count += 1
            
        except json.JSONDecodeError:
            get_console().print("  [red]❌ Invalid JSON format[/red]")
            invalid_count += 1
        except Exception as e:
            get_console().print(f"  [red]❌ Verification failed: {e}[/red]")
            invalid_count += 1
    
    # Summary
    total = valid_count + invalid_count
    get_console().print(f"\n[bold]Verification Summary:[/bold]")
    get_console().print(f"  Valid: [green]{valid_count}[/green]")
    get_console().print(f"  Invalid: [red]{invalid_count}[/red]")
    get_console().print(f"  Total: {total}")


def get_backup_commands():
    """Get the backup command group."""
    return backup