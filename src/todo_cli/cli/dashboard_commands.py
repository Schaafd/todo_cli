"""CLI commands for dashboard management."""

import click
from rich.console import Console


@click.group("dashboard-mgr")
def dashboard_group():
    """Manage custom dashboards."""
    pass


@dashboard_group.command("show")
@click.argument("name", default="default")
def show_dashboard(name):
    """Display a dashboard. Use 'default' or a template name."""
    from ..services.dashboard import DashboardManager, WidgetType
    from ..services.dashboard_renderer import DashboardRenderer
    from ..storage import Storage
    from ..config import get_config

    console = Console()
    manager = DashboardManager()
    renderer = DashboardRenderer(console)

    # Try to find by name among saved dashboards
    dashboards = manager.list_dashboards()
    dashboard = None
    for d in dashboards:
        if d["name"].lower() == name.lower() or d["id"] == name:
            dashboard = manager.load_dashboard(d["id"])
            break

    # If not found, try template names
    template_map = {
        "productivity": "productivity_overview",
        "project": "project_dashboard",
        "time_tracking": "time_tracking",
        "minimal": "minimal",
    }
    if dashboard is None and name in template_map:
        dashboard = manager.create_template_dashboard(template_map[name])

    if dashboard is None and name == "default":
        dashboard = manager.create_template_dashboard("minimal")

    if dashboard is None:
        console.print(f"[red]Dashboard '{name}' not found.[/red]")
        console.print("[dim]Use 'dashboard-mgr list' to see available dashboards or specify a template name.[/dim]")
        return

    # Refresh widget data
    config = get_config()
    storage = Storage(config)
    all_todos = []
    for proj_name in (storage.list_projects() or [config.default_project]):
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)

    manager.refresh_dashboard_data(dashboard, all_todos)
    renderer.render(dashboard)


@dashboard_group.command("create")
@click.argument("name")
@click.option("--template", "-t", type=click.Choice(["productivity", "project", "time_tracking", "minimal"]),
              default=None)
@click.option("--description", "-d", default="")
def create_dashboard(name, template, description):
    """Create a new dashboard, optionally from a template."""
    from ..services.dashboard import DashboardManager

    console = Console()
    manager = DashboardManager()

    template_map = {
        "productivity": "productivity_overview",
        "project": "project_dashboard",
        "time_tracking": "time_tracking",
        "minimal": "minimal",
    }

    if template:
        dashboard = manager.create_template_dashboard(template_map[template])
        dashboard.name = name
        if description:
            dashboard.description = description
        manager.save_dashboard(dashboard)
    else:
        dashboard = manager.create_dashboard(name, description)

    console.print(f"[green]Dashboard '{dashboard.name}' created (id: {dashboard.id[:12]}...)[/green]")


@dashboard_group.command("list")
def list_dashboards():
    """List all saved dashboards."""
    from ..services.dashboard import DashboardManager
    from ..services.dashboard_renderer import DashboardRenderer

    console = Console()
    manager = DashboardManager()
    renderer = DashboardRenderer(console)
    dashboards = manager.list_dashboards()
    renderer.render_dashboard_list(dashboards)


@dashboard_group.command("add-widget")
@click.argument("dashboard_name")
@click.option("--type", "-t", "widget_type", required=True,
              type=click.Choice(["metric", "gauge", "sparkline", "chart_bar", "chart_pie",
                                 "table", "list", "text", "progress_bar"]))
@click.option("--title", required=True)
@click.option("--source", "-s", required=True,
              type=click.Choice(["todo_metrics", "project_metrics", "time_tracking"]))
@click.option("--size", default="medium",
              type=click.Choice(["small", "medium", "large", "wide", "full"]))
@click.option("--metric", "-m", help="Metric type for the data source")
def add_widget(dashboard_name, widget_type, title, source, size, metric):
    """Add a widget to a dashboard."""
    from ..services.dashboard import DashboardManager, WidgetType, WidgetSize

    console = Console()
    manager = DashboardManager()

    # Find dashboard
    dashboards = manager.list_dashboards()
    dashboard = None
    for d in dashboards:
        if d["name"].lower() == dashboard_name.lower() or d["id"] == dashboard_name:
            dashboard = manager.load_dashboard(d["id"])
            break

    if dashboard is None:
        console.print(f"[red]Dashboard '{dashboard_name}' not found.[/red]")
        return

    wtype = WidgetType(widget_type)
    wsize = WidgetSize(size)
    params = {}
    if metric:
        params["metric_type"] = metric

    widget = manager.create_widget(wtype, title, source, wsize, **params)
    dashboard.add_widget(widget)
    manager.save_dashboard(dashboard)
    console.print(f"[green]Widget '{title}' added to dashboard '{dashboard.name}'.[/green]")


@dashboard_group.command("remove-widget")
@click.argument("dashboard_name")
@click.argument("widget_id")
def remove_widget(dashboard_name, widget_id):
    """Remove a widget from a dashboard."""
    from ..services.dashboard import DashboardManager

    console = Console()
    manager = DashboardManager()

    dashboards = manager.list_dashboards()
    dashboard = None
    for d in dashboards:
        if d["name"].lower() == dashboard_name.lower() or d["id"] == dashboard_name:
            dashboard = manager.load_dashboard(d["id"])
            break

    if dashboard is None:
        console.print(f"[red]Dashboard '{dashboard_name}' not found.[/red]")
        return

    if dashboard.remove_widget(widget_id):
        manager.save_dashboard(dashboard)
        console.print(f"[green]Widget removed from dashboard '{dashboard.name}'.[/green]")
    else:
        console.print(f"[red]Widget '{widget_id}' not found in dashboard.[/red]")


@dashboard_group.command("delete")
@click.argument("name")
def delete_dashboard(name):
    """Delete a dashboard."""
    from ..services.dashboard import DashboardManager

    console = Console()
    manager = DashboardManager()

    dashboards = manager.list_dashboards()
    for d in dashboards:
        if d["name"].lower() == name.lower() or d["id"] == name:
            if manager.delete_dashboard(d["id"]):
                console.print(f"[green]Dashboard '{d['name']}' deleted.[/green]")
                return
    console.print(f"[red]Dashboard '{name}' not found.[/red]")


@dashboard_group.command("reset")
@click.argument("name")
def reset_dashboard(name):
    """Reset a dashboard to its template defaults."""
    from ..services.dashboard import DashboardManager

    console = Console()
    manager = DashboardManager()

    dashboards = manager.list_dashboards()
    for d in dashboards:
        if d["name"].lower() == name.lower() or d["id"] == name:
            dashboard = manager.load_dashboard(d["id"])
            if dashboard:
                dashboard.widgets.clear()
                manager.save_dashboard(dashboard)
                console.print(f"[green]Dashboard '{dashboard.name}' has been reset (all widgets removed).[/green]")
                return
    console.print(f"[red]Dashboard '{name}' not found.[/red]")


@dashboard_group.command("templates")
def list_templates():
    """List available dashboard templates."""
    from rich.table import Table

    console = Console()
    table = Table(title="Dashboard Templates", show_lines=True)
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Widgets")

    templates = [
        ("productivity", "Productivity overview with scores, completion rate, and time tracking", "4"),
        ("project", "Project-focused metrics: health, velocity, and burndown", "3"),
        ("time_tracking", "Time tracking dashboard with sessions, hours, and focus score", "4"),
        ("minimal", "Minimal dashboard with total, overdue, and completion rate", "3"),
    ]
    for name, desc, widgets in templates:
        table.add_row(name, desc, widgets)

    console.print(table)
