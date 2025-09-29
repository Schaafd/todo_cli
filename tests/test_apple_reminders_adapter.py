"""Test Apple Reminders adapter functionality.

This module tests the Apple Reminders sync adapter including AppleScript
integration, data mapping, and bidirectional sync capabilities.
"""

import pytest
import subprocess
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.todo_cli.adapters.apple_reminders_adapter import AppleRemindersAdapter, AppleScriptInterface, AppleScriptError
from src.todo_cli.app_sync_models import (
    AppSyncProvider, AppSyncConfig, ExternalTodoItem, SyncDirection, ConflictStrategy
)
from src.todo_cli.todo import Todo, Priority, TodoStatus


@pytest.fixture
def apple_reminders_config():
    """Create test configuration for Apple Reminders."""
    return AppSyncConfig(
        provider=AppSyncProvider.APPLE_REMINDERS,
        enabled=True,
        sync_direction=SyncDirection.BIDIRECTIONAL,
        conflict_strategy=ConflictStrategy.NEWEST_WINS,
        sync_completed_tasks=True
    )


@pytest.fixture
def apple_reminders_adapter(apple_reminders_config):
    """Create Apple Reminders adapter for testing."""
    return AppleRemindersAdapter(apple_reminders_config)


@pytest.fixture
def mock_apple_script():
    """Create mock AppleScript interface."""
    mock = Mock(spec=AppleScriptInterface)
    mock.get_reminders_lists.return_value = [
        {"id": "list1", "name": "Reminders"},
        {"id": "list2", "name": "Work"},
        {"id": "list3", "name": "Personal"}
    ]
    mock.get_reminders_in_list.return_value = []
    mock.create_reminder.return_value = "reminder123"
    mock.update_reminder.return_value = True
    mock.delete_reminder.return_value = True
    mock.reminder_exists.return_value = True
    return mock


@pytest.fixture
def sample_reminder_data():
    """Sample Apple Reminders data for testing."""
    return {
        "id": "reminder123",
        "name": "Test reminder",
        "body": "Test description",
        "completed": False,
        "due_date": datetime.now(timezone.utc),
        "priority": 5,
        "list_name": "Reminders"
    }


@pytest.fixture
def sample_todo():
    """Sample Todo for testing."""
    return Todo(
        id=1,
        text="Test todo",
        project="test",
        description="Test description",
        due_date=datetime.now(timezone.utc),
        priority=Priority.MEDIUM,
        completed=False
    )


class TestAppleScriptInterface:
    """Test AppleScript interface functionality."""
    
    @patch('subprocess.run')
    def test_run_script_success(self, mock_subprocess):
        """Test successful AppleScript execution."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "test output"
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        result = interface.run_script('tell application "Reminders" to get name')
        
        assert result == "test output"
        mock_subprocess.assert_called_once()
    
    @patch('subprocess.run')
    def test_run_script_failure(self, mock_subprocess):
        """Test AppleScript execution failure."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = "Script error"
        
        interface = AppleScriptInterface()
        
        with pytest.raises(AppleScriptError):
            interface.run_script('invalid script')
    
    @patch('subprocess.run')
    def test_get_reminders_lists(self, mock_subprocess):
        """Test getting reminders lists."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Reminders, Work|||list1, list2"
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        lists = interface.get_reminders_lists()
        
        assert len(lists) == 2
        assert lists[0]["name"] == "Reminders"
        assert lists[0]["id"] == "list1"
        assert lists[1]["name"] == "Work"
        assert lists[1]["id"] == "list2"
    
    @patch('subprocess.run')
    def test_get_reminders_in_list(self, mock_subprocess):
        """Test getting reminders from a specific list."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "Test Task|||false|||rem123|||||||Test note|||5"
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        reminders = interface.get_reminders_in_list("Reminders")
        
        assert len(reminders) == 1
        assert reminders[0]["name"] == "Test Task"
        assert reminders[0]["completed"] == False
        assert reminders[0]["id"] == "rem123"
        assert reminders[0]["body"] == "Test note"
        assert reminders[0]["priority"] == 5
    
    @patch('subprocess.run')
    def test_create_reminder(self, mock_subprocess):
        """Test creating a new reminder."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "new_reminder_id"
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        reminder_id = interface.create_reminder(
            list_name="Reminders",
            name="New Task",
            body="Task description",
            priority=3
        )
        
        assert reminder_id == "new_reminder_id"
    
    @patch('subprocess.run')
    def test_update_reminder(self, mock_subprocess):
        """Test updating an existing reminder."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        success = interface.update_reminder(
            reminder_id="rem123",
            name="Updated Task",
            completed=True
        )
        
        assert success == True
    
    @patch('subprocess.run')
    def test_delete_reminder(self, mock_subprocess):
        """Test deleting a reminder."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        success = interface.delete_reminder("rem123")
        
        assert success == True
    
    @patch('subprocess.run')
    def test_reminder_exists(self, mock_subprocess):
        """Test checking if reminder exists."""
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "true"
        mock_subprocess.return_value.stderr = ""
        
        interface = AppleScriptInterface()
        exists = interface.reminder_exists("rem123")
        
        assert exists == True


class TestAppleRemindersAdapter:
    """Test Apple Reminders adapter functionality."""
    
    def test_adapter_initialization(self, apple_reminders_adapter):
        """Test adapter initialization."""
        assert apple_reminders_adapter.provider == AppSyncProvider.APPLE_REMINDERS
        assert apple_reminders_adapter.default_list_name == "Reminders"
        assert apple_reminders_adapter.sync_completed_reminders == True
    
    def test_get_required_credentials(self, apple_reminders_adapter):
        """Test that no credentials are required."""
        credentials = apple_reminders_adapter.get_required_credentials()
        assert credentials == []
    
    def test_get_supported_features(self, apple_reminders_adapter):
        """Test supported features."""
        features = apple_reminders_adapter.get_supported_features()
        expected_features = [
            "create", "read", "update", "delete",
            "lists", "due_dates", "priorities", 
            "descriptions", "completion_status"
        ]
        for feature in expected_features:
            assert feature in features
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, apple_reminders_adapter, mock_apple_script):
        """Test successful authentication."""
        apple_reminders_adapter.apple_script = mock_apple_script
        
        result = await apple_reminders_adapter.authenticate()
        
        assert result == True
        mock_apple_script.get_reminders_lists.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, apple_reminders_adapter):
        """Test authentication failure."""
        apple_reminders_adapter.apple_script.get_reminders_lists.side_effect = Exception("Access denied")
        
        with pytest.raises(Exception):  # Should raise AuthenticationError
            await apple_reminders_adapter.authenticate()
    
    @pytest.mark.asyncio
    async def test_fetch_items(self, apple_reminders_adapter, mock_apple_script, sample_reminder_data):
        """Test fetching items from Apple Reminders."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter._lists_cache = {"Reminders": "list1"}
        
        # Mock the reminders data
        mock_apple_script.get_reminders_in_list.return_value = [sample_reminder_data]
        
        # Mock authentication
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        items = await apple_reminders_adapter.fetch_items()
        
        assert len(items) == 1
        assert isinstance(items[0], ExternalTodoItem)
        assert items[0].external_id == "reminder123"
        assert items[0].title == "Test reminder"
        assert items[0].provider == AppSyncProvider.APPLE_REMINDERS
    
    @pytest.mark.asyncio
    async def test_create_item(self, apple_reminders_adapter, mock_apple_script, sample_todo):
        """Test creating an item in Apple Reminders."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        external_id = await apple_reminders_adapter.create_item(sample_todo)
        
        assert external_id == "reminder123"
        mock_apple_script.create_reminder.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_item(self, apple_reminders_adapter, mock_apple_script, sample_todo):
        """Test updating an item in Apple Reminders."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        success = await apple_reminders_adapter.update_item("reminder123", sample_todo)
        
        assert success == True
        mock_apple_script.reminder_exists.assert_called_once_with("reminder123")
        mock_apple_script.update_reminder.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_item_not_exists(self, apple_reminders_adapter, mock_apple_script, sample_todo):
        """Test updating an item that doesn't exist."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        mock_apple_script.reminder_exists.return_value = False
        
        success = await apple_reminders_adapter.update_item("nonexistent", sample_todo)
        
        assert success == False
    
    @pytest.mark.asyncio
    async def test_delete_item(self, apple_reminders_adapter, mock_apple_script):
        """Test deleting an item from Apple Reminders."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        success = await apple_reminders_adapter.delete_item("reminder123")
        
        assert success == True
        mock_apple_script.delete_reminder.assert_called_once_with("reminder123")
    
    @pytest.mark.asyncio
    async def test_verify_item_exists(self, apple_reminders_adapter, mock_apple_script):
        """Test verifying if an item exists."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        exists = await apple_reminders_adapter.verify_item_exists("reminder123")
        
        assert exists == True
        mock_apple_script.reminder_exists.assert_called_once_with("reminder123")
    
    @pytest.mark.asyncio
    async def test_fetch_projects(self, apple_reminders_adapter, mock_apple_script):
        """Test fetching projects (lists) from Apple Reminders."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        projects = await apple_reminders_adapter.fetch_projects()
        
        expected_projects = {"Reminders": "list1", "Work": "list2", "Personal": "list3"}
        assert projects == expected_projects
    
    def test_map_todo_to_external(self, apple_reminders_adapter, sample_todo):
        """Test mapping Todo to Apple Reminders format."""
        external_data = apple_reminders_adapter.map_todo_to_external(sample_todo)
        
        assert external_data["name"] == sample_todo.text
        assert external_data["body"] == sample_todo.description
        assert external_data["due_date"] == sample_todo.due_date
        assert external_data["completed"] == sample_todo.completed
        assert external_data["list_name"] == "Reminders"  # default
        assert external_data["priority"] == 5  # Medium priority maps to 5
    
    def test_map_external_to_todo(self, apple_reminders_adapter, sample_reminder_data):
        """Test mapping Apple Reminders data to ExternalTodoItem."""
        external_item = apple_reminders_adapter.map_external_to_todo(sample_reminder_data)
        
        assert isinstance(external_item, ExternalTodoItem)
        assert external_item.external_id == "reminder123"
        assert external_item.title == "Test reminder"
        assert external_item.description == "Test description"
        assert external_item.provider == AppSyncProvider.APPLE_REMINDERS
        assert external_item.project == "Reminders"
        assert external_item.completed == False
        assert external_item.tags == []  # Apple Reminders doesn't have tags
    
    def test_priority_mapping_to_apple(self, apple_reminders_adapter):
        """Test priority mapping to Apple Reminders scale."""
        # Test all priority levels
        assert apple_reminders_adapter._map_priority_to_apple(Priority.LOW) == 7
        assert apple_reminders_adapter._map_priority_to_apple(Priority.MEDIUM) == 5
        assert apple_reminders_adapter._map_priority_to_apple(Priority.HIGH) == 3
        assert apple_reminders_adapter._map_priority_to_apple(Priority.CRITICAL) == 1
        assert apple_reminders_adapter._map_priority_to_apple(None) == 5  # Default
    
    def test_priority_mapping_from_apple(self, apple_reminders_adapter):
        """Test priority mapping from Apple Reminders scale."""
        # Test Apple's 1-9 scale to our 1-4 scale
        assert apple_reminders_adapter._map_priority_from_apple(1) == 4  # Critical
        assert apple_reminders_adapter._map_priority_from_apple(2) == 4  # Critical
        assert apple_reminders_adapter._map_priority_from_apple(3) == 3  # High
        assert apple_reminders_adapter._map_priority_from_apple(4) == 3  # High
        assert apple_reminders_adapter._map_priority_from_apple(5) == 2  # Medium
        assert apple_reminders_adapter._map_priority_from_apple(6) == 2  # Medium
        assert apple_reminders_adapter._map_priority_from_apple(7) == 1  # Low
        assert apple_reminders_adapter._map_priority_from_apple(8) == 1  # Low
        assert apple_reminders_adapter._map_priority_from_apple(9) == 1  # Low
    
    def test_get_list_name_default(self, apple_reminders_adapter):
        """Test getting default list name."""
        list_name = apple_reminders_adapter._get_list_name("")
        assert list_name == "Reminders"
        
        list_name = apple_reminders_adapter._get_list_name(None)
        assert list_name == "Reminders"
    
    def test_get_list_name_mapped(self, apple_reminders_adapter):
        """Test getting mapped list name."""
        # Test direct mapping
        list_name = apple_reminders_adapter._get_list_name("work")
        assert list_name == "work"
    
    def test_should_include_reminder_completed(self, apple_reminders_adapter):
        """Test filtering completed reminders."""
        # Should include completed when sync_completed_reminders is True
        apple_reminders_adapter.sync_completed_reminders = True
        assert apple_reminders_adapter._should_include_reminder({"completed": True}) == True
        assert apple_reminders_adapter._should_include_reminder({"completed": False}) == True
        
        # Should exclude completed when sync_completed_reminders is False
        apple_reminders_adapter.sync_completed_reminders = False
        assert apple_reminders_adapter._should_include_reminder({"completed": True}) == False
        assert apple_reminders_adapter._should_include_reminder({"completed": False}) == True
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_mappings(self, apple_reminders_adapter, mock_apple_script):
        """Test cleaning up stale sync mappings."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        
        # Mock mapping store
        mock_mapping_store = Mock()
        mock_mapping_store.get_mappings_for_provider.return_value = [
            Mock(external_id="reminder1", todo_id=1),
            Mock(external_id="reminder2", todo_id=2),
        ]
        mock_mapping_store.delete_mapping = AsyncMock()
        
        # Mock one reminder as non-existent
        mock_apple_script.reminder_exists.side_effect = [True, False]
        
        cleaned_count = await apple_reminders_adapter.cleanup_stale_mappings(mock_mapping_store)
        
        assert cleaned_count == 1
        mock_mapping_store.delete_mapping.assert_called_once_with(2, AppSyncProvider.APPLE_REMINDERS)


@pytest.mark.asyncio 
class TestAppleRemindersIntegration:
    """Integration tests for Apple Reminders adapter."""
    
    async def test_full_sync_flow(self, apple_reminders_adapter, mock_apple_script):
        """Test complete sync flow."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        apple_reminders_adapter._lists_cache = {"Reminders": "list1"}
        
        # Test fetch
        mock_apple_script.get_reminders_in_list.return_value = [{
            "id": "rem1",
            "name": "Test reminder",
            "body": "",
            "completed": False,
            "due_date": None,
            "priority": 5,
            "list_name": "Reminders"
        }]
        
        items = await apple_reminders_adapter.fetch_items()
        assert len(items) == 1
        
        # Test create
        todo = Todo(id=2, text="New todo", project="test")
        external_id = await apple_reminders_adapter.create_item(todo)
        assert external_id == "reminder123"
        
        # Test update
        todo.text = "Updated todo"
        success = await apple_reminders_adapter.update_item(external_id, todo)
        assert success == True
        
        # Test delete
        success = await apple_reminders_adapter.delete_item(external_id)
        assert success == True


class TestAppleRemindersErrorHandling:
    """Test error handling in Apple Reminders adapter."""
    
    @pytest.mark.asyncio
    async def test_applescript_timeout(self, apple_reminders_adapter):
        """Test handling of AppleScript timeouts."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("cmd", 30)):
            interface = AppleScriptInterface()
            
            with pytest.raises(AppleScriptError):
                interface.run_script("test script")
    
    @pytest.mark.asyncio
    async def test_fetch_items_error_recovery(self, apple_reminders_adapter, mock_apple_script):
        """Test error recovery during item fetching."""
        apple_reminders_adapter.apple_script = mock_apple_script
        apple_reminders_adapter.ensure_authenticated = AsyncMock()
        apple_reminders_adapter._lists_cache = {"List1": "id1", "List2": "id2"}
        
        # Make one list fail but others succeed
        def side_effect(list_name):
            if list_name == "List1":
                raise Exception("Access denied")
            return []
        
        mock_apple_script.get_reminders_in_list.side_effect = side_effect
        
        # Should not raise exception, but continue with other lists
        items = await apple_reminders_adapter.fetch_items()
        assert items == []  # Empty because no reminders returned
    
    def test_date_parsing_fallback(self):
        """Test date parsing fallback behavior."""
        interface = AppleScriptInterface()
        
        # Test with invalid date string
        result = interface._parse_apple_date("invalid date")
        # Should return some datetime (current implementation returns now)
        assert isinstance(result, datetime)
        
        # Test with empty date string
        result = interface._parse_apple_date("")
        assert result is None
        
        result = interface._parse_apple_date(None)
        assert result is None