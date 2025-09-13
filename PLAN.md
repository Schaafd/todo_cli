# Enhanced Todo CLI Application Plan (Final)

## Core Architecture

**Storage Format**: Markdown files organized by project, with frontmatter for metadata
- `~/.todo/projects/[project-name].md` - Individual project files
- `~/.todo/config.yaml` - Global configuration
- YAML frontmatter in each MD file for project metadata

**Enhanced Data Structure**:
```yaml
# Project frontmatter with comprehensive metadata
---
# Core project identification
name: "work"
display_name: "Work Projects"
description: "Professional tasks and team collaboration"

# Timestamps
created: "2025-01-15T09:00:00Z"
modified: "2025-09-13T21:20:00Z"

# Project metadata and organization
tags: ["professional", "team", "development", "meetings"]
color: "blue"
icon: "💼"
active: true
archived: false
default_priority: "medium"

# Project hierarchy and relationships
parent_project: null
subprojects: ["work-frontend", "work-backend", "work-devops"]

# Goals and tracking
goal: "Deliver Q4 features and maintain team productivity"
deadline: "2025-12-31T23:59:59Z"
progress: 0.65  # 65% complete

# Advanced project settings
team_members: ["john", "sarah", "alice", "bob"]
stakeholders: ["manager", "product-owner", "tech-lead"]
default_contexts: ["office", "remote", "meetings"]

# Integration and sync settings
sync_enabled: true
sync_last_update: "2025-09-13T20:45:00Z"
sync_provider: "github"
sync_config:
  repository: "company/work-todos"
  branch: "main"
  auto_commit: true

# Custom fields for this project
custom_fields:
  sprint: "2025-Q4-Sprint-2"
  budget_code: "PROJ-2025-456"
  department: "Engineering"
  client: "Internal"
  risk_level: "medium"

# Statistics and metrics (auto-generated)
stats:
  total_tasks: 45
  completed_tasks: 29
  overdue_tasks: 3
  high_priority_tasks: 8
  avg_completion_time: 2.5  # days
  last_activity: "2025-09-13T16:30:00Z"
---

# Work Tasks

## Pinned Tasks

- [ ] Review pull request #123 @urgent @code-review @office ^2025-01-20 !2025-01-25 ~high *3d +john +sarah &manager [PINNED] #PR-123
  - Detailed code review of the authentication refactor PR
  - Focus on security implications and error handling
  - Check integration with SSO service
  - Located at: https://github.com/company/project/pull/123
  - Depends on: #456, #789
  - Energy: high
  - Progress: 25%
  - Time spent: 45m

- [ ] Weekly team sync @meeting @conference-room-a ^2025-01-24 !2025-01-24T14:00:00 ~medium *1h +team &manager %weekly:friday [PINNED] #team-meetings
  - Prepare sprint demo for stakeholders
  - Review velocity metrics and blockers
  - Discuss upcoming Q4 planning
  - Location: Conference Room A
  - Energy: medium
  - Waiting for: quarterly-metrics-report

## Active Tasks

- [/] Implement user profile page @development @frontend ^2025-01-15 !2025-01-23 ~high *2d +sarah +bob &product-owner #user-features
  - Using the new design system components
  - Support dark/light mode switching
  - Add avatar upload functionality
  - URL: https://figma.com/file/user-profile-design
  - Progress: 60%
  - Blocks: #deployment-235
  - Status: in_progress

- [ ] Fix authentication bug @urgent @backend @security ^2025-01-16 !2025-01-22 ~critical *2d +alice &product-owner #security
  - Users occasionally getting logged out during session
  - Check token refresh mechanism
  - Add additional logging for debugging
  - Time estimate: 12h
  - Energy: high
  - Context: @deep-work

- [ ] Update API documentation @documentation @api ^2025-01-18 !2025-01-26 ~low *4h +john #maintenance
  - Update all endpoints to match latest changes
  - Add examples for new authentication flow
  - Generate Swagger spec for external consumers
  - Defer until: 2025-01-20
  - Files: [/docs/api/auth.md, /docs/api/users.md]

- [ ] Research performance improvements @research @performance ^2025-01-17 ~medium *1d +bob #optimization
  - Investigate database query optimization
  - Profile frontend rendering bottlenecks
  - Benchmark current vs potential solutions
  - Location: @home
  - Energy: high
  - URL: https://confluence.company.com/performance-targets

## Completed Tasks

- [x] Attend standup meeting @meeting @video-call ^2025-01-15 !2025-01-15 ~medium *15m +team &scrum-master %daily #recurring
  - Discussed authentication bug blocking frontend team
  - Updated on API documentation progress
  - Assigned performance research to Bob
  - Completed: 2025-01-15T09:15:00Z
  - Time spent: 18m
  - Next occurrence: 2025-01-16T09:00:00Z

- [x] Setup monitoring alerts @devops @monitoring ^2025-01-10 !2025-01-15 ~high *4h +john &tech-lead #infrastructure
  - Configured CPU/memory thresholds
  - Added Slack notification channel
  - Created escalation policy for critical alerts
  - Completed: 2025-01-14T16:20:00Z
  - Completed by: john
  - Time spent: 3.5h
```

## Enhanced CLI Interface Design

**Core Commands**:
- `todo add "Fix login bug" @urgent #work ^tomorrow !next-week ~high *2d +john &manager` - Full natural language entry
- `todo add "Daily standup" @meeting %daily ~medium *15m +team` - Recurring task
- `todo pin 1` - Pin/unpin a task
- `todo list` - Show all todos (pinned tasks always at top)
- `todo list --overdue` - Show overdue tasks
- `todo list --upcoming [days]` - Show tasks due within N days (default: 7)
- `todo list --pinned` - Show only pinned tasks
- `todo list --recurring` - Show recurring task templates
- `todo list #work @urgent ~high` - Filter by project, tags, priority
- `todo done 1` - Mark todo as complete (creates next instance if recurring)
- `todo skip 1` - Skip one instance of recurring task
- `todo projects` - List all projects
- `todo export [project]` - Export to stdout/file

**Quick Add Mode**:
- `todo` (no args) - Enter interactive quick-add mode
- Shows dashboard: pinned tasks (star), overdue (red), today (yellow), upcoming (blue)
- Prompts for new task entry with smart parsing

**Enhanced Natural Language Syntax**:
- `#project` - Project assignment
- `@tag` - Tags
- `^date` - Start date ("^tomorrow", "^2025-01-20", "^next-monday")
- `!date` - Due date ("!friday", "!2025-01-25", "!in-2-weeks")
- `~priority` - Priority (critical, high, medium, low)
- `*effort` - Level of effort ("*2d", "*4h", "*30m", "*large", "*small")
- `+assignee` - Assignees ("+ john", "+alice,bob")
- `&stakeholder` - Stakeholders ("&manager", "&product-owner")
- `%recurrence` - Recurring pattern ("% daily", "%weekly:friday", "%monthly:15", "%yearly")
- `[PIN]` or `[P]` - Pin the task

**Recurrence Patterns**:
- `%daily` - Every day
- `%weekly` or `%weekly:monday` - Weekly on specific day
- `%monthly` or `%monthly:15` - Monthly on specific date
- `%yearly` or `%yearly:jan-15` - Yearly on specific date
- `%workdays` - Monday through Friday
- `%custom:3d` - Every 3 days (custom intervals)

## Enhanced File Structure
```
todo_cli/
├── src/
│   ├── __init__.py
│   ├── cli.py          # Click-based CLI interface
│   ├── todo.py         # Enhanced Todo class with all fields
│   ├── project.py      # Project management
│   ├── parser.py       # Enhanced natural language parsing
│   ├── storage.py      # Markdown file operations
│   ├── config.py       # Configuration management
│   ├── filters.py      # Date-based and priority filtering
│   ├── dashboard.py    # Quick-add mode and dashboard views
│   ├── dates.py        # Date parsing utilities
│   ├── recurring.py    # Recurring task management
│   └── pins.py         # Pinned task handling
├── tests/
├── README.md
├── pyproject.toml
└── requirements.txt
```

## Technical Stack
- **CLI Framework**: Click (clean, extensible)
- **Config Management**: PyYAML
- **Markdown Processing**: python-frontmatter
- **Date Parsing**: python-dateutil, parsedatetime
- **Rich Display**: rich (colors, tables, progress bars)
- **Recurring Logic**: python-dateutil.rrule for complex recurrence
- **Testing**: pytest

## Enhanced Todo Model

### Core Todo Data Structure
```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"

@dataclass
class Todo:
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
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
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
        """Post-initialization validation and setup"""
        if self.completed and not self.completed_date:
            self.completed_date = datetime.now()
        
        if self.status == TodoStatus.COMPLETED:
            self.completed = True
            
        # Update modified timestamp
        self.modified = datetime.now()

@dataclass
class Project:
    """Enhanced project model"""
    name: str
    display_name: str = ""
    description: str = ""
    created: datetime = field(default_factory=datetime.now)
    modified: datetime = field(default_factory=datetime.now)
    
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
    
    # Custom fields
    custom_fields: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RecurrenceRule:
    """Detailed recurrence configuration"""
    pattern: str  # "daily", "weekly", "monthly", "yearly", "custom"
    interval: int = 1  # Every N periods
    days_of_week: List[int] = field(default_factory=list)  # 0=Monday, 6=Sunday
    day_of_month: Optional[int] = None  # For monthly recurrence
    month_of_year: Optional[int] = None  # For yearly recurrence
    end_date: Optional[datetime] = None  # When to stop recurring
    max_occurrences: Optional[int] = None  # Maximum number of instances
    
    # Advanced options
    skip_weekends: bool = False
    skip_holidays: bool = False
    advance_if_weekend: bool = False  # Move to next business day if falls on weekend
    
    def next_occurrence(self, from_date: datetime) -> Optional[datetime]:
        """Calculate next occurrence from given date"""
        # Implementation would use dateutil.rrule
        pass
```

### Data Serialization Models

```python
@dataclass
class TodoMarkdownFormat:
    """Markdown representation of a todo with frontmatter"""
    
    @staticmethod
    def to_markdown(todo: Todo) -> str:
        """Convert Todo to markdown format with YAML frontmatter"""
        # Checkbox format based on status
        checkbox_map = {
            TodoStatus.PENDING: "- [ ]",
            TodoStatus.IN_PROGRESS: "- [/]",
            TodoStatus.COMPLETED: "- [x]",
            TodoStatus.CANCELLED: "- [-]",
            TodoStatus.BLOCKED: "- [!]"
        }
        
        checkbox = checkbox_map.get(todo.status, "- [ ]")
        
        # Build task line with all metadata
        task_line = f"{checkbox} {todo.text}"
        
        # Add inline metadata
        if todo.tags:
            task_line += f" {' '.join(['@' + tag for tag in todo.tags])}"
        
        if todo.context:
            task_line += f" {' '.join(['@' + ctx for ctx in todo.context])}"
        
        if todo.start_date:
            task_line += f" ^{todo.start_date.strftime('%Y-%m-%d')}"
        
        if todo.due_date:
            task_line += f" !{todo.due_date.strftime('%Y-%m-%d')}"
        
        if todo.priority != Priority.MEDIUM:
            task_line += f" ~{todo.priority.value}"
        
        if todo.effort:
            task_line += f" *{todo.effort}"
        
        if todo.assignees:
            task_line += f" {' '.join(['+' + assignee for assignee in todo.assignees])}"
        
        if todo.stakeholders:
            task_line += f" {' '.join(['&' + stakeholder for stakeholder in todo.stakeholders])}"
        
        if todo.recurrence:
            task_line += f" %{todo.recurrence}"
        
        if todo.pinned:
            task_line += " [PINNED]"
        
        if todo.location:
            task_line += f" @{todo.location}"
        
        if todo.waiting_for:
            task_line += f" (waiting: {', '.join(todo.waiting_for)})"
        
        # Add ID as hidden comment
        task_line += f" <!-- id:{todo.id} -->"
        
        return task_line
    
    @staticmethod
    def from_markdown(line: str, project: str = "inbox") -> Todo:
        """Parse markdown line back to Todo object"""
        # Implementation would parse the markdown syntax
        # This is a complex parser that would handle all the @ # ^ ! ~ * + & % syntax
        pass

@dataclass
class ProjectMarkdownFormat:
    """Project file format with YAML frontmatter"""
    
    @staticmethod
    def to_markdown(project: Project, todos: List[Todo]) -> str:
        """Convert project and todos to markdown file"""
        frontmatter = {
            "name": project.name,
            "display_name": project.display_name,
            "description": project.description,
            "created": project.created.isoformat(),
            "modified": project.modified.isoformat(),
            "tags": project.tags,
            "color": project.color,
            "icon": project.icon,
            "active": project.active,
            "archived": project.archived,
            "default_priority": project.default_priority.value,
            "goal": project.goal,
            "deadline": project.deadline.isoformat() if project.deadline else None,
            "progress": project.progress,
            "custom_fields": project.custom_fields
        }
        
        yaml_front = "---\n"
        for key, value in frontmatter.items():
            if value is not None:
                yaml_front += f"{key}: {repr(value)}\n"
        yaml_front += "---\n\n"
        
        # Project title and description
        content = f"# {project.display_name or project.name}\n\n"
        if project.description:
            content += f"{project.description}\n\n"
        
        # Group todos by status and priority
        pinned_todos = [t for t in todos if t.pinned and not t.completed]
        active_todos = [t for t in todos if not t.completed and not t.pinned]
        completed_todos = [t for t in todos if t.completed]
        
        if pinned_todos:
            content += "## Pinned Tasks\n\n"
            for todo in pinned_todos:
                content += TodoMarkdownFormat.to_markdown(todo) + "\n"
            content += "\n"
        
        if active_todos:
            content += "## Active Tasks\n\n"
            # Sort by priority then due date
            priority_order = {Priority.CRITICAL: 0, Priority.HIGH: 1, Priority.MEDIUM: 2, Priority.LOW: 3}
            active_todos.sort(key=lambda t: (priority_order.get(t.priority, 2), t.due_date or datetime.max))
            
            for todo in active_todos:
                content += TodoMarkdownFormat.to_markdown(todo) + "\n"
            content += "\n"
        
        if completed_todos:
            content += "## Completed Tasks\n\n"
            for todo in sorted(completed_todos, key=lambda t: t.completed_date or datetime.min, reverse=True):
                content += TodoMarkdownFormat.to_markdown(todo) + "\n"
        
        return yaml_front + content

@dataclass 
class ConfigModel:
    """Global configuration model"""
    
    # Default settings
    default_project: str = "inbox"
    default_priority: Priority = Priority.MEDIUM
    default_view: str = "dashboard"  # dashboard, list, pinned, etc.
    
    # Display preferences
    show_completed: bool = True
    show_archived: bool = False
    max_completed_days: int = 30  # Only show completed tasks from last N days
    
    # Date preferences
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M"
    first_day_of_week: int = 0  # 0=Monday, 6=Sunday
    
    # Behavior settings
    auto_archive_completed: bool = False
    auto_archive_days: int = 30
    confirm_deletion: bool = True
    
    # Integration settings
    sync_enabled: bool = False
    sync_provider: Optional[str] = None  # "github", "dropbox", etc.
    sync_config: Dict[str, Any] = field(default_factory=dict)
    
    # Custom fields and extensions
    custom_contexts: List[str] = field(default_factory=list)  # Custom @contexts
    custom_priorities: List[str] = field(default_factory=list)  # Additional priorities
    plugins: List[str] = field(default_factory=list)  # Plugin names
    
    # File paths
    data_dir: str = "~/.todo"
    backup_dir: str = "~/.todo/backups"
    
    def to_yaml(self) -> str:
        """Serialize config to YAML"""
        import yaml
        return yaml.dump(self.__dict__, default_flow_style=False)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'ConfigModel':
        """Deserialize config from YAML"""
        import yaml
        data = yaml.safe_load(yaml_str)
        return cls(**data)
```

### Enhanced Storage Schema

```python
@dataclass
class StorageSchema:
    """Database-like schema for file-based storage"""
    
    # File structure
    # ~/.todo/
    # ├── config.yaml                 # Global configuration
    # ├── projects/
    # │   ├── inbox.md                # Default inbox project
    # │   ├── work.md                 # Work project
    # │   └── personal.md             # Personal project
    # ├── templates/
    # │   ├── recurring.yaml          # Recurring task templates
    # │   └── project_templates.yaml  # Project templates
    # ├── backups/
    # │   └── YYYY-MM-DD/            # Daily backups
    # ├── archive/
    # │   └── YYYY/                  # Archived projects by year
    # └── logs/
    #     ├── changes.log            # Change history
    #     └── sync.log               # Sync operations
    
    @staticmethod
    def get_project_path(data_dir: str, project_name: str) -> str:
        """Get file path for a project"""
        return f"{data_dir}/projects/{project_name}.md"
    
    @staticmethod
    def get_config_path(data_dir: str) -> str:
        """Get config file path"""
        return f"{data_dir}/config.yaml"
    
    @staticmethod
    def get_backup_path(data_dir: str, date: datetime) -> str:
        """Get backup directory for a date"""
        return f"{data_dir}/backups/{date.strftime('%Y-%m-%d')}"
    
    @staticmethod
    def ensure_directories(data_dir: str):
        """Create necessary directory structure"""
        import os
        os.makedirs(f"{data_dir}/projects", exist_ok=True)
        os.makedirs(f"{data_dir}/templates", exist_ok=True)
        os.makedirs(f"{data_dir}/backups", exist_ok=True)
        os.makedirs(f"{data_dir}/archive", exist_ok=True)
        os.makedirs(f"{data_dir}/logs", exist_ok=True)
```

## Implementation Phases
1. **Enhanced Storage** - Extended markdown format with pinning and recurrence
2. **Core CLI** - Basic add, list, complete with new syntax
3. **Smart Parsing** - Natural language processing for all fields including recurrence
4. **Pinning System** - Pin/unpin functionality and display priority
5. **Recurring Engine** - Recurrence pattern parsing and instance generation
6. **Dashboard Mode** - Interactive quick-add with pinned tasks prominently displayed
7. **Advanced Filtering** - Date-based queries, priority sorting, recurrence management
8. **Export & Polish** - Multiple export formats, UX refinements

## Dashboard Views
- **Default View**: Pinned tasks (⭐), Today's tasks, overdue (red), upcoming this week
- **Pinned View**: All pinned tasks with full details
- **Overdue Filter**: All past-due tasks sorted by due date
- **Upcoming Filter**: Tasks due within specified timeframe
- **Recurring View**: Active recurring templates and next instances
- **Priority View**: High/critical tasks across all projects
- **Assignee View**: Tasks by person
- **Effort Planning**: Tasks grouped by effort estimates

## Recurring Task Logic
- **Template Storage**: Recurring tasks stored as templates in special section
- **Instance Generation**: New instances created when previous completed or at start date
- **Skip Logic**: Allow skipping instances without affecting future occurrences
- **Completion Handling**: Completing a recurring task immediately generates next instance
- **Editing**: Changes to recurring template affect future instances only