"""
Storage Bridge Layer

Bridges the web application with the existing CLI storage system, providing:
- User-scoped access to projects and tasks
- Multi-user concurrent access safety
- Permission management
- Integration with existing markdown storage
"""

from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set
from datetime import datetime
import json
import threading

from ..storage import Storage, ProjectMarkdownFormat, TodoMarkdownFormat
from ..domain import Todo, Project, TodoStatus, Priority
from ..config import ConfigModel, get_config
from .database import DatabaseManager, User, get_db


# ============================================================================
# User Permissions
# ============================================================================

class UserPermissions:
    """Manages user permissions for projects"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.permissions_file = Path.home() / ".todo" / "web_permissions.json"
        self._lock = threading.Lock()
        self._ensure_permissions_file()
    
    def _ensure_permissions_file(self):
        """Ensure permissions file exists"""
        if not self.permissions_file.exists():
            self.permissions_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_permissions({})
    
    def _load_permissions(self) -> Dict[str, Dict[str, List[str]]]:
        """Load permissions from file
        
        Returns:
            Dict mapping user_id -> {project_name: [permissions]}
        """
        try:
            with open(self.permissions_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _save_permissions(self, permissions: Dict[str, Dict[str, List[str]]]):
        """Save permissions to file"""
        with open(self.permissions_file, 'w') as f:
            json.dump(permissions, f, indent=2)
    
    def grant_project_access(
        self,
        user_id: str,
        project_name: str,
        permissions: Optional[List[str]] = None
    ):
        """Grant user access to a project
        
        Args:
            user_id: User ID
            project_name: Project name
            permissions: List of permissions (read, write, delete)
        """
        if permissions is None:
            permissions = ["read", "write"]
        
        with self._lock:
            perms = self._load_permissions()
            
            if user_id not in perms:
                perms[user_id] = {}
            
            perms[user_id][project_name] = permissions
            self._save_permissions(perms)
    
    def revoke_project_access(self, user_id: str, project_name: str):
        """Revoke user access to a project"""
        with self._lock:
            perms = self._load_permissions()
            
            if user_id in perms and project_name in perms[user_id]:
                del perms[user_id][project_name]
                self._save_permissions(perms)
    
    def get_user_projects(self, user_id: str) -> List[str]:
        """Get all projects a user has access to
        
        Args:
            user_id: User ID
            
        Returns:
            List of project names
        """
        perms = self._load_permissions()
        return list(perms.get(user_id, {}).keys())
    
    def has_permission(
        self,
        user_id: str,
        project_name: str,
        permission: str
    ) -> bool:
        """Check if user has permission for a project
        
        Args:
            user_id: User ID
            project_name: Project name
            permission: Permission to check (read, write, delete)
            
        Returns:
            True if user has permission
        """
        perms = self._load_permissions()
        
        if user_id not in perms or project_name not in perms[user_id]:
            return False
        
        return permission in perms[user_id][project_name]
    
    def get_project_permissions(
        self,
        user_id: str,
        project_name: str
    ) -> List[str]:
        """Get user's permissions for a project
        
        Args:
            user_id: User ID
            project_name: Project name
            
        Returns:
            List of permissions
        """
        perms = self._load_permissions()
        return perms.get(user_id, {}).get(project_name, [])


# ============================================================================
# Storage Bridge
# ============================================================================

class StorageBridge:
    """Bridges web app with CLI storage system"""
    
    def __init__(
        self,
        db: Optional[DatabaseManager] = None,
        config: Optional[ConfigModel] = None
    ):
        """Initialize storage bridge
        
        Args:
            db: Database manager instance
            config: Configuration model
        """
        self.db = db or get_db()
        self.config = config or get_config()
        self.storage = Storage(self.config)
        self.permissions = UserPermissions(self.db)
        self._lock = threading.Lock()
    
    # ========================================================================
    # Permission Helpers
    # ========================================================================
    
    def _check_permission(
        self,
        user_id: str,
        project_name: str,
        permission: str
    ):
        """Check permission and raise if denied
        
        Raises:
            PermissionError: If user doesn't have permission
        """
        if not self.permissions.has_permission(user_id, project_name, permission):
            raise PermissionError(
                f"User does not have '{permission}' permission for project '{project_name}'"
            )
    
    # ========================================================================
    # Project Operations
    # ========================================================================
    
    def create_project_for_user(
        self,
        user_id: str,
        project_name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> Project:
        """Create a new project for a user
        
        Args:
            user_id: User ID
            project_name: Project name
            description: Project description
            color: Project color
            
        Returns:
            Created Project object
        """
        # Create project
        project = Project(
            name=project_name,
            display_name=project_name,
            description=description or "",
            color=color
        )
        
        # Save project
        with self._lock:
            self.storage.save_project(project, [])
        
        # Grant user full access
        self.permissions.grant_project_access(
            user_id,
            project_name,
            ["read", "write", "delete"]
        )
        
        return project
    
    def get_user_projects(self, user_id: str) -> List[Project]:
        """Get all projects user has access to
        
        Args:
            user_id: User ID
            
        Returns:
            List of Project objects
        """
        project_names = self.permissions.get_user_projects(user_id)
        projects = []
        
        for project_name in project_names:
            project, _ = self.storage.load_project(project_name)
            if project:
                projects.append(project)
        
        return projects
    
    def get_project(
        self,
        user_id: str,
        project_name: str
    ) -> Optional[Project]:
        """Get a specific project
        
        Args:
            user_id: User ID
            project_name: Project name
            
        Returns:
            Project object or None
            
        Raises:
            PermissionError: If user doesn't have read permission
        """
        self._check_permission(user_id, project_name, "read")
        
        project, _ = self.storage.load_project(project_name)
        return project
    
    def update_project(
        self,
        user_id: str,
        project_name: str,
        description: Optional[str] = None,
        color: Optional[str] = None
    ) -> bool:
        """Update a project
        
        Args:
            user_id: User ID
            project_name: Project name
            description: New description
            color: New color
            
        Returns:
            True if updated successfully
            
        Raises:
            PermissionError: If user doesn't have write permission
        """
        self._check_permission(user_id, project_name, "write")
        
        with self._lock:
            project, todos = self.storage.load_project(project_name)
            
            if not project:
                return False
            
            if description is not None:
                project.description = description
            if color is not None:
                project.color = color
            
            return self.storage.save_project(project, todos)
    
    def delete_project(
        self,
        user_id: str,
        project_name: str
    ) -> bool:
        """Delete a project
        
        Args:
            user_id: User ID
            project_name: Project name
            
        Returns:
            True if deleted successfully
            
        Raises:
            PermissionError: If user doesn't have delete permission
        """
        self._check_permission(user_id, project_name, "delete")
        
        with self._lock:
            # Backup before delete
            self.storage.backup_project(project_name)
            
            # Delete project
            success = self.storage.delete_project(project_name)
            
            if success:
                # Revoke all permissions
                self.permissions.revoke_project_access(user_id, project_name)
            
            return success
    
    # ========================================================================
    # Task Operations
    # ========================================================================
    
    def get_user_tasks(
        self,
        user_id: str,
        project_name: Optional[str] = None,
        status: Optional[TodoStatus] = None,
        priority: Optional[Priority] = None,
        tags: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Todo]:
        """Get tasks for a user with optional filtering
        
        Args:
            user_id: User ID
            project_name: Filter by project
            status: Filter by status
            priority: Filter by priority
            tags: Filter by tags
            limit: Maximum number of tasks
            
        Returns:
            List of Todo objects
        """
        # Get accessible projects
        if project_name:
            # Check permission for specific project
            try:
                self._check_permission(user_id, project_name, "read")
                project_names = [project_name]
            except PermissionError:
                return []
        else:
            # Get all accessible projects
            project_names = self.permissions.get_user_projects(user_id)
        
        # Load tasks from all accessible projects
        all_tasks = []
        for pname in project_names:
            _, todos = self.storage.load_project(pname)
            all_tasks.extend(todos)
        
        # Apply filters
        filtered_tasks = all_tasks
        
        if status is not None:
            filtered_tasks = [t for t in filtered_tasks if t.status == status]
        
        if priority is not None:
            filtered_tasks = [t for t in filtered_tasks if t.priority == priority]
        
        if tags:
            filtered_tasks = [
                t for t in filtered_tasks
                if any(tag in t.tags for tag in tags)
            ]
        
        # Apply limit
        if limit:
            filtered_tasks = filtered_tasks[:limit]
        
        return filtered_tasks
    
    def get_task(
        self,
        user_id: str,
        task_id: int,
        project_name: Optional[str] = None
    ) -> Optional[Todo]:
        """Get a specific task
        
        Args:
            user_id: User ID
            task_id: Task ID
            project_name: Optional project hint
            
        Returns:
            Todo object or None
        """
        # If project specified, check that first
        if project_name:
            try:
                self._check_permission(user_id, project_name, "read")
                _, todos = self.storage.load_project(project_name)
                for todo in todos:
                    if todo.id == task_id:
                        return todo
            except PermissionError:
                pass
        
        # Otherwise search all accessible projects
        tasks = self.get_user_tasks(user_id)
        for task in tasks:
            if task.id == task_id:
                return task
        
        return None
    
    def create_task(
        self,
        user_id: str,
        project_name: str,
        text: str,
        **kwargs
    ) -> Todo:
        """Create a new task
        
        Args:
            user_id: User ID
            project_name: Project name
            text: Task text
            **kwargs: Additional task attributes
            
        Returns:
            Created Todo object
            
        Raises:
            PermissionError: If user doesn't have write permission
        """
        self._check_permission(user_id, project_name, "write")
        
        with self._lock:
            # Load project
            project, todos = self.storage.load_project(project_name)
            
            if not project:
                raise ValueError(f"Project '{project_name}' not found")
            
            # Get next ID
            next_id = self.storage.get_next_todo_id(project_name)
            
            # Create todo
            todo = Todo(
                id=next_id,
                text=text,
                project=project_name,
                **kwargs
            )
            
            # Add to project
            todos.append(todo)
            
            # Save
            self.storage.save_project(project, todos)
            
            return todo
    
    def update_task(
        self,
        user_id: str,
        task_id: int,
        project_name: Optional[str] = None,
        **updates
    ) -> Optional[Todo]:
        """Update a task
        
        Args:
            user_id: User ID
            task_id: Task ID
            project_name: Optional project hint
            **updates: Fields to update
            
        Returns:
            Updated Todo object or None
            
        Raises:
            PermissionError: If user doesn't have write permission
        """
        # Find task and its project
        task = self.get_task(user_id, task_id, project_name)
        if not task:
            return None
        
        task_project = task.project
        self._check_permission(user_id, task_project, "write")
        
        with self._lock:
            # Load project
            project, todos = self.storage.load_project(task_project)
            
            # Find and update task
            for i, todo in enumerate(todos):
                if todo.id == task_id:
                    # Update fields
                    for key, value in updates.items():
                        if hasattr(todo, key):
                            setattr(todo, key, value)
                    
                    todos[i] = todo
                    
                    # Save
                    self.storage.save_project(project, todos)
                    
                    return todo
        
        return None
    
    def delete_task(
        self,
        user_id: str,
        task_id: int,
        project_name: Optional[str] = None
    ) -> bool:
        """Delete a task
        
        Args:
            user_id: User ID
            task_id: Task ID
            project_name: Optional project hint
            
        Returns:
            True if deleted successfully
            
        Raises:
            PermissionError: If user doesn't have write permission
        """
        # Find task and its project
        task = self.get_task(user_id, task_id, project_name)
        if not task:
            return False
        
        task_project = task.project
        self._check_permission(user_id, task_project, "write")
        
        with self._lock:
            # Load project
            project, todos = self.storage.load_project(task_project)
            
            # Remove task
            todos = [t for t in todos if t.id != task_id]
            
            # Save
            return self.storage.save_project(project, todos)
    
    def toggle_task_completion(
        self,
        user_id: str,
        task_id: int,
        project_name: Optional[str] = None
    ) -> Optional[Todo]:
        """Toggle task completion status
        
        Args:
            user_id: User ID
            task_id: Task ID
            project_name: Optional project hint
            
        Returns:
            Updated Todo object or None
        """
        task = self.get_task(user_id, task_id, project_name)
        if not task:
            return None
        
        new_status = (
            TodoStatus.COMPLETED
            if task.status != TodoStatus.COMPLETED
            else TodoStatus.PENDING
        )
        
        return self.update_task(
            user_id,
            task_id,
            project_name,
            status=new_status,
            completed=(new_status == TodoStatus.COMPLETED),
            completed_date=datetime.utcnow() if new_status == TodoStatus.COMPLETED else None
        )


# ============================================================================
# Singleton Instance
# ============================================================================

_storage_bridge: Optional[StorageBridge] = None


def get_storage_bridge() -> StorageBridge:
    """Get singleton storage bridge instance
    
    Returns:
        StorageBridge: Storage bridge instance
    """
    global _storage_bridge
    if _storage_bridge is None:
        _storage_bridge = StorageBridge()
    return _storage_bridge


def reset_storage_bridge():
    """Reset storage bridge (useful for testing)"""
    global _storage_bridge
    _storage_bridge = None
