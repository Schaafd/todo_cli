"""Test bidirectional sync functionality including deletion handling.

This module tests the enhanced sync manager that handles deletions and conflicts
between local and remote todo items.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from src.todo_cli.app_sync_manager import AppSyncManager
from src.todo_cli.app_sync_models import (
    AppSyncProvider, SyncMapping, ExternalTodoItem, SyncResult, SyncStatus
)
from src.todo_cli.todo import Todo, Priority, TodoStatus
from src.todo_cli.storage import Storage


@pytest.fixture
def mock_storage():
    """Mock storage for testing."""
    storage = Mock(spec=Storage)
    storage.get_all_todos.return_value = []
    storage.get_todo.return_value = None
    storage.add_todo.return_value = 1
    storage.update_todo.return_value = None
    storage.delete_todo.return_value = None
    return storage


@pytest.fixture
def sync_manager(mock_storage):
    """Create sync manager with mocked dependencies."""
    manager = AppSyncManager(mock_storage)
    
    # Mock the lazy-loaded dependencies
    manager._mapping_store = Mock()
    manager._mapping_store.get_mappings_for_provider.return_value = []
    manager._mapping_store.save_mapping = AsyncMock()
    manager._mapping_store.delete_mapping = AsyncMock()
    manager._mapping_store.save_conflict = AsyncMock()
    
    return manager


@pytest.fixture
def mock_adapter():
    """Mock sync adapter for testing."""
    adapter = Mock()
    adapter.provider = AppSyncProvider.TODOIST
    adapter.ensure_authenticated = AsyncMock()
    adapter.fetch_items = AsyncMock(return_value=[])
    adapter.create_item = AsyncMock(return_value="ext123")
    adapter.update_item = AsyncMock(return_value=True)
    adapter.delete_item = AsyncMock(return_value=True)
    adapter.verify_item_exists = AsyncMock(return_value=True)
    adapter.should_sync_todo = Mock(return_value=True)
    return adapter


@pytest.mark.asyncio
class TestBidirectionalSync:
    """Test bidirectional sync functionality."""
    
    async def test_remote_deletion_sync(self, sync_manager, mock_adapter):
        """Test that remotely deleted items are deleted locally."""
        # Setup: Local todo with mapping, but not in remote fetch
        local_todo = Todo(
            id=1, text="Test todo", project="test", 
            created=datetime.now(timezone.utc)
        )
        mapping = SyncMapping(
            todo_id=1,
            external_id="ext123",
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="hash123",
            local_hash="local123",
            remote_hash="remote123"
        )
        
        # Mock storage to return the todo
        sync_manager.storage.get_todo.return_value = local_todo
        sync_manager.storage.get_all_todos.return_value = [local_todo]
        
        # Mock mapping store to return the mapping
        sync_manager._mapping_store.get_mappings_for_provider.return_value = [mapping]
        
        # Mock adapter to return empty list (simulating remote deletion)
        mock_adapter.fetch_items.return_value = []
        mock_adapter.verify_item_exists.return_value = False  # Confirm deletion
        
        # Register adapter
        sync_manager.register_adapter(AppSyncProvider.TODOIST, mock_adapter)
        
        # Run sync
        result = await sync_manager._sync_provider_internal(
            AppSyncProvider.TODOIST, strategy=None
        )
        
        # Verify remote deletion was handled
        assert result.items_deleted == 1
        sync_manager.storage.delete_todo.assert_called_once_with(1)
        sync_manager._mapping_store.delete_mapping.assert_called_once_with(1, AppSyncProvider.TODOIST)
    
    async def test_local_deletion_sync(self, sync_manager, mock_adapter):
        """Test that locally deleted items are deleted remotely."""
        # Setup: Mapping exists but no local todo (simulating local deletion)
        mapping = SyncMapping(
            todo_id=1,
            external_id="ext123",
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="hash123"
        )
        
        # Mock storage to return empty list (local todo deleted)
        sync_manager.storage.get_all_todos.return_value = []
        sync_manager._mapping_store.get_mappings_for_provider.return_value = [mapping]
        
        # Mock adapter fetch returns empty (no remote items to process)
        mock_adapter.fetch_items.return_value = []
        
        # Register adapter
        sync_manager.register_adapter(AppSyncProvider.TODOIST, mock_adapter)
        
        # Run sync
        result = await sync_manager._sync_provider_internal(
            AppSyncProvider.TODOIST, strategy=None
        )
        
        # Verify local deletion was pushed to remote
        mock_adapter.delete_item.assert_called_once_with("ext123")
        sync_manager._mapping_store.delete_mapping.assert_called_once_with(1, AppSyncProvider.TODOIST)
    
    async def test_deletion_conflict_detection(self, sync_manager, mock_adapter):
        """Test detection of deletion conflicts."""
        # Setup: Local todo modified, remote todo deleted
        local_todo = Todo(
            id=1, text="Modified locally", project="test", 
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc)
        )
        mapping = SyncMapping(
            todo_id=1,
            external_id="ext123", 
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="hash123",
            local_hash="old_hash",  # Different from current, indicating local changes
            remote_hash="remote123"
        )
        
        # Mock storage
        sync_manager.storage.get_todo.return_value = local_todo
        sync_manager.storage.get_all_todos.return_value = [local_todo]
        sync_manager._mapping_store.get_mappings_for_provider.return_value = [mapping]
        
        # Mock adapter: remote item deleted (not in fetch) but verify confirms deletion
        mock_adapter.fetch_items.return_value = []
        mock_adapter.verify_item_exists.return_value = False
        
        # Register adapter
        sync_manager.register_adapter(AppSyncProvider.TODOIST, mock_adapter)
        
        # Run sync
        result = await sync_manager._sync_provider_internal(
            AppSyncProvider.TODOIST, strategy=None
        )
        
        # Verify conflict was detected (not auto-resolved because of local changes)
        assert result.conflicts_detected >= 1
        sync_manager._mapping_store.save_conflict.assert_called()
    
    async def test_update_conflict_detection(self, sync_manager, mock_adapter):
        """Test detection of update conflicts."""
        # Setup: Both local and remote modified
        local_todo = Todo(
            id=1, text="Modified locally", project="test",
            created=datetime.now(timezone.utc),
            modified=datetime.now(timezone.utc)
        )
        remote_item = ExternalTodoItem(
            external_id="ext123",
            provider=AppSyncProvider.TODOIST,
            title="Modified remotely",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        mapping = SyncMapping(
            todo_id=1,
            external_id="ext123",
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="old_hash",
            local_hash="old_local_hash",  # Different from current
            remote_hash="old_remote_hash"  # Different from current
        )
        
        # Mock storage and mapping
        sync_manager.storage.get_todo.return_value = local_todo
        sync_manager.storage.get_all_todos.return_value = [local_todo]
        sync_manager._mapping_store.get_mappings_for_provider.return_value = [mapping]
        
        # Mock adapter to return modified remote item
        mock_adapter.fetch_items.return_value = [remote_item]
        
        # Register adapter
        sync_manager.register_adapter(AppSyncProvider.TODOIST, mock_adapter)
        
        # Run sync
        result = await sync_manager._sync_provider_internal(
            AppSyncProvider.TODOIST, strategy=None
        )
        
        # Verify conflict was detected
        assert result.conflicts_detected >= 1
        sync_manager._mapping_store.save_conflict.assert_called()


@pytest.mark.asyncio
class TestSyncMethods:
    """Test individual sync methods."""
    
    async def test_detect_remote_deletions(self, sync_manager, mock_adapter):
        """Test remote deletion detection method."""
        # Setup mapping for a task that won't be in remote items
        mapping = SyncMapping(
            todo_id=1,
            external_id="deleted_ext123",
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="hash123"
        )
        mapping_dict = {1: mapping}
        seen_external_ids = set()  # Empty - simulates task not found in remote fetch
        
        # Mock adapter to confirm deletion
        mock_adapter.verify_item_exists.return_value = False
        
        # Mock local todo exists
        local_todo = Todo(id=1, text="Test", project="test")
        sync_manager.storage.get_todo.return_value = local_todo
        
        result = SyncResult(status=SyncStatus.SUCCESS, provider=AppSyncProvider.TODOIST)
        
        # Test the method
        await sync_manager._detect_remote_deletions(
            mock_adapter, mapping_dict, seen_external_ids, result
        )
        
        # Verify deletion was handled
        assert result.items_deleted == 1
        sync_manager.storage.delete_todo.assert_called_once_with(1)
    
    async def test_detect_local_deletions(self, sync_manager, mock_adapter):
        """Test local deletion detection method."""
        # Setup mapping for a task that won't be in local todos
        mapping = SyncMapping(
            todo_id=1,
            external_id="ext123",
            provider=AppSyncProvider.TODOIST,
            last_synced=datetime.now(timezone.utc),
            sync_hash="hash123"
        )
        mapping_dict = {1: mapping}
        seen_todo_ids = set()  # Empty - simulates local deletion
        
        # Mock adapter methods
        mock_adapter.verify_item_exists.return_value = True
        mock_adapter.delete_item.return_value = True
        
        result = SyncResult(status=SyncStatus.SUCCESS, provider=AppSyncProvider.TODOIST)
        
        # Test the method
        await sync_manager._detect_local_deletions(
            mock_adapter, mapping_dict, seen_todo_ids, result
        )
        
        # Verify remote deletion was attempted
        mock_adapter.delete_item.assert_called_once_with("ext123")