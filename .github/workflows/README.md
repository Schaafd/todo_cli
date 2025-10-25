# GitHub Actions CI/CD Workflows

This directory contains automated workflows for continuous integration and deployment.

## Workflows

### 1. CI Workflow (`ci.yml`)

**Triggers:** Push to `main`/`develop` branches, Pull Requests

**Jobs:**

#### Lint and Format Check
- Black code formatting verification
- isort import sorting verification  
- flake8 linting

#### Type Check
- MyPy static type checking on `src/` directory

#### Test Suite
- **Matrix:** Ubuntu + macOS, Python 3.11 + 3.12
- Runs pytest with coverage reporting
- Uploads coverage to Codecov
- Uploads test artifacts

#### PWA Quality Check
- JavaScript syntax validation for all PWA files
- Verifies PWA manifest and service worker exist
- Checks for console.log statements (warning only)

#### API Integration Tests
- Starts API server in background
- Tests `/health`, `/api/tasks`, `/api/contexts` endpoints
- Verifies API is responding correctly

#### Build Verification
- Builds Python package with `uv build`
- Verifies CLI installation and basic commands
- Uploads build artifacts

#### Security Scan
- Runs `pip-audit` for known vulnerabilities (non-blocking)

#### All Checks Passed
- Final gate ensuring all required jobs succeeded
- Blocks merging if any critical check fails

---

### 2. PR Quality Checks (`pr-checks.yml`)

**Triggers:** Pull Request opened, synchronized, or reopened

**Jobs:**

#### PR Title Convention Check
- Enforces semantic commit format
- Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`
- Example: `feat: Add notification system`

#### PR Size Labeling
- Automatically labels PR by size:
  - `size/xs`: 0-10 lines
  - `size/s`: 11-100 lines
  - `size/m`: 101-500 lines
  - `size/l`: 501-1000 lines
  - `size/xl`: 1000+ lines

#### Code Coverage Check
- Runs tests with coverage
- Comments coverage report on PR
- Minimum targets:
  - Green: 70%+
  - Orange: 50-70%
  - Red: <50%

#### Dependency Review
- Scans for vulnerable dependencies
- Blocks moderate+ severity vulnerabilities
- Denies GPL-3.0 and AGPL-3.0 licenses

#### Changelog Check
- Ensures CHANGELOG.md is updated (except for docs-only changes)
- Comments on PR if missing

#### Code Complexity Check
- Analyzes cyclomatic complexity with radon
- Checks maintainability index
- Warns on overly complex functions (non-blocking)

---

## Status Badges

Add these to your README.md:

```markdown
[![CI](https://github.com/Schaafd/todo_cli/workflows/CI/badge.svg)](https://github.com/Schaafd/todo_cli/actions/workflows/ci.yml)
[![PR Checks](https://github.com/Schaafd/todo_cli/workflows/PR%20Quality%20Checks/badge.svg)](https://github.com/Schaafd/todo_cli/actions/workflows/pr-checks.yml)
[![codecov](https://codecov.io/gh/Schaafd/todo_cli/branch/main/graph/badge.svg)](https://codecov.io/gh/Schaafd/todo_cli)
```

---

## Local Development

Run the same checks locally before pushing:

```bash
# Format code
uv run black .
uv run isort .

# Lint
uv run flake8 src/ tests/

# Type check
uv run mypy --config-file pyproject.toml src/

# Run tests with coverage
uv run python -m pytest --cov=src/todo_cli --cov-report=term-missing

# Check JavaScript syntax
find src/todo_cli/web/static/js -name "*.js" -exec node -c {} \;

# Build package
uv build

# Verify CLI
uv run todo --version
uv run todo --help
```

### Pre-commit Hooks

Install pre-commit hooks to run checks automatically:

```bash
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files
```

---

## Required Secrets

### For Codecov (optional)

Add `CODECOV_TOKEN` to repository secrets:
1. Go to [codecov.io](https://codecov.io)
2. Add your repository
3. Copy the token
4. Add to GitHub: Settings → Secrets → Actions → New repository secret

---

## Troubleshooting

### Job Failures

**Lint/Format Failures:**
```bash
# Fix automatically
uv run black .
uv run isort .
```

**Test Failures:**
```bash
# Run tests locally with verbose output
uv run python -m pytest -vv

# Run specific failing test
uv run python -m pytest tests/test_specific.py::test_function -vv
```

**Type Check Failures:**
```bash
# Run mypy locally
uv run mypy --config-file pyproject.toml src/

# Check specific file
uv run mypy src/todo_cli/specific_file.py
```

**API Integration Test Failures:**
```bash
# Test API locally
uv run uvicorn src.todo_cli.web.server:app --host 127.0.0.1 --port 8000

# In another terminal, test endpoints
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/tasks
```

### Skipping CI for Commits

Add `[skip ci]` to commit message to skip CI:
```bash
git commit -m "docs: Update README [skip ci]"
```

---

## Adding New Checks

### Python Quality Check

Edit `.github/workflows/ci.yml`:

```yaml
- name: Your New Check
  run: |
    uv run your-tool-here
```

### PWA/JavaScript Check

Add to `pwa-check` job in `ci.yml`:

```yaml
- name: Your PWA Check
  run: |
    # Your commands here
```

### PR-specific Check

Add new job to `.github/workflows/pr-checks.yml`:

```yaml
your-check:
  name: Your Check Name
  runs-on: ubuntu-latest
  steps:
    - name: Checkout code
      uses: actions/checkout@v4
    - name: Run your check
      run: |
        # Your commands
```

---

## Best Practices

1. **Keep jobs fast**: Use caching for dependencies
2. **Fail fast**: Set `continue-on-error: false` for critical checks
3. **Matrix testing**: Test across OS and Python versions
4. **Artifact upload**: Save important files for debugging
5. **Clear naming**: Use descriptive job and step names
6. **Dependencies**: Specify job dependencies with `needs:`

---

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [uv Documentation](https://github.com/astral-sh/uv)
- [pytest Documentation](https://docs.pytest.org/)
- [codecov Documentation](https://docs.codecov.com/)
