# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## 📦 Project Overview

Todo CLI is a sophisticated Python 3.11+ command-line todo application built with Clean Architecture principles. It features advanced task management, natural language parsing, multi-app synchronization, analytics, and extensible plugin architecture.

## 🛠️ Development Commands

### Dependency Management (uv-based)
```bash
# Install dependencies
uv sync

# Install with development dependencies
uv sync --all-extras

# Install from lockfile
uv sync --locked

# Run application
uv run todo --help
```

### Testing
```bash
# Run all tests
uv run python -m pytest

# Run with coverage
uv run python -m pytest --cov=src/todo_cli --cov-report=term-missing

# Run specific test file
uv run python -m pytest tests/test_todo.py -v

# Run by test marker
uv run python -m pytest -m "not slow"
uv run python -m pytest -m integration
```

### Code Quality & Formatting
```bash
# Format code (Black + isort)
uv run black .
uv run isort .

# Lint with flake8
uv run flake8

# Type checking with mypy
uv run mypy --config-file pyproject.toml

# Run all pre-commit hooks
uv run pre-commit run --all-files

# Install pre-commit hooks (one-time setup)
uv run pre-commit install
```

### Application Commands
```bash
# Main CLI entry point (shows dashboard by default)
uv run todo

# Common development testing patterns
uv run todo add "Test task @dev ~high due tomorrow"
uv run todo list --project work
uv run todo app-sync setup todoist
uv run todo export json --project personal
uv run todo analytics summary
```

## 🏗️ Architecture Overview

### Domain-Driven Design Structure

The codebase follows Clean Architecture with clear separation:

- **Domain Layer** (`domain/`): Core business models and logic
  - `Todo`: Rich task model with 40+ fields
  - `Project`: Project management with team members and analytics
  - `parser.py`: Natural language parsing engine
  - `recurring.py`: Smart recurring task system

- **Services Layer** (`services/`): Application business logic
  - `query_engine.py`: Advanced search and filtering
  - `recommendations.py`: AI-powered task suggestions
  - `analytics.py`: Productivity analysis and reporting
  - `notifications.py`: Desktop and email notification system
  - `export.py`: Multi-format export system (JSON, CSV, PDF, etc.)

- **Sync Layer** (`sync/`): Multi-app synchronization
  - `app_sync_manager.py`: Orchestrates external app synchronization
  - `app_sync_adapter.py`: Base adapter for external integrations
  - `sync_engine.py`: Conflict resolution and sync logic
  - `providers/`: External app adapters (Todoist, Apple Reminders, etc.)

- **CLI Layer** (`cli/`): User interface commands
  - `tasks.py`: Main CLI commands and dashboard (main entry point)
  - `app_sync.py`: App synchronization commands
  - `analytics_commands.py`: Analytics and reporting commands

### Key Patterns

- **Adapter Pattern**: External app integrations (`sync/providers/`)
- **Factory Pattern**: Service creation and dependency injection
- **Strategy Pattern**: Conflict resolution strategies
- **Observer Pattern**: Notification system
- **Builder Pattern**: Natural language task parsing (`domain/parser.py`)

### Storage System

- **Format**: Markdown files with YAML frontmatter
- **Location**: `~/.todo/projects/` (human-readable, git-friendly)
- **Structure**: Individual project files with rich metadata
- **Backup**: Automatic backups in `~/.todo/backups/`

### Configuration Hierarchy

1. `pyproject.toml` - Project dependencies and tool configuration
2. `~/.todo/config.yaml` - User preferences and defaults
3. `~/.todo/app_sync_config.yaml` - App synchronization settings
4. Environment variables and CLI options

## 🧪 Testing Strategy

- **Unit Tests**: Individual component testing
- **Integration Tests**: Cross-component interaction
- **Parser Tests**: 32 comprehensive natural language parsing scenarios
- **Sync Tests**: Multi-app synchronization scenarios
- **Coverage Target**: Core functionality coverage with pytest-cov

Test files are organized by module structure under `tests/` directory.

## 🔄 External Integrations

### Sync Providers
- **Todoist**: Full bidirectional sync with projects and labels
- **Apple Reminders**: Native macOS integration (in progress)
- **Extensible**: Ready for TickTick, Notion, Microsoft Todo

### Credential Management
- **Primary**: System keyring integration
- **Fallback**: Encrypted JSON storage
- **Security**: No plaintext secrets in configuration

## 📊 Phase-Based Development

Currently in **Phase 6**: Multi-App Synchronization
- Completed: Phases 1-5 (Enhanced storage, Natural language parsing, Query engine, Smart integrations)
- Next: Phase 7 (Advanced reporting & analytics)

## 🎯 Development Guidelines

### Natural Language Processing
The parser (`domain/parser.py`) is central to user experience. When modifying:
- Maintain comprehensive test coverage
- Preserve backward compatibility with existing syntax
- Update parser tests for new features

### Sync System Architecture
When adding new sync providers:
- Extend `sync/app_sync_adapter.py` base class
- Add provider to `sync/providers/` directory
- Update CLI commands in `cli/app_sync.py`
- Include comprehensive sync tests

### CLI Command Structure
Main entry point is `cli/tasks.py:main()`. Commands follow Click patterns:
- Group commands by functionality
- Provide rich help text and examples
- Use consistent option naming
- Include progress indicators for long operations

### Storage Considerations
- All data is human-readable Markdown + YAML
- Preserve file structure compatibility
- Include migration logic for breaking changes
- Maintain backup systems

### Theme System
The application includes a sophisticated theming system (`theme.py`, `theme_engine/`) for customizable CLI appearance.

## 💡 Common Patterns

### Error Handling
- Use rich error messages with helpful suggestions
- Implement graceful degradation for optional features
- Provide clear recovery instructions

### Configuration Loading
- Use `get_config()` and `get_storage()` factory functions
- Support environment variable overrides
- Validate configuration on startup

### Service Dependencies
Services are designed to be loosely coupled with dependency injection patterns. Use factory functions rather than direct instantiation.

## 🚨 Important Notes

### Python Version
- **Minimum**: Python 3.11
- **Type Hints**: Comprehensive type annotations throughout
- **Modern Features**: Uses Python 3.11+ features like `tomllib`

### Dependency Management
- **Primary**: `uv` for fast dependency resolution
- **Lockfile**: `uv.lock` must be committed
- **Extra Groups**: Development dependencies in `[dependency-groups]`

### Multi-Platform Considerations
- macOS-specific features in Apple Reminders integration
- Cross-platform notification system
- Path handling for different operating systems

## 🎨 Theming System

### Theme Management Commands

```bash
# List all available themes
uv run todo theme list

# Get detailed theme information
uv run todo theme info <theme_name>

# Preview a theme without applying it
uv run todo theme preview <theme_name> [--variant <variant>]

# Set the active theme
uv run todo theme set <theme_name> [--variant <variant>] [--compact] [--high-contrast] [--colorblind-safe]

# Validate all themes for issues
uv run todo theme validate
```

### Available Themes

- **city_lights** - Modern dark theme inspired by city lights (default)
- **dracula** - Dark theme with purple, pink, and cyan accents
- **gruvbox_dark** - Retro groove color scheme with warm, earthy tones
- **nord** - Arctic, north-bluish minimalist theme
- **one_light** - Clean, bright light theme for daytime use
- **solarized_dark** - Scientifically-designed dark color scheme

### Theme Configuration

Theme settings are stored in `~/.todo/config.yaml`:

```yaml
# Theme settings
theme_name: "city_lights"
theme_variant: null                # Optional variant name
theme_compact: false               # Compact layout mode
theme_high_contrast: false         # High contrast accessibility mode
theme_colorblind_safe: false       # Colorblind-safe color palette
```

### Theme Architecture

The theming system (`src/todo_cli/theme_engine/`) provides:

- **Palette System**: Named colors with semantic meaning
- **Component Tokens**: UI element styling (headers, tables, etc.)
- **Semantic Tokens**: Status-based styling (success, error, etc.)
- **Variants**: Theme modifications (high-contrast, compact, colorblind-safe)
- **Terminal Capability Detection**: Automatic color downgrading for older terminals
- **Accessibility Features**: WCAG contrast validation and colorblind-safe palettes

### Creating Custom Themes

Themes are defined as YAML files in `src/todo_cli/theme_presets/`. Structure:

```yaml
name: my_theme
display_name: "My Custom Theme"
description: "Description of the theme"
version: "1.0.0"
author: "Your Name"
min_capability: "16"  # color_16, color_256, truecolor

palette:
  background: "#1a1a1a"
  text_primary: "#ffffff"
  primary: "#007acc"
  # ... more colors

components:
  todo_pending: "primary"
  todo_completed: "success"
  # ... component mappings

variants:
  - name: high_contrast
    description: "High contrast version"
    palette_overrides:
      background: "#000000"
      text_primary: "#ffffff"
```

### Theme Development Guidelines

When modifying themes:

- Follow the existing palette structure for consistency
- Test with different terminal capabilities (16-color, 256-color, truecolor)
- Validate accessibility with `todo theme validate`
- Include colorblind-safe variants for accessibility
- Test both light and dark terminal backgrounds
- Ensure adequate contrast ratios (4.5:1 minimum, 7:1 for AAA)

### Backward Compatibility

The theme system includes a backward compatibility layer in `theme.py` that:

- Falls back to legacy City Lights colors if theme engine fails
- Provides graceful degradation for missing theme files
- Maintains existing CLI styling even with theme engine errors
