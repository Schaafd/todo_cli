"""Tests for the dashboard system: renderer, manager, templates, config."""

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from rich.console import Console
from rich.panel import Panel

from todo_cli.config import ConfigModel, Config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """Point all config/data to a tmp directory so tests are isolated."""
    data_dir = str(tmp_path / "todo_data")
    backup_dir = str(tmp_path / "todo_data" / "backups")
    monkeypatch.setenv("HOME", str(tmp_path))
    # Reset Config singleton between tests
    Config._instance = None

    config = ConfigModel(data_dir=data_dir, backup_dir=backup_dir)
    Config._instance = config
    yield config
    Config._instance = None


@pytest.fixture
def manager():
    from todo_cli.services.dashboard import DashboardManager
    return DashboardManager()


@pytest.fixture
def sample_todo():
    """Return a minimal Todo-like object for data source testing."""
    from todo_cli.domain import Todo, Priority, TodoStatus
    todo = Todo(id=1, text="Test task", project="inbox")
    todo.priority = Priority.MEDIUM
    todo.status = TodoStatus.PENDING
    return todo


# ---------------------------------------------------------------------------
# DashboardManager CRUD
# ---------------------------------------------------------------------------

class TestDashboardManager:
    def test_create_dashboard(self, manager):
        dashboard = manager.create_dashboard("My Board", "A test board")
        assert dashboard.name == "My Board"
        assert dashboard.description == "A test board"
        assert dashboard.id

    def test_list_dashboards(self, manager):
        manager.create_dashboard("Board1")
        manager.create_dashboard("Board2")
        dashboards = manager.list_dashboards()
        names = {d["name"] for d in dashboards}
        assert "Board1" in names
        assert "Board2" in names

    def test_load_dashboard(self, manager):
        created = manager.create_dashboard("Loadable")
        loaded = manager.load_dashboard(created.id)
        assert loaded is not None
        assert loaded.name == "Loadable"

    def test_delete_dashboard(self, manager):
        created = manager.create_dashboard("ToDelete")
        assert manager.delete_dashboard(created.id) is True
        assert manager.load_dashboard(created.id) is None

    def test_delete_nonexistent(self, manager):
        assert manager.delete_dashboard("nonexistent-id") is False

    def test_save_and_reload(self, manager):
        dashboard = manager.create_dashboard("Persist")
        from todo_cli.services.dashboard import WidgetType, WidgetSize
        widget = manager.create_widget(WidgetType.METRIC, "W1", "todo_metrics", WidgetSize.SMALL, metric_type="total_tasks")
        dashboard.add_widget(widget)
        manager.save_dashboard(dashboard)

        reloaded = manager.load_dashboard(dashboard.id)
        assert reloaded is not None
        assert len(reloaded.widgets) == 1
        assert reloaded.widgets[0].title == "W1"


# ---------------------------------------------------------------------------
# Widget add / remove
# ---------------------------------------------------------------------------

class TestWidgetManagement:
    def test_add_widget(self, manager):
        from todo_cli.services.dashboard import WidgetType, WidgetSize
        dashboard = manager.create_dashboard("Widgets")
        widget = manager.create_widget(WidgetType.GAUGE, "G1", "todo_metrics", WidgetSize.MEDIUM)
        dashboard.add_widget(widget)
        assert len(dashboard.widgets) == 1

    def test_remove_widget(self, manager):
        from todo_cli.services.dashboard import WidgetType, WidgetSize
        dashboard = manager.create_dashboard("Widgets")
        widget = manager.create_widget(WidgetType.GAUGE, "G1", "todo_metrics", WidgetSize.MEDIUM)
        dashboard.add_widget(widget)
        assert dashboard.remove_widget(widget.id) is True
        assert len(dashboard.widgets) == 0

    def test_remove_nonexistent_widget(self, manager):
        dashboard = manager.create_dashboard("Widgets")
        assert dashboard.remove_widget("no-such-id") is False

    def test_get_widget(self, manager):
        from todo_cli.services.dashboard import WidgetType, WidgetSize
        dashboard = manager.create_dashboard("Widgets")
        widget = manager.create_widget(WidgetType.TEXT, "T1", "todo_metrics", WidgetSize.SMALL)
        dashboard.add_widget(widget)
        found = dashboard.get_widget(widget.id)
        assert found is not None
        assert found.title == "T1"


# ---------------------------------------------------------------------------
# Template creation
# ---------------------------------------------------------------------------

class TestTemplates:
    @pytest.mark.parametrize("template_name,expected_widgets", [
        ("productivity_overview", 4),
        ("project_dashboard", 3),
        ("time_tracking", 4),
        ("minimal", 3),
    ])
    def test_template_creation(self, manager, template_name, expected_widgets):
        dashboard = manager.create_template_dashboard(template_name)
        assert dashboard is not None
        assert len(dashboard.widgets) == expected_widgets

    def test_minimal_template_widgets(self, manager):
        dashboard = manager.create_template_dashboard("minimal")
        titles = {w.title for w in dashboard.widgets}
        assert "Total Tasks" in titles
        assert "Overdue Tasks" in titles
        assert "Completion Rate" in titles

    def test_unknown_template_returns_empty(self, manager):
        dashboard = manager.create_template_dashboard("nonexistent")
        assert dashboard is not None
        assert len(dashboard.widgets) == 0


# ---------------------------------------------------------------------------
# DashboardRenderer – each widget type renders without error
# ---------------------------------------------------------------------------

class TestDashboardRenderer:
    @pytest.fixture
    def renderer(self):
        from todo_cli.services.dashboard_renderer import DashboardRenderer
        console = Console(file=open(os.devnull, "w"), force_terminal=True)
        return DashboardRenderer(console)

    @pytest.fixture
    def widget_renderer(self):
        from todo_cli.services.dashboard_renderer import WidgetRenderer
        console = Console(file=open(os.devnull, "w"), force_terminal=True)
        return WidgetRenderer(console)

    def _make_widget(self, wtype_str, data_kwargs=None):
        from todo_cli.services.dashboard import Widget, WidgetType, WidgetSize, WidgetData
        wtype = WidgetType(wtype_str)
        widget = Widget(
            id="test-w",
            title=f"Test {wtype_str}",
            widget_type=wtype,
            size=WidgetSize.MEDIUM,
            data_source="todo_metrics",
        )
        widget.cached_data = WidgetData(**(data_kwargs or {"value": 42, "label": "Test"}))
        return widget

    @pytest.mark.parametrize("wtype,extra", [
        ("metric", {"value": 42, "label": "Tasks", "unit": "", "trend": 5.2, "icon": "T", "color": "cyan"}),
        ("gauge", {"value": 75, "label": "Score", "unit": "/100"}),
        ("sparkline", {"value": 0, "label": "Trend", "series": [{"data": [1, 3, 2, 5, 4]}]}),
        ("chart_bar", {"value": 0, "label": "Bar", "series": [{"data": [10, 20, 30]}], "categories": ["A", "B", "C"]}),
        ("chart_pie", {"value": 0, "label": "Pie", "series": [{"data": [40, 30, 30]}], "categories": ["X", "Y", "Z"]}),
        ("table", {"value": 0, "label": "Tbl", "headers": ["Name", "Val"], "rows": [["a", "1"], ["b", "2"]]}),
        ("list", {"value": 0, "label": "Lst", "categories": ["Item1", "Item2"]}),
        ("text", {"value": "Hello world", "label": "Info"}),
        ("progress_bar", {"value": 60, "label": "Progress", "unit": "/100"}),
    ])
    def test_render_widget_type(self, widget_renderer, wtype, extra):
        widget = self._make_widget(wtype, extra)
        panel = widget_renderer.render_widget(widget)
        assert isinstance(panel, Panel)

    def test_render_full_dashboard(self, renderer, manager):
        dashboard = manager.create_template_dashboard("minimal")
        # Give widgets some cached data
        from todo_cli.services.dashboard import WidgetData
        for w in dashboard.widgets:
            w.cached_data = WidgetData(value=10, label=w.title)
        # Should not raise
        renderer.render(dashboard)

    def test_render_empty_dashboard(self, renderer, manager):
        dashboard = manager.create_dashboard("Empty")
        renderer.render(dashboard)

    def test_render_dashboard_list(self, renderer, manager):
        manager.create_dashboard("A")
        manager.create_dashboard("B")
        dashboards = manager.list_dashboards()
        renderer.render_dashboard_list(dashboards)

    def test_render_dashboard_list_empty(self, renderer):
        renderer.render_dashboard_list([])


# ---------------------------------------------------------------------------
# Config serialization with new dashboard fields
# ---------------------------------------------------------------------------

class TestConfigDashboardFields:
    def test_defaults(self):
        config = ConfigModel()
        assert config.dashboard_default == "default"
        assert config.dashboard_auto_refresh is False
        assert config.dashboard_refresh_interval == 300

    def test_to_yaml_includes_dashboard_fields(self):
        config = ConfigModel()
        yaml_str = config.to_yaml()
        assert "dashboard_default" in yaml_str
        assert "dashboard_auto_refresh" in yaml_str
        assert "dashboard_refresh_interval" in yaml_str

    def test_roundtrip(self):
        config = ConfigModel(
            dashboard_default="my_dash",
            dashboard_auto_refresh=True,
            dashboard_refresh_interval=60,
        )
        yaml_str = config.to_yaml()
        restored = ConfigModel.from_yaml(yaml_str)
        assert restored.dashboard_default == "my_dash"
        assert restored.dashboard_auto_refresh is True
        assert restored.dashboard_refresh_interval == 60


# ---------------------------------------------------------------------------
# Dashboard export / import
# ---------------------------------------------------------------------------

class TestDashboardExportImport:
    def test_export_json(self, manager):
        dashboard = manager.create_dashboard("Exportable", "desc")
        exported = manager.export_dashboard(dashboard.id)
        assert exported is not None
        data = json.loads(exported)
        assert data["name"] == "Exportable"

    def test_import_json(self, manager):
        dashboard = manager.create_dashboard("Original")
        exported = manager.export_dashboard(dashboard.id)
        imported = manager.import_dashboard(exported)
        assert imported is not None
        assert imported.name == "Original"
        # Should have a new ID
        assert imported.id != dashboard.id

    def test_export_nonexistent(self, manager):
        assert manager.export_dashboard("no-id") is None
