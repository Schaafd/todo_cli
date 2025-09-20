"""Enhanced Todo data model for the Todo CLI application."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from .utils.datetime import now_utc, ensure_aware, to_iso_string


class Priority(Enum):
    """Task priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass
class Todo:
    """Enhanced Todo model with comprehensive task management features."""
    
    # Core identification
    id: int
    text: str
    description: str = ""  # Extended description/notes
    
    # Status and completion
    status: TodoStatus = TodoStatus.PENDING
    completed: bool = False
    completed_date: Optional[datetime] = None
    completed_by: Optional[str] = None
    
    # Organization
    project: str = "inbox"
    tags: List[str] = field(default_factory=list)
    context: List[str] = field(default_factory=list)  # @contexts like @home, @work, @phone
    
    # Scheduling
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    scheduled_date: Optional[datetime] = None  # When to work on it
    defer_until: Optional[datetime] = None  # Hide until this date
    
    # Priority and effort
    priority: Priority = Priority.MEDIUM
    effort: str = ""  # "2d", "4h", "large", "small", etc.
    energy_level: str = "medium"  # high, medium, low (mental energy required)
    
    # People and collaboration
    assignees: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)
    created_by: str = ""
    delegated_to: Optional[str] = None
    waiting_for: List[str] = field(default_factory=list)  # People/things you're waiting on
    
    # Metadata
    created: datetime = field(default_factory=now_utc)
    modified: datetime = field(default_factory=now_utc)
    pinned: bool = False
    archived: bool = False
    
    # Recurrence and templates
    recurrence: Optional[str] = None  # "daily", "weekly:friday", etc.
    parent_recurring_id: Optional[int] = None  # Links to recurring template
    recurring_template: bool = False  # True if this is a template, not an instance
    next_due: Optional[datetime] = None  # For recurring tasks
    recurrence_count: int = 0  # How many times this has recurred
    
    # Dependencies and relationships
    depends_on: List[int] = field(default_factory=list)  # Other todo IDs
    blocks: List[int] = field(default_factory=list)  # Todo IDs this blocks
    parent_id: Optional[int] = None  # For subtasks
    children: List[int] = field(default_factory=list)  # Subtask IDs
    
    # Progress and tracking
    progress: float = 0.0  # 0.0 to 1.0 (percentage complete)
    time_spent: int = 0  # Minutes spent on this task
    time_estimate: Optional[int] = None  # Estimated minutes
    
    # Location and resources
    location: Optional[str] = None  # Where this needs to be done
    url: Optional[str] = None  # Related URL/link
    files: List[str] = field(default_factory=list)  # Related file paths
    
    # Custom fields and metadata
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)  # Additional notes/comments
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        # Ensure all datetime fields are timezone-aware
        self.created = ensure_aware(self.created)
        self.modified = ensure_aware(self.modified)
        self.start_date = ensure_aware(self.start_date)
        self.due_date = ensure_aware(self.due_date)
        self.scheduled_date = ensure_aware(self.scheduled_date)
        self.defer_until = ensure_aware(self.defer_until)
        self.completed_date = ensure_aware(self.completed_date)
        self.next_due = ensure_aware(self.next_due)
        
        if self.completed and not self.completed_date:
            self.completed_date = now_utc()
        
        if self.status == TodoStatus.COMPLETED:
            self.completed = True
            
        # Update modified timestamp
        self.modified = now_utc()
        
        # Validate datetime fields after normalization
        self.validate_datetimes()
    
    def complete(self, completed_by: Optional[str] = None):
        """Mark the task as completed."""
        self.completed = True
        self.status = TodoStatus.COMPLETED
        self.completed_date = now_utc()
        self.completed_by = completed_by
        self.modified = now_utc()
        self.progress = 1.0
    
    def reopen(self):
        """Reopen a completed task."""
        self.completed = False
        self.status = TodoStatus.PENDING
        self.completed_date = None
        self.completed_by = None
        self.modified = now_utc()
        if self.progress >= 1.0:
            self.progress = 0.0
    
    def start(self):
        """Mark the task as in progress."""
        self.status = TodoStatus.IN_PROGRESS
        if not self.start_date:
            self.start_date = now_utc()
        self.modified = now_utc()
    
    def block(self, reason: Optional[str] = None):
        """Mark the task as blocked."""
        self.status = TodoStatus.BLOCKED
        self.modified = now_utc()
        if reason:
            self.notes.append(f"Blocked: {reason}")
    
    def cancel(self, reason: Optional[str] = None):
        """Cancel the task."""
        self.status = TodoStatus.CANCELLED
        self.modified = now_utc()
        if reason:
            self.notes.append(f"Cancelled: {reason}")
    
    def pin(self):
        """Pin the task to the top."""
        self.pinned = True
        self.modified = now_utc()
    
    def unpin(self):
        """Unpin the task."""
        self.pinned = False
        self.modified = now_utc()
    
    def add_time(self, minutes: int):
        """Add time spent on the task."""
        self.time_spent += minutes
        self.modified = now_utc()
    
    def update_progress(self, progress: float):
        """Update task progress (0.0 to 1.0)."""
        self.progress = max(0.0, min(1.0, progress))
        self.modified = now_utc()
        
        # Auto-complete if progress reaches 100%
        if self.progress >= 1.0 and not self.completed:
            self.complete()
    
    def is_overdue(self) -> bool:
        """Check if the task is overdue."""
        if self.due_date and not self.completed:
            return now_utc() > self.due_date
        return False
    
    def is_deferred(self) -> bool:
        """Check if the task is currently deferred."""
        if self.defer_until and not self.completed:
            return now_utc() < self.defer_until
        return False
    
    def is_active(self) -> bool:
        """Check if the task is active (not completed, cancelled, or deferred)."""
        return (
            not self.completed
            and self.status not in [TodoStatus.CANCELLED, TodoStatus.BLOCKED]
            and not self.is_deferred()
        )
    
    def validate_datetimes(self, strict_mode: bool = False) -> Dict[str, Any]:
        """Validate all datetime fields are timezone-aware.
        
        Args:
            strict_mode: If True, raise exceptions on validation failures.
                        If False, log warnings and attempt auto-fixes.
        
        Returns:
            Dictionary with validation results including any fixes applied.
            
        Raises:
            DateTimeValidationError: If strict_mode is True and validation fails.
        """
        from .utils.validation import validate_todo_datetimes
        return validate_todo_datetimes(self, strict_mode=strict_mode)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the Todo to a dictionary with timezone-aware ISO strings."""
        return {
            "id": self.id,
            "text": self.text,
            "description": self.description,
            "status": self.status.value,
            "completed": self.completed,
            "completed_date": to_iso_string(self.completed_date),
            "completed_by": self.completed_by,
            "project": self.project,
            "tags": self.tags,
            "context": self.context,
            "start_date": to_iso_string(self.start_date),
            "due_date": to_iso_string(self.due_date),
            "scheduled_date": to_iso_string(self.scheduled_date),
            "defer_until": to_iso_string(self.defer_until),
            "priority": self.priority.value,
            "effort": self.effort,
            "energy_level": self.energy_level,
            "assignees": self.assignees,
            "stakeholders": self.stakeholders,
            "created_by": self.created_by,
            "delegated_to": self.delegated_to,
            "waiting_for": self.waiting_for,
            "created": to_iso_string(self.created),
            "modified": to_iso_string(self.modified),
            "pinned": self.pinned,
            "archived": self.archived,
            "recurrence": self.recurrence,
            "parent_recurring_id": self.parent_recurring_id,
            "recurring_template": self.recurring_template,
            "next_due": to_iso_string(self.next_due),
            "recurrence_count": self.recurrence_count,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "parent_id": self.parent_id,
            "children": self.children,
            "progress": self.progress,
            "time_spent": self.time_spent,
            "time_estimate": self.time_estimate,
            "location": self.location,
            "url": self.url,
            "files": self.files,
            "custom_fields": self.custom_fields,
            "notes": self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Todo':
        """Create a Todo from a dictionary."""
        # Helper function to parse datetime strings with timezone awareness
        def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
            if date_str:
                try:
                    parsed = datetime.fromisoformat(date_str)
                    return ensure_aware(parsed)
                except ValueError:
                    return None
            return None
        
        return cls(
            id=data.get("id", 0),
            text=data.get("text", ""),
            description=data.get("description", ""),
            status=TodoStatus(data.get("status", "pending")),
            completed=data.get("completed", False),
            completed_date=parse_datetime(data.get("completed_date")),
            completed_by=data.get("completed_by"),
            project=data.get("project", "inbox"),
            tags=data.get("tags", []),
            context=data.get("context", []),
            start_date=parse_datetime(data.get("start_date")),
            due_date=parse_datetime(data.get("due_date")),
            scheduled_date=parse_datetime(data.get("scheduled_date")),
            defer_until=parse_datetime(data.get("defer_until")),
            priority=Priority(data.get("priority", "medium")),
            effort=data.get("effort", ""),
            energy_level=data.get("energy_level", "medium"),
            assignees=data.get("assignees", []),
            stakeholders=data.get("stakeholders", []),
            created_by=data.get("created_by", ""),
            delegated_to=data.get("delegated_to"),
            waiting_for=data.get("waiting_for", []),
            created=parse_datetime(data.get("created")) or now_utc(),
            modified=parse_datetime(data.get("modified")) or now_utc(),
            pinned=data.get("pinned", False),
            archived=data.get("archived", False),
            recurrence=data.get("recurrence"),
            parent_recurring_id=data.get("parent_recurring_id"),
            recurring_template=data.get("recurring_template", False),
            next_due=parse_datetime(data.get("next_due")),
            recurrence_count=data.get("recurrence_count", 0),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", []),
            parent_id=data.get("parent_id"),
            children=data.get("children", []),
            progress=data.get("progress", 0.0),
            time_spent=data.get("time_spent", 0),
            time_estimate=data.get("time_estimate"),
            location=data.get("location"),
            url=data.get("url"),
            files=data.get("files", []),
            custom_fields=data.get("custom_fields", {}),
            notes=data.get("notes", []),
        )
