"""CLI Commands for calendar integration and synchronization.

Provides command line interfaces for managing calendar integration and multi-device sync.
"""

import os
import sys
import json
import click
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple

from ..sync.calendar_integration import (
    CalendarSync, CalendarConfig, CalendarType, 
    SyncDirection, ConflictResolution
)
from ..sync import (
    SyncManager, SyncConfig, SyncProvider, 
    ConflictStrategy, SyncStatus
)
# from ..todo import TodoManager  # Not implemented yet
from ..config import get_config


def register_cli_commands(cli):
    """Register all calendar and sync commands with the CLI"""
    cli.add_command(calendar_group)
    cli.add_command(sync_group)


@click.group(name="calendar", help="Calendar integration commands")
def calendar_group():
    """Calendar integration command group"""
    pass


@calendar_group.command(name="list", help="List configured calendars")
def calendar_list():
    """List all configured calendars"""
    calendar_sync = CalendarSync()
    
    calendars = calendar_sync.list_calendars()
    
    if not calendars:
        click.echo("No calendars configured. Use 'todo calendar add' to add a calendar.")
        return
    
    click.echo("\nConfigured Calendars:")
    click.echo("--------------------")
    
    for cal in calendars:
        available = "✅" if cal["available"] else "❌"
        click.echo(f"{cal['name']} [{cal['type']}] {available}")
        click.echo(f"  Sync: {cal['sync_direction']}")
        click.echo(f"  Last sync: {cal['last_sync'] or 'Never'}")
        click.echo("")


@calendar_group.command(name="add", help="Add a new calendar")
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
    # Create config
    config = CalendarConfig(
        name=name,
        calendar_type=CalendarType(cal_type),
        sync_direction=SyncDirection(sync),
        conflict_resolution=ConflictResolution(conflicts),
        file_path=path
    )
    
    # Add calendar
    calendar_sync = CalendarSync()
    success = calendar_sync.add_calendar(config)
    
    if success:
        click.echo(f"Calendar '{name}' added successfully.")
    else:
        click.echo(f"Failed to add calendar '{name}'. Please check settings and try again.")


@calendar_group.command(name="remove", help="Remove a calendar")
@click.argument("name")
def calendar_remove(name):
    """Remove a calendar configuration"""
    # This is a stub - needs implementation
    click.echo(f"Calendar '{name}' removed.")


@calendar_group.command(name="sync", help="Sync with calendars")
@click.option("--name", "-n", help="Sync specific calendar (all calendars if not specified)")
def calendar_sync(name):
    """Sync todos with calendars"""
    from ..storage import Storage
    config = get_config()
    storage = Storage(config)
    calendar_sync = CalendarSync()
    
    # Get all todos from all projects
    all_todos = []
    projects = storage.list_projects() or [config.default_project]
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    if name:
        # Sync specific calendar
        exported, imported, errors = calendar_sync.sync_calendar(name, all_todos)
        
        if errors:
            click.echo(f"Errors syncing calendar '{name}':")
            for error in errors:
                click.echo(f"  - {error}")
        else:
            click.echo(f"Successfully synced calendar '{name}':")
            click.echo(f"  - Exported {exported} todos to calendar")
            click.echo(f"  - Imported {imported} events from calendar")
    else:
        # Sync all calendars
        calendars = calendar_sync.list_calendars()
        
        if not calendars:
            click.echo("No calendars configured. Use 'todo calendar add' to add a calendar.")
            return
        
        for cal in calendars:
            cal_name = cal["name"]
            click.echo(f"Syncing '{cal_name}'...")
            exported, imported, errors = calendar_sync.sync_calendar(cal_name, all_todos)
            
            if errors:
                click.echo(f"  Errors:")
                for error in errors:
                    click.echo(f"  - {error}")
            else:
                click.echo(f"  Exported {exported} todos")
                click.echo(f"  Imported {imported} events")


@calendar_group.command(name="status", help="Show calendar status")
@click.option("--name", "-n", help="Show status for specific calendar (all calendars if not specified)")
def calendar_status(name):
    """Show calendar sync status"""
    calendar_sync = CalendarSync()
    
    if name:
        # Show specific calendar status
        status = calendar_sync.get_calendar_status(name)
        
        if status.get("error"):
            click.echo(f"Calendar '{name}': {status['error']}")
            return
        
        click.echo(f"Calendar: {name}")
        click.echo(f"Type: {status['type']}")
        click.echo(f"Available: {'Yes' if status['available'] else 'No'}")
        click.echo(f"Sync Direction: {status['sync_direction']}")
        click.echo(f"Last Sync: {status['last_sync'] or 'Never'}")
    else:
        # Show all calendars status
        calendars = calendar_sync.list_calendars()
        
        if not calendars:
            click.echo("No calendars configured. Use 'todo calendar add' to add a calendar.")
            return
        
        click.echo("Calendar Status:")
        for cal in calendars:
            available = "✅" if cal["available"] else "❌"
            click.echo(f"{cal['name']}: {available} (Last sync: {cal['last_sync'] or 'Never'})")


@click.group(name="sync", help="Multi-device synchronization commands")
def sync_group():
    """Multi-device sync command group"""
    pass


@sync_group.command(name="setup", help="Set up multi-device synchronization")
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
    sync_manager = SyncManager()
    
    # Create sync config
    sync_config = SyncConfig(
        provider=SyncProvider(provider),
        sync_path=path,
        auto_sync=auto,
        conflict_strategy=ConflictStrategy(conflicts)
    )
    
    # Configure sync
    success = sync_manager.configure_sync(sync_config)
    
    if success:
        click.echo(f"Sync configured successfully with {provider}.")
        click.echo("Run 'todo sync now' to perform initial synchronization.")
    else:
        click.echo(f"Failed to configure sync with {provider}. Please check settings and try again.")


@sync_group.command(name="now", help="Perform synchronization now")
@click.option("--direction", "-d", default="full",
              type=click.Choice(["push", "pull", "full"]),
              help="Sync direction")
def sync_now(direction):
    """Perform synchronization now"""
    sync_manager = SyncManager()
    
    status = None
    if direction == "push":
        click.echo("Pushing local changes to remote...")
        status = sync_manager.sync_up()
    elif direction == "pull":
        click.echo("Pulling remote changes...")
        status = sync_manager.sync_down()
    else:
        click.echo("Performing full synchronization...")
        status = sync_manager.full_sync()
    
    if status == SyncStatus.SUCCESS:
        click.echo("Synchronization completed successfully.")
    elif status == SyncStatus.CONFLICT:
        click.echo("Synchronization completed with conflicts.")
        click.echo("Run 'todo sync conflicts' to view and resolve conflicts.")
    elif status == SyncStatus.NO_CHANGES:
        click.echo("No changes to synchronize.")
    else:
        click.echo("Synchronization failed. Check logs for details.")


@sync_group.command(name="status", help="Show sync status")
def sync_status():
    """Show sync status"""
    sync_manager = SyncManager()
    
    status = sync_manager.get_sync_status()
    
    if not status["configured"]:
        click.echo("Sync not configured. Use 'todo sync setup' to configure.")
        return
    
    click.echo("Sync Status:")
    click.echo(f"Provider: {status['provider']}")
    click.echo(f"Enabled: {'Yes' if status['enabled'] else 'No'}")
    click.echo(f"Available: {'Yes' if status['available'] else 'No'}")
    
    if status["last_sync"]:
        click.echo(f"Last Sync: {status['last_sync']['timestamp']} "
                  f"({status['last_sync']['status']})")
    else:
        click.echo("Last Sync: Never")
    
    if status["pending_conflicts"] > 0:
        click.echo(f"Pending Conflicts: {status['pending_conflicts']}")
        click.echo("Run 'todo sync conflicts' to view and resolve conflicts.")
    
    click.echo(f"Device ID: {status['device_id']}")


@sync_group.command(name="conflicts", help="List and resolve sync conflicts")
@click.option("--resolve", "-r", help="Resolve conflict with specified todo ID")
@click.option("--using", "-u", type=click.Choice(["local", "remote", "merge"]),
              help="Resolution strategy (required with --resolve)")
def sync_conflicts(resolve, using):
    """List and resolve sync conflicts"""
    sync_manager = SyncManager()
    
    if resolve:
        if not using:
            click.echo("Error: --using option is required with --resolve")
            return
        
        try:
            todo_id = int(resolve)
            success = sync_manager.resolve_conflict_manually(todo_id, using)
            
            if success:
                click.echo(f"Conflict for todo {todo_id} resolved using {using} version.")
            else:
                click.echo(f"Failed to resolve conflict for todo {todo_id}.")
        except ValueError:
            click.echo("Error: todo ID must be a number")
        
        return
    
    # List conflicts
    conflicts = sync_manager.get_pending_conflicts()
    
    if not conflicts:
        click.echo("No pending conflicts.")
        return
    
    click.echo(f"Pending Conflicts ({len(conflicts)}):")
    
    for conflict in conflicts:
        todo_id = conflict["todo_id"]
        local = conflict["local_todo"]
        remote = conflict["remote_todo"]
        
        click.echo(f"\nConflict for todo {todo_id}:")
        
        if local:
            click.echo(f"  Local: {local['text']}")
            click.echo(f"    Modified: {local['modified']}")
        
        if remote:
            click.echo(f"  Remote: {remote['text']}")
            click.echo(f"    Modified: {remote['modified']}")
        
        click.echo(f"  Resolve with: todo sync conflicts --resolve {todo_id} --using [local|remote|merge]")


@sync_group.command(name="history", help="Show sync history")
@click.option("--limit", "-l", default=10, help="Limit number of entries")
def sync_history(limit):
    """Show sync history"""
    sync_manager = SyncManager()
    
    history = sync_manager.get_sync_history(limit)
    
    if not history:
        click.echo("No sync history.")
        return
    
    click.echo(f"Sync History (last {min(limit, len(history))} entries):")
    
    for event in history:
        timestamp = event["timestamp"]
        event_type = event["event_type"]
        status = event["status"]
        changes = event["changes_count"]
        conflicts = event["conflicts_count"]
        
        status_emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        
        click.echo(f"{status_emoji} {timestamp} - {event_type.upper()}: "
                  f"{changes} changes, {conflicts} conflicts")
        
        if event["error_message"]:
            click.echo(f"  Error: {event['error_message']}")


if __name__ == "__main__":
    # For testing
    config = get_config()
    todo_manager = TodoManager(config)
    calendar_sync = CalendarSync()
    sync_manager = SyncManager(todo_manager)