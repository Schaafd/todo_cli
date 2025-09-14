"""Theming system for Productivity Ninja CLI.

Provides color schemes and styling inspired by dark modern themes
like City Lights for a beautiful terminal experience.
"""

from rich.console import Console
from rich.theme import Theme
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from typing import Dict, Any, List
from datetime import datetime, date


# City Lights inspired color palette
CITY_LIGHTS_COLORS = {
    # Background and base colors
    'background': '#1D252C',
    'surface': '#2D3B47', 
    'surface_light': '#41505E',
    
    # Primary colors
    'primary': '#68D5F3',      # Bright cyan
    'secondary': '#5CCFE6',    # Light cyan  
    'accent': '#B7C5D3',      # Light blue-gray
    
    # Status colors
    'success': '#8BD649',      # Bright green
    'warning': '#FFD93D',      # Bright yellow
    'error': '#F78C6C',       # Coral/orange
    'critical': '#FF5370',     # Bright red
    
    # Text colors
    'text_primary': '#B7C5D3',    # Light blue-gray
    'text_secondary': '#718CA1',  # Medium blue-gray
    'text_muted': '#4F5B66',      # Dark blue-gray
    'text_bright': '#FFFFFF',     # Pure white
    
    # Syntax highlighting colors (inspired by City Lights)
    'keyword': '#5CCFE6',      # Light cyan
    'string': '#8BD649',       # Bright green  
    'number': '#F78C6C',       # Coral
    'comment': '#4F5B66',      # Muted
}

# Rich theme definition
PRODUCTIVITY_NINJA_THEME = Theme({
    # Base styles
    'default': f"{CITY_LIGHTS_COLORS['text_primary']}",
    'muted': f"{CITY_LIGHTS_COLORS['text_muted']}",
    'bright': f"{CITY_LIGHTS_COLORS['text_bright']} bold",
    
    # Status styles
    'success': f"{CITY_LIGHTS_COLORS['success']} bold",
    'warning': f"{CITY_LIGHTS_COLORS['warning']} bold", 
    'error': f"{CITY_LIGHTS_COLORS['error']} bold",
    'critical': f"{CITY_LIGHTS_COLORS['critical']} bold",
    
    # Priority styles
    'priority_critical': f"{CITY_LIGHTS_COLORS['critical']} bold",
    'priority_high': f"{CITY_LIGHTS_COLORS['warning']}",
    'priority_medium': f"{CITY_LIGHTS_COLORS['text_primary']}",
    'priority_low': f"{CITY_LIGHTS_COLORS['text_muted']}",
    
    # Component styles
    'primary': f"{CITY_LIGHTS_COLORS['primary']} bold",
    'secondary': f"{CITY_LIGHTS_COLORS['secondary']}",
    'accent': f"{CITY_LIGHTS_COLORS['accent']}",
    
    # Todo status styles
    'todo_pending': f"{CITY_LIGHTS_COLORS['primary']}",
    'todo_completed': f"{CITY_LIGHTS_COLORS['success']}",
    'todo_pinned': f"{CITY_LIGHTS_COLORS['warning']}",
    'todo_overdue': f"{CITY_LIGHTS_COLORS['critical']}",
    
    # Metadata styles
    'tag': f"{CITY_LIGHTS_COLORS['secondary']}",
    'assignee': f"{CITY_LIGHTS_COLORS['success']}",
    'due_date': f"{CITY_LIGHTS_COLORS['primary']}",
    'due_date_overdue': f"{CITY_LIGHTS_COLORS['critical']}",
    
    # UI elements
    'header': f"{CITY_LIGHTS_COLORS['text_bright']} bold",
    'subheader': f"{CITY_LIGHTS_COLORS['accent']} bold",
    'border': f"{CITY_LIGHTS_COLORS['surface_light']}",
})


def get_ascii_title() -> str:
    """Get the ASCII art title for Productivity Ninja CLI."""
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
    return Console(theme=PRODUCTIVITY_NINJA_THEME)


def show_startup_banner(console: Console) -> None:
    """Display the startup banner with ASCII art and theme."""
    title_text = Text(get_ascii_title(), style="primary")
    
    subtitle = Text("⚡ Master Your Tasks. Unleash Your Potential. ⚡", style="accent")
    version_info = Text("v1.0.0", style="muted")
    
    # Create the banner panel with centered title
    banner_content = Align.center(title_text)
    banner_panel = Panel(
        banner_content,
        title="[bright]Welcome to[/bright]",
        subtitle=f"[accent]{subtitle}[/accent]\n[muted]{version_info}[/muted]",
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


# Theme configuration for export
THEME_CONFIG = {
    'name': 'productivity_ninja',
    'colors': CITY_LIGHTS_COLORS,
    'theme': PRODUCTIVITY_NINJA_THEME,
}
