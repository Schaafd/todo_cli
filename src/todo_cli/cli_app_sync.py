"""CLI commands for app sync management.

This module provides command-line interface for managing synchronization
with external todo applications and services.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rich_print

from .app_sync_manager import AppSyncManager
from .app_sync_models import AppSyncProvider, AppSyncConfig, ConflictStrategy, SyncDirection
from .credential_manager import CredentialManager
from .sync_mapping_store import SyncMappingStore
from .adapters import TodoistAdapter
from .storage import get_storage
from .theme import get_theme

console = Console()
theme = get_theme()


def get_app_sync_manager() -> AppSyncManager:
    """Get initialized app sync manager."""
    storage = get_storage()
    return AppSyncManager(storage)


@click.group(name="app-sync")
def app_sync_group():
    """Manage synchronization with external todo applications."""
    pass


@app_sync_group.command("setup")
@click.argument("provider", type=click.Choice([p.value for p in AppSyncProvider]), required=False)
@click.option("--interactive/--no-interactive", default=None, 
              help="Use interactive setup. Auto-detected if not specified.")
@click.option("--api-token", help="API token for authentication")
@click.option("--auto-sync/--no-auto-sync", default=True, help="Enable auto-sync")
@click.option("--conflict-strategy", type=click.Choice([s.value for s in ConflictStrategy]), 
              default="newest_wins", help="Default conflict resolution strategy")
@click.option("--skip-mapping", is_flag=True, help="Skip project mapping even in interactive mode")
@click.option("--timeout", type=int, default=60, help="Timeout in seconds for network operations")
def setup_provider(provider: Optional[str], interactive: Optional[bool], api_token: Optional[str], 
                  auto_sync: bool, conflict_strategy: str, skip_mapping: bool, timeout: int):
    """Set up synchronization with an external provider."""
    
    if not provider and interactive:
        # Show available providers
        console.print("\n[bold cyan]Available Providers:[/bold cyan]")
        providers_table = Table(show_header=True, header_style="bold magenta")
        providers_table.add_column("Provider", style="cyan")
        providers_table.add_column("Status", justify="center")
        providers_table.add_column("Description")
        
        providers_info = {
            AppSyncProvider.TODOIST: ("✅", "Popular todo app with projects and labels"),
            AppSyncProvider.APPLE_REMINDERS: ("🚧", "macOS/iOS built-in reminders app"),
            AppSyncProvider.TICKTICK: ("🚧", "Cross-platform todo app with calendar integration"),
            AppSyncProvider.NOTION: ("🚧", "All-in-one workspace with database support"),
            AppSyncProvider.MICROSOFT_TODO: ("🚧", "Microsoft's task management app"),
            AppSyncProvider.GOOGLE_TASKS: ("🚧", "Google's simple task management"),
        }
        
        for prov, (status, desc) in providers_info.items():
            providers_table.add_row(prov.value, status, desc)
        
        console.print(providers_table)
        
        provider_choices = [p.value for p in AppSyncProvider]
        provider = Prompt.ask("\nSelect a provider", choices=provider_choices)
    
    if not provider:
        console.print("[red]Provider is required[/red]")
        return
    
    provider_enum = AppSyncProvider(provider)
    
    # Auto-detect interactive mode if not specified
    if interactive is None:
        import sys
        interactive = sys.stdin.isatty()
        if not interactive:
            console.print("[yellow]Non-interactive environment detected. Running in non-interactive mode.[/yellow]")
        else:
            console.print("[dim]Interactive environment detected.[/dim]")
            
    try:
        asyncio.run(_setup_provider_async(provider_enum, interactive, api_token, auto_sync, 
                                        conflict_strategy, skip_mapping, timeout))
    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled by user (Ctrl+C)[/yellow]")
    except asyncio.TimeoutError:
        console.print("\n[red]Setup timed out. Try again with --no-interactive or increase --timeout.[/red]")
    except Exception as e:
        console.print(f"\n[red]Setup failed: {e}[/red]")
        import traceback
        console.print("[dim]Stack trace (for debugging):[/dim]")
        console.print(traceback.format_exc())


async def _setup_provider_async(provider: AppSyncProvider, interactive: bool, api_token: Optional[str],
                               auto_sync: bool, conflict_strategy: str, skip_mapping: bool = False,
                               timeout: int = 60):
    """Async setup implementation."""
    console.print(f"\n[bold cyan]Setting up {provider.value.replace('_', ' ').title()}[/bold cyan]")
    
    # Check if we're in a non-interactive environment but interactive mode was requested
    import sys
    if interactive and not sys.stdin.isatty():
        console.print("[yellow]⚠️  Non-interactive environment detected but interactive mode requested.[/yellow]")
        console.print("[yellow]   Falling back to non-interactive mode.[/yellow]")
        interactive = False
    
    # Get credential manager
    cred_manager = CredentialManager()
    
    if not cred_manager.is_keyring_available():
        console.print("[yellow]⚠️  Keyring not available - credentials will be stored as environment variables[/yellow]")
    
    # Provider-specific setup
    if provider == AppSyncProvider.TODOIST:
        success = await _setup_todoist(cred_manager, interactive, api_token, auto_sync, 
                                     conflict_strategy, skip_mapping, timeout)
    else:
        console.print(f"[red]Provider {provider.value} is not yet implemented[/red]")
        return
    
    if success:
        console.print(f"[green]✅ {provider.value.replace('_', ' ').title()} setup completed successfully![/green]")
        
        # Ask about first sync
        if interactive and Confirm.ask("Would you like to run an initial sync now?"):
            await _run_sync_command(provider.value)
    else:
        console.print(f"[red]❌ {provider.value.replace('_', ' ').title()} setup failed[/red]")


async def _setup_todoist(cred_manager: CredentialManager, interactive: bool, api_token: Optional[str],
                        auto_sync: bool, conflict_strategy: str, skip_mapping: bool = False,
                        timeout: int = 60) -> bool:
    """Set up Todoist synchronization."""
    
    # Get API token
    if not api_token and interactive:
        console.print("\n[bold cyan]Todoist Setup[/bold cyan]")
        console.print("1. Go to: [link]https://todoist.com/prefs/integrations[/link]")
        console.print("2. Copy your API token")
        console.print("3. Paste it below (input will be hidden)")
        
        api_token = Prompt.ask("Enter your Todoist API token", password=True)
    
    if not api_token:
        console.print("[red]API token is required for Todoist[/red]")
        return False
    
    # Store credentials
    if not cred_manager.store_credential(AppSyncProvider.TODOIST, "api_token", api_token):
        console.print("[red]Failed to store API token[/red]")
        return False
    
    # Test connection
    console.print("\n[yellow]Testing connection...[/yellow]")
    
    config = AppSyncConfig(
        provider=AppSyncProvider.TODOIST,
        auto_sync=auto_sync,
        conflict_strategy=ConflictStrategy(conflict_strategy)
    )
    config.set_credential("api_token", api_token)
    
    try:
        adapter = TodoistAdapter(config)
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task("Connecting to Todoist...", total=None)
            
            # Add timeout to authentication
            try:
                auth_result = await asyncio.wait_for(adapter.authenticate(), timeout=timeout)
                if auth_result:
                    progress.update(task, description="✅ Connected to Todoist")
                    console.print("[green]✅ Connection successful[/green]")
                    
                    # Get user info and projects with timeout
                    from .adapters.todoist_adapter import TodoistAPI
                    async with TodoistAPI(api_token) as api:
                        console.print("Fetching user info and projects...")
                        user_info = await asyncio.wait_for(api.get_user_info(), timeout=timeout)
                        projects = await asyncio.wait_for(api.get_projects(), timeout=timeout)
                    
                    console.print(f"Connected as: [bold cyan]{user_info.get('full_name', 'Unknown User')}[/bold cyan]")
                    console.print(f"Found {len(projects)} Todoist projects")
                    
                    # Setup project mapping if interactive and not explicitly skipped
                    if interactive and projects and not skip_mapping:
                        console.print("\n[bold cyan]Project Mapping[/bold cyan]")
                        console.print("You'll now be asked to map your local projects to Todoist projects.")
                        console.print("This helps sync your todos between systems.")
                        console.print("[dim](Use --skip-mapping to skip this step)[/dim]\n")
                        
                        # Ask for confirmation before starting interactive mapping
                        if not Confirm.ask("Proceed with project mapping?", default=True):
                            console.print("[yellow]Project mapping skipped by user[/yellow]")
                        else:
                            await _setup_project_mapping(config, projects)
                    elif skip_mapping:
                        console.print("[yellow]Project mapping skipped (--skip-mapping)[/yellow]")
                    elif not interactive:
                        console.print("[yellow]Project mapping skipped (non-interactive mode)[/yellow]")
                    
                    # Save configuration
                    await _save_sync_config(config)
                    
                    return True
                else:
                    console.print("[red]❌ Authentication failed[/red]")
                    return False
                    
            except asyncio.TimeoutError:
                progress.update(task, description="❌ Connection timed out")
                console.print(f"[red]❌ Connection timed out after {timeout} seconds[/red]")
                console.print("Try again with a longer timeout: --timeout <seconds>")
                return False
                
    except Exception as e:
        console.print(f"[red]❌ Connection failed: {e}[/red]")
        return False


async def _setup_project_mapping(config: AppSyncConfig, todoist_projects: List[Dict]):
    """Set up project mapping between local and Todoist projects."""
    console.print("\n[bold cyan]Project Mapping Setup[/bold cyan]")
    
    # Get local projects
    storage = get_storage()
    local_projects = set()
    
    console.print("[dim]Scanning for local projects...[/dim]")
    
    # Get projects from existing todos
    try:
        for project_name in storage.get_all_projects():
            local_projects.add(project_name)
            
        console.print(f"[green]Found {len(local_projects)} local projects[/green]")
        
        if not local_projects:
            console.print("No local projects found. You can set up mapping later using 'todo app-sync map-project'")
            return
    except Exception as e:
        console.print(f"[red]Error reading local projects: {e}[/red]")
        console.print("You can set up mapping later using 'todo app-sync map-project'")
        return
    
    # Show available Todoist projects
    todoist_table = Table(title="Available Todoist Projects")
    todoist_table.add_column("ID", style="dim")
    todoist_table.add_column("Name", style="cyan")
    todoist_table.add_column("Color", style="dim")
    
    for project in todoist_projects:
        todoist_table.add_row(
            str(project.get('id', '')),
            project.get('name', ''),
            project.get('color', 'none')
        )
    
    console.print(todoist_table)
    
    # Offer bulk mapping option to save time
    if len(local_projects) > 3 and len(todoist_projects) > 0:
        console.print("\n[yellow]You have many local projects. Would you like to map them all at once?[/yellow]")
        if Confirm.ask("Map all projects to a single Todoist project?"):
            # Show Todoist projects for selection
            project_choices = [p['name'] for p in todoist_projects]
            
            todoist_project = Prompt.ask(
                "Select a Todoist project for ALL local projects",
                choices=project_choices
            )
            
            # Find project ID
            project_id = None
            for p in todoist_projects:
                if p['name'] == todoist_project:
                    project_id = p['id']
                    break
                    
            if project_id:
                # Map all projects to this one
                for local_project in sorted(local_projects):
                    config.project_mappings[local_project] = str(project_id)
                    
                console.print(f"✅ Mapped {len(local_projects)} projects to '{todoist_project}'")
                return
    
    # Individual project mapping
    console.print("\n[cyan]Individual Project Mapping[/cyan]")
    console.print("[dim](Answer y/n for each project, then select the Todoist project)[/dim]")
    
    # Set up mappings
    for local_project in sorted(local_projects):
        console.print(f"\nProject: [bold]{local_project}[/bold]")
        if Confirm.ask(f"Map this project to Todoist?"):
            # Get Todoist project choices
            project_choices = [p['name'] for p in todoist_projects]
            project_choices.append("skip")
            
            todoist_project = Prompt.ask(
                f"Select Todoist project for '{local_project}'",
                choices=project_choices,
                default="skip"
            )
            
            if todoist_project != "skip":
                # Find project ID
                project_id = None
                for p in todoist_projects:
                    if p['name'] == todoist_project:
                        project_id = p['id']
                        break
                
                if project_id:
                    config.project_mappings[local_project] = str(project_id)
                    console.print(f"✅ Mapped '{local_project}' → '{todoist_project}'")
            else:
                console.print("[dim]Skipped[/dim]")
        else:
            console.print("[dim]Skipped[/dim]")


async def _save_sync_config(config: AppSyncConfig):
    """Save sync configuration."""
    from .app_sync_config import get_app_sync_config_manager, ProviderSettings
    
    config_manager = get_app_sync_config_manager()
    
    # Create provider settings from the config
    settings = ProviderSettings(
        enabled=config.enabled,
        auto_sync=config.auto_sync,
        sync_interval=config.sync_interval,
        sync_direction=config.sync_direction,
        conflict_strategy=config.conflict_strategy,
        sync_completed_tasks=config.sync_completed_tasks,
        sync_archived_tasks=config.sync_archived_tasks,
        project_mappings=config.project_mappings,
        tag_mappings=config.tag_mappings,
        max_retries=config.max_retries,
        timeout_seconds=config.timeout_seconds,
        rate_limit_requests_per_minute=config.rate_limit_requests_per_minute,
        batch_size=config.batch_size,
        settings=config.settings
    )
    
    config_manager.set_provider_settings(config.provider, settings)
    console.print(f"[dim]Configuration saved for {config.provider.value}[/dim]")


@app_sync_group.command("doctor")
def app_sync_doctor():
    """Run diagnostics to troubleshoot app sync issues."""
    try:
        asyncio.run(_run_app_sync_doctor())
    except Exception as e:
        console.print(f"[red]Doctor check failed: {e}[/red]")


async def _run_app_sync_doctor():
    """Run comprehensive app sync diagnostics."""
    console.print("\n[bold cyan]🩺 Todo CLI App Sync Doctor[/bold cyan]\n")
    
    checks_passed = 0
    total_checks = 0
    
    # Check 1: Environment
    total_checks += 1
    console.print("[cyan]1. Environment Check[/cyan]")
    import sys
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"   Python version: {python_version}")
    console.print(f"   Interactive TTY: {sys.stdin.isatty()}")
    checks_passed += 1
    console.print("   ✅ Environment OK\n")
    
    # Check 2: Configuration directory
    total_checks += 1
    console.print("[cyan]2. Configuration Directory[/cyan]")
    config_dir = Path.home() / ".todo"
    try:
        if config_dir.exists():
            console.print(f"   Config dir: {config_dir} (exists)")
            console.print(f"   Writable: {os.access(config_dir, os.W_OK)}")
        else:
            console.print(f"   Config dir: {config_dir} (missing)")
        checks_passed += 1
        console.print("   ✅ Config directory OK\n")
    except Exception as e:
        console.print(f"   ❌ Config directory error: {e}\n")
    
    # Check 3: Network connectivity
    total_checks += 1
    console.print("[cyan]3. Network Connectivity[/cyan]")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.todoist.com/")
            console.print(f"   Todoist API: {response.status_code}")
            checks_passed += 1
            console.print("   ✅ Network OK\n")
    except Exception as e:
        console.print(f"   ❌ Network error: {e}\n")
    
    # Check 4: Credentials
    total_checks += 1
    console.print("[cyan]4. Credentials Check[/cyan]")
    api_token = os.getenv('TODOIST_API_TOKEN')
    if api_token:
        console.print(f"   TODOIST_API_TOKEN: Set ({len(api_token)} chars)")
        
        # Test token validity
        try:
            from .adapters.todoist_adapter import TodoistAPI
            async with TodoistAPI(api_token) as api:
                user_info = await asyncio.wait_for(api.get_user_info(), timeout=10.0)
                console.print(f"   Token valid for: {user_info.get('full_name', 'Unknown')}")
                checks_passed += 1
                console.print("   ✅ Credentials OK\n")
        except Exception as e:
            console.print(f"   ❌ Token validation failed: {e}\n")
    else:
        console.print("   TODOIST_API_TOKEN: Not set")
        console.print("   ❌ No API token found\n")
    
    # Summary
    console.print(f"[bold]Summary: {checks_passed}/{total_checks} checks passed[/bold]")
    
    if checks_passed == total_checks:
        console.print("\n🎉 [green]All checks passed! App sync should work correctly.[/green]")
    else:
        console.print("\n⚠️ [yellow]Some checks failed. See above for issues to fix.[/yellow]")
        
        # Provide suggestions
        console.print("\n[bold cyan]Suggestions:[/bold cyan]")
        if not api_token:
            console.print("• Set TODOIST_API_TOKEN: export TODOIST_API_TOKEN='your_token'")
            console.print("• Get token from: https://todoist.com/prefs/integrations")
        console.print("• Try non-interactive setup: --no-interactive")
        console.print("• Use timeout flag: --timeout 120")
        console.print("• Skip project mapping: --skip-mapping")


@app_sync_group.command("status")
@click.option("--detailed", "-d", is_flag=True, help="Show detailed status information")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def sync_status(detailed: bool, output_json: bool):
    """Show synchronization status for all providers."""
    try:
        asyncio.run(_show_sync_status(detailed, output_json))
    except Exception as e:
        console.print(f"[red]Failed to get sync status: {e}[/red]")


async def _show_sync_status(detailed: bool, output_json: bool):
    """Show sync status implementation."""
    manager = get_app_sync_manager()
    status = manager.get_sync_status()
    
    if output_json:
        console.print(json.dumps(status, indent=2, default=str))
        return
    
    # Create status display
    console.print("\n[bold cyan]App Sync Status[/bold cyan]")
    
    if not status['providers']:
        console.print("[yellow]No providers configured[/yellow]")
        console.print("Run 'todo app-sync setup <provider>' to get started")
        return
    
    # Summary panel
    summary_text = f"""
    [cyan]Providers:[/cyan] {status['total_registered']} registered, {status['total_enabled']} enabled
    [cyan]Active syncs:[/cyan] {status['active_operations']}
    """
    
    console.print(Panel(summary_text.strip(), title="Summary", border_style="cyan"))
    
    # Provider details
    for provider_name, provider_status in status['providers'].items():
        _display_provider_status(provider_name, provider_status, detailed)


def _display_provider_status(provider_name: str, provider_status: Dict[str, Any], detailed: bool):
    """Display status for a single provider."""
    # Status indicators
    if not provider_status['enabled']:
        status_icon = "⏸️"
        status_text = "[dim]Disabled[/dim]"
    elif provider_status['is_syncing']:
        status_icon = "🔄"
        status_text = "[yellow]Syncing...[/yellow]"
    elif provider_status['last_sync_status'] == 'success':
        status_icon = "✅"
        status_text = "[green]Connected[/green]"
    elif provider_status['last_sync_status'] == 'error':
        status_icon = "❌"
        status_text = "[red]Error[/red]"
    else:
        status_icon = "❓"
        status_text = "[dim]Unknown[/dim]"
    
    # Create provider table
    provider_table = Table(title=f"{status_icon} {provider_status['provider_name']}")
    provider_table.add_column("Property", style="cyan")
    provider_table.add_column("Value")
    
    # Basic info
    provider_table.add_row("Status", status_text)
    provider_table.add_row("Auto-sync", "✅" if provider_status['auto_sync'] else "❌")
    provider_table.add_row("Sync direction", provider_status['sync_direction'])
    provider_table.add_row("Conflict strategy", provider_status['conflict_strategy'])
    
    # Last sync info
    if provider_status['last_sync']:
        last_sync = datetime.fromisoformat(provider_status['last_sync'])
        time_ago = _format_time_ago(datetime.now() - last_sync.replace(tzinfo=None))
        provider_table.add_row("Last sync", f"{time_ago} ago")
        
        if provider_status['last_sync_duration']:
            duration = f"{provider_status['last_sync_duration']:.1f}s"
            provider_table.add_row("Duration", duration)
    else:
        provider_table.add_row("Last sync", "[dim]Never[/dim]")
    
    # Stats
    if 'items_synced' in provider_status:
        provider_table.add_row("Items synced", str(provider_status['items_synced']))
        provider_table.add_row("Conflicts", str(provider_status['conflicts_detected']))
        provider_table.add_row("Errors", str(provider_status['errors']))
    
    # Features (if detailed)
    if detailed:
        features = ", ".join(provider_status['supported_features'])
        provider_table.add_row("Features", features)
    
    console.print(provider_table)


def _format_time_ago(delta):
    """Format time delta in human-readable form."""
    seconds = int(delta.total_seconds())
    
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m"
    elif seconds < 86400:
        return f"{seconds // 3600}h"
    else:
        return f"{seconds // 86400}d"


@app_sync_group.command("sync")
@click.argument("provider", type=click.Choice([p.value for p in AppSyncProvider]), required=False)
@click.option("--all", "sync_all", is_flag=True, help="Sync all enabled providers")
@click.option("--strategy", type=click.Choice([s.value for s in ConflictStrategy]), 
              help="Override conflict resolution strategy")
def sync_command(provider: Optional[str], sync_all: bool, strategy: Optional[str]):
    """Manually trigger synchronization."""
    try:
        if sync_all:
            asyncio.run(_sync_all_providers(strategy))
        elif provider:
            asyncio.run(_run_sync_command(provider, strategy))
        else:
            console.print("[yellow]Specify a provider or use --all to sync all providers[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Sync cancelled[/yellow]")
    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/red]")


async def _sync_all_providers(strategy_override: Optional[str]):
    """Sync all enabled providers."""
    manager = get_app_sync_manager()
    
    conflict_strategy = ConflictStrategy(strategy_override) if strategy_override else None
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Syncing all providers...", total=None)
        
        results = await manager.sync_all(conflict_strategy)
        
        if not results:
            progress.update(task, description="No enabled providers found")
            console.print("[yellow]No enabled providers to sync[/yellow]")
            return
        
        progress.update(task, description=f"Synced {len(results)} providers")
    
    # Display results
    console.print(f"\n[bold cyan]Sync Results[/bold cyan]")
    
    results_table = Table()
    results_table.add_column("Provider", style="cyan")
    results_table.add_column("Status", justify="center")
    results_table.add_column("Items", justify="right")
    results_table.add_column("Conflicts", justify="right")
    results_table.add_column("Duration", justify="right")
    
    for provider, result in results.items():
        # Status icon
        if result.status.value == 'success':
            status_icon = "✅"
        elif result.status.value == 'error':
            status_icon = "❌"
        else:
            status_icon = "⚠️"
        
        items_text = f"{result.items_created}+{result.items_updated}+{result.items_deleted}"
        duration_text = f"{result.duration_seconds:.1f}s"
        
        results_table.add_row(
            provider.value,
            status_icon,
            items_text,
            str(result.conflicts_detected),
            duration_text
        )
    
    console.print(results_table)
    
    # Show errors if any
    for provider, result in results.items():
        if result.errors:
            console.print(f"\n[red]Errors for {provider.value}:[/red]")
            for error in result.errors:
                console.print(f"  • {error}")


async def _run_sync_command(provider: str, strategy_override: Optional[str] = None):
    """Run sync for a specific provider."""
    manager = get_app_sync_manager()
    provider_enum = AppSyncProvider(provider)
    
    conflict_strategy = ConflictStrategy(strategy_override) if strategy_override else None
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task(f"Syncing {provider}...", total=None)
        
        try:
            result = await manager.sync_provider(provider_enum, conflict_strategy)
            progress.update(task, description=f"✅ Sync completed")
        except ValueError as e:
            progress.update(task, description=f"❌ {e}")
            console.print(f"[red]{e}[/red]")
            return
    
    # Display result
    _display_sync_result(provider, result)


def _display_sync_result(provider: str, result):
    """Display sync result for a single provider."""
    console.print(f"\n[bold cyan]{provider.replace('_', ' ').title()} Sync Result[/bold cyan]")
    
    # Status
    if result.status.value == 'success':
        console.print("[green]✅ Sync successful[/green]")
    elif result.status.value == 'error':
        console.print("[red]❌ Sync failed[/red]")
    else:
        console.print(f"[yellow]⚠️ Sync {result.status.value}[/yellow]")
    
    # Stats
    stats_table = Table()
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Count", justify="right")
    
    stats_table.add_row("Items created", str(result.items_created))
    stats_table.add_row("Items updated", str(result.items_updated))
    stats_table.add_row("Items deleted", str(result.items_deleted))
    stats_table.add_row("Conflicts detected", str(result.conflicts_detected))
    stats_table.add_row("Conflicts resolved", str(result.conflicts_resolved))
    stats_table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    
    console.print(stats_table)
    
    # Errors and warnings
    if result.errors:
        console.print("\n[red]Errors:[/red]")
        for error in result.errors:
            console.print(f"  • {error}")
    
    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")


@app_sync_group.command("enable")
@click.argument("provider", type=click.Choice([p.value for p in AppSyncProvider]))
def enable_provider(provider: str):
    """Enable synchronization for a provider."""
    from .app_sync_config import get_app_sync_config_manager
    
    provider_enum = AppSyncProvider(provider)
    config_manager = get_app_sync_config_manager()
    
    config_manager.enable_provider(provider_enum)
    console.print(f"[green]✅ Enabled {provider.replace('_', ' ').title()}[/green]")


@app_sync_group.command("disable")
@click.argument("provider", type=click.Choice([p.value for p in AppSyncProvider]))
def disable_provider(provider: str):
    """Disable synchronization for a provider."""
    from .app_sync_config import get_app_sync_config_manager
    
    provider_enum = AppSyncProvider(provider)
    config_manager = get_app_sync_config_manager()
    
    config_manager.disable_provider(provider_enum)
    console.print(f"[yellow]⏸️ Disabled {provider.replace('_', ' ').title()}[/yellow]")


@app_sync_group.command("map-project")
@click.argument("provider", type=click.Choice([p.value for p in AppSyncProvider]))
@click.argument("local_project")
@click.argument("external_project")
def map_project(provider: str, local_project: str, external_project: str):
    """Map a local project to an external provider project."""
    from .app_sync_config import get_app_sync_config_manager
    
    provider_enum = AppSyncProvider(provider)
    config_manager = get_app_sync_config_manager()
    
    config_manager.add_project_mapping(provider_enum, local_project, external_project)
    console.print(f"[green]✅ Mapped '{local_project}' → '{external_project}' for {provider}[/green]")


@app_sync_group.command("conflicts")
@click.option("--provider", type=click.Choice([p.value for p in AppSyncProvider]), 
              help="Show conflicts for specific provider")
@click.option("--resolve", is_flag=True, help="Interactively resolve conflicts")
def show_conflicts(provider: Optional[str], resolve: bool):
    """Show and optionally resolve sync conflicts."""
    try:
        asyncio.run(_handle_conflicts(provider, resolve))
    except Exception as e:
        console.print(f"[red]Failed to handle conflicts: {e}[/red]")


async def _handle_conflicts(provider: Optional[str], resolve: bool):
    """Handle sync conflicts."""
    mapping_store = SyncMappingStore()
    
    if provider:
        provider_enum = AppSyncProvider(provider)
        conflicts = await mapping_store.get_conflicts_for_provider(provider_enum, resolved=False)
    else:
        conflicts = await mapping_store.get_all_conflicts(resolved=False)
    
    if not conflicts:
        console.print("[green]✅ No unresolved conflicts[/green]")
        return
    
    console.print(f"\n[bold cyan]Found {len(conflicts)} unresolved conflicts[/bold cyan]")
    
    # Display conflicts
    for i, conflict in enumerate(conflicts, 1):
        console.print(f"\n[bold yellow]Conflict {i}/{len(conflicts)}[/bold yellow]")
        console.print(f"Provider: {conflict.provider.value}")
        console.print(f"Type: {conflict.conflict_type.value}")
        console.print(f"Todo ID: {conflict.todo_id}")
        console.print(f"Detected: {conflict.detected_at.strftime('%Y-%m-%d %H:%M:%S')}")
        console.print(f"Description: {conflict.describe()}")
        
        if resolve:
            # Interactive resolution
            choices = ["local", "remote", "skip", "quit"]
            action = Prompt.ask(
                "Resolution action",
                choices=choices,
                default="skip"
            )
            
            if action == "quit":
                break
            elif action == "local":
                conflict.resolve("local_wins")
                await mapping_store.save_conflict(conflict)
                console.print("[green]✅ Resolved: keeping local version[/green]")
            elif action == "remote":
                conflict.resolve("remote_wins")
                await mapping_store.save_conflict(conflict)
                console.print("[green]✅ Resolved: keeping remote version[/green]")
            else:
                console.print("[dim]Skipped[/dim]")


@app_sync_group.command("list")
def list_providers():
    """List all available and configured providers."""
    console.print("\n[bold cyan]Available Providers[/bold cyan]")
    
    # This would show configured vs available providers
    manager = get_app_sync_manager()
    status = manager.get_sync_status()
    
    all_providers = list(AppSyncProvider)
    configured_providers = [AppSyncProvider(name) for name in status['providers'].keys()]
    
    providers_table = Table()
    providers_table.add_column("Provider", style="cyan")
    providers_table.add_column("Status", justify="center")
    providers_table.add_column("Implementation", justify="center")
    
    for provider in all_providers:
        if provider in configured_providers:
            status_icon = "✅ Configured"
        else:
            status_icon = "⚪ Available"
        
        # Implementation status
        if provider == AppSyncProvider.TODOIST:
            impl_status = "✅ Complete"
        else:
            impl_status = "🚧 Coming Soon"
        
        providers_table.add_row(
            provider.value.replace('_', ' ').title(),
            status_icon,
            impl_status
        )
    
    console.print(providers_table)


# Export the command group
__all__ = ['app_sync_group']