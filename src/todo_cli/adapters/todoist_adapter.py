"""Todoist adapter for app synchronization.

This module provides integration with the Todoist API for bidirectional
synchronization of todo items, projects, labels, and due dates.
"""

import httpx
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

from ..app_sync_adapter import SyncAdapter, AuthenticationError, NetworkError, ValidationError, RateLimitError
from ..app_sync_models import (
    AppSyncProvider,
    AppSyncConfig,
    ExternalTodoItem,
    SyncDirection
)
from ..todo import Todo, Priority, TodoStatus
from ..utils.datetime import ensure_aware, now_utc


logger = logging.getLogger(__name__)


class TodoistAPI:
    """Todoist API client with comprehensive endpoint coverage."""
    
    BASE_URL = "https://api.todoist.com/rest/v2/"
    SYNC_BASE_URL = "https://api.todoist.com/sync/v9/"
    
    def __init__(self, api_token: str):
        """Initialize Todoist API client.
        
        Args:
            api_token: Todoist API token
        """
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=30.0)
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                           use_sync_api: bool = False) -> Dict[str, Any]:
        """Make HTTP request to Todoist API.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data
            use_sync_api: Whether to use Sync API instead of REST API
            
        Returns:
            Response data
            
        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limit is exceeded
            NetworkError: If network request fails
        """
        base_url = self.SYNC_BASE_URL if use_sync_api else self.BASE_URL
        url = urljoin(base_url, endpoint)
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url, headers=self.headers, params=data)
            elif method.upper() == "POST":
                response = await self.client.post(url, headers=self.headers, json=data)
            elif method.upper() == "PUT":
                response = await self.client.put(url, headers=self.headers, json=data)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid Todoist API token")
            elif response.status_code == 403:
                raise AuthenticationError("Todoist API access forbidden")
            elif response.status_code == 429:
                raise RateLimitError("Todoist API rate limit exceeded")
            elif response.status_code >= 400:
                error_msg = f"Todoist API error {response.status_code}: {response.text}"
                raise NetworkError(error_msg)
            
            if response.status_code == 204:  # No content
                return {}
            
            return response.json()
            
        except httpx.TimeoutException:
            raise NetworkError("Todoist API request timed out")
        except httpx.RequestError as e:
            raise NetworkError(f"Todoist API request failed: {e}")
    
    # Authentication & User Info
    
    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user information."""
        return await self._make_request("GET", "user", use_sync_api=True)
    
    # Projects
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects."""
        return await self._make_request("GET", "projects")
    
    async def create_project(self, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new project."""
        data = {"name": name, **kwargs}
        return await self._make_request("POST", "projects", data)
    
    # Tasks
    
    async def get_tasks(self, project_id: Optional[str] = None, 
                       label_id: Optional[str] = None,
                       filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tasks with optional filtering."""
        params = {}
        if project_id:
            params["project_id"] = project_id
        if label_id:
            params["label_id"] = label_id
        if filter_query:
            params["filter"] = filter_query
        
        return await self._make_request("GET", "tasks", params)
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        return await self._make_request("GET", f"tasks/{task_id}")
    
    async def create_task(self, content: str, **kwargs) -> Dict[str, Any]:
        """Create a new task."""
        data = {"content": content, **kwargs}
        return await self._make_request("POST", "tasks", data)
    
    async def update_task(self, task_id: str, **kwargs) -> Dict[str, Any]:
        """Update an existing task."""
        return await self._make_request("POST", f"tasks/{task_id}", kwargs)
    
    async def close_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        await self._make_request("POST", f"tasks/{task_id}/close")
        return True
    
    async def reopen_task(self, task_id: str) -> bool:
        """Reopen a completed task."""
        await self._make_request("POST", f"tasks/{task_id}/reopen")
        return True
    
    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        await self._make_request("DELETE", f"tasks/{task_id}")
        return True
    
    # Labels
    
    async def get_labels(self) -> List[Dict[str, Any]]:
        """Get all labels."""
        return await self._make_request("GET", "labels")
    
    async def create_label(self, name: str, **kwargs) -> Dict[str, Any]:
        """Create a new label."""
        data = {"name": name, **kwargs}
        return await self._make_request("POST", "labels", data)
    
    # Sync API for incremental updates
    
    async def sync(self, sync_token: str = "*", resource_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Sync data using Todoist Sync API for incremental updates."""
        data = {"sync_token": sync_token}
        if resource_types:
            data["resource_types"] = json.dumps(resource_types)
        
        return await self._make_request("POST", "sync", data, use_sync_api=True)


class TodoistAdapter(SyncAdapter):
    """Todoist adapter for app synchronization."""
    
    def __init__(self, config: AppSyncConfig):
        """Initialize Todoist adapter.
        
        Args:
            config: App sync configuration
        """
        super().__init__(config)
        self.api_token = config.get_credential("api_token")
        self.api: Optional[TodoistAPI] = None
        self._projects_cache: Dict[str, str] = {}  # name -> id
        self._labels_cache: Dict[str, str] = {}  # name -> id
        self._sync_token: Optional[str] = None
        
        # Todoist-specific settings
        self.default_project_id = config.get_setting("default_project_id")
        self.create_missing_projects = config.get_setting("create_missing_projects", True)
        self.create_missing_labels = config.get_setting("create_missing_labels", True)
        self.sync_completed_tasks = config.sync_completed_tasks
    
    def get_required_credentials(self) -> List[str]:
        """Get required credentials for Todoist."""
        return ["api_token"]
    
    def get_supported_features(self) -> List[str]:
        """Get features supported by Todoist adapter."""
        return [
            "create", "read", "update", "delete",
            "projects", "labels", "due_dates", "priorities",
            "descriptions", "subtasks", "recurring_dates",
            "filters", "collaboration"
        ]
    
    async def authenticate(self) -> bool:
        """Authenticate with Todoist API."""
        if not self.api_token:
            raise AuthenticationError("No Todoist API token provided")
        
        try:
            async with TodoistAPI(self.api_token) as api:
                user_info = await api.get_user_info()
                if user_info and "id" in user_info:
                    self.logger.info(f"Authenticated with Todoist as {user_info.get('full_name', 'Unknown User')}")
                    return True
                return False
                
        except AuthenticationError:
            self.logger.error("Todoist authentication failed - invalid API token")
            raise
        except Exception as e:
            self.logger.error(f"Todoist authentication failed: {e}")
            raise AuthenticationError(f"Failed to authenticate with Todoist: {e}")
    
    async def test_connection(self) -> bool:
        """Test connection to Todoist API."""
        try:
            return await self.authenticate()
        except Exception:
            return False
    
    async def fetch_items(self, since: Optional[datetime] = None) -> List[ExternalTodoItem]:
        """Fetch todo items from Todoist."""
        await self.ensure_authenticated()
        
        try:
            async with TodoistAPI(self.api_token) as api:
                self.api = api
                
                # Refresh caches
                await self._refresh_caches()
                
                # Get tasks
                if since and self._sync_token:
                    # Use incremental sync
                    sync_data = await api.sync(self._sync_token)
                    tasks = sync_data.get("items", [])
                    self._sync_token = sync_data.get("sync_token")
                else:
                    # Full sync
                    tasks = await api.get_tasks()
                    # Get sync token for future incremental syncs
                    sync_data = await api.sync("*", ["items"])
                    self._sync_token = sync_data.get("sync_token")
                
                external_items = []
                for task in tasks:
                    if not self._should_include_task(task):
                        continue
                    
                    try:
                        external_item = self.map_external_to_todo(task)
                        external_items.append(external_item)
                    except Exception as e:
                        self.logger.warning(f"Failed to map Todoist task {task.get('id')}: {e}")
                        continue
                
                self.logger.info(f"Fetched {len(external_items)} tasks from Todoist")
                return external_items
                
        except Exception as e:
            self.logger.error(f"Failed to fetch Todoist items: {e}")
            raise NetworkError(f"Failed to fetch from Todoist: {e}")
    
    async def create_item(self, todo: Todo) -> str:
        """Create a new item in Todoist."""
        await self.ensure_authenticated()
        
        try:
            async with TodoistAPI(self.api_token) as api:
                await self._refresh_caches()
                
                # Map to Todoist format
                task_data = self.map_todo_to_external(todo)
                
                # Create the task
                created_task = await api.create_task(**task_data)
                task_id = created_task["id"]
                
                self.log_sync_operation("create", f"Created task {task_id}: {todo.text}")
                return task_id
                
        except Exception as e:
            self.logger.error(f"Failed to create Todoist task: {e}")
            raise NetworkError(f"Failed to create in Todoist: {e}")
    
    async def update_item(self, external_id: str, todo: Todo) -> bool:
        """Update an existing item in Todoist."""
        await self.ensure_authenticated()
        
        try:
            async with TodoistAPI(self.api_token) as api:
                await self._refresh_caches()
                
                # Get current task to compare
                try:
                    current_task = await api.get_task(external_id)
                except Exception:
                    self.logger.warning(f"Task {external_id} not found in Todoist, cannot update")
                    return False
                
                # Map to Todoist format
                task_data = self.map_todo_to_external(todo)
                
                # Handle completion status change
                current_completed = current_task.get("is_completed", False)
                new_completed = todo.completed
                
                if current_completed != new_completed:
                    if new_completed:
                        await api.close_task(external_id)
                    else:
                        await api.reopen_task(external_id)
                
                # Update other fields if not completed
                if not new_completed:
                    # Remove completion-related fields from update data
                    update_data = {k: v for k, v in task_data.items() 
                                 if k not in ["is_completed"]}
                    
                    if update_data:
                        await api.update_task(external_id, **update_data)
                
                self.log_sync_operation("update", f"Updated task {external_id}: {todo.text}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to update Todoist task {external_id}: {e}")
            raise NetworkError(f"Failed to update in Todoist: {e}")
    
    async def delete_item(self, external_id: str) -> bool:
        """Delete an item from Todoist."""
        await self.ensure_authenticated()
        
        try:
            async with TodoistAPI(self.api_token) as api:
                await api.delete_task(external_id)
                self.log_sync_operation("delete", f"Deleted task {external_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete Todoist task {external_id}: {e}")
            return False
    
    async def fetch_projects(self) -> Dict[str, str]:
        """Fetch available projects from Todoist."""
        await self.ensure_authenticated()
        
        try:
            async with TodoistAPI(self.api_token) as api:
                projects = await api.get_projects()
                
                project_map = {}
                for project in projects:
                    project_map[project["name"]] = project["id"]
                
                return project_map
                
        except Exception as e:
            self.logger.error(f"Failed to fetch Todoist projects: {e}")
            return {}
    
    def map_todo_to_external(self, todo: Todo) -> Dict[str, Any]:
        """Map a local Todo to Todoist task format."""
        task_data = {
            "content": todo.text
        }
        
        # Description/notes
        if todo.notes:
            task_data["description"] = todo.notes
        
        # Due date
        if todo.due_date:
            # Todoist accepts various date formats
            task_data["due_string"] = todo.due_date.strftime("%Y-%m-%d %H:%M")
            if todo.due_date.time() == todo.due_date.time().replace(hour=23, minute=59, second=59, microsecond=0):
                # All-day task
                task_data["due_string"] = todo.due_date.strftime("%Y-%m-%d")
        
        # Priority mapping (Todoist: 1=low, 2=normal, 3=high, 4=urgent)
        priority_map = {
            Priority.LOW: 1,
            Priority.MEDIUM: 2,
            Priority.HIGH: 3,
            Priority.CRITICAL: 4
        }
        if todo.priority:
            task_data["priority"] = priority_map.get(todo.priority, 2)
        
        # Project
        project_id = self._get_project_id(todo.project)
        if project_id:
            task_data["project_id"] = project_id
        
        # Labels/tags
        if todo.tags:
            label_ids = []
            for tag in todo.tags:
                label_id = self._get_label_id(tag)
                if label_id:
                    label_ids.append(label_id)
            
            if label_ids:
                task_data["label_ids"] = label_ids
        
        return task_data
    
    def map_external_to_todo(self, external_data: Dict[str, Any]) -> ExternalTodoItem:
        """Map Todoist task data to ExternalTodoItem."""
        task = external_data
        
        # Parse due date with comprehensive timezone normalization
        due_date = None
        if task.get("due"):
            try:
                due_info = task["due"]
                if isinstance(due_info, dict) and "date" in due_info:
                    # Parse ISO format date
                    date_str = due_info["date"]
                    if "T" in date_str:
                        # Full datetime with timezone info
                        parsed_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                        due_date = ensure_aware(parsed_date)
                    else:
                        # All-day task - create timezone-aware datetime
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                            hour=23, minute=59, second=59, tzinfo=timezone.utc
                        )
                        due_date = ensure_aware(parsed_date)
            except Exception as e:
                self.logger.warning(f"Failed to parse due date from Todoist task: {e}")
        
        # Map priority (Todoist: 1=low, 2=normal, 3=high, 4=urgent)
        priority = task.get("priority", 2)
        
        # Get project name
        project_name = self._get_project_name(task.get("project_id", ""))
        
        # Get label names
        tags = []
        if task.get("label_ids"):
            for label_id in task["label_ids"]:
                label_name = self._get_label_name(label_id)
                if label_name:
                    tags.append(label_name)
        
        # Parse created and updated dates with timezone normalization
        created_at = None
        if task.get("created_at"):
            try:
                parsed_date = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
                created_at = ensure_aware(parsed_date)
            except Exception as e:
                self.logger.warning(f"Failed to parse created_at from Todoist task: {e}")
        
        # Fallback to current time if no created_at available
        if created_at is None:
            created_at = now_utc()
        
        updated_at = created_at  # Todoist doesn't provide separate updated_at
        
        # Completion info with timezone normalization
        completed = task.get("is_completed", False)
        completed_at = None
        if completed and task.get("completed_at"):
            try:
                parsed_date = datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00"))
                completed_at = ensure_aware(parsed_date)
            except Exception as e:
                self.logger.warning(f"Failed to parse completed_at from Todoist task: {e}")
        
        # Final validation: ensure all datetime fields are timezone-aware
        due_date = ensure_aware(due_date) if due_date else None
        created_at = ensure_aware(created_at) if created_at else None
        updated_at = ensure_aware(updated_at) if updated_at else None
        completed_at = ensure_aware(completed_at) if completed_at else None
        
        return ExternalTodoItem(
            external_id=str(task["id"]),
            provider=AppSyncProvider.TODOIST,
            title=task["content"],
            description=task.get("description", ""),
            due_date=due_date,
            priority=priority,
            tags=tags,
            project=project_name,
            project_id=task.get("project_id"),
            completed=completed,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=updated_at,
            parent_id=task.get("parent_id"),
            url=task.get("url"),
            raw_data=task
        )
    
    async def _refresh_caches(self):
        """Refresh projects and labels caches."""
        try:
            if not self.api:
                return
            
            # Refresh projects cache
            projects = await self.api.get_projects()
            self._projects_cache = {
                project["name"]: project["id"] for project in projects
            }
            
            # Refresh labels cache
            labels = await self.api.get_labels()
            self._labels_cache = {
                label["name"]: label["id"] for label in labels
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to refresh Todoist caches: {e}")
    
    def _get_project_id(self, project_name: str) -> Optional[str]:
        """Get Todoist project ID from name."""
        if not project_name:
            return self.default_project_id
        
        # Check mapping configuration first
        mapped_project = self.apply_project_mapping(project_name)
        if mapped_project != project_name:
            # Use mapped project name
            project_name = mapped_project
        
        # Look up in cache
        project_id = self._projects_cache.get(project_name)
        if project_id:
            return project_id
        
        # TODO: Optionally create missing project if configured
        if self.create_missing_projects and self.api:
            self.logger.info(f"Creating missing Todoist project: {project_name}")
            # This would need to be implemented as an async method call
        
        return self.default_project_id
    
    def _get_project_name(self, project_id: str) -> str:
        """Get project name from Todoist project ID."""
        if not project_id:
            return "Inbox"
        
        # Reverse lookup in cache
        for name, cached_id in self._projects_cache.items():
            if cached_id == project_id:
                # Apply reverse mapping
                return self.apply_reverse_project_mapping(name)
        
        return "Inbox"
    
    def _get_label_id(self, label_name: str) -> Optional[str]:
        """Get Todoist label ID from name."""
        if not label_name:
            return None
        
        # Check mapping configuration
        mapped_labels = self.apply_tag_mapping([label_name])
        if mapped_labels:
            label_name = mapped_labels[0]
        
        return self._labels_cache.get(label_name)
    
    def _get_label_name(self, label_id: str) -> Optional[str]:
        """Get label name from Todoist label ID."""
        if not label_id:
            return None
        
        # Reverse lookup in cache
        for name, cached_id in self._labels_cache.items():
            if cached_id == label_id:
                # Apply reverse mapping
                mapped_names = self.apply_reverse_tag_mapping([name])
                return mapped_names[0] if mapped_names else name
        
        return None
    
    def _should_include_task(self, task: Dict[str, Any]) -> bool:
        """Check if a task should be included in sync."""
        # Skip completed tasks if not configured to sync them
        if task.get("is_completed", False) and not self.sync_completed_tasks:
            return False
        
        # Skip archived/deleted tasks
        if task.get("is_deleted", False):
            return False
        
        return True