"""
FastAPI web server for Todo CLI PWA.

This module provides a REST API and serves the PWA interface for the Todo CLI application.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Import Todo CLI components
from todo_cli.config import get_config
from todo_cli.storage import Storage
from todo_cli.domain.todo import Todo
from todo_cli.domain.project import Project
from todo_cli.services.query_engine import QueryEngine


class TaskCreateRequest(BaseModel):
    """Request model for creating a new task."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    tags: Optional[List[str]] = None
    context: Optional[str] = None
    due_date: Optional[str] = None
    project: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    """Request model for updating an existing task."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high|urgent)$")
    tags: Optional[List[str]] = None
    context: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(pending|completed|blocked)$")


class TaskResponse(BaseModel):
    """Response model for task data."""
    id: str
    title: str
    description: Optional[str]
    priority: Optional[str]
    tags: List[str]
    context: Optional[str]
    status: str
    created_at: Optional[str]
    updated_at: Optional[str]
    due_date: Optional[str]
    project: Optional[str]
    is_blocked: bool
    dependencies: List[str]


class ContextResponse(BaseModel):
    """Response model for context data."""
    name: str
    task_count: int


class ProjectResponse(BaseModel):
    """Response model for project data."""
    name: str
    display_name: str
    description: str
    task_count: int
    completed_tasks: int
    active: bool
    created_at: str
    color: Optional[str] = None


class BackupResponse(BaseModel):
    """Response model for backup data."""
    filename: str
    created_at: str
    size: int


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = "healthy"
    timestamp: str
    version: str
    api_version: str = "v1"
    database_status: str
    total_tasks: int
    total_projects: int


class ErrorResponse(BaseModel):
    """Standard error response model."""
    detail: str
    type: str = "about:blank"
    title: str
    status: int
    instance: str


# Initialize FastAPI app
app = FastAPI(
    title="Todo CLI Web API",
    description="REST API for Todo CLI PWA",
    version="1.0.0"
)

# Add CORS middleware for development and PWA
# Restrict CORS origins to trusted development hosts and avoid credentialed requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Get paths
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Initialize templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Backup configuration
BACKUP_DIR = Path.home() / ".todo" / "backups"


def ensure_backup_dir() -> Path:
    """Ensure backup directory exists and return its path."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def sanitize_backup_filename(filename: str) -> str:
    """Validate backup filenames to prevent path traversal."""
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup filename is required",
        )

    normalized = Path(filename).name
    if normalized != filename or ".." in Path(filename).parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid backup filename")
    if not normalized.endswith(".json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Backups must be JSON files")
    return normalized


def build_backup_payload(storage: Storage) -> Dict[str, Any]:
    """Create a snapshot of all projects and tasks for backup."""
    config = get_config()
    projects = storage.list_projects() or [config.default_project]

    backup_data: Dict[str, Any] = {
        "projects": {},
        "config": {
            "default_project": config.default_project,
        },
        "metadata": {
            "created_at": datetime.utcnow().isoformat() + "Z",
            "version": "1.0"
        },
        "backup_metadata": {
            "version": "1.0",
            "backup_type": "manual"
        }
    }

    for project_name in projects:
        try:
            project, todos = storage.load_project(project_name)
            if project or todos:
                backup_data["projects"][project_name] = {
                    "project": project.to_dict() if project else {"name": project_name},
                    "todos": [todo.to_dict() for todo in todos] if todos else []
                }
        except Exception:
            continue

    return backup_data


def list_backup_files() -> List[BackupResponse]:
    """List available backups with metadata."""
    backup_dir = ensure_backup_dir()
    backups: List[BackupResponse] = []

    for backup_file in sorted(backup_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = backup_file.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z"

        try:
            with backup_file.open("r") as f:
                data = json.load(f)
                meta = data.get("backup_metadata", {})
                created_at = meta.get("timestamp", created_at)
        except (json.JSONDecodeError, OSError) as exc:
            # Continue listing backups even if metadata cannot be read
            print(f"Warning: Unable to read backup metadata from {backup_file.name}: {exc}")

        backups.append(BackupResponse(
            filename=backup_file.name,
            created_at=created_at,
            size=stat.st_size,
        ))

    return backups


def restore_backup(storage: Storage, filename: str) -> None:
    """Restore all projects and todos from a backup file."""
    safe_name = sanitize_backup_filename(filename)
    backup_path = ensure_backup_dir() / safe_name

    if not backup_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")

    with backup_path.open("r") as f:
        backup_data = json.load(f)

    projects_data = backup_data.get("projects", {})
    if not isinstance(projects_data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid backup format")

    for project_name, payload in projects_data.items():
        try:
            project_dict = payload.get("project", {"name": project_name})
            todos_data = payload.get("todos", [])

            project = Project.from_dict(project_dict)
            todos = [Todo.from_dict(todo_dict) for todo_dict in todos_data if isinstance(todo_dict, dict)]

            storage.save_project(project, todos)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Failed to restore project {project_name}: {exc}")

# Global dependencies
def get_todo_storage():
    """Get the todo storage instance."""
    config = get_config()
    return Storage(config)


def get_query_engine():
    """Get the query engine instance."""
    config = get_config()
    return QueryEngine(config.data_dir)


def todo_to_response(todo: Todo) -> TaskResponse:
    """Convert a Todo object to TaskResponse."""
    from todo_cli.domain.todo import TodoStatus
    
    # Get status string
    if todo.status == TodoStatus.COMPLETED:
        status = "completed"
    elif todo.status == TodoStatus.BLOCKED:
        status = "blocked"
    else:
        status = "pending"
    
    # Get context - handle both string and list
    context = None
    if todo.context:
        if isinstance(todo.context, list) and todo.context:
            context = todo.context[0]  # Take first context for simplicity
        elif isinstance(todo.context, str):
            context = todo.context
    
    # Use composite key: project:id to ensure uniqueness across projects
    project_name = todo.project if hasattr(todo, 'project') and todo.project else "inbox"
    composite_id = str(todo.id)
    
    return TaskResponse(
        id=composite_id,
        title=todo.text,  # Use 'text' attribute
        description=todo.description or "",
        priority=todo.priority.value if hasattr(todo.priority, 'value') else todo.priority,
        tags=todo.tags or [],
        context=context,
        status=status,
        created_at=todo.created.isoformat() if hasattr(todo, 'created') and todo.created else None,
        updated_at=todo.modified.isoformat() if hasattr(todo, 'modified') and todo.modified else None,
        due_date=todo.due_date.isoformat() if todo.due_date else None,
        project=project_name,
        is_blocked=todo.status == TodoStatus.BLOCKED,
        dependencies=getattr(todo, 'dependencies', []) or []
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main PWA page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", response_model=HealthResponse)
async def health_check(storage=Depends(get_todo_storage)):
    """Health check endpoint with system status."""
    try:
        # Check database connectivity by listing projects
        projects = storage.list_projects()
        database_status = "healthy"
        
        # Count total tasks across all projects
        total_tasks = 0
        total_projects = len(projects)
        
        for project_name in projects:
            try:
                project_obj, todos = storage.load_project(project_name)
                if todos:
                    total_tasks += len(todos)
            except Exception:
                # Don't fail health check if one project has issues
                pass
        
        return HealthResponse(
            timestamp=datetime.utcnow().isoformat() + "Z",
            version="1.0.0",
            database_status=database_status,
            total_tasks=total_tasks,
            total_projects=total_projects
        )
        
    except Exception as e:
        # Return unhealthy status but still 200 OK
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow().isoformat() + "Z", 
            version="1.0.0",
            database_status=f"error: {str(e)}",
            total_tasks=0,
            total_projects=0
        )


# Task endpoints
@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(
    context: Optional[str] = None,
    project: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    storage=Depends(get_todo_storage),
    query_engine=Depends(get_query_engine)
):
    """Get all tasks with optional filtering."""
    try:
        # Load all todos from all projects
        all_todos = []
        projects = storage.list_projects()
        
        for project_name in projects:
            try:
                project_obj, todos = storage.load_project(project_name)
                if project_obj and todos:  # Only add if both exist
                    all_todos.extend(todos)
            except Exception as e:
                # Log error but continue with other projects
                print(f"Warning: Failed to load project '{project_name}': {e}")
                continue
        
        # Apply filters
        filtered_todos = all_todos
        
        # Context filter - handle both string and list contexts
        if context:
            filtered_todos = [
                todo for todo in filtered_todos 
                if (
                    (isinstance(todo.context, list) and context in todo.context) or
                    (isinstance(todo.context, str) and todo.context == context) or
                    (todo.context == context)
                )
            ]
        
        # Project filter
        if project:
            filtered_todos = [todo for todo in filtered_todos if todo.project == project]
        
        # Status filter
        if status:
            from todo_cli.domain.todo import TodoStatus
            status_map = {
                "completed": TodoStatus.COMPLETED,
                "blocked": TodoStatus.BLOCKED, 
                "pending": TodoStatus.PENDING
            }
            if status in status_map:
                filtered_todos = [todo for todo in filtered_todos if todo.status == status_map[status]]
        
        # Search filter
        if search:
            search_lower = search.lower()
            filtered_todos = [
                todo for todo in filtered_todos
                if (search_lower in todo.text.lower() or 
                    (todo.description and search_lower in todo.description.lower()))
            ]
        
        # Convert todos to response format with error handling
        response_todos = []
        conversion_errors = 0
        
        for todo in filtered_todos:
            try:
                response_todo = todo_to_response(todo)
                response_todos.append(response_todo)
            except Exception as e:
                conversion_errors += 1
                print(f"Warning: Failed to convert todo {getattr(todo, 'id', 'unknown')}: {e}")
                continue
        
        if conversion_errors > 0:
            print(f"Warning: {conversion_errors} todos failed conversion")
            
        return response_todos
        
    except Exception as e:
        # Return structured error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve tasks",
                "details": str(e),
                "type": "server_error"
            }
        )


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreateRequest,
    storage=Depends(get_todo_storage)
):
    """Create a new task."""
    try:
        if not getattr(task_data, "title", "").strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="Title is required")

        # Get project name
        project_name = task_data.project or "default"
        
        # Load or create project to get next ID
        project, existing_todos = storage.load_project(project_name)
        if not project:
            project = Project(name=project_name)
            existing_todos = []
        
        # Get next ID
        next_id = 1
        if existing_todos:
            next_id = max(todo.id for todo in existing_todos) + 1
        
        # Create new todo
        todo = Todo(
            id=next_id,
            text=task_data.title,  # Use 'text' instead of 'title'
            project=project_name
        )
        
        # Set optional fields
        if task_data.description:
            todo.description = task_data.description
        if task_data.priority:
            from todo_cli.domain.todo import Priority
            todo.priority = Priority(task_data.priority)
        if task_data.tags:
            todo.tags = task_data.tags
        if task_data.context:
            todo.context = [task_data.context]
        
        # Parse due date if provided
        if task_data.due_date:
            from datetime import datetime
            try:
                todo.due_date = datetime.fromisoformat(task_data.due_date.replace('Z', '+00:00'))
            except ValueError:
                pass  # Invalid date format, ignore
        
        # Add todo to existing todos
        existing_todos.append(todo)
        
        # Save project
        storage.save_project(project, existing_todos)
        
        return todo_to_response(todo)
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, storage=Depends(get_todo_storage)):
    """Get a specific task by ID (format: project:id or just id for backward compatibility)."""
    try:
        # Parse composite ID (project:id) or plain ID
        if ':' in task_id:
            project_name, todo_id_str = task_id.split(':', 1)
            # Search in specific project
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if str(todo.id) == todo_id_str:
                        return todo_to_response(todo)
        else:
            # Backward compatibility: search all projects (returns first match)
            projects = storage.list_projects()
            for project_name in projects:
                project, todos = storage.load_project(project_name)
                if project and todos:
                    for todo in todos:
                        if str(todo.id) == task_id:
                            return todo_to_response(todo)
        
        raise HTTPException(status_code=404, detail="Task not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving task: {str(e)}")


@app.put("/api/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdateRequest,
    storage=Depends(get_todo_storage)
):
    """Update an existing task (ID format: project:id or just id)."""
    try:
        # Parse composite ID (project:id) or plain ID
        if ':' in task_id:
            project_name, todo_id_str = task_id.split(':', 1)
            # Update in specific project
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if str(todo.id) == todo_id_str:
                        # Update fields
                        if task_data.title is not None:
                            todo.text = task_data.title  # Use 'text' instead of 'title'
                        if task_data.description is not None:
                            todo.description = task_data.description
                        if task_data.priority is not None:
                            todo.priority = task_data.priority
                        if task_data.tags is not None:
                            todo.tags = task_data.tags
                        if task_data.context is not None:
                            todo.context = [task_data.context] if task_data.context else []
                        if task_data.status is not None:
                            from todo_cli.domain.todo import TodoStatus
                            if task_data.status == "completed":
                                todo.status = TodoStatus.COMPLETED
                            elif task_data.status == "blocked":
                                todo.status = TodoStatus.BLOCKED
                            else:  # pending
                                todo.status = TodoStatus.PENDING
                        
                        if task_data.due_date is not None:
                            if task_data.due_date:
                                from datetime import datetime
                                try:
                                    todo.due_date = datetime.fromisoformat(task_data.due_date.replace('Z', '+00:00'))
                                except ValueError:
                                    pass
                            else:
                                todo.due_date = None
                        
                        # Update timestamp
                        from datetime import datetime, timezone
                        todo.modified = datetime.now(timezone.utc)
                        
                        # Save project
                        storage.save_project(project, todos)
                        
                        return todo_to_response(todo)
        
        raise HTTPException(status_code=404, detail="Task not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating task: {str(e)}")


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, storage=Depends(get_todo_storage)):
    """Delete a task (ID format: project:id or just id)."""
    try:
        # Parse composite ID (project:id) or plain ID
        if ':' in task_id:
            project_name, todo_id_str = task_id.split(':', 1)
            # Delete from specific project
            project, todos = storage.load_project(project_name)
            if project and todos:
                for i, todo in enumerate(todos):
                    if str(todo.id) == todo_id_str:
                        todos.pop(i)
                        storage.save_project(project, todos)
                        return {"message": "Task deleted successfully"}
        else:
            # Backward compatibility: search all projects
            projects = storage.list_projects()
            for project_name in projects:
                project, todos = storage.load_project(project_name)
                if project and todos:
                    for i, todo in enumerate(todos):
                        if str(todo.id) == task_id:
                            todos.pop(i)
                            storage.save_project(project, todos)
                            return {"message": "Task deleted successfully"}
        
        raise HTTPException(status_code=404, detail="Task not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")


# Project endpoints
@app.get("/api/projects", response_model=List[ProjectResponse])
async def get_projects(storage=Depends(get_todo_storage)):
    """Get all projects with task counts."""
    try:
        projects_data = []
        projects = storage.list_projects()
        
        for project_name in projects:
            try:
                project_obj, todos = storage.load_project(project_name)
                if project_obj:
                    # Count tasks by status
                    task_count = len(todos) if todos else 0
                    completed_tasks = 0
                    
                    if todos:
                        from todo_cli.domain.todo import TodoStatus
                        completed_tasks = sum(1 for todo in todos if todo.status == TodoStatus.COMPLETED)
                    
                    projects_data.append(ProjectResponse(
                        name=project_obj.name,
                        display_name=project_obj.display_name or project_obj.name,
                        description=project_obj.description or "",
                        task_count=task_count,
                        completed_tasks=completed_tasks,
                        active=project_obj.active,
                        created_at=project_obj.created.isoformat() if hasattr(project_obj, 'created') and project_obj.created else "",
                        color=getattr(project_obj, 'color', None)
                    ))
            except Exception as e:
                print(f"Warning: Failed to load project '{project_name}': {e}")
                continue
        
        return projects_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "message": "Failed to retrieve projects",
                "details": str(e),
                "type": "server_error"
            }
        )


# Context endpoints
@app.get("/api/contexts", response_model=List[ContextResponse])
async def get_contexts(storage=Depends(get_todo_storage)):
    """Get all available contexts."""
    try:
        contexts = {}
        projects = storage.list_projects()
        
        for project_name in projects:
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if todo.context:
                        # Handle context as list
                        context_list = todo.context if isinstance(todo.context, list) else [todo.context]
                        for context in context_list:
                            contexts[context] = contexts.get(context, 0) + 1
        
        return [
            ContextResponse(name=context, task_count=count)
            for context, count in contexts.items()
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving contexts: {str(e)}")


# Tag endpoints
@app.get("/api/tags")
async def get_tags(storage=Depends(get_todo_storage)):
    """Get all available tags."""
    try:
        tags = {}
        projects = storage.list_projects()
        
        for project_name in projects:
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if todo.tags:
                        for tag in todo.tags:
                            tags[tag] = tags.get(tag, 0) + 1
        
        return [
            {"name": tag, "task_count": count}
            for tag, count in tags.items()
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tags: {str(e)}")


# Backup endpoints
@app.get("/api/backups", response_model=List[BackupResponse])
async def get_backups():
    """Get list of available backups."""
    try:
        return list_backup_files()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving backups: {str(e)}")


@app.post("/api/backups", response_model=BackupResponse)
async def create_backup_api(storage=Depends(get_todo_storage)):
    """Create a new backup."""
    try:
        ensure_backup_dir()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_manual.json"
        backup_path = BACKUP_DIR / filename

        payload = build_backup_payload(storage)
        payload["backup_metadata"]["timestamp"] = datetime.utcnow().isoformat() + "Z"

        with backup_path.open("w") as f:
            json.dump(payload, f, indent=2)

        stat = backup_path.stat()
        return BackupResponse(
            filename=filename,
            created_at=payload["backup_metadata"]["timestamp"],
            size=stat.st_size,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating backup: {str(e)}")


@app.post("/api/backups/{filename}/restore")
async def restore_backup_api(filename: str, storage=Depends(get_todo_storage)):
    """Restore from a backup."""
    try:
        restore_backup(storage, filename)
        return {"message": "Restore completed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring backup: {str(e)}")


# ---------------------------------------------------------------------------
# Dashboard API endpoints
# ---------------------------------------------------------------------------

class DashboardCreateRequest(BaseModel):
    """Request model for creating a dashboard."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = ""
    template: Optional[str] = None


@app.get("/api/dashboards")
async def list_dashboards_api():
    """List all saved dashboards."""
    try:
        from todo_cli.services.dashboard import DashboardManager
        manager = DashboardManager()
        return manager.list_dashboards()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing dashboards: {str(e)}")


@app.get("/api/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Get a specific dashboard by ID."""
    try:
        from todo_cli.services.dashboard import DashboardManager
        manager = DashboardManager()
        dashboard = manager.load_dashboard(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return dashboard.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving dashboard: {str(e)}")


@app.post("/api/dashboards")
async def create_dashboard_api(request: DashboardCreateRequest):
    """Create a new dashboard, optionally from a template."""
    try:
        from todo_cli.services.dashboard import DashboardManager
        manager = DashboardManager()

        template_map = {
            "productivity": "productivity_overview",
            "project": "project_dashboard",
            "time_tracking": "time_tracking",
            "minimal": "minimal",
        }

        if request.template and request.template in template_map:
            dashboard = manager.create_template_dashboard(template_map[request.template])
            dashboard.name = request.name
            if request.description:
                dashboard.description = request.description
            manager.save_dashboard(dashboard)
        else:
            dashboard = manager.create_dashboard(request.name, request.description or "")

        return dashboard.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating dashboard: {str(e)}")


@app.delete("/api/dashboards/{dashboard_id}")
async def delete_dashboard_api(dashboard_id: str):
    """Delete a dashboard."""
    try:
        from todo_cli.services.dashboard import DashboardManager
        manager = DashboardManager()
        if manager.delete_dashboard(dashboard_id):
            return {"message": "Dashboard deleted successfully"}
        raise HTTPException(status_code=404, detail="Dashboard not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting dashboard: {str(e)}")


@app.get("/api/dashboards/{dashboard_id}/data")
async def get_dashboard_data(dashboard_id: str, storage=Depends(get_todo_storage)):
    """Refresh and return all widget data for a dashboard."""
    try:
        from todo_cli.services.dashboard import DashboardManager
        manager = DashboardManager()
        dashboard = manager.load_dashboard(dashboard_id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        # Collect all todos for data refresh
        all_todos = []
        projects = storage.list_projects()
        for project_name in projects:
            try:
                project_obj, todos = storage.load_project(project_name)
                if todos:
                    all_todos.extend(todos)
            except Exception:
                continue

        manager.refresh_dashboard_data(dashboard, all_todos)
        return dashboard.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing dashboard: {str(e)}")


# Note: Main health endpoint is at /health (not /api/health)


# ---------------------------------------------------------------------------
# Pomodoro API endpoints
# ---------------------------------------------------------------------------

# Module-level timer instance for the web API
_pomodoro_timer = None


def _get_pomodoro_timer():
    global _pomodoro_timer
    if _pomodoro_timer is None:
        from todo_cli.services.pomodoro import PomodoroTimer
        _pomodoro_timer = PomodoroTimer()
    return _pomodoro_timer


class PomodoroStartRequest(BaseModel):
    """Request model for starting a pomodoro session."""
    task_id: Optional[str] = None
    task_text: Optional[str] = None
    duration: Optional[int] = None


@app.post("/api/pomodoro/start")
async def pomodoro_start(request: PomodoroStartRequest):
    """Start a pomodoro focus session."""
    try:
        timer = _get_pomodoro_timer()
        if request.duration:
            timer.config.focus_minutes = request.duration
        session = timer.start_focus(task_id=request.task_id, task_text=request.task_text)
        return {
            "status": "started",
            "session": session.to_dict(),
            "remaining_seconds": timer.get_remaining_seconds(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting pomodoro: {str(e)}")


@app.post("/api/pomodoro/stop")
async def pomodoro_stop():
    """Stop/interrupt the current pomodoro session."""
    try:
        timer = _get_pomodoro_timer()
        session = timer.interrupt_session()
        if session:
            return {"status": "stopped", "session": session.to_dict()}
        return {"status": "idle", "message": "No active session"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping pomodoro: {str(e)}")


@app.post("/api/pomodoro/pause")
async def pomodoro_pause():
    """Pause the current pomodoro session."""
    try:
        timer = _get_pomodoro_timer()
        timer.pause()
        return {"status": timer.state.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error pausing pomodoro: {str(e)}")


@app.post("/api/pomodoro/resume")
async def pomodoro_resume():
    """Resume a paused pomodoro session."""
    try:
        timer = _get_pomodoro_timer()
        timer.resume()
        return {"status": timer.state.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resuming pomodoro: {str(e)}")


@app.get("/api/pomodoro/status")
async def pomodoro_status():
    """Get current pomodoro timer status."""
    try:
        timer = _get_pomodoro_timer()
        result = {
            "state": timer.state.value,
            "session_count": timer.session_count,
            "remaining_seconds": timer.get_remaining_seconds(),
        }
        if timer.current_session:
            result["current_session"] = timer.current_session.to_dict()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting pomodoro status: {str(e)}")


@app.get("/api/pomodoro/stats")
async def pomodoro_stats(days: int = 7):
    """Get pomodoro statistics."""
    try:
        timer = _get_pomodoro_timer()
        stats = timer.get_stats(days=days)
        return {
            "total_sessions": stats.total_sessions,
            "completed_sessions": stats.completed_sessions,
            "interrupted_sessions": stats.interrupted_sessions,
            "total_focus_minutes": stats.total_focus_minutes,
            "total_break_minutes": stats.total_break_minutes,
            "average_focus_minutes": stats.average_focus_minutes,
            "current_streak": stats.current_streak,
            "best_streak": stats.best_streak,
            "sessions_today": stats.sessions_today,
            "focus_minutes_today": stats.focus_minutes_today,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting pomodoro stats: {str(e)}")


@app.get("/api/pomodoro/history")
async def pomodoro_history(limit: int = 20):
    """Get pomodoro session history."""
    try:
        timer = _get_pomodoro_timer()
        sessions = timer.history[-limit:]
        return [s.to_dict() for s in sessions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting pomodoro history: {str(e)}")


# ---------------------------------------------------------------------------
# AI API endpoints
# ---------------------------------------------------------------------------


class AIAskRequest(BaseModel):
    """Request model for AI ask endpoint."""
    question: str = Field(..., min_length=1)


class AISuggestRequest(BaseModel):
    """Request model for AI suggest endpoint."""
    context: Optional[str] = None
    energy: Optional[str] = None
    available_time: Optional[int] = None


class AICategorizeRequest(BaseModel):
    """Request model for AI categorize endpoint."""
    text: str = Field(..., min_length=1)


def _get_ai_assistant():
    """Get a configured AI assistant or raise 503."""
    from todo_cli.services.ai_assistant import create_assistant_from_config

    assistant = create_assistant_from_config()
    if assistant is None or not assistant.provider.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI provider is not available. Install the required package and configure credentials.",
        )
    return assistant


def _load_all_todos(storage):
    """Load all todos from all projects."""
    all_todos = []
    projects = storage.list_projects()
    for project_name in projects:
        try:
            _, todos = storage.load_project(project_name)
            if todos:
                all_todos.extend(todos)
        except Exception:
            continue
    return all_todos


@app.post("/api/ai/suggest")
async def ai_suggest(request: AISuggestRequest, storage=Depends(get_todo_storage)):
    """Get AI suggestion for next task to work on."""
    assistant = _get_ai_assistant()
    todos = _load_all_todos(storage)

    parts = []
    if request.context:
        parts.append(f"context: {request.context}")
    if request.energy:
        parts.append(f"energy level: {request.energy}")
    if request.available_time:
        parts.append(f"available time: {request.available_time} minutes")
    extra = ", ".join(parts) if parts else None

    try:
        result = assistant.suggest_next_task(todos, context=extra)
        return {"suggestion": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@app.post("/api/ai/ask")
async def ai_ask(request: AIAskRequest, storage=Depends(get_todo_storage)):
    """Ask a natural language question about tasks."""
    assistant = _get_ai_assistant()
    todos = _load_all_todos(storage)

    try:
        result = assistant.smart_query(request.question, todos)
        return {"answer": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@app.post("/api/ai/categorize")
async def ai_categorize(request: AICategorizeRequest):
    """Auto-categorize a task with AI-suggested metadata."""
    assistant = _get_ai_assistant()

    try:
        result = assistant.auto_categorize(request.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@app.get("/api/ai/summary")
async def ai_summary(
    project: Optional[str] = None,
    storage=Depends(get_todo_storage),
):
    """Get an AI-generated summary of task status."""
    assistant = _get_ai_assistant()
    todos = _load_all_todos(storage)

    if project:
        todos = [t for t in todos if t.project == project]

    try:
        result = assistant.summarize_tasks(todos)
        return {"summary": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@app.get("/api/ai/status")
async def ai_status():
    """Check AI provider availability."""
    from todo_cli.services.ai_assistant import OpenAIProvider, OllamaProvider

    config = get_config()
    provider_name = getattr(config, "ai_provider", "openai")

    openai_available = False
    ollama_available = False

    try:
        openai_prov = OpenAIProvider(
            api_key=getattr(config, "ai_openai_api_key", None),
        )
        openai_available = openai_prov.is_available()
    except Exception:
        pass

    try:
        ollama_prov = OllamaProvider(
            host=getattr(config, "ai_ollama_host", "http://localhost:11434"),
        )
        ollama_available = ollama_prov.is_available()
    except Exception:
        pass

    return {
        "configured_provider": provider_name,
        "model": getattr(config, "ai_model", "gpt-4o-mini"),
        "openai_available": openai_available,
        "ollama_available": ollama_available,
    }


# ---------------------------------------------------------------------------
# Collaboration API endpoints
# ---------------------------------------------------------------------------

from todo_cli.services.collaboration import (
    CollaborationDB,
    CollaborationManager,
    ProjectRole,
    ActivityType,
)
from todo_cli.services.realtime import realtime_manager

_collab_manager: Optional[CollaborationManager] = None


def _get_collab_manager() -> CollaborationManager:
    global _collab_manager
    if _collab_manager is None:
        _collab_manager = CollaborationManager()
    return _collab_manager


class ShareProjectRequest(BaseModel):
    name: str = Field(..., min_length=1)
    owner_id: str = Field(..., min_length=1)
    description: str = ""


class AddMemberRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    role: str = Field(default="editor", pattern="^(admin|editor|viewer)$")
    inviter_id: str = Field(..., min_length=1)


class CommentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class AssignRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    assigned_by: str = Field(..., min_length=1)


@app.post("/api/projects/share")
async def share_project_api(request: ShareProjectRequest):
    """Create a new shared project."""
    try:
        manager = _get_collab_manager()
        project = manager.share_project(request.name, request.owner_id, request.description)
        return project.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sharing project: {str(e)}")


@app.get("/api/projects/shared")
async def list_shared_projects_api(user_id: str):
    """List shared projects for a user."""
    try:
        manager = _get_collab_manager()
        projects = manager.db.list_user_projects(user_id)
        return [p.to_dict() for p in projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing shared projects: {str(e)}")


@app.get("/api/projects/{project_id}/members")
async def get_project_members_api(project_id: str):
    """Get members of a shared project."""
    try:
        manager = _get_collab_manager()
        members = manager.db.get_project_members(project_id)
        return [m.to_dict() for m in members]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting members: {str(e)}")


@app.post("/api/projects/{project_id}/members")
async def add_project_member_api(project_id: str, request: AddMemberRequest):
    """Add a member to a shared project."""
    try:
        manager = _get_collab_manager()
        role = ProjectRole(request.role)
        member = manager.invite_member(project_id, request.inviter_id,
                                       request.user_id, request.username, role)
        if member:
            return member.to_dict()
        raise HTTPException(status_code=403, detail="Permission denied")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding member: {str(e)}")


@app.delete("/api/projects/{project_id}/members/{user_id}")
async def remove_project_member_api(project_id: str, user_id: str):
    """Remove a member from a shared project."""
    try:
        manager = _get_collab_manager()
        success = manager.db.remove_member(project_id, user_id)
        if success:
            return {"message": "Member removed"}
        raise HTTPException(status_code=404, detail="Member not found or cannot remove owner")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing member: {str(e)}")


@app.get("/api/projects/{project_id}/activity")
async def get_project_activity_api(project_id: str, limit: int = 50):
    """Get activity feed for a project."""
    try:
        manager = _get_collab_manager()
        entries = manager.db.get_activity_feed(project_id, limit)
        return [e.to_dict() for e in entries]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting activity: {str(e)}")


@app.post("/api/tasks/{task_id}/comments")
async def add_task_comment_api(task_id: str, request: CommentRequest):
    """Add a comment to a task."""
    try:
        manager = _get_collab_manager()
        comment = manager.db.add_comment(task_id, request.user_id,
                                         request.username, request.content)
        return comment.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding comment: {str(e)}")


@app.get("/api/tasks/{task_id}/comments")
async def get_task_comments_api(task_id: str):
    """Get comments for a task."""
    try:
        manager = _get_collab_manager()
        comments = manager.db.get_comments(task_id)
        return [c.to_dict() for c in comments]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting comments: {str(e)}")


@app.post("/api/tasks/{task_id}/assign")
async def assign_task_api(task_id: str, request: AssignRequest):
    """Assign a task to a user."""
    try:
        manager = _get_collab_manager()
        success = manager.db.assign_task(task_id, request.user_id, request.assigned_by)
        if success:
            return {"message": "Task assigned", "task_id": task_id, "user_id": request.user_id}
        raise HTTPException(status_code=500, detail="Failed to assign task")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error assigning task: {str(e)}")


@app.get("/api/activity/me")
async def get_my_activity_api(user_id: str, limit: int = 50):
    """Get activity for the current user."""
    try:
        manager = _get_collab_manager()
        entries = manager.db.get_user_activity(user_id, limit)
        return [e.to_dict() for e in entries]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting activity: {str(e)}")


# WebSocket endpoint for real-time updates
from fastapi import WebSocket, WebSocketDisconnect


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for real-time collaboration updates."""
    await websocket.accept()
    username = user_id  # simplified; a real app would look up username
    connection_id = await realtime_manager.connect(websocket, user_id, username)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue
            action = msg.get("action")
            if action == "subscribe":
                project_id = msg.get("project_id")
                if project_id:
                    await realtime_manager.subscribe_project(connection_id, project_id)
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "project_id": project_id,
                    }))
            elif action == "unsubscribe":
                project_id = msg.get("project_id")
                if project_id:
                    await realtime_manager.unsubscribe_project(connection_id, project_id)
                    await websocket.send_text(json.dumps({
                        "type": "unsubscribed",
                        "project_id": project_id,
                    }))
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        await realtime_manager.disconnect(connection_id)
    except Exception:
        await realtime_manager.disconnect(connection_id)


def start_server(host: str = "127.0.0.1", port: int = 8000, debug: bool = False):
    """Start the web server."""
    uvicorn.run(
        "todo_cli.web.server:app",
        host=host,
        port=port,
        reload=debug,
        reload_dirs=["src/todo_cli"] if debug else None
    )


if __name__ == "__main__":
    start_server(debug=True)