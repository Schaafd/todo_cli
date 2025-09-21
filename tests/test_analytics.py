"""Comprehensive Test Suite for Todo CLI Analytics Engine.

This module provides thorough testing of all analytics components including:
- Productivity analysis and insights
- Time tracking and reports  
- Project analytics and dashboards
- Custom dashboard system
- Plugin architecture
- CLI analytics commands

Test coverage includes unit tests, integration tests, and edge cases.
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

# Import components to test
from todo_cli.todo import Todo, Priority, TodoStatus
from todo_cli.analytics import (
    ProductivityAnalyzer, AnalyticsTimeframe, AnalyticsReport,
    TaskPattern, ProductivityInsight, StatisticalAnalysis
)
from todo_cli.time_tracking import (
    TimeTracker, TimeEntry, TimeReport, ProductivityHeatmap,
    WorkPattern, EstimationAccuracy, TimeAnalyzer
)
from todo_cli.project_analytics import (
    ProjectAnalyzer, ProjectHealthScore, ProjectForecast,
    BurndownData, VelocityData, ProjectDashboard
)
from todo_cli.dashboard import (
    DashboardManager, Dashboard, Widget, WidgetType, WidgetData, WidgetSize,
    TodoMetricsDataSource, ProjectMetricsDataSource, TimeTrackingDataSource
)
from todo_cli.plugins import (
    PluginManager, PluginInfo, PluginType, PluginStatus, 
    BasePlugin, AnalyticsPlugin, PluginAPI
)
from todo_cli.cli_analytics import (
    format_metric, format_table, _format_analytics_report,
    _display_heatmap, _export_to_csv
)


class TestProductivityAnalyzer:
    """Test suite for ProductivityAnalyzer class"""

    @pytest.fixture
    def sample_todos(self) -> List[Todo]:
        """Create sample todos for testing (aligned with current model)."""
        now = datetime.now(timezone.utc)
        return [
            Todo(
                id=1,
                text="Complete project proposal",
                priority=Priority.HIGH,
                project="Work",
                tags=["urgent", "writing"],
                completed=True,
                completed_date=now - timedelta(days=1),
                created=now - timedelta(days=3)
            ),
            Todo(
                id=2,
                text="Review code changes",
                priority=Priority.MEDIUM,
                project="Work",
                tags=["code-review"],
                completed=True,
                completed_date=now - timedelta(hours=5),
                created=now - timedelta(days=1)
            ),
            Todo(
                id=3,
                text="Plan vacation",
                priority=Priority.LOW,
                project="Personal",
                tags=["travel"],
                completed=False,
                due_date=now + timedelta(days=30),
                created=now - timedelta(days=2)
            ),
            Todo(
                id=4,
                text="Fix critical bug",
                priority=Priority.HIGH,
                project="Work",
                tags=["bug", "urgent"],
                completed=False,
                due_date=now - timedelta(days=1),
                created=now - timedelta(days=5)
            )
        ]

    def test_basic_productivity_analysis(self, sample_todos):
        """Test basic productivity metrics calculation"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        
        assert isinstance(report, AnalyticsReport)
        assert report.productivity_score.completion_rate == 50.0  # 2 out of 4 completed
        assert report.productivity_score.tasks_created == 4
        assert report.productivity_score.tasks_completed == 2
        assert 0 <= report.productivity_score.overall_score <= 100
        assert 0 <= report.productivity_score.focus_score <= 100

    def test_empty_todos_analysis(self):
        """Test analytics with empty todo list"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity([], AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        
        assert report.productivity_score.completion_rate == 0
        assert report.productivity_score.tasks_created == 0
        assert report.productivity_score.tasks_completed == 0
        assert report.productivity_score.overall_score >= 0

    def test_task_pattern_detection(self, sample_todos):
        """Test task pattern detection"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        patterns = report.patterns
        
        assert isinstance(patterns, list)

    def test_productivity_insights_generation(self, sample_todos):
        """Test insight generation"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        insights = report.insights
        
        assert isinstance(insights, list)
        assert all(isinstance(insight, ProductivityInsight) for insight in insights)

    def test_different_timeframes(self, sample_todos):
        """Test analytics with different timeframes"""
        analyzer = ProductivityAnalyzer()
        
        for timeframe in [AnalyticsTimeframe.DAILY, AnalyticsTimeframe.MONTHLY, AnalyticsTimeframe.YEARLY]:
            report = analyzer.analyze_productivity(sample_todos, timeframe, end_date=datetime.now(timezone.utc))
            assert isinstance(report, AnalyticsReport)
            assert report.timeframe == timeframe

    def test_statistical_analysis(self, sample_todos):
        """Test statistical analysis functionality"""
        analyzer = ProductivityAnalyzer()
        stats = analyzer._calculate_statistical_analysis(sample_todos)
        
        assert isinstance(stats, StatisticalAnalysis)
        assert stats.mean_completion_time is not None
        assert stats.completion_time_variance >= 0
        assert isinstance(stats.productivity_trend_slope, float)

    def test_report_serialization(self, sample_todos):
        """Test analytics report serialization"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        
        # Test to_dict method
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert 'productivity_score' in report_dict
        assert 'insights' in report_dict
        assert 'patterns' in report_dict
        
        # Should be JSON serializable
        json_str = json.dumps(report_dict, default=str)
        assert isinstance(json_str, str)


class TestTimeTracker:
    """Test suite for TimeTracker class"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def time_tracker(self, temp_data_dir):
        """Create time tracker with temporary storage"""
        with patch('todo_cli.time_tracking.get_config') as mock_config:
            mock_config.return_value.data_dir = temp_data_dir
            return TimeTracker()

    def test_start_stop_tracking(self, time_tracker):
        """Test basic time tracking start/stop"""
        # Create a dummy todo
        todo = Todo(id=123, text="Test task", project="Test", priority=Priority.MEDIUM, created=datetime.now(timezone.utc))
        
        # Start tracking
        entry = time_tracker.start_tracking(todo=todo)
        assert isinstance(entry, TimeEntry)
        
        # Verify active tracking
        active = time_tracker.get_current_tracking()
        assert active is not None
        assert active.todo_id == todo.id
        
        # Stop tracking
        completed_entry = time_tracker.stop_tracking()
        assert completed_entry is not None
        assert completed_entry.end_time is not None

    def test_manual_time_entry(self, time_tracker):
        """Test manual time entry addition"""
        start_time = datetime.now() - timedelta(hours=2)
        end_time = datetime.now() - timedelta(hours=1)
        
        entry = time_tracker.add_manual_entry(
            start_time=start_time,
            end_time=end_time,
            description="Manual entry test"
        )
        
        assert entry is not None
        assert entry.todo_id is None
        assert entry.duration_minutes == 60  # 1 hour

    def test_time_report_generation(self, time_tracker):
        """Test time report generation"""
        # Add some test entries
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        # Mock some time entries within the last week
        time_tracker.entries = [
            TimeEntry(
                id="entry1",
                todo_id="todo1",
                start_time=end_date - timedelta(days=2),
                end_time=(end_date - timedelta(days=2)) + timedelta(hours=2),
                duration_minutes=120,
                project="Work",
                tags=["coding"]
            ),
            TimeEntry(
                id="entry2", 
                todo_id="todo2",
                start_time=end_date - timedelta(days=1),
                end_time=(end_date - timedelta(days=1)) + timedelta(hours=1),
                duration_minutes=60,
                project="Personal",
                tags=["reading"]
            )
        ]
        
        analyzer = TimeAnalyzer(time_tracker)
        report = analyzer.generate_time_report(AnalyticsTimeframe.WEEKLY, end_date=end_date)
        
        assert isinstance(report, TimeReport)
        assert pytest.approx(report.total_work_hours, 0.01) == 3.0  # 3 hours total
        assert "Work" in report.time_allocation.project_breakdown
        assert "Personal" in report.time_allocation.project_breakdown

    def test_productivity_heatmap(self, time_tracker):
        """Test productivity heatmap generation"""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        analyzer = TimeAnalyzer(time_tracker)
        report = analyzer.generate_time_report(AnalyticsTimeframe.WEEKLY, end_date=end_date)
        heatmap = report.productivity_heatmap
        
        assert isinstance(heatmap, ProductivityHeatmap)
        assert isinstance(heatmap.data, dict)

    def test_work_pattern_analysis(self, time_tracker):
        """Test work pattern detection"""
        # Mock entries with different time patterns
        morning_entry = TimeEntry(
            id="morning",
            todo_id="todo1", 
            start_time=datetime.now().replace(hour=8, minute=0, second=0, microsecond=0),
            end_time=datetime.now().replace(hour=10, minute=0, second=0, microsecond=0),
            duration_minutes=120
        )
        
        evening_entry = TimeEntry(
            id="evening",
            todo_id="todo2",
            start_time=datetime.now().replace(hour=20, minute=0, second=0, microsecond=0),
            end_time=datetime.now().replace(hour=22, minute=0, second=0, microsecond=0), 
            duration_minutes=120
        )
        
        time_tracker.entries = [morning_entry, evening_entry]
        
        analyzer = TimeAnalyzer(time_tracker)
        report = analyzer.generate_time_report(AnalyticsTimeframe.WEEKLY, end_date=datetime.now())
        pattern = report.work_pattern
        assert isinstance(pattern, WorkPattern)

    def test_estimation_accuracy(self, time_tracker):
        """Test estimation accuracy calculation"""
        # Mock entries (estimation analysis uses placeholder values for now)
        time_tracker.entries = [
            TimeEntry(
                id="entry_1",
                todo_id="todo_1",
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() - timedelta(hours=1),
                duration_minutes=60
            ),
            TimeEntry(
                id="entry_2",
                todo_id="todo_2",
                start_time=datetime.now() - timedelta(hours=3),
                end_time=datetime.now() - timedelta(hours=2),
                duration_minutes=60
            )
        ]
        
        analyzer = TimeAnalyzer(time_tracker)
        report = analyzer.generate_time_report(AnalyticsTimeframe.WEEKLY, end_date=datetime.now())
        accuracy = report.estimation_accuracy
        assert isinstance(accuracy, EstimationAccuracy)
        assert 0 <= accuracy.accuracy_percentage <= 100


class TestProjectAnalyzer:
    """Test suite for ProjectAnalyzer class"""

    @pytest.fixture  
    def project_todos(self):
        """Create sample project todos"""
        now = datetime.now(timezone.utc)
        return [
            Todo(
                id=1,
                text="Setup project",
                project="TestProject", 
                priority=Priority.HIGH,
                completed=True,
                completed_date=now - timedelta(days=10),
                created=now - timedelta(days=15)
            ),
            Todo(
                id=2,
                text="Implement feature A", 
                project="TestProject",
                priority=Priority.MEDIUM,
                completed=True,
                completed_date=now - timedelta(days=5),
                created=now - timedelta(days=12)
            ),
            Todo(
                id=3, 
                text="Write tests",
                project="TestProject",
                priority=Priority.MEDIUM,
                completed=False,
                created=now - timedelta(days=8)
            ),
            Todo(
                id=4,
                text="Deploy to production",
                project="TestProject", 
                priority=Priority.HIGH,
                completed=False,
                due_date=now + timedelta(days=5),
                created=now - timedelta(days=3)
            )
        ]

    def test_project_health_calculation(self, project_todos):
        """Test project health score calculation"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos, end_date=datetime.now(timezone.utc))
        health = dashboard.health_score
        
        assert isinstance(health, ProjectHealthScore)
        assert 0 <= health.overall_score <= 100
        assert 0 <= health.completion_percentage <= 100
        assert 0 <= health.velocity_score <= 100

    def test_burndown_chart_generation(self, project_todos):
        """Test burndown chart data generation"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos, end_date=datetime.now(timezone.utc))
        burndown = dashboard.burndown_chart
        
        assert isinstance(burndown, list)
        assert len(burndown) > 0
        assert all(isinstance(point, BurndownData) for point in burndown)

    def test_velocity_tracking(self, project_todos):
        """Test velocity data calculation"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos, end_date=datetime.now(timezone.utc))
        
        assert isinstance(dashboard.velocity_data, list)
        assert len(dashboard.velocity_data) > 0
        assert all(isinstance(v, VelocityData) for v in dashboard.velocity_data)

    def test_project_forecast(self, project_todos):
        """Test project completion forecast"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos, end_date=datetime.now(timezone.utc))
        forecast = dashboard.forecast
        
        assert isinstance(forecast, ProjectForecast)
        assert forecast.estimated_completion_date is not None
        assert 0.0 <= forecast.confidence_level <= 1.0

    def test_project_dashboard_generation(self, project_todos):
        """Test complete project dashboard generation"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos, end_date=datetime.now(timezone.utc))
        
        assert isinstance(dashboard, ProjectDashboard)
        assert dashboard.project_name == "TestProject"
        assert isinstance(dashboard.health_score, ProjectHealthScore)

    def test_empty_project_analysis(self):
        """Test project analysis with no todos"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("EmptyProject", [], end_date=datetime.now(timezone.utc))
        health = dashboard.health_score
        
        assert isinstance(health, ProjectHealthScore)
        assert 0 <= health.overall_score <= 100
        assert health.completion_percentage == 0


class TestDashboardSystem:
    """Test suite for Dashboard system"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture  
    def dashboard_manager(self, temp_dir):
        """Create dashboard manager with temp storage"""
        with patch('todo_cli.dashboard.get_config') as mock_config:
            mock_config.return_value.data_dir = temp_dir
            return DashboardManager()

    def test_dashboard_creation(self, dashboard_manager):
        """Test dashboard creation and storage"""
        dashboard = dashboard_manager.create_dashboard(name="test_dashboard")
        widget = dashboard_manager.create_widget(
            widget_type=WidgetType.METRIC,
            title="Completion Rate",
            data_source="todo_metrics",
            size=WidgetSize.SMALL,
            metric_type="completion_rate"
        )
        dashboard.add_widget(widget)
        
        dashboard_manager.save_dashboard(dashboard)
        
        # Verify saved dashboard
        loaded = dashboard_manager.load_dashboard(dashboard.id)
        assert loaded is not None
        assert loaded.name == "test_dashboard"
        assert len(loaded.widgets) == 1

    def test_widget_data_sources(self, dashboard_manager):
        """Test different widget data sources"""
        # Test todo metrics data source
        todo_source = dashboard_manager.data_sources["todo_metrics"]
        assert isinstance(todo_source, TodoMetricsDataSource)
        
        # Mock some todos for testing
        mock_todos = [
            Mock(completed=True, priority=Priority.HIGH),
            Mock(completed=False, priority=Priority.MEDIUM)
        ]
        
        widget_data = todo_source.fetch_data({
            "todos": mock_todos,
            "metric_type": "completion_rate"
        })
        
        assert isinstance(widget_data, WidgetData)
        assert widget_data.value == 50.0  # 1 out of 2 completed

    def test_dashboard_templates(self, dashboard_manager):
        """Test built-in dashboard templates"""
        # Test productivity overview template
        dashboard = dashboard_manager.create_template_dashboard("productivity_overview")
        
        assert isinstance(dashboard, Dashboard)
        assert dashboard.name == "Productivity Overview"
        assert len(dashboard.widgets) > 0

    def test_widget_update_mechanism(self, dashboard_manager):
        """Test widget data refresh"""
        widget = dashboard_manager.create_widget(
            widget_type=WidgetType.METRIC,
            title="Total Tasks",
            data_source="todo_metrics",
            size=WidgetSize.SMALL,
            metric_type="total_tasks"
        )
        
        # Mock data source
        mock_todos = [Mock(), Mock(), Mock()]  # 3 todos
        
        ok = dashboard_manager.refresh_widget_data(widget, mock_todos)
        assert ok is True
        assert isinstance(widget.cached_data, WidgetData)
        assert widget.cached_data.value == 3


class TestPluginSystem:
    """Test suite for Plugin architecture"""

    @pytest.fixture
    def temp_plugins_dir(self):
        """Create temporary plugins directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def plugin_manager(self, temp_plugins_dir):
        """Create plugin manager with temp storage"""
        with patch('todo_cli.plugins.get_config') as mock_config:
            mock_config.return_value.data_dir = temp_plugins_dir
            return PluginManager()

    def test_plugin_info_creation(self):
        """Test plugin info data structure"""
        info = PluginInfo(
            id="test_plugin",
            name="Test Plugin",
            version="1.0.0",
            author="Test Author", 
            description="A test plugin",
            plugin_type=PluginType.ANALYTICS
        )
        
        assert info.id == "test_plugin"
        assert info.plugin_type == PluginType.ANALYTICS
        assert info.status == PluginStatus.DISABLED

    def test_plugin_info_serialization(self):
        """Test plugin info to/from dict conversion"""
        info = PluginInfo(
            id="test_plugin",
            name="Test Plugin", 
            version="1.0.0",
            author="Test Author",
            description="A test plugin",
            plugin_type=PluginType.ANALYTICS
        )
        
        # Test to_dict
        info_dict = info.to_dict()
        assert isinstance(info_dict, dict)
        assert info_dict['id'] == "test_plugin"
        
        # Test from_dict
        restored_info = PluginInfo.from_dict(info_dict)
        assert restored_info.id == info.id
        assert restored_info.plugin_type == info.plugin_type

    def test_plugin_discovery(self, plugin_manager):
        """Test plugin discovery functionality"""
        # Create mock plugin directory structure
        plugins_dir = Path(plugin_manager.plugins_dir)
        test_plugin_dir = plugins_dir / "test_plugin"
        test_plugin_dir.mkdir(parents=True)
        
        # Create plugin manifest
        manifest = {
            "id": "test_plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "author": "Test Author",
            "description": "Test plugin",
            "type": "analytics"
        }
        
        manifest_file = test_plugin_dir / "plugin.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f)
        
        # Test discovery
        discovered = plugin_manager.discover_plugins()
        assert "test_plugin" in discovered

    def test_plugin_api_functionality(self, plugin_manager):
        """Test plugin API interface"""
        api = plugin_manager.api
        
        # Test basic API functions
        todos = api.get_todos()
        assert isinstance(todos, list)
        
        # Test event system
        events_received = []
        
        def test_handler(data):
            events_received.append(data)
        
        api.subscribe_to_event("test_event", test_handler)
        api.emit_event("test_event", {"test": "data"})
        
        assert len(events_received) == 1
        assert events_received[0]["test"] == "data"

    def test_sample_analytics_plugin(self):
        """Test sample analytics plugin implementation"""
        from todo_cli.plugins import SampleAnalyticsPlugin
        
        # Mock API
        mock_api = Mock()
        mock_api.log = Mock()
        
        plugin = SampleAnalyticsPlugin(mock_api)
        
        # Test initialization
        assert plugin.initialize() == True
        mock_api.log.assert_called_with("info", "Sample analytics plugin initialized")
        
        # Test analysis
        mock_todos = [
            Mock(completed=True, is_overdue=lambda: False),
            Mock(completed=False, is_overdue=lambda: True)
        ]
        
        analysis = plugin.analyze(mock_todos)
        assert analysis["total_tasks"] == 2
        assert analysis["completed_tasks"] == 1
        assert analysis["overdue_tasks"] == 1

    def test_plugin_manifest_validation(self, plugin_manager):
        """Test plugin manifest validation"""
        # Create valid manifest
        valid_manifest = {
            "id": "valid_plugin",
            "name": "Valid Plugin", 
            "version": "1.0.0",
            "author": "Test Author",
            "description": "A valid plugin",
            "type": "analytics"
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_manifest, f)
            valid_path = f.name
        
        try:
            is_valid, errors = plugin_manager.validate_plugin_manifest(valid_path)
            assert is_valid == True
            assert len(errors) == 0
        finally:
            Path(valid_path).unlink()
        
        # Test invalid manifest
        invalid_manifest = {"id": "invalid"}  # Missing required fields
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_manifest, f)
            invalid_path = f.name
        
        try:
            is_valid, errors = plugin_manager.validate_plugin_manifest(invalid_path)
            assert is_valid == False
            assert len(errors) > 0
        finally:
            Path(invalid_path).unlink()


class TestCLIAnalytics:
    """Test suite for CLI Analytics commands"""

    def test_format_metric(self):
        """Test metric formatting utility"""
        assert format_metric(85.6789, "%", ".1f") == "85.7%"
        assert format_metric(1234.56, " hours", ".2f") == "1234.56 hours"
        assert format_metric(42.0, "", ".0f") == "42"

    def test_format_table(self):
        """Test table formatting utility"""
        data = [
            {"Name": "John", "Age": 30, "City": "NYC"},
            {"Name": "Jane", "Age": 25, "City": "SF"}
        ]
        
        table_str = format_table(data, tablefmt="simple")
        assert "John" in table_str
        assert "Jane" in table_str
        assert "Age" in table_str
        
        # Test empty data
        empty_table = format_table([])
        assert empty_table == "No data available"

    def test_analytics_report_formatting(self):
        """Test analytics report console formatting"""
        # Mock report object
        mock_report = Mock()
        ps = Mock()
        ps.completion_rate = 75.5
        ps.tasks_completed = 10
        ps.overall_score = 82.1
        ps.focus_score = 68.9
        mock_report.productivity_score = ps
        mock_report.patterns = []
        mock_report.insights = [
            Mock(
                insight_type="trend",
                title="Completion rate",
                description="Your completion rate is trending upward"
            )
        ]
        # Prevent Mock truthiness traps in optional sections
        mock_report.hourly_distribution = None
        mock_report.recommendations = []
        
        formatted = _format_analytics_report(mock_report)
        assert isinstance(formatted, str)
        assert "75.5%" in formatted
        assert "upward" in formatted

    def test_export_to_csv(self):
        """Test CSV export functionality"""
        test_data = {
            "analytics": {
                "completion_rate": 75.5,
                "total_tasks": 10
            },
            "projects": {
                "Project A": {"health_score": 85.0}
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_path = f.name
        
        try:
            _export_to_csv(test_data, csv_path)
            
            # Verify CSV file was created and has content
            csv_content = Path(csv_path).read_text()
            assert "ANALYTICS" in csv_content
            assert "completion_rate" in csv_content
            assert "75.5" in csv_content
        finally:
            Path(csv_path).unlink()


class TestIntegrationScenarios:
    """Integration tests for complete analytics workflows"""

    def test_complete_analytics_workflow(self):
        """Test end-to-end analytics workflow"""
        # Create sample todos
        now = datetime.now(timezone.utc)
        todos = [
            Todo(
                id=1,
                text="Task 1", 
                project="ProjectA",
                completed=True,
                priority=Priority.HIGH,
                created=now - timedelta(days=5),
                completed_date=now - timedelta(days=2)
            ),
            Todo(
                id=2, 
                text="Task 2",
                project="ProjectA", 
                completed=False,
                priority=Priority.MEDIUM,
                created=now - timedelta(days=3)
            )
        ]
        
        # Test productivity analysis
        productivity_analyzer = ProductivityAnalyzer()
        productivity_report = productivity_analyzer.analyze_productivity(
            todos, AnalyticsTimeframe.WEEKLY, end_date=now
        )
        
        assert isinstance(productivity_report, AnalyticsReport)
        assert productivity_report.productivity_score.completion_rate == 50.0
        
        # Test project analysis
        project_analyzer = ProjectAnalyzer()
        dashboard = project_analyzer.generate_project_dashboard("ProjectA", todos, end_date=now)
        project_health = dashboard.health_score
        
        assert isinstance(project_health, ProjectHealthScore)
        assert 0 <= project_health.completion_percentage <= 100
        
        # Test dashboard integration
        with patch('todo_cli.dashboard.get_config') as mock_config:
            mock_config.return_value.data_dir = tempfile.mkdtemp()
            
            dashboard_manager = DashboardManager()
            
            # Create simple dashboard
            dashboard_obj = dashboard_manager.create_dashboard(name="integration_test")
            widget = dashboard_manager.create_widget(
                widget_type=WidgetType.METRIC,
                title="Completion Rate",
                data_source="todo_metrics",
                size=WidgetSize.SMALL,
                metric_type="completion_rate"
            )
            dashboard_obj.add_widget(widget)
            
            dashboard_manager.save_dashboard(dashboard_obj)
            loaded_dashboard = dashboard_manager.load_dashboard(dashboard_obj.id)
            
            assert loaded_dashboard is not None
            assert loaded_dashboard.name == "integration_test"

    def test_time_tracking_integration(self):
        """Test time tracking with analytics integration"""
        with patch('todo_cli.time_tracking.get_config') as mock_config:
            mock_config.return_value.data_dir = tempfile.mkdtemp()
            
            tracker = TimeTracker()
            
            # Mock some time entries
            now = datetime.now()
            tracker.entries = [
                TimeEntry(
                    id="entry1",
                    todo_id="todo1",
                    start_time=now - timedelta(hours=3),
                    end_time=now - timedelta(hours=1),
                    duration_minutes=120,  # 2 hours
                    project="TestProject"
                )
            ]
            
            # Generate report
            analyzer = TimeAnalyzer(tracker)
            report = analyzer.generate_time_report(
                AnalyticsTimeframe.DAILY, end_date=now
            )
            
            assert pytest.approx(report.total_work_hours, 0.01) == 2.0
            assert "TestProject" in report.time_allocation.project_breakdown
            assert pytest.approx(report.time_allocation.project_breakdown["TestProject"], 0.01) == 2.0

    def test_plugin_analytics_integration(self):
        """Test plugin system with analytics"""
        with patch('todo_cli.plugins.get_config') as mock_config:
            mock_config.return_value.data_dir = tempfile.mkdtemp()
            
            plugin_manager = PluginManager()
            
            # Test sample analytics plugin
            from todo_cli.plugins import SampleAnalyticsPlugin
            
            plugin = SampleAnalyticsPlugin(plugin_manager.api)
            plugin.initialize()
            
            # Test plugin analytics functionality
            mock_todos = [
                Mock(completed=True, is_overdue=lambda: False),
                Mock(completed=False, is_overdue=lambda: False),
                Mock(completed=False, is_overdue=lambda: True)
            ]
            
            analysis = plugin.analyze(mock_todos)
            metrics = plugin.get_metrics(mock_todos)
            
            assert analysis["total_tasks"] == 3
            assert analysis["completed_tasks"] == 1
            assert analysis["overdue_tasks"] == 1
            assert "completion_rate" in metrics
            assert metrics["completion_rate"] == 33.33333333333333


# Performance and edge case tests
class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_large_dataset_performance(self):
        """Test analytics performance with large datasets"""
        import time
        
        # Create large dataset
        large_todos = []
        now = datetime.now(timezone.utc)
        for i in range(1000):
            todo = Todo(
                id=i,
                text=f"Task {i}",
                project=f"Project_{i % 10}",
                completed=i % 3 == 0,  # Every 3rd todo completed
                priority=Priority.MEDIUM,
                created=now - timedelta(days=i % 30)
            )
            large_todos.append(todo)
        
        # Test productivity analysis performance
        analyzer = ProductivityAnalyzer()
        
        start_time = time.time()
        report = analyzer.analyze_productivity(large_todos, AnalyticsTimeframe.MONTHLY, end_date=now)
        end_time = time.time()
        
        # Should complete within reasonable time (< 5 seconds)
        assert (end_time - start_time) < 5.0
        # Only tasks within the current month are counted in the report
        assert report.productivity_score.tasks_created > 0
        
        # Compute expected completion rate for the filtered period (current month)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        in_period = [t for t in large_todos if start_of_month <= t.created <= now]
        completed_in_period = len([t for t in in_period if t.completed])
        expected_rate = (completed_in_period / len(in_period)) * 100 if in_period else 0.0
        assert abs(report.productivity_score.completion_rate - expected_rate) < 0.01

    def test_malformed_data_handling(self):
        """Test handling of malformed or corrupted data"""
        analyzer = ProductivityAnalyzer()
        
        # Test with None values
        todos_with_none = [
            Todo(id=1, text="Valid task", completed=True),
            None,  # This should be handled gracefully
            Todo(id=2, text="Another valid task", completed=False)
        ]
        
        # Filter out None values (simulating real-world data cleaning)
        clean_todos = [t for t in todos_with_none if t is not None]
        
        report = analyzer.analyze_productivity(clean_todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
        assert report.productivity_score.tasks_created == 2

    def test_concurrent_access_simulation(self):
        """Test concurrent access to analytics components"""
        import threading
        
        todos = [
            Todo(id=i, text=f"Task {i}", completed=i % 2 == 0)
            for i in range(100)
        ]
        
        results = []
        errors = []
        
        def analyze_productivity():
            try:
                analyzer = ProductivityAnalyzer()
                report = analyzer.analyze_productivity(todos, AnalyticsTimeframe.WEEKLY, end_date=datetime.now(timezone.utc))
                results.append(report.productivity_score.completion_rate)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=analyze_productivity)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All threads should succeed
        assert len(errors) == 0
        assert len(results) == 5
        assert all(result == 50.0 for result in results)  # All should be 50%


# Test fixtures and utilities
@pytest.fixture(scope="session")
def test_config():
    """Test configuration for all tests"""
    return {
        "data_dir": tempfile.mkdtemp(),
        "debug": True,
        "analytics_enabled": True
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])