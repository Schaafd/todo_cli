"""Tests for Todo model."""

import pytest
from datetime import datetime, timedelta, timezone

from todo_cli.todo import Todo, TodoStatus, Priority


class TestTodo:
    """Test Todo model functionality."""
    
    def test_todo_creation(self):
        """Test basic todo creation."""
        todo = Todo(id=1, text="Test task")
        
        assert todo.id == 1
        assert todo.text == "Test task"
        assert todo.status == TodoStatus.PENDING
        assert todo.completed is False
        assert todo.priority == Priority.MEDIUM
        assert todo.project == "inbox"
    
    def test_todo_completion(self):
        """Test todo completion."""
        todo = Todo(id=1, text="Test task")
        
        # Initially not completed
        assert not todo.completed
        assert todo.completed_date is None
        
        # Complete the task
        todo.complete("test_user")
        
        assert todo.completed is True
        assert todo.status == TodoStatus.COMPLETED
        assert todo.completed_by == "test_user"
        assert todo.completed_date is not None
        assert todo.progress == 1.0
    
    def test_todo_reopen(self):
        """Test reopening a completed todo."""
        todo = Todo(id=1, text="Test task")
        todo.complete()
        
        # Reopen the task
        todo.reopen()
        
        assert not todo.completed
        assert todo.status == TodoStatus.PENDING
        assert todo.completed_date is None
        assert todo.completed_by is None
        assert todo.progress == 0.0
    
    def test_todo_pin_unpin(self):
        """Test pinning and unpinning todos."""
        todo = Todo(id=1, text="Test task")
        
        # Initially not pinned
        assert not todo.pinned
        
        # Pin the task
        todo.pin()
        assert todo.pinned
        
        # Unpin the task
        todo.unpin()
        assert not todo.pinned
    
    def test_todo_status_changes(self):
        """Test status changes."""
        todo = Todo(id=1, text="Test task")
        
        # Start the task
        todo.start()
        assert todo.status == TodoStatus.IN_PROGRESS
        assert todo.start_date is not None
        
        # Block the task
        todo.block("Waiting for approval")
        assert todo.status == TodoStatus.BLOCKED
        assert "Blocked: Waiting for approval" in todo.notes
        
        # Cancel the task
        todo.cancel("No longer needed")
        assert todo.status == TodoStatus.CANCELLED
        assert "Cancelled: No longer needed" in todo.notes
    
    def test_todo_overdue(self):
        """Test overdue detection."""
        # Task due yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        todo = Todo(id=1, text="Overdue task", due_date=yesterday)
        
        assert todo.is_overdue()
        
        # Task due tomorrow
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        todo.due_date = tomorrow
        
        assert not todo.is_overdue()
        
        # Completed task should not be overdue
        todo.due_date = yesterday
        todo.complete()
        
        assert not todo.is_overdue()
    
    def test_todo_deferred(self):
        """Test deferred task detection."""
        # Task deferred until tomorrow
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        todo = Todo(id=1, text="Deferred task", defer_until=tomorrow)
        
        assert todo.is_deferred()
        
        # Task deferred until yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        todo.defer_until = yesterday
        
        assert not todo.is_deferred()
    
    def test_todo_active(self):
        """Test active task detection."""
        todo = Todo(id=1, text="Active task")
        
        # Pending task is active
        assert todo.is_active()
        
        # In progress task is active
        todo.start()
        assert todo.is_active()
        
        # Completed task is not active
        todo.complete()
        assert not todo.is_active()
        
        # Cancelled task is not active
        todo = Todo(id=2, text="Cancelled task")
        todo.cancel()
        assert not todo.is_active()
        
        # Blocked task is not active
        todo = Todo(id=3, text="Blocked task")
        todo.block()
        assert not todo.is_active()
        
        # Deferred task is not active
        tomorrow = datetime.now() + timedelta(days=1)
        todo = Todo(id=4, text="Deferred task", defer_until=tomorrow)
        assert not todo.is_active()
    
    def test_todo_progress(self):
        """Test progress tracking."""
        todo = Todo(id=1, text="Task with progress")
        
        # Initial progress
        assert todo.progress == 0.0
        
        # Update progress
        todo.update_progress(0.5)
        assert todo.progress == 0.5
        
        # Progress clamped to 0.0-1.0
        todo.update_progress(-0.1)
        assert todo.progress == 0.0
        
        todo.update_progress(1.5)
        assert todo.progress == 1.0
        assert todo.completed  # Auto-completed at 100%
    
    def test_todo_time_tracking(self):
        """Test time tracking."""
        todo = Todo(id=1, text="Task with time tracking", time_estimate=120)
        
        assert todo.time_estimate == 120
        assert todo.time_spent == 0
        
        # Add time
        todo.add_time(30)
        assert todo.time_spent == 30
        
        todo.add_time(45)
        assert todo.time_spent == 75
    
    def test_todo_to_dict(self):
        """Test todo serialization to dictionary."""
        todo = Todo(
            id=1,
            text="Test task",
            priority=Priority.HIGH,
            tags=["urgent", "work"],
            assignees=["john", "jane"]
        )
        
        data = todo.to_dict()
        
        assert data["id"] == 1
        assert data["text"] == "Test task"
        assert data["priority"] == "high"
        assert data["tags"] == ["urgent", "work"]
        assert data["assignees"] == ["john", "jane"]
        assert data["status"] == "pending"