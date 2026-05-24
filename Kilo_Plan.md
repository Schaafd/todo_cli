# Plan: Simplify, Improve, and Harden Todo CLI

## Current State Analysis

**Project**: Todo CLI v0.2.0 - Feature-rich Python CLI for task management
**Tech Stack**: Python 3.11+, Click, Rich, Pydantic, FastAPI (PWA)
**Architecture**: Domain models → Storage (Markdown+YAML) → CLI Commands (19 files) → Services (19 files)
**Features**: 40+ field todo model, 8 sync providers, AI, voice, Pomodoro, themes, PWA, iOS, notifications

### Current Metrics
- **Tests**: 705 passing, 0 failing (across 33 test files)
- **Coverage**: 42% overall (storage.py 62%, CLI commands not well covered, utils/validation.py 0%, sync_engine.py 0%)
- **Warnings**: 79 Pydantic deprecation warnings (V1 `@validator`, `.dict()` patterns)
- **mypy**: Not installed/enabled (`ignore_missing_imports = true` in pyproject.toml)

### Strengths
- Rich feature set with natural language parsing
- Clean domain model with comprehensive fields (40+ per todo)
- Good theming system (14 themes with variants)
- Multiple export formats (JSON, CSV, Markdown, HTML, PDF, iCal, YAML, TSV)
- Test infrastructure in place (705 tests all passing)
- Lazy import pattern for CLI entry point

### Weaknesses Identified
1. **CLI Complexity**: 30+ commands across nested groups, poor discoverability (all alphabetical, no categories)
2. **Inconsistent Patterns**: `done` vs `complete` naming; scattered error handling patterns
3. **No Shell Completion**: `completion_setup.sh` exists but not integrated into CLI
4. **No Interactive Mode**: Users must memorize complex syntax for task creation
5. **Validation Disabled**: `Todo.__post_init__` has commented-out validation, `utils/validation.py` at 0% coverage
6. **Type Checking Permissive**: mypy configured with `ignore_missing_imports = true`, no enforcement
7. **Error Handling Inconsistent**: `sys.exit(1)` in some commands, silent returns in others, `print()` used for errors in storage.py
8. **No Input Sanitization**: CLI commands lack defensive input validation
9. **Missing Alias System**: No shortcuts for common operations
10. **Help Quality**: Click's auto-help doesn't showcase the rich feature set well
11. **Pydantic Deprecation**: V1 patterns (`@validator`, `.dict()`) scattered throughout codebase
12. **Storage Not Atomic**: `save_project` writes directly without temp file + rename pattern
13. **Storage uses `print()` for errors**: Lines 471, 490-497, 510 in storage.py use bare print instead of Rich console
14. **Storage lacks file locking**: No protection against concurrent access
15. **TodoMarkdownFormat.from_markdown uses regex-only parsing**: Missing fields (energy_level, time_estimate, description, etc.) are not parsed back from markdown
16. **Recurring tasks use module-level global**: `recurring_manager = RecurringTaskManager()` at line 51 of tasks.py prevents proper testing
17. **AI/voice commands create own Console instances**: Don't use themed console (`_get_console()` in ai_commands.py vs `get_console()` in tasks.py)

---

## Improvement Plan

### Phase 1: Simplify User Interaction (High Impact)

#### 1.1 Shell Completion Setup
**Goal**: Zero-friction tab completion for all shells (bash, zsh, fish)

- [ ] Create `todo completion install` command that auto-detects shell and installs completion script
- [ ] Create `todo completion show` command that outputs completion script for current shell
- [ ] Update `completion_setup.sh` to be idempotent (safe to run multiple times)
- [ ] Support Click's built-in completion via `@click.shell_completion` decorator
- [ ] Add completion for: commands, options, project names, saved queries, tags, contexts

**Files**: `src/todo_cli/cli/completion.py` (new), update `src/todo_cli/cli/tasks.py`

#### 1.2 Command Aliases System
**Goal**: Users can create shortcuts for complex commands

- [ ] Add `todo alias` command group:
  - `todo alias list` - Show all aliases
  - `todo alias set <name> <command>` - Create alias (e.g., `todo alias set ls "list --overdue"`)
  - `todo alias remove <name>` - Delete alias
- [ ] Implement alias resolution in CLI entry point before Click parsing
- [ ] Store aliases in `~/.todo/aliases.yaml`
- [ ] Pre-define useful aliases:
  - `ls` → `list`
  - `rm` → `bulk delete`
  - `mv` → `bulk project`
  - `co` → `done` (complete)

**Files**: `src/todo_cli/cli/aliases.py` (new), `src/todo_cli/config.py`, `~/.todo/aliases.yaml`

#### 1.3 Interactive Mode
**Goal**: Guided task creation for new users

- [ ] Add `todo interactive` or `todo i` command
- [ ] Step-by-step prompts:
  1. "What's the task?" → text input
  2. "Which project?" → tab-complete from existing projects
  3. "Priority?" → [critical/high/medium/low]
  4. "Due date?" → natural language input
  5. "Tags?" → suggest from existing tags
- [ ] Show preview before saving
- [ ] Use `questionary` or `prompt_toolkit` for interactive prompts

**Files**: `src/todo_cli/cli/interactive.py` (new)

#### 1.4 Improved Help System
**Goal**: Better command discovery and contextual help

- [ ] Create custom Click help formatter with:
  - Command categories (Task Management, Organization, Integrations, Settings)
  - Quick start examples at top of `todo --help`
  - "Did you mean?" suggestions for typos
- [ ] Add `todo quick-start` command showing 5 most useful commands
- [ ] Add `--help` on root to show categorized commands instead of alphabetical list
- [ ] Implement command aliases in help text

**Files**: `src/todo_cli/cli/help.py` (new), modify `src/todo_cli/cli/tasks.py` main group

#### 1.5 Command Naming Consistency
**Goal**: All commands follow consistent verb-noun pattern

- [ ] Rename `done` → `complete` (add `done` as deprecated alias)
- [ ] Ensure all commands use consistent option naming:
  - Use `--project` consistently (not `-p` in some, `--project` in others)
  - Standardize short flags across commands
- [ ] Add deprecation warnings for renamed commands

**Files**: `src/todo_cli/cli/tasks.py`

---

### Phase 2: Harden the CLI (Quality & Reliability)

#### 2.1 Input Validation & Sanitization
**Goal**: Defensive handling of all user inputs

- [ ] Add validation for:
  - Task text length (max 500 chars)
  - Project names (alphanumeric, hyphens, underscores only)
  - Tag names (no special characters)
  - Date parsing (graceful fallback on invalid dates)
  - ID ranges (prevent negative or non-existent IDs)
- [ ] Create `src/todo_cli/validators.py` with reusable validators
- [ ] Add Click validators via custom parameter types
- [ ] Enable and fix the commented-out validation in `Todo.__post_init__`

**Files**: `src/todo_cli/validators.py` (new), `src/todo_cli/domain/todo.py`, all CLI command files

#### 2.2 Consistent Error Handling
**Goal**: Uniform error messages with actionable suggestions

- [ ] Create custom exception hierarchy:
  - `TodoCLIError` (base)
  - `TaskNotFoundError`
  - `ProjectNotFoundError`
  - `ValidationError`
  - `StorageError`
- [ ] Create centralized error handler in CLI entry point
- [ ] Standardize error output format:
  ```
  ❌ Error: Task 42 not found in any project
  💡 Try: todo list to see available tasks
  ```
- [ ] Add `--debug` flag for stack traces
- [ ] Handle all `sys.exit(1)` calls through central handler

**Files**: `src/todo_cli/exceptions.py` (new), `src/todo_cli/cli/tasks.py`

#### 2.3 Enable Type Checking
**Goal**: Catch bugs before runtime

- [ ] Update `pyproject.toml` mypy config:
  - Remove `ignore_missing_imports = true`
  - Add per-module ignore for third-party libs without stubs
  - Enable `strict_optional = true`
  - Enable `disallow_untyped_defs = true`
- [ ] Fix type errors in existing code
- [ ] Add mypy to pre-commit hooks
- [ ] Add type stubs for custom modules

**Files**: `pyproject.toml`, all `.py` files with type errors

#### 2.4 Test Coverage Improvements
**Goal**: Test the CLI layer, not just domain logic

- [ ] Add CLI integration tests using Click's `CliRunner`
- [ ] Test command combinations and edge cases:
  - `todo add` with various natural language inputs
  - `todo list` with all filter combinations
  - `todo bulk` operations
  - `todo export` with all formats
- [ ] Add tests for error handling paths
- [ ] Add tests for alias resolution
- [ ] Add tests for shell completion

**Files**: `tests/test_cli_integration.py` (new), `tests/test_aliases.py` (new)

#### 2.5 Storage Hardening
**Goal**: Prevent data corruption and loss

- [ ] Add atomic writes (write to temp file, then rename)
- [ ] Add backup before destructive operations (delete, bulk delete)
- [ ] Validate file format on load (detect corrupted markdown)
- [ ] Add data migration system for future schema changes
- [ ] Add integrity checks for cross-references (depends_on, parent_id)
- [ ] Handle concurrent access (file locking)

**Files**: `src/todo_cli/storage.py`

#### 2.6 Performance Optimization
**Goal**: Fast CLI startup even with 1000+ tasks

- [ ] Profile CLI startup time
- [ ] Implement lazy loading for services (already partially done)
- [ ] Add caching for frequently accessed data (project lists, tags)
- [ ] Optimize `list` command for large task sets
- [ ] Add `--fast` mode that skips expensive operations

**Files**: `src/todo_cli/storage.py`, `src/todo_cli/cli/tasks.py`

---

### Phase 3: UX Polish (Delightful Experience)

#### 3.1 Quick Edit Mode
**Goal**: Edit task properties without full command syntax

- [ ] Add `todo edit <id>` command with interactive property editor
- [ ] Allow inline property updates:
  - `todo edit 5 --set priority=high`
  - `todo edit 5 --set due=tomorrow`
  - `todo edit 5 --set "text=New task text"`
- [ ] Show before/after preview

**Files**: `src/todo_cli/cli/edit.py` (new)

#### 3.2 Undo/Revert System
**Goal**: Recover from mistakes

- [ ] Add `todo undo` command (reverses last operation)
- [ ] Store operation history in `~/.todo/operations.log`
- [ ] Support undo for: add, complete, delete, bulk operations
- [ ] Add `todo history` to show recent operations

**Files**: `src/todo_cli/services/operation_history.py` (new), `src/todo_cli/cli/undo.py` (new)

#### 3.3 Smart Defaults
**Goal**: Less typing for common operations

- [ ] Remember last-used project (store in config)
- [ ] Remember last-used context
- [ ] Auto-suggest based on time of day (morning → work, evening → personal)
- [ ] Auto-complete task text from similar existing tasks

**Files**: `src/todo_cli/config.py`, `src/todo_cli/cli/tasks.py`

#### 3.4 Progress Indicators
**Goal**: Feedback for long operations

- [ ] Add progress bars for bulk operations
- [ ] Add spinner for sync/export operations
- [ ] Show ETA for recurring task generation
- [ ] Add quiet mode `--quiet` flag to suppress all output except errors

**Files**: Various CLI command files

---

## Implementation Order

1. **Start with Phase 2.2** (Error handling) - Foundation: centralized exceptions + `--debug` flag
2. **Then Phase 2.5** (Storage hardening) - Atomic writes + replace `print()` with Rich console + backup before destructive ops
3. **Then Phase 2.1** (Input validation) - Enable commented-out validators + Click custom types
4. **Then Phase 1.5** (Command naming) - Rename `done` → `complete` with deprecation alias
5. **Then Phase 1.1** (Shell completion) - Click's built-in `@click.shell_completion`
6. **Then Phase 1.4** (Help system) - Categorized help + "did you mean?"
7. **Then Phase 1.2** (Aliases) - Command shortcuts system
8. **Then Phase 2.3** (Type checking) - Enable mypy strict mode incrementally
9. **Then Phase 2.4** (CLI tests) - Add CliRunner integration tests for commands
10. **Then Phase 1.3** (Interactive mode) - Guided task creation
11. **Then Phase 3.1** (Edit command) - Inline property editing
12. **Then Phase 3.2** (Undo system) - Operation history
13. **Then Phase 3.3** (Smart defaults) - Remember last project/context
14. **Then Phase 3.4** (Progress indicators) - Spinners + `--quiet` flag
15. **Then Phase 2.6** (Performance) - Profile + cache + lazy loading

## Risk Assessment

- **Low Risk**: Command naming, help system, shell completion, progress indicators
- **Medium Risk**: Input validation (may break existing workflows), type checking, storage atomic writes
- **Higher Risk**: Storage hardening (data migration), undo system (complex state management), interactive mode (new dependency)

## Quick Wins (First Session)
These can be completed in a single session and provide immediate value:
1. Add `--debug` flag to root CLI group (expose stack traces)
2. Replace `print()` calls in storage.py with Rich console error output
3. Create custom exception hierarchy
4. Add centralized error handler with actionable suggestions
5. Rename `done` → `complete` with `done` as deprecated alias

## Success Metrics

- [ ] CLI help is categorized and discoverable
- [ ] Tab completion works for all commands and options
- [ ] All user inputs are validated with helpful error messages
- [ ] Error messages include actionable suggestions
- [ ] mypy passes with strict mode
- [ ] Test coverage > 80% for CLI layer
- [ ] Storage operations are atomic and backed up
- [ ] Users can create and use command aliases
- [ ] Interactive mode guides new users
- [ ] Undo works for common operations
- [ ] Zero Pydantic deprecation warnings
- [ ] `done` command shows deprecation warning pointing to `complete`
- [ ] All 705 tests still pass after changes
- [ ] Coverage improves from 42% baseline (especially CLI layer and storage)
