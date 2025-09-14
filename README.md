# Todo CLI ✅

> A powerful, feature-rich command-line todo application with advanced task management capabilities

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Phase 1 Complete](https://img.shields.io/badge/phase-1%20complete-green.svg)](./PLAN.md)
[![Tests Passing](https://img.shields.io/badge/tests-passing-green.svg)](#testing)

## 🚀 Features (Phase 1 Complete)

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

### 🎨 Professional CLI Interface
- **Rich UI**: Beautiful colored output with emojis and status indicators
- **Smart Dashboard**: Overview of pinned, overdue, and upcoming tasks
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

### Basic Usage
```bash
# Show dashboard (default command)
todo

# Add a task
todo add "Review pull request #123"

# Add a task with metadata
todo add "Fix authentication bug" --priority high --due 2025-09-20 -t urgent -t backend

# List all tasks
todo list

# List tasks with filters
todo list --overdue
todo list --priority high
todo list --project work

# Complete a task
todo done 1

# Pin/unpin important tasks
todo pin 2

# Show all projects
todo projects
```

### Advanced Task Syntax
```bash
# Rich metadata in task creation
todo add "Review PR" --priority high --due 2025-09-20 --tags code-review urgent --assignee john --pin

# Filter and search
todo list --status in_progress
todo list --pinned
todo list --project work --priority critical
```

## 📊 Dashboard View

The dashboard provides an at-a-glance view of your tasks:

```
📋 Todo Dashboard

⭐ Pinned Tasks
  1 ⏳ Review pull request #123 @urgent !2025-09-20 ~high +john
  3 🔄 Fix authentication bug @backend @security ~critical

🔥 Overdue Tasks
  2 ⏳ Update documentation @docs !2025-09-15 ~medium

📅 Due Today
  4 ⏳ Team standup meeting @meeting ~medium +team

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

**Test Coverage**: 11 tests covering core functionality with 100% pass rate.

## 🏗️ Architecture

Todo CLI is built with a clean, extensible architecture:

```
src/todo_cli/
├── __init__.py         # Package exports
├── todo.py             # Todo model (40+ fields)
├── project.py          # Project management
├── config.py           # Configuration system
├── storage.py          # Markdown + YAML storage
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

### 🔄 Phase 2: Smart Parsing & Natural Language (Next)
- [ ] Enhanced natural language parsing
- [ ] Smart date parsing ("tomorrow", "next Friday")
- [ ] Improved task syntax parsing
- [ ] Better error messages and suggestions

### 🔮 Phase 3: Advanced Features (Planned)
- [ ] Recurring tasks
- [ ] Advanced dashboard views
- [ ] Export functionality
- [ ] Plugin system
- [ ] Sync capabilities

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

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Schaafd/todo_cli/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Schaafd/todo_cli/discussions)
- **Documentation**: [PLAN.md](./PLAN.md) for detailed technical specifications

---

**Phase 1 Complete** ✨ | Built with ❤️ for productivity enthusiasts