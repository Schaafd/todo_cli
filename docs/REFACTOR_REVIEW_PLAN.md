# Todo CLI In-Depth Refactor Review & Improvement Plan

## Executive Summary

The application has impressive feature breadth, but the current implementation has signs of **feature accretion without strong architectural boundaries**. The biggest opportunities are:

1. **Decompose large mixed-responsibility modules** (especially CLI + storage + sync).
2. **Establish stronger domain and validation invariants** (currently partially disabled).
3. **Normalize error handling, logging, and dependency wiring**.
4. **Reduce duplicated parsing/serialization logic and tighten typed interfaces**.
5. **Introduce a staged modernization roadmap with measurable quality gates**.

---

## What I Reviewed

- Project/package layout and dependencies.
- CLI entrypoint and command module structure.
- Domain model quality and invariants.
- Storage parsing/serialization strategy.
- Sync subsystem boundaries.
- AI provider abstraction and integration style.

---

## Key Refactor Opportunities

### 1) Strengthen module boundaries and layering

**Current signals**
- The CLI module `tasks.py` performs command wiring, formatting, parsing orchestration, storage access, and business behavior directly. This creates a “god module” risk over time.
- Service and sync modules include both domain logic and infrastructure concerns in single files.

**Refactor direction**
- Adopt a simple layered structure:
  - `domain/` (entities, value objects, invariants)
  - `application/` (use-cases / command handlers)
  - `infrastructure/` (file storage, adapters, provider clients)
  - `interfaces/cli` and `interfaces/web`
- Keep Click command functions thin and delegate behavior to application services.

**Outcome**
- Better testability, easier feature additions, reduced merge conflicts.

### 2) Re-enable and formalize domain validation

**Current signals**
- The `Todo` model explicitly has validation disabled (`pass` with comment about temporary disable), indicating invariants are not enforced consistently.

**Refactor direction**
- Introduce explicit validation methods or pydantic-backed command DTOs before entity construction.
- Reinstate invariant checks in `__post_init__` for status/completed/progress/date consistency.
- Add regression tests for parsing edge cases that previously required disabling validation.

**Outcome**
- Less silent data corruption and fewer downstream bugs.

### 3) Split storage concerns and harden parsing contracts

**Current signals**
- `storage.py` combines: dependency fallback import logic, markdown parsing, ID comment rewriting, repository-like operations, and time/date normalization.
- Frontmatter fallback and markdown reconstruction are mixed with business mapping.

**Refactor direction**
- Extract into focused modules:
  - `storage/frontmatter_codec.py`
  - `storage/markdown_task_codec.py`
  - `storage/repository.py`
- Add a formal `TodoSerializationError` hierarchy and avoid silent exception swallowing where possible.
- Add round-trip property tests (`Todo -> markdown -> Todo`) with fixtures.

**Outcome**
- More reliable persistence and easier migration to alternate backends.

### 4) Standardize error handling and logging

**Current signals**
- Mixed patterns: direct `print`, `sys.exit`, broad `except Exception`, and inconsistent user-facing error reporting.

**Refactor direction**
- Introduce a unified error taxonomy (config, validation, storage, provider/network, auth).
- Route infrastructure logs through `logging` with configurable verbosity.
- Keep CLI layer responsible for presentation and exit codes only.

**Outcome**
- Debuggability in production and cleaner user error messages.

### 5) Improve sync architecture for extensibility

**Current signals**
- `sync/service.py` contains many enums, dataclasses, adapter logic, provider branching, and filesystem/process concerns in one place.

**Refactor direction**
- Split into:
  - sync domain models (`sync/models.py`)
  - conflict engine (`sync/conflicts.py`)
  - provider interface (`sync/providers/base.py`)
  - provider implementations (`sync/providers/*.py`)
  - orchestration service (`sync/service.py`)
- Prefer explicit capability interfaces (e.g., supports incremental sync, supports delete propagation).

**Outcome**
- Easier provider onboarding and fewer regressions across adapters.

### 6) Tighten AI integration boundaries

**Current signals**
- AI service API is a good start, but prompt construction, provider config resolution, and JSON parsing fallback are concentrated in one class.

**Refactor direction**
- Separate:
  - `ai/providers/*`
  - `ai/prompts/*`
  - `ai/parsers/*`
  - `ai/use_cases/*`
- Add contract tests with deterministic fake providers to validate structured outputs.

**Outcome**
- Safer upgrades of provider SDKs/models and more predictable behavior.

### 7) Reduce duplication across interfaces (CLI/Web/iOS)

**Current signals**
- Multiple entry points imply risk of duplicated business rules drifting across command, API, and mobile-support code.

**Refactor direction**
- Move core use-cases into application layer and expose them to CLI + API with shared DTOs.
- Keep transport-specific mapping in interface layers only.

**Outcome**
- Single source of truth for behavior.

---

## Proposed Implementation Plan (Phased)

### Phase 1 (1–2 weeks): Safety + Baseline
- Add architectural decision record (ADR) for layering and coding conventions.
- Re-enable validation with feature flag if needed (`strict_validation=false` default).
- Introduce centralized error types and logging scaffold.
- Add key characterization tests around add/list/done flows and markdown round-trip.

### Phase 2 (2–3 weeks): Structural Extraction
- Extract storage codecs/repository.
- Extract CLI command handlers into application services.
- Split sync models/interfaces from implementation.

### Phase 3 (2–4 weeks): Provider & Integration Cleanup
- Refactor sync providers to explicit contracts.
- Refactor AI providers/prompts/parsers with contract tests.
- Add dependency injection container/factory for CLI + API bootstrap.

### Phase 4 (ongoing): Quality Gates and Performance
- Add CI gates: mypy (incremental strictness), coverage thresholds by package, lint.
- Add smoke benchmarks for loading large project files and sync throughput.
- Add observability for failures (structured logs + optional telemetry hooks).

---

## Recommended Priorities

1. **P0:** Domain validation and storage round-trip correctness.
2. **P1:** CLI/application decoupling and unified error handling.
3. **P1:** Sync decomposition for maintainability.
4. **P2:** AI boundary cleanup and shared DTOs across interfaces.

---

## Suggested Success Metrics

- 30–50% reduction in average module size for top 5 largest Python files.
- 90%+ pass rate on new round-trip/characterization tests before major refactors.
- Fewer broad `except Exception` usages in application logic.
- Reduced change surface: feature PRs touch fewer layers/files on average.

