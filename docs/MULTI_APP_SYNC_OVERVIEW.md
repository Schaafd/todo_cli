# Multi-App Synchronization Overview

## 🔄 Introduction

Todo CLI's multi-app synchronization system provides seamless bidirectional sync with popular todo applications, allowing you to work with your preferred tools while maintaining a unified task management experience.

## 🚀 Supported Providers

### ✅ **Fully Supported**

#### 📝 **Todoist** 
- **Type**: Cloud-based API integration
- **Authentication**: API token required
- **Features**: Full CRUD, projects, labels, due dates, priorities, descriptions
- **Platform**: Cross-platform (web, mobile, desktop)
- **Setup**: `todo app-sync setup todoist`
- **Documentation**: [Todoist Sync Guide](TODOIST_SYNC.md)

#### 🍎 **Apple Reminders**
- **Type**: Native macOS integration via AppleScript
- **Authentication**: System privacy permissions only
- **Features**: Full CRUD, lists, due dates, priorities, descriptions, completion status
- **Platform**: macOS only (syncs with iOS via iCloud)
- **Setup**: `todo app-sync setup apple_reminders`
- **Documentation**: [Apple Reminders Sync Guide](APPLE_REMINDERS_SYNC.md)

### 🚧 **Coming Soon**

#### 🎯 **TickTick**
- **Type**: Cloud-based API integration
- **Features**: Projects, tags, calendar integration, time tracking
- **Platform**: Cross-platform with advanced scheduling

#### 📊 **Notion**
- **Type**: Database API integration  
- **Features**: Rich metadata, database relationships, advanced filtering
- **Platform**: Cross-platform with powerful organization

#### 🏢 **Microsoft Todo**
- **Type**: Microsoft Graph API integration
- **Features**: Office 365 integration, shared lists, file attachments
- **Platform**: Cross-platform with Microsoft ecosystem

#### 📧 **Google Tasks**
- **Type**: Google API integration
- **Features**: Gmail integration, Google Calendar sync, simple task management
- **Platform**: Cross-platform with Google Workspace

## 🎯 Quick Start Guide

### 1. **Setup Your First Provider**

```bash
# Choose your preferred provider
todo app-sync setup todoist        # For cloud-based sync
todo app-sync setup apple_reminders # For macOS native sync

# Or choose interactively
todo app-sync setup --interactive
```

### 2. **Configure Project Mapping**

Map your local todo projects to external app projects/lists:

```bash
# Interactive mapping setup
todo app-sync project-map todoist
todo app-sync project-map apple_reminders

# Direct mapping
todo app-sync project-map todoist --local work --remote "Work Projects"
```

### 3. **Start Syncing**

```bash
# Sync with specific provider
todo app-sync sync todoist
todo app-sync sync apple_reminders

# Sync with all configured providers
todo app-sync sync --all

# Enable automatic syncing
todo app-sync enable todoist
todo app-sync enable apple_reminders
```

## 📊 Feature Comparison

| Feature | Todoist | Apple Reminders | TickTick | Notion | MS Todo | Google Tasks |
|---------|---------|-----------------|----------|--------|---------|--------------|
| **CRUD Operations** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Bidirectional Sync** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Projects/Lists** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Tags/Labels** | ✅ | ❌ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Due Dates** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Priorities** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Descriptions** | ✅ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Subtasks** | ✅ | ❌ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Attachments** | ❌ | ❌ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Collaboration** | ✅ | ❌ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Offline Access** | ❌ | ✅ | 🚧 | 🚧 | 🚧 | 🚧 |
| **Authentication** | API Token | System Privacy | API | API | OAuth | OAuth |
| **Platform** | All | macOS/iOS | All | All | All | All |

## 🔧 Common Commands

### Setup and Configuration
```bash
# List available providers
todo app-sync list

# Check sync status
todo app-sync status
todo app-sync status todoist

# Configure providers
todo app-sync enable/disable PROVIDER
todo app-sync config PROVIDER --setting value
```

### Synchronization
```bash
# Manual sync
todo app-sync sync PROVIDER
todo app-sync sync --all
todo app-sync sync --dry-run

# Automatic sync
todo app-sync auto-sync --enable PROVIDER
todo app-sync auto-sync --disable PROVIDER
```

### Conflict Management
```bash
# View conflicts
todo app-sync conflicts
todo app-sync conflicts --provider PROVIDER

# Resolve conflicts
todo app-sync resolve-conflicts PROVIDER
todo app-sync resolve-conflicts --strategy newest_wins
```

### Maintenance
```bash
# Clean up stale mappings
todo app-sync cleanup PROVIDER
todo app-sync cleanup --all

# Run diagnostics
todo app-sync doctor
todo app-sync test-connection PROVIDER
```

## 🎨 Sync Strategies

### Conflict Resolution
When the same task is modified in both places, you can choose:

- **Newest Wins**: Use the most recently modified version
- **Local Wins**: Always prefer local changes
- **Remote Wins**: Always prefer external app changes  
- **Manual**: Review each conflict individually
- **Skip**: Leave conflicts unresolved

### Sync Directions
Configure how data flows between systems:

- **Bidirectional**: Changes sync in both directions (recommended)
- **Push Only**: Local changes go to external app only
- **Pull Only**: External app changes come to local only

### Data Mapping
Control how your data maps between systems:

- **Projects ↔ Projects/Lists**: Map local projects to external projects or lists
- **Tags ↔ Labels**: Map local tags to external labels (where supported)
- **Priorities**: Intelligent mapping between different priority scales
- **Due Dates**: Full timezone-aware synchronization

## 🔒 Security and Privacy

### Credential Storage
- **System Keyring**: Preferred secure storage (macOS Keychain, Windows Credential Store, Linux Secret Service)
- **Encrypted Cache**: Fallback encrypted storage for unsupported systems
- **Environment Variables**: Manual credential management option

### Privacy Considerations
- **Todoist**: Requires API token with task permissions
- **Apple Reminders**: Requires system privacy permission for Reminders access
- **Network Traffic**: All API communications use HTTPS/TLS encryption
- **Local Storage**: All local data remains on your system

## 🚀 Performance

### Sync Efficiency
- **Incremental Updates**: Only sync changed items
- **Change Detection**: Hash-based change tracking
- **Batch Operations**: Efficient bulk updates where supported
- **Rate Limiting**: Respects API rate limits to avoid throttling

### Storage Optimization
- **Minimal Metadata**: Only essential sync data stored locally
- **Automatic Cleanup**: Stale mappings automatically removed
- **Compression**: Efficient storage of sync mappings and history

## 🔧 Troubleshooting

### Common Issues

#### 1. **Authentication Problems**
```bash
# Test authentication
todo app-sync test-connection PROVIDER

# Re-authenticate
todo app-sync setup PROVIDER --force
```

#### 2. **Sync Conflicts**
```bash
# View and resolve
todo app-sync conflicts
todo app-sync resolve-conflicts PROVIDER --strategy newest_wins
```

#### 3. **Missing Tasks**
```bash
# Check project mappings
todo app-sync status PROVIDER

# Clean up stale mappings
todo app-sync cleanup PROVIDER
```

#### 4. **Performance Issues**
```bash
# Run diagnostics
todo app-sync doctor

# Check network connectivity
ping api.todoist.com  # For Todoist
```

### Debug Mode

Enable detailed logging for troubleshooting:
```bash
export TODO_CLI_LOG_LEVEL=DEBUG
todo app-sync sync PROVIDER
```

## 📈 Best Practices

### 1. **Regular Syncing**
- Enable auto-sync for seamless experience
- Sync before making major changes
- Monitor sync status regularly

### 2. **Consistent Organization**
- Use consistent project names across systems
- Set up comprehensive project mapping
- Maintain clean project structures

### 3. **Conflict Prevention**
- Make changes in one place at a time when possible
- Sync frequently to minimize conflicts
- Use descriptive task titles to aid conflict resolution

### 4. **Backup Strategy**
- Regular data exports: `todo export json -o backup.json`
- Version control your todo directory
- Test sync setup in dry-run mode first

## 🚀 Roadmap

### Phase 6.1 - Enhanced Provider Support
- TickTick integration with calendar sync
- Notion database integration
- Microsoft Todo with Office 365 features

### Phase 6.2 - Advanced Features  
- Webhook-based real-time sync
- Advanced conflict resolution with merge strategies
- Multi-directional sync (3+ providers simultaneously)

### Phase 6.3 - Platform Expansion
- Android integration (via Termux)
- Web interface for sync management
- Mobile companion apps

## 📚 Documentation Links

- **[Todoist Sync Guide](TODOIST_SYNC.md)** - Detailed Todoist integration guide
- **[Apple Reminders Sync Guide](APPLE_REMINDERS_SYNC.md)** - Complete Apple Reminders setup and usage
- **[Bidirectional Sync Technical Details](BIDIRECTIONAL_SYNC.md)** - Technical implementation details
- **[Troubleshooting Guide](troubleshooting-sync.md)** - Common issues and solutions

## 🤝 Contributing

Want to add support for your favorite todo app?

1. Check our [Provider Development Guide](PROVIDER_DEVELOPMENT.md)
2. Follow the adapter pattern in `src/todo_cli/adapters/`
3. Add comprehensive tests and documentation
4. Submit a PR with your integration

Popular provider requests:
- Asana integration
- Trello integration  
- Linear integration
- GitHub Issues integration
- Jira integration

## 📄 License

Multi-app synchronization is part of Todo CLI and follows the same license terms as the main project.