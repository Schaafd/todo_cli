"""
Test for global unique ID generation across all projects.

This test ensures that todo IDs are unique globally across all projects,
preventing duplicate IDs that could cause issues in the system.
"""

import pytest
from unittest.mock import Mock

from src.todo_cli.storage import Storage
from src.todo_cli.domain import Todo
from src.todo_cli.config import ConfigModel


@pytest.fixture
def storage_with_existing_todos(tmp_path):
    """Create a storage instance with some existing todos across multiple projects."""
    config = ConfigModel(data_dir=str(tmp_path))
    storage = Storage(config)
    
    # Create todos in different projects with known IDs
    projects_and_todos = [
        ("inbox", [
            Todo(id=1, text="Inbox task 1"),
            Todo(id=5, text="Inbox task 5"),
            Todo(id=10, text="Inbox task 10"),
        ]),
        ("work", [
            Todo(id=3, text="Work task 3"),
            Todo(id=7, text="Work task 7"),
        ]),
        ("personal", [
            Todo(id=2, text="Personal task 2"),
            Todo(id=8, text="Personal task 8"),
        ]),
    ]
    
    for project_name, todos in projects_and_todos:
        # Create a basic project
        from src.todo_cli.domain import Project
        project = Project(name=project_name)
        
        # Save the project with todos
        storage.save_project(project, todos)
    
    return storage


class TestGlobalUniqueIds:
    """Test suite for global unique ID generation."""
    
    def test_get_next_todo_id_returns_global_max_plus_one(self, storage_with_existing_todos):
        """Test that get_next_todo_id returns the global maximum ID + 1."""
        storage = storage_with_existing_todos
        
        # Current max ID across all projects should be 10
        next_id = storage.get_next_todo_id()
        assert next_id == 11
        
        # Test with project parameter (should be same as global)
        next_id_with_project = storage.get_next_todo_id("inbox")
        assert next_id_with_project == 11
    
    def test_add_todo_without_id_gets_unique_global_id(self, storage_with_existing_todos):
        """Test that adding a todo without ID gets a unique global ID."""
        storage = storage_with_existing_todos
        
        # Add todo to inbox without specifying ID
        new_todo_inbox = Todo(id=0, text="New inbox task", project="inbox")
        assigned_id_inbox = storage.add_todo(new_todo_inbox)
        assert assigned_id_inbox == 11
        
        # Add todo to work without specifying ID
        new_todo_work = Todo(id=0, text="New work task", project="work")
        assigned_id_work = storage.add_todo(new_todo_work)
        assert assigned_id_work == 12
        
        # Add todo to new project without specifying ID
        new_todo_new_project = Todo(id=0, text="New project task", project="new_project")
        assigned_id_new_project = storage.add_todo(new_todo_new_project)
        assert assigned_id_new_project == 13
    
    def test_add_todo_with_duplicate_id_gets_reassigned(self, storage_with_existing_todos):
        """Test that adding a todo with duplicate ID gets reassigned globally unique ID."""
        storage = storage_with_existing_todos
        
        # Try to add todo with existing ID 5
        duplicate_todo = Todo(id=5, text="Duplicate ID task", project="personal")
        assigned_id = storage.add_todo(duplicate_todo)
        
        # Should get reassigned to next available global ID
        assert assigned_id == 11
        assert assigned_id != 5
    
    def test_all_todos_have_unique_ids_after_additions(self, storage_with_existing_todos):
        """Test that all todos across all projects have unique IDs after adding new ones."""
        storage = storage_with_existing_todos
        
        # Add several todos to different projects
        new_todos = [
            Todo(id=0, text="Task A", project="inbox"),
            Todo(id=0, text="Task B", project="work"),
            Todo(id=0, text="Task C", project="personal"),
            Todo(id=0, text="Task D", project="new_project"),
            # Try to add with existing ID (should get reassigned)
            Todo(id=1, text="Task E with duplicate ID", project="inbox"),
        ]
        
        for todo in new_todos:
            storage.add_todo(todo)
        
        # Check that all todos have unique IDs
        all_todos = storage.get_all_todos()
        all_ids = [todo.id for todo in all_todos]
        unique_ids = set(all_ids)
        
        assert len(all_ids) == len(unique_ids), f"Duplicate IDs found: {all_ids}"
    
    def test_empty_storage_starts_with_id_one(self, tmp_path):
        """Test that empty storage starts ID generation from 1."""
        config = ConfigModel(data_dir=str(tmp_path))
        storage = Storage(config)
        
        next_id = storage.get_next_todo_id()
        assert next_id == 1
        
        # Add first todo
        first_todo = Todo(id=0, text="First task", project="inbox")
        assigned_id = storage.add_todo(first_todo)
        assert assigned_id == 1
    
    def test_get_next_todo_id_consistency_across_projects(self, storage_with_existing_todos):
        """Test that get_next_todo_id returns same value regardless of project parameter."""
        storage = storage_with_existing_todos
        
        # All these calls should return the same value
        next_id_global = storage.get_next_todo_id()
        next_id_inbox = storage.get_next_todo_id("inbox")
        next_id_work = storage.get_next_todo_id("work")
        next_id_nonexistent = storage.get_next_todo_id("nonexistent_project")
        
        assert next_id_global == next_id_inbox == next_id_work == next_id_nonexistent == 11
    
    def test_concurrent_todo_additions_remain_unique(self, storage_with_existing_todos):
        """Test that rapidly adding todos maintains uniqueness (simulates concurrent access)."""
        storage = storage_with_existing_todos
        
        # Simulate multiple rapid additions
        assigned_ids = []
        projects = ["inbox", "work", "personal", "project1", "project2"]
        
        for i in range(20):  # Add 20 todos rapidly
            project = projects[i % len(projects)]
            todo = Todo(id=0, text=f"Rapid task {i}", project=project)
            assigned_id = storage.add_todo(todo)
            assigned_ids.append(assigned_id)
        
        # Check that all assigned IDs are unique
        unique_ids = set(assigned_ids)
        assert len(assigned_ids) == len(unique_ids), f"Duplicate IDs in rapid addition: {assigned_ids}"
        
        # Check that IDs are sequential starting from 11
        expected_ids = list(range(11, 31))  # 11 to 30
        assert sorted(assigned_ids) == expected_ids