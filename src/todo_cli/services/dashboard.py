"""Custom Dashboard System for Todo CLI.

This module provides a flexible dashboard framework where users can create
custom views with widgets, charts, and KPIs tailored to their workflow.

Features:
- Widget-based architecture with various chart and metric types
- Customizable layouts and arrangements
- Real-time data updates and refresh capabilities
- Dashboard templates for common use cases
- Export and sharing capabilities
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Callable, Type
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
from abc import ABC, abstractmethod

from ..domain import Todo, Priority, TodoStatus
from .analytics import AnalyticsTimeframe, ProductivityAnalyzer, AnalyticsReport
from .time_tracking import TimeTracker, TimeAnalyzer, TimeReport
from .project_analytics import ProjectAnalyzer, ProjectDashboard
from ..config import get_config


class WidgetType(Enum):
    """Types of dashboard widgets"""
    METRIC = "metric"                    # Single number display
    CHART_LINE = "chart_line"           # Line chart
    CHART_BAR = "chart_bar"             # Bar chart
    CHART_PIE = "chart_pie"             # Pie chart
    CHART_HEATMAP = "chart_heatmap"     # Heatmap
    TABLE = "table"                     # Data table
    PROGRESS_BAR = "progress_bar"       # Progress indicator
    GAUGE = "gauge"                     # Gauge/speedometer
    SPARKLINE = "sparkline"             # Mini line chart
    TEXT = "text"                       # Text/markdown content
    LIST = "list"                       # List of items
    CALENDAR = "calendar"               # Calendar view


class WidgetSize(Enum):
    """Widget size options"""
    SMALL = "small"      # 1x1
    MEDIUM = "medium"    # 2x1
    LARGE = "large"      # 2x2
    WIDE = "wide"        # 3x1
    FULL = "full"        # Full width


class RefreshInterval(Enum):
    """Data refresh intervals"""
    MANUAL = 0          # Manual refresh only
    REAL_TIME = 1       # Real-time (1 second)
    FAST = 5           # Every 5 seconds
    NORMAL = 30        # Every 30 seconds
    SLOW = 300         # Every 5 minutes
    HOURLY = 3600      # Every hour


@dataclass
class WidgetData:
    """Data structure for widget content"""
    value: Any = None
    label: str = ""
    unit: str = ""
    trend: Optional[float] = None  # Percentage change
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Chart data
    series: List[Dict[str, Any]] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # Table data
    headers: List[str] = field(default_factory=list)
    rows: List[List[Any]] = field(default_factory=list)
    
    # Additional display properties
    color: Optional[str] = None
    icon: Optional[str] = None
    format: Optional[str] = None  # Format string for values
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class DataSource(ABC):
    """Abstract base class for data sources"""
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def fetch_data(self, params: Dict[str, Any]) -> WidgetData:
        """Fetch data for the widget"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get configuration schema for this data source"""
        pass


class TodoMetricsDataSource(DataSource):
    """Data source for todo-related metrics"""
    
    def __init__(self):
        super().__init__("todo_metrics")
        self.analyzer = ProductivityAnalyzer()
    
    def fetch_data(self, params: Dict[str, Any]) -> WidgetData:
        """Fetch todo metrics data"""
        metric_type = params.get('metric_type', 'total_tasks')
        timeframe = AnalyticsTimeframe(params.get('timeframe', 'weekly'))
        todos = params.get('todos', [])
        
        if metric_type == 'total_tasks':
            return WidgetData(
                value=len(todos),
                label="Total Tasks",
                icon="📋",
                metadata={'timeframe': timeframe.value}
            )
        
        elif metric_type == 'completed_tasks':
            completed = len([t for t in todos if t.completed])
            return WidgetData(
                value=completed,
                label="Completed Tasks",
                icon="✅",
                metadata={'timeframe': timeframe.value}
            )
        
        elif metric_type == 'completion_rate':
            total = len(todos)
            completed = len([t for t in todos if t.completed])
            rate = (completed / total * 100) if total > 0 else 0
            return WidgetData(
                value=rate,
                label="Completion Rate",
                unit="%",
                icon="📊",
                format=".1f"
            )
        
        elif metric_type == 'overdue_tasks':
            overdue = len([t for t in todos if t.is_overdue() and not t.completed])
            return WidgetData(
                value=overdue,
                label="Overdue Tasks",
                icon="⏰",
                color="red" if overdue > 0 else "green"
            )
        
        elif metric_type == 'productivity_score':
            report = self.analyzer.analyze_productivity(todos, timeframe)
            return WidgetData(
                value=report.productivity_score.overall_score,
                label="Productivity Score",
                unit="/100",
                icon="🎯",
                format=".1f",
                trend=report.productivity_score.completion_rate_trend
            )
        
        else:
            return WidgetData(value=0, label="Unknown Metric")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            'metric_type': {
                'type': 'select',
                'options': ['total_tasks', 'completed_tasks', 'completion_rate', 
                          'overdue_tasks', 'productivity_score'],
                'default': 'total_tasks',
                'label': 'Metric Type'
            },
            'timeframe': {
                'type': 'select',
                'options': ['daily', 'weekly', 'monthly', 'quarterly'],
                'default': 'weekly',
                'label': 'Time Frame'
            }
        }


class ProjectMetricsDataSource(DataSource):
    """Data source for project-related metrics"""
    
    def __init__(self):
        super().__init__("project_metrics")
        self.analyzer = ProjectAnalyzer()
    
    def fetch_data(self, params: Dict[str, Any]) -> WidgetData:
        """Fetch project metrics data"""
        metric_type = params.get('metric_type', 'project_health')
        project_name = params.get('project_name', 'default')
        todos = params.get('todos', [])
        
        # Filter todos for the project
        project_todos = [t for t in todos if t.project == project_name]
        
        if metric_type == 'project_health':
            dashboard = self.analyzer.generate_project_dashboard(project_name, project_todos)
            return WidgetData(
                value=dashboard.health_score.overall_score,
                label=f"{project_name} Health",
                unit="/100",
                icon="💚" if dashboard.health_score.overall_score > 70 else "⚠️",
                format=".1f",
                color="green" if dashboard.health_score.overall_score > 70 else "orange"
            )
        
        elif metric_type == 'velocity':
            dashboard = self.analyzer.generate_project_dashboard(project_name, project_todos)
            if dashboard.velocity_data:
                current_velocity = dashboard.velocity_data[-1].tasks_per_day
                return WidgetData(
                    value=current_velocity,
                    label="Current Velocity",
                    unit="tasks/day",
                    icon="🚀",
                    format=".2f"
                )
            else:
                return WidgetData(value=0, label="Current Velocity", unit="tasks/day")
        
        elif metric_type == 'burndown':
            dashboard = self.analyzer.generate_project_dashboard(project_name, project_todos)
            if dashboard.burndown_chart:
                latest = dashboard.burndown_chart[-1]
                return WidgetData(
                    value=latest.remaining_work,
                    label="Remaining Work",
                    unit="hours",
                    icon="🔥",
                    format=".1f",
                    series=[{
                        'name': 'Remaining Work',
                        'data': [point.remaining_work for point in dashboard.burndown_chart[-7:]]
                    }],
                    categories=[point.date.strftime('%m/%d') for point in dashboard.burndown_chart[-7:]]
                )
            else:
                return WidgetData(value=0, label="Remaining Work", unit="hours")
        
        else:
            return WidgetData(value=0, label="Unknown Metric")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            'metric_type': {
                'type': 'select',
                'options': ['project_health', 'velocity', 'burndown'],
                'default': 'project_health',
                'label': 'Metric Type'
            },
            'project_name': {
                'type': 'text',
                'default': 'default',
                'label': 'Project Name'
            }
        }


class TimeTrackingDataSource(DataSource):
    """Data source for time tracking metrics"""
    
    def __init__(self):
        super().__init__("time_tracking")
        self.time_tracker = TimeTracker()
        self.analyzer = TimeAnalyzer(self.time_tracker)
    
    def fetch_data(self, params: Dict[str, Any]) -> WidgetData:
        """Fetch time tracking data"""
        metric_type = params.get('metric_type', 'hours_today')
        timeframe = AnalyticsTimeframe(params.get('timeframe', 'daily'))
        
        if metric_type == 'hours_today':
            entries = self.time_tracker.get_entries_for_timeframe(AnalyticsTimeframe.DAILY)
            total_hours = sum(e.get_duration_hours() for e in entries if e.end_time)
            return WidgetData(
                value=total_hours,
                label="Hours Today",
                unit="h",
                icon="⏱️",
                format=".1f"
            )
        
        elif metric_type == 'current_session':
            active_entry = self.time_tracker.get_current_tracking()
            if active_entry:
                hours = active_entry.get_duration_hours()
                return WidgetData(
                    value=hours,
                    label="Current Session",
                    unit="h",
                    icon="🎯",
                    format=".1f",
                    color="green"
                )
            else:
                return WidgetData(
                    value=0,
                    label="Current Session",
                    unit="h",
                    color="gray"
                )
        
        elif metric_type == 'focus_score':
            report = self.analyzer.generate_time_report(timeframe)
            if report.average_focus_level:
                return WidgetData(
                    value=report.average_focus_level,
                    label="Average Focus",
                    unit="/10",
                    icon="🎯",
                    format=".1f"
                )
            else:
                return WidgetData(value=0, label="Average Focus", unit="/10")
        
        elif metric_type == 'productivity_heatmap':
            report = self.analyzer.generate_time_report(AnalyticsTimeframe.WEEKLY)
            heatmap_data = report.productivity_heatmap.data
            
            # Convert to format suitable for display
            series_data = []
            categories = list(range(24))  # Hours 0-23
            
            for date_str, hours_data in heatmap_data.items():
                day_data = [hours_data.get(str(hour), 0) for hour in range(24)]
                series_data.append({
                    'name': date_str,
                    'data': day_data
                })
            
            return WidgetData(
                label="Productivity Heatmap",
                series=series_data,
                categories=[f"{h:02d}:00" for h in categories],
                metadata={'type': 'heatmap'}
            )
        
        else:
            return WidgetData(value=0, label="Unknown Metric")
    
    def get_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            'metric_type': {
                'type': 'select',
                'options': ['hours_today', 'current_session', 'focus_score', 'productivity_heatmap'],
                'default': 'hours_today',
                'label': 'Metric Type'
            },
            'timeframe': {
                'type': 'select',
                'options': ['daily', 'weekly', 'monthly'],
                'default': 'daily',
                'label': 'Time Frame'
            }
        }


@dataclass
class Widget:
    """Dashboard widget configuration and state"""
    id: str
    title: str
    widget_type: WidgetType
    size: WidgetSize
    data_source: str
    data_params: Dict[str, Any] = field(default_factory=dict)
    
    # Layout properties
    position_x: int = 0
    position_y: int = 0
    
    # Display properties
    show_title: bool = True
    show_border: bool = True
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    
    # Behavior
    refresh_interval: RefreshInterval = RefreshInterval.MANUAL
    auto_refresh: bool = False
    
    # Cached data
    last_updated: Optional[datetime] = None
    cached_data: Optional[WidgetData] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'widget_type': self.widget_type.value,
            'size': self.size.value,
            'data_source': self.data_source,
            'data_params': self.data_params,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'show_title': self.show_title,
            'show_border': self.show_border,
            'background_color': self.background_color,
            'text_color': self.text_color,
            'refresh_interval': self.refresh_interval.value,
            'auto_refresh': self.auto_refresh,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'cached_data': self.cached_data.to_dict() if self.cached_data else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Widget':
        """Create from dictionary"""
        widget = cls(
            id=data['id'],
            title=data['title'],
            widget_type=WidgetType(data['widget_type']),
            size=WidgetSize(data['size']),
            data_source=data['data_source'],
            data_params=data.get('data_params', {}),
            position_x=data.get('position_x', 0),
            position_y=data.get('position_y', 0),
            show_title=data.get('show_title', True),
            show_border=data.get('show_border', True),
            background_color=data.get('background_color'),
            text_color=data.get('text_color'),
            refresh_interval=RefreshInterval(data.get('refresh_interval', 0)),
            auto_refresh=data.get('auto_refresh', False)
        )
        
        if data.get('last_updated'):
            widget.last_updated = datetime.fromisoformat(data['last_updated'])
        
        if data.get('cached_data'):
            widget.cached_data = WidgetData(**data['cached_data'])
        
        return widget


@dataclass
class Dashboard:
    """Custom dashboard configuration"""
    id: str
    name: str
    description: str = ""
    widgets: List[Widget] = field(default_factory=list)
    
    # Layout properties
    columns: int = 12  # Grid columns
    auto_layout: bool = False
    
    # Access control
    is_public: bool = False
    owner: str = ""
    shared_with: List[str] = field(default_factory=list)
    
    # Metadata
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'widgets': [w.to_dict() for w in self.widgets],
            'columns': self.columns,
            'auto_layout': self.auto_layout,
            'is_public': self.is_public,
            'owner': self.owner,
            'shared_with': self.shared_with,
            'created': self.created.isoformat(),
            'modified': self.modified.isoformat(),
            'tags': self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dashboard':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            widgets=[Widget.from_dict(w) for w in data.get('widgets', [])],
            columns=data.get('columns', 12),
            auto_layout=data.get('auto_layout', False),
            is_public=data.get('is_public', False),
            owner=data.get('owner', ''),
            shared_with=data.get('shared_with', []),
            created=datetime.fromisoformat(data.get('created', datetime.now().isoformat())),
            modified=datetime.fromisoformat(data.get('modified', datetime.now().isoformat())),
            tags=data.get('tags', [])
        )
    
    def add_widget(self, widget: Widget):
        """Add widget to dashboard"""
        self.widgets.append(widget)
        self.modified = datetime.now()
    
    def remove_widget(self, widget_id: str) -> bool:
        """Remove widget from dashboard"""
        original_length = len(self.widgets)
        self.widgets = [w for w in self.widgets if w.id != widget_id]
        
        if len(self.widgets) < original_length:
            self.modified = datetime.now()
            return True
        return False
    
    def get_widget(self, widget_id: str) -> Optional[Widget]:
        """Get widget by ID"""
        return next((w for w in self.widgets if w.id == widget_id), None)


class DashboardManager:
    """Manager for custom dashboards"""
    
    def __init__(self):
        self.config = get_config()
        self.dashboards_dir = Path(self.config.data_dir) / "dashboards"
        self.dashboards_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data sources
        self.data_sources: Dict[str, DataSource] = {
            'todo_metrics': TodoMetricsDataSource(),
            'project_metrics': ProjectMetricsDataSource(),
            'time_tracking': TimeTrackingDataSource()
        }
    
    def create_dashboard(self, name: str, description: str = "") -> Dashboard:
        """Create a new dashboard"""
        dashboard = Dashboard(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            owner="current_user"  # In a real app, this would be the authenticated user
        )
        
        self.save_dashboard(dashboard)
        return dashboard
    
    def save_dashboard(self, dashboard: Dashboard):
        """Save dashboard to file"""
        dashboard.modified = datetime.now()
        file_path = self.dashboards_dir / f"{dashboard.id}.json"
        
        try:
            with open(file_path, 'w') as f:
                json.dump(dashboard.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving dashboard: {e}")
    
    def load_dashboard(self, dashboard_id: str) -> Optional[Dashboard]:
        """Load dashboard from file"""
        file_path = self.dashboards_dir / f"{dashboard_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            return Dashboard.from_dict(data)
        except Exception as e:
            print(f"Error loading dashboard: {e}")
            return None
    
    def list_dashboards(self) -> List[Dict[str, Any]]:
        """List all dashboards"""
        dashboards = []
        
        for file_path in self.dashboards_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                dashboards.append({
                    'id': data['id'],
                    'name': data['name'],
                    'description': data.get('description', ''),
                    'widget_count': len(data.get('widgets', [])),
                    'modified': data.get('modified')
                })
            except Exception:
                continue
        
        return dashboards
    
    def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete a dashboard"""
        file_path = self.dashboards_dir / f"{dashboard_id}.json"
        
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception as e:
                print(f"Error deleting dashboard: {e}")
        
        return False
    
    def create_widget(self, widget_type: WidgetType, title: str, data_source: str,
                     size: WidgetSize = WidgetSize.MEDIUM, **params) -> Widget:
        """Create a new widget"""
        return Widget(
            id=str(uuid.uuid4()),
            title=title,
            widget_type=widget_type,
            size=size,
            data_source=data_source,
            data_params=params
        )
    
    def refresh_widget_data(self, widget: Widget, todos: List[Todo]) -> bool:
        """Refresh data for a specific widget"""
        if widget.data_source not in self.data_sources:
            return False
        
        try:
            # Prepare parameters
            params = widget.data_params.copy()
            params['todos'] = todos
            
            # Fetch new data
            data_source = self.data_sources[widget.data_source]
            widget.cached_data = data_source.fetch_data(params)
            widget.last_updated = datetime.now()
            
            return True
        except Exception as e:
            print(f"Error refreshing widget {widget.id}: {e}")
            return False
    
    def refresh_dashboard_data(self, dashboard: Dashboard, todos: List[Todo]):
        """Refresh data for all widgets in a dashboard"""
        for widget in dashboard.widgets:
            self.refresh_widget_data(widget, todos)
        
        dashboard.modified = datetime.now()
    
    def get_widget_schema(self, data_source_name: str) -> Dict[str, Any]:
        """Get configuration schema for a data source"""
        if data_source_name in self.data_sources:
            return self.data_sources[data_source_name].get_schema()
        return {}
    
    def create_template_dashboard(self, template_name: str) -> Dashboard:
        """Create a dashboard from a predefined template"""
        
        if template_name == "productivity_overview":
            dashboard = self.create_dashboard(
                "Productivity Overview", 
                "General productivity metrics and insights"
            )
            
            # Add productivity score widget
            productivity_widget = self.create_widget(
                WidgetType.GAUGE,
                "Productivity Score",
                "todo_metrics",
                WidgetSize.MEDIUM,
                metric_type="productivity_score",
                timeframe="weekly"
            )
            productivity_widget.position_x = 0
            productivity_widget.position_y = 0
            dashboard.add_widget(productivity_widget)
            
            # Add completion rate widget
            completion_widget = self.create_widget(
                WidgetType.METRIC,
                "Completion Rate",
                "todo_metrics",
                WidgetSize.SMALL,
                metric_type="completion_rate",
                timeframe="weekly"
            )
            completion_widget.position_x = 6
            completion_widget.position_y = 0
            dashboard.add_widget(completion_widget)
            
            # Add overdue tasks widget
            overdue_widget = self.create_widget(
                WidgetType.METRIC,
                "Overdue Tasks",
                "todo_metrics",
                WidgetSize.SMALL,
                metric_type="overdue_tasks"
            )
            overdue_widget.position_x = 9
            overdue_widget.position_y = 0
            dashboard.add_widget(overdue_widget)
            
            # Add time tracking widget
            time_widget = self.create_widget(
                WidgetType.METRIC,
                "Hours Today",
                "time_tracking",
                WidgetSize.SMALL,
                metric_type="hours_today"
            )
            time_widget.position_x = 0
            time_widget.position_y = 3
            dashboard.add_widget(time_widget)
            
            return dashboard
        
        elif template_name == "project_dashboard":
            dashboard = self.create_dashboard(
                "Project Dashboard",
                "Project-focused metrics and tracking"
            )
            
            # Add project health widget
            health_widget = self.create_widget(
                WidgetType.GAUGE,
                "Project Health",
                "project_metrics",
                WidgetSize.MEDIUM,
                metric_type="project_health",
                project_name="default"
            )
            dashboard.add_widget(health_widget)
            
            # Add velocity widget
            velocity_widget = self.create_widget(
                WidgetType.METRIC,
                "Current Velocity",
                "project_metrics",
                WidgetSize.SMALL,
                metric_type="velocity",
                project_name="default"
            )
            dashboard.add_widget(velocity_widget)
            
            # Add burndown chart
            burndown_widget = self.create_widget(
                WidgetType.CHART_LINE,
                "Burndown Chart",
                "project_metrics",
                WidgetSize.LARGE,
                metric_type="burndown",
                project_name="default"
            )
            dashboard.add_widget(burndown_widget)
            
            return dashboard
        
        elif template_name == "time_tracking":
            dashboard = self.create_dashboard(
                "Time Tracking",
                "Time tracking and productivity analysis"
            )
            
            # Add current session widget
            session_widget = self.create_widget(
                WidgetType.METRIC,
                "Current Session",
                "time_tracking",
                WidgetSize.MEDIUM,
                metric_type="current_session"
            )
            dashboard.add_widget(session_widget)
            
            # Add daily hours widget
            hours_widget = self.create_widget(
                WidgetType.METRIC,
                "Hours Today",
                "time_tracking",
                WidgetSize.SMALL,
                metric_type="hours_today"
            )
            dashboard.add_widget(hours_widget)
            
            # Add focus score widget
            focus_widget = self.create_widget(
                WidgetType.GAUGE,
                "Focus Score",
                "time_tracking",
                WidgetSize.SMALL,
                metric_type="focus_score"
            )
            dashboard.add_widget(focus_widget)
            
            # Add productivity heatmap
            heatmap_widget = self.create_widget(
                WidgetType.CHART_HEATMAP,
                "Productivity Heatmap",
                "time_tracking",
                WidgetSize.LARGE,
                metric_type="productivity_heatmap"
            )
            dashboard.add_widget(heatmap_widget)
            
            return dashboard
        
        else:
            # Default empty dashboard
            return self.create_dashboard("Custom Dashboard", "")
    
    def export_dashboard(self, dashboard_id: str, format_type: str = "json") -> Optional[str]:
        """Export dashboard configuration"""
        dashboard = self.load_dashboard(dashboard_id)
        if not dashboard:
            return None
        
        if format_type == "json":
            return json.dumps(dashboard.to_dict(), indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def import_dashboard(self, data: str, format_type: str = "json") -> Optional[Dashboard]:
        """Import dashboard configuration"""
        try:
            if format_type == "json":
                dashboard_data = json.loads(data)
                # Generate new ID to avoid conflicts
                dashboard_data['id'] = str(uuid.uuid4())
                dashboard_data['created'] = datetime.now().isoformat()
                dashboard_data['modified'] = datetime.now().isoformat()
                
                dashboard = Dashboard.from_dict(dashboard_data)
                self.save_dashboard(dashboard)
                return dashboard
            else:
                raise ValueError(f"Unsupported import format: {format_type}")
        except Exception as e:
            print(f"Error importing dashboard: {e}")
            return None
    
    def get_dashboard_insights(self, dashboard: Dashboard) -> List[str]:
        """Generate insights about dashboard usage and effectiveness"""
        insights = []
        
        widget_count = len(dashboard.widgets)
        if widget_count == 0:
            insights.append("📊 Dashboard is empty - add widgets to start tracking metrics")
        elif widget_count > 20:
            insights.append("🔍 Dashboard has many widgets - consider organizing into multiple focused dashboards")
        
        # Check for data freshness
        stale_widgets = [w for w in dashboard.widgets 
                        if w.last_updated and (datetime.now() - w.last_updated).hours > 24]
        if stale_widgets:
            insights.append(f"⏰ {len(stale_widgets)} widgets have stale data - consider refreshing")
        
        # Check widget distribution
        widget_types = [w.widget_type.value for w in dashboard.widgets]
        if widget_types.count('metric') > len(widget_types) * 0.7:
            insights.append("📈 Dashboard is metric-heavy - consider adding charts for trend analysis")
        
        return insights