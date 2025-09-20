"""Data models and structures for multi-app synchronization system.

This module contains the core data structures used across the app sync system,
including external todo representations, sync mappings, and conflict models.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum

from .todo import Todo, Priority, TodoStatus
from .utils.datetime import now_utc, ensure_aware


class AppSyncProvider(Enum):
    """Supported app sync providers."""
    TODOIST = "todoist"
    APPLE_REMINDERS = "apple_reminders"
    TICKTICK = "ticktick"
    NOTION = "notion"
    EVERNOTE = "evernote"
    MICROSOFT_TODO = "microsoft_todo"
    ANY_DO = "any_do"
    GOOGLE_TASKS = "google_tasks"
    OMNIFOCUS = "omnifocus"
    THINGS = "things"


class SyncDirection(Enum):
    """Sync direction options."""
    BIDIRECTIONAL = "bidirectional"
    PUSH_ONLY = "push_only"  # Local to remote only
    PULL_ONLY = "pull_only"  # Remote to local only


class ConflictStrategy(Enum):
    """Conflict resolution strategies."""
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    NEWEST_WINS = "newest_wins"
    MANUAL = "manual"
    MERGE = "merge"
    SKIP = "skip"


class SyncStatus(Enum):
    """Sync operation status."""
    SUCCESS = "success"
    CONFLICT = "conflict"
    ERROR = "error"
    NO_CHANGES = "no_changes"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class ConflictType(Enum):
    """Types of sync conflicts."""
    MODIFIED_BOTH = "modified_both"      # Both sides modified
    DELETED_LOCAL = "deleted_local"      # Deleted locally, modified remotely
    DELETED_REMOTE = "deleted_remote"    # Modified locally, deleted remotely
    CREATED_BOTH = "created_both"        # Same item created on both sides


@dataclass
class ExternalTodoItem:
    """Unified representation of a todo item from an external provider."""
    
    external_id: str
    provider: AppSyncProvider
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    project: Optional[str] = None
    project_id: Optional[str] = None
    completed: bool = False
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    parent_id: Optional[str] = None  # For subtasks
    url: Optional[str] = None
    assignee: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure datetime fields are timezone-aware."""
        if self.due_date and self.due_date.tzinfo is None:
            self.due_date = self.due_date.replace(tzinfo=timezone.utc)
        if self.completed_at and self.completed_at.tzinfo is None:
            self.completed_at = self.completed_at.replace(tzinfo=timezone.utc)
        if self.created_at and self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)
        if self.updated_at and self.updated_at.tzinfo is None:
            self.updated_at = self.updated_at.replace(tzinfo=timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        # Convert enum to string
        data['provider'] = self.provider.value
        # Convert datetimes to ISO strings
        for field_name in ['due_date', 'completed_at', 'created_at', 'updated_at']:
            if data.get(field_name):
                data[field_name] = data[field_name].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExternalTodoItem':
        """Create from dictionary representation."""
        # Convert provider string back to enum
        if isinstance(data.get('provider'), str):
            data['provider'] = AppSyncProvider(data['provider'])
        
        # Convert ISO strings back to datetimes and ensure timezone awareness
        for field_name in ['due_date', 'completed_at', 'created_at', 'updated_at']:
            if data.get(field_name) and isinstance(data[field_name], str):
                data[field_name] = ensure_aware(datetime.fromisoformat(data[field_name]))
        
        return cls(**data)
    
    def to_todo(self, todo_id: Optional[int] = None) -> Todo:
        """Convert external item to Todo object."""
        return Todo(
            id=todo_id or 0,
            text=self.title,
            project=self.project or "default",
            tags=self.tags,
            due_date=self.due_date,
            priority=self._map_priority_from_external(),
            status=TodoStatus.COMPLETED if self.completed else TodoStatus.PENDING,
            created=self.created_at or now_utc(),
            modified=self.updated_at or now_utc(),
            description=self.description or ""
        )
    
    def _map_priority_from_external(self) -> Priority:
        """Map external priority to Todo priority."""
        if self.priority is None:
            return Priority.MEDIUM
        
        # Generic mapping - adapters should override this
        priority_map = {
            0: Priority.LOW,
            1: Priority.LOW,
            2: Priority.MEDIUM,
            3: Priority.HIGH,
            4: Priority.CRITICAL
        }
        return priority_map.get(self.priority, Priority.MEDIUM)
    
    def compute_hash(self) -> str:
        """Compute hash for change detection."""
        # Include all relevant fields for comparison
        hash_data = {
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'priority': self.priority,
            'tags': sorted(self.tags),
            'project': self.project,
            'completed': self.completed,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()


@dataclass
class SyncMapping:
    """Maps local todos to external items across providers."""
    
    todo_id: int
    external_id: str
    provider: AppSyncProvider
    last_synced: datetime
    sync_hash: str  # Hash for change detection
    local_hash: Optional[str] = None  # Hash of local todo
    remote_hash: Optional[str] = None  # Hash of remote item
    created_at: datetime = field(default_factory=now_utc)
    sync_count: int = 0  # Number of successful syncs
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['provider'] = self.provider.value
        data['last_synced'] = self.last_synced.isoformat()
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncMapping':
        """Create from dictionary representation."""
        if isinstance(data.get('provider'), str):
            data['provider'] = AppSyncProvider(data['provider'])
        
        if isinstance(data.get('last_synced'), str):
            data['last_synced'] = ensure_aware(datetime.fromisoformat(data['last_synced']))
        
        if isinstance(data.get('created_at'), str):
            data['created_at'] = ensure_aware(datetime.fromisoformat(data['created_at']))
        
        return cls(**data)
    
    def update_sync(self, local_hash: str, remote_hash: str):
        """Update mapping after successful sync."""
        self.local_hash = local_hash
        self.remote_hash = remote_hash
        self.sync_hash = self._compute_combined_hash(local_hash, remote_hash)
        self.last_synced = now_utc()
        self.sync_count += 1
        self.last_error = None
    
    def _compute_combined_hash(self, local_hash: str, remote_hash: str) -> str:
        """Compute combined hash from local and remote hashes."""
        combined = f"{local_hash}:{remote_hash}"
        return hashlib.sha256(combined.encode()).hexdigest()


@dataclass
class SyncConflict:
    """Represents a synchronization conflict between local and remote items."""
    
    todo_id: int
    provider: AppSyncProvider
    conflict_type: ConflictType
    local_todo: Optional[Todo] = None
    remote_item: Optional[ExternalTodoItem] = None
    local_changes: Dict[str, Any] = field(default_factory=dict)
    remote_changes: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=now_utc)
    resolved: bool = False
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = {
            'todo_id': self.todo_id,
            'provider': self.provider.value,
            'conflict_type': self.conflict_type.value,
            'local_todo': self.local_todo.to_dict() if self.local_todo else None,
            'remote_item': self.remote_item.to_dict() if self.remote_item else None,
            'local_changes': self.local_changes,
            'remote_changes': self.remote_changes,
            'detected_at': self.detected_at.isoformat(),
            'resolved': self.resolved,
            'resolution': self.resolution,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncConflict':
        """Create from dictionary representation."""
        # Convert enums
        data['provider'] = AppSyncProvider(data['provider'])
        data['conflict_type'] = ConflictType(data['conflict_type'])
        
        # Convert datetime strings and ensure timezone awareness
        data['detected_at'] = ensure_aware(datetime.fromisoformat(data['detected_at']))
        if data.get('resolved_at'):
            data['resolved_at'] = ensure_aware(datetime.fromisoformat(data['resolved_at']))
        
        # Convert nested objects
        if data.get('local_todo'):
            data['local_todo'] = Todo.from_dict(data['local_todo'])
        if data.get('remote_item'):
            data['remote_item'] = ExternalTodoItem.from_dict(data['remote_item'])
        
        return cls(**data)
    
    def resolve(self, resolution: str):
        """Mark conflict as resolved."""
        self.resolved = True
        self.resolution = resolution
        self.resolved_at = now_utc()
    
    def describe(self) -> str:
        """Get human-readable description of the conflict."""
        if self.conflict_type == ConflictType.MODIFIED_BOTH:
            return f"Both local and remote versions of task '{self.local_todo.text if self.local_todo else 'Unknown'}' were modified"
        elif self.conflict_type == ConflictType.DELETED_LOCAL:
            return f"Task was deleted locally but modified remotely"
        elif self.conflict_type == ConflictType.DELETED_REMOTE:
            return f"Task '{self.local_todo.text if self.local_todo else 'Unknown'}' was modified locally but deleted remotely"
        elif self.conflict_type == ConflictType.CREATED_BOTH:
            return f"Similar task was created on both local and remote"
        else:
            return f"Unknown conflict type: {self.conflict_type.value}"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    
    status: SyncStatus
    provider: AppSyncProvider
    items_synced: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    conflicts_detected: int = 0
    conflicts_resolved: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    def complete(self):
        """Mark sync as completed and calculate duration."""
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
    
    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)
        if self.status == SyncStatus.SUCCESS:
            self.status = SyncStatus.ERROR
    
    def add_warning(self, warning: str):
        """Add a warning to the result."""
        self.warnings.append(warning)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['status'] = self.status.value
        data['provider'] = self.provider.value
        data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


@dataclass
class AppSyncConfig:
    """Configuration for app synchronization."""
    
    provider: AppSyncProvider
    enabled: bool = True
    sync_direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    auto_sync: bool = False
    sync_interval: int = 300  # seconds
    conflict_strategy: ConflictStrategy = ConflictStrategy.NEWEST_WINS
    
    # Provider-specific settings
    credentials: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)
    
    # Sync filters
    sync_completed_tasks: bool = True
    sync_archived_tasks: bool = False
    project_mappings: Dict[str, str] = field(default_factory=dict)  # local -> remote
    tag_mappings: Dict[str, str] = field(default_factory=dict)  # local -> remote
    
    # Advanced settings
    max_retries: int = 3
    timeout_seconds: int = 30
    rate_limit_requests_per_minute: int = 50
    batch_size: int = 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        data['provider'] = self.provider.value
        data['sync_direction'] = self.sync_direction.value
        data['conflict_strategy'] = self.conflict_strategy.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppSyncConfig':
        """Create from dictionary representation."""
        # Convert enums
        data['provider'] = AppSyncProvider(data['provider'])
        data['sync_direction'] = SyncDirection(data.get('sync_direction', 'bidirectional'))
        data['conflict_strategy'] = ConflictStrategy(data.get('conflict_strategy', 'newest_wins'))
        
        return cls(**data)
    
    def get_credential(self, key: str) -> Optional[str]:
        """Get credential value."""
        return self.credentials.get(key)
    
    def set_credential(self, key: str, value: str):
        """Set credential value."""
        self.credentials[key] = value
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting value."""
        return self.settings.get(key, default)
    
    def set_setting(self, key: str, value: Any):
        """Set setting value."""
        self.settings[key] = value


# Type aliases for convenience
AppSyncProviders = List[AppSyncProvider]
SyncMappings = List[SyncMapping]
SyncConflicts = List[SyncConflict]
ExternalTodoItems = List[ExternalTodoItem]