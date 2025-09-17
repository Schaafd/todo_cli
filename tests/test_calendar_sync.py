"""Test script for calendar integration and sync functionality."""

import os
import sys
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from todo_cli.config import Config
from todo_cli.todo import Todo, Priority, TodoStatus
from todo_cli.calendar_integration import (
    CalendarSync, CalendarConfig, CalendarType, 
    SyncDirection, ConflictResolution, CalendarEvent
)
from todo_cli.sync import (
    SyncManager, SyncConfig, SyncProvider, 
    ConflictStrategy, SyncStatus, LocalFileAdapter
)


def test_calendar_event_creation():
    """Test creating calendar events from todos"""
    print("Testing calendar event creation...")
    
    # Create a sample todo
    todo = Todo(
        id=1,
        text="Team meeting",
        project="work",
        priority=Priority.HIGH,
        due_date=datetime.now() + timedelta(hours=2),
        description="Discuss project status",
        tags=["meetings", "team"],
        created=datetime.now(),
        modified=datetime.now(),
        time_estimate=60
    )
    
    # Create calendar event
    event = CalendarEvent.from_todo(todo)
    
    # Check event properties
    assert event.title == "Team meeting"
    assert event.project == "work"
    assert event.priority == "high"
    assert event.tags == ["meetings", "team"]
    assert "Discuss project status" in event.description
    
    # Test iCal format
    ical_text = event.to_ical_event()
    assert "BEGIN:VEVENT" in ical_text
    assert "SUMMARY:Team meeting" in ical_text
    assert "X-TODO-ID:1" in ical_text
    assert "END:VEVENT" in ical_text
    
    print("✅ Calendar event creation test passed")


def test_ical_adapter():
    """Test iCal file adapter"""
    print("Testing iCal adapter...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        ical_path = Path(temp_dir) / "test.ics"
        
        # Create config
        config = CalendarConfig(
            name="test_calendar",
            calendar_type=CalendarType.ICAL,
            sync_direction=SyncDirection.EXPORT_ONLY,
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            file_path=str(ical_path)
        )
        
        # Create adapter
        from todo_cli.calendar_integration import ICalAdapter
        adapter = ICalAdapter(config)
        
        # Check availability
        assert adapter.is_available()
        
        # Create test events
        events = [
            CalendarEvent(
                uid="test-1",
                title="Test Event 1",
                description="First test event",
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1)
            ),
            CalendarEvent(
                uid="test-2",
                title="Test Event 2",
                description="Second test event",
                start_time=datetime.now() + timedelta(days=1),
                end_time=datetime.now() + timedelta(days=1, hours=1)
            )
        ]
        
        # Write events
        success = adapter.write_events(events)
        assert success
        assert ical_path.exists()
        
        # Read events back
        read_events = adapter.read_events()
        assert len(read_events) == 2
        
        # Check event content
        event_titles = [e.title for e in read_events]
        assert "Test Event 1" in event_titles
        assert "Test Event 2" in event_titles
        
    print("✅ iCal adapter test passed")


def test_sync_manager():
    """Test sync manager functionality"""
    print("Testing sync manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        config_dir = Path(temp_dir) / "config"
        sync_dir = Path(temp_dir) / "sync"
        
        config_dir.mkdir()
        sync_dir.mkdir()
        
        # Create mock config and todo manager
        class MockConfig:
            def __init__(self):
                self.data_dir = str(config_dir)
                self.default_project = "inbox"
        
        class MockTodoManager:
            def __init__(self):
                self.todos = [
                    Todo(
                        id=1,
                        text="Test task 1",
                        project="work",
                        priority=Priority.MEDIUM,
                        created=datetime.now(),
                        modified=datetime.now()
                    ),
                    Todo(
                        id=2,
                        text="Test task 2",
                        project="personal",
                        priority=Priority.LOW,
                        created=datetime.now(),
                        modified=datetime.now()
                    )
                ]
            
            def get_todos(self):
                return self.todos
            
            def add_todo(self, text, **kwargs):
                new_id = max(t.id for t in self.todos) + 1 if self.todos else 1
                todo = Todo(
                    id=new_id,
                    text=text,
                    project=kwargs.get('project', 'inbox'),
                    priority=kwargs.get('priority', Priority.MEDIUM),
                    created=datetime.now(),
                    modified=datetime.now()
                )
                self.todos.append(todo)
                return todo
            
            def update_todo(self, todo_id, **kwargs):
                for todo in self.todos:
                    if todo.id == todo_id:
                        for key, value in kwargs.items():
                            setattr(todo, key, value)
                        todo.modified = datetime.now()
                        break
        
        # Mock the get_config function
        import todo_cli.sync
        original_get_config = todo_cli.sync.get_config
        todo_cli.sync.get_config = lambda: MockConfig()
        
        try:
            # Create sync manager
            todo_manager = MockTodoManager()
            sync_manager = SyncManager(todo_manager)
            
            # Create sync config
            sync_config = SyncConfig(
                provider=SyncProvider.LOCAL_FILE,
                sync_path=str(sync_dir),
                enabled=True,
                auto_sync=False,
                conflict_strategy=ConflictStrategy.NEWEST_WINS
            )
            
            # Configure sync
            success = sync_manager.configure_sync(sync_config)
            assert success
            
            # Test sync up
            status = sync_manager.sync_up()
            assert status == SyncStatus.SUCCESS
            
            # Check if sync file was created
            device_files = list(sync_dir.glob("todos_*.json"))
            assert len(device_files) == 1
            
            # Verify file content
            with open(device_files[0], 'r') as f:
                sync_data = json.load(f)
            
            assert sync_data['device_id'] == sync_manager.device_id
            assert len(sync_data['todos']) == 2
            
            # Test sync status
            status = sync_manager.get_sync_status()
            assert status['configured'] == True
            assert status['enabled'] == True
            assert status['available'] == True
            assert status['provider'] == 'local_file'
            
        finally:
            # Restore original get_config
            todo_cli.sync.get_config = original_get_config
    
    print("✅ Sync manager test passed")


def test_local_file_adapter():
    """Test local file sync adapter"""
    print("Testing local file adapter...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        sync_config = SyncConfig(
            provider=SyncProvider.LOCAL_FILE,
            sync_path=temp_dir
        )
        
        adapter = LocalFileAdapter(sync_config)
        
        # Test availability
        assert adapter.is_available()
        
        # Test file operations
        test_data = '{"test": "data"}'
        filename = "test.json"
        
        # Upload data
        success = adapter.upload_data(test_data, filename)
        assert success
        
        # Download data
        downloaded = adapter.download_data(filename)
        assert downloaded == test_data
        
        # List files
        files = adapter.list_files()
        assert filename in files
        
        # Delete file
        success = adapter.delete_file(filename)
        assert success
        
        files = adapter.list_files()
        assert filename not in files
    
    print("✅ Local file adapter test passed")


def main():
    """Run all tests"""
    print("🧪 Running calendar integration and sync tests...")
    print()
    
    try:
        test_calendar_event_creation()
        test_ical_adapter()
        test_sync_manager()
        test_local_file_adapter()
        
        print()
        print("🎉 All tests passed! Calendar integration and sync functionality is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()