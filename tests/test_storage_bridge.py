"""
Unit tests for storage bridge module
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from src.todo_cli.webapp.storage_bridge import (
    StorageBridge,
    UserPermissions,
    get_storage_bridge,
    reset_storage_bridge,
)
from src.todo_cli.webapp.database import DatabaseManager, User
from src.todo_cli.domain import Todo, TodoStatus, Priority, Project
from src.todo_cli.config import ConfigModel


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""
    with tempfile.TemporaryDirectory() as data_dir:
        with tempfile.TemporaryDirectory() as backup_dir:
            with tempfile.TemporaryDirectory() as db_dir:
                yield {
                    'data': Path(data_dir),
                    'backup': Path(backup_dir),
                    'db': Path(db_dir)
                }


@pytest.fixture
def test_config(temp_dirs):
    """Create test configuration"""
    return ConfigModel(
        data_dir=str(temp_dirs['data']),
        backup_dir=str(temp_dirs['backup']),
        default_project="inbox"
    )


@pytest.fixture
def test_db(temp_dirs):
    """Create test database"""
    db_path = temp_dirs['db'] / "test.db"
    return DatabaseManager(db_path)


@pytest.fixture
def test_user(test_db):
    """Create test user"""
    return test_db.create_user(
        username="testuser",
        email="test@example.com",
        password="password123"
    )


@pytest.fixture
def test_user2(test_db):
    """Create second test user"""
    return test_db.create_user(
        username="testuser2",
        email="test2@example.com",
        password="password123"
    )


@pytest.fixture
def storage_bridge(test_db, test_config):
    """Create storage bridge for testing"""
    bridge = StorageBridge(db=test_db, config=test_config)
    yield bridge
    # Cleanup
    reset_storage_bridge()


class TestUserPermissions:
    """Test user permissions management"""
    
    def test_grant_project_access(self, test_db, test_user):
        """Test granting project access"""
        perms = UserPermissions(test_db)
        
        perms.grant_project_access(test_user.id, "work", ["read", "write"])
        
        assert perms.has_permission(test_user.id, "work", "read")
        assert perms.has_permission(test_user.id, "work", "write")
        assert not perms.has_permission(test_user.id, "work", "delete")
    
    def test_grant_default_permissions(self, test_db, test_user):
        """Test default permissions are read and write"""
        perms = UserPermissions(test_db)
        
        perms.grant_project_access(test_user.id, "work")
        
        permissions = perms.get_project_permissions(test_user.id, "work")
        assert "read" in permissions
        assert "write" in permissions
    
    def test_revoke_project_access(self, test_db, test_user):
        """Test revoking project access"""
        perms = UserPermissions(test_db)
        
        perms.grant_project_access(test_user.id, "work", ["read", "write"])
        perms.revoke_project_access(test_user.id, "work")
        
        assert not perms.has_permission(test_user.id, "work", "read")
    
    def test_get_user_projects(self, test_db, test_user):
        """Test getting user projects"""
        perms = UserPermissions(test_db)
        
        perms.grant_project_access(test_user.id, "work")
        perms.grant_project_access(test_user.id, "personal")
        perms.grant_project_access(test_user.id, "hobby")
        
        projects = perms.get_user_projects(test_user.id)
        assert len(projects) == 3
        assert "work" in projects
        assert "personal" in projects
        assert "hobby" in projects
    
    def test_permission_isolation(self, test_db, test_user, test_user2):
        """Test that permissions are isolated between users"""
        perms = UserPermissions(test_db)
        
        perms.grant_project_access(test_user.id, "work", ["read", "write"])
        
        assert perms.has_permission(test_user.id, "work", "read")
        assert not perms.has_permission(test_user2.id, "work", "read")


class TestStorageBridgeProjects:
    """Test storage bridge project operations"""
    
    def test_create_project_for_user(self, storage_bridge, test_user):
        """Test creating a project for a user"""
        project = storage_bridge.create_project_for_user(
            test_user.id,
            "myproject",
            description="Test project",
            color="#FF0000"
        )
        
        assert project.name == "myproject"
        assert project.description == "Test project"
        assert project.color == "#FF0000"
        
        # Check permissions were granted
        assert storage_bridge.permissions.has_permission(
            test_user.id, "myproject", "read"
        )
        assert storage_bridge.permissions.has_permission(
            test_user.id, "myproject", "write"
        )
        assert storage_bridge.permissions.has_permission(
            test_user.id, "myproject", "delete"
        )
    
    def test_get_user_projects(self, storage_bridge, test_user):
        """Test getting user projects"""
        # Create projects
        storage_bridge.create_project_for_user(test_user.id, "project1")
        storage_bridge.create_project_for_user(test_user.id, "project2")
        
        projects = storage_bridge.get_user_projects(test_user.id)
        
        assert len(projects) == 2
        project_names = [p.name for p in projects]
        assert "project1" in project_names
        assert "project2" in project_names
    
    def test_get_project_with_permission(self, storage_bridge, test_user):
        """Test getting a project with permission"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        project = storage_bridge.get_project(test_user.id, "work")
        
        assert project is not None
        assert project.name == "work"
    
    def test_get_project_without_permission(self, storage_bridge, test_user, test_user2):
        """Test getting a project without permission raises error"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        with pytest.raises(PermissionError):
            storage_bridge.get_project(test_user2.id, "work")
    
    def test_update_project(self, storage_bridge, test_user):
        """Test updating a project"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        success = storage_bridge.update_project(
            test_user.id,
            "work",
            description="Updated description",
            color="#00FF00"
        )
        
        assert success is True
        
        project = storage_bridge.get_project(test_user.id, "work")
        assert project.description == "Updated description"
        assert project.color == "#00FF00"
    
    def test_update_project_without_permission(self, storage_bridge, test_user, test_user2):
        """Test updating project without permission raises error"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        with pytest.raises(PermissionError):
            storage_bridge.update_project(test_user2.id, "work", description="Hack")
    
    def test_delete_project(self, storage_bridge, test_user):
        """Test deleting a project"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        success = storage_bridge.delete_project(test_user.id, "work")
        
        assert success is True
        
        # Permission should be revoked
        assert not storage_bridge.permissions.has_permission(
            test_user.id, "work", "read"
        )
    
    def test_delete_project_without_permission(self, storage_bridge, test_user, test_user2):
        """Test deleting project without permission raises error"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        with pytest.raises(PermissionError):
            storage_bridge.delete_project(test_user2.id, "work")


class TestStorageBridgeTasks:
    """Test storage bridge task operations"""
    
    def test_create_task(self, storage_bridge, test_user):
        """Test creating a task"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(
            test_user.id,
            "work",
            "Test task",
            priority=Priority.HIGH,
            tags=["urgent"]
        )
        
        assert task.text == "Test task"
        assert task.project == "work"
        assert task.priority == Priority.HIGH
        assert "urgent" in task.tags
    
    def test_create_task_without_permission(self, storage_bridge, test_user, test_user2):
        """Test creating task without permission raises error"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        with pytest.raises(PermissionError):
            storage_bridge.create_task(test_user2.id, "work", "Hack task")
    
    def test_get_user_tasks(self, storage_bridge, test_user):
        """Test getting user tasks"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task1 = storage_bridge.create_task(test_user.id, "work", "Task 1")
        task2 = storage_bridge.create_task(test_user.id, "work", "Task 2")
        
        tasks = storage_bridge.get_user_tasks(test_user.id)
        
        assert len(tasks) == 2
        task_ids = [t.id for t in tasks]
        assert task1.id in task_ids
        assert task2.id in task_ids
    
    def test_get_user_tasks_filtered_by_project(self, storage_bridge, test_user):
        """Test getting user tasks filtered by project"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        storage_bridge.create_project_for_user(test_user.id, "personal")
        
        task1 = storage_bridge.create_task(test_user.id, "work", "Work task")
        task2 = storage_bridge.create_task(test_user.id, "personal", "Personal task")
        
        work_tasks = storage_bridge.get_user_tasks(test_user.id, project_name="work")
        
        assert len(work_tasks) == 1
        assert work_tasks[0].id == task1.id
    
    def test_get_user_tasks_filtered_by_status(self, storage_bridge, test_user):
        """Test getting user tasks filtered by status"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task1 = storage_bridge.create_task(
            test_user.id, "work", "Task 1", status=TodoStatus.PENDING
        )
        task2 = storage_bridge.create_task(
            test_user.id, "work", "Task 2", status=TodoStatus.COMPLETED
        )
        
        pending_tasks = storage_bridge.get_user_tasks(
            test_user.id, status=TodoStatus.PENDING
        )
        
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == task1.id
    
    def test_get_user_tasks_filtered_by_priority(self, storage_bridge, test_user):
        """Test getting user tasks filtered by priority"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task1 = storage_bridge.create_task(
            test_user.id, "work", "Task 1", priority=Priority.HIGH
        )
        task2 = storage_bridge.create_task(
            test_user.id, "work", "Task 2", priority=Priority.LOW
        )
        
        high_priority_tasks = storage_bridge.get_user_tasks(
            test_user.id, priority=Priority.HIGH
        )
        
        assert len(high_priority_tasks) == 1
        assert high_priority_tasks[0].id == task1.id
    
    def test_get_user_tasks_with_limit(self, storage_bridge, test_user):
        """Test getting user tasks with limit"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        for i in range(5):
            storage_bridge.create_task(test_user.id, "work", f"Task {i}")
        
        tasks = storage_bridge.get_user_tasks(test_user.id, limit=3)
        
        assert len(tasks) == 3
    
    def test_get_task(self, storage_bridge, test_user):
        """Test getting a specific task"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        created_task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        retrieved_task = storage_bridge.get_task(test_user.id, created_task.id)
        
        assert retrieved_task is not None
        assert retrieved_task.id == created_task.id
        assert retrieved_task.text == "Test task"
    
    def test_get_task_without_permission(self, storage_bridge, test_user, test_user2):
        """Test getting task without permission returns None"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        retrieved_task = storage_bridge.get_task(test_user2.id, task.id)
        
        assert retrieved_task is None
    
    def test_update_task(self, storage_bridge, test_user):
        """Test updating a task"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Original text")
        
        updated_task = storage_bridge.update_task(
            test_user.id,
            task.id,
            text="Updated text",
            priority=Priority.CRITICAL
        )
        
        assert updated_task is not None
        assert updated_task.text == "Updated text"
        assert updated_task.priority == Priority.CRITICAL
    
    def test_update_task_without_permission(self, storage_bridge, test_user, test_user2):
        """Test updating task without permission returns None"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        # User 2 cannot see user 1's task, so update returns None
        result = storage_bridge.update_task(test_user2.id, task.id, text="Hacked")
        assert result is None
    
    def test_delete_task(self, storage_bridge, test_user):
        """Test deleting a task"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        success = storage_bridge.delete_task(test_user.id, task.id)
        
        assert success is True
        
        # Task should no longer exist
        retrieved_task = storage_bridge.get_task(test_user.id, task.id)
        assert retrieved_task is None
    
    def test_delete_task_without_permission(self, storage_bridge, test_user, test_user2):
        """Test deleting task without permission returns False"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        # User 2 cannot see user 1's task, so delete returns False
        result = storage_bridge.delete_task(test_user2.id, task.id)
        assert result is False
    
    def test_toggle_task_completion(self, storage_bridge, test_user):
        """Test toggling task completion"""
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        task = storage_bridge.create_task(test_user.id, "work", "Test task")
        
        # Toggle to completed
        updated_task = storage_bridge.toggle_task_completion(test_user.id, task.id)
        
        assert updated_task is not None
        assert updated_task.status == TodoStatus.COMPLETED
        assert updated_task.completed is True
        
        # Toggle back to pending
        updated_task = storage_bridge.toggle_task_completion(test_user.id, task.id)
        
        assert updated_task.status == TodoStatus.PENDING
        assert updated_task.completed is False


class TestMultiUserIsolation:
    """Test multi-user data isolation"""
    
    def test_users_cannot_see_each_others_projects(
        self, storage_bridge, test_user, test_user2
    ):
        """Test that users cannot see each other's projects"""
        storage_bridge.create_project_for_user(test_user.id, "user1_project")
        storage_bridge.create_project_for_user(test_user2.id, "user2_project")
        
        user1_projects = storage_bridge.get_user_projects(test_user.id)
        user2_projects = storage_bridge.get_user_projects(test_user2.id)
        
        assert len(user1_projects) == 1
        assert len(user2_projects) == 1
        assert user1_projects[0].name == "user1_project"
        assert user2_projects[0].name == "user2_project"
    
    def test_users_cannot_see_each_others_tasks(
        self, storage_bridge, test_user, test_user2
    ):
        """Test that users cannot see each other's tasks"""
        # Use unique project names to avoid conflicts in markdown storage
        storage_bridge.create_project_for_user(test_user.id, "user1_work")
        storage_bridge.create_project_for_user(test_user2.id, "user2_work")
        
        task1 = storage_bridge.create_task(test_user.id, "user1_work", "User 1 task")
        task2 = storage_bridge.create_task(test_user2.id, "user2_work", "User 2 task")
        
        user1_tasks = storage_bridge.get_user_tasks(test_user.id)
        user2_tasks = storage_bridge.get_user_tasks(test_user2.id)
        
        assert len(user1_tasks) == 1
        assert len(user2_tasks) == 1
        assert user1_tasks[0].id == task1.id
        assert user2_tasks[0].id == task2.id


class TestConcurrentAccess:
    """Test concurrent access safety"""
    
    def test_concurrent_project_creation(self, storage_bridge, test_user):
        """Test that concurrent project creation is thread-safe"""
        import threading
        
        results = []
        
        def create_project(name):
            try:
                project = storage_bridge.create_project_for_user(
                    test_user.id, name
                )
                results.append(project)
            except Exception as e:
                results.append(e)
        
        threads = [
            threading.Thread(target=create_project, args=(f"project{i}",))
            for i in range(5)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All projects should be created successfully
        assert len(results) == 5
        assert all(isinstance(r, Project) for r in results)
    
    def test_concurrent_task_creation(self, storage_bridge, test_user):
        """Test that concurrent task creation is thread-safe"""
        import threading
        
        storage_bridge.create_project_for_user(test_user.id, "work")
        
        results = []
        
        def create_task(text):
            try:
                task = storage_bridge.create_task(test_user.id, "work", text)
                results.append(task)
            except Exception as e:
                results.append(e)
        
        threads = [
            threading.Thread(target=create_task, args=(f"Task {i}",))
            for i in range(10)
        ]
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All tasks should be created successfully
        assert len(results) == 10
        assert all(isinstance(r, Todo) for r in results)
        
        # All task IDs should be unique
        task_ids = [r.id for r in results if isinstance(r, Todo)]
        assert len(task_ids) == len(set(task_ids))
