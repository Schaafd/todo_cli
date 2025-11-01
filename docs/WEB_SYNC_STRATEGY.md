# Web App Sync Strategy & Conflict Resolution

**Version:** 1.0.0  
**Date:** 2025-01-11  
**Status:** Phase 2 - Sync Strategy Design

## Executive Summary

This document details the synchronization strategy for the Todo CLI web application, extending the existing `sync/sync_engine.py` to support real-time web-to-CLI bidirectional synchronization. The design leverages proven conflict resolution mechanisms while adding WebSocket-based real-time updates and optimistic UI patterns.

## Overview

The sync system bridges three domains:
1. **CLI → Storage**: Direct markdown file manipulation (existing)
2. **Web → Storage**: Real-time bidirectional sync (new)
3. **CLI ↔ External Apps**: Todoist, Apple Reminders, etc. (existing)

The web app becomes another sync "client" alongside external apps, with special considerations for real-time UX.

## Sync Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                   Sync Coordinator                           │
│  (WebSocket Hub + Existing Sync Engine Integration)         │
└────┬──────────────────────────┬──────────────────────────┬──┘
     │                          │                          │
┌────▼────────┐      ┌──────────▼─────────┐     ┌────────▼────┐
│  Web Client │      │  Sync Engine       │     │ CLI Process │
│  (Browser)  │      │  (sync_engine.py)  │     │  (Local)    │
└────┬────────┘      └──────────┬─────────┘     └────────┬────┘
     │                          │                          │
     │         ┌────────────────▼──────────────┐          │
     └─────────► Storage Layer (Markdown)      ◄──────────┘
               │  + SQLite Index (Web Only)    │
               └───────────────────────────────┘
```

### Key Classes

#### 1. WebSyncCoordinator (New)
Location: `src/todo_cli/webapp/server/sync_coordinator.py`

Orchestrates real-time sync across web clients and integrates with existing sync engine.

```python
class WebSyncCoordinator:
    """Coordinates real-time synchronization for web clients."""
    
    def __init__(self, storage: Storage, sync_engine: SyncEngine):
        self.storage = storage
        self.sync_engine = sync_engine
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.change_buffer: Dict[int, List[TodoChange]] = {}
        
    async def register_client(self, user_id: int, websocket: WebSocket):
        """Register new web client connection."""
        
    async def unregister_client(self, user_id: int, websocket: WebSocket):
        """Remove web client connection."""
        
    async def broadcast_change(
        self, user_id: int, change: TodoChange, exclude_ws: Optional[WebSocket] = None
    ):
        """Broadcast change to all connected clients for a user."""
        
    async def handle_client_change(
        self, user_id: int, change: TodoChange, source_ws: WebSocket
    ):
        """Process incoming change from web client."""
```

#### 2. WebSyncAdapter (New)
Location: `src/todo_cli/webapp/server/sync_adapter.py`

Adapts the web app to work with the existing sync engine as if it were an external provider.

```python
class WebSyncAdapter:
    """Adapter to treat web clients as a sync provider."""
    
    provider = "WEB_APP"  # Special internal provider
    
    async def fetch_items(self, user_id: int, since: Optional[datetime] = None):
        """Fetch pending changes from web clients."""
        
    async def push_change(self, user_id: int, change: TodoChange):
        """Push change to connected web clients."""
        
    async def handle_conflict(
        self, user_id: int, conflict: SyncConflict, strategy: ConflictStrategy
    ):
        """Resolve conflict and notify web clients."""
```

## Data Models

### TodoChange (New)

Represents a discrete change event for sync.

```python
@dataclass
class TodoChange:
    """Represents a change to a todo item."""
    
    change_id: str  # UUID for deduplication
    change_type: ChangeType  # CREATED, UPDATED, DELETED, COMPLETED
    todo_id: int
    user_id: int
    timestamp: datetime
    device_id: str  # Identifies source (web-chrome-abc, cli-local, etc.)
    
    # Change data
    before: Optional[Dict[str, Any]] = None  # Previous state
    after: Optional[Dict[str, Any]] = None   # New state
    fields_changed: List[str] = field(default_factory=list)
    
    # Sync metadata
    version: int = 1  # Version vector for ordering
    parent_change_id: Optional[str] = None  # For operation chaining
    is_optimistic: bool = False  # Client-side optimistic update
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for transmission."""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoChange':
        """Deserialize from transmission."""
        
    def compute_hash(self) -> str:
        """Compute hash for deduplication."""
```

### SyncState (New)

Tracks sync state for each user and device.

```python
@dataclass
class SyncState:
    """Tracks synchronization state for a user/device."""
    
    user_id: int
    device_id: str
    last_sync: datetime
    version_vector: Dict[str, int]  # device_id -> version
    pending_changes: List[str] = field(default_factory=list)  # change_ids
    acknowledged_changes: Set[str] = field(default_factory=set)
    
    def update_version(self, device_id: str):
        """Increment version for a device."""
        self.version_vector[device_id] = self.version_vector.get(device_id, 0) + 1
    
    def is_ahead_of(self, other: 'SyncState') -> bool:
        """Check if this state is ahead of another (version vector comparison)."""
        for device_id, version in self.version_vector.items():
            if version > other.version_vector.get(device_id, 0):
                return True
        return False
```

## Synchronization Flow

### 1. Initial Connection

```
Web Client                  Sync Coordinator              Storage
    |                              |                         |
    |-- WebSocket Connect -------->|                         |
    |   (with JWT token)           |                         |
    |                              |                         |
    |<-- Connection Accepted ------|                         |
    |    (sync_state)              |                         |
    |                              |                         |
    |-- Request Full Sync -------->|                         |
    |                              |-- Load User Todos ----->|
    |                              |<-- Todos Data ----------|
    |<-- Full State ---------------|                         |
    |    (all todos)               |                         |
```

### 2. Client-Initiated Change (Optimistic Update)

```
Web Client                  Sync Coordinator              Storage
    |                              |                         |
    |-- Todo Change Event -------->|                         |
    |   (optimistic_id: temp-123)  |                         |
    |   (change_type: UPDATED)     |                         |
    |                              |                         |
    |                              |-- Validate Change ----->|
    |                              |-- Save to Storage ----->|
    |                              |<-- Success (id: 456) ---|
    |                              |                         |
    |<-- Change Confirmed ---------|                         |
    |   (permanent_id: 456)        |                         |
    |   (resolve temp-123 -> 456)  |                         |
    |                              |                         |
    |                              |-- Broadcast to Others ->|
    |                              |   (other web clients)   |
```

### 3. Server-Initiated Change (CLI or Another Client)

```
CLI / Other Client         Sync Coordinator           Web Client
    |                              |                         |
    |-- Modify Storage ----------->|                         |
    |   (via CLI or other WS)      |                         |
    |                              |                         |
    |                              |-- Detect Change ------->|
    |                              |   (file watcher/event)  |
    |                              |                         |
    |                              |-- Broadcast Change ---->|
    |                              |   (all connected clients|
    |                              |    for user)            |
    |                              |                         |
    |                              |<-- Change Acknowledged -|
```

### 4. Conflict Detection & Resolution

```
Web Client 1               Sync Coordinator           Web Client 2
    |                              |                         |
    |-- Update Todo 123 ---------->|                         |
    |   (version: 5)               |<-- Update Todo 123 -----|
    |                              |    (version: 5)         |
    |                              |                         |
    |                              |-- Conflict Detected! ---|
    |                              |   (both at version 5)   |
    |                              |                         |
    |                              |-- Apply Strategy -------|
    |                              |   (NEWEST_WINS)         |
    |                              |                         |
    |<-- Conflict Resolved --------|-- Conflict Resolved --->|
    |   (winner: Client 2)         |   (winner: Client 2)    |
    |   (update to version 6)      |   (confirmed version 6) |
```

## Change Detection Strategy

### File System Watching (CLI Changes)

Use `watchdog` library to monitor markdown file changes:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TodoFileHandler(FileSystemEventHandler):
    """Monitor markdown file changes from CLI."""
    
    def __init__(self, sync_coordinator: WebSyncCoordinator):
        self.sync_coordinator = sync_coordinator
        self.debounce_timer: Dict[str, float] = {}
    
    def on_modified(self, event):
        """Handle file modification event."""
        if not event.is_directory and event.src_path.endswith('.md'):
            # Debounce rapid changes (e.g., auto-save)
            if self._should_process(event.src_path):
                asyncio.run(self._process_file_change(event.src_path))
    
    async def _process_file_change(self, file_path: str):
        """Process a file change and broadcast to clients."""
        # Parse file to extract changed todos
        project_name = Path(file_path).stem
        project, todos = self.storage.load_project(project_name)
        
        # Detect specific changes (compare with cached state)
        changes = self._detect_changes(project_name, todos)
        
        # Broadcast to all connected web clients
        for change in changes:
            await self.sync_coordinator.broadcast_change(
                user_id=change.user_id,
                change=change,
                exclude_ws=None  # No exclusions for file changes
            )
```

### Database Index Tracking (Web Changes)

SQLite index maintains last known state for fast change detection:

```sql
-- Track todo versions in index
CREATE TABLE todo_versions (
    todo_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    last_modified TIMESTAMP NOT NULL,
    modified_by TEXT NOT NULL,  -- device_id
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Detect changes by comparing hashes
SELECT todo_id, version, content_hash 
FROM todo_versions 
WHERE user_id = ? 
  AND version > ?
ORDER BY version ASC;
```

## Conflict Resolution Strategies

Leverage existing `ConflictResolver` from `sync/sync_engine.py` with web-specific extensions:

### Strategy 1: LOCAL_WINS (Client Wins)
**Use Case:** User explicitly chose to keep their version

```python
async def resolve_local_wins(conflict: SyncConflict, client_ws: WebSocket):
    """Keep the web client's version, discard others."""
    # 1. Accept client's version
    client_version = conflict.local_todo
    
    # 2. Save to storage
    storage.update_todo(client_version)
    
    # 3. Broadcast to other clients (force update)
    await broadcast_change(
        user_id=conflict.user_id,
        change=TodoChange(change_type=ChangeType.FORCE_UPDATE, after=client_version),
        exclude_ws=client_ws
    )
    
    # 4. Mark conflict resolved
    conflict.resolve("local_wins")
```

### Strategy 2: REMOTE_WINS (Server Wins)
**Use Case:** Another client or CLI took precedence

```python
async def resolve_remote_wins(conflict: SyncConflict, client_ws: WebSocket):
    """Keep the server's version, overwrite client."""
    # 1. Use server version (latest from storage or other client)
    server_version = conflict.remote_item.to_todo(conflict.todo_id)
    
    # 2. Send force update to this client
    await send_to_client(
        websocket=client_ws,
        message=TodoChange(change_type=ChangeType.FORCE_UPDATE, after=server_version)
    )
    
    # 3. Mark conflict resolved
    conflict.resolve("remote_wins")
```

### Strategy 3: NEWEST_WINS (Timestamp-Based)
**Use Case:** Default automatic resolution

```python
async def resolve_newest_wins(conflict: SyncConflict, client_ws: WebSocket):
    """Compare timestamps and keep the newest version."""
    local_time = conflict.local_todo.modified
    remote_time = conflict.remote_item.updated_at
    
    if local_time > remote_time:
        await resolve_local_wins(conflict, client_ws)
    else:
        await resolve_remote_wins(conflict, client_ws)
```

### Strategy 4: MERGE (Field-Level Merge)
**Use Case:** Intelligent combination of both versions

```python
async def resolve_merge(conflict: SyncConflict, client_ws: WebSocket):
    """Merge non-conflicting fields intelligently."""
    merged_todo = conflict.local_todo.copy()
    
    # Apply merge rules (from existing sync_engine.py)
    merge_rules = {
        'text': 'prefer_longest',
        'description': 'prefer_longest',
        'due_date': 'prefer_earliest',
        'priority': 'prefer_highest',
        'tags': 'merge_unique',
        'completed': 'prefer_completed'
    }
    
    for field, rule in merge_rules.items():
        local_value = getattr(conflict.local_todo, field)
        remote_value = getattr(conflict.remote_item, field)
        
        merged_value = apply_merge_rule(rule, local_value, remote_value)
        setattr(merged_todo, field, merged_value)
    
    # Save merged version
    storage.update_todo(merged_todo)
    
    # Broadcast to all clients (including originator)
    await broadcast_change(
        user_id=conflict.user_id,
        change=TodoChange(change_type=ChangeType.FORCE_UPDATE, after=merged_todo),
        exclude_ws=None  # Send to all
    )
    
    conflict.resolve("merge")
```

### Strategy 5: MANUAL (User Intervention)
**Use Case:** Ambiguous conflicts requiring user choice

```python
async def resolve_manual(conflict: SyncConflict, client_ws: WebSocket):
    """Present conflict to user for manual resolution."""
    # 1. Send conflict notification to client
    conflict_message = {
        "type": "sync.conflict",
        "conflict_id": conflict.id,
        "local_version": conflict.local_todo.to_dict(),
        "remote_version": conflict.remote_item.to_dict(),
        "conflict_type": conflict.conflict_type.value,
        "detected_at": conflict.detected_at.isoformat()
    }
    
    await send_to_client(client_ws, conflict_message)
    
    # 2. Wait for user choice (received via another message)
    # ... handled in separate message handler ...
    
    # 3. Apply user's choice when received
    # (will call one of the other resolution strategies)
```

## Optimistic UI Pattern

### Client-Side Optimistic Update

```javascript
// client-side: src/todo_cli/webapp/static/js/sync-manager.js

class SyncManager {
    constructor(apiClient, websocket) {
        this.apiClient = apiClient;
        this.websocket = websocket;
        this.pendingChanges = new Map();  // temp_id -> change
        this.optimisticTimeoutMs = 5000;  // Rollback timeout
    }
    
    async updateTodoOptimistic(todo) {
        // 1. Generate temporary ID for this change
        const tempId = `temp-${Date.now()}-${Math.random()}`;
        
        // 2. Apply change to UI immediately
        uiManager.updateTodoInDOM(todo);
        
        // 3. Store change as pending
        const change = {
            tempId,
            todo,
            timestamp: Date.now(),
            rollbackTimer: null
        };
        this.pendingChanges.set(tempId, change);
        
        // 4. Send to server via WebSocket
        this.websocket.send(JSON.stringify({
            type: 'todo.update',
            temp_id: tempId,
            data: todo
        }));
        
        // 5. Set rollback timer
        change.rollbackTimer = setTimeout(() => {
            this.rollbackChange(tempId);
        }, this.optimisticTimeoutMs);
        
        return tempId;
    }
    
    handleServerConfirmation(message) {
        const { temp_id, permanent_id, version } = message.data;
        
        // 1. Find pending change
        const change = this.pendingChanges.get(temp_id);
        if (!change) return;
        
        // 2. Clear rollback timer
        clearTimeout(change.rollbackTimer);
        
        // 3. Update UI with permanent ID
        uiManager.confirmOptimisticUpdate(temp_id, permanent_id, version);
        
        // 4. Remove from pending
        this.pendingChanges.delete(temp_id);
    }
    
    handleServerConflict(message) {
        const { temp_id, conflict_data } = message.data;
        
        // 1. Rollback optimistic change
        this.rollbackChange(temp_id);
        
        // 2. Show conflict resolution UI
        uiManager.showConflictDialog(conflict_data);
    }
    
    rollbackChange(tempId) {
        const change = this.pendingChanges.get(tempId);
        if (!change) return;
        
        // 1. Revert UI to previous state
        uiManager.revertTodo(change.todo);
        
        // 2. Show error notification
        notificationManager.error('Failed to sync change. Rolling back.');
        
        // 3. Remove from pending
        this.pendingChanges.delete(tempId);
    }
}
```

### Server-Side Confirmation Flow

```python
# server-side: src/todo_cli/webapp/server/websocket.py

async def handle_todo_update(
    websocket: WebSocket, 
    user_id: int, 
    message: Dict[str, Any]
):
    """Handle todo update from web client."""
    temp_id = message.get('temp_id')
    todo_data = message['data']
    
    try:
        # 1. Validate change
        todo = Todo.from_dict(todo_data)
        validate_todo(todo, user_id)
        
        # 2. Check for conflicts
        conflict = await detect_conflict(user_id, todo)
        
        if conflict:
            # 3a. Handle conflict
            await send_conflict_to_client(websocket, temp_id, conflict)
            return
        
        # 3b. No conflict - save change
        storage.update_todo(todo)
        permanent_id = todo.id
        version = increment_version(user_id, todo.id)
        
        # 4. Confirm to originating client
        await websocket.send_json({
            'type': 'sync.confirmed',
            'temp_id': temp_id,
            'permanent_id': permanent_id,
            'version': version
        })
        
        # 5. Broadcast to other clients
        await broadcast_change(
            user_id=user_id,
            change=TodoChange(
                change_type=ChangeType.UPDATED,
                todo_id=permanent_id,
                after=todo.to_dict()
            ),
            exclude_ws=websocket
        )
        
    except Exception as e:
        # Error - rollback optimistic update
        await websocket.send_json({
            'type': 'sync.error',
            'temp_id': temp_id,
            'error': str(e)
        })
```

## Version Vectors & Ordering

### Version Vector Implementation

Each client maintains a version vector to track causal ordering:

```python
class VersionVector:
    """Vector clock for distributed sync ordering."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.vector: Dict[str, int] = {device_id: 0}
    
    def increment(self):
        """Increment this device's version."""
        self.vector[self.device_id] += 1
    
    def update(self, other: Dict[str, int]):
        """Merge with another vector (take max of each component)."""
        for device_id, version in other.items():
            self.vector[device_id] = max(
                self.vector.get(device_id, 0),
                version
            )
    
    def happens_before(self, other: 'VersionVector') -> bool:
        """Check if this event happened before another."""
        # This happens before other if:
        # - all our versions <= other's versions
        # - at least one is strictly less
        
        all_less_or_equal = all(
            self.vector.get(device_id, 0) <= other.vector.get(device_id, 0)
            for device_id in self.vector
        )
        
        at_least_one_less = any(
            self.vector.get(device_id, 0) < other.vector.get(device_id, 0)
            for device_id in self.vector
        )
        
        return all_less_or_equal and at_least_one_less
    
    def concurrent_with(self, other: 'VersionVector') -> bool:
        """Check if this event is concurrent (conflicts) with another."""
        return not self.happens_before(other) and not other.happens_before(self)
```

### Change Ordering Example

```
Device A (CLI):     [A:1, B:0, C:0]  →  [A:2, B:0, C:0]
Device B (Web 1):   [A:1, B:1, C:0]  →  [A:1, B:2, C:0]
Device C (Web 2):   [A:1, B:1, C:1]  →  [A:1, B:1, C:2]

Sync at server:
1. A:2 arrives → [A:2, B:0, C:0]
2. B:2 arrives → [A:2, B:2, C:0]  (merge)
3. C:2 arrives → [A:2, B:2, C:2]  (merge)

If B:2 and C:2 modify same field:
- Concurrent! → Detect conflict
- Apply NEWEST_WINS or MERGE strategy
```

## Edge Cases & Error Handling

### 1. Client Disconnect During Sync

```python
async def handle_client_disconnect(user_id: int, websocket: WebSocket):
    """Handle client disconnect mid-sync."""
    # 1. Cancel pending optimistic changes from this client
    device_id = get_device_id(websocket)
    pending = await get_pending_changes(user_id, device_id)
    
    for change in pending:
        if change.is_optimistic and not change.acknowledged:
            # Mark as failed, will retry on reconnect
            await mark_change_failed(change.change_id)
    
    # 2. Remove from active connections
    await coordinator.unregister_client(user_id, websocket)
    
    # 3. Keep sync state for reconnection window (5 minutes)
    await store_disconnect_state(user_id, device_id, ttl=300)
```

### 2. Client Reconnect (Resume Sync)

```python
async def handle_client_reconnect(
    user_id: int, 
    websocket: WebSocket, 
    last_sync_version: Dict[str, int]
):
    """Resume sync after reconnection."""
    # 1. Retrieve disconnect state
    disconnect_state = await get_disconnect_state(user_id, get_device_id(websocket))
    
    if disconnect_state:
        # 2. Get changes since disconnect
        missed_changes = await get_changes_since_version(
            user_id, 
            last_sync_version
        )
        
        # 3. Send missed changes
        for change in missed_changes:
            await websocket.send_json(change.to_dict())
        
        # 4. Resume normal sync
        await coordinator.register_client(user_id, websocket)
    else:
        # Disconnect state expired, do full sync
        await perform_full_sync(user_id, websocket)
```

### 3. Simultaneous Conflicting Changes

```python
async def handle_simultaneous_conflicts(
    change1: TodoChange, 
    change2: TodoChange
) -> TodoChange:
    """Resolve when two changes arrive at same time."""
    # 1. Check version vectors
    v1 = change1.version_vector
    v2 = change2.version_vector
    
    if v1.happens_before(v2):
        # change1 causally before change2, apply change2
        return change2
    elif v2.happens_before(v1):
        # change2 causally before change1, apply change1
        return change1
    else:
        # Concurrent changes - use tiebreaker
        # Option A: Timestamp
        if change1.timestamp > change2.timestamp:
            winner = change1
        elif change2.timestamp > change1.timestamp:
            winner = change2
        else:
            # Option B: Device ID lexicographic order (deterministic)
            winner = change1 if change1.device_id < change2.device_id else change2
        
        # Create conflict record for audit
        await record_resolved_conflict(
            winner=winner,
            loser=change1 if winner == change2 else change2,
            strategy="concurrent_tiebreaker"
        )
        
        return winner
```

### 4. Network Partition Healing

```python
async def handle_partition_healing(user_id: int):
    """Reconcile state after network partition resolves."""
    # 1. Get all devices for this user
    devices = await get_user_devices(user_id)
    
    # 2. Collect version vectors from all online devices
    vectors = {}
    for device_id in devices:
        state = await get_sync_state(user_id, device_id)
        if state:
            vectors[device_id] = state.version_vector
    
    # 3. Detect divergent changes (concurrent on different branches)
    divergent_changes = await find_divergent_changes(user_id, vectors)
    
    # 4. Resolve conflicts
    for todo_id, changes in divergent_changes.items():
        # Group conflicting changes by todo
        conflict = create_conflict_from_changes(changes)
        
        # Apply resolution strategy
        resolved = await resolve_conflict(conflict, strategy=ConflictStrategy.MERGE)
        
        # Broadcast resolution to all devices
        await broadcast_change(
            user_id=user_id,
            change=TodoChange(
                change_type=ChangeType.FORCE_UPDATE,
                after=resolved
            )
        )
```

## Performance Optimizations

### 1. Change Batching

Batch multiple changes into single broadcast:

```python
class ChangeBatcher:
    """Batch multiple changes for efficient transmission."""
    
    def __init__(self, flush_interval_ms: int = 100, max_batch_size: int = 50):
        self.flush_interval_ms = flush_interval_ms
        self.max_batch_size = max_batch_size
        self.pending_batches: Dict[int, List[TodoChange]] = {}
        self.flush_timers: Dict[int, asyncio.Task] = {}
    
    async def add_change(self, user_id: int, change: TodoChange):
        """Add change to batch for user."""
        if user_id not in self.pending_batches:
            self.pending_batches[user_id] = []
        
        self.pending_batches[user_id].append(change)
        
        # Start flush timer if not already running
        if user_id not in self.flush_timers:
            self.flush_timers[user_id] = asyncio.create_task(
                self._flush_after_delay(user_id)
            )
        
        # Flush immediately if batch full
        if len(self.pending_batches[user_id]) >= self.max_batch_size:
            await self.flush_batch(user_id)
    
    async def _flush_after_delay(self, user_id: int):
        """Flush batch after delay."""
        await asyncio.sleep(self.flush_interval_ms / 1000)
        await self.flush_batch(user_id)
    
    async def flush_batch(self, user_id: int):
        """Send batched changes to clients."""
        if user_id not in self.pending_batches:
            return
        
        changes = self.pending_batches[user_id]
        if not changes:
            return
        
        # Send batch
        await broadcast_batch(user_id, changes)
        
        # Clear batch
        self.pending_batches[user_id] = []
        
        # Cancel timer
        if user_id in self.flush_timers:
            self.flush_timers[user_id].cancel()
            del self.flush_timers[user_id]
```

### 2. Incremental Sync (Delta Updates)

Only send changed fields, not full todo objects:

```python
def compute_delta(before: Todo, after: Todo) -> Dict[str, Any]:
    """Compute minimal delta between two todo states."""
    delta = {}
    
    for field in ['text', 'description', 'due_date', 'priority', 'status', 
                  'tags', 'project', 'completed']:
        before_value = getattr(before, field)
        after_value = getattr(after, field)
        
        if before_value != after_value:
            delta[field] = after_value
    
    return delta

# Usage
change = TodoChange(
    change_type=ChangeType.UPDATED,
    todo_id=123,
    fields_changed=['text', 'priority'],
    after={'text': 'Updated text', 'priority': 'high'}  # Only changed fields
)
```

### 3. Compression for Large Payloads

```python
import gzip
import json

async def send_compressed(websocket: WebSocket, data: Dict[str, Any]):
    """Send JSON data with gzip compression."""
    json_str = json.dumps(data)
    
    # Only compress if payload is large enough
    if len(json_str) > 1024:
        compressed = gzip.compress(json_str.encode('utf-8'))
        await websocket.send_bytes(compressed)
    else:
        await websocket.send_json(data)
```

## Testing Strategy

### Unit Tests

```python
# Test conflict detection
def test_detect_concurrent_changes():
    change1 = TodoChange(
        todo_id=1,
        version_vector={'client1': 2, 'client2': 1},
        timestamp=datetime(2025, 1, 1, 10, 0, 0)
    )
    
    change2 = TodoChange(
        todo_id=1,
        version_vector={'client1': 1, 'client2': 2},
        timestamp=datetime(2025, 1, 1, 10, 0, 1)
    )
    
    assert change1.version_vector.concurrent_with(change2.version_vector)

# Test optimistic rollback
async def test_optimistic_rollback():
    manager = SyncManager(api_client, websocket)
    
    temp_id = await manager.updateTodoOptimistic(todo)
    
    # Simulate timeout
    await asyncio.sleep(manager.optimisticTimeoutMs / 1000 + 0.1)
    
    # Verify rollback occurred
    assert temp_id not in manager.pendingChanges
```

### Integration Tests

```python
# Test multi-client sync
async def test_multi_client_sync():
    # Setup
    client1 = await connect_client(user_id=1)
    client2 = await connect_client(user_id=1)
    
    # Client 1 creates todo
    await client1.send_json({
        'type': 'todo.create',
        'data': {'text': 'Test task', 'project': 'inbox'}
    })
    
    # Client 2 should receive creation event
    message = await client2.receive_json()
    assert message['type'] == 'sync.change'
    assert message['data']['change_type'] == 'CREATED'

# Test conflict resolution
async def test_conflict_resolution():
    client1 = await connect_client(user_id=1)
    client2 = await connect_client(user_id=1)
    
    # Both clients update same todo simultaneously
    await asyncio.gather(
        client1.send_json({
            'type': 'todo.update',
            'data': {'id': 1, 'text': 'Version A'}
        }),
        client2.send_json({
            'type': 'todo.update',
            'data': {'id': 1, 'text': 'Version B'}
        })
    )
    
    # Both should receive conflict resolution
    msg1 = await client1.receive_json()
    msg2 = await client2.receive_json()
    
    # Verify both converge to same version
    assert msg1['data']['text'] == msg2['data']['text']
```

## Monitoring & Observability

### Metrics to Track

```python
# Sync performance metrics
sync_latency_histogram = Histogram(
    'todo_sync_latency_seconds',
    'Latency for sync operations',
    buckets=[0.001, 0.01, 0.1, 0.5, 1.0, 2.0, 5.0]
)

conflict_rate_counter = Counter(
    'todo_sync_conflicts_total',
    'Total number of sync conflicts detected',
    ['resolution_strategy']
)

active_connections_gauge = Gauge(
    'todo_websocket_connections',
    'Number of active WebSocket connections',
    ['user_id']
)

change_throughput_counter = Counter(
    'todo_changes_total',
    'Total number of todo changes',
    ['change_type', 'source']
)
```

### Logging

```python
# Structured logging for sync events
logger.info(
    "Sync conflict resolved",
    extra={
        'user_id': user_id,
        'todo_id': todo_id,
        'conflict_type': conflict.conflict_type.value,
        'resolution_strategy': strategy.value,
        'resolution_time_ms': resolution_time * 1000
    }
)
```

## Migration & Rollout

### Phase 1: Internal Alpha (Week 1-2)
- Deploy sync infrastructure
- Test with single user, multiple devices
- Monitor performance and conflicts

### Phase 2: Limited Beta (Week 3-4)
- Invite 10-20 power users
- Enable conflict resolution UI
- Gather feedback on sync UX

### Phase 3: General Availability (Week 5+)
- Enable for all web app users
- CLI users can opt-in to web sync
- Monitor at scale, tune performance

## Conclusion

This sync strategy extends Todo CLI's proven sync engine to support real-time web-to-CLI synchronization while maintaining data integrity through robust conflict resolution. The design prioritizes:

1. **Consistency**: Version vectors and conflict detection ensure data integrity
2. **Performance**: Optimistic updates and batching provide responsive UX
3. **Reliability**: Rollback mechanisms and reconnection handling ensure robustness
4. **Compatibility**: Integrates seamlessly with existing CLI and external app sync

Next phase: Implement authentication and user management infrastructure to enable per-user sync isolation.
