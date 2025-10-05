"""Advanced synchronization engine with conflict detection and resolution.

This module provides sophisticated conflict detection, resolution strategies,
and change tracking for bidirectional synchronization between local todos
and external applications.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum

from .app_sync_models import (
    AppSyncProvider,
    SyncMapping,
    SyncConflict,
    ExternalTodoItem,
    ConflictType,
    ConflictStrategy
)
from ..domain import Todo


logger = logging.getLogger(__name__)


class ChangeType(Enum):
    """Types of changes detected during sync."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    COMPLETED = "completed"
    REOPENED = "reopened"


@dataclass
class Change:
    """Represents a change detected during sync."""
    change_type: ChangeType
    item_id: Union[int, str]  # Local todo ID or external ID
    field_changes: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # field -> (old, new)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def get_changed_fields(self) -> Set[str]:
        """Get set of fields that changed."""
        return set(self.field_changes.keys())
    
    def is_structural_change(self) -> bool:
        """Check if this is a structural change (creation/deletion)."""
        return self.change_type in [ChangeType.CREATED, ChangeType.DELETED]
    
    def is_completion_change(self) -> bool:
        """Check if this is a completion status change."""
        return self.change_type in [ChangeType.COMPLETED, ChangeType.REOPENED]


@dataclass
class SyncPlan:
    """Plan for synchronizing changes between local and remote."""
    local_creates: List[Todo] = field(default_factory=list)
    local_updates: List[Tuple[Todo, SyncMapping]] = field(default_factory=list)
    local_deletes: List[SyncMapping] = field(default_factory=list)
    
    remote_creates: List[ExternalTodoItem] = field(default_factory=list)
    remote_updates: List[Tuple[ExternalTodoItem, SyncMapping]] = field(default_factory=list)
    remote_deletes: List[str] = field(default_factory=list)  # External IDs
    
    conflicts: List[SyncConflict] = field(default_factory=list)
    
    def has_changes(self) -> bool:
        """Check if there are any changes to sync."""
        return (bool(self.local_creates) or bool(self.local_updates) or bool(self.local_deletes) or
                bool(self.remote_creates) or bool(self.remote_updates) or bool(self.remote_deletes))
    
    def change_count(self) -> int:
        """Get total number of changes."""
        return (len(self.local_creates) + len(self.local_updates) + len(self.local_deletes) +
                len(self.remote_creates) + len(self.remote_updates) + len(self.remote_deletes))
    
    def conflict_count(self) -> int:
        """Get number of conflicts."""
        return len(self.conflicts)


class ConflictDetector:
    """Advanced conflict detection for synchronization."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_conflicts(self, local_changes: List[Change], remote_changes: List[Change],
                        mappings: Dict[int, SyncMapping]) -> List[SyncConflict]:
        """Detect conflicts between local and remote changes.
        
        Args:
            local_changes: Changes detected locally
            remote_changes: Changes detected remotely  
            mappings: Current sync mappings
            
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # Create lookup maps
        local_by_id = {c.item_id: c for c in local_changes if isinstance(c.item_id, int)}
        remote_by_external_id = {c.item_id: c for c in remote_changes if isinstance(c.item_id, str)}
        
        # Map remote changes to local todo IDs
        remote_by_local_id = {}
        for mapping in mappings.values():
            if mapping.external_id in remote_by_external_id:
                remote_by_local_id[mapping.todo_id] = remote_by_external_id[mapping.external_id]
        
        # Check for conflicts on same items
        for local_id, local_change in local_by_id.items():
            remote_change = remote_by_local_id.get(local_id)
            if not remote_change:
                continue
            
            conflict = self._analyze_change_conflict(local_change, remote_change, mappings.get(local_id))
            if conflict:
                conflicts.append(conflict)
        
        # Check for deletion conflicts
        for mapping in mappings.values():
            local_change = local_by_id.get(mapping.todo_id)
            remote_change = remote_by_external_id.get(mapping.external_id)
            
            if local_change and local_change.change_type == ChangeType.DELETED and remote_change:
                # Item deleted locally but modified remotely
                conflict = SyncConflict(
                    todo_id=mapping.todo_id,
                    provider=mapping.provider,
                    conflict_type=ConflictType.DELETED_LOCAL,
                    remote_changes=remote_change.field_changes
                )
                conflicts.append(conflict)
                
            elif remote_change and remote_change.change_type == ChangeType.DELETED and local_change:
                # Item deleted remotely but modified locally
                conflict = SyncConflict(
                    todo_id=mapping.todo_id,
                    provider=mapping.provider,
                    conflict_type=ConflictType.DELETED_REMOTE,
                    local_changes=local_change.field_changes
                )
                conflicts.append(conflict)
        
        return conflicts
    
    def _analyze_change_conflict(self, local_change: Change, remote_change: Change, 
                               mapping: Optional[SyncMapping]) -> Optional[SyncConflict]:
        """Analyze if two changes conflict."""
        if not mapping:
            return None
        
        # No conflict if only one side changed
        if local_change.change_type == ChangeType.CREATED and remote_change.change_type != ChangeType.CREATED:
            return None
        if remote_change.change_type == ChangeType.CREATED and local_change.change_type != ChangeType.CREATED:
            return None
        
        # Check for overlapping field changes
        local_fields = local_change.get_changed_fields()
        remote_fields = remote_change.get_changed_fields()
        overlapping_fields = local_fields.intersection(remote_fields)
        
        if overlapping_fields:
            # Check if the changes are actually different
            conflicting_changes = {}
            for field in overlapping_fields:
                local_new = local_change.field_changes[field][1]
                remote_new = remote_change.field_changes[field][1]
                
                if local_new != remote_new:
                    conflicting_changes[field] = {
                        'local': local_new,
                        'remote': remote_new
                    }
            
            if conflicting_changes:
                return SyncConflict(
                    todo_id=mapping.todo_id,
                    provider=mapping.provider,
                    conflict_type=ConflictType.MODIFIED_BOTH,
                    local_changes=local_change.field_changes,
                    remote_changes=remote_change.field_changes
                )
        
        return None


class ChangeDetector:
    """Detects changes in todos for synchronization."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_local_changes(self, current_todos: List[Todo], 
                           mappings: Dict[int, SyncMapping]) -> List[Change]:
        """Detect changes in local todos since last sync.
        
        Args:
            current_todos: Current state of local todos
            mappings: Sync mappings with last known hashes
            
        Returns:
            List of detected changes
        """
        changes = []
        current_by_id = {todo.id: todo for todo in current_todos}
        
        # Check for modifications and deletions
        for mapping in mappings.values():
            current_todo = current_by_id.get(mapping.todo_id)
            
            if not current_todo:
                # Todo was deleted
                changes.append(Change(
                    change_type=ChangeType.DELETED,
                    item_id=mapping.todo_id
                ))
                continue
            
            # Check if todo was modified
            current_hash = self._compute_todo_hash(current_todo)
            if current_hash != mapping.local_hash:
                # Todo was modified - detect what changed
                field_changes = self._detect_field_changes(mapping, current_todo)
                
                # Determine change type
                change_type = ChangeType.MODIFIED
                if 'completed' in field_changes:
                    old_completed, new_completed = field_changes['completed']
                    if not old_completed and new_completed:
                        change_type = ChangeType.COMPLETED
                    elif old_completed and not new_completed:
                        change_type = ChangeType.REOPENED
                
                changes.append(Change(
                    change_type=change_type,
                    item_id=mapping.todo_id,
                    field_changes=field_changes
                ))
        
        # Check for new todos
        mapped_ids = {m.todo_id for m in mappings.values()}
        for todo in current_todos:
            if todo.id not in mapped_ids:
                changes.append(Change(
                    change_type=ChangeType.CREATED,
                    item_id=todo.id
                ))
        
        return changes
    
    def detect_remote_changes(self, remote_items: List[ExternalTodoItem],
                            mappings: Dict[int, SyncMapping]) -> List[Change]:
        """Detect changes in remote items since last sync.
        
        Args:
            remote_items: Current state of remote items
            mappings: Sync mappings with last known hashes
            
        Returns:
            List of detected changes
        """
        changes = []
        remote_by_id = {item.external_id: item for item in remote_items}
        mapping_by_external_id = {m.external_id: m for m in mappings.values()}
        
        # Check for modifications and deletions
        for external_id, mapping in mapping_by_external_id.items():
            remote_item = remote_by_id.get(external_id)
            
            if not remote_item:
                # Item was deleted remotely
                changes.append(Change(
                    change_type=ChangeType.DELETED,
                    item_id=external_id
                ))
                continue
            
            # Check if item was modified
            current_hash = remote_item.compute_hash()
            if current_hash != mapping.remote_hash:
                # Item was modified - detect what changed
                field_changes = self._detect_external_field_changes(mapping, remote_item)
                
                # Determine change type
                change_type = ChangeType.MODIFIED
                if 'completed' in field_changes:
                    old_completed, new_completed = field_changes['completed']
                    if not old_completed and new_completed:
                        change_type = ChangeType.COMPLETED
                    elif old_completed and not new_completed:
                        change_type = ChangeType.REOPENED
                
                changes.append(Change(
                    change_type=change_type,
                    item_id=external_id,
                    field_changes=field_changes
                ))
        
        # Check for new items
        mapped_external_ids = {m.external_id for m in mappings.values()}
        for item in remote_items:
            if item.external_id not in mapped_external_ids:
                changes.append(Change(
                    change_type=ChangeType.CREATED,
                    item_id=item.external_id
                ))
        
        return changes
    
    def _compute_todo_hash(self, todo: Todo) -> str:
        """Compute hash for a todo."""
        # Create an external item to use its hash function
        from .app_sync_models import ExternalTodoItem, AppSyncProvider
        
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
    
    def _detect_field_changes(self, mapping: SyncMapping, current_todo: Todo) -> Dict[str, Tuple[Any, Any]]:
        """Detect which fields changed in a todo."""
        changes = {}
        
        # This is a simplified implementation - in practice, we'd need to store
        # the previous state or reconstruct it from the mapping
        # For now, we'll just indicate that something changed
        changes['last_modified'] = (mapping.last_synced, current_todo.updated_at)
        
        return changes
    
    def _detect_external_field_changes(self, mapping: SyncMapping, 
                                     current_item: ExternalTodoItem) -> Dict[str, Tuple[Any, Any]]:
        """Detect which fields changed in an external item."""
        changes = {}
        
        # Similar to above - simplified implementation
        changes['last_modified'] = (mapping.last_synced, current_item.updated_at)
        
        return changes


class ConflictResolver:
    """Resolves synchronization conflicts using various strategies."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def resolve_conflict(self, conflict: SyncConflict, strategy: ConflictStrategy,
                        local_todo: Optional[Todo] = None,
                        remote_item: Optional[ExternalTodoItem] = None) -> Dict[str, Any]:
        """Resolve a single conflict using the specified strategy.
        
        Args:
            conflict: The conflict to resolve
            strategy: Resolution strategy to use
            local_todo: Current local todo (if available)
            remote_item: Current remote item (if available)
            
        Returns:
            Resolution data with 'action' and optional 'data' fields
        """
        if strategy == ConflictStrategy.LOCAL_WINS:
            return self._resolve_local_wins(conflict, local_todo)
        elif strategy == ConflictStrategy.REMOTE_WINS:
            return self._resolve_remote_wins(conflict, remote_item)
        elif strategy == ConflictStrategy.NEWEST_WINS:
            return self._resolve_newest_wins(conflict, local_todo, remote_item)
        elif strategy == ConflictStrategy.MERGE:
            return self._resolve_merge(conflict, local_todo, remote_item)
        elif strategy == ConflictStrategy.MANUAL:
            return {'action': 'manual', 'reason': 'Manual resolution required'}
        elif strategy == ConflictStrategy.SKIP:
            return {'action': 'skip', 'reason': 'Conflict skipped by user choice'}
        else:
            return {'action': 'error', 'reason': f'Unknown strategy: {strategy}'}
    
    def _resolve_local_wins(self, conflict: SyncConflict, local_todo: Optional[Todo]) -> Dict[str, Any]:
        """Resolve conflict by keeping local version."""
        return {
            'action': 'keep_local',
            'reason': 'Local version wins by strategy',
            'data': local_todo.to_dict() if local_todo else None
        }
    
    def _resolve_remote_wins(self, conflict: SyncConflict, remote_item: Optional[ExternalTodoItem]) -> Dict[str, Any]:
        """Resolve conflict by keeping remote version."""
        return {
            'action': 'keep_remote', 
            'reason': 'Remote version wins by strategy',
            'data': remote_item.to_dict() if remote_item else None
        }
    
    def _resolve_newest_wins(self, conflict: SyncConflict, local_todo: Optional[Todo], 
                           remote_item: Optional[ExternalTodoItem]) -> Dict[str, Any]:
        """Resolve conflict by keeping newest version."""
        local_time = local_todo.updated_at if local_todo else datetime.min.replace(tzinfo=timezone.utc)
        remote_time = remote_item.updated_at if remote_item else datetime.min.replace(tzinfo=timezone.utc)
        
        if local_time > remote_time:
            return self._resolve_local_wins(conflict, local_todo)
        else:
            return self._resolve_remote_wins(conflict, remote_item)
    
    def _resolve_merge(self, conflict: SyncConflict, local_todo: Optional[Todo], 
                      remote_item: Optional[ExternalTodoItem]) -> Dict[str, Any]:
        """Resolve conflict by merging changes intelligently."""
        if not local_todo or not remote_item:
            # Can't merge without both versions
            return self._resolve_newest_wins(conflict, local_todo, remote_item)
        
        # Create merged version starting with local
        merged_data = local_todo.to_dict()
        
        # Apply smart merge rules
        merge_rules = {
            'title': 'prefer_longest',
            'description': 'prefer_longest', 
            'due_date': 'prefer_earliest',
            'priority': 'prefer_highest',
            'tags': 'merge_unique',
            'completed': 'prefer_completed'
        }
        
        for field, rule in merge_rules.items():
            local_value = getattr(local_todo, field, None)
            remote_value = getattr(remote_item, field, None)
            
            merged_value = self._apply_merge_rule(rule, local_value, remote_value)
            if merged_value is not None:
                merged_data[field] = merged_value
        
        return {
            'action': 'merge',
            'reason': 'Intelligent merge applied',
            'data': merged_data
        }
    
    def _apply_merge_rule(self, rule: str, local_value: Any, remote_value: Any) -> Any:
        """Apply a specific merge rule to two values."""
        if rule == 'prefer_longest':
            local_len = len(str(local_value)) if local_value else 0
            remote_len = len(str(remote_value)) if remote_value else 0
            return local_value if local_len >= remote_len else remote_value
        
        elif rule == 'prefer_earliest':
            if local_value and remote_value:
                return min(local_value, remote_value)
            return local_value or remote_value
        
        elif rule == 'prefer_highest':
            if local_value and remote_value:
                return max(local_value, remote_value)
            return local_value or remote_value
        
        elif rule == 'merge_unique':
            if isinstance(local_value, list) and isinstance(remote_value, list):
                return list(set(local_value + remote_value))
            return local_value or remote_value
        
        elif rule == 'prefer_completed':
            if local_value or remote_value:
                return True
            return False
        
        return local_value


class SyncEngine:
    """Main synchronization engine coordinating all sync operations."""
    
    def __init__(self):
        self.change_detector = ChangeDetector()
        self.conflict_detector = ConflictDetector()
        self.conflict_resolver = ConflictResolver()
        self.logger = logging.getLogger(__name__)
    
    def create_sync_plan(self, local_todos: List[Todo], remote_items: List[ExternalTodoItem],
                        mappings: Dict[int, SyncMapping], 
                        sync_direction: str = "bidirectional") -> SyncPlan:
        """Create a comprehensive sync plan.
        
        Args:
            local_todos: Current local todos
            remote_items: Current remote items  
            mappings: Existing sync mappings
            sync_direction: Direction to sync ("bidirectional", "push_only", "pull_only")
            
        Returns:
            Complete sync plan with all required operations
        """
        plan = SyncPlan()
        
        # Detect changes
        local_changes = self.change_detector.detect_local_changes(local_todos, mappings)
        remote_changes = self.change_detector.detect_remote_changes(remote_items, mappings)
        
        # Detect conflicts
        conflicts = self.conflict_detector.detect_conflicts(local_changes, remote_changes, mappings)
        plan.conflicts = conflicts
        
        # Create lookup maps
        local_by_id = {todo.id: todo for todo in local_todos}
        remote_by_id = {item.external_id: item for item in remote_items}
        
        # Process local changes (push to remote)
        if sync_direction in ["bidirectional", "push_only"]:
            for change in local_changes:
                if not isinstance(change.item_id, int):
                    continue
                
                todo = local_by_id.get(change.item_id)
                mapping = mappings.get(change.item_id)
                
                # Skip conflicted items
                if any(c.todo_id == change.item_id for c in conflicts):
                    continue
                
                if change.change_type == ChangeType.CREATED and todo:
                    plan.local_creates.append(todo)
                elif change.change_type in [ChangeType.MODIFIED, ChangeType.COMPLETED, ChangeType.REOPENED]:
                    if todo and mapping:
                        plan.local_updates.append((todo, mapping))
                elif change.change_type == ChangeType.DELETED and mapping:
                    plan.local_deletes.append(mapping)
        
        # Process remote changes (pull from remote)
        if sync_direction in ["bidirectional", "pull_only"]:
            for change in remote_changes:
                if not isinstance(change.item_id, str):
                    continue
                
                item = remote_by_id.get(change.item_id)
                # Find mapping by external ID
                mapping = None
                for m in mappings.values():
                    if m.external_id == change.item_id:
                        mapping = m
                        break
                
                # Skip conflicted items
                if mapping and any(c.todo_id == mapping.todo_id for c in conflicts):
                    continue
                
                if change.change_type == ChangeType.CREATED and item:
                    plan.remote_creates.append(item)
                elif change.change_type in [ChangeType.MODIFIED, ChangeType.COMPLETED, ChangeType.REOPENED]:
                    if item and mapping:
                        plan.remote_updates.append((item, mapping))
                elif change.change_type == ChangeType.DELETED:
                    plan.remote_deletes.append(change.item_id)
        
        self.logger.info(f"Created sync plan: {plan.change_count()} changes, {plan.conflict_count()} conflicts")
        return plan
    
    def resolve_conflicts(self, conflicts: List[SyncConflict], strategy: ConflictStrategy,
                         local_todos: Dict[int, Todo], remote_items: Dict[str, ExternalTodoItem]) -> List[Dict[str, Any]]:
        """Resolve all conflicts using the specified strategy.
        
        Args:
            conflicts: List of conflicts to resolve
            strategy: Resolution strategy
            local_todos: Current local todos by ID
            remote_items: Current remote items by external ID
            
        Returns:
            List of resolution results
        """
        resolutions = []
        
        for conflict in conflicts:
            local_todo = local_todos.get(conflict.todo_id)
            
            # Find remote item by mapping
            remote_item = None
            for item in remote_items.values():
                if item.provider == conflict.provider and str(item.external_id):
                    # This is simplified - in practice we'd use the mapping
                    remote_item = item
                    break
            
            resolution = self.conflict_resolver.resolve_conflict(
                conflict, strategy, local_todo, remote_item
            )
            resolutions.append({
                'conflict': conflict,
                'resolution': resolution
            })
        
        return resolutions