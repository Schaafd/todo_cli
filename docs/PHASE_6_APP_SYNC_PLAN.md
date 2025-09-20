# Phase 6: Multi-App Synchronization Plan

## Executive Summary

This plan outlines the implementation of a comprehensive multi-app synchronization system for the Todo CLI, starting with Todoist and designed to be easily extensible to other platforms like Apple Reminders, TickTick, Notion, Evernote, and more. The architecture leverages an adapter pattern with a unified sync engine that handles bidirectional synchronization, conflict resolution, and mapping between different app data models.

## Goals & Requirements

### Primary Goals
1. **Bidirectional sync** with Todoist as the first integration
2. **Extensible architecture** allowing easy addition of new apps
3. **Conflict resolution** with multiple strategies
4. **Data mapping** between Todo CLI's model and various app formats
5. **Authentication management** for multiple services
6. **Incremental sync** to minimize API calls and bandwidth
7. **Error resilience** with retry logic and graceful degradation

### Non-functional Requirements
- Performance: Sync operations should complete within 10 seconds for typical workloads
- Reliability: Handle network failures, API rate limits, and partial failures
- Security: Safe storage of API credentials and tokens
- Usability: Simple setup and transparent sync status reporting

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Todo CLI Core                        │
├─────────────────────────────────────────────────────────┤
│                  App Sync Manager                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Unified Sync Engine                      │  │
│  │  • Conflict Resolution                           │  │
│  │  • Change Detection                              │  │
│  │  • Sync Orchestration                           │  │
│  │  • Error Handling                               │  │
│  └──────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  Adapter Layer                           │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │
│  │Todoist  │ │ Apple   │ │TickTick │ │ Notion  │ ...  │
│  │Adapter  │ │Reminders│ │ Adapter │ │ Adapter │      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
├─────────────────────────────────────────────────────────┤
│              Service Connectors                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐      │
│  │Todoist  │ │EventKit │ │TickTick │ │ Notion  │      │
│  │   API   │ │Framework│ │   API   │ │   API   │      │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Base App Sync Framework (`app_sync.py`)

```python
# Core abstractions
class AppSyncProvider(Enum):
    TODOIST = "todoist"
    APPLE_REMINDERS = "apple_reminders"
    TICKTICK = "ticktick"
    NOTION = "notion"
    EVERNOTE = "evernote"
    MICROSOFT_TODO = "microsoft_todo"
    ANY_DO = "any_do"
    GOOGLE_TASKS = "google_tasks"

class AppSyncAdapter(ABC):
    """Base adapter for all app integrations"""
    
    @abstractmethod
    async def authenticate(self) -> bool
    
    @abstractmethod
    async def fetch_items(self, since: Optional[datetime]) -> List[ExternalTodoItem]
    
    @abstractmethod
    async def create_item(self, item: Todo) -> str  # Returns external ID
    
    @abstractmethod
    async def update_item(self, external_id: str, item: Todo) -> bool
    
    @abstractmethod
    async def delete_item(self, external_id: str) -> bool
    
    @abstractmethod
    def map_to_external(self, todo: Todo) -> Dict[str, Any]
    
    @abstractmethod
    def map_from_external(self, external_data: Dict[str, Any]) -> Todo

class AppSyncManager:
    """Manages multiple app syncs"""
    
    def register_adapter(self, provider: AppSyncProvider, adapter: AppSyncAdapter)
    def sync_all(self, strategy: ConflictStrategy)
    def sync_provider(self, provider: AppSyncProvider)
    def get_sync_status(self) -> Dict[AppSyncProvider, SyncStatus]
```

### 2. Todoist Adapter (`adapters/todoist_adapter.py`)

```python
class TodoistAdapter(AppSyncAdapter):
    """Todoist-specific implementation"""
    
    def __init__(self, api_token: str):
        self.api = TodoistAPI(api_token)
        self.project_mapping = {}  # Map between local projects and Todoist projects
        
    async def authenticate(self) -> bool:
        # Validate API token
        
    async def fetch_items(self, since: Optional[datetime]) -> List[ExternalTodoItem]:
        # Use Todoist Sync API for incremental updates
        
    def map_to_external(self, todo: Todo) -> Dict[str, Any]:
        # Convert Todo to Todoist task format
        return {
            'content': todo.text,
            'priority': self._map_priority(todo.priority),
            'due': self._format_due_date(todo.due),
            'labels': todo.tags,
            'project_id': self.project_mapping.get(todo.project)
        }
        
    def map_from_external(self, todoist_task: Dict) -> Todo:
        # Convert Todoist task to Todo
```

### 3. Data Models (`models/app_sync_models.py`)

```python
@dataclass
class ExternalTodoItem:
    """Unified external todo representation"""
    external_id: str
    provider: AppSyncProvider
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    priority: Optional[int]
    tags: List[str]
    project: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: datetime
    raw_data: Dict[str, Any]  # Original API response
    
@dataclass
class SyncMapping:
    """Maps local todos to external items"""
    todo_id: int
    external_id: str
    provider: AppSyncProvider
    last_synced: datetime
    sync_hash: str  # For change detection
    
@dataclass
class SyncConflict:
    """Represents a sync conflict"""
    todo_id: int
    provider: AppSyncProvider
    local_changes: Dict[str, Any]
    remote_changes: Dict[str, Any]
    conflict_type: str
```

### 4. Sync Engine (`sync_engine.py`)

```python
class AppSyncEngine:
    """Core synchronization logic"""
    
    def __init__(self, storage: Storage, config: AppSyncConfig):
        self.storage = storage
        self.config = config
        self.adapters: Dict[AppSyncProvider, AppSyncAdapter] = {}
        self.mapping_store = SyncMappingStore()
        
    async def sync(self, provider: AppSyncProvider, strategy: ConflictStrategy):
        # 1. Fetch remote changes
        # 2. Detect local changes
        # 3. Resolve conflicts
        # 4. Apply changes bidirectionally
        # 5. Update sync mappings
        
    def detect_changes(self, todos: List[Todo], mappings: List[SyncMapping]) -> SyncChanges:
        # Compare hashes to detect what changed locally
        
    async def resolve_conflicts(self, conflicts: List[SyncConflict], strategy: ConflictStrategy):
        # Apply conflict resolution strategy
        
    def apply_remote_changes(self, changes: List[ExternalTodoItem]):
        # Update local todos with remote changes
        
    async def push_local_changes(self, todos: List[Todo], adapter: AppSyncAdapter):
        # Send local changes to remote service
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
1. **Core Models & Abstractions**
   - [ ] Create `app_sync_models.py` with data models
   - [ ] Implement `AppSyncAdapter` base class
   - [ ] Create `AppSyncManager` for orchestration
   - [ ] Build `SyncMappingStore` for persistence

2. **Configuration & Storage**
   - [ ] Extend config system for app credentials
   - [ ] Create secure credential storage (keyring integration)
   - [ ] Add sync mapping database (SQLite or JSON)
   - [ ] Implement change detection with hashing

### Phase 2: Todoist Integration (Week 2)
1. **Todoist Adapter**
   - [ ] Implement authentication flow
   - [ ] Build data mappers (bidirectional)
   - [ ] Handle Todoist-specific features (labels, filters, sections)
   - [ ] Implement incremental sync using Sync API
   - [ ] Add project synchronization

2. **Testing & Validation**
   - [ ] Unit tests for Todoist adapter
   - [ ] Integration tests with mock API
   - [ ] End-to-end sync scenarios
   - [ ] Performance benchmarks

### Phase 3: Sync Engine (Week 3)
1. **Core Engine Implementation**
   - [ ] Change detection algorithm
   - [ ] Conflict resolution strategies
   - [ ] Batch operations for efficiency
   - [ ] Error handling and retry logic
   - [ ] Progress reporting and callbacks

2. **Advanced Features**
   - [ ] Bidirectional project sync
   - [ ] Tag/label mapping
   - [ ] Priority translation
   - [ ] Recurring task handling
   - [ ] Attachment/note sync

### Phase 4: CLI Integration (Week 4)
1. **CLI Commands**
   ```bash
   todo app-sync setup <provider>       # Interactive setup
   todo app-sync list                   # List configured apps
   todo app-sync status                 # Show sync status
   todo app-sync sync [--provider=...] # Manual sync
   todo app-sync enable/disable <provider>
   todo app-sync map-project <local> <external>
   todo app-sync conflicts               # View/resolve conflicts
   ```

2. **Auto-sync & Monitoring**
   - [ ] Background sync daemon
   - [ ] Sync on startup option
   - [ ] Sync status in dashboard
   - [ ] Conflict notifications
   - [ ] Sync history and logs

### Phase 5: Additional Adapters (Weeks 5-6)
1. **Apple Reminders** (Week 5)
   - [ ] EventKit framework integration
   - [ ] AppleScript bridge for macOS
   - [ ] Reminder list mapping

2. **TickTick** (Week 5)
   - [ ] OAuth2 authentication
   - [ ] API client implementation
   - [ ] Custom field mapping

3. **Notion** (Week 6)
   - [ ] Database integration
   - [ ] Page-to-todo mapping
   - [ ] Rich text handling

4. **Quick Adapters** (Week 6)
   - [ ] Google Tasks
   - [ ] Microsoft To Do
   - [ ] Any.do
   - [ ] Evernote tasks

## Technical Specifications

### Authentication & Security

```python
class CredentialManager:
    """Secure credential storage"""
    
    def store_credential(self, provider: AppSyncProvider, key: str, value: str):
        # Use keyring library for secure storage
        keyring.set_password(f"todo_cli_{provider.value}", key, value)
        
    def get_credential(self, provider: AppSyncProvider, key: str) -> Optional[str]:
        return keyring.get_password(f"todo_cli_{provider.value}", key)
        
    def delete_credentials(self, provider: AppSyncProvider):
        # Clean up stored credentials
```

### Data Mapping Strategy

```python
class MappingStrategy:
    """Defines how to map between systems"""
    
    # Priority mappings
    PRIORITY_MAP = {
        AppSyncProvider.TODOIST: {
            Priority.LOW: 1,
            Priority.MEDIUM: 2,
            Priority.HIGH: 3,
            Priority.CRITICAL: 4
        },
        AppSyncProvider.APPLE_REMINDERS: {
            Priority.LOW: 0,
            Priority.MEDIUM: 5,
            Priority.HIGH: 1,
            Priority.CRITICAL: 1
        }
    }
    
    # Field mappings
    FIELD_MAP = {
        AppSyncProvider.TODOIST: {
            'text': 'content',
            'due': 'due_string',
            'tags': 'labels',
            'notes': 'description'
        }
    }
```

### Conflict Resolution

```python
class ConflictResolver:
    """Handles sync conflicts"""
    
    def resolve(self, conflict: SyncConflict, strategy: ConflictStrategy) -> Resolution:
        if strategy == ConflictStrategy.LOCAL_WINS:
            return self.keep_local(conflict)
        elif strategy == ConflictStrategy.REMOTE_WINS:
            return self.keep_remote(conflict)
        elif strategy == ConflictStrategy.NEWEST_WINS:
            return self.keep_newest(conflict)
        elif strategy == ConflictStrategy.MERGE:
            return self.merge_changes(conflict)
        elif strategy == ConflictStrategy.MANUAL:
            return self.prompt_user(conflict)
            
    def merge_changes(self, conflict: SyncConflict) -> Resolution:
        # Intelligent merge based on field-level changes
        merged = {}
        for field in conflict.local_changes:
            if field not in conflict.remote_changes:
                merged[field] = conflict.local_changes[field]
            elif conflict.local_changes[field] == conflict.remote_changes[field]:
                merged[field] = conflict.local_changes[field]
            else:
                # Conflict on same field - use strategy
                merged[field] = self.resolve_field_conflict(field, conflict)
        return Resolution(action='merge', data=merged)
```

### Rate Limiting & Error Handling

```python
class RateLimiter:
    """Prevents API rate limit violations"""
    
    def __init__(self, requests_per_minute: int = 50):
        self.rate = requests_per_minute
        self.tokens = requests_per_minute
        self.updated_at = time.time()
        
    async def acquire(self):
        """Wait if necessary to respect rate limits"""
        while self.tokens < 1:
            await asyncio.sleep(0.1)
            self._refill()
        self.tokens -= 1
        
class RetryHandler:
    """Handles transient failures"""
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(TransientError)
    )
    async def execute_with_retry(self, func, *args, **kwargs):
        return await func(*args, **kwargs)
```

## Configuration Schema

```yaml
# ~/.todo/app_sync.yaml
sync:
  providers:
    todoist:
      enabled: true
      api_token: "${TODOIST_API_TOKEN}"  # Environment variable
      sync_interval: 300  # seconds
      auto_sync: true
      conflict_strategy: newest_wins
      project_mappings:
        work: "2298435862"  # Todoist project ID
        personal: "2298435863"
      
    apple_reminders:
      enabled: false
      default_list: "Tasks"
      sync_completed: true
      
    notion:
      enabled: false
      api_key: "${NOTION_API_KEY}"
      database_id: "abc123def456"
      
  global:
    sync_on_startup: true
    sync_on_exit: false
    max_retries: 3
    timeout: 30  # seconds
    conflict_strategy: manual
    log_level: info
```

## Testing Strategy

### Unit Tests
- Adapter mapping functions
- Conflict resolution logic
- Change detection algorithms
- Authentication flows

### Integration Tests
- Mock API servers for each service
- End-to-end sync scenarios
- Conflict simulation and resolution
- Error recovery scenarios

### Performance Tests
- Large dataset synchronization
- Incremental sync efficiency
- API call minimization
- Memory usage profiling

## Security Considerations

1. **Credential Storage**
   - Use OS keychain/keyring
   - Never store plaintext tokens
   - Support environment variables
   - Implement token refresh where applicable

2. **Data Privacy**
   - Local encryption option
   - Minimal data retention
   - Clear audit logging
   - GDPR compliance

3. **Network Security**
   - TLS for all API calls
   - Certificate pinning option
   - Proxy support
   - Rate limit compliance

## User Experience

### First-time Setup
```bash
$ todo app-sync setup todoist
Welcome to Todoist sync setup!

1. Get your API token from: https://todoist.com/prefs/integrations
2. Enter your API token: ********
3. Testing connection... ✓
4. Found 3 Todoist projects:
   - Inbox (default)
   - Work
   - Personal
   
5. Would you like to map local projects? (y/n): y
   Map 'work' to: Work
   Map 'personal' to: Personal
   
6. Select conflict resolution strategy:
   1) Local changes win
   2) Remote changes win
   3) Newest changes win
   4) Ask me each time
   > 3
   
Setup complete! Run 'todo app-sync sync' to start syncing.
Enable auto-sync? (y/n): y
```

### Sync Status Display
```bash
$ todo app-sync status

╭─── App Sync Status ───────────────────────────────╮
│                                                    │
│ Todoist        ✓ Connected                       │
│   Last sync:   2 minutes ago                     │
│   Items:       42 synced, 3 pending              │
│   Conflicts:   None                              │
│                                                   │
│ Apple Reminders ○ Disabled                       │
│                                                   │
│ TickTick       ✗ Authentication required         │
│                                                   │
│ Auto-sync:     Enabled (every 5 minutes)         │
│ Next sync:     in 3 minutes                      │
│                                                   │
╰────────────────────────────────────────────────────╯
```

## Success Metrics

1. **Functional Metrics**
   - Successful sync rate > 99%
   - Conflict resolution accuracy > 95%
   - Data integrity maintained 100%

2. **Performance Metrics**
   - Sync time < 10s for 1000 items
   - API calls minimized via incremental sync
   - Memory usage < 50MB during sync

3. **User Experience Metrics**
   - Setup completion rate > 90%
   - User-reported sync issues < 1%
   - Feature adoption rate > 60%

## Future Enhancements

1. **Advanced Features**
   - Multi-account support per provider
   - Selective sync (filter what syncs)
   - Sync rules and automation
   - Collaborative task sharing

2. **Additional Integrations**
   - Calendar apps (Google Calendar, Outlook)
   - Project management (Jira, Asana, Trello)
   - Note-taking apps (Obsidian, Roam)
   - Time tracking (Toggl, Harvest)

3. **Intelligence Layer**
   - Smart conflict resolution using AI
   - Automatic project/tag mapping
   - Duplicate detection and merging
   - Sync optimization based on usage patterns

## Appendix: Provider-Specific Details

### Todoist
- API: REST v2 + Sync API v9
- Auth: API Token or OAuth2
- Rate Limit: 450 requests/minute
- Features: Projects, Labels, Filters, Sections
- Docs: https://developer.todoist.com

### Apple Reminders
- API: EventKit (macOS) / AppleScript bridge
- Auth: System permissions
- Features: Lists, Smart Lists, Tags (iOS 15+)
- Limitations: macOS/iOS only

### TickTick
- API: REST API v2
- Auth: OAuth2
- Rate Limit: 2000 requests/hour
- Features: Lists, Tags, Pomodoro stats
- Docs: https://developer.ticktick.com

### Notion
- API: REST v1
- Auth: Internal Integration Token
- Rate Limit: 3 requests/second
- Features: Databases, Pages, Properties
- Docs: https://developers.notion.com

### Microsoft To Do
- API: Microsoft Graph
- Auth: OAuth2 (Azure AD)
- Features: Lists, Steps, My Day
- Docs: https://docs.microsoft.com/en-us/graph/

## Implementation Timeline

- **Week 1**: Foundation & Architecture
- **Week 2**: Todoist Integration
- **Week 3**: Sync Engine & Conflict Resolution
- **Week 4**: CLI Integration & Testing
- **Week 5**: Apple Reminders & TickTick
- **Week 6**: Notion & Additional Adapters
- **Week 7**: Testing, Documentation & Polish
- **Week 8**: Beta Testing & Bug Fixes

Total estimated time: 8 weeks for full implementation with 5+ app integrations.