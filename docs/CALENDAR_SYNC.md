# Calendar Integration and Sync Documentation

This document describes the calendar integration and multi-device synchronization features of the Todo CLI application.

## Overview

The Todo CLI now includes comprehensive calendar integration and multi-device synchronization capabilities as part of **Phase 4: Smart Integration Features**. These features allow you to:

- **Calendar Integration**: Sync your todos with popular calendar applications (iCal, Google Calendar, Apple Calendar)
- **Multi-Device Sync**: Keep your todos synchronized across multiple devices using various cloud providers or Git repositories
- **Conflict Resolution**: Handle sync conflicts intelligently with customizable strategies
- **Offline Support**: Continue working offline with automatic sync when connectivity is restored

## Calendar Integration

### Supported Calendar Types

- **iCal (.ics files)**: Standard calendar format supported by most calendar applications
- **Apple Calendar**: Native macOS Calendar app integration using AppleScript
- **Google Calendar**: Integration with Google Calendar (planned)
- **Local File**: Simple file-based calendar storage

### Calendar Commands

#### List Calendars
```bash
todo calendar list
```
Shows all configured calendar integrations with their status and last sync time.

#### Add Calendar Integration
```bash
todo calendar add --name "my-calendar" --type ical --path "/path/to/calendar.ics"
todo calendar add --name "work-cal" --type apple_calendar --sync export_only
```

Options:
- `--name`: Unique name for the calendar integration
- `--type`: Calendar type (ical, apple_calendar, google_calendar, local_file)
- `--path`: File path for file-based calendars
- `--sync`: Sync direction (import_only, export_only, bidirectional)
- `--conflicts`: Conflict resolution (todo_wins, calendar_wins, manual, newest_wins)

#### Sync with Calendars
```bash
todo calendar sync                    # Sync all calendars
todo calendar sync --name my-calendar # Sync specific calendar
```

#### Calendar Status
```bash
todo calendar status                    # Show all calendar status
todo calendar status --name my-calendar # Show specific calendar status
```

### Calendar Event Features

When todos are synced to calendars, they become calendar events with:

- **Title**: Todo text
- **Description**: Todo description plus metadata (assignees, waiting for, URL)
- **Start/End Time**: Based on due date and time estimate
- **Location**: Todo location field
- **Custom Fields**: Todo ID, project, priority, and tags are preserved

### Calendar Sync Filtering

You can configure which todos get synced to calendars:

- **Project filtering**: Only sync specific projects
- **Tag filtering**: Only sync todos with specific tags
- **Completion status**: Include/exclude completed tasks
- **Date range**: Only sync recent todos

## Multi-Device Synchronization

### Supported Sync Providers

- **Local File**: Sync via shared filesystem (useful for network drives)
- **Git Repository**: Use Git for version-controlled synchronization
- **Dropbox**: Cloud storage sync (planned)
- **Google Drive**: Google Drive integration (planned)
- **iCloud**: Apple iCloud sync (planned)

### Sync Commands

#### Setup Sync
```bash
# Local file sync
todo sync setup --provider local_file --path "/shared/todos"

# Git repository sync
todo sync setup --provider git --path "/path/to/git/repo"
```

Options:
- `--provider`: Sync provider type
- `--path`: Sync location (directory or repository URL)
- `--auto/--manual`: Enable/disable automatic sync
- `--conflicts`: Conflict resolution strategy

#### Manual Sync
```bash
todo sync now                    # Full bidirectional sync
todo sync now --direction push   # Push local changes only
todo sync now --direction pull   # Pull remote changes only
```

#### Sync Status
```bash
todo sync status
```
Shows sync configuration, last sync time, and any pending conflicts.

#### Conflict Management
```bash
todo sync conflicts              # List all conflicts
todo sync conflicts --resolve 123 --using local   # Resolve using local version
todo sync conflicts --resolve 123 --using remote  # Resolve using remote version
```

#### Sync History
```bash
todo sync history --limit 20
```
Shows recent sync operations with status and change counts.

### Conflict Resolution Strategies

1. **local_wins**: Local changes always take precedence
2. **remote_wins**: Remote changes always take precedence  
3. **newest_wins**: Most recently modified version wins
4. **manual**: User manually resolves each conflict
5. **merge**: Attempt intelligent merging (planned)

### Device Identity

Each device gets a unique device ID that's used to:
- Track which changes came from which device
- Avoid syncing a device's own changes back to itself
- Maintain sync history per device

## Configuration

### Calendar Configuration Storage

Calendar configurations are stored in the application's data directory:
- Calendar sync history: `~/.config/todo-cli/calendar_sync_history.json`
- Calendar configurations: Stored in the main configuration

### Sync Configuration Storage

Sync configurations and state are stored in:
- Device ID: `~/.config/todo-cli/sync/device_id.txt`
- Sync history: `~/.config/todo-cli/sync/sync_history.json`
- Pending conflicts: `~/.config/todo-cli/sync/conflicts.json`

## Best Practices

### Calendar Integration

1. **Start with Export Only**: Begin with `export_only` sync to avoid importing unwanted events
2. **Use Project Filtering**: Only sync work todos to work calendar, personal todos to personal calendar
3. **Set Conflict Strategy**: Use `newest_wins` for automatic conflict resolution
4. **Regular Sync**: Run `todo calendar sync` regularly or set up automatic sync

### Multi-Device Sync

1. **Choose Appropriate Provider**: Use Git for version control, local file for simplicity
2. **Handle Conflicts Promptly**: Resolve sync conflicts as soon as they appear
3. **Backup Before Major Changes**: Create backups before significant todo reorganizations
4. **Test Sync Setup**: Use `todo sync status` to verify setup before relying on it

## Troubleshooting

### Calendar Issues

**Calendar not available**: Check file paths and permissions
**Sync failures**: Verify calendar application is installed and accessible
**Missing events**: Check sync direction and filtering settings

### Sync Issues

**Device not syncing**: Verify network connectivity and provider access
**Conflicts not resolving**: Use manual conflict resolution for complex cases
**Sync failures**: Check provider credentials and path accessibility

### Common Solutions

1. **Check Status**: Use status commands to diagnose issues
2. **Review History**: Check sync/calendar history for error patterns
3. **Test Connectivity**: Verify provider access independently
4. **Reset if Needed**: Remove and re-add problematic integrations

## Examples

### Complete Setup Example

```bash
# Set up calendar integration
todo calendar add --name "work" --type ical --path "~/calendars/work.ics" --sync export_only

# Set up multi-device sync
todo sync setup --provider git --path "~/sync-repo" --conflicts newest_wins

# Test the setup
todo calendar status
todo sync status

# Perform initial sync
todo calendar sync
todo sync now

# Check for any issues
todo sync conflicts
```

### Workflow Integration

```bash
# Morning routine: pull latest changes
todo sync now --direction pull

# Add some todos during the day
todo add "Team meeting @work due today"
todo add "Review PR #urgent @code"

# Evening routine: sync everything
todo calendar sync
todo sync now

# Check status before leaving
todo sync status
todo calendar status
```

This completes the calendar integration and sync functionality for Phase 4 of the Todo CLI project.