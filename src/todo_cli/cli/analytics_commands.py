"""CLI Analytics Commands for Todo CLI.

This module provides comprehensive command-line interface commands for analytics,
including interactive reports, data export, visualization, and dashboard management.

Features:
- Interactive analytics reports
- Data export in multiple formats  
- Visualization and charting
- Dashboard management commands
- Plugin management for analytics
- Time tracking commands
- Project analytics
"""

import click
import json
import csv
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import tabulate

from ..services.analytics import (
    ProductivityAnalyzer, AnalyticsTimeframe, AnalyticsReport,
    TaskPattern, ProductivityInsight
)
from ..services.time_tracking import (
    TimeTracker, TimeReport, ProductivityHeatmap, 
    WorkPattern, EstimationAccuracy
)
from ..services.project_analytics import (
    ProjectAnalyzer, ProjectHealthScore, ProjectForecast,
    BurndownData, VelocityData
)
from ..services.dashboard import (
    DashboardManager, Dashboard, Widget, WidgetType,
    TodoMetricsDataSource, ProjectMetricsDataSource, TimeTrackingDataSource
)
from ..services.plugins import PluginManager, PluginType, PluginStatus
from ..config import get_config
from ..storage import Storage


# Helper function for storage
def get_storage():
    """Get initialized storage instance."""
    config = get_config()
    return Storage(config)


def get_all_todos():
    """Get all todos from all projects."""
    storage = get_storage()
    config = get_config()
    
    all_todos = []
    projects = storage.list_projects()
    if not projects:
        projects = [config.default_project]
    
    for proj_name in projects:
        proj, todos = storage.load_project(proj_name)
        if todos:
            all_todos.extend(todos)
    
    return all_todos


# Console formatting helpers
def format_metric(value: float, unit: str = "", format_spec: str = ".2f") -> str:
    """Format a metric value with proper units"""
    formatted = f"{value:{format_spec}}"
    return f"{formatted}{unit}" if unit else formatted


def format_table(data: List[Dict], headers: Optional[List[str]] = None, 
                tablefmt: str = "grid") -> str:
    """Format data as a table"""
    if not data:
        return "No data available"
    
    if headers is None:
        headers = "keys"
    
    return tabulate.tabulate(data, headers=headers, tablefmt=tablefmt)


def print_section(title: str, content: str = ""):
    """Print a formatted section"""
    click.echo(f"\n{'=' * 60}")
    click.echo(f"{title:^60}")
    click.echo(f"{'=' * 60}")
    if content:
        click.echo(content)
    click.echo()


def print_subsection(title: str):
    """Print a formatted subsection"""
    click.echo(f"\n{title}")
    click.echo("-" * len(title))


# Main analytics command group
@click.group(name='analytics')
def analytics_cli():
    """Analytics and reporting commands for Todo CLI"""
    pass


@analytics_cli.command(name='overview')
@click.option('--timeframe', '-t', 
              type=click.Choice(['daily', 'weekly', 'monthly', 'yearly', 'all']),
              default='weekly', help='Timeframe for analysis')
@click.option('--format', '-f',
              type=click.Choice(['text', 'json', 'csv']),
              default='text', help='Output format')
@click.option('--export', '-e', type=click.Path(), help='Export to file')
def analytics_overview(timeframe: str, format: str, export: Optional[str]):
    """Generate comprehensive analytics overview"""
    
    try:
        # Get data
        todos = get_all_todos()
        
        if not todos:
            click.echo("No todos found for analysis")
            return
        
        # Generate analytics
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(todos, AnalyticsTimeframe(timeframe))
        
        if format == 'json':
            output = json.dumps(report.to_dict(), indent=2)
        elif format == 'csv':
            # Convert to CSV-friendly format
            rows = []
            for insight in report.insights:
                rows.append({
                    'metric': insight.metric_name,
                    'value': insight.value,
                    'trend': insight.trend,
                    'description': insight.description
                })
            
            if export:
                with open(export, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=['metric', 'value', 'trend', 'description'])
                    writer.writeheader()
                    writer.writerows(rows)
                click.echo(f"Analytics exported to {export}")
                return
            else:
                output = format_table(rows)
        else:  # text format
            output = _format_analytics_report(report)
        
        if export and format != 'csv':
            Path(export).write_text(output)
            click.echo(f"Analytics exported to {export}")
        else:
            click.echo(output)
            
    except Exception as e:
        click.echo(f"Error generating analytics: {e}", err=True)
        sys.exit(1)


def _format_analytics_report(report: AnalyticsReport) -> str:
    """Format analytics report for console display"""
    output = []
    
    output.append("\n" + "=" * 60)
    output.append("📊 PRODUCTIVITY ANALYTICS OVERVIEW".center(60))
    output.append("=" * 60)
    
    # Summary metrics
    output.append("\n📈 KEY METRICS")
    output.append("-" * 50)
    
    key_metrics = [
        {"Metric": "Completion Rate", "Value": f"{report.productivity_score.completion_rate:.1f}%"},
        {"Metric": "Tasks Completed", "Value": f"{report.productivity_score.tasks_completed}"},
        {"Metric": "Productivity Score", "Value": f"{report.productivity_score.overall_score:.1f}/100"},
        {"Metric": "Focus Score", "Value": f"{report.productivity_score.focus_score:.1f}/100"}
    ]
    
    output.append(format_table(key_metrics, tablefmt="simple"))
    
    # Task patterns
    if report.patterns:
        output.append("\n🔍 TASK PATTERNS")
        output.append("-" * 50)
        
        pattern_data = []
        for pattern in report.patterns:
            pattern_data.append({
                "Pattern": pattern.pattern_type,
                "Frequency": f"{pattern.frequency}%",
                "Confidence": f"{pattern.confidence:.1f}",
                "Description": pattern.description[:60] + "..." if len(pattern.description) > 60 else pattern.description
            })
        
        output.append(format_table(pattern_data, tablefmt="simple"))
    
    # Insights
    if report.insights:
        output.append("\n💡 KEY INSIGHTS")
        output.append("-" * 50)
        
        for insight in report.insights:
            icon_map = {"strength": "💪", "weakness": "⚠️", "opportunity": "🎯", "trend": "📊"}
            icon = icon_map.get(insight.insight_type, "💡")
            output.append(f"{icon} {insight.title}: {insight.description}")
        output.append("")
    
    # Time-based analysis
    if hasattr(report, 'hourly_distribution') and report.hourly_distribution:
        output.append("\n⏰ PEAK PRODUCTIVITY HOURS")
        output.append("-" * 50)
        
        sorted_hours = sorted(report.hourly_distribution.items(), key=lambda x: x[1], reverse=True)[:5]
        for hour, count in sorted_hours:
            bar = "█" * min(int(count / max(report.hourly_distribution.values()) * 20), 20)
            output.append(f"{hour:02d}:00 {bar} ({count} tasks)")
        output.append("")
    
    # Recommendations
    if hasattr(report, 'recommendations') and report.recommendations:
        output.append("\n🎯 RECOMMENDATIONS")
        output.append("-" * 50)
        
        for i, rec in enumerate(report.recommendations, 1):
            output.append(f"{i}. {rec}")
        output.append("")
    
    return "\n".join(output)


@analytics_cli.command(name='time')
@click.option('--period', '-p',
              type=click.Choice(['today', 'yesterday', 'week', 'month']),
              default='week', help='Time period to analyze')
@click.option('--project', help='Filter by project')
@click.option('--tag', help='Filter by tag')
@click.option('--heatmap', is_flag=True, help='Show productivity heatmap')
def time_analytics(period: str, project: Optional[str], tag: Optional[str], heatmap: bool):
    """Time tracking and productivity analysis"""
    
    try:
        tracker = TimeTracker()
        
        # Calculate date range
        end_date = datetime.now()
        if period == 'today':
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'yesterday':
            start_date = (end_date - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
        elif period == 'week':
            start_date = end_date - timedelta(days=7)
        else:  # month
            start_date = end_date - timedelta(days=30)
        
        # Generate time report
        report = tracker.generate_time_report(start_date, end_date, project, tag)
        
        print_section(f"⏱️  TIME TRACKING REPORT - {period.upper()}")
        
        # Summary
        print_subsection("📊 Time Summary")
        click.echo(f"Total Time Tracked: {report.total_time_tracked:.2f} hours")
        click.echo(f"Average Daily Time: {report.average_daily_hours:.2f} hours")
        click.echo(f"Most Productive Day: {report.most_productive_day}")
        click.echo(f"Work-Life Balance Score: {report.work_life_balance_score:.1f}/100")
        
        # Time allocation
        if report.time_by_project:
            print_subsection("📁 Time by Project")
            project_data = [
                {"Project": proj, "Hours": f"{hours:.2f}", "Percentage": f"{(hours/report.total_time_tracked*100):.1f}%"}
                for proj, hours in sorted(report.time_by_project.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            click.echo(format_table(project_data, tablefmt="simple"))
        
        if report.time_by_tag:
            print_subsection("🏷️  Time by Tag")
            tag_data = [
                {"Tag": tag_name, "Hours": f"{hours:.2f}", "Percentage": f"{(hours/report.total_time_tracked*100):.1f}%"}
                for tag_name, hours in sorted(report.time_by_tag.items(), key=lambda x: x[1], reverse=True)[:10]
            ]
            click.echo(format_table(tag_data, tablefmt="simple"))
        
        # Estimation accuracy
        if hasattr(report, 'estimation_accuracy'):
            print_subsection("🎯 Estimation Accuracy")
            acc = report.estimation_accuracy
            click.echo(f"Average Accuracy: {acc.average_accuracy:.1f}%")
            click.echo(f"Overestimation Tendency: {acc.overestimation_percentage:.1f}%")
            click.echo(f"Underestimation Tendency: {acc.underestimation_percentage:.1f}%")
        
        # Productivity heatmap
        if heatmap:
            print_subsection("🔥 Productivity Heatmap")
            heatmap_data = tracker.generate_productivity_heatmap(start_date, end_date)
            _display_heatmap(heatmap_data)
            
    except Exception as e:
        click.echo(f"Error generating time analytics: {e}", err=True)


def _display_heatmap(heatmap: ProductivityHeatmap):
    """Display productivity heatmap in console"""
    
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    hours = list(range(24))
    
    # Find max value for scaling
    max_value = 0
    for day_data in heatmap.data.values():
        max_value = max(max_value, max(day_data.values()) if day_data else 0)
    
    if max_value == 0:
        click.echo("No productivity data available")
        return
    
    # Display header
    click.echo("     " + "".join(f"{h:3d}" for h in hours))
    
    # Display heatmap
    for day in days:
        row = f"{day}: "
        day_data = heatmap.data.get(day, {})
        
        for hour in hours:
            value = day_data.get(hour, 0)
            if value == 0:
                row += "   "
            else:
                intensity = int((value / max_value) * 4)
                symbols = [" ", ".", ":", "#", "█"]
                row += f" {symbols[intensity]} "
        
        click.echo(row)
    
    # Display legend
    click.echo("\nLegend: █ = High activity, # = Medium, : = Low, . = Minimal, (space) = No activity")


@analytics_cli.command(name='projects')
@click.option('--project', help='Specific project to analyze')
@click.option('--all', '-a', is_flag=True, help='Show all projects')
def project_analytics(project: Optional[str], all: bool):
    """Project-level analytics and insights"""
    
    try:
        todos = get_all_todos()
        
        analyzer = ProjectAnalyzer()
        
        if project:
            # Analyze specific project
            project_todos = [t for t in todos if t.project == project]
            if not project_todos:
                click.echo(f"No todos found for project: {project}")
                return
            
            dashboard = analyzer.generate_project_dashboard(project, project_todos)
            _display_project_dashboard(project, dashboard)
            
        else:
            # Analyze all projects
            projects = set(t.project for t in todos if t.project)
            
            if not projects:
                click.echo("No projects found")
                return
            
            print_section("📊 PROJECT ANALYTICS OVERVIEW")
            
            project_summaries = []
            for proj in sorted(projects):
                proj_todos = [t for t in todos if t.project == proj]
                health_score = analyzer.calculate_project_health(proj_todos)
                
                project_summaries.append({
                    "Project": proj,
                    "Tasks": len(proj_todos),
                    "Completed": len([t for t in proj_todos if t.completed]),
                    "Health": f"{health_score.overall_score:.1f}/100",
                    "Status": health_score.status
                })
            
            click.echo(format_table(project_summaries, tablefmt="grid"))
            
            if all:
                for proj in sorted(projects):
                    proj_todos = [t for t in todos if t.project == proj]
                    dashboard = analyzer.generate_project_dashboard(proj, proj_todos)
                    _display_project_dashboard(proj, dashboard, brief=True)
                    
    except Exception as e:
        click.echo(f"Error generating project analytics: {e}", err=True)


def _display_project_dashboard(project_name: str, dashboard, brief: bool = False):
    """Display project dashboard"""
    
    print_section(f"📁 PROJECT: {project_name}")
    
    # Health score
    health = dashboard.health_score
    status_emoji = {"healthy": "✅", "warning": "⚠️", "critical": "🚨"}.get(health.status, "❓")
    
    click.echo(f"{status_emoji} Health Score: {health.overall_score:.1f}/100 ({health.status.title()})")
    
    if not brief:
        click.echo(f"   • Completion Rate: {health.completion_rate:.1f}%")
        click.echo(f"   • Velocity Score: {health.velocity_score:.1f}/100")  
        click.echo(f"   • Quality Score: {health.quality_score:.1f}/100")
        click.echo("")
        
        # Progress metrics
        metrics = dashboard.progress_metrics
        progress_data = [
            {"Metric": "Total Tasks", "Value": metrics["total_tasks"]},
            {"Metric": "Completed", "Value": metrics["completed_tasks"]},
            {"Metric": "In Progress", "Value": metrics.get("in_progress_tasks", 0)},
            {"Metric": "Overdue", "Value": metrics.get("overdue_tasks", 0)}
        ]
        
        click.echo(format_table(progress_data, tablefmt="simple"))
        
        # Forecast
        if hasattr(dashboard, 'forecast'):
            forecast = dashboard.forecast
            click.echo(f"\n🔮 Project Forecast:")
            click.echo(f"   • Estimated Completion: {forecast.estimated_completion_date.strftime('%Y-%m-%d')}")
            click.echo(f"   • Confidence Level: {forecast.confidence_level:.1f}%")
            click.echo(f"   • Days Remaining: {forecast.days_remaining}")
    
    click.echo("")


@analytics_cli.command(name='dashboard')
@click.option('--name', required=True, help='Dashboard name')
@click.option('--create', is_flag=True, help='Create new dashboard')
@click.option('--list', 'list_dashboards', is_flag=True, help='List all dashboards')
def dashboard_command(name: str, create: bool, list_dashboards: bool):
    """Manage and display custom dashboards"""
    
    try:
        manager = DashboardManager()
        
        if list_dashboards:
            dashboards = manager.list_dashboards()
            if dashboards:
                click.echo("Available Dashboards:")
                for dashboard_name in dashboards:
                    click.echo(f"  • {dashboard_name}")
            else:
                click.echo("No dashboards found")
            return
        
        if create:
            # Interactive dashboard creation
            _create_dashboard_interactive(manager, name)
            return
        
        # Display existing dashboard
        dashboard = manager.get_dashboard(name)
        if not dashboard:
            click.echo(f"Dashboard '{name}' not found")
            return
        
        _display_dashboard(manager, dashboard)
        
    except Exception as e:
        click.echo(f"Error with dashboard: {e}", err=True)


def _create_dashboard_interactive(manager: DashboardManager, name: str):
    """Interactively create a new dashboard"""
    
    click.echo(f"Creating dashboard: {name}")
    
    # Get available data sources
    available_sources = list(manager.data_sources.keys())
    click.echo(f"Available data sources: {', '.join(available_sources)}")
    
    widgets = []
    
    while True:
        widget_name = click.prompt("Widget name (or 'done' to finish)")
        if widget_name.lower() == 'done':
            break
        
        data_source = click.prompt(f"Data source for {widget_name}", 
                                 type=click.Choice(available_sources))
        
        widget_type = click.prompt("Widget type",
                                 type=click.Choice(['metric', 'chart', 'table', 'gauge']))
        
        widget = Widget(
            name=widget_name,
            widget_type=WidgetType(widget_type),
            data_source=data_source,
            config={}
        )
        widgets.append(widget)
    
    # Create dashboard
    dashboard = Dashboard(
        name=name,
        widgets=widgets,
        layout={'type': 'vertical'},  # Simple layout
        refresh_interval=300
    )
    
    manager.save_dashboard(dashboard)
    click.echo(f"Dashboard '{name}' created successfully!")


def _display_dashboard(manager: DashboardManager, dashboard: Dashboard):
    """Display dashboard in console"""
    
    print_section(f"📊 DASHBOARD: {dashboard.name}")
    
    todos = get_all_todos()
    
    for widget in dashboard.widgets:
        print_subsection(f"📈 {widget.name}")
        
        try:
            data_source = manager.data_sources.get(widget.data_source)
            if data_source:
                # Prepare parameters
                params = {'todos': todos}
                params.update(widget.config)
                
                # Fetch data
                widget_data = data_source.fetch_data(params)
                
                # Display based on widget type
                if widget.widget_type == WidgetType.METRIC:
                    icon = getattr(widget_data, 'icon', '📊')
                    value = format_metric(widget_data.value, widget_data.unit, 
                                        getattr(widget_data, 'format', '.2f'))
                    click.echo(f"{icon} {widget_data.label}: {value}")
                    
                elif widget.widget_type == WidgetType.TABLE:
                    if hasattr(widget_data, 'rows'):
                        click.echo(format_table(widget_data.rows))
                    else:
                        click.echo(f"Value: {widget_data.value}")
                        
                else:  # Chart, gauge, etc.
                    click.echo(f"{widget_data.label}: {widget_data.value}")
                    
            else:
                click.echo(f"Data source '{widget.data_source}' not found")
                
        except Exception as e:
            click.echo(f"Error loading widget data: {e}")
    
    click.echo("")


@analytics_cli.command(name='export')
@click.argument('type', type=click.Choice(['analytics', 'time', 'projects', 'all']))
@click.option('--format', '-f', type=click.Choice(['json', 'csv', 'excel']),
              default='json', help='Export format')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.option('--timeframe', '-t', 
              type=click.Choice(['daily', 'weekly', 'monthly', 'yearly']),
              default='monthly', help='Timeframe for export')
def export_analytics(type: str, format: str, output: Optional[str], timeframe: str):
    """Export analytics data in various formats"""
    
    try:
        todos = get_all_todos()
        
        export_data = {}
        
        if type in ['analytics', 'all']:
            analyzer = ProductivityAnalyzer()
            report = analyzer.analyze_productivity(todos, AnalyticsTimeframe(timeframe))
            export_data['analytics'] = report.to_dict()
        
        if type in ['time', 'all']:
            tracker = TimeTracker()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)  # Last 30 days
            time_report = tracker.generate_time_report(start_date, end_date)
            export_data['time_tracking'] = time_report.to_dict()
        
        if type in ['projects', 'all']:
            analyzer = ProjectAnalyzer()
            projects = set(t.project for t in todos if t.project)
            project_data = {}
            
            for project in projects:
                project_todos = [t for t in todos if t.project == project]
                dashboard = analyzer.generate_project_dashboard(project, project_todos)
                project_data[project] = dashboard.to_dict()
            
            export_data['projects'] = project_data
        
        # Generate filename if not provided
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = f"todo_analytics_{type}_{timestamp}.{format}"
        
        # Export in requested format
        if format == 'json':
            with open(output, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
                
        elif format == 'csv':
            # Flatten data for CSV export
            _export_to_csv(export_data, output)
            
        elif format == 'excel':
            # Would require openpyxl or xlsxwriter
            click.echo("Excel export not yet implemented")
            return
        
        click.echo(f"Analytics exported to: {output}")
        
    except Exception as e:
        click.echo(f"Error exporting analytics: {e}", err=True)


def _export_to_csv(data: Dict[str, Any], output_path: str):
    """Export analytics data to CSV format"""
    
    # Create a flattened CSV with multiple sections
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        for section_name, section_data in data.items():
            writer.writerow([f"=== {section_name.upper()} ==="])
            writer.writerow([])
            
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if isinstance(value, (list, dict)):
                        writer.writerow([key, str(value)])
                    else:
                        writer.writerow([key, value])
            
            writer.writerow([])


# Plugin management commands
@analytics_cli.group(name='plugins')
def plugins_cli():
    """Plugin management for analytics"""
    pass


@plugins_cli.command(name='list')
@click.option('--type', 'plugin_type', type=click.Choice([t.value for t in PluginType]),
              help='Filter by plugin type')
@click.option('--status', type=click.Choice([s.value for s in PluginStatus]),
              help='Filter by plugin status')
def list_plugins(plugin_type: Optional[str], status: Optional[str]):
    """List installed plugins"""
    
    try:
        manager = PluginManager()
        plugins = manager.list_plugins()
        
        # Apply filters
        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type.value == plugin_type]
        
        if status:
            plugins = [p for p in plugins if p.status.value == status]
        
        if not plugins:
            click.echo("No plugins found matching criteria")
            return
        
        print_section("🧩 INSTALLED PLUGINS")
        
        plugin_data = []
        for plugin in plugins:
            status_emoji = {
                "enabled": "✅",
                "disabled": "⏸️",
                "error": "❌",
                "loading": "⏳"
            }.get(plugin.status.value, "❓")
            
            plugin_data.append({
                "Name": plugin.name,
                "ID": plugin.id,
                "Version": plugin.version,
                "Type": plugin.plugin_type.value,
                "Status": f"{status_emoji} {plugin.status.value}",
                "Author": plugin.author
            })
        
        click.echo(format_table(plugin_data, tablefmt="grid"))
        
    except Exception as e:
        click.echo(f"Error listing plugins: {e}", err=True)


@plugins_cli.command(name='install')
@click.argument('path', type=click.Path(exists=True))
def install_plugin(path: str):
    """Install a plugin from directory"""
    
    try:
        manager = PluginManager()
        
        if manager.install_plugin(path):
            click.echo("✅ Plugin installed successfully")
        else:
            click.echo("❌ Failed to install plugin")
            
    except Exception as e:
        click.echo(f"Error installing plugin: {e}", err=True)


@plugins_cli.command(name='enable')
@click.argument('plugin_id')
def enable_plugin(plugin_id: str):
    """Enable a plugin"""
    
    try:
        manager = PluginManager()
        
        if manager.enable_plugin(plugin_id):
            click.echo(f"✅ Plugin '{plugin_id}' enabled")
        else:
            click.echo(f"❌ Failed to enable plugin '{plugin_id}'")
            
    except Exception as e:
        click.echo(f"Error enabling plugin: {e}", err=True)


@plugins_cli.command(name='disable')
@click.argument('plugin_id')
def disable_plugin(plugin_id: str):
    """Disable a plugin"""
    
    try:
        manager = PluginManager()
        
        if manager.disable_plugin(plugin_id):
            click.echo(f"⏸️  Plugin '{plugin_id}' disabled")
        else:
            click.echo(f"❌ Failed to disable plugin '{plugin_id}'")
            
    except Exception as e:
        click.echo(f"Error disabling plugin: {e}", err=True)


# Add all command groups to main analytics CLI
def get_analytics_commands():
    """Get all analytics CLI commands"""
    return analytics_cli


if __name__ == '__main__':
    analytics_cli()