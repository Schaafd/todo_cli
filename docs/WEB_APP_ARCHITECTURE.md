# Web App Architecture Design

**Version:** 1.0.0  
**Date:** 2025-01-11  
**Status:** Phase 1 - Architecture & Design

## Executive Summary

This document outlines the architecture for a sophisticated remote web interface for Todo CLI that preserves the terminal aesthetic while enabling cross-device synchronization. The web app will coexist with the existing PWA, providing remote access with authentication, real-time sync, and advanced task management capabilities.

## Design Principles

### 1. Terminal-Inspired Interface
- Monospace typography (JetBrains Mono, Fira Code)
- Existing theme engine palettes (city_lights, dracula, gruvbox, nord)
- Flat material design with subtle depth (1-2px shadows)
- Command palette as primary interaction (Cmd/Ctrl+K)
- Keyboard-first navigation and shortcuts

### 2. CLI-Web Consistency
- Natural language parser works identically in web interface
- Command palette mirrors CLI commands
- Consistent task metadata and attributes
- Unified storage format (Markdown + YAML)

### 3. Cross-Device Sync
- Real-time bidirectional synchronization
- Optimistic UI updates with rollback
- Conflict detection and resolution
- Offline support with sync queue

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interfaces                          │
├──────────────┬──────────────┬──────────────┬────────────────┤
│     CLI      │     PWA      │   Web App    │  Mobile Web    │
│  (Local)     │  (Offline)   │  (Remote)    │  (Responsive)  │
└──────┬───────┴──────┬───────┴──────┬───────┴────────┬───────┘
       │              │              │                │
       │              │              │                │
┌──────▼──────────────▼──────────────▼────────────────▼───────┐
│                    FastAPI Backend                           │
├──────────────────────────────────────────────────────────────┤
│  REST API  │  WebSocket  │  Auth  │  Real-time Sync         │
└──────┬───────────┬────────┬───────┬──────────────────────────┘
       │           │        │       │
┌──────▼───────────▼────────▼───────▼──────────────────────────┐
│              Service Layer                                    │
├───────────────┬───────────────┬──────────────┬───────────────┤
│  Sync Engine  │  Query Engine │  Parser      │  Auth Service │
└───────┬───────┴───────┬───────┴──────┬───────┴───────┬───────┘
        │               │              │               │
┌───────▼───────────────▼──────────────▼───────────────▼───────┐
│                   Storage Layer                               │
├───────────────────────────────────────────────────────────────┤
│  Markdown Files  │  SQLite Index  │  Redis Cache  │  Keyring │
└───────────────────────────────────────────────────────────────┘
```

## Component Separation: PWA vs Web App

### PWA (Existing - Offline-First)
**Purpose:** Fast, offline-capable local task management

**Characteristics:**
- No authentication required
- Local-only data storage
- Service worker for offline capability
- Fast, immediate responses
- Personal use focused

**Location:** `src/todo_cli/web/`

**Keep As-Is:**
- Current PWA implementation
- Offline-first service worker
- Local caching strategy
- Simple static file serving

### Web App (New - Remote Access)
**Purpose:** Cross-device synchronized task management

**Characteristics:**
- Authentication required (JWT-based)
- Real-time sync via WebSocket
- Multi-user support
- Collaborative features
- Advanced analytics and reporting

**Location:** `src/todo_cli/webapp/`

**New Structure:**
```
src/todo_cli/webapp/
├── server/
│   ├── __init__.py
│   ├── app.py                    # Main FastAPI application
│   ├── auth.py                   # Authentication middleware
│   ├── websocket.py              # WebSocket handlers
│   └── routes/
│       ├── __init__.py
│       ├── auth.py               # Auth endpoints
│       ├── tasks.py              # Task CRUD endpoints
│       ├── sync.py               # Sync endpoints
│       └── analytics.py          # Analytics endpoints
├── static/
│   ├── js/
│   │   ├── config.js
│   │   ├── auth.js               # Authentication manager
│   │   ├── sync-manager.js       # Real-time sync
│   │   ├── command-palette.js    # Command palette UI
│   │   ├── task-editor.js        # Rich task editor
│   │   ├── kanban.js             # Kanban board
│   │   ├── calendar.js           # Calendar view
│   │   └── app.js                # Main application
│   ├── css/
│   │   ├── terminal-theme.css    # Terminal-inspired styles
│   │   ├── material-flat.css     # Flat material components
│   │   └── main.css              # Application styles
│   └── manifest.json
└── templates/
    └── index.html                # Single-page application
```

## Data Architecture

### Storage Strategy

**Primary Storage:** Markdown files with YAML frontmatter (current)
- Preserves human readability
- Git-friendly version control
- CLI compatibility
- Location: `~/.todo/projects/`

**Secondary Index:** SQLite database (new)
- Fast full-text search
- Multi-user queries
- Sync metadata
- User session management
- Location: `~/.todo/webapp.db`

**Cache Layer:** Redis (optional, for scaling)
- Real-time sync coordination
- WebSocket pub/sub
- Session management
- Rate limiting

### Database Schema (SQLite)

```sql
-- Users
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    settings JSON
);

-- User sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Todo index (mirrors markdown storage)
CREATE TABLE todo_index (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    project TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    priority TEXT,
    due_date TIMESTAMP,
    tags JSON,
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    markdown_path TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Full-text search
CREATE VIRTUAL TABLE todo_fts USING fts5(
    text, description, tags, project,
    content=todo_index
);

-- Sync metadata
CREATE TABLE sync_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    last_sync TIMESTAMP,
    sync_version INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Shared projects (collaboration)
CREATE TABLE project_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    shared_with_id INTEGER NOT NULL,
    permission TEXT NOT NULL, -- 'view', 'edit', 'admin'
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    FOREIGN KEY (shared_with_id) REFERENCES users(id)
);
```

## Synchronization Architecture

### Real-Time Sync Strategy

**Protocol:** WebSocket for bidirectional communication

**Flow:**
1. Client connects via WebSocket with JWT token
2. Server subscribes client to user's sync channel
3. Changes broadcast to all connected clients
4. Optimistic UI updates with rollback on conflict
5. Conflict resolution via existing sync engine

### Sync Engine Extensions

Leverage existing `sync/sync_engine.py` for:
- Change detection
- Conflict resolution strategies
- Version tracking
- Merge logic

**New Components:**

```python
# src/todo_cli/webapp/server/sync_coordinator.py
class WebSyncCoordinator:
    """Coordinates real-time sync across web clients."""
    
    async def broadcast_change(self, user_id: int, change: TodoChange):
        """Broadcast change to all connected clients."""
        
    async def handle_client_change(self, user_id: int, change: TodoChange):
        """Process incoming change from client."""
        
    async def detect_conflicts(self, local_change, remote_change):
        """Use existing sync engine for conflict detection."""
```

### Conflict Resolution

**Strategies (from existing sync engine):**
- `LOCAL_WINS`: Web client's change takes precedence
- `REMOTE_WINS`: Server/other client's change wins
- `NEWEST_WINS`: Most recent timestamp wins
- `MERGE`: Intelligent field-level merge
- `MANUAL`: User chooses resolution

**UI for Conflicts:**
- Toast notification of conflict
- Side-by-side diff view
- One-click resolution options
- Merge editor for manual resolution

## Authentication & Security

### Authentication Flow

**JWT-based with Refresh Tokens**

1. **Registration/Login:**
   - POST `/api/auth/register` or `/api/auth/login`
   - Returns: `access_token` (15min) + `refresh_token` (30 days)
   - Tokens stored in httpOnly cookies

2. **Protected Endpoints:**
   - Middleware validates JWT from cookie or Authorization header
   - Extracts `user_id` for data scoping
   - Returns 401 if expired/invalid

3. **Token Refresh:**
   - POST `/api/auth/refresh` with refresh token
   - Returns new access token
   - Client automatically refreshes before expiry

### Security Measures

- Password hashing with bcrypt (work factor 12)
- CSRF protection for state-changing operations
- Rate limiting (100 req/min per user)
- SQL injection prevention (parameterized queries)
- XSS protection (Content Security Policy)
- CORS configuration for web origins only

## API Design

### REST Endpoints

```
# Authentication
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/logout
POST   /api/auth/refresh
GET    /api/auth/me

# Tasks (scoped to authenticated user)
GET    /api/tasks                    # List with filters
POST   /api/tasks                    # Create (natural language)
GET    /api/tasks/:id
PUT    /api/tasks/:id
DELETE /api/tasks/:id
PATCH  /api/tasks/:id/status
PATCH  /api/tasks/:id/complete
POST   /api/tasks/batch              # Bulk operations

# Projects
GET    /api/projects
POST   /api/projects
GET    /api/projects/:name
PUT    /api/projects/:name
DELETE /api/projects/:name

# Search
GET    /api/search?q=:query          # Full-text search
POST   /api/search/advanced          # Advanced query

# Sync
GET    /api/sync/status
POST   /api/sync/pull                # Force pull from storage
POST   /api/sync/push                # Force push to storage

# Collaboration
POST   /api/projects/:name/share
GET    /api/projects/:name/shares
DELETE /api/projects/:name/shares/:id

# Analytics
GET    /api/analytics/summary
GET    /api/analytics/productivity
GET    /api/analytics/trends
```

### WebSocket Protocol

```javascript
// Connection
ws://localhost:8000/ws/sync?token=<jwt_token>

// Messages (JSON)
{
  "type": "todo.created" | "todo.updated" | "todo.deleted",
  "data": {
    "id": 123,
    "project": "work",
    "text": "Task text",
    // ... todo fields
  },
  "timestamp": "2025-01-11T22:00:00Z",
  "user_id": 1,
  "device_id": "web-chrome-abc123"
}

// Server to Client
{
  "type": "sync.change",
  "data": { /* change data */ }
}

{
  "type": "sync.conflict",
  "data": {
    "conflict_type": "MODIFIED_BOTH",
    "local_version": { /* todo */ },
    "remote_version": { /* todo */ }
  }
}

{
  "type": "sync.status",
  "data": {
    "connected": true,
    "last_sync": "2025-01-11T21:59:00Z",
    "pending_changes": 0
  }
}
```

## UI/UX Design

### Terminal-Inspired Design System

**Color Palette:**
- Use existing theme engine (`src/todo_cli/theme_engine/`)
- Load theme configuration from user settings
- Support all existing themes (city_lights, dracula, gruvbox, nord, etc.)

**Typography:**
```css
--font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', 'Consolas', monospace;
--font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;

/* Sizes */
--text-xs: 0.75rem;   /* 12px */
--text-sm: 0.875rem;  /* 14px */
--text-base: 1rem;    /* 16px */
--text-lg: 1.125rem;  /* 18px */
--text-xl: 1.25rem;   /* 20px */
```

**Spacing:**
```css
/* 4px base unit */
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
```

**Shadows (Flat Material):**
```css
--shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.1);
--shadow-md: 0 2px 4px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 4px 8px rgba(0, 0, 0, 0.12);
```

### Key UI Components

#### 1. Command Palette (Primary Interaction)
- Keyboard shortcut: `Cmd/Ctrl + K`
- Fuzzy search for commands and tasks
- Natural language input (e.g., "add task buy milk @home ~high")
- Recent commands history
- Contextual suggestions

#### 2. Split-Pane Layout (Tmux-inspired)
```
┌────────────────────────────────────────┐
│  [☰] Todo CLI          [⚙] [@user] [×]│  ← Header
├──────────┬─────────────────────────────┤
│ Projects │  Active Tasks               │  ← Main content
│          │  ┌────────────────────────┐ │
│ • inbox  │  │ - [ ] Task 1          │ │
│ • work   │  │ - [ ] Task 2          │ │
│ • home   │  │ - [/] Task 3          │ │
│          │  └────────────────────────┘ │
│          │                             │
│          │  Completed Tasks            │
│          │  ┌────────────────────────┐ │
│          │  │ - [x] Done task       │ │
│          │  └────────────────────────┘ │
├──────────┴─────────────────────────────┤
│  ⌨ Press Cmd+K for command palette     │  ← Status bar
└────────────────────────────────────────┘
```

#### 3. Task Editor (Rich Inline Editing)
- Click task text to edit inline
- Metadata badges (priority, tags, due date)
- Drag handle for reordering
- Checkbox for status changes
- Context menu (right-click) for actions

#### 4. View Modes
- **List View:** Traditional task list (default)
- **Kanban Board:** Drag-drop between status columns
- **Calendar View:** Tasks by due date
- **Timeline:** Gantt-style project timeline
- **Focus Mode:** Single task, distraction-free

#### 5. Sync Indicator
```
Connected • Last sync 2m ago
Syncing... (3 items)
Offline • 5 pending changes
Conflict detected! [Resolve]
```

### Keyboard Shortcuts

**Global:**
- `Cmd/Ctrl + K`: Command palette
- `Cmd/Ctrl + N`: New task
- `Cmd/Ctrl + F`: Focus search
- `Cmd/Ctrl + ,`: Settings
- `Cmd/Ctrl + Shift + P`: Quick project switcher

**Navigation:**
- `↑/↓` or `j/k`: Navigate tasks (vim-style)
- `Enter`: Edit selected task
- `Escape`: Cancel/close
- `Space`: Toggle task completion
- `Tab`: Switch panes

**Task Actions:**
- `e`: Edit task
- `d`: Delete task
- `p`: Set priority
- `t`: Add tag
- `m`: Move to project
- `s`: Set status

## Multi-User Architecture

### Data Isolation

**User-Scoped Storage:**
- Each user has dedicated directory: `~/.todo/users/{user_id}/`
- Markdown files stored per-user
- Shared projects via symbolic links or references

**Database Queries:**
- All queries filtered by `user_id`
- Middleware injects `user_id` from JWT
- Row-level security enforced

### Collaboration Model

**Project Sharing:**
- Owner can share projects with other users
- Permissions: `view`, `edit`, `admin`
- Real-time updates for shared projects
- Activity feed shows who changed what

**Future: Teams & Organizations:**
- Team workspaces (Phase 10)
- Role-based access control
- Project templates

## Deployment Strategy

### Development

```bash
# Terminal 1: Start backend
cd src/todo_cli/webapp/server
uvicorn app:app --reload --port 8080

# Terminal 2: Watch frontend (if using build tool)
cd src/todo_cli/webapp/static
npm run dev  # Optional

# Access at http://localhost:8080
```

### Production

**Option 1: Docker Compose**
```yaml
version: '3.8'
services:
  webapp:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/root/.todo
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - REDIS_URL=redis://redis:6379
  
  redis:
    image: redis:7-alpine
```

**Option 2: Single Binary (uvicorn)**
```bash
uvicorn todo_cli.webapp.server.app:app \
  --host 0.0.0.0 \
  --port 8080 \
  --workers 4
```

## Migration Path

### Phase 1: Architecture & Design ✓
- Document architecture decisions
- Define API contracts
- Design UI/UX mockups

### Phase 2: Authentication & User Management
- Implement user registration/login
- JWT token management
- User settings storage

### Phase 3: Core Web UI
- Terminal-inspired design system
- Command palette
- Basic task CRUD

### Phase 4: Real-Time Sync
- WebSocket infrastructure
- Bidirectional sync
- Conflict resolution UI

### Phase 5: Advanced Features
- Kanban board, calendar, timeline views
- Collaboration and sharing
- Advanced analytics

## Open Questions & Decisions

### Resolved

1. **Storage Strategy:** Hybrid - Keep markdown as source of truth, add SQLite for indexing
2. **Authentication:** JWT with httpOnly cookies
3. **Sync Protocol:** WebSocket for real-time, REST for operations
4. **UI Framework:** Vanilla JS (consistent with PWA)

### To Resolve

1. **Redis Dependency:** Optional for development, required for multi-instance production?
2. **File Locking:** How to handle concurrent markdown file writes?
3. **Backup Strategy:** Automatic backups before sync operations?
4. **Mobile Experience:** Responsive web or dedicated mobile API endpoints?
5. **Migration Tool:** Script to migrate existing CLI users to web app?

## Performance Considerations

### Backend
- Connection pooling for database
- Redis caching for frequent queries
- Rate limiting to prevent abuse
- Pagination for large todo lists (100 items per page)
- Background jobs for heavy operations (analytics)

### Frontend
- Virtual scrolling for long task lists
- Debounced search/filter operations
- Optimistic UI updates
- Service worker caching for static assets
- Lazy loading for heavy components (calendar, analytics)

## Security Checklist

- [ ] Password hashing (bcrypt, work factor 12)
- [ ] JWT secret from environment variable
- [ ] httpOnly, Secure cookies in production
- [ ] CSRF tokens for state-changing operations
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS protection (Content Security Policy)
- [ ] Rate limiting (100 req/min per user)
- [ ] Input validation and sanitization
- [ ] Secure WebSocket connections (wss://)
- [ ] User data isolation (scoped queries)

## Monitoring & Observability

### Logging
- Structured JSON logging
- User actions (create, update, delete)
- Sync events (conflicts, resolutions)
- Authentication events (login, logout)
- Error tracking with stack traces

### Metrics
- Active WebSocket connections
- Sync latency (client to server round-trip)
- Conflict rate (conflicts per sync operation)
- API response times
- Database query performance

### Health Checks
- `/health`: Basic liveness check
- `/health/ready`: Readiness check (DB, Redis)
- `/metrics`: Prometheus-compatible metrics

## Conclusion

This architecture preserves the terminal aesthetic and CLI consistency while enabling sophisticated web-based task management with real-time sync. The hybrid storage strategy (markdown + SQLite) maintains human-readable files while supporting multi-user queries and full-text search.

Key decisions:
- **Separation**: PWA remains offline-first, Web App adds remote sync
- **Authentication**: JWT-based, user-scoped data
- **Sync**: WebSocket for real-time, leverages existing sync engine
- **UI**: Terminal-inspired flat material design with command palette
- **Storage**: Markdown primary, SQLite index for queries

Next steps: Begin Phase 2 with authentication and user management implementation.
