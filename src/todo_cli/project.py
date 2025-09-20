"""Enhanced Project data model for the Todo CLI application."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .todo import Priority
from .utils.datetime import now_utc, ensure_aware, to_iso_string


@dataclass
class Project:
    """Enhanced project model with comprehensive project management features."""
    
    name: str
    display_name: str = ""
    description: str = ""
    created: datetime = field(default_factory=now_utc)
    modified: datetime = field(default_factory=now_utc)
    
    # Project metadata
    tags: List[str] = field(default_factory=list)
    color: str = "blue"  # For UI display
    icon: str = "📋"  # Emoji or icon identifier
    
    # Project settings
    active: bool = True
    archived: bool = False
    default_priority: Priority = Priority.MEDIUM
    
    # Organization
    parent_project: Optional[str] = None
    subprojects: List[str] = field(default_factory=list)
    
    # Goals and tracking
    goal: str = ""  # Project objective
    deadline: Optional[datetime] = None
    progress: float = 0.0  # Overall project progress
    
    # Team and collaboration
    team_members: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)
    default_contexts: List[str] = field(default_factory=list)
    
    # Integration settings
    sync_enabled: bool = False
    sync_last_update: Optional[datetime] = None
    sync_provider: Optional[str] = None
    sync_config: Dict[str, Any] = field(default_factory=dict)
    
    # Custom fields
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    
    # Statistics (auto-generated)
    stats: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Post-initialization setup."""
        # Ensure all datetime fields are timezone-aware
        self.created = ensure_aware(self.created)
        self.modified = ensure_aware(self.modified)
        self.deadline = ensure_aware(self.deadline)
        self.sync_last_update = ensure_aware(self.sync_last_update)
        
        if not self.display_name:
            self.display_name = self.name.replace("_", " ").replace("-", " ").title()
        
        # Initialize default stats
        if not self.stats:
            self.stats = {
                "total_tasks": 0,
                "completed_tasks": 0,
                "overdue_tasks": 0,
                "high_priority_tasks": 0,
                "avg_completion_time": 0.0,
                "last_activity": to_iso_string(self.created),
            }
        
        self.modified = now_utc()
        
        # Validate datetime fields after normalization (non-strict mode)
        try:
            self.validate_datetimes(strict_mode=False)
        except Exception:
            # Ignore validation errors during parsing to avoid circular imports
            pass
    
    def archive(self):
        """Archive the project."""
        self.archived = True
        self.active = False
        self.modified = now_utc()
    
    def unarchive(self):
        """Unarchive the project."""
        self.archived = False
        self.active = True
        self.modified = now_utc()
    
    def deactivate(self):
        """Deactivate the project without archiving."""
        self.active = False
        self.modified = now_utc()
    
    def activate(self):
        """Activate the project."""
        self.active = True
        self.modified = now_utc()
    
    def update_stats(self, todos: List[Any]):
        """Update project statistics based on todos."""
        from .todo import TodoStatus, Priority
        
        now = now_utc()
        
        # Defensive measure: Ensure all todo datetime fields are timezone-aware
        # This prevents comparison errors between naive and aware datetimes
        for todo in todos:
            if hasattr(todo, 'created') and todo.created:
                todo.created = ensure_aware(todo.created)
            if hasattr(todo, 'modified') and todo.modified:
                todo.modified = ensure_aware(todo.modified)
            if hasattr(todo, 'due_date') and todo.due_date:
                todo.due_date = ensure_aware(todo.due_date)
            if hasattr(todo, 'start_date') and todo.start_date:
                todo.start_date = ensure_aware(todo.start_date)
            if hasattr(todo, 'completed_date') and todo.completed_date:
                todo.completed_date = ensure_aware(todo.completed_date)
        
        total_tasks = len(todos)
        completed_tasks = sum(1 for todo in todos if todo.completed)
        overdue_tasks = sum(1 for todo in todos if todo.is_overdue())
        high_priority_tasks = sum(
            1 for todo in todos 
            if todo.priority in [Priority.HIGH, Priority.CRITICAL]
        )
        
        # Calculate average completion time
        completed_todos = [todo for todo in todos if todo.completed and todo.completed_date]
        if completed_todos:
            completion_times = []
            for todo in completed_todos:
                if todo.completed_date and todo.created:
                    # Ensure timezone-aware before subtraction
                    cd = ensure_aware(todo.completed_date)
                    cr = ensure_aware(todo.created)
                    if cd and cr:
                        delta = cd - cr
                        completion_times.append(delta.total_seconds() / (24 * 3600))  # Convert to days
            
            avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0.0
        else:
            avg_completion_time = 0.0
        
        # Find last activity - normalize datetimes to avoid naive/aware comparisons
        last_activity = ensure_aware(self.created)
        for todo in todos:
            mod = ensure_aware(getattr(todo, 'modified', None)) or last_activity
            if mod > last_activity:
                last_activity = mod
        
        # Update progress
        if total_tasks > 0:
            self.progress = completed_tasks / total_tasks
        else:
            self.progress = 0.0
        
        self.stats = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "overdue_tasks": overdue_tasks,
            "high_priority_tasks": high_priority_tasks,
            "avg_completion_time": round(avg_completion_time, 2),
            "last_activity": to_iso_string(last_activity),
        }
        
        self.modified = now
    
    def is_overdue(self) -> bool:
        """Check if the project is overdue."""
        if self.deadline and not self.archived:
            return now_utc() > self.deadline
        return False
    
    def add_subproject(self, subproject_name: str):
        """Add a subproject."""
        if subproject_name not in self.subprojects:
            self.subprojects.append(subproject_name)
            self.modified = now_utc()
    
    def remove_subproject(self, subproject_name: str):
        """Remove a subproject."""
        if subproject_name in self.subprojects:
            self.subprojects.remove(subproject_name)
            self.modified = now_utc()
    
    def add_team_member(self, member: str):
        """Add a team member."""
        if member not in self.team_members:
            self.team_members.append(member)
            self.modified = now_utc()
    
    def remove_team_member(self, member: str):
        """Remove a team member."""
        if member in self.team_members:
            self.team_members.remove(member)
            self.modified = now_utc()
    
    def add_stakeholder(self, stakeholder: str):
        """Add a stakeholder."""
        if stakeholder not in self.stakeholders:
            self.stakeholders.append(stakeholder)
            self.modified = now_utc()
    
    def remove_stakeholder(self, stakeholder: str):
        """Remove a stakeholder."""
        if stakeholder in self.stakeholders:
            self.stakeholders.remove(stakeholder)
            self.modified = now_utc()
    
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
        from .utils.validation import validate_project_datetimes
        return validate_project_datetimes(self, strict_mode=strict_mode)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the Project to a dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "created": to_iso_string(self.created),
            "modified": to_iso_string(self.modified),
            "tags": self.tags,
            "color": self.color,
            "icon": self.icon,
            "active": self.active,
            "archived": self.archived,
            "default_priority": self.default_priority.value,
            "parent_project": self.parent_project,
            "subprojects": self.subprojects,
            "goal": self.goal,
            "deadline": to_iso_string(self.deadline) if self.deadline else None,
            "progress": self.progress,
            "team_members": self.team_members,
            "stakeholders": self.stakeholders,
            "default_contexts": self.default_contexts,
            "sync_enabled": self.sync_enabled,
            "sync_last_update": to_iso_string(self.sync_last_update) if self.sync_last_update else None,
            "sync_provider": self.sync_provider,
            "sync_config": self.sync_config,
            "custom_fields": self.custom_fields,
            "stats": self.stats,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create a Project from a dictionary."""
        # Convert string dates back to timezone-aware datetime objects
        if "created" in data and isinstance(data["created"], str):
            data["created"] = ensure_aware(datetime.fromisoformat(data["created"]))
        if "modified" in data and isinstance(data["modified"], str):
            data["modified"] = ensure_aware(datetime.fromisoformat(data["modified"]))
        if "deadline" in data and data["deadline"] and isinstance(data["deadline"], str):
            data["deadline"] = ensure_aware(datetime.fromisoformat(data["deadline"]))
        if "sync_last_update" in data and data["sync_last_update"] and isinstance(data["sync_last_update"], str):
            data["sync_last_update"] = ensure_aware(datetime.fromisoformat(data["sync_last_update"]))
        
        # Convert priority string back to enum
        if "default_priority" in data and isinstance(data["default_priority"], str):
            data["default_priority"] = Priority(data["default_priority"])
        
        return cls(**data)
