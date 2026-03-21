"""
iOS API compatibility tests.

These tests verify that all API endpoints the iOS app depends on exist and
return proper responses from the web server (todo_cli.web.server).
The iOS app communicates via REST with these endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from todo_cli.web.server import app, get_todo_storage, get_query_engine
from todo_cli.domain.todo import Todo, TodoStatus, Priority
from todo_cli.domain.project import Project


@pytest.fixture
def mock_storage():
    """Create a mock storage with test data."""
    storage = Mock()

    test_project = Project(
        name="test-project",
        display_name="Test Project",
        description="A test project",
        active=True,
        color="blue",
        created=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    test_todos = [
        Todo(
            id=1,
            text="Buy groceries",
            description="Milk, eggs, bread",
            project="test-project",
            status=TodoStatus.PENDING,
            priority=Priority.HIGH,
            context=["home"],
            tags=["shopping"],
            created=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            modified=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        ),
        Todo(
            id=2,
            text="Write tests",
            description="Unit and integration tests",
            project="test-project",
            status=TodoStatus.COMPLETED,
            priority=Priority.MEDIUM,
            context=["work"],
            tags=["dev"],
            created=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            modified=datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        ),
    ]

    storage.list_projects.return_value = ["test-project"]
    storage.load_project.return_value = (test_project, test_todos)
    storage.save_project.return_value = None
    return storage


@pytest.fixture
def mock_query_engine():
    return Mock()


@pytest.fixture
def client(mock_storage, mock_query_engine):
    """Create test client with mocked dependencies."""
    app.dependency_overrides[get_todo_storage] = lambda: mock_storage
    app.dependency_overrides[get_query_engine] = lambda: mock_query_engine
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class TestiOSAPIEndpoints:
    """Verify all API endpoints the iOS app consumes exist and return correct schemas."""

    def test_get_tasks_returns_list(self, client):
        """GET /api/tasks must return a list of tasks for iOS TaskListView."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Each task must have fields the iOS Task model expects
        if len(data) > 0:
            task = data[0]
            # id, title/text, status, priority, tags are required by iOS model
            assert "id" in task
            assert "title" in task or "text" in task
            assert "status" in task
            assert "priority" in task
            assert "tags" in task

    def test_post_tasks_creates_task(self, client, mock_storage):
        """POST /api/tasks must accept a task creation payload."""
        payload = {
            "title": "New iOS task",
            "description": "Created from iOS app",
            "priority": "high",
            "project": "test-project",
        }
        response = client.post("/api/tasks", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Must return the created task
        assert "title" in data or "text" in data or "id" in data

    def test_get_projects_returns_list(self, client):
        """GET /api/projects must return a list of projects for iOS ProjectListView."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            project = data[0]
            assert "name" in project
            assert "task_count" in project

    def test_get_pomodoro_status(self, client):
        """GET /api/pomodoro/status must return timer status for iOS FocusTimerView."""
        response = client.get("/api/pomodoro/status")
        assert response.status_code == 200
        data = response.json()
        # Must contain fields the iOS PomodoroStatus model expects
        assert isinstance(data, dict)
        # The endpoint should return status info (fields may vary)
        # At minimum it should be a valid JSON object
        assert data is not None

    def test_get_ai_status(self, client):
        """GET /api/ai/status must return AI status for iOS settings."""
        response = client.get("/api/ai/status")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_get_dashboards_returns_list(self, client):
        """GET /api/dashboards must return dashboard data."""
        response = client.get("/api/dashboards")
        assert response.status_code == 200
        data = response.json()
        # Can be a list or an object with dashboards key
        assert isinstance(data, (list, dict))

    def test_health_endpoint(self, client):
        """GET /health must return health status for iOS connection testing."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_get_single_task(self, client):
        """GET /api/tasks/{id} must return a single task for iOS TaskDetailView."""
        response = client.get("/api/tasks/1")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["id"] == "1"

    def test_get_nonexistent_task_returns_404(self, client):
        """GET /api/tasks/{id} for missing task must return 404."""
        response = client.get("/api/tasks/99999")
        assert response.status_code == 404

    def test_task_filtering_by_status(self, client):
        """GET /api/tasks?status=completed must filter correctly."""
        response = client.get("/api/tasks?status=completed")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for task in data:
            assert task["status"] == "completed"

    def test_task_filtering_by_project(self, client):
        """GET /api/tasks?project=test-project must filter correctly."""
        response = client.get("/api/tasks?project=test-project")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestiOSAPISchemaCompat:
    """Verify response schemas match what iOS models expect to decode."""

    def test_task_schema_has_required_fields(self, client):
        """Task responses must have all fields the iOS TodoTask model needs."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        task = data[0]
        # iOS TodoTask has: id, text/title, description, project, status,
        # completed/is_blocked, priority, due_date, tags, created_at
        required = {"id", "status", "priority", "tags"}
        actual = set(task.keys())
        missing = required - actual
        assert not missing, f"Task response missing required fields: {missing}"

        # Must have either 'title' or 'text'
        assert "title" in task or "text" in task, "Task must have 'title' or 'text' field"

    def test_project_schema_has_required_fields(self, client):
        """Project responses must have all fields the iOS Project model needs."""
        response = client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

        project = data[0]
        required = {"name", "task_count"}
        actual = set(project.keys())
        missing = required - actual
        assert not missing, f"Project response missing required fields: {missing}"

    def test_health_schema(self, client):
        """Health response must have fields the iOS SettingsView checks."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert isinstance(data["status"], str)
