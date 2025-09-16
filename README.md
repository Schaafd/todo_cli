# Todo CLI ✅

> A powerful, feature-rich command-line todo application with advanced task management capabilities

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Phase 3 Complete](https://img.shields.io/badge/phase-3%20complete-green.svg)](./PLAN.md)
[![Tests Passing](https://img.shields.io/badge/tests-32%20passing-green.svg)](#testing)

## 🚀 Features (Phase 3 Complete)

### 🧠 **NEW: Smart Natural Language Parsing**
- **One-Line Task Creation**: Rich metadata extraction from natural language
- **Smart Date Parsing**: "tomorrow", "next Friday", "end of month", ISO dates
- **Intelligent Metadata Detection**: Auto-categorizes @contexts, #projects, ~priorities, +people
- **Error Prevention**: Smart suggestions for typos and invalid input
- **Advanced Syntax**: Time estimates, energy levels, effort sizing, waiting dependencies

### 📋 Enhanced Task Management
- **Rich Data Model**: 40+ fields including priorities, scheduling, collaboration, progress tracking
- **Multiple Status Types**: Pending, In Progress, Completed, Cancelled, Blocked
- **Priority Levels**: Critical, High, Medium, Low with color-coded display
- **Time Tracking**: Estimates, actual time spent, progress percentages
- **Collaboration**: Assignees, stakeholders, delegation, "waiting for" tracking

### 🗂️ Project Organization
- **Project Management**: Team members, deadlines, goals, progress tracking
- **Auto Statistics**: Completion rates, average completion time, activity tracking
- **Hierarchical Structure**: Parent/child projects and subtasks
- **Custom Fields**: Flexible metadata for any use case

### 💾 Smart Storage
- **Human-Readable Format**: Markdown files with YAML frontmatter
- **Rich Inline Metadata**: Natural syntax (`@tags`, `!due-dates`, `~priority`, `+assignees`)
- **Version Control Friendly**: Plain text format works great with git
- **Organized Structure**: `~/.todo/projects/` with individual project files

### 🎯 **NEW: Enhanced Query Engine & AI Recommendations**
- **Advanced Search**: Complex queries with logical operators (AND, OR, NOT)
- **Smart Recommendations**: AI-powered task suggestions based on context and patterns
- **Saved Queries**: Persistent search shortcuts with @query syntax
- **Bulk Operations**: Multi-todo operations (complete, pin, priority, project moves)
- **Pattern Learning**: Analyzes your work habits for intelligent suggestions

### 📊 Professional CLI Interface
- **Rich UI**: Beautiful colored output with emojis and status indicators
- **Smart Dashboard**: Overview of pinned, overdue, and upcoming tasks
- **Organized Views**: Today, Tomorrow, Upcoming, and Backlog task organization
- **Powerful Filtering**: By project, status, priority, assignee, due date
- **Intuitive Commands**: Natural command structure with helpful options

## 📦 Installation

### Prerequisites
- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) for dependency management

### Install from Source
```bash
# Clone the repository
git clone https://github.com/Schaafd/todo_cli.git
cd todo_cli

# Install with uv
uv sync

# The 'todo' command is now available
uv run todo --help
```

### Development Installation
```bash
# Clone and install for development
git clone https://github.com/Schaafd/todo_cli.git
cd todo_cli
uv sync --all-extras

# Run tests
uv run python -m pytest
```

## 🎯 Quick Start

### 🌟 **NEW: Natural Language Task Creation**
```bash
# Simple task
todo add "Review pull request"

# Rich task with smart parsing - all metadata extracted automatically!
todo add "Review security PR #webapp @urgent @work ~high +reviewer due tomorrow est:2h [PIN]"

# Meeting with stakeholders and effort estimation
todo add "Team standup #project-alpha @meetings ~medium +team &stakeholders due friday 2pm *large"

# Personal task with energy and dependencies
todo add "Call doctor @phone ~high energy:low est:15m (waiting: insurance approval)"

# Quick pinned reminder
todo add "Submit expense report due end of week [P]"
```

### 🎨 Natural Language Syntax Guide
- **Projects**: `#project-name` → Auto-assigns to project
- **Tags**: `@urgent`, `@meeting` → Regular tags
- **Contexts**: `@home`, `@work`, `@phone` → Auto-categorized contexts
- **Priority**: `~critical`, `~high`, `~medium`, `~low`
- **Assignees**: `+john`, `+team` → People assigned
- **Stakeholders**: `&manager`, `&client` → People to keep informed
- **Due Dates**: `due tomorrow`, `due friday 2pm`, `due 2025-12-25`
- **Time Estimates**: `est:2h`, `est:30m`, `est:45min`
- **Energy Level**: `energy:high`, `energy:low`
- **Effort Size**: `*large`, `*small`, `*medium`
- **Pinned**: `[PIN]`, `[PINNED]`, `[P]`
- **Waiting For**: `(waiting: approval, review)`
- **Recurrence**: `%weekly`, `%daily`
- **URLs**: Automatically detected and extracted

### Basic Commands
```bash
# Show dashboard (default)
todo

# List and filter tasks
todo list
todo list --overdue
todo list --priority high
todo list --project work

# Complete and manage tasks
todo done 1
todo pin 2
todo projects

# Get smart suggestions for typos
todo add "Bug fix ~invalid" --dry-run  # Shows helpful error message

# Preview without saving
todo add "Complex task #proj @tag ~high" --dry-run
```

### 🔍 **Advanced Search & Query Commands**
```bash
# Advanced search with complex logic
todo search "priority:high,critical AND is:active"
todo search "tag:urgent OR tag:important"
todo search "(project:webapp OR project:api) status:pending"

# Smart recommendations based on context
todo recommend --energy high --context work --time 45
todo recommend --explain  # Show detailed explanations

# Save and use query shortcuts
todo search "is:overdue OR due:today" --save="urgent-tasks"
todo search "@urgent-tasks"  # Use saved query

# Bulk operations
todo bulk complete 1 2 3       # Mark multiple as complete
todo bulk priority 5 7 9 --priority high  # Set priority
todo bulk project 4 5 --project work      # Move to project

# Query management
todo queries --list             # List saved queries
todo queries --delete "old-query"  # Delete saved query
```

### 🔄 **NEW: Recurring Tasks & Smart Scheduling**
```bash
# Create recurring tasks with natural language patterns
todo recurring "Daily standup @meetings ~high" "daily"
todo recurring "Review monthly reports @review" "monthly" --project work
todo recurring "Security patch review @security" "every 2 weeks" --project maintenance

# Preview recurring tasks before creating
todo recurring "Quarterly planning @planning" "every 3 months" --preview

# Set limits and end dates
todo recurring "Pay rent +landlord" "monthly" --max-occurrences 12
todo recurring "Doctor checkup @health" "every 6 months" --end-date 2026-12-31

# Manage recurring tasks
todo recurring-list                    # List all recurring tasks
todo recurring-generate --days 7       # Generate tasks for next 7 days
todo recurring-generate --dry-run       # Preview without creating

# Control recurring tasks
todo recurring-pause recurring_id       # Pause a recurring task
todo recurring-resume recurring_id      # Resume a paused recurring task
todo recurring-delete recurring_id      # Delete a recurring task
```

### 📤 **NEW: Export & Backup System**
```bash
# Export to various formats
todo export json                       # Export all tasks to JSON
todo export csv --project work         # Export work project to CSV
todo export html --no-completed        # Export pending tasks to HTML
todo export pdf --project personal     # Export to professional PDF report

# Advanced export options
todo export markdown --group-by-project  # Group by project in Markdown
todo export yaml --include-metadata     # Include extended metadata
todo export ical --no-completed         # Export to calendar format

# Custom output and automation
todo export json -o ~/backups/todos.json
todo export html --open-after           # Open exported file automatically
todo export csv --no-completed -o weekly_report.csv

# Supported formats: json, csv, tsv, markdown, html, pdf, ical, yaml
```

## 📊 Dashboard View

The dashboard provides an at-a-glance view of your tasks with rich formatting:

```
📋 Todo Dashboard

⭐ Pinned Tasks
  1 ⭐ ⏳ Review security PR @urgent !2025-09-15 +reviewer
  Context: @work
  Estimate: 2h 0m
  
  3 🔄 Team standup @meetings !2025-09-19 +team
  Effort: *large

🔥 Overdue Tasks
  2 ⏳ Update documentation @docs !2025-09-14 ~medium

📅 Due Today
  4 ⏳ Call doctor
  Context: @phone
  Energy: low
  Estimate: 15m
  Waiting for: insurance approval

Total: 12 | Active: 8 | Completed: 4
```

## 🗃️ File Structure

Todo CLI organizes your data in a clean, version-control-friendly structure:

```
~/.todo/
├── config.yaml              # Your preferences
├── projects/
│   ├── inbox.md             # Default project
│   ├── work.md              # Work-related tasks
│   └── personal.md          # Personal tasks
└── backups/                 # Automatic backups
    └── 2025-09-14/
```

### Example Project File (`work.md`)
```markdown
---
name: "work"
display_name: "Work Projects"
team_members: ["john", "sarah", "alice"]
stats:
  total_tasks: 15
  completed_tasks: 8
  overdue_tasks: 2
---

# Work Projects

## Pinned Tasks

- [ ] Review pull request #123 @urgent @code-review ^2025-09-15 !2025-09-20 ~high +john +sarah [PINNED] <!-- id:1 -->

## Active Tasks

- [/] Fix authentication bug @security @urgent ^2025-09-14 !2025-09-18 ~critical +alice <!-- id:2 -->
- [ ] Update API documentation @docs ^2025-09-16 !2025-09-25 ~medium +john <!-- id:3 -->

## Completed Tasks

- [x] Setup monitoring alerts @devops ~high +john <!-- id:4 -->
```

## ⚙️ Configuration

Customize Todo CLI behavior with `~/.todo/config.yaml`:

```yaml
# Default settings
default_project: "inbox"
default_priority: "medium"
default_view: "dashboard"

# Display preferences
show_completed: true
max_completed_days: 30
no_color: false
use_emoji: true

# Behavior
auto_archive_completed: false
confirm_deletion: true

# Custom contexts and priorities
custom_contexts: ["home", "office", "errands"]
custom_priorities: ["someday"]
```

## 🧪 Testing

Todo CLI includes a comprehensive test suite:

```bash
# Run all tests
uv run python -m pytest

# Run with coverage
uv run python -m pytest --cov=src/todo_cli --cov-report=term-missing

# Run specific test file
uv run python -m pytest tests/test_todo.py -v
```

**Test Coverage**: 43 tests covering core functionality and natural language parsing with 100% pass rate.

## 🏗️ Architecture

Todo CLI is built with a clean, extensible architecture:

```
src/todo_cli/
├── __init__.py         # Package exports
├── todo.py             # Todo model (40+ fields)
├── project.py          # Project management
├── config.py           # Configuration system
├── storage.py          # Markdown + YAML storage
├── parser.py           # Natural language parsing engine
├── query_engine.py     # Advanced search and filtering engine
├── recommendations.py  # AI-powered task recommendation system
├── recurring.py        # Smart recurring task system with pattern recognition
├── theme.py            # UI theming and formatting
└── cli.py              # Click-based CLI interface
```

### Key Design Principles
- **Type Safety**: Full type hints throughout
- **Separation of Concerns**: Clean module boundaries
- **Extensibility**: Ready for advanced features
- **Data Integrity**: Robust validation and error handling

## 📅 Development Roadmap

### ✅ Phase 1: Enhanced Storage & Core CLI (Complete)
- [x] Rich data models with 40+ fields
- [x] Markdown + YAML storage system
- [x] Professional CLI with Rich UI
- [x] Project management
- [x] Basic filtering and search
- [x] Configuration system
- [x] Comprehensive test suite

### ✅ Phase 2: Smart Parsing & Natural Language (Complete)
- [x] **Advanced Natural Language Parsing** - Extract rich metadata from plain text
- [x] **Smart Date Parsing** - "tomorrow", "next Friday", "end of month", ISO dates
- [x] **Intelligent Metadata Detection** - Auto-categorizes @contexts, #projects, ~priorities
- [x] **Error Prevention & Suggestions** - Smart typo detection and helpful corrections
- [x] **Comprehensive Syntax Support** - Time estimates, energy levels, waiting dependencies
- [x] **32 Parser Tests** - Full coverage of parsing scenarios and edge cases
- [x] **Rich Preview System** - See exactly what will be created before saving

### ✅ Phase 3: Enhanced Query Engine (Complete)
- [x] **Advanced Search & Filtering** - Comprehensive query syntax with logical operators
- [x] **Smart Task Recommendations** - AI-powered recommendations based on patterns and context
- [x] **Query Shortcuts & Saved Searches** - Persistent saved queries with @shortcut syntax
- [x] **Advanced Sorting Options** - Multi-field sorting with contextual defaults
- [x] **Bulk Operations** - Multi-todo operations with confirmation prompts

### ✅ Phase 4: Smart Integration Features (In Progress)
- [x] **Recurring tasks with smart scheduling** - Full CLI integration with natural language patterns
- [x] **Export functionality** - Multiple formats (JSON, CSV, Markdown, HTML, PDF, ICAL, YAML)
- [ ] Notification system
- [ ] Calendar integration
- [ ] Sync capabilities

### 🌟 Phase 5: Advanced Reporting & Analytics (Planned)
- [ ] Productivity insights
- [ ] Time tracking reports
- [ ] Project analytics
- [ ] Custom dashboards
- [ ] Plugin system

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup
```bash
git clone https://github.com/Schaafd/todo_cli.git
cd todo_cli
uv sync --all-extras

# Run tests
uv run python -m pytest

# Run linting
uv run black src/ tests/
uv run flake8 src/ tests/
```

### Contribution Guidelines
- Follow the existing code style (Black, flake8)
- Add tests for new features
- Update documentation
- Use conventional commit messages
- Target the appropriate phase branch

### Branch Structure
- `main` - Latest stable release
- `feat/phase-N-*` - Feature branches for each phase
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI framework
- [Rich](https://rich.readthedocs.io/) for beautiful terminal output
- [uv](https://github.com/astral-sh/uv) for fast Python package management
- [PyYAML](https://pyyaml.org/) for configuration management
- [python-frontmatter](https://python-frontmatter.readthedocs.io/) for markdown processing
- [parsedatetime](https://github.com/bear/parsedatetime) for natural language date parsing
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) for intelligent typo detection

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Schaafd/todo_cli/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Schaafd/todo_cli/discussions)
- **Documentation**: [PLAN.md](./PLAN.md) for detailed technical specifications

---

**Phase 4 In Progress** 🚀 | Built with ❤️ for productivity enthusiasts

> **NEW**: Recurring Tasks with Smart Scheduling & Multi-Format Export!
> Try: `todo recurring "Daily standup @meetings" "daily" --preview` or `todo export html --open-after`
