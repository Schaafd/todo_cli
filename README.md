# Todo CLI ✅

> A powerful, feature-rich command-line todo application with advanced task management capabilities

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Phase 6 Complete](https://img.shields.io/badge/phase-6%20complete-brightgreen.svg)](./docs/PHASE_6_APP_SYNC_PLAN.md)
[![Tests Passing](https://img.shields.io/badge/tests-173%20passing-green.svg)](#testing)
[![PWA Ready](https://img.shields.io/badge/PWA-ready-blue.svg)](#progressive-web-app-pwa)

## 🚀 Features

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

### 🔄 **NEW: Multi-App Synchronization (Phase 6)**
- **Bidirectional Sync**: Keep todos in sync with external apps like Todoist and Apple Reminders
- **Multiple Provider Support**: Todoist (API-based) and Apple Reminders (native macOS integration)
- **Conflict Resolution**: Multiple strategies (newest wins, manual, local/remote preference)
- **Secure Credential Storage**: System keyring integration with fallback options
- **Project Mapping**: Map local projects to external app projects/lists
- **Incremental Updates**: Efficient sync using change detection and timestamps
- **Extensible Architecture**: Adapter pattern ready for TickTick, Notion, Microsoft Todo, and more

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

### 🎨 **NEW: Advanced Theming System**
- **14 Built-in Themes**: From professional light themes to dramatic dark experiences
- **Background Colors**: Rich panel backgrounds with proper color contrast
- **Themed Borders**: Distinct styling for different dashboard sections
- **Light & Dark Options**: Themes optimized for different terminal backgrounds
- **Accessibility Features**: High contrast variants and colorblind-safe palettes
- **Live Theme Switching**: Change themes instantly without restarting
- **Theme Validation**: Built-in contrast checking and accessibility validation

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

# Freeform date phrases (no explicit 'due' needed)
todo add "Pay rent by Monday"
todo add "Pick up order on 9/21"
todo add "Write recap for tomorrow"
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

### 🔔 **NEW: Smart Notification System**
```bash
# Check notification system status
todo notify status                     # Show availability and settings

# Configure notifications
todo notify config --enabled --desktop  # Enable desktop notifications
todo notify config --due-soon-hours 12  # Notify 12 hours before due
todo notify config --overdue-hours 6    # Remind every 6 hours for overdue
todo notify config --quiet-start 22 --quiet-end 8  # Set quiet hours

# Manual notification management
todo notify test                       # Send test notification
todo notify check                      # Check for due/overdue tasks now
todo notify history                    # View notification history
todo notify history --type overdue     # Filter by notification type

# Email notifications (optional)
todo notify config --email --email-address user@example.com
todo notify config --smtp-server smtp.gmail.com --smtp-username user@example.com

# Notification types: due_soon, overdue, recurring_generated, daily_summary
```

### 🔄 **NEW: Multi-App Synchronization Commands**
```bash
# List available providers and their status
todo app-sync list                    # Show all providers (configured vs available)

# Setup synchronization with external providers
todo app-sync setup todoist           # Interactive setup with Todoist
todo app-sync setup apple_reminders   # Interactive setup with Apple Reminders (macOS only)
todo app-sync setup todoist --api-token YOUR_TOKEN  # Non-interactive setup
todo app-sync setup --interactive      # Choose from available providers

# Perform synchronization
todo app-sync sync todoist            # Sync with Todoist
todo app-sync sync apple_reminders    # Sync with Apple Reminders
todo app-sync sync --all              # Sync with all configured providers
todo app-sync sync --dry-run          # Preview sync without making changes

# Check synchronization status
todo app-sync status                  # Show status of all providers
todo app-sync status todoist          # Show status for specific provider

# Manage provider configurations
todo app-sync enable todoist          # Enable auto-sync for provider
todo app-sync disable todoist         # Disable auto-sync for provider

# Project and label mapping
todo app-sync project-map todoist     # Interactive project mapping setup
todo app-sync project-map todoist --local work --remote "Work Projects"
todo app-sync project-map apple_reminders --local personal --remote "Personal"

# Handle sync conflicts
todo app-sync conflicts               # List unresolved conflicts
todo app-sync conflicts --resolve     # Interactive conflict resolution
todo app-sync conflicts --provider todoist  # Filter by provider

# Supported providers:
# ✅ todoist        - Full bidirectional sync with projects and labels
# ✅ apple_reminders - Full bidirectional sync with lists (macOS native integration)
# 🚧 ticktick      - Coming soon (cross-platform with calendar sync)
# 🚧 notion        - Coming soon (database integration)
# 🚧 microsoft_todo - Coming soon (Office 365 integration)
# 🚧 google_tasks   - Coming soon (Google Workspace integration)
```

### 🎨 **NEW: Theme Management Commands**
```bash
# List all available themes
todo theme list                       # Show all themes with descriptions and variants

# Get detailed theme information
todo theme info city_lights          # Show palette, variants, and validation results
todo theme info forest --show-palette  # Display color palette details

# Preview themes before applying
todo theme preview matrix             # Preview Matrix theme without applying
todo theme preview autumn --variant high_contrast  # Preview with variant

# Apply themes
todo theme set city_lights            # Set to default City Lights theme
todo theme set forest --compact       # Apply Forest theme with compact layout
todo theme set sky --high-contrast    # Apply Sky theme with high contrast
todo theme set matrix --colorblind-safe  # Apply colorblind-safe Matrix variant

# Validate themes for accessibility
todo theme validate                   # Check all themes for contrast issues
todo theme validate forest            # Validate specific theme

# Available Themes:
# 🌃 city_lights     - Modern dark theme inspired by city lights at night (default)
# 🌅 dracula         - Dark theme with purple, pink, and cyan accents
# 🍂 gruvbox_dark    - Retro groove with warm, earthy tones
# ❄️  nord           - Arctic, north-bluish minimalist theme
# ☀️  one_light      - Clean, bright theme for light terminals
# 🌙 solarized_dark  - Scientifically-designed dark color scheme
#
# 🌲 forest          - Fresh forest greens with natural earth tones
# 🍁 autumn          - Warm autumn oranges with harvest colors
# 🌤️  sky            - Bright sky blues with cloud whites
#
# 🔋 matrix          - Enter the Matrix - bright green code on black
# 🌅 sunset          - Warm sunset colors with orange/pink/purple backgrounds
# 🌊 ocean           - Deep ocean blues with aquatic gradients
# 💻 terminal        - Nostalgic retro terminal with amber/green CRT colors
#
# Theme Variants Available:
# --high-contrast    - Enhanced contrast for better accessibility
# --compact          - Reduced padding and spacing for minimal layouts
# --colorblind-safe  - Optimized colors for colorblind accessibility
```

### 🛠️ **Troubleshooting App Sync Issues**

If you encounter any issues with app synchronization, check out our comprehensive troubleshooting guide:

📖 **[App Sync Troubleshooting Guide](docs/troubleshooting-sync.md)**

The guide covers:
- Common symptoms and quick fixes (setup hangs, authentication issues, network problems)
- Step-by-step diagnostic procedures
- Advanced recovery techniques
- How to report issues with proper debugging information

**Quick health check:**
```bash
# Run diagnostics
uv run todo app-sync doctor

# Check configuration
ls -la ~/.todo/
uv run todo app-sync status
```

## 🌐 Progressive Web App (PWA)

Todo CLI includes a production-ready Progressive Web App with a modern REST API for managing tasks through any web browser!

### Quick Start

```bash
# Using CLI command (recommended)
todo web start --port 8000

# Or using uvicorn directly
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000

# Open PWA in browser
open http://127.0.0.1:8000
```

### ✨ PWA Features

#### Core Task Management
- **📋 Full CRUD Operations**: Create, read, update, delete tasks with rich metadata
- **🎯 Kanban Board View**: Visual board with drag-and-drop (Pending → In Progress → Completed)
- **🏷️ Smart Filtering**: Filter by contexts, tags, projects, priorities, and status
- **🔍 Advanced Search**: Full-text search across task titles and descriptions
- **⚡ Quick Capture**: Rapid task entry with keyboard shortcuts
- **📝 Rich Editing**: Inline editing with validation and auto-save

#### Modern Web Capabilities
- **📴 Offline-First**: Service worker enables full offline functionality
  - Network-first strategy for API calls (always fresh when online)
  - Cache-first for static assets (instant loading)
  - Automatic background sync when connection returns
  - Smart cache versioning and cleanup
- **🔔 Smart Notifications**: 
  - Actionable error messages with retry capabilities
  - Toast notifications for all operations
  - Real-time feedback on network status
  - Offline mode indicators
- **📱 Responsive Design**: Optimized for mobile, tablet, and desktop
- **♿ Accessibility**: WCAG-compliant with ARIA labels, keyboard navigation, reduced motion
- **🎨 Modern UI**: Clean interface with smooth animations and transitions

#### Data Management
- **💾 Backup & Restore**: 
  - Create backups directly from web interface
  - Browse and restore from previous backups
  - Automatic timestamps and validation
- **🔄 Real-time Sync**: Changes from CLI appear in PWA (with manual refresh)
- **🔐 Data Integrity**: Client-side validation prevents invalid data
- **📊 Context Views**: Browse tasks organized by context or tag
- **📈 Project Overview**: See task counts and completion rates per project

### 🛠️ REST API

The PWA is powered by a FastAPI-based REST API with comprehensive endpoints:

#### Health & Status
- `GET /health` - Server health check with database stats

#### Task Operations
- `GET /api/tasks` - List all tasks with filtering support
  - Query params: `status`, `priority`, `context`, `project`, `tag`
- `GET /api/tasks/{id}` - Get single task by composite ID (project:id)
- `POST /api/tasks` - Create new task with validation
- `PUT /api/tasks/{id}` - Update existing task (partial updates supported)
- `DELETE /api/tasks/{id}` - Delete task

#### Metadata & Organization
- `GET /api/contexts` - List all contexts with task counts
- `GET /api/tags` - List all tags with usage statistics
- `GET /api/projects` - List projects with metadata and stats

#### Backup Management
- `GET /api/backups` - List available backups with timestamps
- `POST /api/backups` - Create new backup
- `POST /api/backups/{filename}/restore` - Restore from backup

### 🏗️ Architecture & Implementation

**Backend Stack:**
- **FastAPI**: Modern async Python web framework (676 lines)
- **Uvicorn**: ASGI server with hot-reload support
- **CORS Middleware**: Configured for development and PWA access
- **Pydantic Models**: Type-safe request/response validation

**Frontend Stack (4,798 total lines):**
- **Vanilla JavaScript**: No framework dependencies (2,789 lines across 7 modules)
  - `app.js` (1,116 lines): Main application logic and UI orchestration
  - `api.js` (190 lines): REST API client wrapper
  - `data-loader.js` (413 lines): Centralized data loading and caching
  - `notifications.js` (344 lines): Toast notification system
  - `sw-manager.js` (299 lines): Service worker lifecycle management
  - `ui.js` (350 lines): UI rendering and DOM manipulation
  - `config.js` (77 lines): Configuration management
- **Service Worker** (323 lines): Advanced caching and offline support
- **Modern CSS** (1,333 lines): Responsive layouts with CSS Grid and Flexbox
- **PWA Manifest**: Installable app configuration

**Key Design Patterns:**
- **Modular Architecture**: Clear separation of concerns (API, UI, data, notifications)
- **Defensive Programming**: Robust error handling and data validation
- **Progressive Enhancement**: Works without JavaScript, enhanced with it
- **Mobile-First**: Responsive design starts with mobile and scales up

### 📖 Documentation & Resources

For detailed setup, troubleshooting, and API examples:

📖 **[Complete PWA Setup Guide](docs/PWA_SETUP.md)**

The comprehensive guide covers:
- **Installation**: Step-by-step setup with uv and uvicorn
- **Configuration**: Environment variables and server options
- **API Documentation**: Complete endpoint reference with curl examples
- **Troubleshooting**: Common issues and solutions
  - CORS configuration
  - Service worker caching problems
  - Data synchronization between CLI and PWA
  - Network and offline mode issues
- **Development**: Tips for extending and debugging the PWA
- **Architecture**: Deep dive into frontend/backend design

### 🚀 Development Commands

```bash
# Start server with CLI (includes startup banner)
todo web start                  # Default: localhost:8000
todo web start --port 3000      # Custom port
todo web start --debug          # Enable debug mode with auto-reload

# Start with uvicorn directly
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000

# Production mode (multiple workers)
uv run uvicorn src.todo_cli.web.server:app --host 0.0.0.0 --port 8000 --workers 4

# Background mode
uv run uvicorn src.todo_cli.web.server:app --port 8000 > /tmp/todo_api.log 2>&1 &

# Get server information
todo web info                   # Show features and endpoints
```

### ✅ CI/CD & Quality Gates

The PWA includes automated quality checks:
- **JavaScript Validation**: Syntax and console.log detection
- **Manifest & Service Worker**: Structure validation
- **API Integration Tests**: Comprehensive endpoint testing (332 test cases)
- **Build Verification**: Package building and CLI command validation

See [.github/workflows/README.md](.github/workflows/README.md) for complete CI/CD documentation.

## 📊 Dashboard View

The dashboard provides an at-a-glance view of your tasks with rich themed formatting:

```
╒═══════════════════╕
│ 📋 Todo Dashboard │
╚═══════════════════╝

╒────────────────────────────────── ⭐ Pinned Tasks ─────────────────────────────────╕
│ 1 ⭐ ⏳ Review security PR @urgent !2025-09-15 +reviewer                                              │
│ Context: @work                                                                                        │
│ Estimate: 2h 0m                                                                                       │
│                                                                                                        │
│ 3 🔄 Team standup @meetings !2025-09-19 +team                                                         │
│ Effort: *large                                                                                        │
╚───────────────────────────────────────────────────────────────────────────────────────────────────────╝

╒───────────────────────────────── 🔥 Overdue Tasks ─────────────────────────────────╕
│ 2 ⏳ Update documentation @docs !2025-09-14 ~medium                                                   │
╚───────────────────────────────────────────────────────────────────────────────────────────────────────╝

╒─────────────────────────────────── 📅 Due Today ───────────────────────────────────╕
│ 4 ⏳ Call doctor                                                                                    │
│ Context: @phone                                                                                       │
│ Energy: low                                                                                           │
│ Estimate: 15m                                                                                         │
│ Waiting for: insurance approval                                                                       │
╚───────────────────────────────────────────────────────────────────────────────────────────────────────╝

╒──────────────────────────────────────── Summary ───────────────────────────────────────╕
│ Total: 12 | Active: 8 | Completed: 4                                                                 │
╚───────────────────────────────────────────────────────────────────────────────────────────────────────╝
```

**Theme Features in Dashboard:**
- 🎨 **Rich Background Colors**: Each section has themed background colors that change with your selected theme
- 🌈 **Themed Borders**: Overdue tasks have red borders, pinned tasks have gold borders, etc.
- 📏 **Visual Hierarchy**: Different themes provide distinct visual experiences (Matrix = green on black, Sky = light blues, Forest = greens)
- ✨ **Consistent Styling**: Colors automatically adapt to your chosen theme for a cohesive experience

## 🗃️ File Structure

Todo CLI organizes your data in a clean, version-control-friendly structure:

```
~/.todo/
├── config.yaml              # Your preferences
├── app_sync_config.yaml     # App synchronization settings
├── projects/
│   ├── inbox.md             # Default project
│   ├── work.md              # Work-related tasks
│   └── personal.md          # Personal tasks
├── sync/
│   ├── mappings.db          # Sync mappings and conflict history
│   └── credentials.json     # Encrypted credential cache (fallback)
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

# Theme settings
theme_name: "city_lights"          # Active theme name
theme_variant: null                # Optional theme variant
theme_compact: false               # Compact layout mode
theme_high_contrast: false         # High contrast accessibility mode
theme_colorblind_safe: false       # Colorblind-safe color palette

# Behavior
auto_archive_completed: false
confirm_deletion: true

# Custom contexts and priorities
custom_contexts: ["home", "office", "errands"]
custom_priorities: ["someday"]
```

### App Sync Configuration (`~/.todo/app_sync_config.yaml`)

```yaml
# Global sync settings
global:
  auto_sync: true
  conflict_strategy: "newest_wins"
  sync_interval: 300  # seconds
  max_retry_attempts: 3
  
# Provider-specific configurations
providers:
  todoist:
    enabled: true
    auto_sync: true
    conflict_strategy: "newest_wins"
    sync_direction: "bidirectional"
    project_mappings:
      work: "Work Projects"
      personal: "Personal"
    label_mappings:
      urgent: "@urgent"
      important: "@important"
    settings:
      sync_completed: false
      sync_labels: true
      sync_projects: true
      rate_limit_delay: 1.0
      
# Conflict resolution strategies:
# - local_wins: Always prefer local changes
# - remote_wins: Always prefer remote changes  
# - newest_wins: Use timestamp to determine winner
# - manual: Prompt user for each conflict
# - merge: Attempt to merge changes automatically
# - skip: Skip conflicted items
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

**Test Coverage**: 173 tests covering:
- Core CLI functionality and domain models
- Natural language parsing (32 comprehensive scenarios)
- API integration and contracts (332 test cases)
- Query engine and recommendations
- Multi-app synchronization
- Export and notification systems

**Pass Rate**: 100% with comprehensive coverage across all modules

## 🧹 Development: Code Quality & Pre-commit

This project uses Black, isort, Flake8, and MyPy. Pre-commit hooks are provided to keep the codebase clean.

Setup (once per machine):
```bash
uv sync --all-extras
uv run pre-commit install
```

Run formatters and linters locally:
```bash
# Format (non-destructive: add to commit via pre-commit)
uv run black .
uv run isort .

# Lint
uv run flake8

# Type-check (configured to be permissive by default)
uv run mypy --config-file pyproject.toml
```

Run all pre-commit hooks on the full repo:
```bash
uv run pre-commit run --all-files
```

## 🏗️ Architecture

Todo CLI is built with a clean, extensible architecture:

```
src/todo_cli/
├── __init__.py            # Package exports
├── domain/                # Domain models and business logic
│   ├── todo.py            # Todo model (40+ fields)
│   ├── project.py         # Project management
│   ├── parser.py          # Natural language parsing engine
│   └── recurring.py       # Smart recurring task system
├── services/              # Application services
│   ├── query_engine.py    # Advanced search and filtering
│   ├── recommendations.py # AI-powered recommendations
│   ├── export.py          # Multi-format export
│   ├── notifications.py   # Desktop and email notifications
│   └── analytics.py       # Productivity analytics
├── sync/                  # Multi-app synchronization
│   ├── app_sync_manager.py  # Sync orchestration
│   ├── app_sync_adapter.py  # Base adapter interface
│   ├── sync_engine.py       # Conflict resolution
│   ├── credential_manager.py # Secure credential storage
│   └── providers/           # External app adapters
│       ├── todoist_adapter.py    # Todoist integration
│       └── apple_reminders_adapter.py # Apple Reminders
├── web/                   # Progressive Web App
│   ├── server.py          # FastAPI REST API (676 lines)
│   ├── static/            # Static web assets
│   │   ├── js/            # JavaScript modules (2,789 lines)
│   │   │   ├── app.js         # Main application logic (1,116 lines)
│   │   │   ├── api.js         # REST API client (190 lines)
│   │   │   ├── data-loader.js # Data loading system (413 lines)
│   │   │   ├── notifications.js # Toast system (344 lines)
│   │   │   ├── sw-manager.js  # Service worker manager (299 lines)
│   │   │   ├── ui.js          # UI rendering (350 lines)
│   │   │   └── config.js      # Configuration (77 lines)
│   │   ├── css/           # Stylesheets (1,333 lines)
│   │   │   ├── main.css       # Core styles (670 lines)
│   │   │   └── enhancements.css # Enhanced UI (663 lines)
│   │   ├── sw.js          # Service worker (323 lines)
│   │   └── manifest.json  # PWA manifest
│   └── templates/         # HTML templates
│       └── index.html     # Main PWA interface
├── theme_engine/          # Advanced theming system
│   ├── engine.py          # Theme compilation and caching
│   ├── registry.py        # Theme registry
│   ├── schema.py          # Theme models and validation
│   └── utils.py           # Color utilities
├── theme_presets/         # Built-in themes (14 total)
│   ├── city_lights.yaml   # Default modern dark theme
│   ├── dracula.yaml       # Dark purple/pink theme
│   ├── forest.yaml        # Nature green theme
│   ├── matrix.yaml        # Matrix green-on-black
│   ├── ocean.yaml         # Deep ocean blues
│   └── [9 more themes...]
└── cli/                   # CLI command interface
    ├── tasks.py           # Main CLI and dashboard
    ├── web.py             # Web server commands
    ├── theme_cmds.py      # Theme management
    ├── app_sync.py        # App sync commands
    └── analytics_commands.py # Analytics CLI
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

### ✅ Phase 4: Smart Integration Features (Complete)
- [x] **Recurring tasks with smart scheduling** - Full CLI integration with natural language patterns
- [x] **Export functionality** - Multiple formats (JSON, CSV, Markdown, HTML, PDF, ICAL, YAML)
- [x] **Notification system** - Desktop and email notifications with smart scheduling
- [x] **Calendar integration** - Bidirectional calendar sync with multiple providers
- [x] **Multi-device sync capabilities** - Cloud storage sync with conflict resolution

### ✅ Phase 5: Advanced Theming System (Complete)
- [x] **14 Built-in Themes** - Professional light themes to dramatic dark experiences
- [x] **Background Color Support** - Rich panel backgrounds with RGB color conversion
- [x] **Themed Borders & Panels** - Distinct styling for dashboard sections
- [x] **Theme Variants** - High contrast, compact, and colorblind-safe options
- [x] **Live Theme Switching** - Change themes instantly without CLI restart
- [x] **Accessibility Features** - WCAG contrast validation and colorblind support
- [x] **Smart Cache Management** - Efficient theme loading with cache invalidation
- [x] **Theme Validation** - Built-in contrast checking and error reporting

### ✅ Phase 6: Multi-App Synchronization & PWA (Complete)
- [x] **Extensible sync architecture** - Adapter pattern for external app integrations
- [x] **Todoist integration** - Full bidirectional sync with projects and labels
- [x] **Apple Reminders integration** - macOS/iOS native bidirectional sync
- [x] **Conflict resolution engine** - Multiple strategies with interactive resolution
- [x] **Secure credential management** - System keyring with encrypted fallbacks
- [x] **Project and label mapping** - Flexible mapping between Todo CLI and external apps
- [x] **CLI commands for sync management** - Complete command suite for app sync
- [x] **Progressive Web App** - Modern web interface with offline support
- [x] **REST API** - FastAPI-based API with comprehensive endpoints
- [x] **Service Worker** - Advanced caching and offline functionality
- [x] **Responsive Design** - Mobile, tablet, and desktop optimized
- [x] **API Integration Tests** - 332 comprehensive test cases
- [x] **CI/CD Pipelines** - Automated quality gates for Python and JavaScript

### 🌟 Phase 7: Advanced Reporting & Analytics (Planned)
- [ ] Productivity insights and trends
- [ ] Time tracking reports and analysis
- [ ] Project analytics and forecasting
- [ ] Custom dashboards and visualizations
- [ ] Plugin system for extensibility

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

## 👏 Acknowledgments

**Python Ecosystem:**
- [Click](https://click.palletsprojects.com/) - Elegant CLI framework
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal output and theming
- [uv](https://github.com/astral-sh/uv) - Lightning-fast Python package management
- [FastAPI](https://fastapi.tiangolo.com/) - Modern async web framework
- [Uvicorn](https://www.uvicorn.org/) - ASGI web server
- [Pydantic](https://pydantic.dev/) - Data validation and settings management
- [PyYAML](https://pyyaml.org/) - Configuration and theme management
- [python-frontmatter](https://python-frontmatter.readthedocs.io/) - Markdown with YAML frontmatter
- [parsedatetime](https://github.com/bear/parsedatetime) - Natural language date parsing
- [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) - Intelligent typo detection

**Web Technologies:**
- Vanilla JavaScript - No framework dependencies, pure performance
- Modern CSS - Grid, Flexbox, and CSS Variables
- Service Workers - Progressive Web App capabilities
- Web APIs - Notifications, Storage, Fetch, and more

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Schaafd/todo_cli/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Schaafd/todo_cli/discussions)
- **Documentation**: [PLAN.md](./PLAN.md) for detailed technical specifications

---

**Phase 6 Complete** ✅ | Built with ❤️ for productivity enthusiasts

## 🎉 What's New in Phase 6

### 🌐 Progressive Web App
> Modern web interface with offline support, Kanban boards, and smart notifications!
> Try: `todo web start` then open http://localhost:8000

### 🔄 Multi-App Synchronization  
> Keep your todos in sync with Todoist and Apple Reminders!
> Try: `todo app-sync setup todoist` or `todo app-sync setup apple_reminders`

### 📈 Enhanced Productivity Features
> Recurring tasks, multi-format export, smart notifications, and comprehensive analytics!
> Try: `todo notify status` | `todo export pdf` | `todo recurring "Daily standup" daily`

### ⚙️ Production-Ready Infrastructure
> Complete CI/CD pipelines with automated testing, linting, and quality gates!
> See: [CI/CD Documentation](.github/workflows/README.md)
