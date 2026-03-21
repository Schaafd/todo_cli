# Changelog

All notable changes to the Todo CLI project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-20

### 🚀 New Features

#### Customizable Dashboard Widgets
- Rich terminal renderer for all widget types: metric, gauge, sparkline, bar/pie charts, tables, lists, progress bars
- CLI command group `dashboard-mgr` with subcommands: show, create, list, add-widget, remove-widget, delete, reset, templates
- Four dashboard templates: Productivity, Project Manager, Time Tracking, Minimal
- REST API endpoints for dashboard CRUD and widget data refresh

#### Voice Input (Speech-to-Task)
- `todo voice add` — record and create tasks from speech
- `todo voice status` — check voice backend availability
- `todo voice test` — test recording/transcription
- Local transcription via Vosk (offline, optional `voice` dependency group)
- Cloud transcription via OpenAI Whisper API (optional `voice-cloud` dependency group)
- Web Speech API integration in PWA with microphone button

#### Third-Party Integrations
- **GitHub Issues sync adapter** — bidirectional sync mapping issues to todos (title, labels→tags, milestones→projects, assignees, state→status, body→description, priority via labels)
- **Jira sync adapter** — bidirectional sync via REST v3 (summary, description, priority, labels→tags, sprint→project, status transitions, assignees)
- **Slack integration plugin** — event-driven notifications for task completion/creation, daily summaries with Block Kit formatting, `/todo` message parsing

#### Complete Sync Provider Coverage
- **Notion adapter** — sync with Notion databases (title, status, priority, tags, due date, assignee, description, project properties)
- **Microsoft Todo adapter** — sync via Microsoft Graph API (title, body, importance, status, due date, categories)
- **Google Tasks adapter** — sync via Google Tasks API (title, notes, due date, status; priority/tags stored as metadata)
- **TickTick adapter** — sync via TickTick Open API (experimental; title, content, priority, tags, due date, status, project)

### 🛠️ Improvements

#### Dependency Updates & Performance
- Upgraded all 57 dependencies to latest versions (FastAPI 0.115→0.135, Pydantic 2.11→2.12, pytest 8→9, etc.)
- Removed duplicate `itsdangerous` and `python-multipart` entries
- Widened FastAPI and httpx version ranges for easier future upgrades
- Lazy-loaded heavy CLI service imports (analytics, recommendations, query engine, export, notifications) for faster startup
- Removed unused sync imports from CLI module
- Enabled deprecation warnings in pytest
- Fixed mypy `follow_imports` from "skip" to "normal"

#### Configuration
- Added dashboard config fields (default layout, auto-refresh, refresh interval)
- Added voice input config fields (provider, language, model path, duration)
- Added Slack integration config fields (channel, notification preferences)
- Sensitive credentials (API keys, tokens) excluded from YAML serialization

#### AI/LLM Integration
- `AIProvider` ABC with `OpenAIProvider` (cloud) and `OllamaProvider` (local) backends
- `TaskAIAssistant`: suggest next task, auto-categorize, smart natural language queries, summarize tasks
- `AIInsightsDataSource` for dashboard widgets
- CLI commands: `ai suggest`, `ai ask`, `ai categorize`, `ai summary`, `ai status`
- 5 REST API endpoints for AI features
- Optional dependency groups: `ai` (openai), `ai-local` (ollama)

#### Pomodoro Focus Timer
- `PomodoroTimer` state machine: idle → focus → short break → focus → ... → long break
- Session tracking with JSON persistence, statistics (streaks, daily totals, averages)
- CLI: `focus start [TASK_ID]` with Rich Live countdown + progress bar, `focus break`, `focus stats`, `focus history`, `focus config`
- PWA circular SVG timer component with API integration
- 7 REST API endpoints for timer control and statistics

#### Collaboration
- `CollaborationDB`: SQLite storage for shared projects, members, activity feed, comments, task assignments
- `CollaborationManager`: role-based permission checking (owner > admin > editor > viewer)
- `RealtimeManager`: WebSocket connection tracking, project subscriptions, broadcasts
- CLI: `collab share`, `collab invite`, `collab members`, `collab activity`, `collab comment`, `collab assign`, `collab projects`
- 11 REST API endpoints + WebSocket endpoint `/ws/{user_id}`

#### iOS App (SwiftUI)
- Native iOS 17+ app with flat material design
- Quick Add: floating action button + always-visible quick add bar with spring animations
- Quick Access: Today/Overdue/Pinned sections, swipe gestures, instant search
- Personalization: 10 accent colors, light/dark/system modes, compact/comfortable density
- Focus Timer: circular pomodoro timer with session tracking
- Full REST API integration with configurable backend URL
- 24 Swift source files, Xcode project, asset catalogs

### 📊 Testing
- Test count: 173 → 705 (532 new tests)
- New test coverage: dashboards (35), voice input (24), Slack plugin (27), GitHub Issues (37), Jira (42), Notion (34), Microsoft Todo (41), Google Tasks (46), TickTick (36), AI assistant (30), Pomodoro (28), Collaboration (54), iOS API compat (14)

## [Unreleased]

### 🛠️ Fixes
- Adjusted weekly analytics calculations to use a rolling seven-day window so completion rates reflect the most recent tasks.
- Swapped the local httpx shim for the real `httpx` dependency with an upper bound to match FastAPI's test client expectations.
- Added missing web dependencies (`itsdangerous`, `python-multipart`) required for authentication and form handling routes.

## [0.1.1] - 2025-09-20

### 🚀 Major Improvements

#### App Sync Setup Reliability
- **Fixed critical setup hang issue** that could cause `todo app-sync setup` to freeze indefinitely
- **Added robust timeout handling** with configurable timeout values (default 60s, customizable via `--timeout`)
- **Improved interactive/non-interactive mode detection** - automatically detects terminal environments
- **Enhanced error handling** with graceful KeyboardInterrupt handling and clear error messages

#### Configuration System Overhaul  
- **Resolved YAML enum serialization issues** - enums now properly serialize to/from strings instead of Python objects
- **Fixed "No providers configured" bug** - AppSyncManager now correctly loads configured providers on initialization
- **Added backward compatibility** for existing configuration files with automatic migration
- **Improved configuration validation** with better error reporting

#### Enhanced Diagnostics and Troubleshooting
- **New `app-sync doctor` command** - comprehensive diagnostic tool for troubleshooting sync issues
  - Validates environment, configuration, credentials, and network connectivity
  - Provides actionable remediation suggestions
  - Checks both environment variables and keyring storage for tokens
- **Enhanced debug logging** throughout the app-sync system
- **Improved error messages** with specific guidance for common issues

### 🛠️ New Features

#### Command Line Interface
- **New setup options:**
  - `--skip-mapping` - Skip interactive project mapping for faster setup
  - `--timeout N` - Set custom timeout for network operations (default: 60 seconds)
  - `--no-interactive` - Force non-interactive mode (also auto-detected)
  - `--debug` - Enable detailed debug logging for troubleshooting

#### Environment Variable Support  
- **Full support for `TODOIST_API_TOKEN`** environment variable
- **Automatic fallback chain:** environment variable → command line flag → interactive prompt → keyring storage
- **Non-interactive automation** - perfect for CI/CD and scripted environments

### 🔧 Technical Improvements

#### Testing Infrastructure
- **Added comprehensive test suite** with 16 new tests covering:
  - App-sync models and enum functionality
  - Environment detection (interactive vs non-interactive)
  - Configuration directory and file handling
  - CLI command availability and import verification
  - Doctor command diagnostic components
- **Configured pytest** with proper settings, coverage reporting, and CI integration
- **Added GitHub Actions workflow** for automated testing on multiple Python versions
- **Test dependencies:** pytest-cov, pytest-mock, responses, respx for comprehensive mocking

#### Code Quality
- **Enhanced type safety** throughout the app-sync codebase
- **Improved error handling** with proper exception propagation
- **Better separation of concerns** between configuration, credentials, and sync logic
- **Consistent logging patterns** with structured debug information

### 📚 Documentation

#### User-Facing Documentation
- **Comprehensive troubleshooting guide** (`docs/troubleshooting-sync.md`) covering:
  - Common symptoms and quick fixes (setup hangs, authentication issues, network problems)
  - Step-by-step diagnostic procedures with copy-paste commands
  - Advanced recovery techniques including complete reset procedures
  - Professional issue reporting template with required debugging information
  - Prevention tips and maintenance best practices
- **Updated README** with troubleshooting guide link and quick health check commands
- **Enhanced command help text** with better descriptions and examples

### 🐛 Bug Fixes

#### Setup and Configuration
- **Fixed indefinite hang during interactive project mapping** - now has timeout and skip options
- **Resolved enum serialization in YAML config files** - no more Python object tags in config
- **Fixed AppSyncManager not loading configured providers** - status commands now work correctly
- **Improved keyring integration** with proper fallback to environment variables

#### Error Handling
- **Fixed timeout errors in non-interactive environments** - better environment detection
- **Improved network error handling** with retries and clear error messages  
- **Fixed authentication token validation** - better error reporting for invalid tokens
- **Enhanced configuration loading** - handles corrupt config files gracefully

### ⚡ Performance

- **Reduced setup time** with `--skip-mapping` option for users who don't need project mapping
- **Better timeout handling** prevents indefinite waits
- **Improved configuration loading** with lazy initialization where appropriate

### 🔒 Security

- **Enhanced credential security** - tokens never exposed in logs or error messages
- **Improved keyring integration** with secure fallback mechanisms
- **Better environment variable handling** with proper masking in debug output

### 💻 Developer Experience

- **Comprehensive test coverage** prevents regressions of the fixed issues
- **Improved debugging tools** with the new doctor command
- **Enhanced error messages** with actionable guidance
- **Better development workflow** with automated testing in CI

### 🎯 Migration Notes

#### For Existing Users
- **No breaking changes** - all existing configurations continue to work
- **Automatic config migration** - old YAML files with Python object serialization are handled gracefully
- **Recommended actions:**
  ```bash
  # Verify your setup is working correctly
  uv run todo app-sync doctor
  
  # Check status (should now show configured providers)
  uv run todo app-sync status
  
  # If you experience issues, see the troubleshooting guide
  # docs/troubleshooting-sync.md
  ```

#### For New Users
- **Setup is now more reliable** - use the new options for better experience:
  ```bash
  # Quick setup without project mapping
  export TODOIST_API_TOKEN="your_token"
  uv run todo app-sync setup todoist --skip-mapping
  
  # Verify everything is working
  uv run todo app-sync doctor
  ```

### 🙏 Acknowledgments

This release significantly improves the reliability and user experience of the app-sync functionality. The improvements are based on:
- Thorough analysis of setup hang issues
- Enhanced error handling and timeout management  
- Comprehensive testing to prevent regressions
- User-focused troubleshooting and documentation improvements

---

## [0.1.0] - 2025-09-16

### 🚀 Initial Release

#### Core Features
- **Full-featured todo management** with rich data models (40+ fields per task)
- **Advanced natural language parsing** - extract metadata from plain text
- **Multi-app synchronization** with Todoist integration
- **Project and context management** with flexible organization
- **Smart search and filtering** with query shortcuts
- **Export system** supporting multiple formats (JSON, CSV, Markdown, HTML, PDF, iCal, YAML)
- **Notification system** with desktop and email notifications
- **Calendar integration** with bidirectional sync capabilities
- **Recurring tasks** with intelligent pattern recognition

#### App Synchronization
- **Todoist adapter** with full bidirectional sync
- **Project and label mapping** between Todo CLI and external apps
- **Conflict resolution engine** with multiple strategies
- **Secure credential management** using system keyring
- **CLI commands** for complete sync management

#### Architecture
- **Clean, extensible architecture** with type safety throughout
- **Adapter pattern** for external app integrations
- **Robust storage system** using Markdown + YAML
- **Comprehensive configuration system** with YAML-based settings

#### Developer Experience
- **Modern Python tooling** with uv for dependency management
- **Comprehensive test suite** with pytest
- **Rich CLI interface** using Rich library for enhanced UX
- **Professional code quality** with type hints and clean architecture

---

For more details on any release, see the [GitHub releases page](https://github.com/Schaafd/todo_cli/releases).