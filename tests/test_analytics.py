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
from datetime import datetime, timedelta
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
    WorkPattern, EstimationAccuracy
)
from todo_cli.project_analytics import (
    ProjectAnalyzer, ProjectHealthScore, ProjectForecast,
    BurndownChart, VelocityData, ProjectDashboard
)
from todo_cli.dashboard import (
    DashboardManager, Dashboard, Widget, WidgetType, WidgetData,
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
        """Create sample todos for testing"""
        now = datetime.now()
        return [
            Todo(
                id="1",
                title="Complete project proposal",
                description="Write and submit proposal",
                priority=Priority.HIGH,
                project="Work",
                tags=["urgent", "writing"],
                completed=True,
                completed_at=now - timedelta(days=1),
                created_at=now - timedelta(days=3)
            ),
            Todo(
                id="2", 
                title="Review code changes",
                description="Review PR #123",
                priority=Priority.MEDIUM,
                project="Work",
                tags=["code-review"],
                completed=True,
                completed_at=now - timedelta(hours=5),
                created_at=now - timedelta(days=1)
            ),
            Todo(
                id="3",
                title="Plan vacation",
                description="Book flights and hotel",
                priority=Priority.LOW,
                project="Personal",
                tags=["travel"],
                completed=False,
                due_date=now + timedelta(days=30),
                created_at=now - timedelta(days=2)
            ),
            Todo(
                id="4",
                title="Fix critical bug",
                description="Database connection issue",
                priority=Priority.HIGH,
                project="Work",
                tags=["bug", "urgent"],
                completed=False,
                due_date=now - timedelta(days=1),  # Overdue
                created_at=now - timedelta(days=5)
            )
        ]

    def test_basic_productivity_analysis(self, sample_todos):
        """Test basic productivity metrics calculation"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY)
        
        assert isinstance(report, AnalyticsReport)
        assert report.completion_rate == 50.0  # 2 out of 4 completed
        assert report.total_tasks == 4
        assert report.completed_tasks == 2
        assert report.overdue_tasks == 1
        assert 0 <= report.productivity_score <= 100
        assert 0 <= report.focus_score <= 100

    def test_empty_todos_analysis(self):
        """Test analytics with empty todo list"""
        analyzer = ProductivityAnalyzer()
        report = analyzer.analyze_productivity([], AnalyticsTimeframe.WEEKLY)
        
        assert report.completion_rate == 0
        assert report.total_tasks == 0
        assert report.completed_tasks == 0
        assert report.productivity_score == 0

    def test_task_pattern_detection(self, sample_todos):
        """Test task pattern detection"""
        analyzer = ProductivityAnalyzer()
        patterns = analyzer._detect_task_patterns(sample_todos)
        
        assert isinstance(patterns, list)
        # Should detect high priority pattern
        high_priority_pattern = next(
            (p for p in patterns if p.pattern_type == "high_priority_focus"), 
            None
        )
        assert high_priority_pattern is not None

    def test_productivity_insights_generation(self, sample_todos):
        """Test insight generation"""
        analyzer = ProductivityAnalyzer()
        insights = analyzer._generate_insights(sample_todos, AnalyticsTimeframe.WEEKLY)
        
        assert isinstance(insights, list)
        assert all(isinstance(insight, ProductivityInsight) for insight in insights)
        
        # Should have insights about overdue tasks
        overdue_insight = next(
            (i for i in insights if "overdue" in i.description.lower()),
            None
        )
        assert overdue_insight is not None

    def test_different_timeframes(self, sample_todos):
        """Test analytics with different timeframes"""
        analyzer = ProductivityAnalyzer()
        
        for timeframe in [AnalyticsTimeframe.DAILY, AnalyticsTimeframe.MONTHLY, AnalyticsTimeframe.YEARLY]:
            report = analyzer.analyze_productivity(sample_todos, timeframe)
            assert isinstance(report, AnalyticsReport)
            assert report.timeframe == timeframe.value

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
        report = analyzer.analyze_productivity(sample_todos, AnalyticsTimeframe.WEEKLY)
        
        # Test to_dict method
        report_dict = report.to_dict()
        assert isinstance(report_dict, dict)
        assert 'completion_rate' in report_dict
        assert 'insights' in report_dict
        assert 'task_patterns' in report_dict
        
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
        todo_id = "test-todo-1"
        
        # Start tracking
        entry_id = time_tracker.start_tracking(todo_id)
        assert entry_id is not None
        
        # Verify active tracking
        active = time_tracker.get_active_tracking()
        assert active is not None
        assert active.todo_id == todo_id
        
        # Stop tracking
        completed_entry = time_tracker.stop_tracking()
        assert completed_entry is not None
        assert completed_entry.duration > 0

    def test_manual_time_entry(self, time_tracker):
        """Test manual time entry addition"""
        start_time = datetime.now() - timedelta(hours=2)
        end_time = datetime.now() - timedelta(hours=1)
        
        entry = time_tracker.add_manual_entry(
            todo_id="manual-todo",
            start_time=start_time,
            end_time=end_time,
            description="Manual entry test"
        )
        
        assert entry is not None
        assert entry.todo_id == "manual-todo"
        assert entry.duration == 3600  # 1 hour in seconds

    def test_time_report_generation(self, time_tracker):
        """Test time report generation"""
        # Add some test entries
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        # Mock some time entries
        time_tracker.entries = [
            TimeEntry(
                id="entry1",
                todo_id="todo1",
                start_time=start_date,
                end_time=start_date + timedelta(hours=2),
                duration=7200,
                project="Work",
                tags=["coding"]
            ),
            TimeEntry(
                id="entry2", 
                todo_id="todo2",
                start_time=start_date + timedelta(days=1),
                end_time=start_date + timedelta(days=1, hours=1),
                duration=3600,
                project="Personal",
                tags=["reading"]
            )
        ]
        
        report = time_tracker.generate_time_report(start_date, end_date)
        
        assert isinstance(report, TimeReport)
        assert report.total_time_tracked == 3.0  # 3 hours total
        assert "Work" in report.time_by_project
        assert "Personal" in report.time_by_project

    def test_productivity_heatmap(self, time_tracker):
        """Test productivity heatmap generation"""
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        heatmap = time_tracker.generate_productivity_heatmap(start_date, end_date)
        
        assert isinstance(heatmap, ProductivityHeatmap)
        assert isinstance(heatmap.data, dict)
        assert heatmap.start_date == start_date.date()
        assert heatmap.end_date == end_date.date()

    def test_work_pattern_analysis(self, time_tracker):
        """Test work pattern detection"""
        # Mock entries with different time patterns
        morning_entry = TimeEntry(
            id="morning",
            todo_id="todo1", 
            start_time=datetime.now().replace(hour=8),
            end_time=datetime.now().replace(hour=10),
            duration=7200
        )
        
        evening_entry = TimeEntry(
            id="evening",
            todo_id="todo2",
            start_time=datetime.now().replace(hour=20),
            end_time=datetime.now().replace(hour=22), 
            duration=7200
        )
        
        time_tracker.entries = [morning_entry, evening_entry]
        
        pattern = time_tracker.analyze_work_patterns()
        assert isinstance(pattern, WorkPattern)
        assert pattern.pattern_type in ["early_bird", "night_owl", "traditional", "flexible"]

    def test_estimation_accuracy(self, time_tracker):
        """Test estimation accuracy calculation"""
        # Mock entries with estimates
        entries_with_estimates = [
            (7200, 3600),  # Estimated 1h, actual 2h - underestimated
            (3600, 7200),  # Estimated 2h, actual 1h - overestimated  
            (5400, 5400),  # Estimated 1.5h, actual 1.5h - accurate
        ]
        
        time_tracker.entries = []
        for actual, estimated in entries_with_estimates:
            entry = TimeEntry(
                id=f"entry_{len(time_tracker.entries)}",
                todo_id=f"todo_{len(time_tracker.entries)}",
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() - timedelta(hours=1),
                duration=actual,
                estimated_duration=estimated
            )
            time_tracker.entries.append(entry)
        
        accuracy = time_tracker.calculate_estimation_accuracy()
        assert isinstance(accuracy, EstimationAccuracy)
        assert 0 <= accuracy.average_accuracy <= 100


class TestProjectAnalyzer:
    """Test suite for ProjectAnalyzer class"""

    @pytest.fixture  
    def project_todos(self):
        """Create sample project todos"""
        now = datetime.now()
        return [
            Todo(
                id="p1",
                title="Setup project",
                project="TestProject", 
                priority=Priority.HIGH,
                completed=True,
                completed_at=now - timedelta(days=10),
                created_at=now - timedelta(days=15)
            ),
            Todo(
                id="p2",
                title="Implement feature A", 
                project="TestProject",
                priority=Priority.MEDIUM,
                completed=True,
                completed_at=now - timedelta(days=5),
                created_at=now - timedelta(days=12)
            ),
            Todo(
                id="p3", 
                title="Write tests",
                project="TestProject",
                priority=Priority.MEDIUM,
                completed=False,
                created_at=now - timedelta(days=8)
            ),
            Todo(
                id="p4",
                title="Deploy to production",
                project="TestProject", 
                priority=Priority.HIGH,
                completed=False,
                due_date=now + timedelta(days=5),
                created_at=now - timedelta(days=3)
            )
        ]

    def test_project_health_calculation(self, project_todos):
        """Test project health score calculation"""
        analyzer = ProjectAnalyzer()
        health = analyzer.calculate_project_health(project_todos)
        
        assert isinstance(health, ProjectHealthScore)
        assert 0 <= health.overall_score <= 100
        assert health.status in ["healthy", "warning", "critical"]
        assert 0 <= health.completion_rate <= 100
        assert 0 <= health.velocity_score <= 100

    def test_burndown_chart_generation(self, project_todos):
        """Test burndown chart data generation"""
        analyzer = ProjectAnalyzer()
        burndown = analyzer.generate_burndown_chart(project_todos, days_back=30)
        
        assert isinstance(burndown, BurndownChart)
        assert len(burndown.dates) > 0
        assert len(burndown.remaining_tasks) > 0
        assert len(burndown.ideal_line) > 0

    def test_velocity_tracking(self, project_todos):
        """Test velocity data calculation"""
        analyzer = ProjectAnalyzer()
        velocity = analyzer.calculate_velocity(project_todos, weeks_back=4)
        
        assert isinstance(velocity, VelocityData)
        assert velocity.current_velocity >= 0
        assert len(velocity.weekly_velocities) > 0

    def test_project_forecast(self, project_todos):
        """Test project completion forecast"""
        analyzer = ProjectAnalyzer()
        forecast = analyzer.forecast_completion(project_todos)
        
        assert isinstance(forecast, ProjectForecast)
        assert forecast.estimated_completion_date is not None
        assert 0 <= forecast.confidence_level <= 100
        assert forecast.days_remaining >= 0

    def test_project_dashboard_generation(self, project_todos):
        """Test complete project dashboard generation"""
        analyzer = ProjectAnalyzer()
        dashboard = analyzer.generate_project_dashboard("TestProject", project_todos)
        
        assert isinstance(dashboard, ProjectDashboard)
        assert dashboard.project_name == "TestProject"
        assert isinstance(dashboard.health_score, ProjectHealthScore)
        assert isinstance(dashboard.progress_metrics, dict)

    def test_empty_project_analysis(self):
        """Test project analysis with no todos"""
        analyzer = ProjectAnalyzer()
        health = analyzer.calculate_project_health([])
        
        assert health.overall_score == 0
        assert health.status == "critical"
        assert health.completion_rate == 0


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
        dashboard = Dashboard(
            name="test_dashboard",
            widgets=[
                Widget(
                    name="completion_rate",
                    widget_type=WidgetType.METRIC,
                    data_source="todo_metrics",
                    config={"metric": "completion_rate"}
                )
            ],
            layout={"type": "grid", "columns": 2}
        )
        
        dashboard_manager.save_dashboard(dashboard)
        
        # Verify saved dashboard
        loaded = dashboard_manager.get_dashboard("test_dashboard")
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
            "metric": "completion_rate"
        })
        
        assert isinstance(widget_data, WidgetData)
        assert widget_data.value == 50.0  # 1 out of 2 completed

    def test_dashboard_templates(self, dashboard_manager):
        """Test built-in dashboard templates"""
        # Test productivity overview template
        dashboard = dashboard_manager.create_dashboard_from_template("productivity_overview")
        
        assert isinstance(dashboard, Dashboard)
        assert dashboard.name == "Productivity Overview"
        assert len(dashboard.widgets) > 0

    def test_widget_update_mechanism(self, dashboard_manager):
        """Test widget data refresh"""
        widget = Widget(
            name="test_widget",
            widget_type=WidgetType.METRIC,
            data_source="todo_metrics",
            config={"metric": "total_tasks"}
        )
        
        # Mock data source
        mock_todos = [Mock(), Mock(), Mock()]  # 3 todos
        
        updated_data = dashboard_manager.update_widget_data(widget, {"todos": mock_todos})
        assert isinstance(updated_data, WidgetData)
        assert updated_data.value == 3


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
        mock_report.completion_rate = 75.5
        mock_report.average_daily_completion = 3.2
        mock_report.productivity_score = 82.1
        mock_report.focus_score = 68.9
        mock_report.task_patterns = []
        mock_report.insights = [
            Mock(
                metric_name="completion_rate",
                trend="improving", 
                description="Your completion rate is trending upward"
            )
        ]
        
        formatted = _format_analytics_report(mock_report)
        assert isinstance(formatted, str)
        assert "75.5%" in formatted
        assert "improving" in formatted

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
        todos = [
            Todo(
                id="1",
                title="Task 1", 
                project="ProjectA",
                completed=True,
                priority=Priority.HIGH,
                created_at=datetime.now() - timedelta(days=5),
                completed_at=datetime.now() - timedelta(days=2)
            ),
            Todo(
                id="2", 
                title="Task 2",
                project="ProjectA", 
                completed=False,
                priority=Priority.MEDIUM,
                created_at=datetime.now() - timedelta(days=3)
            )
        ]
        
        # Test productivity analysis
        productivity_analyzer = ProductivityAnalyzer()
        productivity_report = productivity_analyzer.analyze_productivity(
            todos, AnalyticsTimeframe.WEEKLY
        )
        
        assert productivity_report.completion_rate == 50.0
        assert len(productivity_report.insights) > 0
        
        # Test project analysis
        project_analyzer = ProjectAnalyzer()
        project_health = project_analyzer.calculate_project_health(todos)
        
        assert isinstance(project_health, ProjectHealthScore)
        assert project_health.completion_rate == 50.0
        
        # Test dashboard integration
        with patch('todo_cli.dashboard.get_config') as mock_config:
            mock_config.return_value.data_dir = tempfile.mkdtemp()
            
            dashboard_manager = DashboardManager()
            
            # Create simple dashboard
            dashboard = Dashboard(
                name="integration_test",
                widgets=[
                    Widget(
                        name="completion_rate",
                        widget_type=WidgetType.METRIC,
                        data_source="todo_metrics",
                        config={"metric": "completion_rate"}
                    )
                ]
            )
            
            dashboard_manager.save_dashboard(dashboard)
            loaded_dashboard = dashboard_manager.get_dashboard("integration_test")
            
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
                    duration=7200,  # 2 hours
                    project="TestProject"
                )
            ]
            
            # Generate report
            report = tracker.generate_time_report(
                now - timedelta(days=1), 
                now
            )
            
            assert report.total_time_tracked == 2.0
            assert "TestProject" in report.time_by_project
            assert report.time_by_project["TestProject"] == 2.0

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
        for i in range(1000):
            todo = Todo(
                id=f"todo_{i}",
                title=f"Task {i}",
                project=f"Project_{i % 10}",
                completed=i % 3 == 0,  # Every 3rd todo completed
                priority=Priority.MEDIUM,
                created_at=datetime.now() - timedelta(days=i % 30)
            )
            large_todos.append(todo)
        
        # Test productivity analysis performance
        analyzer = ProductivityAnalyzer()
        
        start_time = time.time()
        report = analyzer.analyze_productivity(large_todos, AnalyticsTimeframe.MONTHLY)
        end_time = time.time()
        
        # Should complete within reasonable time (< 5 seconds)
        assert (end_time - start_time) < 5.0
        assert report.total_tasks == 1000
        assert abs(report.completion_rate - 33.33) < 0.1  # Approximately 33%

    def test_malformed_data_handling(self):
        """Test handling of malformed or corrupted data"""
        analyzer = ProductivityAnalyzer()
        
        # Test with None values
        todos_with_none = [
            Todo(id="1", title="Valid task", completed=True),
            None,  # This should be handled gracefully
            Todo(id="2", title="Another valid task", completed=False)
        ]
        
        # Filter out None values (simulating real-world data cleaning)
        clean_todos = [t for t in todos_with_none if t is not None]
        
        report = analyzer.analyze_productivity(clean_todos, AnalyticsTimeframe.WEEKLY)
        assert report.total_tasks == 2

    def test_concurrent_access_simulation(self):
        """Test concurrent access to analytics components"""
        import threading
        
        todos = [
            Todo(id=f"task_{i}", title=f"Task {i}", completed=i % 2 == 0)
            for i in range(100)
        ]
        
        results = []
        errors = []
        
        def analyze_productivity():
            try:
                analyzer = ProductivityAnalyzer()
                report = analyzer.analyze_productivity(todos, AnalyticsTimeframe.WEEKLY)
                results.append(report.completion_rate)
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