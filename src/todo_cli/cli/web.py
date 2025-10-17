"""
Web server CLI commands for Todo CLI.

This module provides commands to start and manage the Todo CLI web server.
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from todo_cli.web.server import start_server


console = Console()


@click.group()
def web():
    """Web server commands for Todo CLI PWA."""
    pass


@web.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind the server to",
    show_default=True
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind the server to",
    show_default=True
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with auto-reload"
)
def start(host: str, port: int, debug: bool):
    """Start the Todo CLI web server."""
    
    # Display startup message
    title = Text("Todo CLI Web Server", style="bold cyan")
    content = Text()
    content.append(f"Server will start at: ", style="white")
    content.append(f"http://{host}:{port}", style="bold green")
    content.append("\n\n")
    content.append("Features available:\n", style="yellow")
    content.append("• Task management with CRUD operations\n", style="white")
    content.append("• Kanban-style board view\n", style="white")  
    content.append("• Context switching\n", style="white")
    content.append("• Backup and restore\n", style="white")
    content.append("• Quick task capture\n", style="white")
    content.append("• Responsive PWA design\n", style="white")
    
    if debug:
        content.append("\n")
        content.append("Debug mode: ", style="yellow")
        content.append("ENABLED", style="bold red")
        content.append(" (auto-reload on file changes)", style="white")
    
    panel = Panel(
        content,
        title=title,
        border_style="cyan",
        padding=(1, 2)
    )
    
    console.print("\n")
    console.print(panel)
    console.print("\n")
    console.print("Press Ctrl+C to stop the server", style="dim")
    console.print("\n")
    
    try:
        start_server(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        console.print("\n")
        console.print("Server stopped", style="yellow")
    except Exception as e:
        console.print(f"\nError starting server: {e}", style="red")
        raise click.ClickException(f"Failed to start server: {e}")


@web.command()
def info():
    """Show information about the web server."""
    
    info_text = Text()
    info_text.append("Todo CLI Web Server\n", style="bold cyan")
    info_text.append("===================\n\n", style="cyan")
    
    info_text.append("The Todo CLI web server provides a Progressive Web App (PWA) interface\n")
    info_text.append("for managing your todos through a modern web browser.\n\n")
    
    info_text.append("Key Features:\n", style="bold yellow")
    info_text.append("• Full task CRUD operations\n")
    info_text.append("• Kanban-style board visualization\n")
    info_text.append("• Context-based task organization\n")
    info_text.append("• Quick capture for rapid task entry\n")
    info_text.append("• Backup and restore functionality\n")
    info_text.append("• Responsive design for mobile and desktop\n")
    info_text.append("• Offline capabilities with service worker\n")
    info_text.append("• Real-time synchronization with CLI data\n\n")
    
    info_text.append("API Endpoints:\n", style="bold yellow")
    info_text.append("• GET /api/tasks - List all tasks\n")
    info_text.append("• POST /api/tasks - Create new task\n")
    info_text.append("• PUT /api/tasks/{id} - Update task\n")
    info_text.append("• DELETE /api/tasks/{id} - Delete task\n")
    info_text.append("• GET /api/contexts - List contexts\n")
    info_text.append("• GET /api/tags - List tags\n")
    info_text.append("• GET /api/backups - List backups\n")
    info_text.append("• POST /api/backups - Create backup\n\n")
    
    info_text.append("Usage:\n", style="bold yellow")
    info_text.append("todo web start         # Start server on localhost:8000\n")
    info_text.append("todo web start --port 3000  # Start on custom port\n")
    info_text.append("todo web start --debug      # Start with debug mode\n")
    
    panel = Panel(
        info_text,
        title="Web Server Information",
        border_style="cyan",
        padding=(1, 2)
    )
    
    console.print(panel)