"""
Pydantic models for API validation
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, validator


# ============================================================================
# User Models
# ============================================================================

class UserBase(BaseModel):
    """Base user model"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    """User creation model"""
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """User login model"""
    username: str
    password: str
    remember: bool = False


class UserResponse(UserBase):
    """User response model"""
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Task Models
# ============================================================================

class TaskBase(BaseModel):
    """Base task model"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    due_date: Optional[datetime] = None
    project_id: Optional[str] = None
    tags: Optional[List[str]] = []
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if v is None:
            return []
        return [tag.strip() for tag in v if tag.strip()]


class TaskCreate(TaskBase):
    """Task creation model"""
    pass


class TaskUpdate(BaseModel):
    """Task update model - all fields optional"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    due_date: Optional[datetime] = None
    project_id: Optional[str] = None
    tags: Optional[List[str]] = None
    completed: Optional[bool] = None
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate and clean tags"""
        if v is None:
            return None
        return [tag.strip() for tag in v if tag.strip()]


class TaskResponse(TaskBase):
    """Task response model"""
    id: str
    user_id: str
    completed: bool
    created_at: datetime
    updated_at: datetime
    is_overdue: bool = False
    is_today: bool = False
    
    class Config:
        from_attributes = True


class TaskToggle(BaseModel):
    """Task completion toggle model"""
    completed: bool


# ============================================================================
# Project Models
# ============================================================================

class ProjectBase(BaseModel):
    """Base project model"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class ProjectCreate(ProjectBase):
    """Project creation model"""
    pass


class ProjectUpdate(BaseModel):
    """Project update model - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class ProjectResponse(ProjectBase):
    """Project response model"""
    id: str
    user_id: str
    task_count: int = 0
    completed_count: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Analytics Models
# ============================================================================

class TaskStats(BaseModel):
    """Task statistics model"""
    total_tasks: int = 0
    completed_tasks: int = 0
    active_tasks: int = 0
    due_today: int = 0
    overdue: int = 0
    completion_rate: float = 0.0


class ProductivityStats(BaseModel):
    """Productivity statistics model"""
    tasks_completed_today: int = 0
    tasks_completed_week: int = 0
    tasks_completed_month: int = 0
    average_completion_time: Optional[float] = None
    most_productive_day: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Analytics response model"""
    task_stats: TaskStats
    productivity: ProductivityStats
    tasks_by_priority: dict = {}
    tasks_by_project: dict = {}
    completion_trend: List[dict] = []


# ============================================================================
# Filter Models
# ============================================================================

class TaskFilter(BaseModel):
    """Task filter model"""
    search: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(all|active|completed)$")
    priority: Optional[str] = Field(None, pattern="^(all|low|medium|high)$")
    project_id: Optional[str] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


# ============================================================================
# Response Models
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Generic error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[dict]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================================
# Token Models
# ============================================================================

class Token(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """JWT token data"""
    username: Optional[str] = None
    exp: Optional[datetime] = None
