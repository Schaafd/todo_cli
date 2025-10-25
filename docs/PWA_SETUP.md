# Todo CLI PWA Setup Guide

This guide explains how to run the Todo CLI Progressive Web App (PWA) and REST API locally for development and testing.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [API Server Setup](#api-server-setup)
- [PWA Setup](#pwa-setup)
- [Environment Variables](#environment-variables)
- [Common Issues & Solutions](#common-issues--solutions)
- [API Documentation](#api-documentation)

---

## Prerequisites

### Required Software

- **Python 3.11+**: Main application runtime
- **uv**: Fast Python package manager ([installation guide](https://github.com/astral-sh/uv))
- **Modern Browser**: Chrome, Firefox, Safari, or Edge for PWA testing

### Optional Software

- **curl** or **httpie**: For testing API endpoints
- **jq**: For pretty-printing JSON responses

---

## Quick Start

The fastest way to get both the API and PWA running:

```bash
# 1. Clone and install dependencies
git clone https://github.com/Schaafd/todo_cli.git
cd todo_cli
uv sync --all-extras

# 2. Start the API server (in one terminal)
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000

# 3. Open PWA in your browser
# Navigate to: http://127.0.0.1:8000
```

That's it! The PWA will be served at the root URL and will automatically connect to the API.

---

## API Server Setup

### Starting the Server

#### Development Mode (Auto-reload)
```bash
cd /path/to/todo_cli
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000
```

#### Production Mode
```bash
uv run uvicorn src.todo_cli.web.server:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Background Mode
```bash
# Start in background
uv run uvicorn src.todo_cli.web.server:app --port 8000 > /tmp/todo_api.log 2>&1 &
echo $!  # Remember this PID

# Check logs
tail -f /tmp/todo_api.log

# Stop server
kill <PID>
```

### Verifying the Server

```bash
# Check health endpoint
curl http://127.0.0.1:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-25T21:17:45.454706Z",
#   "version": "1.0.0",
#   "api_version": "v1",
#   "database_status": "healthy",
#   "total_tasks": 35,
#   "total_projects": 16
# }

# Test task endpoint
curl http://127.0.0.1:8000/api/tasks | jq '.[:2]'
```

### Server Configuration

The API server uses FastAPI and serves both:
- **REST API endpoints** at `/api/*`
- **Static PWA files** at root `/`

Default configuration:
- Host: `127.0.0.1` (localhost only)
- Port: `8000`
- CORS: Enabled for local development
- Data source: `~/.todo/projects/` (Markdown files)

---

## PWA Setup

### Accessing the PWA

Once the API server is running, the PWA is automatically available:

```bash
# Open in your default browser
open http://127.0.0.1:8000

# Or manually navigate to:
# http://127.0.0.1:8000
```

### PWA Features

The PWA includes:
- **Task Management**: View, create, edit, delete tasks
- **Board View**: Kanban-style board (Pending, In Progress, Completed)
- **Context View**: Browse tasks by context
- **Tags View**: Browse tasks by tags
- **Backup/Restore**: Create and restore backups
- **Offline Support**: Service worker caches static assets
- **Smart Notifications**: Actionable error messages with retry

### PWA Architecture

```
src/todo_cli/web/
├── server.py              # FastAPI server (API + static files)
├── static/
│   ├── js/
│   │   ├── app.js         # Main application logic
│   │   ├── api.js         # API client wrapper
│   │   ├── ui.js          # UI rendering functions
│   │   ├── notifications.js  # Toast notification system
│   │   ├── data-loader.js    # Centralized data loading
│   │   ├── sw-manager.js     # Service worker manager
│   │   └── config.js         # Configuration
│   ├── css/
│   │   ├── main.css          # Main styles
│   │   └── enhancements.css  # Enhanced UI styles
│   ├── sw.js                 # Service worker
│   └── manifest.json         # PWA manifest
└── templates/
    └── index.html            # Main HTML template
```

### Service Worker & Offline Mode

The PWA includes a service worker for offline functionality:

- **Network-first** for API routes (always fetch fresh data)
- **Cache-first** for static assets (faster load times)
- **Offline indicator** when network is unavailable
- **Automatic cache cleanup** for stale data

To disable the service worker:
```javascript
// In browser console
navigator.serviceWorker.getRegistrations().then(registrations => {
    registrations.forEach(r => r.unregister());
});
```

---

## Environment Variables

### Optional Configuration

Create a `.env` file in the project root (not committed to git):

```bash
# API Configuration
API_HOST=127.0.0.1
API_PORT=8000
API_WORKERS=1

# Data Storage
TODO_DATA_PATH=~/.todo

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
LOG_LEVEL=info
```

### Example .env File

We provide `.env.example` as a template:

```bash
cp .env.example .env
# Edit .env with your settings
```

---

## Common Issues & Solutions

### Issue: API Server Won't Start

**Symptoms:**
- ModuleNotFoundError
- Port already in use
- Import errors

**Solutions:**

```bash
# 1. Verify installation
uv sync --all-extras

# 2. Check if port is in use
lsof -i :8000
# Kill process if needed: kill <PID>

# 3. Try a different port
uv run uvicorn src.todo_cli.web.server:app --port 8001

# 4. Check Python version
python --version  # Should be 3.11+
```

### Issue: PWA Shows "No Tasks"

**Symptoms:**
- PWA loads but shows empty state
- Console shows network errors
- Tasks exist in CLI but not in PWA

**Solutions:**

```bash
# 1. Verify API is running and returning data
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/tasks | jq 'length'

# 2. Check browser console for errors (F12)
# Look for:
# - CORS errors
# - Network timeouts
# - JSON parsing errors

# 3. Clear browser cache and service worker
# In DevTools > Application > Clear Storage > Clear site data

# 4. Verify tasks exist in CLI
uv run todo list

# 5. Check API endpoint directly
curl http://127.0.0.1:8000/api/tasks | jq '.[:2]'
```

### Issue: CORS Errors

**Symptoms:**
- Browser console shows CORS policy errors
- API requests blocked
- "Access-Control-Allow-Origin" errors

**Solutions:**

```bash
# 1. Verify CORS is enabled in server.py
# The server should have CORSMiddleware configured

# 2. Check allowed origins match your PWA URL
# Default allows: http://localhost:*, http://127.0.0.1:*

# 3. For custom origins, set CORS_ORIGINS env variable
export CORS_ORIGINS="http://localhost:3000,http://myapp.local"
```

### Issue: Service Worker Cache Issues

**Symptoms:**
- Old version of PWA loads after updates
- Static files don't update
- Stale data displayed

**Solutions:**

```javascript
// 1. Hard refresh in browser
// Chrome/Firefox: Ctrl+Shift+R (Cmd+Shift+R on Mac)

// 2. Clear service worker cache (DevTools Console)
caches.keys().then(keys => {
    keys.forEach(key => caches.delete(key));
    window.location.reload();
});

// 3. Unregister service worker
navigator.serviceWorker.getRegistrations().then(registrations => {
    registrations.forEach(r => r.unregister());
    window.location.reload();
});
```

### Issue: Notifications Not Appearing

**Symptoms:**
- Error messages don't show
- Success toasts missing
- No feedback on actions

**Solutions:**

```javascript
// 1. Check notifications.js is loaded
console.log(typeof notifications);  // Should be 'object'

// 2. Test notification system manually
notifications.success('Test notification', 3000);

// 3. Check browser console for JavaScript errors

// 4. Verify enhancements.css is loaded
// Look for .notification-container styles in DevTools
```

### Issue: Data Not Syncing Between CLI and PWA

**Symptoms:**
- Tasks added in CLI don't appear in PWA
- Changes in PWA not visible in CLI
- Stale data after reload

**Solutions:**

```bash
# 1. Verify both use the same data directory
# CLI config:
cat ~/.todo/config.yaml | grep storage_path

# API should read from the same location

# 2. Restart API server after CLI changes
# The API doesn't watch for file changes

# 3. Force PWA to reload data
# Click any view in PWA navigation to refresh

# 4. Check file permissions
ls -la ~/.todo/projects/
# Files should be readable by both CLI and API user
```

### Issue: Long API Response Times

**Symptoms:**
- Slow initial load
- Delayed task updates
- Timeout errors

**Solutions:**

```bash
# 1. Check task count
uv run todo list --all | wc -l

# 2. Archive completed tasks
uv run todo archive --older-than 90

# 3. Enable API logging to see slow queries
export LOG_LEVEL=debug

# 4. Consider pagination (future enhancement)
curl "http://127.0.0.1:8000/api/tasks?limit=50"
```

---

## API Documentation

### Base URL

```
http://127.0.0.1:8000
```

### Available Endpoints

#### Health Check
```bash
GET /health

Response:
{
  "status": "healthy",
  "timestamp": "2025-10-25T21:17:45.454706Z",
  "version": "1.0.0",
  "api_version": "v1",
  "database_status": "healthy",
  "total_tasks": 35,
  "total_projects": 16
}
```

#### List All Tasks
```bash
GET /api/tasks
GET /api/tasks?status=pending
GET /api/tasks?priority=high
GET /api/tasks?context=work

Response: Array of task objects
[
  {
    "id": "39",
    "title": "Test PWA integration",
    "description": "",
    "priority": "high",
    "tags": ["web"],
    "context": null,
    "status": "pending",
    "created_at": "2025-10-25T21:49:43.737464+00:00",
    "updated_at": "2025-10-25T21:49:43.737465+00:00",
    "due_date": "2025-10-26T00:00:00+00:00",
    "project": "inbox",
    "is_blocked": false,
    "dependencies": []
  }
]
```

#### Get Single Task
```bash
GET /api/tasks/{task_id}

Example:
curl http://127.0.0.1:8000/api/tasks/39

Response: Single task object (same structure as above)
```

#### Create Task
```bash
POST /api/tasks
Content-Type: application/json

{
  "title": "New task",
  "description": "Task description",
  "priority": "high",
  "tags": ["urgent"],
  "context": "work",
  "due_date": "2025-10-26T00:00:00Z"
}

Response: Created task object with id
```

#### Update Task
```bash
PUT /api/tasks/{task_id}
Content-Type: application/json

{
  "title": "Updated title",
  "status": "completed"
}

Response: Updated task object
```

#### Delete Task
```bash
DELETE /api/tasks/{task_id}

Response: 204 No Content
```

#### List Contexts
```bash
GET /api/contexts

Response:
[
  {
    "name": "work",
    "task_count": 12
  },
  {
    "name": "home",
    "task_count": 5
  }
]
```

#### List Tags
```bash
GET /api/tags

Response: Array of tag objects with counts
```

#### List Projects
```bash
GET /api/projects

Response: Array of project objects
```

#### List Backups
```bash
GET /api/backups

Response:
[
  {
    "filename": "backup_2025-10-25_12-30-45.zip",
    "created_at": "2025-10-25T12:30:45Z",
    "size": 102400
  }
]
```

#### Create Backup
```bash
POST /api/backups

Response:
{
  "filename": "backup_2025-10-25_14-22-10.zip",
  "size": 105600,
  "created_at": "2025-10-25T14:22:10Z"
}
```

#### Restore Backup
```bash
POST /api/backups/{filename}/restore

Response: 200 OK
{
  "message": "Backup restored successfully",
  "restored_tasks": 35
}
```

### Example API Usage

#### Using curl

```bash
# List all high priority tasks
curl -s "http://127.0.0.1:8000/api/tasks?priority=high" | jq '.'

# Create a new task
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fix critical bug",
    "priority": "urgent",
    "tags": ["bug", "critical"]
  }' | jq '.'

# Update task status
curl -X PUT http://127.0.0.1:8000/api/tasks/39 \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}' | jq '.'

# Delete a task
curl -X DELETE http://127.0.0.1:8000/api/tasks/39
```

#### Using httpie

```bash
# List tasks
http GET http://127.0.0.1:8000/api/tasks

# Create task
http POST http://127.0.0.1:8000/api/tasks \
  title="Review PR" \
  priority="high" \
  tags:='["review"]'

# Update task
http PUT http://127.0.0.1:8000/api/tasks/39 \
  status="completed"
```

#### Using JavaScript (in PWA)

```javascript
// The PWA includes an API client wrapper
// Available globally as `api`

// List tasks
const tasks = await api.getTasks({ priority: 'high' });

// Get single task
const task = await api.getTask('39');

// Create task
const newTask = await api.createTask({
  title: 'New task',
  priority: 'high',
  tags: ['urgent']
});

// Update task
await api.updateTask('39', { status: 'completed' });

// Delete task
await api.deleteTask('39');

// Toggle task completion
await api.toggleTask('39');

// Get contexts
const contexts = await api.getContexts();
```

---

## Development Tips

### Debugging the API

```bash
# Enable debug logging
export LOG_LEVEL=debug
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000 --log-level debug

# Watch API logs
tail -f /tmp/todo_api.log

# Test with verbose curl
curl -v http://127.0.0.1:8000/health
```

### Debugging the PWA

```javascript
// Open browser DevTools (F12)

// Enable debug mode (in config.js)
ENV.DEBUG = true;

// Check loaded modules
console.log('API:', typeof api);
console.log('Notifications:', typeof notifications);
console.log('Data Loader:', typeof dataLoader);
console.log('UI:', typeof ui);

// Monitor API requests
api.config.DEBUG = true;

// Test notification system
notifications.success('Test success', 3000);
notifications.error('Test error', 5000);
notifications.showNetworkError(() => console.log('Retry clicked'));

// Check service worker status
navigator.serviceWorker.ready.then(registration => {
    console.log('Service Worker:', registration);
});

// View cached data
caches.keys().then(keys => console.log('Cache keys:', keys));
```

### Hot Reload Workflow

```bash
# Terminal 1: API server with auto-reload
uv run uvicorn src.todo_cli.web.server:app --reload --port 8000

# Terminal 2: Watch logs
tail -f /tmp/todo_api.log

# Browser: PWA at http://127.0.0.1:8000
# Changes to Python code trigger API reload
# Changes to JS/CSS require browser refresh (Ctrl+R)
```

---

## Next Steps

- **Testing**: See [TESTING.md](./TESTING.md) for API and PWA test strategies
- **Contributing**: See [CONTRIBUTING.md](../CONTRIBUTING.md) for development guidelines
- **Production**: See [DEPLOYMENT.md](./DEPLOYMENT.md) for production setup (coming soon)

---

## Getting Help

If you encounter issues not covered here:

1. **Check the logs**: `tail -f /tmp/todo_api.log`
2. **Browser console**: Open DevTools (F12) and check Console and Network tabs
3. **Health check**: Verify API is responding: `curl http://127.0.0.1:8000/health`
4. **Report issues**: [GitHub Issues](https://github.com/Schaafd/todo_cli/issues)

Include in your report:
- Error messages (API logs and browser console)
- Steps to reproduce
- Environment (OS, Python version, browser)
- API health check output
