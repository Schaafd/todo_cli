"""Application services for Todo CLI."""

from .query_engine import QueryEngine
from .recommendations import (
    TaskRecommendationEngine,
    get_context_suggestions,
    get_energy_suggestions,
)
from .export import ExportManager, ExportFormat
from .notifications import NotificationManager, NotificationType, NotificationPreferences
from .analytics import (
    ProductivityAnalyzer,
    AnalyticsTimeframe,
    AnalyticsReport,
    ProductivityScore,
)
from .project_analytics import ProjectAnalyzer, ProjectHealthScore, ProjectForecast
from .time_tracking import (
    TimeTracker,
    TimeReport,
    ProductivityHeatmap,
    WorkPattern,
    EstimationAccuracy,
)
from .dashboard import DashboardManager, Dashboard, Widget, WidgetType
from .plugins import PluginManager, PluginType, PluginStatus

__all__ = [
    "QueryEngine",
    "TaskRecommendationEngine",
    "get_context_suggestions",
    "get_energy_suggestions",
    "ExportManager",
    "ExportFormat",
    "NotificationManager",
    "NotificationType",
    "NotificationPreferences",
    "ProductivityAnalyzer",
    "AnalyticsTimeframe",
    "AnalyticsReport",
    "ProductivityScore",
    "ProjectAnalyzer",
    "ProjectHealthScore",
    "ProjectForecast",
    "TimeTracker",
    "TimeReport",
    "ProductivityHeatmap",
    "WorkPattern",
    "EstimationAccuracy",
    "DashboardManager",
    "Dashboard",
    "Widget",
    "WidgetType",
    "PluginManager",
    "PluginType",
    "PluginStatus",
]
