"""Theming system for Todo CLI - Backward Compatibility Layer.

This module provides backward compatibility for the legacy theming system
while delegating to the new ThemeEngine for all functionality.
"""

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from typing import Dict, Any, List, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# Import the new theme engine
try:
    from .theme_engine import ThemeEngine
    from .config import get_config
    _THEME_ENGINE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Theme engine not available, falling back to legacy: {e}")
    _THEME_ENGINE_AVAILABLE = False


# Legacy City Lights colors for fallback
CITY_LIGHTS_COLORS = {
    'background': '#1D252C',
    'surface': '#2D3B47', 
    'surface_light': '#41505E',
    'primary': '#68D5F3',
    'secondary': '#5CCFE6',
    'accent': '#B7C5D3',
    'success': '#8BD649',
    'warning': '#FFD93D',
    'error': '#F78C6C',
    'critical': '#FF5370',
    'text_primary': '#B7C5D3',
    'text_secondary': '#718CA1',
    'text_muted': '#4F5B66',
    'text_bright': '#FFFFFF',
    'keyword': '#5CCFE6',
    'string': '#8BD649',
    'number': '#F78C6C',
    'comment': '#4F5B66',
}

# Legacy Rich theme for fallback
_LEGACY_THEME = Theme({
    'default': f"{CITY_LIGHTS_COLORS['text_primary']}",
    'muted': f"{CITY_LIGHTS_COLORS['text_muted']}",
    'bright': f"{CITY_LIGHTS_COLORS['text_bright']} bold",
    'success': f"{CITY_LIGHTS_COLORS['success']} bold",
    'warning': f"{CITY_LIGHTS_COLORS['warning']} bold", 
    'error': f"{CITY_LIGHTS_COLORS['error']} bold",
    'critical': f"{CITY_LIGHTS_COLORS['critical']} bold",
    'priority_critical': f"{CITY_LIGHTS_COLORS['critical']} bold",
    'priority_high': f"{CITY_LIGHTS_COLORS['warning']}",
    'priority_medium': f"{CITY_LIGHTS_COLORS['text_primary']}",
    'priority_low': f"{CITY_LIGHTS_COLORS['text_muted']}",
    'primary': f"{CITY_LIGHTS_COLORS['primary']} bold",
    'secondary': f"{CITY_LIGHTS_COLORS['secondary']}",
    'accent': f"{CITY_LIGHTS_COLORS['accent']}",
    'todo_pending': f"{CITY_LIGHTS_COLORS['primary']}",
    'todo_completed': f"{CITY_LIGHTS_COLORS['success']}",
    'todo_pinned': f"{CITY_LIGHTS_COLORS['warning']}",
    'todo_overdue': f"{CITY_LIGHTS_COLORS['critical']}",
    'tag': f"{CITY_LIGHTS_COLORS['secondary']}",
    'assignee': f"{CITY_LIGHTS_COLORS['success']}",
    'due_date': f"{CITY_LIGHTS_COLORS['primary']}",
    'due_date_overdue': f"{CITY_LIGHTS_COLORS['critical']}",
    'header': f"{CITY_LIGHTS_COLORS['text_bright']} bold",
    'subheader': f"{CITY_LIGHTS_COLORS['accent']} bold",
    'border': f"{CITY_LIGHTS_COLORS['surface_light']}",
})

# Global theme engine instance
_theme_engine: Optional[ThemeEngine] = None


def _get_theme_engine() -> Optional[ThemeEngine]:
    """Get the global theme engine instance."""
    global _theme_engine
    
    if not _THEME_ENGINE_AVAILABLE:
        logger.debug("Theme engine not available, using legacy theming")
        return None
    
    if _theme_engine is None:
        try:
            config = get_config()
            _theme_engine = ThemeEngine.from_config(config)
            logger.debug(f"Theme engine initialized with theme: {config.theme_name}")
        except ImportError as e:
            logger.warning(f"Theme engine dependencies missing: {e}")
            return None
        except FileNotFoundError as e:
            logger.warning(f"Theme file not found: {e}. Using fallback theme.")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize theme engine: {e}")
            return None
    
    return _theme_engine


def get_productivity_ninja_theme() -> Theme:
    """Get the current theme as a Rich Theme object.
    
    This function delegates to the new theme engine if available,
    otherwise falls back to the legacy City Lights theme.
    """
    engine = _get_theme_engine()
    if engine:
        try:
            return engine.compile_rich_theme()
        except Exception as e:
            logger.error(f"Error compiling theme: {e}")
    
    # Fallback to legacy theme
    return _LEGACY_THEME


# Backward compatibility: expose as module-level variable
PRODUCTIVITY_NINJA_THEME = get_productivity_ninja_theme()


def get_ascii_title() -> str:
    """Get the ASCII art title for Productivity Ninja CLI."""
    engine = _get_theme_engine()
    if engine:
        try:
            # Try to get banner from current theme
            theme_def = engine.registry.load_theme_definition(
                engine.registry.get_default_theme_name()
            )
            if theme_def.ascii_art and theme_def.ascii_art.banner:
                return theme_def.ascii_art.banner
        except Exception as e:
            logger.debug(f"Could not load theme banner: {e}")
    
    # Fallback to default banner
    return """
 ██████╗ ██████╗  ██████╗ ██████╗ ██╗   ██╗ ██████╗████████╗██╗██╗   ██╗██╗████████╗██╗   ██╗
 ██╔══██╗██╔══██╗██╔═══██╗██╔══██╗██║   ██║██╔════╝╚══██╔══╝██║██║   ██║██║╚══██╔══╝╚██╗ ██╔╝
 ██████╔╝██████╔╝██║   ██║██║  ██║██║   ██║██║        ██║   ██║██║   ██║██║   ██║    ╚████╔╝ 
 ██╔═══╝ ██╔══██╗██║   ██║██║  ██║██║   ██║██║        ██║   ██║╚██╗ ██╔╝██║   ██║     ╚██╔╝  
 ██║     ██║  ██║╚██████╔╝██████╔╝╚██████╔╝╚██████╗   ██║   ██║ ╚████╔╝ ██║   ██║      ██║   
 ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝   ╚═╝   ╚═╝  ╚═══╝  ╚═╝   ╚═╝      ╚═╝   
                                                                                                
 ███╗   ██╗██╗███╗   ██╗     ██╗ █████╗      ██████╗██╗     ██╗                            
 ████╗  ██║██║████╗  ██║     ██║██╔══██╗    ██╔════╝██║     ██║                            
 ██╔██╗ ██║██║██╔██╗ ██║     ██║███████║    ██║     ██║     ██║                            
 ██║╚██╗██║██║██║╚██╗██║██   ██║██╔══██║    ██║     ██║     ██║                            
 ██║ ╚████║██║██║ ╚████║╚█████╔╝██║  ██║    ╚██████╗███████╗██║                            
 ╚═╝  ╚═══╝╚═╝╚═╝  ╚═══╝ ╚════╝ ╚═╝  ╚═╝     ╚═════╝╚══════╝╚═╝                            
"""


def get_themed_console() -> Console:
    """Get a console instance with the Productivity Ninja theme applied."""
    engine = _get_theme_engine()
    if engine:
        try:
            return engine.get_console()
        except Exception as e:
            logger.error(f"Error creating themed console: {e}")
    
    # Fallback to legacy console
    return Console(theme=_LEGACY_THEME)


def show_startup_banner(console: Console) -> None:
    """Display the startup banner with ASCII art and theme."""
    # Safe styling with fallbacks
    title_style = "primary"
    subtitle_style = "accent"
    version_style = "muted"
    
    # Try to use theme engine styles if available
    engine = _get_theme_engine()
    if not engine:
        # Fallback to basic Rich styles
        title_style = "cyan bold"
        subtitle_style = "blue"
        version_style = "dim"
    
    title_text = Text(get_ascii_title(), style=title_style)
    
    # Try to get theme-specific subtitle and version
    subtitle_text = "⚡ Master Your Tasks. Unleash Your Potential. ⚡"
    
    if engine:
        try:
            theme_def = engine.registry.load_theme_definition(
                engine.registry.get_default_theme_name()
            )
            if theme_def.ascii_art:
                if theme_def.ascii_art.subtitle:
                    subtitle_text = theme_def.ascii_art.subtitle
                if theme_def.ascii_art.subtitle_style:
                    subtitle_style = theme_def.ascii_art.subtitle_style
        except Exception as e:
            logger.debug(f"Could not load theme subtitle: {e}")
    
    subtitle = Text(subtitle_text, style=subtitle_style)
    version_info = Text("v1.0.0", style=version_style)
    
    # Create the banner panel with centered title
    banner_content = Align.center(title_text)
    banner_panel = Panel(
        banner_content,
        title="[bright]Welcome to[/bright]",
        subtitle=f"[{subtitle_style}]{subtitle}[/{subtitle_style}]\n[muted]{version_info}[/muted]",
        border_style="border",
        padding=(1, 2)
    )
    
    console.print()
    console.print(banner_panel)
    console.print()


def show_quick_help(console: Console) -> None:
    """Show quick help with themed styling."""
    help_text = """[header]Quick Start:[/header]
  [primary]todo add[/primary] [muted]"Review architecture proposal @meetings due friday"[/muted]
  [primary]todo list[/primary] [muted]--pinned[/muted]               Show pinned tasks
  [primary]todo done[/primary] [muted]<id>[/muted]                  Complete a task  
  [primary]todo dashboard[/primary]                    Show overview
  [primary]todo --help[/primary]                      Full help
  
[subheader]💡 Pro Tips:[/subheader]
  Use [tag]@tags[/tag], [assignee]+assignees[/assignee], priorities [warning]~high[/warning], and [accent][PIN][/accent] for power!
"""
    
    console.print(Panel(
        help_text,
        title="[accent]Getting Started[/accent]",
        border_style="border",
        padding=(1, 1)
    ))


def get_priority_style(priority_str: str) -> str:
    """Get the style name for a priority level."""
    priority_map = {
        'critical': 'priority_critical',
        'high': 'priority_high', 
        'medium': 'priority_medium',
        'low': 'priority_low'
    }
    return priority_map.get(priority_str.lower(), 'priority_medium')


def get_status_emoji(status: str, pinned: bool = False) -> str:
    """Get emoji for todo status with theming consideration."""
    status_emojis = {
        'pending': '⏳',
        'in_progress': '🔄', 
        'completed': '✅',
        'cancelled': '❌',
        'blocked': '🚫'
    }
    
    emoji = status_emojis.get(status, '⏳')
    
    # Add star for pinned items
    if pinned:
        emoji = f"⭐ {emoji}"
        
    return emoji


def organize_todos_by_date(todos, sort_by_priority: bool = False):
    """Organize todos into date-based views: Today, Tomorrow, Upcoming, Backlog.
    
    Args:
        todos: List of Todo objects
        sort_by_priority: If True, sort by priority (high to low), otherwise by ID
        
    Returns:
        Dict with keys: 'today', 'tomorrow', 'upcoming', 'backlog'
    """
    from datetime import timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    views = {
        'today': [],
        'tomorrow': [], 
        'upcoming': [],
        'backlog': []
    }
    
    for todo in todos:
        if todo.completed:
            continue  # Skip completed todos
            
        if todo.due_date:
            due_date = todo.due_date.date()
            if due_date == today:
                views['today'].append(todo)
            elif due_date == tomorrow:
                views['tomorrow'].append(todo)
            elif due_date > tomorrow:
                views['upcoming'].append(todo)
        else:
            views['backlog'].append(todo)
    
    # Sort each view
    for view_todos in views.values():
        if sort_by_priority:
            # Sort by priority (critical=0, high=1, medium=2, low=3), then by ID
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            view_todos.sort(key=lambda t: (priority_order.get(t.priority.value, 2), t.id))
        else:
            # Sort by ID only
            view_todos.sort(key=lambda t: t.id)
    
    return views


def get_view_header(view_name: str, count: int) -> str:
    """Get a styled header for a task view.
    
    Args:
        view_name: Name of the view (today, tomorrow, upcoming, backlog)
        count: Number of tasks in the view
        
    Returns:
        Formatted header string with styling
    """
    view_icons = {
        'today': '📅',
        'tomorrow': '🕰', 
        'upcoming': '📆',
        'backlog': '📋'
    }
    
    view_titles = {
        'today': 'Today',
        'tomorrow': 'Tomorrow',
        'upcoming': 'Upcoming',
        'backlog': 'Backlog'
    }
    
    icon = view_icons.get(view_name, '📋')
    title = view_titles.get(view_name, view_name.title())
    
    if count == 0:
        return f"[muted]{icon} {title}[/muted]"
    elif view_name == 'today':
        return f"[critical]{icon} {title} ({count})[/critical]"
    elif view_name == 'tomorrow':
        return f"[warning]{icon} {title} ({count})[/warning]"
    elif view_name == 'upcoming':
        return f"[primary]{icon} {title} ({count})[/primary]"
    else:  # backlog
        return f"[accent]{icon} {title} ({count})[/accent]"


def get_theme() -> Theme:
    """Get the default theme for the application.
    
    Returns:
        Rich Theme instance with current theme styling
    """
    return PRODUCTIVITY_NINJA_THEME


# Theme configuration for export
THEME_CONFIG = {
    'name': 'productivity_ninja',
    'colors': CITY_LIGHTS_COLORS,
    'theme': PRODUCTIVITY_NINJA_THEME,
}
