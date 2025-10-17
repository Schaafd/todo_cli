"""
FastAPI web server for Todo CLI PWA.

This module provides a REST API and serves the PWA interface for the Todo CLI application.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from fastapi import FastAPI, HTTPException, Request, Depends
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


class BackupResponse(BaseModel):
    """Response model for backup data."""
    filename: str
    created_at: str
    size: int


# Initialize FastAPI app
app = FastAPI(
    title="Todo CLI Web API",
    description="REST API for Todo CLI PWA",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
    
    return TaskResponse(
        id=str(todo.id),
        title=todo.text,  # Use 'text' attribute
        description=todo.description or "",
        priority=todo.priority.value if hasattr(todo.priority, 'value') else todo.priority,
        tags=todo.tags or [],
        context=context,
        status=status,
        created_at=todo.created.isoformat() if hasattr(todo, 'created') and todo.created else None,
        updated_at=todo.modified.isoformat() if hasattr(todo, 'modified') and todo.modified else None,
        due_date=todo.due_date.isoformat() if todo.due_date else None,
        project=todo.project if hasattr(todo, 'project') else None,
        is_blocked=todo.status == TodoStatus.BLOCKED,
        dependencies=getattr(todo, 'dependencies', []) or []
    )


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main PWA page."""
    return templates.TemplateResponse("index.html", {"request": request})


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
        print(f"DEBUG: Found projects: {projects}")
        
        for project_name in projects:
            project_obj, todos = storage.load_project(project_name)
            print(f"DEBUG: Project '{project_name}' loaded: project={project_obj is not None}, todos_count={len(todos) if todos else 0}")
            if project_obj:  # Process projects even if todos list is empty
                if todos:  # Only extend if todos is not None and not empty
                    print(f"DEBUG: Adding {len(todos)} todos from project '{project_name}'")
                    all_todos.extend(todos)
        
        # Apply filters
        filtered_todos = all_todos
        print(f"DEBUG: Filter params - context: {context}, project: {project}, status: {status}, search: {search}")
        print(f"DEBUG: Before filtering - todos count: {len(filtered_todos)}")
        if filtered_todos:
            first_todo = filtered_todos[0]
            print(f"DEBUG: Sample todo - id: {getattr(first_todo, 'id', 'missing')}, text: {getattr(first_todo, 'text', 'missing')}, status: {getattr(first_todo, 'status', 'missing')}, context: {getattr(first_todo, 'context', 'missing')}")
        
        if context:
            print(f"DEBUG: Filtering by context: {context}")
            filtered_todos = [todo for todo in filtered_todos if todo.context == context]
        
        if project:
            filtered_todos = [todo for todo in filtered_todos if todo.project == project]
        
        if status:
            from todo_cli.domain.todo import TodoStatus
            if status == "completed":
                filtered_todos = [todo for todo in filtered_todos if todo.status == TodoStatus.COMPLETED]
            elif status == "blocked":
                filtered_todos = [todo for todo in filtered_todos if todo.status == TodoStatus.BLOCKED]
            elif status == "pending":
                filtered_todos = [todo for todo in filtered_todos if todo.status == TodoStatus.PENDING]
        
        if search:
            search_lower = search.lower()
            filtered_todos = [
                todo for todo in filtered_todos
                if (search_lower in todo.text.lower() or 
                    (todo.description and search_lower in todo.description.lower()))
            ]
        
        print(f"DEBUG: Total todos loaded: {len(all_todos)}, after filtering: {len(filtered_todos)}")
        
        # Convert todos to response format with error handling
        response_todos = []
        for todo in filtered_todos:
            try:
                response_todo = todo_to_response(todo)
                response_todos.append(response_todo)
            except Exception as e:
                print(f"DEBUG: Error converting todo {getattr(todo, 'id', '?')}: {e}")
                continue
        
        print(f"DEBUG: Successfully converted {len(response_todos)} todos")
        return response_todos
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tasks: {str(e)}")


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
    """Get a specific task by ID."""
    try:
        # Search for the todo across all projects
        projects = storage.list_projects()
        
        for project_name in projects:
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if todo.id == task_id:
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
    """Update an existing task."""
    try:
        # Find and update the todo
        projects = storage.list_projects()
        
        for project_name in projects:
            project, todos = storage.load_project(project_name)
            if project and todos:
                for todo in todos:
                    if todo.id == task_id:
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
    """Delete a task."""
    try:
        # Find and delete the todo
        projects = storage.list_projects()
        
        for project_name in projects:
            project, todos = storage.load_project(project_name)
            if project and todos:
                for i, todo in enumerate(todos):
                    if todo.id == task_id:
                        todos.pop(i)
                        storage.save_project(project, todos)
                        return {"message": "Task deleted successfully"}
        
        raise HTTPException(status_code=404, detail="Task not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")


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


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Todo CLI Web API"}


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