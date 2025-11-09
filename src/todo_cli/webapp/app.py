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
    get_password_hash,
)
from todo_cli.webapp.database import (
    get_db,
    create_user,
    get_user_by_username,
    get_user_by_email,
)
from todo_cli.webapp.models import UserCreate, TaskCreate, TaskUpdate

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

# Custom template filters
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    # Initialize database tables
    from todo_cli.webapp.database import init_db
    init_db()


# ============================================================================
# Template Context Processors
# ============================================================================

def get_template_context(request: Request, current_user=None):
    """Get common template context"""
    return {
        "request": request,
        "current_user": current_user,
        "projects": [],  # Will be populated from database
        "task_count": 0,  # Will be populated from database
    }


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
    db = next(get_db())
    user = authenticate_user(db, username, password)
    
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
    db = next(get_db())
    
    # Validation
    if password != password_confirm:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Passwords do not match"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if user exists
    if get_user_by_username(db, username):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Username already taken"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    if get_user_by_email(db, email):
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered"},
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    # Create user
    hashed_password = get_password_hash(password)
    user = create_user(db, username, email, hashed_password)
    
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
    # Mock data - will be replaced with database queries
    context = get_template_context(request, current_user)
    context.update({
        "stats": {
            "total_tasks": 24,
            "completed_tasks": 12,
            "due_today": 3,
            "overdue": 1,
        },
        "today_tasks": [],
        "upcoming_tasks": [],
        "recent_projects": [],
    })
    
    return templates.TemplateResponse("dashboard.html", context)


@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request, current_user=Depends(get_current_user)):
    """Tasks list page"""
    context = get_template_context(request, current_user)
    context.update({
        "tasks": [],  # Will be populated from database
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
async def api_get_tasks(current_user=Depends(get_current_user)):
    """Get all tasks for current user"""
    # TODO: Implement database query
    return {"tasks": []}


@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: str, current_user=Depends(get_current_user)):
    """Get single task"""
    # TODO: Implement database query
    return {"task": {}}


@app.post("/api/tasks")
async def api_create_task(
    task: TaskCreate,
    current_user=Depends(get_current_user)
):
    """Create new task"""
    # TODO: Implement database insert
    return {"success": True, "task_id": "new-task-id"}


@app.put("/api/tasks/{task_id}")
async def api_update_task(
    task_id: str,
    task: TaskUpdate,
    current_user=Depends(get_current_user)
):
    """Update task"""
    # TODO: Implement database update
    return {"success": True}


@app.post("/api/tasks/{task_id}/toggle")
async def api_toggle_task(task_id: str, current_user=Depends(get_current_user)):
    """Toggle task completion status"""
    # TODO: Implement database update
    return {"success": True}


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: str, current_user=Depends(get_current_user)):
    """Delete task"""
    # TODO: Implement database delete
    return {"success": True}


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
