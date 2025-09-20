"""Enhanced Project data model for the Todo CLI application."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .todo import Priority


@dataclass
class Project:
    """Enhanced project model with comprehensive project management features."""
    
    name: str
    display_name: str = ""
    description: str = ""
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    modified: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
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
                "last_activity": self.created.isoformat(),
            }
        
        self.modified = datetime.now(timezone.utc)
    
    def archive(self):
        """Archive the project."""
        self.archived = True
        self.active = False
        self.modified = datetime.now(timezone.utc)
    
    def unarchive(self):
        """Unarchive the project."""
        self.archived = False
        self.active = True
        self.modified = datetime.now(timezone.utc)
    
    def deactivate(self):
        """Deactivate the project without archiving."""
        self.active = False
        self.modified = datetime.now(timezone.utc)
    
    def activate(self):
        """Activate the project."""
        self.active = True
        self.modified = datetime.now(timezone.utc)
    
    def update_stats(self, todos: List[Any]):
        """Update project statistics based on todos."""
        from .todo import TodoStatus, Priority
        
        now = datetime.now(timezone.utc)
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
                    delta = todo.completed_date - todo.created
                    completion_times.append(delta.total_seconds() / (24 * 3600))  # Convert to days
            
            avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0.0
        else:
            avg_completion_time = 0.0
        
        # Find last activity
        last_activity = self.created
        for todo in todos:
            if todo.modified > last_activity:
                last_activity = todo.modified
        
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
            "last_activity": last_activity.isoformat(),
        }
        
        self.modified = now
    
    def is_overdue(self) -> bool:
        """Check if the project is overdue."""
        if self.deadline and not self.archived:
            return datetime.now(timezone.utc) > self.deadline
        return False
    
    def add_subproject(self, subproject_name: str):
        """Add a subproject."""
        if subproject_name not in self.subprojects:
            self.subprojects.append(subproject_name)
            self.modified = datetime.now(timezone.utc)
    
    def remove_subproject(self, subproject_name: str):
        """Remove a subproject."""
        if subproject_name in self.subprojects:
            self.subprojects.remove(subproject_name)
            self.modified = datetime.now(timezone.utc)
    
    def add_team_member(self, member: str):
        """Add a team member."""
        if member not in self.team_members:
            self.team_members.append(member)
            self.modified = datetime.now(timezone.utc)
    
    def remove_team_member(self, member: str):
        """Remove a team member."""
        if member in self.team_members:
            self.team_members.remove(member)
            self.modified = datetime.now(timezone.utc)
    
    def add_stakeholder(self, stakeholder: str):
        """Add a stakeholder."""
        if stakeholder not in self.stakeholders:
            self.stakeholders.append(stakeholder)
            self.modified = datetime.now(timezone.utc)
    
    def remove_stakeholder(self, stakeholder: str):
        """Remove a stakeholder."""
        if stakeholder in self.stakeholders:
            self.stakeholders.remove(stakeholder)
            self.modified = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the Project to a dictionary."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "created": self.created.isoformat(),
            "modified": self.modified.isoformat(),
            "tags": self.tags,
            "color": self.color,
            "icon": self.icon,
            "active": self.active,
            "archived": self.archived,
            "default_priority": self.default_priority.value,
            "parent_project": self.parent_project,
            "subprojects": self.subprojects,
            "goal": self.goal,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "progress": self.progress,
            "team_members": self.team_members,
            "stakeholders": self.stakeholders,
            "default_contexts": self.default_contexts,
            "sync_enabled": self.sync_enabled,
            "sync_last_update": self.sync_last_update.isoformat() if self.sync_last_update else None,
            "sync_provider": self.sync_provider,
            "sync_config": self.sync_config,
            "custom_fields": self.custom_fields,
            "stats": self.stats,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create a Project from a dictionary."""
        # Convert string dates back to datetime objects
        if "created" in data and isinstance(data["created"], str):
            data["created"] = datetime.fromisoformat(data["created"])
        if "modified" in data and isinstance(data["modified"], str):
            data["modified"] = datetime.fromisoformat(data["modified"])
        if "deadline" in data and data["deadline"] and isinstance(data["deadline"], str):
            data["deadline"] = datetime.fromisoformat(data["deadline"])
        if "sync_last_update" in data and data["sync_last_update"] and isinstance(data["sync_last_update"], str):
            data["sync_last_update"] = datetime.fromisoformat(data["sync_last_update"])
        
        # Convert priority string back to enum
        if "default_priority" in data and isinstance(data["default_priority"], str):
            data["default_priority"] = Priority(data["default_priority"])
        
        return cls(**data)