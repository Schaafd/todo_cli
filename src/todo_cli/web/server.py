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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins for development
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
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
    composite_id = f"{project_name}:{todo.id}"
    
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
        # For now, return empty list
        # TODO: Implement backup functionality
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving backups: {str(e)}")


@app.post("/api/backups")
async def create_backup_api():
    """Create a new backup."""
    try:
        # TODO: Implement backup functionality
        return {"message": "Backup functionality not yet implemented", "filename": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating backup: {str(e)}")


@app.post("/api/backups/{filename}/restore")
async def restore_backup_api(filename: str):
    """Restore from a backup."""
    try:
        # TODO: Implement restore functionality
        return {"message": "Restore functionality not yet implemented"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring backup: {str(e)}")


# Note: Main health endpoint is at /health (not /api/health)


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