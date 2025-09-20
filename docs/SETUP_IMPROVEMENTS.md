# App Sync Setup Improvements

## Problem Resolved

The `todo app-sync setup todoist` command was hanging during the interactive project mapping phase. Users with many local projects (in this case, 9 projects) would experience a "hang" while the CLI was actually waiting for user input to map each project to Todoist projects.

## Root Cause

The hang occurred because:

1. **Silent prompts**: The CLI waited for user input without clear indication
2. **No non-interactive fallback**: The setup always tried to be interactive
3. **Many projects**: Users with multiple projects faced lengthy interactive sessions
4. **No timeout handling**: Network operations could hang indefinitely
5. **Terminal compatibility**: Some terminals/environments don't handle interactive prompts well

## Solutions Implemented

### 1. Enhanced CLI Options

```bash
# New options added to setup command:
uv run todo app-sync setup todoist --help

Options:
  --interactive / --no-interactive    Auto-detected if not specified
  --skip-mapping                     Skip project mapping
  --timeout INTEGER                  Network timeout in seconds (default: 60)
```

### 2. Auto-Detection of Interactive Environment

The CLI now automatically detects whether it's running in an interactive terminal:

```bash
# Interactive terminal - shows mapping prompts
uv run todo app-sync setup todoist

# Non-interactive (CI, pipes) - skips prompts automatically  
echo "data" | uv run todo app-sync setup todoist
```

### 3. Improved Project Mapping UX

- **Bulk mapping option**: Map all projects to one Todoist project at once
- **Clear progress indication**: Shows what's happening during setup
- **Skip confirmation**: Ask before starting lengthy mapping process
- **Better error handling**: Graceful failures with helpful messages

### 4. Network Timeout Handling

All network operations now have configurable timeouts:

```bash
# Use longer timeout for slow connections
uv run todo app-sync setup todoist --timeout 120
```

### 5. New Doctor Command

Added comprehensive diagnostics:

```bash
uv run todo app-sync doctor
```

This checks:
- Environment and Python version
- Configuration directory permissions
- Network connectivity to Todoist API
- API token validity
- Provides troubleshooting suggestions

## Usage Examples

### Quick Setup (Non-Interactive)
```bash
export TODOIST_API_TOKEN="your_token_here"
uv run todo app-sync setup todoist --no-interactive
```

### Interactive Setup with Bulk Mapping
```bash
export TODOIST_API_TOKEN="your_token_here"
uv run todo app-sync setup todoist --interactive
# Choose "y" for bulk mapping when prompted
```

### Skip Project Mapping
```bash
uv run todo app-sync setup todoist --skip-mapping
# Set up mapping later with: todo app-sync map-project
```

### Troubleshooting
```bash
# Run diagnostics first
uv run todo app-sync doctor

# Then try setup with verbose output and longer timeout
uv run todo app-sync setup todoist --timeout 120 --no-interactive
```

## Backward Compatibility

All existing commands work as before:
- Default behavior is now smarter (auto-detects environment)
- Interactive mode still available when running in proper terminals
- Non-interactive mode is automatically used in scripts/CI

## Testing

The improvements have been tested with:
- ✅ Non-interactive environments (CI, scripts)
- ✅ Interactive terminals with TTY
- ✅ Network timeout scenarios
- ✅ Multiple local projects (9 projects tested)
- ✅ Bulk and individual project mapping
- ✅ Error conditions and edge cases

## Migration

No migration needed! The improvements are backward-compatible:

- Old command still works: `uv run todo app-sync setup todoist`
- New options are optional and have sensible defaults
- Auto-detection makes the experience smoother without changes