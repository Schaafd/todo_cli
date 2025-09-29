"""Main orchestration class for managing multiple app sync adapters.

This module provides the central AppSyncManager class that coordinates
synchronization across multiple external applications and services.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field

from .app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    SyncResult,
    SyncStatus,
    ConflictStrategy,
    SyncMapping,
    SyncConflict,
    ExternalTodoItem
)
from .app_sync_adapter import AppSyncAdapter, AppSyncError
from .todo import Todo
from .storage import Storage


logger = logging.getLogger(__name__)


@dataclass
class SyncOperation:
    """Represents a sync operation in progress."""
    provider: AppSyncProvider
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    result: Optional[SyncResult] = None
    cancelled: bool = False
    
    def is_complete(self) -> bool:
        return self.completed_at is not None or self.cancelled
    
    def duration_seconds(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return 0.0


class AppSyncManager:
    """Main orchestration class for managing multiple app sync adapters.
    
    This class provides a unified interface for:
    - Registering and managing multiple sync adapters
    - Coordinating sync operations across providers
    - Handling conflicts and error scenarios
    - Providing sync status and history
    """
    
    def __init__(self, storage: Storage):
        """Initialize the sync manager.
        
        Args:
            storage: Todo storage instance
        """
        self.storage = storage
        self.adapters: Dict[AppSyncProvider, AppSyncAdapter] = {}
        self.configs: Dict[AppSyncProvider, AppSyncConfig] = {}
        self.active_operations: Dict[AppSyncProvider, SyncOperation] = {}
        self.sync_history: List[SyncResult] = []
        self.max_history_entries = 100
        self.logger = logging.getLogger(__name__)
        
        # Will be initialized when first needed
        self._mapping_store = None
        self._credential_manager = None
    
    @property
    def mapping_store(self):
        """Lazy-load the mapping store."""
        if self._mapping_store is None:
            from .sync_mapping_store import SyncMappingStore
            self._mapping_store = SyncMappingStore()
        return self._mapping_store
    
    @property
    def credential_manager(self):
        """Lazy-load the credential manager."""
        if self._credential_manager is None:
            from .credential_manager import CredentialManager
            self._credential_manager = CredentialManager()
        return self._credential_manager
    
    # Adapter Management
    
    def register_adapter(self, provider: AppSyncProvider, adapter: AppSyncAdapter):
        """Register a sync adapter for a provider.
        
        Args:
            provider: The sync provider
            adapter: The adapter instance
        """
        self.adapters[provider] = adapter
        self.configs[provider] = adapter.config
        self.logger.info(f"Registered adapter for {provider.value}")
    
    def unregister_adapter(self, provider: AppSyncProvider):
        """Unregister a sync adapter.
        
        Args:
            provider: The sync provider to unregister
        """
        if provider in self.adapters:
            del self.adapters[provider]
            del self.configs[provider]
            self.logger.info(f"Unregistered adapter for {provider.value}")
    
    def get_adapter(self, provider: AppSyncProvider) -> Optional[AppSyncAdapter]:
        """Get registered adapter for a provider.
        
        Args:
            provider: The sync provider
            
        Returns:
            The adapter instance or None if not registered
        """
        return self.adapters.get(provider)
    
    def get_registered_providers(self) -> List[AppSyncProvider]:
        """Get list of registered providers.
        
        Returns:
            List of registered provider enums
        """
        return list(self.adapters.keys())
    
    def get_enabled_providers(self) -> List[AppSyncProvider]:
        """Get list of enabled providers.
        
        Returns:
            List of enabled provider enums
        """
        return [
            provider for provider, config in self.configs.items()
            if config.enabled
        ]
    
    # Sync Operations
    
    async def sync_all(self, strategy: Optional[ConflictStrategy] = None) -> Dict[AppSyncProvider, SyncResult]:
        """Sync all enabled providers.
        
        Args:
            strategy: Optional conflict resolution strategy override
            
        Returns:
            Dictionary mapping providers to their sync results
        """
        enabled_providers = self.get_enabled_providers()
        
        if not enabled_providers:
            self.logger.warning("No enabled providers to sync")
            return {}
        
        self.logger.info(f"Starting sync for {len(enabled_providers)} providers: {[p.value for p in enabled_providers]}")
        
        # Create sync operations for all providers
        operations = {}
        for provider in enabled_providers:
            operation = SyncOperation(provider=provider)
            self.active_operations[provider] = operation
            operations[provider] = operation
        
        # Run syncs concurrently
        tasks = []
        for provider in enabled_providers:
            task = asyncio.create_task(self._sync_provider_internal(provider, strategy))
            tasks.append(task)
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        sync_results = {}
        for i, provider in enumerate(enabled_providers):
            result = results[i]
            operation = operations[provider]
            
            if isinstance(result, Exception):
                # Handle exception
                sync_result = SyncResult(
                    status=SyncStatus.ERROR,
                    provider=provider
                )
                sync_result.add_error(f"Sync failed: {str(result)}")
                sync_result.complete()
            else:
                sync_result = result
            
            operation.result = sync_result
            operation.completed_at = datetime.now(timezone.utc)
            sync_results[provider] = sync_result
            
            # Remove from active operations
            if provider in self.active_operations:
                del self.active_operations[provider]
            
            # Add to history
            self.sync_history.append(sync_result)
        
        # Trim history
        self._trim_sync_history()
        
        self.logger.info(f"Sync completed for {len(enabled_providers)} providers")
        return sync_results
    
    async def sync_provider(self, provider: AppSyncProvider, strategy: Optional[ConflictStrategy] = None) -> SyncResult:
        """Sync a specific provider.
        
        Args:
            provider: The provider to sync
            strategy: Optional conflict resolution strategy override
            
        Returns:
            Sync result
        """
        if provider not in self.adapters:
            raise ValueError(f"No adapter registered for {provider.value}")
        
        if not self.configs[provider].enabled:
            raise ValueError(f"Provider {provider.value} is not enabled")
        
        # Create sync operation
        operation = SyncOperation(provider=provider)
        self.active_operations[provider] = operation
        
        try:
            result = await self._sync_provider_internal(provider, strategy)
            operation.result = result
            operation.completed_at = datetime.now(timezone.utc)
            
            # Add to history
            self.sync_history.append(result)
            self._trim_sync_history()
            
            return result
            
        finally:
            # Clean up active operation
            if provider in self.active_operations:
                del self.active_operations[provider]
    
    async def _sync_provider_internal(self, provider: AppSyncProvider, strategy: Optional[ConflictStrategy] = None) -> SyncResult:
        """Internal sync implementation for a provider.
        
        Args:
            provider: The provider to sync
            strategy: Optional conflict resolution strategy override
            
        Returns:
            Sync result
        """
        adapter = self.adapters[provider]
        config = self.configs[provider]
        effective_strategy = strategy or config.conflict_strategy
        
        result = SyncResult(status=SyncStatus.SUCCESS, provider=provider)
        
        try:
            self.logger.info(f"Starting sync for {provider.value}")
            
            # Ensure authentication
            await adapter.ensure_authenticated()
            
            # Get last sync time for incremental sync
            last_sync_time = await self._get_last_sync_time(provider)
            
            # Fetch remote items
            remote_items = await adapter.fetch_items(since=last_sync_time)
            self.logger.info(f"Fetched {len(remote_items)} remote items from {provider.value}")
            
            # Get local todos that should be synced
            local_todos = await self._get_local_todos_for_sync(provider)
            self.logger.info(f"Found {len(local_todos)} local todos for sync")
            
            # Get existing mappings
            mappings = await self.mapping_store.get_mappings_for_provider(provider)
            mapping_dict = {m.todo_id: m for m in mappings}
            
            # Sync bidirectionally based on config
            if config.sync_direction.value in ['bidirectional', 'push_only']:
                await self._push_local_changes(adapter, local_todos, mapping_dict, result)
            
            if config.sync_direction.value in ['bidirectional', 'pull_only']:
                await self._pull_remote_changes(adapter, remote_items, mapping_dict, result)
            
            # Handle conflicts if any were detected
            if result.conflicts_detected > 0:
                await self._resolve_conflicts(provider, effective_strategy, result)
            
            # Update last sync time
            await self._update_last_sync_time(provider)
            
            result.complete()
            self.logger.info(f"Sync completed for {provider.value}: {result.items_synced} items synced")
            
        except Exception as e:
            result.add_error(f"Sync failed: {str(e)}")
            result.complete()
            self.logger.error(f"Sync failed for {provider.value}: {e}")
        
        return result
    
    async def _push_local_changes(self, adapter: AppSyncAdapter, local_todos: List[Todo], 
                                  mapping_dict: Dict[int, SyncMapping], result: SyncResult):
        """Push local changes to remote service."""
        # Track which local todos we've seen (for deletion detection)
        seen_todo_ids = set()
        
        for todo in local_todos:
            try:
                seen_todo_ids.add(todo.id)
                existing_mapping = mapping_dict.get(todo.id)
                
                if existing_mapping:
                    # Check if this is actually a conflict
                    local_hash = self._compute_todo_hash(todo)
                    if (existing_mapping.local_hash and 
                        existing_mapping.local_hash != local_hash):
                        # Local has changes, push them
                        success = await adapter.update_item(existing_mapping.external_id, todo)
                        if success:
                            result.items_updated += 1
                            # Update mapping - remote hash will be updated during pull
                            existing_mapping.update_sync(local_hash, existing_mapping.remote_hash or "")
                            await self.mapping_store.save_mapping(existing_mapping)
                        else:
                            # Update failed, likely because remote task doesn't exist
                            # Remove the stale mapping and create a new task
                            self.logger.info(f"Removing stale mapping for todo {todo.id} and creating new task")
                            await self.mapping_store.delete_mapping(todo.id, adapter.provider)
                            
                            # Create new item instead
                            external_id = await adapter.create_item(todo)
                            result.items_created += 1
                            
                            # Create new mapping
                            new_mapping = SyncMapping(
                                todo_id=todo.id,
                                external_id=external_id,
                                provider=adapter.provider,
                                last_synced=datetime.now(timezone.utc),
                                sync_hash=local_hash,
                                local_hash=local_hash
                            )
                            await self.mapping_store.save_mapping(new_mapping)
                else:
                    # Create new item
                    external_id = await adapter.create_item(todo)
                    result.items_created += 1
                    
                    # Create new mapping
                    local_hash = self._compute_todo_hash(todo)
                    new_mapping = SyncMapping(
                        todo_id=todo.id,
                        external_id=external_id,
                        provider=adapter.provider,
                        last_synced=datetime.now(timezone.utc),
                        sync_hash=local_hash,
                        local_hash=local_hash
                    )
                    await self.mapping_store.save_mapping(new_mapping)
                    
            except Exception as e:
                result.add_error(f"Failed to push todo {todo.id}: {str(e)}")
        
        # Detect local deletions: mappings that exist but weren't seen in local todos
        await self._detect_local_deletions(adapter, mapping_dict, seen_todo_ids, result)
    
    async def _pull_remote_changes(self, adapter: AppSyncAdapter, remote_items: List[ExternalTodoItem],
                                   mapping_dict: Dict[int, SyncMapping], result: SyncResult):
        """Pull remote changes to local storage."""
        # Create reverse mapping (external_id -> mapping)
        external_mapping = {m.external_id: m for m in mapping_dict.values()}
        
        # Track which remote items we've seen (for deletion detection)
        seen_external_ids = set()
        
        for item in remote_items:
            try:
                seen_external_ids.add(item.external_id)
                existing_mapping = external_mapping.get(item.external_id)
                
                if existing_mapping:
                    # Update existing local todo
                    local_todo = self.storage.get_todo(existing_mapping.todo_id)
                    if local_todo:
                        # Check for conflicts
                        local_hash = self._compute_todo_hash(local_todo)
                        remote_hash = item.compute_hash()
                        
                        if (existing_mapping.local_hash and 
                            existing_mapping.local_hash != local_hash and 
                            existing_mapping.remote_hash != remote_hash):
                            # Conflict detected - both local and remote have changes
                            await self._handle_sync_conflict(existing_mapping, local_todo, item, result)
                        else:
                            # No conflict, safe to update
                            updated_todo = item.to_todo(existing_mapping.todo_id)
                            self.storage.update_todo(updated_todo)
                            result.items_updated += 1
                            
                            # Update mapping
                            existing_mapping.update_sync(local_hash, remote_hash)
                            await self.mapping_store.save_mapping(existing_mapping)
                    else:
                        # Local todo was deleted - this is a deletion conflict
                        await self._handle_deletion_conflict(existing_mapping, None, item, result)
                else:
                    # Create new local todo
                    new_todo = item.to_todo()
                    new_todo_id = self.storage.add_todo(new_todo)
                    result.items_created += 1
                    
                    # Create new mapping
                    remote_hash = item.compute_hash()
                    new_mapping = SyncMapping(
                        todo_id=new_todo_id,
                        external_id=item.external_id,
                        provider=adapter.provider,
                        last_synced=datetime.now(timezone.utc),
                        sync_hash=remote_hash,
                        remote_hash=remote_hash,
                        local_hash=remote_hash
                    )
                    await self.mapping_store.save_mapping(new_mapping)
                    
            except Exception as e:
                result.add_error(f"Failed to pull remote item {item.external_id}: {str(e)}")
        
        # Detect deletions: mappings that exist but weren't seen in remote items
        await self._detect_remote_deletions(adapter, mapping_dict, seen_external_ids, result)
    
    async def _resolve_conflicts(self, provider: AppSyncProvider, strategy: ConflictStrategy, result: SyncResult):
        """Resolve sync conflicts based on strategy."""
        # Get pending conflicts for this provider
        conflicts = await self.mapping_store.get_conflicts_for_provider(provider, resolved=False)
        
        for conflict in conflicts:
            try:
                if strategy == ConflictStrategy.LOCAL_WINS:
                    # Keep local version, push to remote
                    await self._resolve_conflict_local_wins(conflict, result)
                elif strategy == ConflictStrategy.REMOTE_WINS:
                    # Keep remote version, update local
                    await self._resolve_conflict_remote_wins(conflict, result)
                elif strategy == ConflictStrategy.NEWEST_WINS:
                    # Keep version with latest timestamp
                    await self._resolve_conflict_newest_wins(conflict, result)
                elif strategy == ConflictStrategy.MANUAL:
                    # Leave for manual resolution
                    continue
                elif strategy == ConflictStrategy.SKIP:
                    # Skip this conflict
                    conflict.resolve("skipped")
                    await self.mapping_store.save_conflict(conflict)
                
                result.conflicts_resolved += 1
                
            except Exception as e:
                result.add_error(f"Failed to resolve conflict for todo {conflict.todo_id}: {str(e)}")
    
    async def _resolve_conflict_local_wins(self, conflict: SyncConflict, result: SyncResult):
        """Resolve conflict by keeping local version."""
        if conflict.local_todo:
            adapter = self.adapters[conflict.provider]
            mapping = await self.mapping_store.get_mapping(conflict.todo_id, conflict.provider)
            
            if mapping:
                # Push local version to remote
                await adapter.update_item(mapping.external_id, conflict.local_todo)
                
                # Update mapping
                local_hash = self._compute_todo_hash(conflict.local_todo)
                mapping.update_sync(local_hash, local_hash)  # Assume remote matches local now
                await self.mapping_store.save_mapping(mapping)
        
        conflict.resolve("local_wins")
        await self.mapping_store.save_conflict(conflict)
    
    async def _resolve_conflict_remote_wins(self, conflict: SyncConflict, result: SyncResult):
        """Resolve conflict by keeping remote version."""
        if conflict.remote_item:
            # Update local todo with remote data
            updated_todo = conflict.remote_item.to_todo(conflict.todo_id)
            self.storage.update_todo(updated_todo)
            
            # Update mapping
            mapping = await self.mapping_store.get_mapping(conflict.todo_id, conflict.provider)
            if mapping:
                remote_hash = conflict.remote_item.compute_hash()
                mapping.update_sync(remote_hash, remote_hash)  # Assume local matches remote now
                await self.mapping_store.save_mapping(mapping)
        
        conflict.resolve("remote_wins")
        await self.mapping_store.save_conflict(conflict)
    
    async def _resolve_conflict_newest_wins(self, conflict: SyncConflict, result: SyncResult):
        """Resolve conflict by keeping newest version."""
        local_newer = False
        
        if conflict.local_todo and conflict.remote_item:
            local_time = conflict.local_todo.updated_at
            remote_time = conflict.remote_item.updated_at
            
            if local_time and remote_time:
                local_newer = local_time > remote_time
            elif local_time:
                local_newer = True
        
        if local_newer:
            await self._resolve_conflict_local_wins(conflict, result)
        else:
            await self._resolve_conflict_remote_wins(conflict, result)
    
    async def _detect_remote_deletions(self, adapter: AppSyncAdapter, mapping_dict: Dict[int, SyncMapping], 
                                      seen_external_ids: Set[str], result: SyncResult):
        """Detect items that were deleted remotely."""
        for mapping in mapping_dict.values():
            if mapping.external_id not in seen_external_ids:
                # This item wasn't in the remote fetch - it might be deleted
                try:
                    # Verify it's actually deleted by attempting to fetch it directly
                    if hasattr(adapter, 'verify_item_exists'):
                        exists = await adapter.verify_item_exists(mapping.external_id)
                        if exists:
                            continue  # Item still exists, just wasn't in the fetch
                    
                    # Item was deleted remotely
                    local_todo = self.storage.get_todo(mapping.todo_id)
                    if local_todo:
                        # Check if local todo was also modified
                        local_hash = self._compute_todo_hash(local_todo)
                        if mapping.local_hash and mapping.local_hash != local_hash:
                            # Deletion conflict - local was modified but remote was deleted
                            await self._handle_deletion_conflict(mapping, local_todo, None, result)
                        else:
                            # Safe to delete locally
                            self.storage.delete_todo(mapping.todo_id)
                            await self.mapping_store.delete_mapping(mapping.todo_id, adapter.provider)
                            result.items_deleted += 1
                            self.logger.info(f"Deleted local todo {mapping.todo_id} (deleted remotely)")
                    else:
                        # Local todo already deleted, just clean up mapping
                        await self.mapping_store.delete_mapping(mapping.todo_id, adapter.provider)
                
                except Exception as e:
                    result.add_error(f"Failed to handle remote deletion for {mapping.external_id}: {str(e)}")
    
    async def _handle_sync_conflict(self, mapping: SyncMapping, local_todo: Todo, 
                                   remote_item: ExternalTodoItem, result: SyncResult):
        """Handle sync conflicts between local and remote changes."""
        # Create conflict record for resolution
        conflict = SyncConflict(
            todo_id=local_todo.id,
            external_id=mapping.external_id,
            provider=mapping.provider,
            conflict_type="update_conflict",
            local_todo=local_todo,
            remote_item=remote_item,
            detected_at=datetime.now(timezone.utc)
        )
        
        await self.mapping_store.save_conflict(conflict)
        result.conflicts_detected += 1
        self.logger.warning(f"Sync conflict detected for todo {local_todo.id}")
    
    async def _detect_local_deletions(self, adapter: AppSyncAdapter, mapping_dict: Dict[int, SyncMapping], 
                                      seen_todo_ids: Set[int], result: SyncResult):
        """Detect items that were deleted locally."""
        for todo_id, mapping in mapping_dict.items():
            if todo_id not in seen_todo_ids:
                # This todo wasn't in the local fetch - it was deleted locally
                try:
                    # Check if the remote item still exists and was modified
                    if hasattr(adapter, 'verify_item_exists'):
                        exists = await adapter.verify_item_exists(mapping.external_id)
                        if exists:
                            # Remote exists but local was deleted - potential conflict
                            # We could fetch the remote item to check for modifications
                            await self._handle_deletion_conflict(mapping, None, None, result)
                            continue
                    
                    # Remote item might also be deleted, or we can't verify - delete remotely
                    success = await adapter.delete_item(mapping.external_id)
                    if success:
                        result.items_deleted += 1
                        self.logger.info(f"Deleted remote task {mapping.external_id} (deleted locally)")
                    
                    # Clean up mapping regardless of remote deletion success
                    await self.mapping_store.delete_mapping(mapping.todo_id, adapter.provider)
                    
                except Exception as e:
                    result.add_error(f"Failed to handle local deletion for todo {todo_id}: {str(e)}")
    
    async def _handle_deletion_conflict(self, mapping: SyncMapping, local_todo: Optional[Todo], 
                                       remote_item: Optional[ExternalTodoItem], result: SyncResult):
        """Handle conflicts involving deletions."""
        if local_todo and not remote_item:
            conflict_type = "remote_deleted_local_modified"
        elif not local_todo and remote_item:
            conflict_type = "local_deleted_remote_modified"
        else:
            conflict_type = "both_deleted"
        
        conflict = SyncConflict(
            todo_id=mapping.todo_id,
            external_id=mapping.external_id,
            provider=mapping.provider,
            conflict_type=conflict_type,
            local_todo=local_todo,
            remote_item=remote_item,
            detected_at=datetime.now(timezone.utc)
        )
        
        # For both_deleted conflicts, auto-resolve by cleaning up
        if conflict_type == "both_deleted":
            await self.mapping_store.delete_mapping(mapping.todo_id, mapping.provider)
            conflict.resolve("both_deleted_cleanup")
            await self.mapping_store.save_conflict(conflict)
            result.conflicts_resolved += 1
        else:
            await self.mapping_store.save_conflict(conflict)
            result.conflicts_detected += 1
            self.logger.warning(f"Deletion conflict detected: {conflict_type} for todo {mapping.todo_id}")
    
    # Utility Methods
    
    async def _get_local_todos_for_sync(self, provider: AppSyncProvider) -> List[Todo]:
        """Get local todos that should be synced for a provider."""
        all_todos = self.storage.get_all_todos()
        adapter = self.adapters[provider]
        
        # Filter todos based on sync criteria
        syncable_todos = []
        for todo in all_todos:
            if adapter.should_sync_todo(todo):
                syncable_todos.append(todo)
        
        return syncable_todos
    
    async def _get_last_sync_time(self, provider: AppSyncProvider) -> Optional[datetime]:
        """Get the last successful sync time for a provider."""
        # Look through sync history for the last successful sync
        for result in reversed(self.sync_history):
            if result.provider == provider and result.status == SyncStatus.SUCCESS:
                return result.started_at
        return None
    
    async def _update_last_sync_time(self, provider: AppSyncProvider):
        """Update the last sync time for a provider."""
        # This is automatically handled by adding results to sync history
        pass
    
    def _compute_todo_hash(self, todo: Todo) -> str:
        """Compute hash for a todo for change detection."""
        # Create an external todo item to use its hash function
        external_item = ExternalTodoItem(
            external_id="",
            provider=AppSyncProvider.TODOIST,  # Doesn't matter for hashing
            title=todo.text,
            description=todo.description,
            due_date=todo.due_date,
            priority=todo.priority.value if todo.priority else None,
            tags=todo.tags,
            project=todo.project,
            completed=todo.completed,
            completed_at=todo.completed_date if todo.completed else None
        )
        return external_item.compute_hash()
    
    def _trim_sync_history(self):
        """Trim sync history to maximum entries."""
        if len(self.sync_history) > self.max_history_entries:
            self.sync_history = self.sync_history[-self.max_history_entries:]
    
    # Status and Information Methods
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status for all providers.
        
        Returns:
            Dictionary with sync status information
        """
        status = {
            'providers': {},
            'active_operations': len(self.active_operations),
            'total_registered': len(self.adapters),
            'total_enabled': len(self.get_enabled_providers())
        }
        
        for provider in self.adapters:
            config = self.configs[provider]
            adapter = self.adapters[provider]
            
            # Find last sync result
            last_result = None
            for result in reversed(self.sync_history):
                if result.provider == provider:
                    last_result = result
                    break
            
            provider_status = {
                'enabled': config.enabled,
                'provider_name': adapter.provider_name,
                'auto_sync': config.auto_sync,
                'sync_direction': config.sync_direction.value,
                'conflict_strategy': config.conflict_strategy.value,
                'last_sync': last_result.started_at.isoformat() if last_result else None,
                'last_sync_status': last_result.status.value if last_result else None,
                'last_sync_duration': last_result.duration_seconds if last_result else None,
                'is_syncing': provider in self.active_operations,
                'supported_features': adapter.get_supported_features()
            }
            
            if last_result:
                provider_status.update({
                    'items_synced': last_result.items_synced,
                    'conflicts_detected': last_result.conflicts_detected,
                    'errors': len(last_result.errors)
                })
            
            status['providers'][provider.value] = provider_status
        
        return status
    
    def get_sync_history(self, limit: Optional[int] = None) -> List[SyncResult]:
        """Get sync history.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of sync results, newest first
        """
        history = list(reversed(self.sync_history))
        if limit:
            history = history[:limit]
        return history
    
    def cancel_sync(self, provider: AppSyncProvider) -> bool:
        """Cancel an active sync operation.
        
        Args:
            provider: Provider to cancel sync for
            
        Returns:
            True if sync was cancelled, False if no active sync
        """
        if provider in self.active_operations:
            operation = self.active_operations[provider]
            operation.cancelled = True
            operation.completed_at = datetime.now(timezone.utc)
            del self.active_operations[provider]
            
            self.logger.info(f"Cancelled sync for {provider.value}")
            return True
        
        return False
    
    def cancel_all_syncs(self) -> int:
        """Cancel all active sync operations.
        
        Returns:
            Number of syncs that were cancelled
        """
        count = len(self.active_operations)
        
        for provider in list(self.active_operations.keys()):
            self.cancel_sync(provider)
        
        self.logger.info(f"Cancelled {count} active sync operations")
        return count