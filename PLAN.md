# Enhanced Todo CLI Application Plan (Final)

## Core Architecture

**Storage Format**: Markdown files organized by project, with frontmatter for metadata
- `~/.todo/projects/[project-name].md` - Individual project files
- `~/.todo/config.yaml` - Global configuration
- YAML frontmatter in each MD file for project metadata

**Enhanced Data Structure**:
```yaml
# Project frontmatter
---
name: "work"
created: "2025-01-15"
tags: ["urgent", "meeting", "code-review"]
---

# Work Tasks
- [ ] Review pull request #123 @urgent @code-review ^2025-01-20 !2025-01-25 ~high *3d +john +sarah &manager [PINNED]
- [x] Attend standup meeting @meeting ^2025-01-15 !2025-01-15 ~medium *15m +team &scrum-master %daily
- [ ] Fix authentication bug @urgent ^2025-01-16 !2025-01-22 ~critical *2d +alice &product-owner
- [ ] Weekly team sync @meeting ~medium *1h +team &manager %weekly:friday [PINNED]
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
```python
@dataclass
class Todo:
    id: int
    text: str
    completed: bool = False
    project: str = "inbox"
    tags: List[str] = field(default_factory=list)
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    priority: str = "medium"  # critical, high, medium, low
    effort: str = ""  # "2d", "4h", "large", etc.
    assignees: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)
    created: datetime = field(default_factory=datetime.now)
    completed_date: Optional[datetime] = None
    pinned: bool = False
    recurrence: Optional[str] = None  # "daily", "weekly:friday", etc.
    parent_recurring_id: Optional[int] = None  # Links to recurring template
    next_due: Optional[datetime] = None  # For recurring tasks
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

Would you like to proceed with this comprehensive plan?