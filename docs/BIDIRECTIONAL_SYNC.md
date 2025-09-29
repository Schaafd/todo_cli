# Bidirectional Sync Enhancement

## Overview

This document describes the enhanced bidirectional synchronization system for the todo CLI application, specifically addressing deletion handling and conflict resolution between local and remote (Todoist) todo items.

## Problem Statement

The original sync implementation had several limitations:

1. **Missing Deletion Sync**: When a task was deleted in Todoist, the deletion was not reflected locally
2. **Incomplete Conflict Resolution**: Basic conflict handling without deletion conflict resolution  
3. **Stale Mapping Issues**: Limited cleanup of orphaned sync mappings
4. **One-way Deletion**: Local deletions didn't consistently propagate to remote services

## Solution Architecture

### Three-Phase Sync Process

1. **Discovery Phase**: Detect all changes (creates, updates, deletions)
2. **Reconciliation Phase**: Resolve conflicts and determine appropriate actions
3. **Application Phase**: Apply all changes bidirectionally

### Key Components

#### 1. Enhanced AppSyncManager (`app_sync_manager.py`)

**New Methods:**
- `_detect_remote_deletions()`: Identifies items deleted remotely
- `_detect_local_deletions()`: Identifies items deleted locally  
- `_handle_sync_conflict()`: Manages update conflicts
- `_handle_deletion_conflict()`: Manages deletion conflicts

**Enhanced Methods:**
- `_pull_remote_changes()`: Now includes conflict detection and deletion handling
- `_push_local_changes()`: Now tracks changes and detects local deletions

#### 2. Enhanced TodoistAdapter (`todoist_adapter.py`)

**New Methods:**
- `verify_item_exists()`: Confirms if a remote task still exists

**Enhanced Methods:**
- `cleanup_stale_mappings()`: Uses the new verify method for consistency

#### 3. Enhanced SyncConflict Model (`app_sync_models.py`)

**New Features:**
- Support for custom string-based conflict types
- Enhanced conflict descriptions for deletion scenarios
- Flexible conflict type handling (enum + string)

## Deletion Handling Strategy

### Remote Deletions (Todoist → Local)

1. **Detection**: During remote fetch, compare returned items with existing mappings
2. **Verification**: Use `verify_item_exists()` to confirm deletion vs. fetch issue
3. **Conflict Check**: Check if local item was also modified since last sync
4. **Resolution**:
   - No local changes: Delete locally and clean up mapping
   - Local changes: Create deletion conflict for user resolution

### Local Deletions (Local → Todoist)  

1. **Detection**: Compare local todos with existing mappings during push phase
2. **Verification**: Check if remote item still exists and was modified
3. **Resolution**:
   - Remote unchanged: Delete remotely and clean up mapping
   - Remote changed: Create deletion conflict for user resolution

## Conflict Resolution

### Conflict Types

| Type | Description | Auto-Resolution |
|------|-------------|-----------------|
| `update_conflict` | Both local and remote modified | Strategy-based |
| `remote_deleted_local_modified` | Remote deleted, local modified | Manual |
| `local_deleted_remote_modified` | Local deleted, remote modified | Manual |
| `both_deleted` | Deleted on both sides | Auto-cleanup |

### Resolution Strategies

- **Local Wins**: Keep local version, push to remote
- **Remote Wins**: Keep remote version, update local
- **Newest Wins**: Keep version with latest timestamp
- **Manual**: Flag for user resolution
- **Skip**: Skip this conflict

## Implementation Details

### Change Detection

The system uses hash-based change detection:

```python
def _compute_todo_hash(self, todo: Todo) -> str:
    # Creates hash from todo content for change detection
    external_item = ExternalTodoItem(...)
    return external_item.compute_hash()
```

### Mapping Tracking

Enhanced `SyncMapping` includes:
- `local_hash`: Hash of local todo state
- `remote_hash`: Hash of remote item state  
- `sync_hash`: Combined hash for overall sync state

### Safe Operations

- **Atomic Operations**: All sync operations are transactional
- **Error Handling**: Graceful degradation on individual item failures
- **Backup Support**: Maintains sync mappings for rollback scenarios

## Usage Examples

### Basic Sync with Deletion Handling

```python
# Register enhanced adapter
manager = AppSyncManager(storage)
adapter = TodoistAdapter(config)
manager.register_adapter(AppSyncProvider.TODOIST, adapter)

# Run bidirectional sync
result = await manager.sync_provider(AppSyncProvider.TODOIST)

# Check results
print(f"Items synced: {result.items_synced}")
print(f"Items deleted: {result.items_deleted}")
print(f"Conflicts detected: {result.conflicts_detected}")
```

### Handling Deletion Conflicts

```python
# Get unresolved conflicts
conflicts = await mapping_store.get_conflicts_for_provider(
    AppSyncProvider.TODOIST, resolved=False
)

for conflict in conflicts:
    if conflict.conflict_type == "remote_deleted_local_modified":
        # User choice: restore remote or delete local
        if user_choice == "restore_remote":
            # Recreate in Todoist
            external_id = await adapter.create_item(conflict.local_todo)
        else:
            # Delete local
            storage.delete_todo(conflict.todo_id)
```

## Testing

Comprehensive test suite in `tests/test_bidirectional_sync.py` covers:

- Remote deletion detection and handling
- Local deletion detection and handling  
- Deletion conflict scenarios
- Update conflict scenarios
- Edge cases and error conditions

Run tests with:
```bash
pytest tests/test_bidirectional_sync.py -v
```

## Performance Considerations

- **Incremental Sync**: Uses Todoist Sync API for efficient incremental updates
- **Batch Verification**: Groups existence checks to minimize API calls
- **Smart Conflict Detection**: Only creates conflicts when actual changes are detected
- **Cleanup Optimization**: Batches mapping cleanup operations

## Migration Notes

The enhanced sync system is backward compatible with existing mappings and configurations. No migration is required, but users will benefit from:

1. **Cleaner Sync State**: Automatic cleanup of stale mappings
2. **Better Conflict Handling**: More granular conflict detection and resolution
3. **Reliable Deletions**: Proper bidirectional deletion sync

## Future Enhancements

Potential improvements for future versions:

1. **Bulk Operations**: Batch create/update/delete operations for efficiency  
2. **Smart Merging**: Automatic merging of non-conflicting changes
3. **Conflict Hints**: AI-powered conflict resolution suggestions
4. **Sync Analytics**: Detailed sync performance and conflict metrics
5. **Real-time Sync**: WebSocket-based real-time synchronization

## Troubleshooting

### Common Issues

1. **Stuck Conflicts**: Use manual resolution or skip strategy
2. **Network Errors**: System gracefully handles temporary failures
3. **Authentication Issues**: Clear error messages with resolution steps

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger('todo_cli.app_sync_manager').setLevel(logging.DEBUG)
```

This provides detailed information about sync operations, conflict detection, and resolution processes.