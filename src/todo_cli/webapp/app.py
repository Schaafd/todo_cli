"""
FastAPI Web Application for Todo CLI
Terminal-inspired task management web interface
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
import uvicorn

from todo_cli.webapp.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)
from todo_cli.webapp.database import get_db, hash_password
from todo_cli.webapp.storage_bridge import get_storage_bridge
from todo_cli.webapp.models import (
    UserCreate,
    TaskCreate,
    TaskUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from todo_cli.domain import TodoStatus, Priority

# Initialize FastAPI app
app = FastAPI(
    title="Todo CLI Web",
    description="Terminal-inspired task management",
    version="1.0.0",
)

# Add session middleware for flash messages
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Mount static files
app.mount("/static", StaticFiles(directory="src/todo_cli/webapp/static"), name="static")

# Templates
templates = Jinja2Templates(directory="src/todo_cli/webapp/templates")

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Database and storage bridge are initialized on first access
    pass


# ============================================================================
# Template Context Processors
# ============================================================================

def get_template_context(request: Request, current_user=None):
    """Get common template context"""
    context = {
        "request": request,
        "current_user": current_user,
    }
    
    if current_user:
        bridge = get_storage_bridge()
        projects = bridge.get_user_projects(current_user.id)
        tasks = bridge.get_user_tasks(current_user.id)
        context["projects"] = projects
        context["task_count"] = len(tasks)
    else:
        context["projects"] = []
        context["task_count"] = 0
    
    return context


# ============================================================================
# Authentication Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Root redirect to login or dashboard"""
    # Check if user is authenticated
    try:
        user = await get_current_user(request)
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: Optional[bool] = Form(False),
):
    """Process login form"""
    user = authenticate_user(username, password)
    
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Invalid username or password"
            },
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    
    # Create access token
    access_token_expires = timedelta(days=30 if remember else 1)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Set cookie and redirect
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=access_token_expires.total_seconds() if remember else None,
        samesite="lax"
    )
    
    return response


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    """Process registration form"""
    db = get_db()
    
    # Validation
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user exists
    if db.get_user_by_username(username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already taken"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    if db.get_user_by_email(email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Create user
    try:
        user = db.create_user(username, email, password)
    except ValueError as e:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": str(e)},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Auto-login after registration
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        samesite="lax"
    )
    
    return response


@app.get("/logout")
async def logout():
    """Logout user"""
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token")
    return response


# ============================================================================
# Dashboard & Main Views
# ============================================================================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, current_user=Depends(get_current_user)):
    """Dashboard page"""
    bridge = get_storage_bridge()
    context = get_template_context(request, current_user)
    
    # Get all user tasks
    all_tasks = bridge.get_user_tasks(current_user.id)
    
    # Calculate stats
    completed_tasks = [t for t in all_tasks if t.completed]
    today = datetime.now().date()
    today_tasks = [t for t in all_tasks if t.due_date and t.due_date.date() == today]
    overdue_tasks = [t for t in all_tasks if t.due_date and t.due_date.date() < today and not t.completed]
    
    context.update({
        "stats": {
            "total_tasks": len(all_tasks),
            "completed_tasks": len(completed_tasks),
            "due_today": len(today_tasks),
            "overdue": len(overdue_tasks),
        },
        "today_tasks": today_tasks[:5],
        "upcoming_tasks": [t for t in all_tasks if t.due_date and t.due_date.date() > today][:5],
        "recent_projects": bridge.get_user_projects(current_user.id)[:5],
    })
    
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, current_user=Depends(get_current_user)):
    """Tasks list page"""
    bridge = get_storage_bridge()
    context = get_template_context(request, current_user)
    
    tasks = bridge.get_user_tasks(current_user.id)
    context.update({
        "tasks": tasks,
    })
    
    return templates.TemplateResponse("tasks.html", context)


@app.get("/tasks/today", response_class=HTMLResponse)
async def tasks_today(request: Request, current_user=Depends(get_current_user)):
    """Today's tasks page"""
    context = get_template_context(request, current_user)
    context.update({
        "tasks": [],  # Filtered to today
        "page_title": "Today's Tasks",
    })
    
    return templates.TemplateResponse("tasks.html", context)


@app.get("/tasks/upcoming", response_class=HTMLResponse)
async def tasks_upcoming(request: Request, current_user=Depends(get_current_user)):
    """Upcoming tasks page"""
    context = get_template_context(request, current_user)
    context.update({
        "tasks": [],  # Filtered to next 7 days
        "page_title": "Upcoming Tasks",
    })
    
    return templates.TemplateResponse("tasks.html", context)


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, current_user=Depends(get_current_user)):
    """Projects list page"""
    context = get_template_context(request, current_user)
    context.update({
        "projects": [],  # Will be populated from database
    })
    
    return templates.TemplateResponse("projects.html", context)


@app.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(
    request: Request,
    project_id: str,
    current_user=Depends(get_current_user)
):
    """Project detail page"""
    context = get_template_context(request, current_user)
    context.update({
        "project": None,  # Will be fetched from database
        "tasks": [],
    })
    
    return templates.TemplateResponse("project_detail.html", context)


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request, current_user=Depends(get_current_user)):
    """Analytics page"""
    context = get_template_context(request, current_user)
    context.update({
        "analytics": {},  # Will be populated from analytics service
    })
    
    return templates.TemplateResponse("analytics.html", context)


# ============================================================================
# API Routes
# ============================================================================

@app.get("/api/tasks")
async def api_get_tasks(
    current_user=Depends(get_current_user),
    project: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
):
    """Get all tasks for current user with optional filtering"""
    bridge = get_storage_bridge()
    
    # Parse filters
    status_filter = TodoStatus(status) if status else None
    priority_filter = Priority(priority) if priority else None
    
    tasks = bridge.get_user_tasks(
        current_user.id,
        project_name=project,
        status=status_filter,
        priority=priority_filter
    )
    
    return {
        "tasks": [
            {
                "id": t.id,
                "text": t.text,
                "project": t.project,
                "status": t.status.value,
                "completed": t.completed,
                "priority": t.priority.value,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "tags": t.tags,
                "created_at": t.created.isoformat() if hasattr(t, 'created') and t.created else None,
            }
            for t in tasks
        ]
    }


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: int, current_user=Depends(get_current_user)):
    """Get single task"""
    bridge = get_storage_bridge()
    task = bridge.get_task(current_user.id, task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task": {
            "id": task.id,
            "text": task.text,
            "project": task.project,
            "status": task.status.value,
            "completed": task.completed,
            "priority": task.priority.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "tags": task.tags,
            "description": task.description if hasattr(task, 'description') else None,
            "created_at": task.created.isoformat() if hasattr(task, 'created') and task.created else None,
        }
    }


@app.post("/api/tasks")
async def api_create_task(
    task: TaskCreate,
    current_user=Depends(get_current_user)
):
    """Create new task"""
    bridge = get_storage_bridge()
    
    # Check if user has access to project
    project_name = task.project_id or "inbox"
    
    try:
        # Create task
        new_task = bridge.create_task(
            current_user.id,
            project_name,
            task.title,
            description=task.description,
            priority=Priority(task.priority) if task.priority else Priority.MEDIUM,
            due_date=task.due_date,
            tags=task.tags or [],
        )
        
        return {
            "success": True,
            "task_id": new_task.id,
            "task": {
                "id": new_task.id,
                "text": new_task.text,
                "project": new_task.project,
                "priority": new_task.priority.value,
            }
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@app.put("/api/tasks/{task_id}")
async def api_update_task(
    task_id: int,
    task: TaskUpdate,
    current_user=Depends(get_current_user)
):
    """Update task"""
    bridge = get_storage_bridge()
    
    # Build updates dict
    updates = {}
    if task.title is not None:
        updates["text"] = task.title
    if task.description is not None:
        updates["description"] = task.description
    if task.priority is not None:
        updates["priority"] = Priority(task.priority)
    if task.due_date is not None:
        updates["due_date"] = task.due_date
    if task.tags is not None:
        updates["tags"] = task.tags
    if task.completed is not None:
        updates["completed"] = task.completed
        updates["status"] = TodoStatus.COMPLETED if task.completed else TodoStatus.PENDING
    
    try:
        updated_task = bridge.update_task(current_user.id, task_id, **updates)
        
        if not updated_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/tasks/{task_id}/toggle")
async def api_toggle_task(task_id: int, current_user=Depends(get_current_user)):
    """Toggle task completion status"""
    bridge = get_storage_bridge()
    
    try:
        updated_task = bridge.toggle_task_completion(current_user.id, task_id)
        
        if not updated_task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {
            "success": True,
            "completed": updated_task.completed
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: int, current_user=Depends(get_current_user)):
    """Delete task"""
    bridge = get_storage_bridge()
    
    try:
        success = bridge.delete_task(current_user.id, task_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return {"success": True}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ============================================================================
# Project API Routes
# ============================================================================

@app.get("/api/projects")
async def api_get_projects(current_user=Depends(get_current_user)):
    """Get all projects for current user"""
    bridge = get_storage_bridge()
    projects = bridge.get_user_projects(current_user.id)
    
    return {
        "projects": [
            {
                "id": p.name,
                "name": p.display_name or p.name,
                "description": p.description,
                "color": p.color,
                "task_count": p.task_count if hasattr(p, 'task_count') else 0,
                "completed_count": p.completed_count if hasattr(p, 'completed_count') else 0,
            }
            for p in projects
        ]
    }


@app.post("/api/projects")
async def api_create_project(
    project: ProjectCreate,
    current_user=Depends(get_current_user)
):
    """Create new project"""
    bridge = get_storage_bridge()
    
    try:
        new_project = bridge.create_project_for_user(
            current_user.id,
            project.name,
            description=project.description,
            color=project.color
        )
        
        return {
            "success": True,
            "project_id": new_project.name,
            "project": {
                "id": new_project.name,
                "name": new_project.display_name or new_project.name,
                "description": new_project.description,
                "color": new_project.color,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """404 error handler"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": 404,
            "error_message": "Page not found"
        },
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    """500 error handler"""
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_code": 500,
            "error_message": "Internal server error"
        },
        status_code=500
    )


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the web application"""
    uvicorn.run(
        "todo_cli.webapp.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
