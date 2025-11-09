"""
Integration tests for web API
"""

import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from src.todo_cli.webapp.app import app
from src.todo_cli.webapp.database import DatabaseManager, reset_db
from src.todo_cli.webapp.storage_bridge import reset_storage_bridge
from src.todo_cli.config import ConfigModel


@pytest.fixture
def temp_dirs():
    """Create temporary directories"""
    with tempfile.TemporaryDirectory() as data_dir:
        with tempfile.TemporaryDirectory() as backup_dir:
            with tempfile.TemporaryDirectory() as db_dir:
                yield {
                    'data': Path(data_dir),
                    'backup': Path(backup_dir),
                    'db': Path(db_dir)
                }


@pytest.fixture
def test_db(temp_dirs):
    """Create test database"""
    db_path = temp_dirs['db'] / "test.db"
    db = DatabaseManager(db_path)
    
    # Set global instance
    import src.todo_cli.webapp.database as db_module
    db_module._db_manager = db
    
    yield db
    
    # Cleanup
    reset_db()


@pytest.fixture
def test_config(temp_dirs):
    """Create test configuration"""
    config = ConfigModel(
        data_dir=str(temp_dirs['data']),
        backup_dir=str(temp_dirs['backup']),
        default_project="inbox"
    )
    
    # Set global config
    import src.todo_cli.config as config_module
    config_module._config = config
    
    yield config
    
    # Cleanup
    config_module._config = None
    reset_storage_bridge()


@pytest.fixture
def client(test_db, test_config):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_user(test_db):
    """Create test user"""
    return test_db.create_user(
        username="testuser",
        email="test@example.com",
        password="password123"
    )


@pytest.fixture
def auth_client(client, test_user):
    """Create authenticated test client"""
    # Login to get token
    response = client.post(
        "/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
        follow_redirects=False
    )
    
    # Extract cookie
    cookies = response.cookies
    
    # Create new client with cookies
    authenticated_client = TestClient(app)
    authenticated_client.cookies = cookies
    
    return authenticated_client


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_login_success(self, client, test_user):
        """Test successful login"""
        response = client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "password123",
            },
            follow_redirects=False
        )
        
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"
        assert "access_token" in response.cookies
    
    def test_login_failure(self, client, test_user):
        """Test failed login"""
        response = client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "wrongpassword",
            }
        )
        
        assert response.status_code == 401
    
    def test_register_success(self, client):
        """Test successful registration"""
        response = client.post(
            "/register",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
                "password_confirm": "password123",
            },
            follow_redirects=False
        )
        
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"
    
    def test_register_password_mismatch(self, client):
        """Test registration with mismatched passwords"""
        response = client.post(
            "/register",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password": "password123",
                "password_confirm": "different",
            }
        )
        
        assert response.status_code == 400
    
    def test_register_duplicate_username(self, client, test_user):
        """Test registration with duplicate username"""
        response = client.post(
            "/register",
            data={
                "username": "testuser",
                "email": "new@example.com",
                "password": "password123",
                "password_confirm": "password123",
            }
        )
        
        assert response.status_code == 400


class TestTaskAPI:
    """Test task API endpoints"""
    
    def test_get_tasks_empty(self, auth_client):
        """Test getting tasks when none exist"""
        response = auth_client.get("/api/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert len(data["tasks"]) == 0
    
    def test_create_task(self, auth_client, test_user, test_config):
        """Test creating a task"""
        # First create a project
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        
        response = auth_client.post(
            "/api/tasks",
            json={
                "title": "Test task",
                "description": "Test description",
                "priority": "high",
                "project_id": "work",
                "tags": ["test"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data
        assert "task" in data
    
    def test_get_created_task(self, auth_client, test_user, test_config):
        """Test getting a created task"""
        # Create project and task
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        
        # Create via API
        create_response = auth_client.post(
            "/api/tasks",
            json={
                "title": "Test task",
                "project_id": "work",
            }
        )
        task_id = create_response.json()["task_id"]
        
        # Get via API
        response = auth_client.get(f"/api/tasks/{task_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "task" in data
        assert data["task"]["id"] == task_id
        assert data["task"]["text"] == "Test task"
    
    def test_update_task(self, auth_client, test_user, test_config):
        """Test updating a task"""
        # Create project and task
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        task = bridge.create_task(test_user.id, "work", "Original text")
        
        # Update via API
        response = auth_client.put(
            f"/api/tasks/{task.id}",
            json={
                "title": "Updated text",
                "priority": "critical"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify update
        updated_task = bridge.get_task(test_user.id, task.id)
        assert updated_task.text == "Updated text"
    
    def test_toggle_task(self, auth_client, test_user, test_config):
        """Test toggling task completion"""
        # Create project and task
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        task = bridge.create_task(test_user.id, "work", "Test task")
        
        # Toggle via API
        response = auth_client.post(f"/api/tasks/{task.id}/toggle")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["completed"] is True
        
        # Toggle back
        response = auth_client.post(f"/api/tasks/{task.id}/toggle")
        data = response.json()
        assert data["completed"] is False
    
    def test_delete_task(self, auth_client, test_user, test_config):
        """Test deleting a task"""
        # Create project and task
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        task = bridge.create_task(test_user.id, "work", "Test task")
        
        # Delete via API
        response = auth_client.delete(f"/api/tasks/{task.id}")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify deletion
        deleted_task = bridge.get_task(test_user.id, task.id)
        assert deleted_task is None
    
    def test_filter_tasks_by_project(self, auth_client, test_user, test_config):
        """Test filtering tasks by project"""
        # Create projects and tasks
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        bridge.create_project_for_user(test_user.id, "personal")
        
        bridge.create_task(test_user.id, "work", "Work task")
        bridge.create_task(test_user.id, "personal", "Personal task")
        
        # Filter by work project
        response = auth_client.get("/api/tasks?project=work")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["project"] == "work"


class TestProjectAPI:
    """Test project API endpoints"""
    
    def test_get_projects_empty(self, auth_client):
        """Test getting projects when none exist"""
        response = auth_client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert len(data["projects"]) == 0
    
    def test_create_project(self, auth_client):
        """Test creating a project"""
        response = auth_client.post(
            "/api/projects",
            json={
                "name": "myproject",
                "description": "Test project",
                "color": "#FF0000"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["project_id"] == "myproject"
    
    def test_get_created_projects(self, auth_client, test_user, test_config):
        """Test getting created projects"""
        # Create projects
        from src.todo_cli.webapp.storage_bridge import get_storage_bridge
        bridge = get_storage_bridge()
        bridge.create_project_for_user(test_user.id, "work")
        bridge.create_project_for_user(test_user.id, "personal")
        
        # Get via API
        response = auth_client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 2
        project_names = [p["id"] for p in data["projects"]]
        assert "work" in project_names
        assert "personal" in project_names


class TestDashboard:
    """Test dashboard page"""
    
    def test_dashboard_requires_auth(self, client):
        """Test dashboard requires authentication"""
        response = client.get("/dashboard", follow_redirects=False)
        
        # Should redirect or return 401
        assert response.status_code in [302, 401]
    
    def test_dashboard_authenticated(self, auth_client):
        """Test dashboard with authentication"""
        response = auth_client.get("/dashboard")
        
        assert response.status_code == 200
