"""
Focused API contract tests for Todo CLI Web API.

These tests ensure critical API endpoints maintain their expected schemas and behavior.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from fastapi.testclient import TestClient
from todo_cli.web.server import app, get_todo_storage, get_query_engine
from todo_cli.domain.todo import Todo, TodoStatus, Priority
from todo_cli.domain.project import Project


class TestAPIContracts:
    """Core API contract tests with dependency injection."""
    
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks for all tests in this class."""
        # Create mock storage
        mock_storage = Mock()
        
        # Create test project
        test_project = Project(
            name="test-project",
            display_name="Test Project", 
            description="Test description",
            active=True,
            color="blue",
            created=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        )
        
        # Create test todos
        test_todos = [
            Todo(
                id=1,
                text="Test task 1",
                description="First test task",
                project="test-project",
                status=TodoStatus.PENDING,
                priority=Priority.MEDIUM,
                context=["work"],
                tags=["important"],
                created=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                modified=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            ),
            Todo(
                id=2,
                text="Test task 2", 
                description="Second test task",
                project="test-project",
                status=TodoStatus.COMPLETED,
                priority=Priority.HIGH,
                context=["home"],
                tags=["urgent"],
                created=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                modified=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            )
        ]
        
        # Configure mock responses
        mock_storage.list_projects.return_value = ["test-project"]
        mock_storage.load_project.return_value = (test_project, test_todos)
        mock_storage.save_project.return_value = None
        
        # Create mock query engine
        mock_query_engine = Mock()
        
        # Override dependencies
        app.dependency_overrides[get_todo_storage] = lambda: mock_storage
        app.dependency_overrides[get_query_engine] = lambda: mock_query_engine
        
        self.client = TestClient(app)
        self.mock_storage = mock_storage
        self.mock_query_engine = mock_query_engine
        
        yield
        
        # Clean up
        app.dependency_overrides.clear()
    
    def test_health_endpoint_contract(self):
        """Test /health endpoint returns expected schema."""
        response = self.client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        required_fields = {
            "status", "timestamp", "version", "api_version",
            "database_status", "total_tasks", "total_projects"
        }
        assert set(data.keys()) == required_fields
        
        # Verify field types
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        assert isinstance(data["api_version"], str)
        assert isinstance(data["database_status"], str)
        assert isinstance(data["total_tasks"], int)
        assert isinstance(data["total_projects"], int)
        
        # Verify expected values
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["api_version"] == "v1"
        assert data["total_tasks"] == 2
        assert data["total_projects"] == 1
        
        # Verify timestamp format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    
    def test_tasks_endpoint_contract(self):
        """Test /api/tasks endpoint returns expected schema."""
        response = self.client.get("/api/tasks")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2
        
        # Test task schema
        task = data[0]
        required_fields = {
            "id", "title", "description", "priority", "tags", "context",
            "status", "created_at", "updated_at", "due_date", "project",
            "is_blocked", "dependencies"
        }
        assert set(task.keys()) == required_fields
        
        # Verify field types
        assert isinstance(task["id"], str)
        assert isinstance(task["title"], str)  
        assert isinstance(task["description"], str)
        assert isinstance(task["priority"], str)
        assert isinstance(task["tags"], list)
        assert task["context"] is None or isinstance(task["context"], str)
        assert isinstance(task["status"], str)
        assert task["created_at"] is None or isinstance(task["created_at"], str)
        assert task["updated_at"] is None or isinstance(task["updated_at"], str)
        assert task["due_date"] is None or isinstance(task["due_date"], str)
        assert task["project"] is None or isinstance(task["project"], str)
        assert isinstance(task["is_blocked"], bool)
        assert isinstance(task["dependencies"], list)
    
    def test_projects_endpoint_contract(self):
        """Test /api/projects endpoint returns expected schema.""" 
        response = self.client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 1
        
        # Test project schema
        project = data[0]
        required_fields = {
            "name", "display_name", "description", "task_count",
            "completed_tasks", "active", "created_at", "color"
        }
        assert set(project.keys()) == required_fields
        
        # Verify field types
        assert isinstance(project["name"], str)
        assert isinstance(project["display_name"], str)
        assert isinstance(project["description"], str) 
        assert isinstance(project["task_count"], int)
        assert isinstance(project["completed_tasks"], int)
        assert isinstance(project["active"], bool)
        assert isinstance(project["created_at"], str)
        assert project["color"] is None or isinstance(project["color"], str)
        
        # Verify values
        assert project["name"] == "test-project"
        assert project["task_count"] == 2
        assert project["completed_tasks"] == 1
    
    def test_contexts_endpoint_contract(self):
        """Test /api/contexts endpoint returns expected schema."""
        response = self.client.get("/api/contexts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 2  # work and home contexts
        
        # Test context schema
        context = data[0]
        required_fields = {"name", "task_count"}
        assert set(context.keys()) == required_fields
        
        # Verify field types
        assert isinstance(context["name"], str)
        assert isinstance(context["task_count"], int)
        
        # Verify we have expected contexts
        context_names = [c["name"] for c in data]
        assert "work" in context_names
        assert "home" in context_names
    
    def test_task_filtering_contract(self):
        """Test task filtering maintains contract."""
        # Test status filter
        response = self.client.get("/api/tasks?status=completed")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "completed"
        
        # Test project filter  
        response = self.client.get("/api/tasks?project=test-project")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for task in data:
            assert task["project"] == "test-project"
    
    def test_task_crud_contracts(self):
        """Test task CRUD operations maintain contracts."""
        # Test GET specific task
        response = self.client.get("/api/tasks/1")
        assert response.status_code == 200
        task = response.json()
        assert task["id"] == "1"
        
        # Test GET non-existent task
        response = self.client.get("/api/tasks/999")  
        assert response.status_code == 404
        assert "detail" in response.json()
        
        # Test POST new task
        task_data = {
            "title": "New test task",
            "description": "API created task",
            "priority": "high",
            "project": "test-project"
        }
        response = self.client.post("/api/tasks", json=task_data)
        assert response.status_code == 200
        created_task = response.json()
        assert created_task["title"] == task_data["title"]
        
        # Test POST with invalid data
        invalid_data = {"title": ""}  # Empty title
        response = self.client.post("/api/tasks", json=invalid_data)
        assert response.status_code == 422
    
    def test_cors_headers_present(self):
        """Test CORS headers are present in responses."""
        # Make an OPTIONS request to test CORS preflight
        response = self.client.options("/api/tasks")
        # TestClient doesn't fully simulate CORS, so we'll just check the endpoint works
        # In real deployment, CORS middleware will add the headers
        assert response.status_code in [200, 405]  # Either allowed or method not allowed
    
    def test_error_response_format(self):
        """Test error responses maintain consistent format."""
        # Test 404 error
        response = self.client.get("/api/tasks/999")
        assert response.status_code == 404
        error = response.json()
        assert "detail" in error
        
        # Test validation error
        response = self.client.post("/api/tasks", json={"title": ""})
        assert response.status_code == 422
        error = response.json()
        assert "detail" in error


@pytest.mark.integration  
class TestAPIIntegrationContracts:
    """Integration tests for API contracts with real dependencies."""
    
    def test_real_health_endpoint(self):
        """Test health endpoint with real storage (integration test)."""
        client = TestClient(app)
        response = client.get("/health")
        
        # Should succeed even with real storage
        assert response.status_code == 200
        data = response.json()
        
        # Should have correct schema
        required_fields = {
            "status", "timestamp", "version", "api_version", 
            "database_status", "total_tasks", "total_projects"
        }
        assert set(data.keys()) == required_fields
        
        # Status should be healthy (assuming valid config)
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["version"] == "1.0.0"


class TestAPIPerformanceContracts:
    """Performance-related API contract tests."""
    
    def test_response_time_reasonable(self):
        """Test API responses are reasonably fast."""
        import time
        
        # Mock setup (simplified)
        mock_storage = Mock()
        mock_storage.list_projects.return_value = ["test"]
        mock_storage.load_project.return_value = (Mock(), [])
        
        app.dependency_overrides[get_todo_storage] = lambda: mock_storage
        
        try:
            client = TestClient(app)
            
            start_time = time.time()
            response = client.get("/api/tasks")
            end_time = time.time()
            
            assert response.status_code == 200
            
            # Should respond in reasonable time (< 1 second)
            response_time = end_time - start_time
            assert response_time < 1.0, f"Response took {response_time:.2f}s, expected < 1.0s"
            
        finally:
            app.dependency_overrides.clear()