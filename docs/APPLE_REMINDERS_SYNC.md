# Apple Reminders Sync Integration

## Overview

The Apple Reminders sync integration provides seamless bidirectional synchronization between your local todo CLI and the native Apple Reminders app on macOS. This integration uses AppleScript to communicate directly with the Reminders app, ensuring reliable and efficient sync without requiring external API keys or authentication.

## Features

### ✅ **Fully Supported**
- **Create, Read, Update, Delete**: Full CRUD operations for reminders
- **Lists Management**: Sync with Apple Reminders lists as projects
- **Due Dates**: Complete due date synchronization 
- **Priorities**: Priority mapping between systems
- **Descriptions**: Rich text descriptions and notes
- **Completion Status**: Bidirectional completion sync
- **Bidirectional Deletion**: Deletes in either place sync properly

### 🍎 **Apple Reminders Specific**
- **Native Integration**: Uses system AppleScript for reliable access
- **No Authentication**: Works with local system access only
- **Real-time Updates**: Changes appear immediately in Reminders app
- **Multiple Lists**: Support for organizing todos across different lists

## System Requirements

- **macOS 10.14+**: Required for Reminders AppleScript support
- **Apple Reminders App**: Must be installed and accessible
- **Terminal Privacy Access**: Terminal needs permission to access Reminders

## Setup Guide

### 1. Grant Privacy Permissions

Before setting up Apple Reminders sync, you need to grant privacy permissions:

1. Open **System Preferences** → **Security & Privacy** → **Privacy**
2. Select **"Reminders"** from the left sidebar
3. Check the box next to **Terminal** (or your shell application)
4. If Terminal isn't listed, click the **"+"** button and add it manually

### 2. Run Setup Command

```bash
todo app-sync setup apple_reminders
```

The setup wizard will:
- Test Apple Reminders access
- Display your available Reminders lists
- Configure sync settings
- Set up project-to-list mappings

### 3. Interactive Configuration

During setup, you'll be prompted to configure:

#### **Default List**
Choose which Reminders list should receive new todos by default:
```
Select default list for new todos:
  1. Reminders (default)
  2. Work
  3. Personal
```

#### **Completion Sync**
Choose whether to sync completed reminders:
```
Sync completed reminders? [Y/n]: y
```

#### **Project Mapping**
Map your local todo projects to Apple Reminders lists:
```
Found 3 local project(s):
  • inbox
  • work  
  • personal

Map 'inbox' to a Reminders list? [Y/n]: y
Select Reminders list for 'inbox':
  1. Reminders
  2. Work
  3. Personal
```

### 4. Verify Setup

Test the integration:
```bash
# Check sync status
todo app-sync status

# Run a test sync
todo app-sync sync apple_reminders
```

## Usage Examples

### Basic Synchronization

```bash
# Sync with Apple Reminders
todo app-sync sync apple_reminders

# Sync all configured providers (including Apple Reminders)
todo app-sync sync

# Auto-sync in background
todo app-sync auto-sync --enable apple_reminders
```

### Managing Lists and Projects

```bash
# List available Reminders lists
todo app-sync list-projects apple_reminders

# Map a local project to a specific list
todo app-sync map-project work "Work List"

# Create a new todo that syncs to specific list
todo add "Review quarterly reports" --project work
# This will appear in your mapped "Work List" in Apple Reminders
```

### Conflict Resolution

```bash
# View sync conflicts
todo app-sync conflicts

# Resolve conflicts interactively  
todo app-sync resolve-conflicts apple_reminders

# Set conflict resolution strategy
todo app-sync config apple_reminders --conflict-strategy newest_wins
```

## Data Mapping

### Project ↔ Lists
- **Local Projects** map to **Apple Reminders Lists**
- Unmapped projects go to the default list
- New lists in Apple Reminders are automatically discovered

### Priority Mapping
| Todo CLI | Apple Reminders | Description |
|----------|----------------|-------------|
| Low (1) | 7-9 | Low priority |
| Medium (2) | 5-6 | Normal priority |  
| High (3) | 3-4 | High priority |
| Critical (4) | 1-2 | High priority |

### Completion Status
- **Pending** ↔ **Incomplete Reminder**
- **Completed** ↔ **Completed Reminder**
- Completion dates are preserved when available

### Due Dates
- Full due date and time synchronization
- Timezone-aware handling
- All-day reminders supported

## Configuration Options

### Provider Settings

```bash
# Enable/disable Apple Reminders sync
todo app-sync config apple_reminders --enabled true

# Set sync direction
todo app-sync config apple_reminders --sync-direction bidirectional

# Configure conflict resolution
todo app-sync config apple_reminders --conflict-strategy newest_wins
```

### Apple Reminders Specific Settings

```bash
# Set default list for new todos
todo app-sync config apple_reminders --setting default_list_name="My Tasks"

# Enable/disable completed reminder sync
todo app-sync config apple_reminders --sync-completed true
```

## Troubleshooting

### Common Issues

#### 1. **Permission Denied**
```
❌ Apple Reminders access failed
This might be due to:
  • Privacy settings blocking access to Reminders
```

**Solution**: 
- Go to System Preferences → Security & Privacy → Privacy → Reminders
- Ensure Terminal is checked
- Restart Terminal and try again

#### 2. **AppleScript Timeout**
```
❌ AppleScript timed out
```

**Solution**:
- Close and reopen Reminders app
- Restart Terminal
- Check if Reminders app is responsive

#### 3. **Reminders Not Appearing**
**Possible Causes**:
- Project mapping not configured
- Default list not set properly
- Completed reminders filter active

**Solution**:
```bash
# Check mapping
todo app-sync status apple_reminders

# Re-run project mapping
todo app-sync setup apple_reminders --skip-authentication
```

#### 4. **Sync Conflicts**
```
⚠️  Conflicts detected: 3
```

**Solution**:
```bash
# View conflicts
todo app-sync conflicts apple_reminders

# Resolve automatically
todo app-sync resolve-conflicts apple_reminders --strategy newest_wins

# Resolve manually
todo app-sync resolve-conflicts apple_reminders --strategy manual
```

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set debug logging
export TODO_CLI_LOG_LEVEL=DEBUG

# Run sync with verbose output
todo app-sync sync apple_reminders --verbose
```

### Diagnostic Commands

```bash
# Run comprehensive diagnostics
todo app-sync doctor

# Test Apple Reminders connection
todo app-sync test-connection apple_reminders

# Clean up stale sync mappings
todo app-sync cleanup apple_reminders
```

## Advanced Configuration

### Custom AppleScript

For advanced users, you can modify the AppleScript behavior by understanding the adapter's structure:

```python
# Location: src/todo_cli/adapters/apple_reminders_adapter.py
# The AppleScriptInterface class contains all AppleScript commands

# Key methods:
# - get_reminders_lists(): Fetch all Reminders lists
# - get_reminders_in_list(): Get reminders from specific list  
# - create_reminder(): Create new reminder
# - update_reminder(): Update existing reminder
# - delete_reminder(): Delete reminder
```

### Project Mapping Strategies

#### 1. **One-to-One Mapping** (Recommended)
Each local project maps to its own Reminders list:
```
inbox → Reminders
work → Work  
personal → Personal
```

#### 2. **Consolidated Mapping**
Multiple projects map to one list:
```
inbox → Reminders
work → Reminders
personal → Reminders
```

#### 3. **Context-Based Mapping**
Map based on context:
```
urgent → High Priority
someday → Someday/Maybe
waiting → Waiting For
```

### Automation Tips

#### 1. **Scheduled Sync**
Set up automatic syncing with cron:
```bash
# Add to crontab (every 15 minutes)
*/15 * * * * /usr/local/bin/todo app-sync sync apple_reminders
```

#### 2. **Integration with Shortcuts**
Create macOS Shortcuts that trigger sync:
```applescript
tell application "Terminal"
    do script "todo app-sync sync apple_reminders"
end tell
```

## Best Practices

### 1. **Organize with Lists**
- Use Apple Reminders lists to organize different areas of life
- Map local projects to specific lists for better organization
- Consider lists like: Work, Personal, Shopping, Ideas

### 2. **Consistent Naming**  
- Keep project names consistent between local and Apple Reminders
- Use clear, descriptive list names
- Avoid special characters that might cause AppleScript issues

### 3. **Regular Sync**
- Sync regularly to avoid conflicts
- Enable auto-sync for seamless experience  
- Monitor sync status periodically

### 4. **Backup Strategy**
- Apple Reminders syncs with iCloud automatically
- Local todos are backed up with your regular todo CLI backups
- Consider exporting data periodically for additional safety

## Performance Notes

- **AppleScript Performance**: Generally fast for typical usage (< 100 reminders per list)
- **Large Lists**: Lists with 500+ reminders may experience slower sync times
- **Background Sync**: Minimal impact on system resources
- **Network Independence**: Works completely offline (no internet required)

## Migration Guide

### From Other Providers

If migrating from Todoist or another provider to Apple Reminders:

1. **Export Current Data**:
   ```bash
   todo export --format json > backup.json
   ```

2. **Set Up Apple Reminders**:
   ```bash
   todo app-sync setup apple_reminders
   ```

3. **Sync Existing Todos**:
   ```bash
   todo app-sync sync apple_reminders
   ```

4. **Verify Data Integrity**:
   - Check that all todos appear in Apple Reminders
   - Verify due dates and priorities are correct
   - Test bidirectional sync by making changes in both places

### To Apple Reminders

To migrate your existing Reminders to todo CLI:

1. **Set Up Sync**:
   ```bash
   todo app-sync setup apple_reminders
   ```

2. **Initial Sync**:
   ```bash
   todo app-sync sync apple_reminders  
   ```

3. **Review Imported Data**:
   ```bash
   todo list --all-projects
   ```

This will import all your existing Apple Reminders as local todos with proper project mapping based on your list configuration.

## Support and Community

- **Issues**: Report bugs on the project GitHub repository
- **Feature Requests**: Submit enhancement requests via GitHub issues  
- **Documentation**: Check the main project documentation for general todo CLI usage
- **Community**: Join discussions in project forums or chat channels

## Changelog

### Version 1.0.0
- ✅ Initial Apple Reminders integration
- ✅ Full CRUD operations support
- ✅ Bidirectional sync with deletion handling
- ✅ Project-to-list mapping
- ✅ Priority and due date synchronization
- ✅ Comprehensive error handling and recovery
- ✅ Complete test coverage