"""Theme management CLI commands.

This module provides CLI commands for managing themes, including listing,
previewing, setting, and customizing themes.
"""

import click
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.align import Align

from ..theme_engine import ThemeEngine, IconPack
from ..config import get_config


@click.group()
def theme():
    """Manage themes and visual styling."""
    pass


@theme.command()
def list():
    """List all available themes."""
    try:
        config = get_config()
        engine = ThemeEngine.from_config(config)
        console = engine.get_console()
        
        themes = engine.list_themes()
        current_theme = config.theme_name
        
        # Create table of themes
        table = Table(
            title="Available Themes",
            show_header=True,
            header_style="bright"
        )
        
        table.add_column("Name", style="cyan", min_width=15)
        table.add_column("Type", style="blue", width=8)
        table.add_column("Description", style="default")
        table.add_column("Variants", style="magenta")
        
        for theme_info in themes:
            if theme_info.get('error'):
                continue
                
            theme_type = theme_info.get('type', 'unknown')
            variants = theme_info.get('variants', [])
            variant_text = ', '.join(variants) if variants else "none"
            
            # Highlight current theme
            name_style = "cyan bold" if theme_info['name'] == current_theme else "cyan"
            
            table.add_row(
                f"[{name_style}]{theme_info['name']}[/{name_style}]",
                theme_type,
                theme_info.get('description', ''),
                variant_text
            )
        
        console.print()
        console.print(table)
        console.print()
        
        # Show quick usage hint with terminal background guidance
        usage_text = Text.assemble(
            ("💡 Tip: Use ", "dim"),
            ("todo theme preview <name>", "cyan"),
            (" to see how a theme looks, or ", "dim"),
            ("todo theme set <name>", "cyan"),
            (" to apply it.", "dim")
        )
        
        guidance_text = Text.assemble(
            ("🎯 Theme Selection Guide:\n", "yellow"),
            ("• Dark terminal: ", "dim"),
            ("city_lights, dracula, gruvbox_dark, nord, solarized_dark", "cyan"),
            ("\n• Light terminal: ", "dim"),
            ("one_light", "cyan")
        )
        
        combined_panel = Panel(
            Text.assemble(
                usage_text, "\n\n", guidance_text
            ),
            title="[cyan]Theme Help[/cyan]",
            border_style="blue",
            padding=(1, 2)
        )
        console.print(combined_panel)
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error listing themes: {e}[/red]")
        sys.exit(1)


@theme.command()
@click.argument('name')
@click.option('--variant', help='Theme variant to preview')
def preview(name: str, variant: Optional[str]):
    """Preview a theme without applying it."""
    try:
        engine = ThemeEngine.from_name(name, variant)
        console = engine.get_console()
        tokens = engine.get_theme_tokens(name, variant)
        
        # Show theme preview
        console.print(f"\n[header]Theme Preview: {name}[/header]")
        if variant:
            console.print(f"[subheader]Variant: {variant}[/subheader]")
        
        console.print()
        
        # Sample content sections
        sections = []
        
        # Status examples
        status_panel = Panel(
            Text.assemble(
                ("✅ ", "todo_completed"), ("Completed task", "todo_completed"), "\n",
                ("⏳ ", "todo_pending"), ("Pending task", "todo_pending"), "\n", 
                ("⭐ ", "todo_pinned"), ("Pinned important task", "todo_pinned"), "\n",
                ("❌ ", "todo_overdue"), ("Overdue task", "todo_overdue")
            ),
            title="[panel_title]Task Status[/panel_title]",
            border_style="border"
        )
        sections.append(status_panel)
        
        # Priority examples  
        priority_panel = Panel(
            Text.assemble(
                ("🔴 ", "priority_critical"), ("Critical priority", "priority_critical"), "\n",
                ("🟡 ", "priority_high"), ("High priority", "priority_high"), "\n",
                ("🔵 ", "priority_medium"), ("Medium priority", "priority_medium"), "\n", 
                ("⚪ ", "priority_low"), ("Low priority", "priority_low")
            ),
            title="[panel_title]Priorities[/panel_title]",
            border_style="border"
        )
        sections.append(priority_panel)
        
        # Metadata examples
        metadata_panel = Panel(
            Text.assemble(
                ("🏷️ ", "tag"), ("@work @urgent", "tag"), "\n",
                ("👤 ", "assignee"), ("+john +sarah", "assignee"), "\n",
                ("📅 ", "due_date"), ("Due: 2024-01-15", "due_date"), "\n",
                ("⏰ ", "due_date_overdue"), ("Overdue: 2024-01-10", "due_date_overdue")
            ),
            title="[panel_title]Metadata[/panel_title]", 
            border_style="border"
        )
        sections.append(metadata_panel)
        
        # Display preview in columns
        console.print(Columns(sections, equal=True, expand=True))
        
        # Color palette info
        console.print(f"\n[subheader]Color Palette[/subheader]")
        
        palette_items = []
        for token_name, token_value in sorted(tokens.items()):
            if any(x in token_name for x in ['primary', 'secondary', 'accent', 'success', 'warning', 'error', 'critical']):
                palette_items.append(f"[{token_name}]{token_name}[/{token_name}]")
        
        if palette_items:
            console.print(" • ".join(palette_items[:8]))  # Show first 8 colors
        
        console.print()
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error previewing theme '{name}': {e}[/red]")
        sys.exit(1)


@theme.command()
@click.argument('name')
@click.option('--variant', help='Theme variant to apply')
@click.option('--compact', is_flag=True, help='Use compact layout')
@click.option('--high-contrast', is_flag=True, help='Use high contrast variant')
@click.option('--colorblind-safe', is_flag=True, help='Use colorblind-safe palette')
def set(name: str, variant: Optional[str], compact: bool, high_contrast: bool, colorblind_safe: bool):
    """Set the active theme."""
    from ..config import get_config, save_config, Config
    
    try:
        # Validate theme exists
        engine = ThemeEngine.from_config(get_config())
        if not engine.theme_exists(name):
            console = Console()
            console.print(f"[red]Error: Theme '{name}' not found.[/red]")
            console.print("Use 'todo theme list' to see available themes.")
            sys.exit(1)
        
        # Get and update configuration
        config = get_config()
        config.theme_name = name
        config.theme_variant = variant
        config.theme_compact = compact
        config.theme_high_contrast = high_contrast
        config.theme_colorblind_safe = colorblind_safe
        
        # Save configuration
        save_config(config)
        
        # Clear cached config instance to force reload
        Config._instance = None
        
        # Create console with new theme
        new_engine = ThemeEngine.from_config(config)
        console = new_engine.get_console()
        
        # Success message
        console.print(f"[success]✅ Theme set to '{name}'[/success]")
        
        if variant:
            console.print(f"[primary]Variant: {variant}[/primary]")
        if compact:
            console.print("[primary]Layout: Compact[/primary]")
        if high_contrast:
            console.print("[primary]Accessibility: High contrast[/primary]")
        if colorblind_safe:
            console.print("[primary]Accessibility: Colorblind-safe palette[/primary]")
        
        console.print("\n[muted]Changes will apply to new CLI sessions.[/muted]")
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error setting theme: {e}[/red]")
        sys.exit(1)


@theme.command()
@click.argument('name')
def info(name: str):
    """Show detailed information about a theme."""
    try:
        engine = ThemeEngine.from_config(get_config())
        console = engine.get_console()
        
        theme_info = engine.get_theme_info(name)
        
        if 'error' in theme_info:
            console.print(f"[red]Error loading theme '{name}': {theme_info['error']}[/red]")
            return
        
        # Display theme information
        console.print(f"\n[bold]Theme Information: {theme_info['display_name']}[/bold]\n")
        
        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column("Property", style="blue", min_width=15)
        info_table.add_column("Value", style="default")
        
        info_table.add_row("Name", theme_info['name'])
        info_table.add_row("Author", theme_info.get('author', 'Unknown'))
        info_table.add_row("Version", theme_info.get('version', '1.0.0'))
        info_table.add_row("Type", theme_info.get('type', 'unknown'))
        info_table.add_row("Min Capability", theme_info.get('min_capability', 'color_16'))
        
        if theme_info.get('extends'):
            info_table.add_row("Extends", theme_info['extends'])
        
        console.print(info_table)
        
        # Description
        if theme_info.get('description'):
            console.print(f"\n[bright]Description[/bright]")
            console.print(theme_info['description'])
        
        # Variants
        variants = theme_info.get('variants', [])
        if variants:
            console.print(f"\n[bright]Available Variants[/bright]")
            for variant in variants:
                variant_text = f"• {variant}"
                console.print(variant_text)
        
        # Validation issues
        issues = theme_info.get('validation_issues', [])
        if issues:
            console.print(f"\n[yellow]⚠️  Validation Issues[/yellow]")
            for issue in issues:
                console.print(f"  • {issue}")
        
        console.print()
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error getting theme info: {e}[/red]")
        sys.exit(1)


# Add more commands as we implement them
@theme.command()
def validate():
    """Validate all installed themes."""
    try:
        engine = ThemeEngine.from_config(get_config())
        console = engine.get_console()
        
        themes = engine.list_themes()
        total_themes = len(themes)
        issues_found = 0
        
        console.print(f"\n[bright]Validating {total_themes} themes...[/bright]\n")
        
        for theme_info in themes:
            theme_name = theme_info['name']
            console.print(f"[cyan]Checking {theme_name}...[/cyan]", end="")
            
            if 'error' in theme_info:
                console.print(f" [red]❌ ERROR[/red]")
                console.print(f"  [red]{theme_info['error']}[/red]")
                issues_found += 1
                continue
            
            # Run validation
            validation_issues = engine.validate_theme(theme_name)
            
            if validation_issues:
                console.print(f" [yellow]⚠️  {len(validation_issues)} warning(s)[/yellow]")
                for issue in validation_issues:
                    console.print(f"  [yellow]• {issue}[/yellow]")
                issues_found += len(validation_issues)
            else:
                console.print(f" [green]✅ Valid[/green]")
        
        # Summary
        console.print()
        if issues_found == 0:
            console.print(f"[green]✅ All {total_themes} themes are valid![/green]")
        else:
            console.print(f"[yellow]⚠️  Found {issues_found} issues across {total_themes} themes.[/yellow]")
            console.print("[muted]Issues are typically accessibility warnings and don't prevent theme usage.[/muted]")
        
    except Exception as e:
        console = Console()
        console.print(f"[red]Error validating themes: {e}[/red]")
        sys.exit(1)


@theme.command()
def detect():
    """Detect terminal capabilities and suggest appropriate themes."""
    from ..theme_engine import detect_terminal_capability, TerminalCapability
    
    console = Console()
    
    # Detect terminal capability
    capability = detect_terminal_capability()
    
    console.print(f"\n[bold]Terminal Detection Results[/bold]\n")
    
    # Color capability
    capability_names = {
        TerminalCapability.MONOCHROME: "Monochrome (no colors)",
        TerminalCapability.COLOR_16: "16 colors", 
        TerminalCapability.COLOR_256: "256 colors",
        TerminalCapability.TRUECOLOR: "Truecolor (16 million colors)"
    }
    
    console.print(f"[cyan]Color Support:[/cyan] {capability_names.get(capability, 'Unknown')}")
    
    # Try to detect terminal background
    # This is tricky, but we can make educated guesses
    import os
    terminal_app = os.environ.get('TERM_PROGRAM', '').lower()
    colorterm = os.environ.get('COLORTERM', '').lower()
    
    console.print(f"[cyan]Terminal:[/cyan] {terminal_app or 'Unknown'}")
    
    # Background detection hints
    console.print("\n[yellow]🎯 Theme Recommendations:[/yellow]")
    
    if capability == TerminalCapability.MONOCHROME:
        console.print("[dim]• Your terminal doesn't support colors. All themes will appear the same.[/dim]")
    else:
        console.print("[green]• If your terminal has a dark background:[/green]")
        console.print("  [cyan]city_lights[/cyan] (default), [cyan]dracula[/cyan], [cyan]gruvbox_dark[/cyan], [cyan]nord[/cyan], [cyan]solarized_dark[/cyan]")
        console.print("\n[green]• If your terminal has a light/white background:[/green]")
        console.print("  [cyan]one_light[/cyan]")
        
        console.print("\n[yellow]💡 Not sure about your background?[/yellow]")
        console.print("  Try: [cyan]todo theme preview city_lights[/cyan] vs [cyan]todo theme preview one_light[/cyan]")
        console.print("  The one that looks better is right for your terminal!")
    
    console.print()


# Register the theme group with the main CLI
def get_theme_commands():
    """Get the theme command group for registration with main CLI."""
    return theme
