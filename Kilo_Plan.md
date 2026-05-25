# Plan: Simplify and Harden Todo CLI

Updated: 2026-05-24

## Intent

Make the CLI easier to use without dumbing it down:

- The common path should be obvious: add, list, finish, edit, delete, search.
- Advanced features should still exist, but they should not dominate first-run help.
- Data should be safe by default. A failed save, partial write, bad input, or interrupted bulk operation should not corrupt the todo store.
- Implementation should preserve existing users and tests unless there is a clear reason to break compatibility.

## Current Verified Baseline

Checked against the repo on 2026-05-24.

- Version: `todo-cli` 0.2.0 in `pyproject.toml`.
- Entry point: `todo = "todo_cli.cli:main"`, which delegates to `src/todo_cli/cli/tasks.py`.
- Root CLI surface: 37 root commands.
- Nested command surface: 93 subcommands under groups.
- Main CLI file size: `src/todo_cli/cli/tasks.py` is about 2,000 lines.
- Tests collected: 905.
- Test status: `uv run python -m pytest -q` passes.
- Coverage: 45% overall from `uv run python -m pytest --cov=todo_cli --cov-report=term-missing -q`.
- CLI coverage is the biggest gap. Many command modules are at 0%, including `tasks.py`, `backup.py`, `calendar.py`, `context.py`, `dependencies.py`, `tags.py`, `theme_cmds.py`, and `web.py`.
- Storage coverage is 65%.
- Existing error taxonomy already exists in `src/todo_cli/core/errors.py`.
- Existing validation utility exists in `src/todo_cli/utils/validation.py`, but it is datetime-focused and untested.
- `Todo.validate_datetimes()` is still commented out in `src/todo_cli/domain/todo.py`.
- `Storage.save_project()` writes directly to the project file. It does not use temp-file-plus-replace.
- `src/todo_cli/storage.py` still uses bare `print()` for load, save, delete, backup, and stats errors.
- Pydantic v2 deprecation warnings remain in theme code that still calls `.dict()`.
- Runtime warning noise also includes weak JWT test secrets and Starlette `TemplateResponse` deprecation warnings.

## Evaluation of the Original Plan

The original plan is directionally right: simplify command discovery, centralize errors, harden storage, add better tests, and improve validation.

I would change the execution strategy.

1. Do not start by adding more top-level features.
   The CLI already exposes 37 root commands. New root commands like `interactive`, `quick-start`, `alias`, `undo`, and `history` may help later, but they also make the first problem worse unless the command surface is cleaned up first.

2. Use what the repo already has.
   The plan proposed `src/todo_cli/exceptions.py`, but `src/todo_cli/core/errors.py` already exists. Extend that instead of creating a competing error module.

3. Do not deprecate `done` as an early move.
   `todo done 1` is short and intuitive. Renaming it to `complete` for consistency is less useful than supporting both names while documenting one canonical path. If we add `complete`, make it a compatibility alias or hidden alias until user behavior says otherwise.

4. Avoid a broad user alias system in the first pass.
   Pre-Click alias expansion can create quoting, completion, debugging, and security problems. Start with a small set of built-in compatibility aliases only after the command taxonomy is stable.

5. Put storage safety before undo.
   Undo is useful, but it depends on trustworthy operation history and safe writes. Atomic storage, backups, and command-level tests should come first.

6. Treat strict typing as incremental.
   Removing `ignore_missing_imports = true` across the entire repo will create a large unrelated cleanup. Start with stricter checks on new or touched core modules, then expand.

7. Add tests with each behavioral change.
   The CLI layer is under-tested. Every command behavior change should land with `CliRunner` coverage using isolated temp config and data directories.

## Target Command Model

The user-facing CLI should feel small even if the product has many features.

Primary commands:

- `todo` - dashboard
- `todo add "task"` - natural-language task capture
- `todo list` - task list and filters
- `todo done <id>` - finish a task
- `todo edit <id>` - edit a task
- `todo delete <id>` - delete a task safely
- `todo search <query>` - search tasks
- `todo projects` - project list
- `todo help` or `todo --help` - practical command discovery

Grouped commands:

- `todo recurring ...`
- `todo sync ...`
- `todo app-sync ...`
- `todo backup ...`
- `todo theme ...`
- `todo doctor ...`
- `todo notify ...`
- `todo tag ...`
- `todo ctx ...`
- `todo dep ...`
- `todo focus ...`
- `todo ai ...`
- `todo web ...`

Compatibility policy:

- Keep existing command names working unless removal is explicitly approved.
- Prefer hiding legacy direct commands from help over deleting them.
- Convert standalone recurring commands such as `recurring-list` into grouped commands such as `todo recurring list`, while keeping old names as hidden aliases.
- Document one clear path per workflow.

## Updated Implementation Plan

### Phase 0: Baseline and Guardrails

Goal: lock down the current behavior before changing it.

- [x] Verify current test status.
- [x] Verify test count and coverage.
- [x] Verify visible command surface.
- [x] Add a small CLI smoke-test fixture using `CliRunner` with temp `data_dir`, `backup_dir`, and config.
- [x] Add smoke coverage for root `--help`, `add --dry-run`, and `list` before changing help behavior.
- [x] Add an isolated CLI fixture so new CLI tests avoid the real `~/.todo` directory.

Files:

- `tests/test_cli_smoke.py` new
- `tests/conftest.py`
- `docs/` or `README.md` if a maintainer note already has a natural home

Exit criteria:

- `uv run python -m pytest -q` passes.
- CLI tests prove `todo --help`, `todo add --dry-run`, `todo list`, and dashboard invocation can run without touching real user data.

### Phase 1: Hardening Foundation

Goal: make failures predictable and protect data.

#### 1.1 Central Error Handling

- [x] Extend `src/todo_cli/core/errors.py` rather than creating a new exception module.
- [x] Add missing specific errors where useful:
  - `TaskNotFoundError`
  - `ProjectNotFoundError`
  - `StorageError` with operation context
  - `CommandUsageError` only if Click's built-ins are not enough
- [x] Add root `--debug` flag.
- [x] Route expected application failures through one renderer:
  - short error message
  - optional suggestion
  - stack trace only with `--debug`
- [x] Convert core commands first: `add`, `quick`, `list`, `done`, `pin`, `bulk`, `projects`, `export`.
- [ ] Leave advanced command groups for later migration unless they block core behavior.

Files:

- `src/todo_cli/core/errors.py`
- `src/todo_cli/cli/tasks.py`
- optional `src/todo_cli/cli/error_handling.py`
- `tests/test_cli_errors.py` new

Exit criteria:

- Core commands no longer call `sys.exit(1)` directly for expected domain, validation, or storage errors.
- Error tests cover normal mode and `--debug`.

#### 1.2 Storage Safety

- [x] Replace direct project writes with atomic write:
  - write to a temp file in the same directory
  - flush and fsync
  - replace with `Path.replace()`
- [x] Raise or return typed storage failures consistently. Avoid silent `None, []` after corrupted reads unless the caller explicitly asks for recovery mode.
- [x] Replace bare `print()` calls in `storage.py` with structured error handling.
- [x] Add backup-before-destructive-operation support for project delete and bulk delete.
- [x] Add tests for interrupted write behavior using temp directories.
- [x] Add tests for duplicate ID rejection.
- [x] Add tests for corrupted markdown and missing project behavior.
- [ ] Defer file locking until atomic writes are in place unless concurrent corruption is reproducible.

Files:

- `src/todo_cli/storage.py`
- `src/todo_cli/core/errors.py`
- `tests/test_storage_hardening.py` new or extend existing storage tests

Exit criteria:

- Existing storage tests pass.
- New tests prove a failed write does not destroy the previous project file.
- Destructive operations create a recoverable backup.

#### 1.3 Input Validation

- [x] Define validation rules around data safety, not arbitrary neatness.
- [x] Validate path-sensitive names, lengths, and IDs:
  - task text cannot be empty
  - task text has a documented max length
  - project names cannot escape the project directory
  - tags and contexts cannot contain whitespace or control characters
  - IDs must be positive integers
- [x] Keep project/tag rules compatible with existing natural-language syntax.
- [x] Re-enable `Todo.validate_datetimes()` or replace it with an equivalent tested path.
- [x] Add Click parameter types only where they make command help and errors better.
  - Current decision: command-boundary validators are clearer than custom Click types for this slice.
- [x] Make dry-run and save paths use the same validation logic.

Files:

- `src/todo_cli/domain/todo.py`
- `src/todo_cli/application/task_commands.py`
- `src/todo_cli/utils/validation.py`
- `src/todo_cli/validation.py`
- `tests/test_validation.py` new

Exit criteria:

- Invalid input fails the same way in `todo add --dry-run` and normal `todo add`.
- Validation errors are helpful and do not show tracebacks unless `--debug` is set.

### Phase 2: Simplify the CLI Surface

Goal: make the product feel smaller and easier to learn.

#### 2.1 Help and Command Taxonomy

- [x] Replace alphabetical root help with categorized help:
  - Core
  - Views and Planning
  - Organization
  - Focus and Notifications
  - Integrations
  - Maintenance
  - Advanced
- [x] Put a short "common commands" block at the top of root help.
- [x] Hide compatibility aliases and legacy direct commands from root help.
- [x] Add typo suggestions for unknown commands if it can be done without fighting Click.
- [x] Keep examples concrete and short.

Files:

- `src/todo_cli/cli/tasks.py`
- `tests/test_cli_help.py` new

Exit criteria:

- `todo --help` shows the common path first.
- Root help no longer makes all integrations look as important as adding and finishing tasks.
- Existing commands still execute.

#### 2.2 Command Consolidation

- [x] Convert flat recurring commands into grouped recurring commands:
  - `todo recurring create`
  - `todo recurring list`
  - `todo recurring generate`
  - `todo recurring pause`
  - `todo recurring resume`
  - `todo recurring delete`
- [x] Preserve the old `todo recurring "task" "pattern"` create shorthand.
- [x] Keep current names as hidden aliases:
  - `recurring-list`
  - `recurring-generate`
  - `recurring-pause`
  - `recurring-resume`
  - `recurring-delete`
- [x] Decide whether `quick` is a distinct workflow or should become `todo add --simple`.
  - Decision: keep `quick` as a distinct capture workflow for now. It is short, explicit, and already behaves differently from natural-language `add`.
- [x] Add `complete` only as an alias for `done` if useful. Do not deprecate `done` yet.
  - Implemented as a hidden compatibility alias so root help still teaches `done`.
- [x] Audit short flags for conflicts. Standardize only the flags that appear in common commands.
  - Decision: keep current common flags. `-p` means project where present; `-t` remains command-local for tag/time; `-l` remains limit.

Files:

- `src/todo_cli/cli/tasks.py`
- `tests/test_cli_command_compatibility.py` new

Exit criteria:

- `todo recurring --help` presents the grouped workflow.
- Legacy recurring commands still pass compatibility tests.
- Root help keeps legacy recurring aliases hidden.

#### 2.3 Shell Completion

- [x] Add `todo completion show --shell <shell>` for bash, zsh, and fish.
- [x] Add `todo completion install` only after the generated scripts are tested.
- [x] Use Click's native completion for commands and options.
- [x] Add data-backed completion for projects, tags, contexts, and saved query names where practical.
- [x] Make install idempotent and reversible.
- [x] Avoid hand-maintaining separate completion scripts if Click's completion support is enough.
- [x] Keep completion script output free of startup/config noise.
- [x] Add `todo completion uninstall` for the generated script file.

Files:

- `src/todo_cli/cli/completion.py` new
- `src/todo_cli/cli/tasks.py`
- `src/todo_cli/config.py`
- `completion_setup.sh`
- `tests/test_cli_completion.py` new

Exit criteria:

- `todo completion show --shell zsh` works.
- `todo completion show --shell fish` works.
- `todo completion install --shell fish` writes an idempotent script.
- `todo completion uninstall --shell <shell>` removes the installed script.
- Completion generation does not load user data unless completing data-backed values.

### Phase 3: Right Features, Not More Features

Goal: add only the features that reduce user friction.

#### 3.1 Edit and Delete

- [x] Add `todo edit <id>` for common field updates.
- [x] Support simple setters:
  - `todo edit 5 --text "new text"`
  - `todo edit 5 --priority high`
  - `todo edit 5 --due tomorrow`
  - `todo edit 5 --project work`
- [x] Add `todo delete <id>` with confirmation unless `--yes` is supplied.
- [x] Backup before delete.
- [x] Consider interactive edit only after non-interactive edit is stable.
  - Decision: defer interactive edit. Non-interactive edit covers the mistake-fix path and is testable in scripts.

Files:

- `src/todo_cli/cli/tasks.py` or new focused command module
- `src/todo_cli/application/task_commands.py`
- `tests/test_cli_edit_delete.py` new

Exit criteria:

- Users can fix mistakes without editing markdown by hand.
- Deletes are recoverable.

#### 3.2 Undo

- [ ] Design undo around operation records only after storage is atomic.
- [ ] Start with one operation: undo last add.
- [ ] Then add undo for done, edit, and delete.
- [ ] Store enough before/after state to recover safely.
- [ ] Add `todo history` only if operation records prove useful.

Files:

- `src/todo_cli/services/operation_history.py` new
- `src/todo_cli/cli/tasks.py`
- `tests/test_cli_undo.py` new

Exit criteria:

- `todo undo` is safe, tested, and boring.

#### 3.3 Guided Add

- [ ] Prefer `todo add --interactive` over a new top-level `todo interactive` command.
- [ ] Add prompts for text, project, priority, due date, tags, and preview.
- [ ] Avoid adding `questionary` until `click.prompt` or current dependencies prove insufficient.
- [ ] Make guided mode optional and non-blocking in non-interactive shells.

Files:

- `src/todo_cli/cli/tasks.py` or `src/todo_cli/cli/interactive.py`
- `tests/test_cli_interactive.py` new

Exit criteria:

- New users can create a task without memorizing syntax.
- CI and scripts never hang on prompts.

### Phase 4: Code Health and Warning Cleanup

Goal: reduce maintenance drag without freezing feature work.

- [ ] Move command handlers out of the 2,000-line `tasks.py` file gradually, starting with recurring, export, and notification commands.
- [ ] Add stricter mypy checks to touched core modules first.
- [ ] Keep `ignore_missing_imports` globally until third-party stub gaps are mapped.
- [ ] Replace Pydantic `.dict()` with `.model_dump()` in theme and sync code.
- [ ] Fix Starlette `TemplateResponse` deprecation warnings.
- [ ] Use longer JWT secrets in tests to remove weak-key warnings.
- [ ] Add pre-commit checks only after local commands are stable and fast.

Files:

- `pyproject.toml`
- `src/todo_cli/theme_engine/*`
- `src/todo_cli/sync/*`
- `src/todo_cli/webapp/*`
- command modules as they are touched

Exit criteria:

- Warning count drops materially.
- Type checking improves on touched modules without creating a giant unrelated migration.

### Phase 5: Performance

Goal: optimize only measured problems.

- [ ] Measure startup time for:
  - `todo --help`
  - `todo`
  - `todo list`
  - `todo add --dry-run`
- [ ] Measure with empty data, 100 tasks, 1,000 tasks, and 10,000 tasks.
- [ ] Keep lazy imports for heavy integration modules.
- [ ] Add caches only where profiling shows repeat work.
- [ ] Avoid `--fast` until a specific slow path needs a user-visible escape hatch.

Files:

- `scripts/` benchmark helper if useful
- `src/todo_cli/cli/__init__.py`
- `src/todo_cli/cli/tasks.py`
- `src/todo_cli/storage.py`

Exit criteria:

- Startup and common command latency are measured and tracked.
- Any optimization has a benchmark or test proving the change.

## Proposed First Implementation Slice

Start here unless we decide to change direction:

1. Add isolated `CliRunner` smoke tests for root help, `add --dry-run`, and `list`.
2. Add `--debug` plumbing and a central expected-error renderer.
3. Extend `core.errors.py` with task, project, and storage-specific errors.
4. Convert `add`, `quick`, `done`, `pin`, and `bulk` to use typed expected errors instead of scattered `sys.exit(1)`.
5. Add atomic writes in `Storage.save_project()`.
6. Replace bare `print()` calls in `storage.py`.
7. Add storage tests for failed write, duplicate IDs, and delete backup behavior.

Why this slice:

- It hardens the path users rely on most.
- It creates the test harness needed for the later help and command taxonomy work.
- It avoids adding new UX features before the current UX is safer.

## Success Metrics

- `uv run python -m pytest -q` stays green.
- Core CLI commands have `CliRunner` coverage.
- Storage writes are atomic and tested.
- Destructive operations have recoverable backups.
- Root help shows the common path first.
- Root command help is categorized, not alphabetized noise.
- Legacy commands still work unless explicitly removed.
- `done` remains supported.
- `complete`, if added, is an alias rather than a breaking rename.
- Warning count is reduced from the current baseline.
- Coverage increases from the verified 45% baseline, with priority on CLI and storage coverage.

## Open Decisions Before Implementation

1. Canonical finish command: keep `done` as the documented command, or document `complete` and keep `done` as a hidden alias?
2. `quick`: keep as a separate command, or fold into `add --simple`?
3. Recurring commands: okay to group under `todo recurring ...` while keeping old names hidden?
4. Destructive operations: require confirmation by default even for scripts, or only when attached to a TTY?
5. How aggressive should root help be about hiding advanced integrations?
